"""
Web App - A Vár ablaka.
Flask + Vue.js alapú felület, WebSocket kapcsolattal.

Funkciók:
- REST API beszélgetésekhez, promptokhoz, beállításokhoz
- Socket.IO valós idejű kommunikáció
- Admin felület modulvezérléssel
- Képfeltöltés (Eye-Core)
- Modell paraméterek állítása
- Beszélgetés előzmények
- Többnyelvű támogatás (i18n)
- Többszintű hozzáférési rendszer (admin, user)
- Audit log
- Teljesítmény metrikák
- Rate limiting
"""

import os
import time
import json
import threading
import uuid
import secrets
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from functools import wraps
from collections import defaultdict
from typing import Dict 

from flask import Flask, render_template, send_from_directory, request, jsonify, session, g, redirect, url_for
from flask_socketio import SocketIO, emit, join_room, leave_room

# i18n import
try:
    from src.i18n.translator import get_translator
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    print("⚠️ Web: i18n nem elérhető, angol alapértelmezettel futok.")

# Projekt gyökér
ROOT_DIR = Path(__file__).parent.parent.parent

class WebApp:
    """
    Web felület.
    - Flask backend
    - Socket.IO valós idejű kommunikáció
    - Vue.js frontend (single file)
    - REST API az adatbázishoz
    - Admin felület
    - Többnyelvű támogatás
    - Rate limiting és biztonság
    """
    
    def __init__(self, modules):
        self.modules = modules  # az összes modul (orchestrator, king, stb)
        self.name = "web"
        self.system_id = getattr(self.modules.get('main', None), 'system_id', 'unknown')
        
        # Flask app
        self.app = Flask(__name__, 
                        template_folder=str(ROOT_DIR / 'src' / 'web' / 'templates'),
                        static_folder=str(ROOT_DIR / 'src' / 'web' / 'static'))
        
        # Titkos kulcs session-ökhöz
        self.app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
        
        # Fordító (alapértelmezett angol)
        self.translator = None
        if I18N_AVAILABLE:
            self.translator = get_translator('en')
        
        # Socket.IO
        self.socketio = SocketIO(self.app, cors_allowed_origins="*", ping_timeout=60, ping_interval=25)
        
        # Szál
        self.thread = None
        self.running = False
        
        # Aktív kapcsolatok
        self.connected_clients = {}
        
        # Admin jelszó (környezeti változóból vagy alapértelmezett)
        self.admin_password = os.environ.get('ADMIN_PASSWORD', 'soulcore2026')
        
        # Rate limiting
        self.rate_limits = defaultdict(list)  # IP -> [timestampek]
        self.rate_limit_requests = 100  # Maximum 100 kérés
        self.rate_limit_window = 60  # 60 másodperc alatt
        
        # Session timeout
        self.session_timeout = 30 * 60  # 30 perc
        
        # Nyelv beállítása kérésenként
        self._setup_before_request()
        
        # Útvonalak beállítása
        self._setup_routes()
        
        # Socket események
        self._setup_socket_events()
        
        print("🌐 Web: Ablak nyílik.")
    
    def _setup_before_request(self):
        """Kérés előtti nyelvbeállítás és rate limiting"""
        @self.app.before_request
        def before_request():
            # Rate limiting
            client_ip = request.remote_addr
            now = time.time()
            
            # Régi bejegyzések törlése
            self.rate_limits[client_ip] = [
                t for t in self.rate_limits[client_ip]
                if now - t < self.rate_limit_window
            ]
            
            # Limit ellenőrzés
            if len(self.rate_limits[client_ip]) >= self.rate_limit_requests:
                return jsonify({
                    'error': 'Rate limit exceeded. Please slow down.'
                }), 429
            
            self.rate_limits[client_ip].append(now)
            
            # Session timeout ellenőrzés
            if session.get('user_id'):
                last_active = session.get('last_active', 0)
                if now - last_active > self.session_timeout:
                    session.clear()
                else:
                    session['last_active'] = now
            
            # Nyelv beállítása
            lang = session.get('language', request.headers.get('Accept-Language', 'en')[:2])
            if lang not in ['en', 'hu']:
                lang = 'en'
            g.language = lang
            if self.translator:
                self.translator.set_language(lang)
    
    def _get_message(self, key: str, **kwargs) -> str:
        """Üzenet lekérése i18n-ből"""
        if self.translator and I18N_AVAILABLE:
            return self.translator.get(key, **kwargs)
        return key
    
    def _audit_log(self, action: str, resource: str = None, details: Dict = None):
        """Audit log bejegyzés"""
        try:
            db = self.modules.get('database')
            if db:
                with db.lock:
                    conn = db._get_connection()
                    conn.execute("""
                        INSERT INTO audit_log (user_id, action, resource, details, ip_address)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        session.get('user_id'),
                        action,
                        resource,
                        json.dumps(details) if details else None,
                        request.remote_addr
                    ))
                    conn.commit()
                    conn.close()
        except Exception as e:
            print(f"🌐 Web: Audit log hiba: {e}")
    
    def _login_required(self, f):
        """Dekorátor a bejelentkezés ellenőrzéséhez"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get('user_id'):
                return jsonify({'error': self._get_message('errors.unauthorized')}), 401
            return f(*args, **kwargs)
        return decorated_function
    
    def _admin_required(self, f):
        """Dekorátor az admin jogosultság ellenőrzéséhez"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get('admin'):
                return jsonify({'error': self._get_message('errors.unauthorized')}), 403
            return f(*args, **kwargs)
        return decorated_function
    
    # ------------------------------------------------------------------------
    # ROUTES - REST API
    # ------------------------------------------------------------------------
    
    def _setup_routes(self):
        """Flask útvonalak - REST API"""
        
        # --- FŐOLDAL ---
        
        @self.app.route('/')
        def index():
            """Főoldal"""
            return render_template('index.html', 
                                  language=g.get('language', 'en'),
                                  gettext=self._get_message)
        
        @self.app.route('/admin')
        @self._admin_required
        def admin_panel():
            """Admin panel (külön oldal)"""
            return render_template('admin.html', language=g.get('language', 'en'))
        
        @self.app.route('/login', methods=['GET', 'POST'])
        def login():
            """Bejelentkezés"""
            if request.method == 'GET':
                return render_template('login.html', language=g.get('language', 'en'))
            
            data = request.get_json() or {}
            password = data.get('password')
            
            if password == self.admin_password:
                session['admin'] = True
                session['login_time'] = time.time()
                session['user_id'] = 1  # Alapértelmezett user ID
                self._audit_log('login', 'user', {'method': 'password'})
                return {'success': True, 'message': self._get_message('ui.login_success')}
            
            self._audit_log('login_failed', 'user', {'ip': request.remote_addr})
            return {'success': False, 'message': self._get_message('errors.unauthorized')}, 401
        
        @self.app.route('/logout', methods=['POST'])
        def logout():
            """Kijelentkezés"""
            self._audit_log('logout', 'user', {'user_id': session.get('user_id')})
            session.clear()
            return {'success': True, 'message': self._get_message('ui.logout_success')}
        
        @self.app.route('/api/session')
        def get_session():
            """Session állapot lekérése"""
            return {
                'is_admin': session.get('admin', False),
                'login_time': session.get('login_time'),
                'user_id': session.get('user_id'),
                'language': g.get('language', 'en')
            }
        
        @self.app.route('/api/language', methods=['POST'])
        def set_language():
            """Nyelv beállítása"""
            data = request.get_json() or {}
            lang = data.get('language', 'en')
            if lang in ['en', 'hu']:
                session['language'] = lang
                if self.translator:
                    self.translator.set_language(lang)
                return {'success': True, 'language': lang}
            return {'success': False, 'message': 'Invalid language'}, 400
        
        # --- RENDSZER STÁTUSZ ---
        
        @self.app.route('/api/status')
        def status():
            """Rendszer státusz (REST)"""
            heartbeat = self.modules.get('heartbeat', {})
            return {
                'status': 'running',
                'modules': list(self.modules.keys()),
                'time': time.time(),
                'uptime': heartbeat.get_state().get('uptime_seconds', 0) if heartbeat else 0,
                'version': '3.0',
                'name': 'SoulCore',
                'system_id': self.system_id[:8] if self.system_id else 'unknown',
                'clients': len(self.connected_clients)
            }
        
        @self.app.route('/api/king/state')
        def king_state():
            """Király állapota"""
            king = self.modules.get('king')
            if king:
                return king.get_state()
            return {'error': self._get_message('errors.model_not_loaded')}, 404
        
        @self.app.route('/api/king/metrics')
        def king_metrics():
            """Király metrikák"""
            king = self.modules.get('king')
            if king and hasattr(king, 'get_metrics'):
                return king.get_metrics()
            return {'error': 'King metrics not available'}, 404
        
        @self.app.route('/api/jester/diagnosis')
        def jester_diagnosis():
            """Bohóc diagnózis"""
            jester = self.modules.get('jester')
            if jester and hasattr(jester, 'get_diagnosis'):
                return jester.get_diagnosis()
            return {'error': 'Jester not available'}, 404
        
        @self.app.route('/api/sentinel/status')
        def sentinel_status():
            """Hardver állapot"""
            sentinel = self.modules.get('sentinel')
            if sentinel:
                return {
                    'gpus': sentinel.get_gpu_status(),
                    'slots': sentinel.get_slots(),
                    'state': sentinel.get_state(),
                    'throttle_factor': sentinel.get_throttle_factor()
                }
            return {'error': 'Sentinel not available'}, 404
        
        @self.app.route('/api/blackbox/stats')
        def blackbox_stats():
            """Naplózás statisztikák"""
            blackbox = self.modules.get('blackbox')
            if blackbox:
                return blackbox.get_stats()
            return {'error': 'BlackBox not available'}, 404
        
        @self.app.route('/api/blackbox/trace/<trace_id>')
        def blackbox_trace(trace_id):
            """Egy trace lekérése"""
            blackbox = self.modules.get('blackbox')
            if blackbox:
                return {'trace': blackbox.get_trace(trace_id)}
            return {'error': 'BlackBox not available'}, 404
        
        @self.app.route('/api/blackbox/search')
        def blackbox_search():
            """Keresés a naplókban"""
            blackbox = self.modules.get('blackbox')
            if not blackbox:
                return {'error': 'BlackBox not available'}, 404
            
            query = request.args.get('q', '')
            limit = request.args.get('limit', 50, type=int)
            
            # Összes esemény lekérése (nincs limit paraméter)
            all_events = blackbox.replay()  # <-- nincs limit paraméter
            
            # Keresés a szövegben
            results = []
            for e in all_events:
                if query.lower() in str(e.get('content', '')).lower():
                    results.append(e)
                if len(results) >= limit:
                    break
            
            return {'results': results}
        
        # --- BESZÉLGETÉSEK API ---
        
        @self.app.route('/api/conversations', methods=['GET'])
        @self._login_required
        def get_conversations():
            """Beszélgetések listázása"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            limit = request.args.get('limit', 50, type=int)
            offset = request.args.get('offset', 0, type=int)
            
            user_id = session.get('user_id')
            convs = db.get_conversations(limit=limit, offset=offset, user_id=user_id)
            return {'conversations': convs, 'total': len(convs)}
        
        @self.app.route('/api/conversations', methods=['POST'])
        @self._login_required
        def create_conversation():
            """Új beszélgetés létrehozása"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            data = request.get_json() or {}
            user_id = session.get('user_id')
            
            conv_id = db.create_conversation(
                title=data.get('title', f"Conversation {datetime.now().strftime('%Y-%m-%d %H:%M')}"),
                model=data.get('model'),
                system_prompt=data.get('system_prompt'),
                metadata=data.get('metadata'),
                user_id=user_id
            )
            
            self._audit_log('create_conversation', 'conversation', {'id': conv_id})
            return {'id': conv_id, 'success': True}
        
        @self.app.route('/api/conversations/<int:conv_id>', methods=['GET'])
        @self._login_required
        def get_conversation(conv_id):
            """Egy beszélgetés adatai"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            conv = db.get_conversation(conv_id)
            if not conv:
                return {'error': self._get_message('errors.not_found', resource='Conversation')}, 404
            
            # Ellenőrizzük, hogy a felhasználó tulajdona-e
            if conv.get('user_id') != session.get('user_id') and not session.get('admin'):
                return {'error': self._get_message('errors.unauthorized')}, 403
            
            return conv
        
        @self.app.route('/api/conversations/<int:conv_id>', methods=['PUT'])
        @self._login_required
        def update_conversation(conv_id):
            """Beszélgetés frissítése"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            data = request.get_json() or {}
            db.update_conversation(conv_id, **data)
            self._audit_log('update_conversation', 'conversation', {'id': conv_id})
            return {'success': True}
        
        @self.app.route('/api/conversations/<int:conv_id>', methods=['DELETE'])
        @self._admin_required
        def delete_conversation(conv_id):
            """Beszélgetés törlése"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            db.delete_conversation(conv_id)
            self._audit_log('delete_conversation', 'conversation', {'id': conv_id})
            return {'success': True}
        
        @self.app.route('/api/conversations/<int:conv_id>/messages', methods=['GET'])
        @self._login_required
        def get_messages(conv_id):
            """Üzenetek lekérése"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            limit = request.args.get('limit', 100, type=int)
            before = request.args.get('before', type=int)
            
            messages = db.get_messages(conv_id, limit=limit)
            
            if before:
                messages = [m for m in messages if m['timestamp'] < before]
                messages = messages[-limit:]
            
            return {'messages': messages, 'count': len(messages)}
        
        @self.app.route('/api/conversations/<int:conv_id>/messages', methods=['POST'])
        @self._login_required
        def add_message(conv_id):
            """Üzenet hozzáadása"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            data = request.get_json() or {}
            msg_id = db.add_message(
                conversation_id=conv_id,
                role=data.get('role', 'user'),
                content=data.get('content', ''),
                tokens=data.get('tokens', 0),
                metadata=data.get('metadata')
            )
            
            return {'id': msg_id, 'success': True}
        
        @self.app.route('/api/conversations/<int:conv_id>/export', methods=['GET'])
        @self._login_required
        def export_conversation(conv_id):
            """Beszélgetés exportálása"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            conv = db.get_conversation(conv_id)
            messages = db.get_messages(conv_id)
            
            format = request.args.get('format', 'json')
            
            if format == 'json':
                return {
                    'conversation': conv,
                    'messages': messages,
                    'exported_at': time.time()
                }
            elif format == 'txt':
                lines = [f"Conversation: {conv['title']}"]
                lines.append(f"Date: {conv['created_at']}")
                lines.append("=" * 50)
                
                for msg in messages:
                    role = "User" if msg['role'] == 'user' else "Assistant"
                    lines.append(f"[{role}] {msg['content']}")
                    lines.append("-" * 30)
                
                return '\n'.join(lines), 200, {'Content-Type': 'text/plain; charset=utf-8'}
            
            return {'error': 'Unsupported format'}, 400
        
        # --- PROMPT SABLONOK API ---
        
        @self.app.route('/api/prompts', methods=['GET'])
        def get_prompts():
            """Prompt sablonok listázása"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            category = request.args.get('category')
            prompts = db.get_prompts(category=category)
            return {'prompts': prompts}
        
        @self.app.route('/api/prompts', methods=['POST'])
        @self._admin_required
        def save_prompt():
            """Prompt mentése"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            data = request.get_json() or {}
            
            prompt_id = db.save_prompt(
                name=data.get('name'),
                content=data.get('content'),
                description=data.get('description', ''),
                category=data.get('category', 'general'),
                is_default=data.get('is_default', False)
            )
            
            self._audit_log('save_prompt', 'prompt', {'id': prompt_id})
            return {'id': prompt_id, 'success': True}
        
        @self.app.route('/api/prompts/<int:prompt_id>', methods=['GET'])
        def get_prompt(prompt_id):
            """Egy prompt lekérése"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            prompt = db.get_prompt(prompt_id=prompt_id)
            if not prompt:
                return {'error': self._get_message('errors.not_found', resource='Prompt')}, 404
            
            return prompt
        
        @self.app.route('/api/prompts/<int:prompt_id>', methods=['DELETE'])
        @self._admin_required
        def delete_prompt(prompt_id):
            """Prompt törlése"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            try:
                db.delete_prompt(prompt_id)
                self._audit_log('delete_prompt', 'prompt', {'id': prompt_id})
                return {'success': True}
            except ValueError as e:
                return {'error': str(e)}, 400
        
        # --- SZEMÉLYISÉGEK API ---
        
        @self.app.route('/api/personalities', methods=['GET'])
        def get_personalities():
            """Személyiségek listázása"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            return {'personalities': db.get_personalities()}
        
        @self.app.route('/api/personalities', methods=['POST'])
        @self._admin_required
        def create_personality():
            """Új személyiség létrehozása"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            data = request.get_json() or {}
            pers_id = db.save_personality(
                name=data.get('name'),
                content=data.get('content'),
                activate=data.get('activate', False)
            )
            
            self._audit_log('create_personality', 'personality', {'id': pers_id})
            return {'id': pers_id, 'success': True}
        
        @self.app.route('/api/personalities/<int:pers_id>/activate', methods=['POST'])
        @self._admin_required
        def activate_personality(pers_id):
            """Személyiség aktiválása"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            db.activate_personality(pers_id)
            self._audit_log('activate_personality', 'personality', {'id': pers_id})
            return {'success': True}
        
        # --- BEÁLLÍTÁSOK API ---
        
        @self.app.route('/api/settings', methods=['GET'])
        def get_settings():
            """Beállítások lekérése (rendszer)"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            category = request.args.get('category')
            settings = db.get_all_system_settings(category=category)
            return settings
        
        @self.app.route('/api/settings/<key>', methods=['GET'])
        def get_setting(key):
            """Egy beállítás lekérése"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            value = db.get_system_setting(key)
            return {'key': key, 'value': value}
        
        @self.app.route('/api/settings/<key>', methods=['POST', 'PUT'])
        @self._admin_required
        def set_setting(key):
            """Beállítás módosítása"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            data = request.get_json() or {}
            db.set_system_setting(
                key=key,
                value=data.get('value'),
                value_type=data.get('type'),
                category=data.get('category', 'general'),
                description=data.get('description', '')
            )
            
            self._audit_log('update_setting', 'setting', {'key': key})
            return {'success': True}
        
        # --- MODELLEK API ---
        
        @self.app.route('/api/models', methods=['GET'])
        def get_models():
            """Modellek listázása"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            active_only = request.args.get('active_only', 'true').lower() == 'true'
            models = db.get_models(active_only=active_only)
            
            king = self.modules.get('king')
            current_model = None
            if king and hasattr(king, 'model') and king.model:
                current_model = getattr(king.model, 'model_path', None)
            
            return {
                'models': models,
                'current_model': current_model
            }
        
        @self.app.route('/api/models', methods=['POST'])
        @self._admin_required
        def add_model():
            """Modell hozzáadása"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            data = request.get_json() or {}
            
            model_path = data.get('path')
            if not os.path.exists(model_path):
                return {'error': self._get_message('errors.file_not_found', path=model_path)}, 400
            
            size = os.path.getsize(model_path)
            size_str = f"{size / 1024 / 1024 / 1024:.1f} GB" if size > 1024**3 else f"{size / 1024 / 1024:.1f} MB"
            
            model_id = db.add_model(
                name=data.get('name'),
                path=model_path,
                size=size_str,
                quantization=data.get('quantization'),
                n_ctx=data.get('n_ctx', 4096),
                n_gpu_layers=data.get('n_gpu_layers', -1),
                description=data.get('description', '')
            )
            
            self._audit_log('add_model', 'model', {'id': model_id})
            return {'id': model_id, 'success': True}
        
        @self.app.route('/api/models/<int:model_id>/activate', methods=['POST'])
        @self._admin_required
        def activate_model(model_id):
            """Aktív modell beállítása"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            model = db.get_model(model_id=model_id)
            if not model:
                return {'error': self._get_message('errors.not_found', resource='Model')}, 404
            
            db.set_active_model(model_id)
            self._audit_log('activate_model', 'model', {'id': model_id})
            return {'success': True, 'model': model['name']}
        
        @self.app.route('/api/models/<int:model_id>', methods=['DELETE'])
        @self._admin_required
        def delete_model(model_id):
            """Modell törlése"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            db.delete_model(model_id)
            self._audit_log('delete_model', 'model', {'id': model_id})
            return {'success': True}
        
        # --- MODUL VEZÉRLÉS (ADMIN) ---
        
        @self.app.route('/api/modules/<module_name>/<action>', methods=['POST'])
        @self._admin_required
        def control_module(module_name, action):
            """Modul vezérlése (start/stop/restart)"""
            module = self.modules.get(module_name)
            if not module:
                return {'error': self._get_message('errors.not_found', resource=f'Module {module_name}')}, 404
            
            if action == 'start' and hasattr(module, 'start'):
                module.start()
                self._audit_log('module_start', 'module', {'name': module_name})
                return {'success': True, 'message': f'{module_name} started'}
            elif action == 'stop' and hasattr(module, 'stop'):
                module.stop()
                self._audit_log('module_stop', 'module', {'name': module_name})
                return {'success': True, 'message': f'{module_name} stopped'}
            elif action == 'restart':
                if hasattr(module, 'stop'):
                    module.stop()
                time.sleep(1)
                if hasattr(module, 'start'):
                    module.start()
                self._audit_log('module_restart', 'module', {'name': module_name})
                return {'success': True, 'message': f'{module_name} restarted'}
            
            return {'error': f'Action {action} not supported'}, 400
        
        # --- KÉP FELTÖLTÉS (EYE-CORE) ---
        
        @self.app.route('/api/vision/process', methods=['POST'])
        @self._login_required
        def process_image():
            """Kép feldolgozása"""
            eye = self.modules.get('eyecore')
            if not eye:
                return {'error': 'EyeCore not available'}, 404
            
            data = request.get_json() or {}
            image_data = data.get('image')
            source = data.get('source', 'upload')
            
            if not image_data:
                return {'error': self._get_message('errors.missing_parameter', param='image')}, 400
            
            result = eye.process_image(image_data, source=source)
            return result
        
        # --- TOOL/SANDBOX ---
        
        @self.app.route('/api/tools/execute', methods=['POST'])
        @self._admin_required
        def execute_code():
            """Kód futtatása sandboxban"""
            sandbox = self.modules.get('sandbox')
            if not sandbox:
                return {'error': 'Sandbox not available'}, 404
            
            data = request.get_json() or {}
            code = data.get('code')
            context = data.get('context', {})
            
            if not code:
                return {'error': self._get_message('errors.missing_parameter', param='code')}, 400
            
            result = sandbox.execute_for_king(code, context)
            self._audit_log('execute_code', 'sandbox', {'code_length': len(code)})
            return {'result': result}
        
        # --- AUDIT LOG API ---
        
        @self.app.route('/api/audit', methods=['GET'])
        @self._admin_required
        def get_audit_log():
            """Audit log lekérése"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            limit = request.args.get('limit', 100, type=int)
            
            with db.lock:
                conn = db._get_connection()
                cursor = conn.execute("""
                    SELECT * FROM audit_log 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """, (limit,))
                logs = [dict(row) for row in cursor.fetchall()]
                conn.close()
            
            return {'audit_log': logs}
        
        # --- PERFORMANCE METRICS API ---
        
        @self.app.route('/api/metrics', methods=['GET'])
        @self._admin_required
        def get_metrics():
            """Teljesítmény metrikák lekérése"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            period = request.args.get('period', 'hour')
            now = time.time()
            
            if period == 'hour':
                since = now - 3600
            elif period == 'day':
                since = now - 86400
            elif period == 'week':
                since = now - 604800
            else:
                since = now - 3600
            
            with db.lock:
                conn = db._get_connection()
                cursor = conn.execute("""
                    SELECT * FROM performance_metrics 
                    WHERE timestamp > ? 
                    ORDER BY timestamp DESC
                """, (since,))
                metrics = [dict(row) for row in cursor.fetchall()]
                conn.close()
            
            return {'metrics': metrics, 'period': period}
        
        # --- EGÉSZSÉGÜGYI ELLENŐRZÉS ---
        
        @self.app.route('/health')
        def health_check():
            """Egészségügyi ellenőrzés (monitoring)"""
            status = {'status': 'healthy', 'timestamp': time.time()}
            
            for name, module in self.modules.items():
                if hasattr(module, 'get_state'):
                    try:
                        state = module.get_state()
                        status[name] = {'status': state.get('status', 'unknown')}
                    except:
                        status[name] = {'status': 'error'}
            
            return status
        
        # --- STATIKUS FÁJLOK ---
        
        @self.app.route('/static/<path:filename>')
        def static_files(filename):
            """Statikus fájlok kiszolgálása"""
            return send_from_directory(str(ROOT_DIR / 'src' / 'web' / 'static'), filename)
    
    # ------------------------------------------------------------------------
    # SOCKET.IO ESEMÉNYEK
    # ------------------------------------------------------------------------
    
    def _setup_socket_events(self):
        """Socket.IO események"""
        
        @self.socketio.on('connect')
        def handle_connect():
            """Új kliens csatlakozott"""
            client_id = request.sid
            self.connected_clients[client_id] = {
                'connected_at': time.time(),
                'ip': request.remote_addr,
                'user_agent': request.headers.get('User-Agent', 'unknown'),
                'language': session.get('language', 'en')
            }
            
            print(f"🌐 Web: Kliens csatlakozott ({client_id[:8]}...)")
            emit('connected', {
                'status': 'ok',
                'time': time.time(),
                'client_id': client_id,
                'language': session.get('language', 'en')
            })
            
            self._broadcast_status()
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """Kliens lecsatlakozott"""
            client_id = request.sid
            if client_id in self.connected_clients:
                del self.connected_clients[client_id]
            print(f"🌐 Web: Kliens lecsatlakozott ({client_id[:8]}...)")
        
        @self.socketio.on('user_message')
        def handle_user_message(data):
            """
            Üzenet érkezett a felhasználótól.
            Formátum: {text: "üzenet", conversation_id: 123}
            """
            text = data.get('text', '')
            conv_id = data.get('conversation_id')
            client_id = request.sid
            
            print(f"🌐 Web: User üzenet ({client_id[:8]}...): {text[:50]}...")
            
            user_name = self.modules.get('scratchpad', {}).get_state('user_name', 'User')
            kvk = f"INTENT:UNKNOWN|USER:{user_name}|MESSAGE:{text}"
            
            orch = self.modules.get('orchestrator')
            if orch:
                state = orch.process_raw_packet(kvk)
                if state and isinstance(state, dict) and 'trace_id' in state:
                    hb = self.modules.get('heartbeat')
                    if hb:
                        hb.register_interaction()
                    
                    if conv_id:
                        db = self.modules.get('database')
                        if db:
                            db.add_message(conv_id, 'user', text)
                    
                    king = self.modules.get('king')
                    if king:
                        model_input = orch.build_model_input(state)
                        
                        intent_packet = {
                            'header': {
                                'trace_id': state['trace_id'],
                                'timestamp': time.time(),
                                'sender': 'web'
                            },
                            'payload': {
                                'intent': {
                                    'class': state.get('packet', {}).get('INTENT', 'unknown'),
                                    'target': 'king'
                                },
                                'entities': [],
                                'text': text
                            }
                        }
                        
                        response = king.process(intent_packet)
                        
                        if response:
                            response_text = response.get('payload', {}).get('response', '')
                            
                            emit('king_response', {
                                'response': response_text,
                                'trace_id': state['trace_id'],
                                'mood': king.get_mood() if hasattr(king, 'get_mood') else 'neutral'
                            })
                            
                            if conv_id:
                                db = self.modules.get('database')
                                if db:
                                    tokens = response.get('state', {}).get('tokens_used', 0)
                                    db.add_message(conv_id, 'assistant', response_text, tokens)
                            
                            jester = self.modules.get('jester')
                            if jester and hasattr(jester, 'check_king'):
                                report = jester.check_king(king.get_state())
                                if report:
                                    emit('jester_note', {
                                        'note': report.get('payload', {}).get('summary', '')
                                    })
                else:
                    print(f"🌐 Web: Hibás orchestrator válasz: {state}")
                    emit('king_response', {
                        'response': self._get_message('errors.processing_error'),
                        'trace_id': None,
                        'mood': 'error'
                    })
        
        @self.socketio.on('image_upload')
        def handle_image_upload(data):
            """Kép feltöltés"""
            image = data.get('image')
            filename = data.get('filename', 'image')
            client_id = request.sid
            
            print(f"🌐 Web: Kép feltöltés ({client_id[:8]}...): {filename}")
            
            eye = self.modules.get('eyecore')
            if eye:
                result = eye.process_image(image, source='upload')
                emit('vision_result', {
                    'description': result.get('description', ''),
                    'ocr': result.get('ocr_text', ''),
                    'success': result.get('success', False)
                })
            else:
                emit('vision_result', {
                    'description': 'Eye-Core not available',
                    'success': False
                })
        
        @self.socketio.on('get_status')
        def handle_get_status():
            """Státusz lekérés"""
            self._broadcast_status()
        
        @self.socketio.on('get_initial_state')
        def handle_get_initial_state():
            """Teljes kezdeti állapot lekérése"""
            client_id = request.sid
            
            blackbox = self.modules.get('blackbox')
            recent = []
            if blackbox:
                recent = blackbox.get_conversation(limit=20)
            
            user_name = self.modules.get('scratchpad', {}).get_state('user_name', 'User')
            user_language = self.modules.get('scratchpad', {}).get_state('user_language', 'en')
            
            emit('initial_state', {
                'messages': recent,
                'userName': user_name,
                'userLanguage': user_language,
                'client_id': client_id,
                'server_time': time.time()
            })
        
        # --- ADATBÁZIS ESEMÉNYEK ---
        
        @self.socketio.on('get_conversations')
        def handle_get_conversations():
            """Beszélgetések listájának lekérése"""
            db = self.modules.get('database')
            if db:
                user_id = session.get('user_id')
                convs = db.get_conversations(limit=50, user_id=user_id)
                emit('conversations_list', {'conversations': convs})
        
        @self.socketio.on('create_conversation')
        def handle_create_conversation(data):
            """Új beszélgetés létrehozása"""
            db = self.modules.get('database')
            if db:
                user_id = session.get('user_id')
                conv_id = db.create_conversation(
                    title=data.get('title'),
                    model=data.get('model'),
                    system_prompt=data.get('system_prompt'),
                    user_id=user_id
                )
                emit('conversation_created', {'id': conv_id})
                
                convs = db.get_conversations(limit=50, user_id=user_id)
                self.socketio.emit('conversations_list', {'conversations': convs})
        
        @self.socketio.on('load_conversation')
        def handle_load_conversation(data):
            """Beszélgetés betöltése"""
            conv_id = data.get('id')
            db = self.modules.get('database')
            
            if db and conv_id:
                messages = db.get_messages(conv_id)
                emit('conversation_loaded', {
                    'id': conv_id,
                    'messages': messages
                })
        
        @self.socketio.on('save_message')
        def handle_save_message(data):
            """Üzenet mentése az adatbázisba"""
            conv_id = data.get('conversation_id')
            role = data.get('role')
            content = data.get('content')
            tokens = data.get('tokens', 0)
            
            db = self.modules.get('database')
            if db and conv_id:
                db.add_message(conv_id, role, content, tokens)
        
        @self.socketio.on('delete_conversation')
        def handle_delete_conversation(data):
            """Beszélgetés törlése"""
            if not session.get('admin'):
                return
            
            conv_id = data.get('id')
            db = self.modules.get('database')
            
            if db and conv_id:
                db.delete_conversation(conv_id)
                user_id = session.get('user_id')
                convs = db.get_conversations(limit=50, user_id=user_id)
                emit('conversations_list', {'conversations': convs})
        
        @self.socketio.on('get_prompts')
        def handle_get_prompts():
            """Prompt sablonok lekérése"""
            db = self.modules.get('database')
            if db:
                prompts = db.get_prompts()
                emit('prompts_list', {'prompts': prompts})
        
        @self.socketio.on('save_prompt')
        def handle_save_prompt(data):
            """Prompt mentése"""
            if not session.get('admin'):
                return
            
            db = self.modules.get('database')
            if db:
                prompt_id = db.save_prompt(
                    name=data.get('name'),
                    content=data.get('content'),
                    description=data.get('description', ''),
                    category=data.get('category', 'general'),
                    is_default=data.get('is_default', False)
                )
                emit('prompt_saved', {'id': prompt_id})
                handle_get_prompts()
        
        @self.socketio.on('get_settings')
        def handle_get_settings():
            """Beállítások lekérése"""
            db = self.modules.get('database')
            if db:
                settings = db.get_all_system_settings()
                emit('settings', settings)
        
        @self.socketio.on('update_setting')
        def handle_update_setting(data):
            """Beállítás módosítása"""
            if not session.get('admin'):
                return
            
            db = self.modules.get('database')
            if db:
                db.set_system_setting(
                    key=data.get('key'),
                    value=data.get('value'),
                    value_type=data.get('type'),
                    category=data.get('category', 'general')
                )
                handle_get_settings()
        
        @self.socketio.on('get_models')
        def handle_get_models():
            """Modellek lekérése"""
            db = self.modules.get('database')
            if db:
                models = db.get_models(active_only=False)
                emit('models_list', {'models': models})
        
        @self.socketio.on('activate_model')
        def handle_activate_model(data):
            """Modell aktiválása"""
            if not session.get('admin'):
                return
            
            model_id = data.get('id')
            db = self.modules.get('database')
            if db:
                db.set_active_model(model_id)
                emit('model_activated', {'id': model_id})
        
        @self.socketio.on('control_module')
        def handle_control_module(data):
            """Modul vezérlése (admin)"""
            if not session.get('admin'):
                emit('module_control_result', {
                    'success': False,
                    'message': self._get_message('errors.unauthorized')
                })
                return
            
            module_name = data.get('module')
            action = data.get('action')
            
            module = self.modules.get(module_name)
            if not module:
                emit('module_control_result', {
                    'success': False,
                    'message': self._get_message('errors.not_found', resource=f'Module {module_name}')
                })
                return
            
            try:
                if action == 'start' and hasattr(module, 'start'):
                    module.start()
                    emit('module_control_result', {'success': True, 'message': f'{module_name} started'})
                elif action == 'stop' and hasattr(module, 'stop'):
                    module.stop()
                    emit('module_control_result', {'success': True, 'message': f'{module_name} stopped'})
                elif action == 'restart':
                    if hasattr(module, 'stop'):
                        module.stop()
                    time.sleep(1)
                    if hasattr(module, 'start'):
                        module.start()
                    emit('module_control_result', {'success': True, 'message': f'{module_name} restarted'})
                else:
                    emit('module_control_result', {'success': False, 'message': f'Action {action} not supported'})
            except Exception as e:
                emit('module_control_result', {'success': False, 'message': str(e)})
            
            self._broadcast_status()
        
        @self.socketio.on('admin_login')
        def handle_admin_login(data):
            """Admin bejelentkezés"""
            password = data.get('password')
            if password == self.admin_password:
                session['admin'] = True
                session['user_id'] = 1
                emit('admin_login_result', {'success': True})
                self._audit_log('socket_admin_login', 'user', {'method': 'socket'})
                self._broadcast_status()
            else:
                emit('admin_login_result', {'success': False, 'message': self._get_message('errors.unauthorized')})
        
        @self.socketio.on('set_language')
        def handle_set_language(data):
            """Nyelv beállítása"""
            lang = data.get('language')
            if lang in ['en', 'hu']:
                session['language'] = lang
                if self.translator:
                    self.translator.set_language(lang)
                emit('language_changed', {'language': lang})
    
    # ------------------------------------------------------------------------
    # STÁTUSZ KEZELÉS
    # ------------------------------------------------------------------------
    
    def _broadcast_status(self):
        """Rendszer státusz broadcastolása minden kliensnek"""
        try:
            sentinel = self.modules.get('sentinel')
            gpu_status = sentinel.get_gpu_status() if sentinel else []
            
            king = self.modules.get('king')
            king_state = king.get_state() if king else {}
            
            hb = self.modules.get('heartbeat')
            hb_state = hb.get_state() if hb else {}
            
            sp = self.modules.get('scratchpad')
            memory_percent = 0
            if sp:
                summary = sp.get_summary()
                memory_percent = min(100, (summary.get('entry_count', 0) / 1000) * 100)
            
            module_statuses = {}
            for name, module in self.modules.items():
                if hasattr(module, 'get_state'):
                    try:
                        state = module.get_state()
                        module_statuses[name] = state.get('status', 'unknown')
                    except:
                        module_statuses[name] = 'error'
                else:
                    module_statuses[name] = 'active'
            
            status = {
                'timestamp': time.time(),
                'heartbeat': hb_state,
                'king': king_state,
                'gpu': gpu_status,
                'memory': {'percent': memory_percent},
                'modules': module_statuses,
                'clients': len(self.connected_clients)
            }
            
            self.socketio.emit('status_update', status)
            
        except Exception as e:
            print(f"🌐 Web: Status broadcast hiba: {e}")
    
    # ------------------------------------------------------------------------
    # INDIÍTÁS / LEÁLLÍTÁS
    # ------------------------------------------------------------------------
    
    def start(self):
        """Web szerver indítása (külön szálon)"""
        self.running = True
        
        def run():
            print("🌐 Web: Szerver indul a http://localhost:5000 címen")
            self.socketio.run(self.app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)
        
        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
        
        self.scratchpad = self.modules.get('scratchpad')
        if self.scratchpad:
            self.scratchpad.set_state('web_status', 'running', self.name)
    
    def stop(self):
        """Web szerver leállítása"""
        self.running = False
        if self.scratchpad:
            self.scratchpad.set_state('web_status', 'stopped', self.name)
        
        self.socketio.stop()
        print("🌐 Web: Ablak becsukódik.")
    
    # ------------------------------------------------------------------------
    # SEGÉDFÜGGVÉNYEK
    # ------------------------------------------------------------------------
    
    def get_state(self):
        """Web app állapota"""
        return {
            'status': 'running' if self.running else 'stopped',
            'clients': len(self.connected_clients),
            'uptime': time.time() - (self.thread.start_time if self.thread and hasattr(self.thread, 'start_time') else time.time())
        }