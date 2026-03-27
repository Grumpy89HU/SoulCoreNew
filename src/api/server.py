"""
SoulCore API szerver - Fő HTTP szerver + WebSocket
"""

import json
import time
import threading
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Dict, Any, Optional

from .handlers import APIHandlers, WebSocketHandler

# Middleware importok
from .middleware import (
    MiddlewareChain, AuthMiddleware, RateLimitMiddleware,
    LoggingMiddleware, CORSMiddleware, ErrorMiddleware, RequestIDMiddleware
)

logger = logging.getLogger(__name__)


class APIHandler(BaseHTTPRequestHandler):
    """API kérések kezelője"""
    
    # Route registry - dinamikus routing
    _routes = {
        'GET': {},
        'POST': {},
        'DELETE': {},
        'PUT': {}
    }
    
    @classmethod
    def route(cls, method, path):
        """Decorator a route regisztráláshoz"""
        def decorator(func):
            cls._routes[method][path] = func
            return func
        return decorator
    
    def __init__(self, *args, **kwargs):
        self.soulcore = kwargs.pop('soulcore', None)
        self.ws_handler = kwargs.pop('ws_handler', None)
        self.handlers = APIHandlers(self.soulcore)
        self.config = self.soulcore.config if self.soulcore else {}
        
        # Middleware lánc inicializálása
        self.middleware_chain = MiddlewareChain()
        self._init_middleware()
        
        self._setup_routes()
        super().__init__(*args, **kwargs)
    
    def _init_middleware(self):
        """Middleware-ek inicializálása a config alapján"""
        middleware_config = self.config.get('middleware', {})
        
        # Auth middleware konfiguráció
        auth_config = middleware_config.get('auth', {})
        # Alapértelmezett publikus path-ok (bővítve)
        default_public_paths = [
            '/health',
            '/api/status',
            '/api/chat',
            '/api/console/chat',
            '/api/conversations'
        ]
        if 'public_paths' not in auth_config:
            auth_config['public_paths'] = default_public_paths
        
        # Rate limit middleware konfiguráció (fejlesztéshez kikapcsolva)
        ratelimit_config = middleware_config.get('ratelimit', {})
        if self.config.get('system', {}).get('environment') == 'development':
            ratelimit_config.setdefault('enabled', False)
        
        # Sorrend fontos!
        middlewares = [
            ('request_id', RequestIDMiddleware, middleware_config.get('request_id', {})),
            ('logging', LoggingMiddleware, middleware_config.get('logging', {})),
            ('ratelimit', RateLimitMiddleware, ratelimit_config),
            ('auth', AuthMiddleware, auth_config),
            ('cors', CORSMiddleware, middleware_config.get('cors', {})),
            ('error', ErrorMiddleware, {
                'debug': self.config.get('system', {}).get('environment') == 'development',
                **middleware_config.get('error', {})
            })
        ]
        
        for name, cls, cfg in middlewares:
            if cfg.get('enabled', True):
                try:
                    self.middleware_chain.add(cls(cfg))
                except Exception as e:
                    logger.error(f"Middleware init error ({name}): {e}")
    
    def _build_request_object(self) -> Dict:
        """Egységes kérés objektum építése a middleware-ek számára"""
        parsed = urlparse(self.path)
        
        # Body beolvasása (POST/PUT esetén)
        body = {}
        if self.command in ['POST', 'PUT']:
            try:
                length = int(self.headers.get('Content-Length', 0))
                if length > 0:
                    body_str = self.rfile.read(length).decode('utf-8')
                    if body_str:
                        body = json.loads(body_str)
            except json.JSONDecodeError:
                body = {'_raw': body_str if 'body_str' in locals() else ''}
            except Exception as e:
                logger.error(f"Body read error: {e}")
        
        return {
            'method': self.command,
            'path': parsed.path,
            'query': parsed.query,
            'headers': dict(self.headers),
            'body': body,
            'client_ip': self.client_address[0] if self.client_address else 'unknown',
            'soulcore': self.soulcore
        }
    
    def _build_response_object(self, result: Any, status: int = 200) -> Dict:
        """
        Egységes válasz objektum építése.
        
        JAVÍTVA: biztonságos típusellenőrzés a 'status' mezőre.
        """
        # Ha a result már egy validációs hiba formátum (tuple)
        if isinstance(result, tuple) and len(result) == 2:
            result, status = result
        
        # Ha a result dict és van benne status mező
        if isinstance(result, dict) and 'status' in result:
            status_value = result.get('status')
            # Csak akkor használjuk a status mezőt, ha az integer
            if isinstance(status_value, int) and status_value >= 400:
                status = status_value
        
        return {
            'status': status,
            'headers': {},
            'body': result if isinstance(result, dict) else {'response': result}
        }
    
    def _process_through_middleware(self, request: Dict, handler_func) -> Dict:
        """Kérés feldolgozása a middleware láncon keresztül"""
        def final_handler(req):
            # Itt hívjuk meg a tényleges API végpontot
            return self._call_api_handler(req)
        
        return self.middleware_chain.process_request(request, final_handler)
    
    def _call_api_handler(self, request: Dict) -> Dict:
        """API végpont hívása a kérés alapján"""
        path = request.get('path', '')
        method = request.get('method', '')
        query = request.get('query', '')
        data = request.get('body', {})
        
        # WebSocket upgrade
        if path == '/ws':
            return self._handle_websocket_response(request)
        
        # Dinamikus path-ok kezelése
        if path.startswith('/api/conversations/') and path.endswith('/messages'):
            if method == 'GET':
                return self._handle_conversation_messages_get_response(path, query)
            elif method == 'POST':
                return self._handle_conversation_messages_post_response(path, data)
        
        # Route keresés
        routes = self._routes.get(method, {})
        handler = routes.get(path)
        
        if handler:
            try:
                if method == 'GET':
                    result = handler(query)
                else:
                    result = handler(data)
                return self._build_response_object(result)
            except Exception as e:
                logger.error(f"Handler error: {e}")
                return self._build_response_object({'error': str(e)}, 500)
        
        return self._build_response_object({'error': 'Not found'}, 404)
    
    def _handle_websocket_response(self, request: Dict) -> Dict:
        """WebSocket upgrade válasz"""
        if not self.ws_handler:
            return self._build_response_object({'error': 'WebSocket handler not available'}, 503)
        
        try:
            # WebSocket handshake
            self.ws_handler.handle_upgrade(self)
            # Ha sikeres, a kapcsolat már WebSocket módban van
            return {'_websocket_upgraded': True}
        except Exception as e:
            logger.error(f"WebSocket upgrade error: {e}")
            return self._build_response_object({'error': 'WebSocket upgrade failed'}, 500)
    
    def _handle_conversation_messages_get_response(self, path: str, query: str) -> Dict:
        """GET /api/conversations/{id}/messages válasz"""
        parts = path.split('/')
        if len(parts) >= 4:
            try:
                conv_id = int(parts[3])
                qs = parse_qs(query)
                result = self.handlers.get_messages(conv_id, qs)
                return self._build_response_object(result)
            except ValueError:
                return self._build_response_object({'error': 'Invalid conversation ID'}, 400)
        return self._build_response_object({'error': 'Missing conversation ID'}, 400)
    
    def _handle_conversation_messages_post_response(self, path: str, data: Dict) -> Dict:
        """POST /api/conversations/{id}/messages válasz"""
        parts = path.split('/')
        if len(parts) >= 4:
            try:
                conv_id = int(parts[3])
                result = self.handlers.add_message(conv_id, data)
                return self._build_response_object(result)
            except ValueError:
                return self._build_response_object({'error': 'Invalid conversation ID'}, 400)
        return self._build_response_object({'error': 'Missing conversation ID'}, 400)
    
    def _setup_routes(self):
        """Route-ok regisztrálása"""
        # GET routes
        self._routes['GET']['/api/status'] = self._get_status
        self._routes['GET']['/api/conversations'] = self._get_conversations
        self._routes['GET']['/api/models'] = self._get_models
        self._routes['GET']['/api/sentinel/status'] = self._get_sentinel_status
        self._routes['GET']['/api/king/state'] = self._get_king_state
        self._routes['GET']['/api/jester/diagnosis'] = self._get_jester_diagnosis
        self._routes['GET']['/api/heartbeat/state'] = self._get_heartbeat_state
        self._routes['GET']['/api/blackbox/search'] = self._get_blackbox_search
        self._routes['GET']['/api/config'] = self._get_config
        self._routes['GET']['/api/identity'] = self._get_identity
        self._routes['GET']['/health'] = self._get_health
        
        # POST routes
        self._routes['POST']['/api/chat'] = self._post_chat
        self._routes['POST']['/api/console/chat'] = self._post_console_chat
        self._routes['POST']['/api/conversations'] = self._post_conversations
        self._routes['POST']['/api/models/load'] = self._post_models_load
        self._routes['POST']['/api/models/unload'] = self._post_models_unload
        self._routes['POST']['/api/modules/start'] = self._post_modules_start
        self._routes['POST']['/api/modules/stop'] = self._post_modules_stop
        self._routes['POST']['/api/memory/remember'] = self._post_memory_remember
        self._routes['POST']['/api/memory/recall'] = self._post_memory_recall
        self._routes['POST']['/api/memory/clean'] = self._post_memory_clean
        self._routes['POST']['/api/config'] = self._post_config
        self._routes['POST']['/api/identity'] = self._post_identity
        self._routes['POST']['/api/king/parameters'] = self._post_king_parameters
        
        # DELETE routes
        self._routes['DELETE']['/api/conversations/'] = self._delete_conversation
        self._routes['DELETE']['/api/models/'] = self._delete_model
    
    # ========== HTTP METÓDUSOK ==========
    
    def do_GET(self):
        """GET kérések kezelése middleware láncon keresztül"""
        request = self._build_request_object()
        response = self._process_through_middleware(request, None)
        
        if response.get('_websocket_upgraded'):
            return  # WebSocket már kezeli a kapcsolatot
        
        self._send_response(response)
    
    def do_POST(self):
        """POST kérések kezelése middleware láncon keresztül"""
        request = self._build_request_object()
        response = self._process_through_middleware(request, None)
        self._send_response(response)
    
    def do_DELETE(self):
        """DELETE kérések kezelése middleware láncon keresztül"""
        request = self._build_request_object()
        response = self._process_through_middleware(request, None)
        self._send_response(response)
    
    def do_OPTIONS(self):
        """CORS preflight kezelése"""
        origins = self._get_allowed_origins()
        self.send_response(200)
        
        if '*' in origins:
            self.send_header('Access-Control-Allow-Origin', '*')
        else:
            referer = self.headers.get('Origin', '')
            if referer in origins:
                self.send_header('Access-Control-Allow-Origin', referer)
            else:
                self.send_header('Access-Control-Allow-Origin', origins[0] if origins else '*')
        
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.send_header('Access-Control-Max-Age', '86400')
        self.end_headers()
    
    def _send_response(self, response: Dict):
        """Válasz küldése"""
        status = response.get('status', 200)
        headers = response.get('headers', {})
        body = response.get('body', {})
        
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        
        # CORS fejlécek
        origins = self._get_allowed_origins()
        if '*' in origins:
            self.send_header('Access-Control-Allow-Origin', '*')
        else:
            referer = self.headers.get('Origin', '')
            if referer in origins:
                self.send_header('Access-Control-Allow-Origin', referer)
        
        # Egyéb fejlécek
        for key, value in headers.items():
            self.send_header(key, value)
        
        self.end_headers()
        
        # Válasz test
        if body:
            self.wfile.write(json.dumps(body, default=str).encode())
    
    # ========== GET HANDLEREK ==========
    
    def _get_status(self, query):
        return self.handlers.get_status()
    
    def _get_conversations(self, query):
        qs = parse_qs(query)
        return self.handlers.get_conversations(qs)
    
    def _get_models(self, query):
        return self.handlers.get_models()
    
    def _get_sentinel_status(self, query):
        return self.handlers.get_sentinel_status()
    
    def _get_king_state(self, query):
        return self.handlers.get_king_state()
    
    def _get_jester_diagnosis(self, query):
        return self.handlers.get_jester_diagnosis()
    
    def _get_heartbeat_state(self, query):
        return self.handlers.get_heartbeat_state()
    
    def _get_blackbox_search(self, query):
        qs = parse_qs(query)
        return self.handlers.search_blackbox(qs)
    
    def _get_config(self, query):
        return self.handlers.get_config()
    
    def _get_identity(self, query):
        return self.handlers.get_identity()
    
    def _get_health(self, query):
        return {'status': 'healthy', 'timestamp': time.time()}
    
    # ========== POST HANDLEREK ==========
    
    def _post_chat(self, data):
        return self.handlers.post_chat(data)
    
    def _post_console_chat(self, data):
        """Konzol chat végpont - CLI és tesztelés"""
        return self.handlers.console_chat(data)
    
    def _post_conversations(self, data):
        return self.handlers.create_conversation(data)
    
    def _post_models_load(self, data):
        return self.handlers.load_model(data)
    
    def _post_models_unload(self, data):
        return self.handlers.unload_model(data)
    
    def _post_modules_start(self, data):
        return self.handlers.start_module(data)
    
    def _post_modules_stop(self, data):
        return self.handlers.stop_module(data)
    
    def _post_memory_remember(self, data):
        return self.handlers.remember_memory(data)
    
    def _post_memory_recall(self, data):
        return self.handlers.recall_memory(data)
    
    def _post_memory_clean(self, data):
        return self.handlers.clean_memory(data)
    
    def _post_config(self, data):
        return self.handlers.update_config(data)
    
    def _post_identity(self, data):
        return self.handlers.update_identity(data)
    
    def _post_king_parameters(self, data):
        return self.handlers.set_king_parameters(data)
    
    # ========== DELETE HANDLEREK ==========
    
    def _delete_conversation(self, conv_id, path):
        if conv_id:
            return self.handlers.delete_conversation(conv_id)
        return {'error': 'Invalid conversation ID'}, 400
    
    def _delete_model(self, model_id, path):
        if model_id:
            return self.handlers.delete_model(model_id)
        return {'error': 'Invalid model ID'}, 400
    
    # ========== SEGÉDFÜGGVÉNYEK ==========
    
    def _get_allowed_origins(self) -> list:
        """CORS engedélyezett origin-ök a configból"""
        if self.soulcore and hasattr(self.soulcore, 'config'):
            security = self.soulcore.config.get('system_settings', {}).get('security', {})
            return security.get('allowed_origins', ['*'])
        return ['*']
    
    def log_message(self, format, *args):
        logger.debug(f"{self.address_string()} - {format % args}")


