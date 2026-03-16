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
"""

import os
import time
import json
import threading
from pathlib import Path
from flask import Flask, render_template, send_from_directory, request, jsonify, session
from flask_socketio import SocketIO, emit, join_room, leave_room
from datetime import datetime, timedelta
import hashlib
import secrets

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
    """
    
    def __init__(self, modules):
        self.modules = modules
        self.name = "web"
        
        # Flask app
        self.app = Flask(__name__, 
                        template_folder=str(ROOT_DIR / 'src' / 'web' / 'templates'),
                        static_folder=str(ROOT_DIR / 'src' / 'web' / 'static'))
        
        # Titkos kulcs session-ökhöz
        self.app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
        
        # Socket.IO
        self.socketio = SocketIO(self.app, cors_allowed_origins="*", ping_timeout=60, ping_interval=25)
        
        # Szál
        self.thread = None
        self.running = False
        
        # Aktív kapcsolatok
        self.connected_clients = {}
        
        # Admin jelszó (később configból)
        self.admin_password = os.environ.get('ADMIN_PASSWORD', 'soulcore2026')
        
        # Útvonalak beállítása
        self._setup_routes()
        
        # Socket események
        self._setup_socket_events()
        
        print("🌐 Web: Ablak nyílik.")
    
    # ------------------------------------------------------------------------
    # ROUTES - REST API
    # ------------------------------------------------------------------------
    
    def _setup_routes(self):
        """Flask útvonalak - REST API"""
        
        # --- FŐOLDAL ---
        
        @self.app.route('/')
        def index():
            """Főoldal"""
            return render_template('index.html')
        
        @self.app.route('/admin')
        def admin_panel():
            """Admin panel (külön oldal)"""
            return render_template('admin.html')
        
        @self.app.route('/login', methods=['POST'])
        def login():
            """Bejelentkezés"""
            data = request.get_json() or {}
            password = data.get('password')
            
            if password == self.admin_password:
                session['admin'] = True
                session['login_time'] = time.time()
                return {'success': True, 'message': 'Sikeres bejelentkezés'}
            
            return {'success': False, 'message': 'Hibás jelszó'}, 401
        
        @self.app.route('/logout', methods=['POST'])
        def logout():
            """Kijelentkezés"""
            session.pop('admin', None)
            return {'success': True}
        
        @self.app.route('/api/session')
        def get_session():
            """Session állapot lekérése"""
            return {
                'is_admin': session.get('admin', False),
                'login_time': session.get('login_time')
            }
        
        # --- RENDSZER STÁTUSZ ---
        
        @self.app.route('/api/status')
        def status():
            """Rendszer státusz (REST)"""
            return {
                'status': 'running',
                'modules': list(self.modules.keys()),
                'time': time.time(),
                'uptime': self.modules.get('heartbeat', {}).get_state().get('uptime_seconds', 0),
                'version': '3.0',
                'name': 'SoulCore'
            }
        
        @self.app.route('/api/king/state')
        def king_state():
            """Király állapota"""
            king = self.modules.get('king')
            if king:
                return king.get_state()
            return {'error': 'King not available'}, 404
        
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
                    'state': sentinel.get_state()
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
        
        # --- BESZÉLGETÉSEK API ---
        
        @self.app.route('/api/conversations', methods=['GET'])
        def get_conversations():
            """Beszélgetések listázása"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            limit = request.args.get('limit', 50, type=int)
            offset = request.args.get('offset', 0, type=int)
            
            convs = db.get_conversations(limit=limit, offset=offset)
            return {'conversations': convs, 'total': len(convs)}
        
        @self.app.route('/api/conversations', methods=['POST'])
        def create_conversation():
            """Új beszélgetés létrehozása"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            data = request.get_json() or {}
            conv_id = db.create_conversation(
                title=data.get('title', f"Beszélgetés {datetime.now().strftime('%Y-%m-%d %H:%M')}"),
                model=data.get('model'),
                system_prompt=data.get('system_prompt'),
                metadata=data.get('metadata')
            )
            
            return {'id': conv_id, 'success': True}
        
        @self.app.route('/api/conversations/<int:conv_id>', methods=['GET'])
        def get_conversation(conv_id):
            """Egy beszélgetés adatai"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            conv = db.get_conversation(conv_id)
            if not conv:
                return {'error': 'Conversation not found'}, 404
            
            return conv
        
        @self.app.route('/api/conversations/<int:conv_id>', methods=['PUT'])
        def update_conversation(conv_id):
            """Beszélgetés frissítése"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            data = request.get_json() or {}
            db.update_conversation(conv_id, **data)
            return {'success': True}
        
        @self.app.route('/api/conversations/<int:conv_id>', methods=['DELETE'])
        def delete_conversation(conv_id):
            """Beszélgetés törlése"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            # Csak admin törölhet
            if not session.get('admin'):
                return {'error': 'Unauthorized'}, 403
            
            db.delete_conversation(conv_id)
            return {'success': True}
        
        @self.app.route('/api/conversations/<int:conv_id>/messages', methods=['GET'])
        def get_messages(conv_id):
            """Üzenetek lekérése"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            limit = request.args.get('limit', 100, type=int)
            before = request.args.get('before', type=int)
            
            messages = db.get_messages(conv_id, limit=limit)
            
            # Ha van before, csak az az előtti üzenetek
            if before:
                messages = [m for m in messages if m['timestamp'] < before]
                messages = messages[-limit:]
            
            return {'messages': messages, 'count': len(messages)}
        
        @self.app.route('/api/conversations/<int:conv_id>/messages', methods=['POST'])
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
                # Egyszerű szöveges export
                lines = [f"Beszélgetés: {conv['title']}"]
                lines.append(f"Idő: {conv['created_at']}")
                lines.append("=" * 50)
                
                for msg in messages:
                    role = "Grumpy" if msg['role'] == 'user' else "Kópé"
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
        def save_prompt():
            """Prompt mentése"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            data = request.get_json() or {}
            
            # Csak admin szerkeszthet
            if not session.get('admin'):
                return {'error': 'Unauthorized'}, 403
            
            prompt_id = db.save_prompt(
                name=data.get('name'),
                content=data.get('content'),
                description=data.get('description', ''),
                category=data.get('category', 'general'),
                is_default=data.get('is_default', False)
            )
            
            return {'id': prompt_id, 'success': True}
        
        @self.app.route('/api/prompts/<int:prompt_id>', methods=['GET'])
        def get_prompt(prompt_id):
            """Egy prompt lekérése"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            prompt = db.get_prompt(prompt_id=prompt_id)
            if not prompt:
                return {'error': 'Prompt not found'}, 404
            
            return prompt
        
        @self.app.route('/api/prompts/<int:prompt_id>', methods=['DELETE'])
        def delete_prompt(prompt_id):
            """Prompt törlése"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            # Csak admin törölhet
            if not session.get('admin'):
                return {'error': 'Unauthorized'}, 403
            
            try:
                db.delete_prompt(prompt_id)
                return {'success': True}
            except ValueError as e:
                return {'error': str(e)}, 400
        
        @self.app.route('/api/prompts/default/<category>', methods=['GET'])
        def get_default_prompt(category):
            """Alapértelmezett prompt lekérése kategória alapján"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            prompts = db.get_prompts(category=category)
            default = next((p for p in prompts if p['is_default']), None)
            
            if default:
                return default
            
            # Ha nincs, az elsőt adjuk
            return prompts[0] if prompts else {'content': '', 'name': 'Üres'}
        
        # --- BEÁLLÍTÁSOK API ---
        
        @self.app.route('/api/settings', methods=['GET'])
        def get_settings():
            """Beállítások lekérése"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            category = request.args.get('category')
            settings = db.get_all_settings(category=category)
            return settings
        
        @self.app.route('/api/settings/<key>', methods=['GET'])
        def get_setting(key):
            """Egy beállítás lekérése"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            value = db.get_setting(key)
            return {'key': key, 'value': value}
        
        @self.app.route('/api/settings/<key>', methods=['POST', 'PUT'])
        def set_setting(key):
            """Beállítás módosítása"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            # Csak admin módosíthat
            if not session.get('admin'):
                return {'error': 'Unauthorized'}, 403
            
            data = request.get_json() or {}
            db.set_setting(
                key=key,
                value=data.get('value'),
                value_type=data.get('type'),
                category=data.get('category', 'general'),
                description=data.get('description', '')
            )
            
            return {'success': True}
        
        @self.app.route('/api/settings/import', methods=['POST'])
        def import_settings():
            """Beállítások importálása JSON-ből"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            if not session.get('admin'):
                return {'error': 'Unauthorized'}, 403
            
            data = request.get_json() or {}
            settings = data.get('settings', {})
            
            for key, value in settings.items():
                if isinstance(value, dict):
                    db.set_setting(
                        key=key,
                        value=value.get('value'),
                        value_type=value.get('type'),
                        category=value.get('category', 'imported'),
                        description=value.get('description', '')
                    )
                else:
                    db.set_setting(key=key, value=value)
            
            return {'success': True, 'count': len(settings)}
        
        @self.app.route('/api/settings/export', methods=['GET'])
        def export_settings():
            """Beállítások exportálása"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            settings = db.get_all_settings()
            return {'settings': settings, 'exported_at': time.time()}
        
        # --- MODELLEK API ---
        
        @self.app.route('/api/models', methods=['GET'])
        def get_models():
            """Modellek listázása"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            active_only = request.args.get('active_only', 'true').lower() == 'true'
            models = db.get_models(active_only=active_only)
            
            # Aktuális modell lekérése a King-től
            king = self.modules.get('king')
            current_model = None
            if king and hasattr(king, 'model') and king.model:
                current_model = getattr(king.model, 'model_path', None)
            
            return {
                'models': models,
                'current_model': current_model
            }
        
        @self.app.route('/api/models', methods=['POST'])
        def add_model():
            """Modell hozzáadása"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            if not session.get('admin'):
                return {'error': 'Unauthorized'}, 403
            
            data = request.get_json() or {}
            
            # Ellenőrizzük, hogy létezik-e a fájl
            model_path = data.get('path')
            if not os.path.exists(model_path):
                return {'error': f'File not found: {model_path}'}, 400
            
            # Fájlméret lekérése
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
            
            return {'id': model_id, 'success': True}
        
        @self.app.route('/api/models/<int:model_id>/activate', methods=['POST'])
        def activate_model(model_id):
            """Aktív modell beállítása"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            if not session.get('admin'):
                return {'error': 'Unauthorized'}, 403
            
            # Modell lekérése
            model = db.get_model(model_id=model_id)
            if not model:
                return {'error': 'Model not found'}, 404
            
            # King újratöltése az új modellel
            king = self.modules.get('king')
            if king:
                # Itt történik a modell váltás
                # Ez bonyolultabb, később
                pass
            
            db.set_active_model(model_id)
            return {'success': True, 'model': model['name']}
        
        @self.app.route('/api/models/<int:model_id>', methods=['DELETE'])
        def delete_model(model_id):
            """Modell törlése"""
            db = self.modules.get('database')
            if not db:
                return {'error': 'Database not available'}, 500
            
            if not session.get('admin'):
                return {'error': 'Unauthorized'}, 403
            
            db.delete_model(model_id)
            return {'success': True}
        
        @self.app.route('/api/models/scan', methods=['POST'])
        def scan_models():
            """Modell mappa átvizsgálása"""
            if not session.get('admin'):
                return {'error': 'Unauthorized'}, 403
            
            data = request.get_json() or {}
            folder = data.get('folder', 'models')
            
            if not os.path.exists(folder):
                return {'error': f'Folder not found: {folder}'}, 400
            
            # GGUF fájlok keresése
            models_found = []
            for file in Path(folder).glob('**/*.gguf'):
                models_found.append({
                    'path': str(file),
                    'name': file.stem,
                    'size': f"{file.stat().st_size / 1024 / 1024 / 1024:.1f} GB"
                })
            
            return {'models': models_found, 'count': len(models_found)}
        
        # --- MODUL VEZÉRLÉS (ADMIN) ---
        
        @self.app.route('/api/modules/<module_name>/<action>', methods=['POST'])
        def control_module(module_name, action):
            """Modul vezérlése (start/stop/restart)"""
            if not session.get('admin'):
                return {'error': 'Unauthorized'}, 403
            
            module = self.modules.get(module_name)
            if not module:
                return {'error': f'Module {module_name} not found'}, 404
            
            if action == 'start' and hasattr(module, 'start'):
                module.start()
                return {'success': True, 'message': f'{module_name} started'}
            elif action == 'stop' and hasattr(module, 'stop'):
                module.stop()
                return {'success': True, 'message': f'{module_name} stopped'}
            elif action == 'restart':
                if hasattr(module, 'stop'):
                    module.stop()
                time.sleep(1)
                if hasattr(module, 'start'):
                    module.start()
                return {'success': True, 'message': f'{module_name} restarted'}
            
            return {'error': f'Action {action} not supported'}, 400
        
        # --- KÉP FELTÖLTÉS (EYE-CORE) ---
        
        @self.app.route('/api/vision/process', methods=['POST'])
        def process_image():
            """Kép feldolgozása"""
            eye = self.modules.get('eyecore')
            if not eye:
                return {'error': 'EyeCore not available'}, 404
            
            data = request.get_json() or {}
            image_data = data.get('image')
            source = data.get('source', 'upload')
            
            if not image_data:
                return {'error': 'No image data'}, 400
            
            result = eye.process_image(image_data, source=source)
            return result
        
        # --- TOOL/SANDBOX ---
        
        @self.app.route('/api/tools/execute', methods=['POST'])
        def execute_code():
            """Kód futtatása sandboxban"""
            if not session.get('admin'):
                return {'error': 'Unauthorized'}, 403
            
            sandbox = self.modules.get('sandbox')
            if not sandbox:
                return {'error': 'Sandbox not available'}, 404
            
            data = request.get_json() or {}
            code = data.get('code')
            context = data.get('context', {})
            
            if not code:
                return {'error': 'No code provided'}, 400
            
            result = sandbox.execute_for_king(code, context)
            return {'result': result}
        
        # --- EGÉSZSÉGÜGYI ELLENŐRZÉS (HEALTH CHECK) ---
        
        @self.app.route('/health')
        def health_check():
            """Egészségügyi ellenőrzés (monitoring)"""
            status = {'status': 'healthy', 'timestamp': time.time()}
            
            # Modulok ellenőrzése
            for name, module in self.modules.items():
                if hasattr(module, 'get_state'):
                    try:
                        state = module.get_state()
                        status[name] = {'status': state.get('status', 'unknown')}
                    except:
                        status[name] = {'status': 'error'}
            
            return status
        
        # --- STATikus FÁJLOK ---
        
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
                'user_agent': request.headers.get('User-Agent', 'unknown')
            }
            
            print(f"🌐 Web: Kliens csatlakozott ({client_id[:8]}...)")
            emit('connected', {
                'status': 'ok',
                'time': time.time(),
                'client_id': client_id
            })
            
            # Küldjük a jelenlegi állapotot
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
            
            # 1. KVK csomag készítése
            kvk = f"INTENT:UNKNOWN|USER:GRUMPY|MESSAGE:{text}"
            
            # 2. Orchestrator feldolgozása
            orch = self.modules.get('orchestrator')
            if orch:
                state = orch.process_raw_packet(kvk)
                if state:
                    # 3. Heartbeat értesítése (interakció történt)
                    hb = self.modules.get('heartbeat')
                    if hb:
                        hb.register_interaction()
                    
                    # 4. Mentés adatbázisba (ha van konverzió)
                    if conv_id:
                        db = self.modules.get('database')
                        if db:
                            db.add_message(conv_id, 'user', text)
                    
                    # 5. King válaszának kérése
                    king = self.modules.get('king')
                    if king:
                        # Kontextus építés
                        model_input = orch.build_model_input(state)
                        
                        # Intent csomag a Kingnek
                        intent_packet = {
                            'header': {
                                'trace_id': state['trace_id'],
                                'timestamp': time.time(),
                                'sender': 'web'
                            },
                            'payload': {
                                'intent': {
                                    'class': state['packet'].get('INTENT', 'unknown'),
                                    'target': 'king'
                                },
                                'entities': [],
                                'text': text
                            }
                        }
                        
                        # King feldolgozás
                        response = king.process(intent_packet)
                        
                        if response:
                            response_text = response.get('payload', {}).get('response', '')
                            
                            # Válasz vissza a kliensnek
                            emit('king_response', {
                                'response': response_text,
                                'trace_id': state['trace_id'],
                                'mood': king.get_mood() if hasattr(king, 'get_mood') else 'neutral'
                            })
                            
                            # Mentés adatbázisba
                            if conv_id:
                                db = self.modules.get('database')
                                if db:
                                    tokens = response.get('state', {}).get('tokens_used', 0)
                                    db.add_message(conv_id, 'assistant', response_text, tokens)
                            
                            # Jester ellenőrzés
                            jester = self.modules.get('jester')
                            if jester and hasattr(jester, 'check_king'):
                                report = jester.check_king(king.get_state())
                                if report:
                                    emit('jester_note', {
                                        'note': report.get('payload', {}).get('summary', '')
                                    })
        
        @self.socketio.on('image_upload')
        def handle_image_upload(data):
            """Kép feltöltés"""
            image = data.get('image')
            filename = data.get('filename', 'kép')
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
                    'description': 'Eye-Core nem elérhető',
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
            
            # Utolsó néhány üzenet a BlackBox-ból
            blackbox = self.modules.get('blackbox')
            recent = []
            if blackbox:
                recent = blackbox.get_conversation(limit=20)
            
            # Felhasználónév
            user_name = self.modules.get('scratchpad', {}).get_state('user_name', 'Grumpy')
            
            emit('initial_state', {
                'messages': recent,
                'userName': user_name,
                'client_id': client_id,
                'server_time': time.time()
            })
        
        # --- ADATBÁZIS ESEMÉNYEK ---
        
        @self.socketio.on('get_conversations')
        def handle_get_conversations():
            """Beszélgetések listájának lekérése"""
            db = self.modules.get('database')
            if db:
                convs = db.get_conversations(limit=50)
                emit('conversations_list', {'conversations': convs})
        
        @self.socketio.on('create_conversation')
        def handle_create_conversation(data):
            """Új beszélgetés létrehozása"""
            db = self.modules.get('database')
            if db:
                conv_id = db.create_conversation(
                    title=data.get('title'),
                    model=data.get('model'),
                    system_prompt=data.get('system_prompt')
                )
                emit('conversation_created', {'id': conv_id})
                
                # Frissítjük a listát mindenkinek
                self.socketio.emit('conversations_list', {
                    'conversations': db.get_conversations(limit=50)
                })
        
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
            conv_id = data.get('id')
            db = self.modules.get('database')
            
            if db and conv_id:
                db.delete_conversation(conv_id)
                # Frissítjük a listát
                emit('conversations_list', {
                    'conversations': db.get_conversations(limit=50)
                })
        
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
                # Frissítjük a listát
                handle_get_prompts()
        
        @self.socketio.on('get_settings')
        def handle_get_settings():
            """Beállítások lekérése"""
            db = self.modules.get('database')
            if db:
                settings = db.get_all_settings()
                emit('settings', settings)
        
        @self.socketio.on('update_setting')
        def handle_update_setting(data):
            """Beállítás módosítása"""
            db = self.modules.get('database')
            if db:
                db.set_setting(
                    key=data.get('key'),
                    value=data.get('value'),
                    value_type=data.get('type'),
                    category=data.get('category', 'general')
                )
                # Visszaküldjük a frissített beállításokat
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
            model_id = data.get('id')
            db = self.modules.get('database')
            if db:
                db.set_active_model(model_id)
                # Itt kellene a King-et is újratölteni
                emit('model_activated', {'id': model_id})
        
        @self.socketio.on('control_module')
        def handle_control_module(data):
            """Modul vezérlése (admin)"""
            module_name = data.get('module')
            action = data.get('action')
            
            module = self.modules.get(module_name)
            if not module:
                emit('module_control_result', {
                    'success': False,
                    'message': f'Module {module_name} not found'
                })
                return
            
            try:
                if action == 'start' and hasattr(module, 'start'):
                    module.start()
                    emit('module_control_result', {
                        'success': True,
                        'message': f'{module_name} started'
                    })
                elif action == 'stop' and hasattr(module, 'stop'):
                    module.stop()
                    emit('module_control_result', {
                        'success': True,
                        'message': f'{module_name} stopped'
                    })
                elif action == 'restart':
                    if hasattr(module, 'stop'):
                        module.stop()
                    time.sleep(1)
                    if hasattr(module, 'start'):
                        module.start()
                    emit('module_control_result', {
                        'success': True,
                        'message': f'{module_name} restarted'
                    })
                else:
                    emit('module_control_result', {
                        'success': False,
                        'message': f'Action {action} not supported'
                    })
            except Exception as e:
                emit('module_control_result', {
                    'success': False,
                    'message': str(e)
                })
            
            # Státusz frissítés
            self._broadcast_status()
        
        @self.socketio.on('admin_login')
        def handle_admin_login(data):
            """Admin bejelentkezés"""
            password = data.get('password')
            if password == self.admin_password:
                # Socket.IO session-be is elmentjük
                emit('admin_login_result', {'success': True})
                # Küldünk egy eseményt, hogy admin státusz frissült
                self._broadcast_status()
            else:
                emit('admin_login_result', {'success': False, 'message': 'Hibás jelszó'})
    
    # ------------------------------------------------------------------------
    # STÁTUSZ KEZELÉS
    # ------------------------------------------------------------------------
    
    def _broadcast_status(self):
        """Rendszer státusz broadcastolása minden kliensnek"""
        try:
            # GPU státusz
            sentinel = self.modules.get('sentinel')
            gpu_status = sentinel.get_gpu_status() if sentinel else []
            
            # King státusz
            king = self.modules.get('king')
            king_state = king.get_state() if king else {}
            
            # Heartbeat
            hb = self.modules.get('heartbeat')
            hb_state = hb.get_state() if hb else {}
            
            # Memória használat (scratchpad)
            sp = self.modules.get('scratchpad')
            memory_percent = 0
            if sp:
                summary = sp.get_summary()
                memory_percent = min(100, (summary.get('entry_count', 0) / 1000) * 100)
            
            # Modul státuszok
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
                'clients': len(self.connected_clients),
                'is_admin': session.get('admin', False)  # Ezt nem broadcastoljuk, csak az adott kliensnek
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
        # Flask leállítása nem triviális, de daemon threadként fut
        if self.scratchpad:
            self.scratchpad.set_state('web_status', 'stopped', self.name)
        
        # Socket.IO leállítása
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