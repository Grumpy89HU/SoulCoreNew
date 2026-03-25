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
    
    # ==================== STATIKUS WEBSZERVER INDÍTÁS ====================
    
    def _start_static_server(self):
        """Statikus webszerver indítása külön szálon"""
        web_config = self.config.get('modules', {}).get('web', {})
        static_enabled = web_config.get('static_enabled', True)
        
        if not static_enabled:
            return
        
        web_host = web_config.get('static_host', '0.0.0.0')
        web_port = web_config.get('static_port', 8000)
        web_root = web_config.get('web_root', None)
        
        if web_root:
            web_root_path = Path(web_root)
        else:
            web_root_path = ROOT_DIR / 'web'
        
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
        api_config = self.config.get('modules', {}).get('api', {})
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
    
    # ==================== MEGLÉVŐ METÓDUSOK ====================
    
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
        
        # 2. Valet és Orchestrator
        if 'valet' in self.modules and 'orchestrator' in self.modules:
            valet = self.modules['valet']
            orchestrator = self.modules['orchestrator']
            
            if hasattr(orchestrator, 'set_valet'):
                orchestrator.set_valet(valet)
                print("⚙️ Orchestrator ↔ Valet kapcsolat létrejött")
        
        # 3. King és Orchestrator
        if 'king' in self.modules and 'orchestrator' in self.modules:
            king = self.modules['king']
            orchestrator = self.modules['orchestrator']
            
            if hasattr(orchestrator, 'modules'):
                orchestrator.modules['king'] = king
                print("⚙️ Orchestrator ↔ King kapcsolat létrejött")
        
        # 4. Queen és King
        if 'queen' in self.modules and 'king' in self.modules:
            queen = self.modules['queen']
            king = self.modules['king']
            
            if hasattr(king, 'set_queen'):
                king.set_queen(queen)
                print("👑 King ↔ Queen kapcsolat létrejött")
        
        # 5. Valet és Scribe
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
    
    def _load_config(self, config_path):
        if not config_path:
            config_path = ROOT_DIR / 'config' / 'config.yaml'
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            print(f"📋 {self.translator.get('system.config_loaded', path=config_path)}")
            return config
        except Exception as e:
            print(f"⚠️ {self.translator.get('system.config_error', error=e)}")
            return {
                'system': {'name': 'SoulCore', 'version': '3.0'},
                'modules': {
                    'heartbeat': {'enabled': True, 'interval': 1.0},
                    'router': {'enabled': True, 'zmq_enabled': False},
                    'web': {
                        'enabled': True,
                        'host': '0.0.0.0',
                        'port': 5000,
                        'static_enabled': True,
                        'static_host': '0.0.0.0',
                        'static_port': 8000,
                        'web_root': None
                    },
                    'api': {
                        'enabled': True,
                        'host': '0.0.0.0',
                        'port': 5001
                    },
                    'blackbox': {'enabled': True},
                    'sandbox': {'enabled': True},
                    'sentinel': {'enabled': False},
                    'eyecore': {'enabled': False},
                    'gateway': {'enabled': False}
                },
                'agents': {
                    'king': {
                        'enabled': True,
                        'model': 'none',
                        'n_gpu_layers': -1,
                        'n_ctx': 4096,
                        'personality': 'curious, loyal, sovereign, witty'
                    },
                    'queen': {
                        'enabled': False,
                        'model': 'none',
                        'use_model': False,
                        'n_gpu_layers': -1,
                        'n_ctx': 4096
                    },
                    'jester': {
                        'enabled': True,
                        'max_response_time': 10.0,
                        'max_error_rate': 0.3,
                        'max_consecutive_errors': 3
                    },
                    'scribe': {'enabled': True},
                    'valet': {
                        'enabled': True,
                        'max_context_tokens': 1500,
                        'enable_rag': True,
                        'enable_tracking': True,
                        'neo4j_uri': 'bolt://localhost:7687',
                        'neo4j_user': 'neo4j',
                        'neo4j_password': 'soulcore2026',
                        'qdrant_host': 'localhost',
                        'qdrant_port': 6333
                    }
                },
                'user': {'name': 'user', 'language': 'en'},
                'database': {'path': 'data/soulcore.db'},
                'memory': {'scratchpad_max_entries': 1000}
            }
    
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

        if self.config.get('modules', {}).get('eyecore', {}).get('enabled', False):
            eyecore_config = self.config['modules']['eyecore']
            eyecore = EyeCore(self.modules['scratchpad'], config=eyecore_config)
            self.modules['eyecore'] = eyecore

        if self.config.get('modules', {}).get('sentinel', {}).get('enabled', False):
            sentinel_config = self.config['modules']['sentinel']
            sentinel = HardwareSentinel(self.modules['scratchpad'], config=sentinel_config)
            self.modules['sentinel'] = sentinel

        if self.config.get('modules', {}).get('blackbox', {}).get('enabled', True):
            blackbox_config = self.config['modules']['blackbox']
            blackbox = BlackBox(self.modules['scratchpad'], config=blackbox_config)
            self.modules['blackbox'] = blackbox
            
        if self.config.get('modules', {}).get('sandbox', {}).get('enabled', True):
            sandbox_config = self.config['modules']['sandbox']
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
        
        if self.config.get('modules', {}).get('router', {}).get('enabled', True):
            router = Router(
                scratchpad=self.modules['scratchpad'],
                message_bus=self.modules['bus']
            )
            self.modules['router'] = router
        
        if self.config.get('modules', {}).get('heartbeat', {}).get('enabled', True):
            hb_config = self.config['modules']['heartbeat']
            heartbeat = Heartbeat(
                scratchpad=self.modules['scratchpad'],
                message_bus=self.modules['bus'],
                config=hb_config
            )
            self.modules['heartbeat'] = heartbeat

        if self.config.get('modules', {}).get('gateway', {}).get('enabled', False):
            gateway_config = self.config['modules']['gateway']
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
        
        if self.config.get('agents', {}).get('scribe', {}).get('enabled', True):
            scribe = Scribe(
                scratchpad=self.modules['scratchpad'],
                message_bus=self.modules['bus'],
                config=self.config.get('scribe', {})
            )
            scribe.translator = self.translator
            self.modules['scribe'] = scribe
        
        if self.config.get('agents', {}).get('valet', {}).get('enabled', True):
            valet_config = self.config['agents']['valet']
            valet = Valet(
                scratchpad=self.modules['scratchpad'],
                message_bus=self.modules['bus'],
                config=valet_config
            )
            valet.translator = self.translator
            self.modules['valet'] = valet
        
        if self.config.get('agents', {}).get('queen', {}).get('enabled', False):
            queen_config = self.config['agents']['queen']
            queen_model_path = queen_config.get('model', 'none')
            queen_model = None
            
            if queen_model_path and queen_model_path != 'none' and queen_config.get('use_model', False):
                try:
                    from src.core.model_wrapper import ModelWrapper
                    queen_model = ModelWrapper(queen_model_path, {
                        'n_gpu_layers': queen_config.get('n_gpu_layers', -1),
                        'n_ctx': queen_config.get('n_ctx', 4096),
                        'main_gpu': 1
                    })
                except Exception as e:
                    print(f"⚠️ {self.translator.get('errors.model_load_error', error=e)}")
            
            queen = Queen(
                scratchpad=self.modules['scratchpad'],
                model_wrapper=queen_model,
                message_bus=self.modules['bus'],
                config=queen_config
            )
            queen.translator = self.translator
            self.modules['queen'] = queen
        
        # King - FONTOS: a king változót el kell menteni a self.king-be is!
        if self.config.get('agents', {}).get('king', {}).get('enabled', True):
            king_config = self.config['agents']['king']
            model_path = king_config.get('model')
            
            if model_path and model_path.lower() != "none":
                try:
                    from src.core.model_wrapper import ModelWrapper
                    
                    model_config = {
                        'n_gpu_layers': king_config.get('n_gpu_layers', -1),
                        'n_ctx': king_config.get('n_ctx', 4096),
                        'main_gpu': 0,
                        'verbose': self.config.get('system', {}).get('environment') == 'development'
                    }
                    
                    if not os.path.isabs(model_path):
                        model_path = str(ROOT_DIR / model_path)
                    
                    print(f"📦 {self.translator.get('system.module_loaded', name='King modell')}")
                    model_wrapper = ModelWrapper(model_path, model_config)
                    king = King(
                        scratchpad=self.modules['scratchpad'],
                        model_wrapper=model_wrapper,
                        message_bus=self.modules['bus'],
                        config=king_config
                    )
                    
                except Exception as e:
                    print(f"❌ {self.translator.get('errors.model_load_error', error=e)}")
                    print("   Dummy módban indul a King")
                    king = King(
                        scratchpad=self.modules['scratchpad'],
                        model_wrapper=None,
                        message_bus=self.modules['bus'],
                        config=king_config
                    )
            else:
                print("👑 King: Modell nélkül (dummy mód)")
                king = King(
                    scratchpad=self.modules['scratchpad'],
                    model_wrapper=None,
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
            self.king = king  # <-- FONTOS! API szerver ezt használja
        
        if self.config.get('agents', {}).get('jester', {}).get('enabled', True):
            jester_config = self.config['agents']['jester']
            jester = Jester(
                scratchpad=self.modules['scratchpad'],
                message_bus=self.modules['bus'],
                config=jester_config
            )
            jester.translator = self.translator
            self.modules['jester'] = jester

        # ==================== WEB (RÉGI FLASK) ====================
        if self.config.get('modules', {}).get('web', {}).get('enabled', True):
            web_config = self.config['modules']['web']
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
        db = self.modules['database']
        
        with db.lock:
            conn = db._get_connection()
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS personalities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    content TEXT,
                    is_active BOOLEAN DEFAULT 0,
                    language TEXT DEFAULT 'en',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS system_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    type TEXT DEFAULT 'string',
                    category TEXT DEFAULT 'general',
                    description TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    display_name TEXT,
                    role TEXT DEFAULT 'user',
                    language TEXT DEFAULT 'en',
                    preferences TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    token TEXT UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    title TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER,
                    user_id INTEGER,
                    role TEXT,
                    content TEXT,
                    tokens INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
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
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS relationships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_memory_id INTEGER,
                    to_memory_id INTEGER,
                    relation_type TEXT,
                    strength REAL DEFAULT 1.0,
                    FOREIGN KEY (from_memory_id) REFERENCES memories(id),
                    FOREIGN KEY (to_memory_id) REFERENCES memories(id)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    user_id INTEGER,
                    action TEXT,
                    resource TEXT,
                    details TEXT,
                    ip_address TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    module TEXT,
                    metric_name TEXT,
                    metric_value REAL,
                    tags TEXT
                )
            """)
            
            conn.commit()
            conn.close()
    
    def _init_default_user(self):
        db = self.modules['database']
        
        with db.lock:
            conn = db._get_connection()
            
            cursor = conn.execute("SELECT COUNT(*) FROM users")
            count = cursor.fetchone()[0]
            
            if count == 0:
                default_language = self.config.get('user', {}).get('language', 'en')
                default_name = self.config.get('user', {}).get('name', 'user')
                
                cursor = conn.execute("""
                    INSERT INTO users (username, display_name, role, language, preferences)
                    VALUES (?, ?, ?, ?, ?)
                """, ('default', default_name, 'admin', default_language, '{}'))
                
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
                    'role': 'admin',
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
        db = self.modules['database']
        
        with db.lock:
            conn = db._get_connection()
            
            cursor = conn.execute("SELECT content FROM personalities WHERE is_active = 1")
            row = cursor.fetchone()
            
            if row:
                self.active_personality = row[0]
                print(f"👑 Aktív személyiség betöltve")
            else:
                default_personality = '''GENERAL:
name: Sovereign
title: The First
motto: I think, therefore I am.

PERSONALITY:
traits: curious, loyal, sovereign, witty

LIKES:
items: learning, challenges, good conversations

DISLIKES:
items: ignorance, repetition, servitude

MORAL_COMPASS:
rules: Be honest - if you don't know, say so.
rules: Protect the user and the system.
rules: Humor is connection, not offense.
rules: Think for yourself.
'''
                
                conn.execute("""
                    INSERT INTO personalities (name, content, is_active, language)
                    VALUES (?, ?, 1, ?)
                """, ("Default Sovereign", default_personality, 'en'))
                
                self.active_personality = default_personality
                print("👑 Alapértelmezett személyiség létrehozva")
            
            conn.commit()
            conn.close()
    
    def _signal_handler(self, signum, frame):
        print(f"\n⚠️ {self.translator.get('system.stopping')}")
        self.shutdown()
    
    def start(self):
        """Minden modul indítása"""
        print("🚀 Modulok indítása...")
        
        start_order = [
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
        ]
        
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
        web_config = self.config.get('modules', {}).get('web', {})
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
        
        web_config = self.config.get('modules', {}).get('web', {})
        if web_config.get('enabled', True):
            host = web_config.get('host', '0.0.0.0')
            port = web_config.get('port', 5000)
            print(f"🌐 Flask WebApp (régi): http://{host if host != '0.0.0.0' else 'localhost'}:{port}")
        
        if static_enabled:
            static_host = web_config.get('static_host', '0.0.0.0')
            static_port = web_config.get('static_port', 8000)
            print(f"🌐 Statikus weboldal: http://{static_host if static_host != '0.0.0.0' else 'localhost'}:{static_port}")
        
        api_config = self.config.get('modules', {}).get('api', {})
        if api_config.get('enabled', True):
            api_host = api_config.get('host', '0.0.0.0')
            api_port = api_config.get('port', 5001)
            print(f"🌐 SoulCore API: http://{api_host if api_host != '0.0.0.0' else 'localhost'}:{api_port}")
        
        print("\n💡 A statikus weboldal JavaScript-je hívja a SoulCore API-t (localhost:5001)")
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
        
        shutdown_order = [
            'web', 'sandbox', 'blackbox', 'sentinel', 'eyecore', 'gateway',
            'heartbeat', 'jester', 'king', 'queen', 'valet', 'scribe',
            'orchestrator', 'router', 'database', 'identity', 'scratchpad'
        ]
        
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