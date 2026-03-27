#!/usr/bin/env python3
"""
SoulCore 3.0 - Main Entry Point
Konfiguráció betöltés, modulok indítása.
"""

import os
import sys
import time
import signal
import threading
import yaml
import uuid
import secrets
from pathlib import Path
from datetime import datetime, timedelta

# Projekt gyökér
ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

from src.core.orchestrator import Orchestrator
from src.core.heartbeat import Heartbeat
from src.core.router import Router
from src.core.identity import SoulIdentity
from src.agents.king import King
from src.agents.jester import Jester
from src.agents.scribe import Scribe
from src.agents.valet import Valet
from src.agents.queen import Queen
from src.memory.scratchpad import Scratchpad
from src.web.app import WebApp
from src.gateway.diplomatic import DiplomaticGateway
from src.vision.eye_core import EyeCore
from src.hardware.sentinel import HardwareSentinel
from src.debug.blackbox import BlackBox
from src.tools.sandbox import Sandbox
from src.database.models import Database
from src.i18n.translator import get_translator
from src.bus.message_bus import MessageBus
from src.api.server import APIServer

# Statikus webszerver import
from server.webserver import StaticServer


class SoulCore:
    """Fő alkalmazás osztály - összefogja az összes modult"""
    
    def __init__(self, config_path=None):
        print("⚡ SoulCore 3.0 indul...")
        
        # Fordító inicializálása (alapértelmezett angol)
        self.translator = get_translator('en')
        
        # Konfiguráció betöltés
        self.config = self._load_config(config_path)
        self.running = True
        self.modules = {}
        self.current_user = None
        self.start_time = time.time()
        
        # Rendszer azonosító
        self.system_id = self._get_system_id()
        
        # API szerver (később indítjuk, miután a kernel kész)
        self.api_server = None
        
        # Statikus webszerver
        self.static_server = None
        self.static_server_thread = None
        
        # Modulok inicializálása
        self._init_modules()
        
        # Modulok összekapcsolása
        self._connect_modules()
        
        # WebApp és King összekapcsolása
        self._connect_webapp_king()
        
        # Rendszerindulás naplózása
        self._log_system_start()
        
        # Signal kezelés
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        print(self.translator.get('system.started'))
    
    # ==================== KONFIGURÁCIÓ BETÖLTÉS ====================
    
    def _load_config(self, config_path):
        """Konfiguráció betöltése fájlból, fallback default.yaml"""
        
        # Alapértelmezett konfiguráció betöltése
        default_config_path = ROOT_DIR / 'config' / 'default.yaml'
        config = {}
        
        if default_config_path.exists():
            try:
                with open(default_config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
                print(f"📋 Alapértelmezett konfiguráció betöltve: {default_config_path}")
            except Exception as e:
                print(f"⚠️ Alapértelmezett konfiguráció betöltési hiba: {e}")
        
        # Felhasználói konfiguráció betöltése (felülírja a default-ot)
        if not config_path:
            config_path = ROOT_DIR / 'config' / 'config.yaml'
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = yaml.safe_load(f) or {}
            
            # Mély összefésülés
            config = self._deep_merge(config, user_config)
            print(f"📋 Felhasználói konfiguráció betöltve: {config_path}")
            
        except Exception as e:
            print(f"⚠️ Felhasználói konfiguráció betöltési hiba: {e}")
            print("   Alapértelmezett konfigurációval indulok.")
        
        return config
    
    def _deep_merge(self, base, override):
        """Két dictionary mély összefésülése"""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    # ==================== STATIKUS WEBSZERVER INDÍTÁS ====================
    
    def _start_static_server(self):
        """Statikus webszerver indítása külön szálon"""
        web_config = self.config.get('web', {})  # <-- modules.web helyett web
        static_enabled = web_config.get('static_enabled', True)
        
        if not static_enabled:
            return
        
        web_host = web_config.get('static_host', '0.0.0.0')
        web_port = web_config.get('static_port', 8000)
        web_root = web_config.get('web_root', None)
        
        if web_root:
            web_root_path = Path(web_root)
        else:
            # A configból olvassuk, ne hardkód
            web_root = web_config.get('web_root_path', 'web')
            web_root_path = ROOT_DIR / web_root
        
        self.static_server = StaticServer(
            host=web_host,
            port=web_port,
            web_root=web_root_path
        )
        
        # Indítás külön szálban
        self.static_server.start_in_thread()
        
        print(f"🌐 Statikus webszerver elindítva: http://{web_host}:{web_port}")
    
    def _stop_static_server(self):
        """Statikus webszerver leállítása"""
        if self.static_server:
            print("\n🛑 Statikus webszerver leállítása...")
            self.static_server.stop()
    
    # ==================== API SZERVER INDÍTÁS ====================
    
    def _start_api_server(self):
        """API szerver indítása (HTTP + WebSocket)"""
        api_config = self.config.get('api', {})  # <-- modules.api helyett gyökér api
        api_enabled = api_config.get('enabled', True)
        
        if not api_enabled:
            print("⚠️ API szerver ki van kapcsolva")
            return
        
        api_host = api_config.get('host', '0.0.0.0')
        api_port = api_config.get('port', 5001)
        ws_port = api_config.get('ws_port', 5002)
        
        self.api_server = APIServer(self, host=api_host, http_port=api_port, ws_port=ws_port)
        self.api_server.start_in_thread()
        
        print(f"🌐 SoulCore API szerver: http://{api_host}:{api_port}")
        print(f"🔌 WebSocket: ws://{api_host}:{ws_port}")
    
    # ==================== MODULOK ÖSSZEKAPCSOLÁSA ====================
    
    def _connect_modules(self):
        """Modulok összekapcsolása"""
        
        # 1. Valet és King
        if 'valet' in self.modules and 'king' in self.modules:
            valet = self.modules['valet']
            king = self.modules['king']
            
            if hasattr(king, 'set_valet'):
                king.set_valet(valet)
                print("👑 King ↔ Valet kapcsolat létrejött")
            
            if hasattr(king, 'model') and king.model and hasattr(valet, 'set_embedder'):
                valet.set_embedder(king.model)
                print("🔗 Valet embedder beállítva (King modelljével)")
        
        # 2. King és Graph-Vault (új)
        if 'king' in self.modules and 'graph_vault' in self.modules:
            king = self.modules['king']
            graph_vault = self.modules['graph_vault']
            if hasattr(king, 'set_graph_vault'):
                king.set_graph_vault(graph_vault)
                print("👑 King ↔ Graph-Vault kapcsolat létrejött")
        
        # 3. Valet és Orchestrator
        if 'valet' in self.modules and 'orchestrator' in self.modules:
            valet = self.modules['valet']
            orchestrator = self.modules['orchestrator']
            
            if hasattr(orchestrator, 'set_valet'):
                orchestrator.set_valet(valet)
                print("⚙️ Orchestrator ↔ Valet kapcsolat létrejött")
        
        # 4. King és Orchestrator
        if 'king' in self.modules and 'orchestrator' in self.modules:
            king = self.modules['king']
            orchestrator = self.modules['orchestrator']
            
            if hasattr(orchestrator, 'modules'):
                orchestrator.modules['king'] = king
                print("⚙️ Orchestrator ↔ King kapcsolat létrejött")
        
        # 5. Queen és King
        if 'queen' in self.modules and 'king' in self.modules:
            queen = self.modules['queen']
            king = self.modules['king']
            
            if hasattr(king, 'set_queen'):
                king.set_queen(queen)
                print("👑 King ↔ Queen kapcsolat létrejött")
        
        # 6. Valet és Scribe
        if 'valet' in self.modules and 'scribe' in self.modules:
            valet = self.modules['valet']
            scribe = self.modules['scribe']
            
            if hasattr(scribe, 'set_valet'):
                scribe.set_valet(valet)
                print("📝 Scribe ↔ Valet kapcsolat létrejött")
    
    def _connect_webapp_king(self):
        """WebApp és King összekapcsolása (régi Flask)"""
        
        if 'web' in self.modules and 'king' in self.modules:
            web = self.modules['web']
            king = self.modules['king']
            
            def king_response_callback(response_text, conversation_id, trace_id):
                if web and hasattr(web, 'socketio'):
                    try:
                        web.socketio.emit("chat:response", {
                            "text": response_text,
                            "trace_id": trace_id,
                            "conversation_id": conversation_id
                        })
                    except Exception as e:
                        print(f"⚠️ King callback hiba: {e}")
            
            if hasattr(king, 'set_response_callback'):
                king.set_response_callback(king_response_callback)
                print("🔗 King ↔ WebApp kapcsolat létrejött")
        
        if 'web' in self.modules and 'orchestrator' in self.modules:
            orch = self.modules['orchestrator']
            web = self.modules['web']
            
            if hasattr(orch, 'set_webapp_callback'):
                def orch_response_callback(response_text, conversation_id, trace_id):
                    if web and hasattr(web, 'socketio'):
                        try:
                            web.socketio.emit("chat:response", {
                                "text": response_text,
                                "trace_id": trace_id,
                                "conversation_id": conversation_id
                            })
                        except Exception as e:
                            print(f"⚠️ Orchestrator callback hiba: {e}")
                
                orch.set_webapp_callback(orch_response_callback)
                print("🔗 Orchestrator ↔ WebApp kapcsolat létrejött")
    
    # ==================== RENDSZER AZONOSÍTÓ ====================
    
    def _get_system_id(self) -> str:
        id_file = ROOT_DIR / 'data' / 'system.id'
        if id_file.exists():
            with open(id_file, 'r') as f:
                return f.read().strip()
        else:
            system_id = str(uuid.uuid4())
            id_file.parent.mkdir(parents=True, exist_ok=True)
            with open(id_file, 'w') as f:
                f.write(system_id)
            return system_id
    
    def _log_system_start(self):
        if 'blackbox' in self.modules:
            self.modules['blackbox'].log(
                event_type='system',
                source='main',
                data={
                    'action': 'start',
                    'system_id': self.system_id,
                    'version': '3.0',
                    'python_version': sys.version,
                    'platform': sys.platform
                },
                level='info'
            )
    
    # ==================== MODULOK INICIALIZÁLÁSA ====================
    
    def _init_modules(self):
        """Minden modul példányosítása"""
        print("📦 Modulok betöltése...")
        
        # ==================== MEMÓRIA ÉS ALAP MODULOK ====================
        self.modules['scratchpad'] = Scratchpad(
            max_history=self.config.get('memory', {}).get('scratchpad_max_entries', 1000)
        )

        db_path = self.config.get('database', {}).get('path', 'data/soulcore.db')
        self.modules['database'] = Database(db_path)
        
        self._init_database_tables()
        self._init_default_user()
        self._load_active_personality()
        
        identity_file = self.config.get('system', {}).get('identity_file', 'config/identity.inf')
        self.modules['identity'] = SoulIdentity(self.modules['scratchpad'], config_path=ROOT_DIR / identity_file)

        # EyeCore
        eyecore_config = self.config.get('modules', {}).get('eyecore', {})
        if eyecore_config.get('enabled', False):
            eyecore = EyeCore(self.modules['scratchpad'], config=eyecore_config)
            self.modules['eyecore'] = eyecore

        # Sentinel
        sentinel_config = self.config.get('modules', {}).get('sentinel', {})
        if sentinel_config.get('enabled', False):
            sentinel = HardwareSentinel(self.modules['scratchpad'], config=sentinel_config)
            self.modules['sentinel'] = sentinel

        # BlackBox
        blackbox_config = self.config.get('modules', {}).get('blackbox', {})
        if blackbox_config.get('enabled', True):
            blackbox = BlackBox(self.modules['scratchpad'], config=blackbox_config)
            self.modules['blackbox'] = blackbox
            
        # Sandbox
        sandbox_config = self.config.get('modules', {}).get('sandbox', {})
        if sandbox_config.get('enabled', True):
            sandbox = Sandbox(self.modules['scratchpad'], config=sandbox_config)
            self.modules['sandbox'] = sandbox

        # ==================== BUSZ ====================
        bus_config = self.config.get('bus', {})
        self.modules['bus'] = MessageBus(bus_config)
        self.modules['bus'].start()
        print("📡 Message Bus inicializálva")

        # ==================== CORE MODULOK ====================
        
        self.modules['orchestrator'] = Orchestrator(
            scratchpad=self.modules['scratchpad'],
            message_bus=self.modules['bus'],
            config=self.config.get('orchestrator', {})
        )
        
        if 'database' in self.modules:
            self.modules['orchestrator'].set_database(self.modules['database'])
        
        router_config = self.config.get('modules', {}).get('router', {})
        if router_config.get('enabled', True):
            router = Router(
                scratchpad=self.modules['scratchpad'],
                message_bus=self.modules['bus']
            )
            self.modules['router'] = router
        
        heartbeat_config = self.config.get('modules', {}).get('heartbeat', {})
        if heartbeat_config.get('enabled', True):
            heartbeat = Heartbeat(
                scratchpad=self.modules['scratchpad'],
                message_bus=self.modules['bus'],
                config=heartbeat_config
            )
            self.modules['heartbeat'] = heartbeat

        gateway_config = self.config.get('modules', {}).get('gateway', {})
        if gateway_config.get('enabled', False):
            try:
                gateway = DiplomaticGateway(
                    scratchpad=self.modules['scratchpad'],
                    orchestrator=self.modules['orchestrator'],
                    config=gateway_config
                )
                gateway.system_id = self.system_id
                self.modules['gateway'] = gateway
            except TypeError as e:
                print(f"⚠️ Gateway inicializálási hiba: {e}")
                
        # ==================== ÁGENSEK ====================
        
        scribe_config = self.config.get('agents', {}).get('scribe', {})
        if scribe_config.get('enabled', True):
            scribe = Scribe(
                scratchpad=self.modules['scratchpad'],
                message_bus=self.modules['bus'],
                config=scribe_config
            )
            scribe.translator = self.translator
            self.modules['scribe'] = scribe
        
        valet_config = self.config.get('agents', {}).get('valet', {})
        if valet_config.get('enabled', True):
            valet = Valet(
                scratchpad=self.modules['scratchpad'],
                message_bus=self.modules['bus'],
                config=valet_config
            )
            valet.translator = self.translator
            self.modules['valet'] = valet
        
        queen_config = self.config.get('agents', {}).get('queen', {})
        if queen_config.get('enabled', False):
            queen_model_path = queen_config.get('model', '')
            queen_model = None
            
            if queen_model_path and queen_model_path.lower() not in ['', 'none'] and queen_config.get('use_model', False):
                try:
                    from src.core.model_wrapper import ModelWrapper
                    queen_model = ModelWrapper(queen_model_path, {
                        'n_gpu_layers': queen_config.get('n_gpu_layers', -1),
                        'n_ctx': queen_config.get('n_ctx', 4096),
                        'main_gpu': 1
                    })
                except Exception as e:
                    print(f"⚠️ Queen modell betöltési hiba: {e}")
            
            queen = Queen(
                scratchpad=self.modules['scratchpad'],
                model_wrapper=queen_model,
                message_bus=self.modules['bus'],
                config=queen_config
            )
            queen.translator = self.translator
            self.modules['queen'] = queen
        
        # King
        king_config = self.config.get('agents', {}).get('king', {})
        if king_config.get('enabled', True):
            model_path = king_config.get('model', '')
            model_wrapper = None
            
            if model_path and model_path.lower() not in ['', 'none']:
                try:
                    from src.core.model_wrapper import ModelWrapper
                    
                    if not os.path.isabs(model_path):
                        model_path = str(ROOT_DIR / model_path)
                    
                    if os.path.exists(model_path):
                        model_config = {
                            'n_gpu_layers': king_config.get('n_gpu_layers', -1),
                            'n_ctx': king_config.get('n_ctx', 4096),
                            'main_gpu': 0,
                            'verbose': self.config.get('system', {}).get('environment') == 'development'
                        }
                        model_wrapper = ModelWrapper(model_path, model_config)
                        print(f"📦 King modell betöltve: {model_path}")
                    else:
                        print(f"⚠️ King modell nem található: {model_path}")
                except Exception as e:
                    print(f"❌ King modell betöltési hiba: {e}")
            
            if not model_wrapper:
                print("👑 King: Modell nélkül (dummy mód)")
            
            king = King(
                scratchpad=self.modules['scratchpad'],
                model_wrapper=model_wrapper,
                message_bus=self.modules['bus'],
                config=king_config
            )
            king.translator = self.translator
            
            # Személyiség beállítása
            if hasattr(self, 'active_personality') and self.active_personality:
                self.modules['scratchpad'].write_note('king', 'personality', self.active_personality)
            elif 'personality' in king_config:
                self.modules['scratchpad'].write_note('king', 'personality', king_config['personality'])
            
            self.modules['king'] = king
            self.king = king
        
        jester_config = self.config.get('agents', {}).get('jester', {})
        if jester_config.get('enabled', True):
            jester = Jester(
                scratchpad=self.modules['scratchpad'],
                message_bus=self.modules['bus'],
                config=jester_config
            )
            jester.translator = self.translator
            self.modules['jester'] = jester

        # ==================== WEB (RÉGI FLASK) ====================
        web_config = self.config.get('web', {})  # <-- modules.web helyett web
        if web_config.get('enabled', True):
            web = WebApp(self.modules)
            web.host = web_config.get('host', '0.0.0.0')
            web.port = web_config.get('port', 5000)
            web.translator = self.translator
            web.system_id = self.system_id
            self.modules['web'] = web
            print("⚠️ Flask WebApp (régi) bekapcsolva - kompatibilitás miatt")
        else:
            print("📁 Flask WebApp (régi) kikapcsolva")
        
        print(f"✅ {len(self.modules)} modul betöltve")
    
    def _init_database_tables(self):
        """Adatbázis táblák inicializálása (csak ha nem léteznek)"""
        db = self.modules['database']
        
        with db.lock:
            conn = db._get_connection()
            
            # Táblák létrehozása (csak ha hiányoznak)
            tables = [
                """CREATE TABLE IF NOT EXISTS personalities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    content TEXT,
                    is_active BOOLEAN DEFAULT 0,
                    language TEXT DEFAULT 'en',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )""",
                """CREATE TABLE IF NOT EXISTS system_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    type TEXT DEFAULT 'string',
                    category TEXT DEFAULT 'general',
                    description TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )""",
                """CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    display_name TEXT,
                    role TEXT DEFAULT 'user',
                    language TEXT DEFAULT 'en',
                    preferences TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP
                )""",
                """CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    token TEXT UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )""",
                """CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    title TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )""",
                """CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER,
                    user_id INTEGER,
                    role TEXT,
                    content TEXT,
                    tokens INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )""",
                """CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    type TEXT,
                    content TEXT,
                    emotional_charge REAL DEFAULT 0,
                    importance REAL DEFAULT 0.5,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_accessed TIMESTAMP,
                    access_count INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )""",
                """CREATE TABLE IF NOT EXISTS relationships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_memory_id INTEGER,
                    to_memory_id INTEGER,
                    relation_type TEXT,
                    strength REAL DEFAULT 1.0,
                    FOREIGN KEY (from_memory_id) REFERENCES memories(id),
                    FOREIGN KEY (to_memory_id) REFERENCES memories(id)
                )""",
                """CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    user_id INTEGER,
                    action TEXT,
                    resource TEXT,
                    details TEXT,
                    ip_address TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )""",
                """CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    module TEXT,
                    metric_name TEXT,
                    metric_value REAL,
                    tags TEXT
                )"""
            ]
            
            for table_sql in tables:
                conn.execute(table_sql)
            
            conn.commit()
            conn.close()
    
    def _init_default_user(self):
        """Alapértelmezett felhasználó létrehozása a config alapján"""
        db = self.modules['database']
        
        with db.lock:
            conn = db._get_connection()
            
            cursor = conn.execute("SELECT COUNT(*) FROM users")
            count = cursor.fetchone()[0]
            
            if count == 0:
                user_config = self.config.get('user', {})
                default_language = user_config.get('language', 'en')
                default_name = user_config.get('name', 'user')
                default_role = user_config.get('role', 'admin')
                
                cursor = conn.execute("""
                    INSERT INTO users (username, display_name, role, language, preferences)
                    VALUES (?, ?, ?, ?, ?)
                """, ('default', default_name, default_role, default_language, '{}'))
                
                user_id = cursor.lastrowid
                
                token = secrets.token_urlsafe(32)
                expires_at = time.time() + 30 * 86400
                
                conn.execute("""
                    INSERT INTO sessions (user_id, token, expires_at)
                    VALUES (?, ?, ?)
                """, (user_id, token, expires_at))
                
                self.current_user = {
                    'id': user_id,
                    'username': 'default',
                    'display_name': default_name,
                    'role': default_role,
                    'language': default_language,
                    'token': token
                }
                
                self.translator.set_language(default_language)
                
                print(f"👤 Alapértelmezett felhasználó: {default_name} ({default_language})")
                
                conn.execute("""
                    INSERT INTO conversations (user_id, title)
                    VALUES (?, ?)
                """, (user_id, self.translator.get('conversation.default_title', 'New Conversation')))
                
                conn.execute("""
                    INSERT INTO audit_log (user_id, action, resource, details)
                    VALUES (?, ?, ?, ?)
                """, (user_id, 'create', 'user', 'Default user created'))
            
            conn.commit()
            conn.close()
    
    def _load_active_personality(self):
        """Aktív személyiség betöltése (identity.inf elsődleges)"""
        db = self.modules['database']
        
        # Először próbáljuk az identity.inf fájlt
        identity_file = self.config.get('system', {}).get('identity_file', 'config/identity.inf')
        identity_path = ROOT_DIR / identity_file
        
        if identity_path.exists():
            try:
                with open(identity_path, 'r', encoding='utf-8') as f:
                    personality = f.read()
                
                with db.lock:
                    conn = db._get_connection()
                    
                    # Ellenőrizzük, hogy van-e már aktív
                    cursor = conn.execute("SELECT id FROM personalities WHERE is_active = 1")
                    existing = cursor.fetchone()
                    
                    if existing:
                        conn.execute("UPDATE personalities SET is_active = 0 WHERE is_active = 1")
                    
                    conn.execute("""
                        INSERT INTO personalities (name, content, is_active, language)
                        VALUES (?, ?, 1, ?)
                    """, ('Sovereign (identity.inf)', personality, 'en'))
                    
                    conn.commit()
                    conn.close()
                
                self.active_personality = personality
                print(f"👑 Személyiség betöltve: {identity_file}")
                return
                
            except Exception as e:
                print(f"⚠️ identity.inf betöltési hiba: {e}")
        
        # Ha nincs identity.inf, próbáljuk az adatbázist
        with db.lock:
            conn = db._get_connection()
            
            cursor = conn.execute("SELECT content FROM personalities WHERE is_active = 1")
            row = cursor.fetchone()
            
            if row:
                self.active_personality = row[0]
                print(f"👑 Aktív személyiség betöltve (adatbázisból)")
            else:
                # Nincs személyiség, de nem hardkódolunk
                self.active_personality = None
                print("⚠️ Nincs aktív személyiség beállítva")
            
            conn.commit()
            conn.close()
    
    def _signal_handler(self, signum, frame):
        print(f"\n⚠️ {self.translator.get('system.stopping')}")
        self.shutdown()
    
    def start(self):
        """Minden modul indítása"""
        print("🚀 Modulok indítása...")
        
        # Indítási sorrend a configból (ha van)
        start_order = self.config.get('start_order', [
            'scratchpad',
            'router',
            'orchestrator',
            'scribe',
            'valet',
            'queen',
            'king',
            'jester',
            'heartbeat',
            'gateway',
            'eyecore',
            'sentinel',
            'blackbox',
            'sandbox',
            'web'
        ])
        
        for name in start_order:
            if name in self.modules:
                module = self.modules[name]
                if hasattr(module, 'start'):
                    print(f"  └─ {name} indul...")
                    try:
                        if name in ['web', 'heartbeat']:
                            threading.Thread(target=module.start, daemon=True).start()
                        else:
                            module.start()
                    except Exception as e:
                        print(f"  ❌ {name} hiba: {e}")
        
        # API szerver indítása (kernel után)
        self._start_api_server()
        
        # Statikus webszerver indítása
        web_config = self.config.get('web', {})
        static_enabled = web_config.get('static_enabled', True)
        
        if static_enabled:
            print("\n📁 Statikus webszerver indítása...")
            self._start_static_server()
        else:
            print("\n⚠️ Statikus webszerver ki van kapcsolva")
        
        if self.current_user:
            self.modules['scratchpad'].set_state('user_name', self.current_user['display_name'], 'system')
            self.modules['scratchpad'].set_state('user_language', self.current_user['language'], 'system')
            self.modules['scratchpad'].set_state('user_role', self.current_user['role'], 'system')
        
        print(f"\n✅ {self.translator.get('system.started')}")
        print(f"   System ID: {self.system_id[:8]}...")
        
        # Web elérhetőségek
        web_config = self.config.get('web', {})
        if web_config.get('enabled', True):
            host = web_config.get('host', '0.0.0.0')
            port = web_config.get('port', 5000)
            print(f"🌐 Flask WebApp (régi): http://{host if host != '0.0.0.0' else 'localhost'}:{port}")
        
        if static_enabled:
            static_host = web_config.get('static_host', '0.0.0.0')
            static_port = web_config.get('static_port', 8000)
            print(f"🌐 Statikus weboldal: http://{static_host if static_host != '0.0.0.0' else 'localhost'}:{static_port}")
        
        api_config = self.config.get('api', {})
        if api_config.get('enabled', True):
            api_host = api_config.get('host', '0.0.0.0')
            api_port = api_config.get('port', 5001)
            print(f"🌐 SoulCore API: http://{api_host if api_host != '0.0.0.0' else 'localhost'}:{api_port}")
        
        print("\n💡 A statikus weboldal JavaScript-je hívja a SoulCore API-t")
        print("=" * 50)
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.shutdown()
    
    def shutdown(self):
        """Minden modul leállítása"""
        print(f"\n📴 {self.translator.get('system.stopping')}")
        self.running = False
        
        self._stop_static_server()
        
        if 'blackbox' in self.modules:
            uptime = time.time() - self.start_time
            self.modules['blackbox'].log(
                event_type='system',
                source='main',
                data={'action': 'stop', 'uptime': uptime},
                level='info'
            )
        
        shutdown_order = self.config.get('shutdown_order', [
            'web', 'sandbox', 'blackbox', 'sentinel', 'eyecore', 'gateway',
            'heartbeat', 'jester', 'king', 'queen', 'valet', 'scribe',
            'orchestrator', 'router', 'database', 'identity', 'scratchpad'
        ])
        
        for name in shutdown_order:
            if name in self.modules:
                module = self.modules[name]
                if hasattr(module, 'stop'):
                    print(f"  └─ {name} leáll...")
                    try:
                        module.stop()
                    except Exception as e:
                        print(f"  ⚠️ {name} leállítási hiba: {e}")
        
        print(f"👋 {self.translator.get('system.stopped')}")
        sys.exit(0)


if __name__ == "__main__":
    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    app = SoulCore(config_path)
    app.start()