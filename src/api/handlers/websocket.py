"""
WebSocket handler a valós idejű kommunikációhoz
RFC 6455 compliant WebSocket szerver
"""

import json
import threading
import time
import logging
import socket
import hashlib
import base64
from typing import Dict, Set, Optional, Callable
from dataclasses import dataclass, field
from queue import Queue

logger = logging.getLogger(__name__)


@dataclass
class WebSocketConnection:
    """WebSocket kapcsolat adatai"""
    client_id: str
    socket: socket.socket
    address: str
    connected_at: float
    last_activity: float
    send_queue: Queue = field(default_factory=Queue)
    subscribed_topics: set = field(default_factory=set)


class WebSocketHandler:
    """
    WebSocket kapcsolatok kezelője
    RFC 6455 szerinti implementáció
    """
    
    # WebSocket opkódok
    OP_CONTINUATION = 0x0
    OP_TEXT = 0x1
    OP_BINARY = 0x2
    OP_CLOSE = 0x8
    OP_PING = 0x9
    OP_PONG = 0xA
    
    def __init__(self, soulcore, host='0.0.0.0', port=5002):
        self.soulcore = soulcore
        self.host = host
        self.port = port
        self.connections: Dict[str, WebSocketConnection] = {}
        self.connection_lock = threading.RLock()
        self.running = False
        self.server_socket: Optional[socket.socket] = None
        self.accept_thread: Optional[threading.Thread] = None
        self.send_threads: Dict[str, threading.Thread] = {}
        
        # Esemény callback-ek
        self.on_message_callbacks: Dict[str, Callable] = {}
        self.on_connect_callbacks: list = []
        self.on_disconnect_callbacks: list = []
        
        # King callback
        self.king_callback_set = False
    
    # ========== SZERVER INDÍTÁS/LEÁLLÍTÁS ==========
    
    def start(self):
        """WebSocket szerver indítása"""
        if self.running:
            return
        
        self.running = True
        
        # Szerver socket létrehozása
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(100)
        self.server_socket.settimeout(1.0)
        
        # Fogadó szál indítása
        self.accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        self.accept_thread.start()
        
        # King callback beállítása
        self._setup_king_callback()
        
        print(f"🔌 WebSocket szerver: ws://{self.host}:{self.port}")
    
    def stop(self):
        """WebSocket szerver leállítása"""
        self.running = False
        
        # Kapcsolatok lezárása
        with self.connection_lock:
            for conn_id in list(self.connections.keys()):
                self._close_connection(conn_id)
        
        # Szerver socket lezárása
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
        # Szálak megvárása
        if self.accept_thread:
            self.accept_thread.join(timeout=2.0)
        
        print("🔌 WebSocket szerver leállítva")
    
    def _setup_king_callback(self):
        """King válasz callback beállítása"""
        if not self.soulcore or not hasattr(self.soulcore, 'king'):
            return
        
        king = self.soulcore.king
        
        def king_response_callback(response_text, conversation_id, trace_id):
            """King válaszának továbbítása a WebSocket-en"""
            self.broadcast_to_conversation(conversation_id, {
                'type': 'chat:response',
                'text': response_text,
                'conversation_id': conversation_id,
                'trace_id': trace_id,
                'timestamp': time.time()
            })
        
        if hasattr(king, 'set_response_callback'):
            king.set_response_callback(king_response_callback)
            self.king_callback_set = True
            logger.info("🔌 King callback beállítva a WebSocket-hez")
    
    # ========== KAPCSOLAT KEZELÉS ==========
    
    def _accept_loop(self):
        """Új kapcsolatok fogadása"""
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                client_socket.settimeout(30.0)
                
                # Kapcsolat kezelése külön szálban
                conn_thread = threading.Thread(
                    target=self._handle_connection,
                    args=(client_socket, address),
                    daemon=True
                )
                conn_thread.start()
                
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logger.error(f"WebSocket accept hiba: {e}")
    
    def _handle_connection(self, client_socket: socket.socket, address):
        """WebSocket kapcsolat kezelése"""
        try:
            # WebSocket handshake
            handshake = client_socket.recv(4096).decode('utf-8')
            if not self._perform_handshake(client_socket, handshake):
                client_socket.close()
                return
            
            # Kapcsolat regisztrálása
            client_id = f"ws_{int(time.time())}_{address[1]}"
            
            conn = WebSocketConnection(
                client_id=client_id,
                socket=client_socket,
                address=f"{address[0]}:{address[1]}",
                connected_at=time.time(),
                last_activity=time.time(),
                send_queue=Queue()
            )
            
            with self.connection_lock:
                self.connections[client_id] = conn
            
            # Kapcsolódási esemény
            for callback in self.on_connect_callbacks:
                try:
                    callback(client_id, conn.address)
                except:
                    pass
            
            logger.info(f"🔌 WebSocket kapcsolódás: {client_id} ({conn.address})")
            
            # Üdvözlő üzenet
            self._send_text(client_id, {
                'type': 'connected',
                'client_id': client_id,
                'timestamp': time.time()
            })
            
            # Küldő szál indítása
            send_thread = threading.Thread(
                target=self._send_loop,
                args=(client_id,),
                daemon=True
            )
            send_thread.start()
            
            with self.connection_lock:
                self.send_threads[client_id] = send_thread
            
            # Fogadó ciklus
            self._receive_loop(client_id, client_socket)
            
        except Exception as e:
            logger.error(f"WebSocket kezelési hiba: {e}")
        finally:
            self._close_connection(client_id)
    
    def _perform_handshake(self, client_socket: socket.socket, handshake: str) -> bool:
        """WebSocket handshake végrehajtása"""
        try:
            lines = handshake.split('\r\n')
            headers = {}
            
            for line in lines[1:]:
                if ': ' in line:
                    key, value = line.split(': ', 1)
                    headers[key] = value
            
            # WebSocket key ellenőrzése
            ws_key = headers.get('Sec-WebSocket-Key')
            if not ws_key:
                return False
            
            # Accept key generálása
            accept_key = base64.b64encode(
                hashlib.sha1((ws_key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
            ).decode()
            
            # Válasz küldése
            response = (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept_key}\r\n"
                "\r\n"
            )
            client_socket.send(response.encode())
            
            return True
            
        except Exception as e:
            logger.error(f"WebSocket handshake hiba: {e}")
            return False
    
    def _receive_loop(self, client_id: str, client_socket: socket.socket):
        """Üzenetek fogadása"""
        while self.running and client_id in self.connections:
            try:
                data = client_socket.recv(4096)
                if not data:
                    break
                
                frames = self._parse_frames(data)
                for opcode, payload in frames:
                    self._handle_frame(client_id, opcode, payload)
                
                with self.connection_lock:
                    if client_id in self.connections:
                        self.connections[client_id].last_activity = time.time()
                
            except socket.timeout:
                continue
            except Exception as e:
                logger.error(f"WebSocket receive hiba {client_id}: {e}")
                break
    
    def _send_loop(self, client_id: str):
        """Üzenetek küldése"""
        while self.running and client_id in self.connections:
            try:
                conn = self.connections.get(client_id)
                if not conn:
                    break
                
                try:
                    message = conn.send_queue.get(timeout=0.5)
                except:
                    continue
                
                # Üzenet küldése - JAVÍTVA: payload bytes legyen
                payload = json.dumps(message).encode('utf-8')
                frame = self._create_frame(self.OP_TEXT, payload)
                conn.socket.send(frame)
                
            except Exception as e:
                logger.error(f"WebSocket send hiba {client_id}: {e}")
                break
    
    def _handle_frame(self, client_id: str, opcode: int, payload: bytes):
        """WebSocket frame feldolgozása"""
        
        if opcode == self.OP_TEXT:
            try:
                data = json.loads(payload.decode('utf-8'))
                self._handle_message(client_id, data)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON from {client_id}")
            except Exception as e:
                logger.error(f"Message handling error: {e}")
                
        elif opcode == self.OP_PING:
            # Ping -> Pong válasz
            self._send_frame(client_id, self.OP_PONG, payload)
            
        elif opcode == self.OP_CLOSE:
            self._close_connection(client_id)
    
    def _handle_message(self, client_id: str, data: Dict):
        """Üzenet feldolgozása"""
        msg_type = data.get('type', '')
        
        if msg_type == 'chat:message':
            text = data.get('text', '')
            conv_id = data.get('conversation_id', 1)
            
            if text:
                if self.soulcore and hasattr(self.soulcore, 'king') and self.soulcore.king:
                    try:
                        self.soulcore.king.generate_response(text, conv_id)
                        logger.info(f"📨 WebSocket: Üzenet a Kingnek: {text[:50]}...")
                    except Exception as e:
                        logger.error(f"King hiba: {e}")
                        self._send_text(client_id, {
                            'type': 'chat:error',
                            'error': str(e),
                            'timestamp': time.time()
                        })
        
        elif msg_type == 'subscribe':
            topic = data.get('topic', '')
            if topic:
                with self.connection_lock:
                    if client_id in self.connections:
                        self.connections[client_id].subscribed_topics.add(topic)
        
        elif msg_type == 'unsubscribe':
            topic = data.get('topic', '')
            if topic:
                with self.connection_lock:
                    if client_id in self.connections:
                        self.connections[client_id].subscribed_topics.discard(topic)
        
        for callback in self.on_message_callbacks.values():
            try:
                callback(client_id, data)
            except:
                pass
    
    def _parse_frames(self, data: bytes) -> list:
        """WebSocket frame-ek feldolgozása"""
        frames = []
        i = 0
        length = len(data)
        
        while i < length:
            byte1 = data[i]
            byte2 = data[i + 1]
            
            fin = (byte1 & 0x80) != 0
            opcode = byte1 & 0x0F
            masked = (byte2 & 0x80) != 0
            payload_len = byte2 & 0x7F
            
            i += 2
            
            if payload_len == 126:
                payload_len = int.from_bytes(data[i:i+2], 'big')
                i += 2
            elif payload_len == 127:
                payload_len = int.from_bytes(data[i:i+8], 'big')
                i += 8
            
            mask = None
            if masked:
                mask = data[i:i+4]
                i += 4
            
            payload = data[i:i+payload_len]
            i += payload_len
            
            if mask:
                payload = bytes([payload[j] ^ mask[j % 4] for j in range(len(payload))])
            
            frames.append((opcode, payload))
        
        return frames
    
    def _create_frame(self, opcode: int, payload: bytes) -> bytes:
        """WebSocket frame létrehozása - JAVÍTVA: payload már bytes"""
        frame = bytearray()
        
        frame.append(0x80 | opcode)
        
        length = len(payload)
        if length < 126:
            frame.append(length)
        elif length < 65536:
            frame.append(126)
            frame.extend(length.to_bytes(2, 'big'))
        else:
            frame.append(127)
            frame.extend(length.to_bytes(8, 'big'))
        
        frame.extend(payload)
        
        return bytes(frame)
    
    def _send_frame(self, client_id: str, opcode: int, payload: bytes):
        """Frame küldése"""
        with self.connection_lock:
            conn = self.connections.get(client_id)
            if not conn:
                return
        
        try:
            frame = self._create_frame(opcode, payload)
            conn.socket.send(frame)
        except Exception as e:
            logger.error(f"Send frame hiba {client_id}: {e}")
            self._close_connection(client_id)
    
    def _send_text(self, client_id: str, data: Dict):
        """Szöveges üzenet küldése"""
        conn = self.connections.get(client_id)
        if conn:
            conn.send_queue.put(data)
    
    def _close_connection(self, client_id: str):
        """Kapcsolat lezárása"""
        with self.connection_lock:
            conn = self.connections.pop(client_id, None)
            send_thread = self.send_threads.pop(client_id, None)
        
        if conn:
            try:
                frame = self._create_frame(self.OP_CLOSE, b'')
                conn.socket.send(frame)
            except:
                pass
            
            try:
                conn.socket.close()
            except:
                pass
            
            for callback in self.on_disconnect_callbacks:
                try:
                    callback(client_id, conn.address)
                except:
                    pass
            
            logger.info(f"🔌 WebSocket lecsatlakozás: {client_id}")
    
    # ========== PUBLIKUS API ==========
    
    def broadcast(self, data: Dict, topic: str = None):
        """Üzenet küldése minden kapcsolatnak"""
        with self.connection_lock:
            for client_id, conn in self.connections.items():
                if topic is None or topic in conn.subscribed_topics:
                    conn.send_queue.put(data)
    
    def send_to(self, client_id: str, data: Dict):
        """Üzenet küldése adott kliensnek"""
        with self.connection_lock:
            conn = self.connections.get(client_id)
            if conn:
                conn.send_queue.put(data)
    
    def broadcast_to_conversation(self, conversation_id: int, data: Dict):
        """Üzenet küldése egy beszélgetés résztvevőinek"""
        self.broadcast(data)
    
    def broadcast_telemetry(self, telemetry_data: Dict):
        """Telemetria adatok broadcast-olása"""
        self.broadcast({
            'type': 'telemetry:update',
            'data': telemetry_data,
            'timestamp': time.time()
        }, topic='telemetry')
    
    def broadcast_notification(self, notification: Dict):
        """Értesítés broadcast-olása"""
        self.broadcast({
            'type': 'notification',
            'notification': notification,
            'timestamp': time.time()
        }, topic='notifications')
    
    def on_message(self, handler: Callable):
        """Üzenetkezelő regisztrálása"""
        callback_id = f"callback_{len(self.on_message_callbacks)}"
        self.on_message_callbacks[callback_id] = handler
        return callback_id
    
    def on_connect(self, callback: Callable):
        """Kapcsolódási eseménykezelő"""
        self.on_connect_callbacks.append(callback)
    
    def on_disconnect(self, callback: Callable):
        """Lecsatlakozási eseménykezelő"""
        self.on_disconnect_callbacks.append(callback)
    
    def get_connections(self) -> Dict:
        """Aktív kapcsolatok listája"""
        with self.connection_lock:
            return {
                client_id: {
                    'address': conn.address,
                    'connected_at': conn.connected_at,
                    'last_activity': conn.last_activity,
                    'subscribed_topics': list(conn.subscribed_topics)
                }
                for client_id, conn in self.connections.items()
            }
    
    def get_connection_count(self) -> int:
        """Aktív kapcsolatok száma"""
        with self.connection_lock:
            return len(self.connections)