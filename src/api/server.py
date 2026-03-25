"""
SoulCore API szerver - Fő HTTP szerver + WebSocket
"""

import json
import time
import threading
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from .handlers import APIHandlers, WebSocketHandler

logger = logging.getLogger(__name__)


class APIHandler(BaseHTTPRequestHandler):
    """API kérések kezelője"""
    
    def __init__(self, *args, **kwargs):
        self.soulcore = kwargs.pop('soulcore', None)
        self.ws_handler = kwargs.pop('ws_handler', None)
        self.handlers = APIHandlers(self.soulcore)
        super().__init__(*args, **kwargs)
    
    # ========== HTTP METÓDUSOK ==========
    
    def do_GET(self):
        """GET kérések kezelése"""
        parsed = urlparse(self.path)
        path = parsed.path
        
        # WebSocket upgrade
        if path == '/ws':
            self._handle_websocket()
            return
        
        # API végpontok
        self._handle_api_get(path, parsed.query)
    
    def _handle_websocket(self):
        """WebSocket upgrade kezelése"""
        # WebSocket handshake-t a WebSocketHandler végzi
        # Itt csak továbbítjuk a socket-et
        pass
    
    def _handle_api_get(self, path: str, query: str):
        """API GET végpontok"""
        qs = parse_qs(query)
        
        if path == '/api/status':
            self._send_json(self.handlers.get_status())
        elif path == '/api/conversations':
            self._send_json(self.handlers.get_conversations(qs))
        elif path == '/api/models':
            self._send_json(self.handlers.get_models())
        elif path == '/api/sentinel/status':
            self._send_json(self.handlers.get_sentinel_status())
        elif path == '/api/king/state':
            self._send_json(self.handlers.get_king_state())
        elif path == '/api/jester/diagnosis':
            self._send_json(self.handlers.get_jester_diagnosis())
        elif path == '/api/heartbeat/state':
            self._send_json(self.handlers.get_heartbeat_state())
        elif path == '/api/blackbox/search':
            self._send_json(self.handlers.search_blackbox(qs))
        elif path == '/api/config':
            self._send_json(self.handlers.get_config())
        elif path == '/api/identity':
            self._send_json(self.handlers.get_identity())
        elif path == '/health':
            self._send_json({'status': 'healthy', 'timestamp': time.time()})
        else:
            self.send_error(404, "Not found")
    
    def do_POST(self):
        """POST kérések kezelése"""
        parsed = urlparse(self.path)
        path = parsed.path
        
        # Body beolvasása
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode('utf-8') if length > 0 else '{}'
        
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._send_error(400, "Invalid JSON")
            return
        
        # API végpontok
        if path == '/api/chat':
            self._send_json(self.handlers.post_chat(data))
        elif path == '/api/conversations':
            self._send_json(self.handlers.create_conversation(data))
        elif path == '/api/models/load':
            self._send_json(self.handlers.load_model(data))
        elif path == '/api/models/unload':
            self._send_json(self.handlers.unload_model(data))
        elif path == '/api/modules/start':
            self._send_json(self.handlers.start_module(data))
        elif path == '/api/modules/stop':
            self._send_json(self.handlers.stop_module(data))
        elif path == '/api/memory/remember':
            self._send_json(self.handlers.remember_memory(data))
        elif path == '/api/memory/recall':
            self._send_json(self.handlers.recall_memory(data))
        elif path == '/api/memory/clean':
            self._send_json(self.handlers.clean_memory(data))
        elif path == '/api/config':
            self._send_json(self.handlers.update_config(data))
        elif path == '/api/identity':
            self._send_json(self.handlers.update_identity(data))
        elif path == '/api/king/parameters':
            self._send_json(self.handlers.set_king_parameters(data))
        else:
            self._send_error(404, "Not found")
    
    def do_DELETE(self):
        """DELETE kérések kezelése"""
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path.startswith('/api/conversations/'):
            parts = path.split('/')
            if len(parts) >= 3:
                try:
                    conv_id = int(parts[2])
                    self._send_json(self.handlers.delete_conversation(conv_id))
                except ValueError:
                    self._send_error(400, "Invalid conversation ID")
        elif path.startswith('/api/models/'):
            parts = path.split('/')
            if len(parts) >= 3:
                try:
                    model_id = int(parts[2])
                    self._send_json(self.handlers.delete_model(model_id))
                except ValueError:
                    self._send_error(400, "Invalid model ID")
        else:
            self._send_error(404, "Not found")
    
    # ========== SEGÉDFÜGGVÉNYEK ==========
    
    def _send_json(self, data, status=200):
        """JSON válasz küldése"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())
    
    def _send_error(self, message, status=400):
        """Hiba válasz küldése"""
        self._send_json({'error': message, 'status': status}, status)
    
    def do_OPTIONS(self):
        """CORS preflight"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def log_message(self, format, *args):
        logger.debug(f"{self.address_string()} - {format % args}")


class APIServer:
    """API szerver (HTTP + WebSocket)"""
    
    def __init__(self, soulcore, host='0.0.0.0', http_port=6000, ws_port=6001):
        self.soulcore = soulcore
        self.host = host
        self.http_port = http_port
        self.ws_port = ws_port
        self.http_server = None
        self.ws_handler = None
        self.http_thread = None
        self.ws_thread = None
    
    def start(self):
        """Szerver indítása"""
        # WebSocket handler
        self.ws_handler = WebSocketHandler(self.soulcore, self.host, self.ws_port)
        self.ws_thread = threading.Thread(target=self.ws_handler.start, daemon=True)
        self.ws_thread.start()
        
        # HTTP szerver
        def handler(*args, **kwargs):
            return APIHandler(*args, soulcore=self.soulcore, ws_handler=self.ws_handler, **kwargs)
        
        self.http_server = HTTPServer((self.host, self.http_port), handler)
        
        print(f"🌐 SoulCore API szerver indul:")
        print(f"   HTTP: http://{self.host}:{self.http_port}")
        print(f"   WebSocket: ws://{self.host}:{self.ws_port}")
        print(f"   King: {'✅' if self.soulcore and hasattr(self.soulcore, 'king') and self.soulcore.king else '❌'}")
        
        try:
            self.http_server.serve_forever()
        except KeyboardInterrupt:
            self.stop()
    
    def start_in_thread(self):
        """Szerver indítása külön szálban"""
        self.http_thread = threading.Thread(target=self.start, daemon=True)
        self.http_thread.start()
        return self.http_thread
    
    def stop(self):
        """Szerver leállítása"""
        if self.ws_handler:
            self.ws_handler.stop()
        
        if self.http_server:
            self.http_server.shutdown()
            self.http_server.server_close()
        
        print("🛑 API szerver leállítva")