class APIServer:
    """API szerver (HTTP + WebSocket)"""
    
    def __init__(self, soulcore, host=None, http_port=None, ws_port=None):
        self.soulcore = soulcore
        self.config = soulcore.config if soulcore else {}
        
        # Portok a configból (hardkód eltávolítva)
        api_config = self.config.get('api', {})
        self.host = host or api_config.get('host', '0.0.0.0')
        self.http_port = http_port or api_config.get('port', 5001)
        self.ws_port = ws_port or api_config.get('ws_port', 5002)
        
        self.http_server = None
        self.ws_handler = None
        self.http_thread = None
        self.ws_thread = None
        
        # WebSocket handler (ha elérhető)
        if WebSocketHandler:
            try:
                self.ws_handler = WebSocketHandler(self.soulcore, self.host, self.ws_port)
            except Exception as e:
                logger.error(f"WebSocket handler init error: {e}")
                self.ws_handler = None
    
    def start(self):
        """Szerver indítása (blokkoló)"""
        # WebSocket indítása külön szálban
        if self.ws_handler:
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
            try:
                self.ws_handler.stop()
            except Exception as e:
                logger.error(f"WebSocket stop error: {e}")
        
        if self.http_server:
            try:
                self.http_server.shutdown()
                self.http_server.server_close()
            except Exception as e:
                logger.error(f"HTTP server stop error: {e}")
        
        print("🛑 API szerver leállítva")