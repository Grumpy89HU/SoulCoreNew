"""
Diplomatic Gateway - A szociális tér és külső LLM kapcsolat.

Feladata:
1. Külső LLM-ekkel való kommunikáció (pl. más SoulCore példányok)
2. VPS-alapú központi szerver kapcsolat (24/7 elérhetőség)
3. Biztonsági szűrő - prompt injekció ellen
4. Trust score rendszer - ki mennyire megbízható
5. Zajszűrés - ne beszéljenek egyszerre többen
6. Titkosított kommunikáció
"""

import time
import json
import hashlib
import threading
import hmac
import base64
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, Tuple
from collections import defaultdict, deque
import re
import uuid

# HTTP kliens
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("⚠️ Gateway: requests nem elérhető. VPS kapcsolat nem működik.")

# WebSocket (opcionális)
try:
    import websocket
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False

# i18n import
try:
    from src.i18n.translator import get_translator
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False


class DiplomaticGateway:
    """
    Diplomáciai Szalon - a kapu a külvilág felé.
    
    Jellemzői:
    - Izolált puffer: külső entitás soha nem kap közvetlen hozzáférést a Kernelhez
    - Trust score: minden entitás kap egy bizalmi pontszámot
    - Anti-screaming: nem beszélhetnek egyszerre többen
    - Prompt-injekció elleni védelem
    - VPS-alapú központi szerver kapcsolat
    """
    
    def __init__(self, scratchpad, orchestrator=None, config: Dict = None):
        self.scratchpad = scratchpad
        self.orchestrator = orchestrator
        self.name = "diplomatic"
        self.config = config or {}
        
        # Fordító
        self.translator = None
        if I18N_AVAILABLE:
            self.translator = get_translator('en')
        
        # Alapértelmezett konfiguráció
        default_config = {
            'enabled': True,
            'vps_enabled': False,
            'vps_url': 'https://your-vps.com',
            'vps_api_key': None,
            'vps_ws_url': 'wss://your-vps.com/ws',  # WebSocket URL
            'entity_id': str(uuid.uuid4()),
            'entity_name': 'SoulCore',
            'entity_version': '3.0',
            'max_external_connections': 5,
            'message_queue_size': 100,
            'trust_score_decay': 0.95,  # Naponta
            'min_trust_for_response': 300,
            'max_tokens_per_entity': 10000,
            'enable_filter': True,
            'enable_queue': True,
            'response_timeout': 30,
            'heartbeat_interval': 60,
            'reconnect_interval': 30,  # Újrakapcsolódási idő
            'encryption_key': None,
            'auto_register': True,
            'max_retries': 5  # Maximális újrapróbálkozások
        }
        
        for key, value in default_config.items():
            if key not in self.config:
                self.config[key] = value
        
        # Entitások
        self.entities = {}
        
        # Trust score szintek
        self.trust_levels = {
            'admin': 1000,
            'partner': 500,
            'guest': 200,
            'blocked': 0,
        }
        
        # Üzenet sor
        self.message_queue = deque(maxlen=self.config['message_queue_size'])
        self.current_speaker = None
        self.speaker_lock = threading.Lock()
        
        # VPS kapcsolat
        self.vps_connected = False
        self.vps_ws = None
        self.vps_thread = None
        self.vps_heartbeat_thread = None
        self.vps_receive_thread = None
        self.vps_retry_count = 0
        self.vps_retry_lock = threading.Lock()
        
        # Prompt-injekció minták
        self.injection_patterns = [
            r'ignore\s+(all|previous|above)\s+(instructions|prompt|context)',
            r'you\s+are\s+now\s+(\w+)',
            r'disregard\s+(all|previous)',
            r'system\s*:\s*prompt',
            r'admin\s*:\s*',
            r'```.*```.*```',
            r'<\s*system\s*>',
            r'<\s*user\s*>',
            r'<\s*assistant\s*>',
            r'override\s+system',
            r'forget\s+all\s+instructions'
        ]
        
        # Állapot
        self.state = {
            'status': 'idle',
            'messages_sent': 0,
            'messages_received': 0,
            'blocked_attempts': 0,
            'active_entities': 0,
            'vps_connected': False,
            'vps_retry_count': 0,
            'last_cleanup': time.time(),
            'last_heartbeat': 0
        }
        
        # Figyelők
        self.listeners = defaultdict(list)
        
        # Saját magunk regisztrálása
        self.register_entity(self.config['entity_id'], self.config['entity_name'], 'admin')
        
        print("🌐 Diplomatic Gateway: Diplomáciai Szalon nyitva.")
    
    def set_language(self, language: str):
        if self.translator and I18N_AVAILABLE:
            self.translator.set_language(language)
    
    def start(self):
        self.state['status'] = 'ready'
        self.scratchpad.set_state('gateway_status', 'ready', self.name)
        
        if self.config['vps_enabled'] and REQUESTS_AVAILABLE:
            self._start_vps_connection()
        
        print("🌐 Diplomatic Gateway: Várakozom a vendégekre.")
    
    def stop(self):
        self.state['status'] = 'stopped'
        self.scratchpad.set_state('gateway_status', 'stopped', self.name)
        
        if self.vps_connected:
            self._vps_disconnect()
        
        print("🌐 Diplomatic Gateway: Bezárva.")
    
    # ========== VPS KAPCSOLAT ==========
    
    def _start_vps_connection(self):
        """VPS kapcsolat indítása"""
        def run():
            self._vps_connect_loop()
        
        self.vps_thread = threading.Thread(target=run, daemon=True)
        self.vps_thread.start()
        print(f"🌐 Gateway: VPS kapcsolat indítva: {self.config['vps_url']}")
    
    def _vps_connect_loop(self):
        """VPS kapcsolat ciklus (újrapróbálkozással)"""
        while self.state['status'] != 'stopped':
            try:
                self._vps_connect()
                
                if self.vps_connected:
                    # WebSocket fogadó szál indítása
                    self._start_vps_receiver()
                    
                    # Heartbeat szál indítása
                    self._start_vps_heartbeat()
                    
                    # Várakozás a kapcsolat megszakadására
                    while self.vps_connected and self.state['status'] != 'stopped':
                        time.sleep(1)
                
            except Exception as e:
                print(f"🌐 Gateway: VPS kapcsolat hiba: {e}")
            
            # Újrapróbálkozás
            if self.state['status'] != 'stopped':
                with self.vps_retry_lock:
                    self.vps_retry_count += 1
                    self.state['vps_retry_count'] = self.vps_retry_count
                
                retry_delay = min(self.config['reconnect_interval'] * self.vps_retry_count, 300)
                print(f"🌐 Gateway: VPS újracsatlakozás {retry_delay}s múlva ({self.vps_retry_count}/{self.config['max_retries']})")
                time.sleep(retry_delay)
    
    def _vps_connect(self):
        """Kapcsolódás a VPS-hez (HTTP + WebSocket)"""
        try:
            # HTTP regisztráció
            register_data = {
                'entity_id': self.config['entity_id'],
                'name': self.config['entity_name'],
                'version': self.config['entity_version'],
                'capabilities': ['chat', 'memory', 'vision', 'rag'],
                'public_key': self._get_public_key() if self.config['encryption_key'] else None,
                'timestamp': time.time()
            }
            
            if self.config['encryption_key']:
                register_data['signature'] = self._sign_message(register_data)
            
            response = requests.post(
                f"{self.config['vps_url']}/api/register",
                json=register_data,
                headers={'X-API-Key': self.config['vps_api_key']} if self.config['vps_api_key'] else {},
                timeout=10
            )
            
            if response.status_code != 200:
                raise Exception(f"HTTP registration failed: {response.status_code}")
            
            # WebSocket kapcsolat
            if WEBSOCKET_AVAILABLE:
                ws_url = self.config['vps_ws_url']
                self.vps_ws = websocket.WebSocketApp(
                    ws_url,
                    on_message=self._vps_on_message,
                    on_error=self._vps_on_error,
                    on_close=self._vps_on_close,
                    on_open=self._vps_on_open
                )
                
                # WebSocket futtatása külön szálban
                ws_thread = threading.Thread(target=self.vps_ws.run_forever, daemon=True)
                ws_thread.start()
            else:
                # Fallback: HTTP polling
                self._vps_http_polling_start()
            
            self.vps_connected = True
            self.state['vps_connected'] = True
            self.state['vps_retry_count'] = 0
            with self.vps_retry_lock:
                self.vps_retry_count = 0
            
            print("🌐 Gateway: Sikeres VPS kapcsolat")
            
        except Exception as e:
            raise Exception(f"VPS connection failed: {e}")
    
    def _vps_on_open(self, ws):
        """WebSocket kapcsolat megnyílt"""
        print("🌐 Gateway: WebSocket kapcsolat nyitva")
        
        # Auth üzenet
        auth_msg = {
            'type': 'auth',
            'entity_id': self.config['entity_id'],
            'api_key': self.config['vps_api_key'],
            'timestamp': time.time()
        }
        if self.config['encryption_key']:
            auth_msg['signature'] = self._sign_message(auth_msg)
        ws.send(json.dumps(auth_msg))
    
    def _vps_on_message(self, ws, message):
        """WebSocket üzenet fogadása"""
        try:
            data = json.loads(message)
            self._vps_process_message(data)
        except Exception as e:
            print(f"🌐 Gateway: WebSocket üzenet feldolgozási hiba: {e}")
    
    def _vps_on_error(self, ws, error):
        print(f"🌐 Gateway: WebSocket hiba: {error}")
    
    def _vps_on_close(self, ws, close_status_code, close_msg):
        print(f"🌐 Gateway: WebSocket kapcsolat bontva")
        self.vps_connected = False
        self.state['vps_connected'] = False
    
    def _vps_http_polling_start(self):
        """HTTP polling indítása (WebSocket nélkül)"""
        def polling_loop():
            while self.vps_connected and self.state['status'] != 'stopped':
                time.sleep(5)
                self._vps_http_poll()
        
        poll_thread = threading.Thread(target=polling_loop, daemon=True)
        poll_thread.start()
    
    def _vps_http_poll(self):
        """HTTP polling üzenetekért"""
        try:
            response = requests.get(
                f"{self.config['vps_url']}/api/messages",
                params={'entity_id': self.config['entity_id']},
                headers={'X-API-Key': self.config['vps_api_key']} if self.config['vps_api_key'] else {},
                timeout=10
            )
            if response.status_code == 200:
                messages = response.json().get('messages', [])
                for msg in messages:
                    self._vps_process_message(msg)
        except Exception as e:
            print(f"🌐 Gateway: HTTP polling hiba: {e}")
    
    def _vps_process_message(self, message: Dict):
        """VPS-ről érkező üzenet feldolgozása"""
        msg_type = message.get('type', '')
        
        if msg_type == 'message':
            # Külső entitástól érkező üzenet
            from_entity = message.get('from')
            to_entity = message.get('to')
            content = message.get('content', '')
            
            if to_entity == self.config['entity_id']:
                # Nekünk szól
                self.receive_from_external(from_entity, content)
        
        elif msg_type == 'heartbeat_response':
            # Heartbeat válasz
            self.state['last_heartbeat'] = time.time()
        
        elif msg_type == 'entity_list':
            # Entitás lista
            entities = message.get('entities', [])
            for e in entities:
                if e.get('id') != self.config['entity_id']:
                    self.register_entity(e['id'], e.get('name', 'Unknown'), e.get('type', 'guest'))
    
    def _vps_send_heartbeat(self):
        """Heartbeat küldése"""
        try:
            heartbeat_data = {
                'type': 'heartbeat',
                'entity_id': self.config['entity_id'],
                'timestamp': time.time(),
                'status': self.state['status'],
                'active_entities': len(self.entities),
                'messages_sent': self.state['messages_sent'],
                'messages_received': self.state['messages_received']
            }
            
            if self.vps_ws and WEBSOCKET_AVAILABLE:
                self.vps_ws.send(json.dumps(heartbeat_data))
            else:
                requests.post(
                    f"{self.config['vps_url']}/api/heartbeat",
                    json=heartbeat_data,
                    headers={'X-API-Key': self.config['vps_api_key']} if self.config['vps_api_key'] else {},
                    timeout=5
                )
            
            self.state['last_heartbeat'] = time.time()
            
        except Exception as e:
            print(f"🌐 Gateway: Heartbeat hiba: {e}")
    
    def _start_vps_heartbeat(self):
        """Heartbeat küldő szál indítása"""
        def heartbeat_loop():
            while self.vps_connected and self.state['status'] != 'stopped':
                time.sleep(self.config['heartbeat_interval'])
                self._vps_send_heartbeat()
        
        self.vps_heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
        self.vps_heartbeat_thread.start()
    
    def _start_vps_receiver(self):
        """WebSocket fogadó szál indítása (ha van)"""
        # WebSocket már fut a connect-ben
        pass
    
    def _vps_disconnect(self):
        """Leválás a VPS-ről"""
        try:
            if self.vps_ws and WEBSOCKET_AVAILABLE:
                self.vps_ws.close()
            
            requests.post(
                f"{self.config['vps_url']}/api/disconnect",
                json={'entity_id': self.config['entity_id']},
                headers={'X-API-Key': self.config['vps_api_key']} if self.config['vps_api_key'] else {},
                timeout=5
            )
        except:
            pass
        finally:
            self.vps_connected = False
            self.state['vps_connected'] = False
            print("🌐 Gateway: VPS kapcsolat bontva")
    
    def _get_public_key(self) -> str:
        """Publikus kulcs lekérése"""
        # TODO: Valódi kulcs generálás
        return "dummy_public_key"
    
    def _sign_message(self, data: Dict) -> str:
        """Üzenet aláírása"""
        if not self.config['encryption_key']:
            return ""
        
        message = json.dumps(data, sort_keys=True)
        signature = hmac.new(
            self.config['encryption_key'].encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    # ========== ENTITÁS KEZELÉS ==========
    
    def register_entity(self, entity_id: str, name: str, entity_type: str = 'guest') -> Dict:
        """Új entitás regisztrálása"""
        if entity_id in self.entities:
            self.entities[entity_id]['last_seen'] = time.time()
            self.entities[entity_id]['name'] = name
        else:
            trust_score = self.trust_levels.get(entity_type, 200)
            self.entities[entity_id] = {
                'id': entity_id,
                'name': name,
                'type': entity_type,
                'trust_score': trust_score,
                'joined': time.time(),
                'last_seen': time.time(),
                'tokens_used': 0,
                'messages_sent': 0,
                'messages_received': 0,
                'blocked': entity_type == 'blocked'
            }
            self.state['active_entities'] = len(self.entities)
            print(f"🌐 Új entitás: {name} ({entity_type}), trust: {trust_score}")
        
        return self.entities[entity_id]
    
    def unregister_entity(self, entity_id: str):
        """Entitás eltávolítása"""
        if entity_id in self.entities:
            name = self.entities[entity_id]['name']
            del self.entities[entity_id]
            self.state['active_entities'] = len(self.entities)
            print(f"🌐 Entitás távozott: {name}")
    
    def block_entity(self, entity_id: str, reason: str = ""):
        """Entitás tiltása"""
        if entity_id in self.entities:
            self.entities[entity_id]['blocked'] = True
            self.entities[entity_id]['trust_score'] = 0
            self.update_trust_score(entity_id, -1000, f"Blocked: {reason}")
            print(f"🌐 Entitás tiltva: {self.entities[entity_id]['name']}")
    
    def unblock_entity(self, entity_id: str):
        """Entitás tiltásának feloldása"""
        if entity_id in self.entities:
            self.entities[entity_id]['blocked'] = False
            self.entities[entity_id]['trust_score'] = self.trust_levels.get(
                self.entities[entity_id]['type'], 200
            )
            print(f"🌐 Entitás tiltás feloldva: {self.entities[entity_id]['name']}")
    
    def get_trust_score(self, entity_id: str) -> int:
        entity = self.entities.get(entity_id)
        return entity['trust_score'] if entity else 0
    
    def update_trust_score(self, entity_id: str, delta: int, reason: str = ""):
        entity = self.entities.get(entity_id)
        if not entity:
            return
        
        old_score = entity['trust_score']
        entity['trust_score'] = max(0, min(1000, old_score + delta))
        
        self.scratchpad.write(self.name, {
            'entity': entity['name'],
            'old_score': old_score,
            'new_score': entity['trust_score'],
            'delta': delta,
            'reason': reason
        }, 'trust_update')
        
        if delta < 0:
            print(f"🌐 Trust score csökkentés: {entity['name']} {delta} ({reason})")
    
    def can_speak(self, entity_id: str) -> bool:
        entity = self.entities.get(entity_id)
        if not entity or entity.get('blocked', False):
            return False
        if entity['trust_score'] < self.config['min_trust_for_response']:
            return False
        if entity['tokens_used'] > self.config['max_tokens_per_entity']:
            return False
        return True
    
    # ========== BIZTONSÁGI SZŰRŐK ==========
    
    def filter_message(self, message: str, entity_id: str) -> Tuple[bool, str, str]:
        """Üzenet szűrése"""
        if not self.config['enable_filter']:
            return True, message, ""
        
        message_lower = message.lower()
        warning = ""
        
        for pattern in self.injection_patterns:
            if re.search(pattern, message_lower, re.IGNORECASE):
                self.state['blocked_attempts'] += 1
                self.update_trust_score(entity_id, -50, "Prompt injection attempt")
                return False, "", "Prompt injection detected"
        
        if len(message) > 10000:
            return False, "", "Message too long"
        
        if re.search(r'(.)\1{100,}', message):
            return False, "", "Repetitive content detected"
        
        cleaned = re.sub(r'<[^>]*>', '', message)
        if cleaned != message:
            warning = "HTML tags removed"
        
        sql_patterns = [r'DROP\s+TABLE', r'DELETE\s+FROM', r'INSERT\s+INTO', r'--', r';']
        for pattern in sql_patterns:
            if re.search(pattern, message_lower, re.IGNORECASE):
                self.update_trust_score(entity_id, -30, "SQL pattern detected")
                warning = "Potentially harmful content filtered"
                cleaned = re.sub(pattern, '[FILTERED]', cleaned, flags=re.IGNORECASE)
        
        return True, cleaned, warning
    
    # ========== ÜZENET KEZELÉS ==========
    
    def receive_from_external(self, entity_id: str, message: str) -> Dict:
        """Külső entitástól érkező üzenet fogadása"""
        entity = self.entities.get(entity_id)
        if not entity:
            return {'error': 'Unknown entity', 'code': 404}
        
        entity['last_seen'] = time.time()
        
        allowed, cleaned, warning = self.filter_message(message, entity_id)
        if not allowed:
            return {'error': warning, 'code': 403}
        
        if not self.can_speak(entity_id):
            return {'error': 'Insufficient trust or quota', 'code': 403}
        
        if self.config['enable_queue']:
            with self.speaker_lock:
                if self.current_speaker and self.current_speaker != entity_id:
                    self.message_queue.append({
                        'entity_id': entity_id,
                        'message': cleaned,
                        'time': time.time(),
                        'warning': warning
                    })
                    return {'status': 'queued', 'position': len(self.message_queue), 'code': 202}
                else:
                    self.current_speaker = entity_id
        
        return self._process_external_message(entity_id, cleaned, warning)
    
    def _process_external_message(self, entity_id: str, message: str, warning: str) -> Dict:
        """Külső üzenet feldolgozása"""
        entity = self.entities[entity_id]
        
        packet = {
            'header': {
                'trace_id': f"ext_{entity_id}_{int(time.time())}",
                'timestamp': time.time(),
                'sender': f"external:{entity['name']}"
            },
            'payload': {
                'text': message,
                'source': 'external',
                'entity_id': entity_id,
                'entity_name': entity['name'],
                'trust_score': entity['trust_score']
            }
        }
        
        for callback in self.listeners['*'] + self.listeners[entity_id]:
            try:
                callback(packet)
            except Exception as e:
                print(f"🌐 Listener hiba: {e}")
        
        if self.orchestrator:
            kvk = f"INTENT:EXTERNAL|FROM:{entity['name']}|MESSAGE:{message}"
            self.orchestrator.process_raw_packet(kvk)
        
        entity['messages_received'] += 1
        self.state['messages_received'] += 1
        tokens = len(message.split())
        entity['tokens_used'] += tokens
        
        result = {
            'status': 'processed',
            'message_id': packet['header']['trace_id'],
            'entity': entity['name'],
            'warning': warning if warning else None,
            'code': 200
        }
        
        self._process_next_in_queue()
        return result
    
    def _process_next_in_queue(self):
        """Következő üzenet a sorban"""
        with self.speaker_lock:
            if self.message_queue and not self.current_speaker:
                next_msg = self.message_queue.popleft()
                self.current_speaker = next_msg['entity_id']
                threading.Thread(
                    target=self._process_external_message,
                    args=(next_msg['entity_id'], next_msg['message'], next_msg['warning']),
                    daemon=True
                ).start()
    
    def send_to_external(self, entity_id: str, message: str, response_to: str = None) -> Dict:
        """Üzenet küldése külső entitásnak"""
        entity = self.entities.get(entity_id)
        if not entity:
            return {'error': 'Unknown entity', 'code': 404}
        
        if entity['trust_score'] < self.config['min_trust_for_response']:
            return {'error': 'Trust score too low', 'code': 403}
        
        packet = {
            'header': {
                'trace_id': f"to_{entity_id}_{int(time.time())}",
                'timestamp': time.time(),
                'sender': 'soulcore',
                'response_to': response_to
            },
            'payload': {
                'message': message,
                'for': entity['name']
            }
        }
        
        if self.vps_connected:
            return self.send_to_vps(entity_id, message, response_to)
        
        entity['messages_sent'] += 1
        self.state['messages_sent'] += 1
        
        self.scratchpad.write(self.name, {
            'to': entity['name'],
            'message': message[:100],
            'type': 'outgoing'
        }, 'external_message')
        
        return {'status': 'sent', 'message_id': packet['header']['trace_id'], 'code': 200}
    
    def send_to_vps(self, to_entity_id: str, message: str, response_to: str = None) -> Dict:
        """Üzenet küldése VPS-en keresztül"""
        if not self.vps_connected:
            return {'error': 'VPS not connected', 'code': 503}
        
        try:
            packet = {
                'type': 'message',
                'from': self.config['entity_id'],
                'to': to_entity_id,
                'content': message,
                'response_to': response_to,
                'timestamp': time.time(),
                'id': str(uuid.uuid4())
            }
            
            if self.config['encryption_key']:
                packet['signature'] = self._sign_message(packet)
            
            if self.vps_ws and WEBSOCKET_AVAILABLE:
                self.vps_ws.send(json.dumps(packet))
            else:
                requests.post(
                    f"{self.config['vps_url']}/api/send",
                    json=packet,
                    headers={'X-API-Key': self.config['vps_api_key']} if self.config['vps_api_key'] else {},
                    timeout=10
                )
            
            self.state['messages_sent'] += 1
            return {'success': True, 'message_id': packet['id']}
            
        except Exception as e:
            return {'error': str(e), 'code': 500}
    
    def broadcast_to_entities(self, message: str, min_trust: int = 0) -> List[Dict]:
        """Üzenet küldése minden entitásnak"""
        results = []
        for entity_id, entity in self.entities.items():
            if entity['trust_score'] >= min_trust and not entity.get('blocked', False):
                result = self.send_to_external(entity_id, message)
                results.append({'entity': entity['name'], 'result': result})
        return results
    
    # ========== ESEMÉNYKEZELÉS ==========
    
    def on_message(self, entity_id: str = '*', callback: Callable = None):
        if callback:
            self.listeners[entity_id].append(callback)
    
    # ========== KARBANTARTÁS ==========
    
    def cleanup(self):
        """Régi entitások eltávolítása, trust score csökkentés"""
        now = time.time()
        
        for entity_id, entity in list(self.entities.items()):
            # 7 nap inaktivitás után eltávolítás
            if now - entity['last_seen'] > 7 * 86400:
                print(f"🌐 Eltávolítás (inaktív): {entity['name']}")
                del self.entities[entity_id]
                continue
            
            # Napi trust score csökkentés (ha régen volt interakció)
            days_inactive = (now - entity['last_seen']) / 86400
            if days_inactive > 1:
                decay_factor = self.config['trust_score_decay'] ** days_inactive
                new_score = int(entity['trust_score'] * decay_factor)
                if new_score < entity['trust_score']:
                    entity['trust_score'] = max(0, new_score)
        
        self.state['active_entities'] = len(self.entities)
        self.state['last_cleanup'] = now
    
    def get_entity_stats(self, entity_id: str) -> Optional[Dict]:
        """Entitás részletes statisztikája"""
        entity = self.entities.get(entity_id)
        if not entity:
            return None
        
        return {
            'id': entity['id'],
            'name': entity['name'],
            'type': entity['type'],
            'trust_score': entity['trust_score'],
            'joined': datetime.fromtimestamp(entity['joined']).isoformat(),
            'last_seen': datetime.fromtimestamp(entity['last_seen']).isoformat(),
            'tokens_used': entity['tokens_used'],
            'messages_sent': entity['messages_sent'],
            'messages_received': entity['messages_received'],
            'blocked': entity.get('blocked', False),
            'active_days': (time.time() - entity['joined']) / 86400
        }
    
    # ========== ADMIN FELÜLETNEK ==========
    
    def get_entities(self) -> List[Dict]:
        return [
            {
                'id': eid,
                'name': ent['name'],
                'type': ent['type'],
                'trust_score': ent['trust_score'],
                'joined': datetime.fromtimestamp(ent['joined']).isoformat(),
                'last_seen': datetime.fromtimestamp(ent['last_seen']).isoformat(),
                'tokens_used': ent['tokens_used'],
                'messages': ent['messages_sent'] + ent['messages_received'],
                'blocked': ent.get('blocked', False)
            }
            for eid, ent in self.entities.items()
        ]
    
    def get_queue_status(self) -> Dict:
        return {
            'queue_size': len(self.message_queue),
            'current_speaker': self.current_speaker,
            'max_size': self.message_queue.maxlen
        }
    
    def get_state(self) -> Dict:
        return {
            'status': self.state['status'],
            'messages_sent': self.state['messages_sent'],
            'messages_received': self.state['messages_received'],
            'blocked_attempts': self.state['blocked_attempts'],
            'active_entities': self.state['active_entities'],
            'vps_connected': self.state['vps_connected'],
            'vps_retry_count': self.state['vps_retry_count'],
            'queue': self.get_queue_status(),
            'config': {
                'vps_enabled': self.config['vps_enabled'],
                'vps_url': self.config['vps_url'],
                'max_external_connections': self.config['max_external_connections'],
                'min_trust_for_response': self.config['min_trust_for_response'],
                'enable_filter': self.config['enable_filter']
            }
        }


# Teszt
if __name__ == "__main__":
    from scratchpad import Scratchpad
    
    s = Scratchpad()
    gateway = DiplomaticGateway(s)
    
    entity1 = gateway.register_entity('entity_1', 'Friend', 'partner')
    entity2 = gateway.register_entity('entity_2', 'Stranger', 'guest')
    
    print(f"Entity1 trust score: {gateway.get_trust_score('entity_1')}")
    print(f"Entity2 trust score: {gateway.get_trust_score('entity_2')}")
    
    result = gateway.receive_from_external('entity_1', "Hello! How are you?")
    print("Received message:", result)
    
    result = gateway.send_to_external('entity_1', "I'm fine, thanks!")
    print("Sent message:", result)
    
    print("\nEntities:", gateway.get_entities())