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
        self.current_user = None  # Aktív felhasználó
        self.start_time = time.time()
        
        # Rendszer azonosító (egyedi UUID a példányhoz)
        self.system_id = self._get_system_id()
        
        # Modulok inicializálása
        self._init_modules()
        
        # Modulok összekapcsolása (Valet, King, Orchestrator)
        self._connect_modules()
        
        # WebApp és King összekapcsolása
        self._connect_webapp_king()
        
        # Rendszerindulás naplózása
        self._log_system_start()
        
        # Signal kezelés a szép leálláshoz
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        print(self.translator.get('system.started'))
    
    def _connect_modules(self):
        """Modulok összekapcsolása (Valet ↔ King ↔ Orchestrator)"""
        
        # 1. Valet és King összekapcsolása
        if 'valet' in self.modules and 'king' in self.modules:
            valet = self.modules['valet']
            king = self.modules['king']
            
            if hasattr(king, 'set_valet'):
                king.set_valet(valet)
                print("👑 King ↔ Valet kapcsolat létrejött")
            
            # Ha van embedder a King-ben, adjuk át a Valet-nek
            if hasattr(king, 'model') and king.model and hasattr(valet, 'set_embedder'):
                valet.set_embedder(king.model)
                print("🔗 Valet embedder beállítva (King modelljével)")
        
        # 2. Valet és Orchestrator összekapcsolása
        if 'valet' in self.modules and 'orchestrator' in self.modules:
            valet = self.modules['valet']
            orchestrator = self.modules['orchestrator']
            
            if hasattr(orchestrator, 'set_valet'):
                orchestrator.set_valet(valet)
                print("⚙️ Orchestrator ↔ Valet kapcsolat létrejött")
        
        # 3. King és Orchestrator összekapcsolása
        if 'king' in self.modules and 'orchestrator' in self.modules:
            king = self.modules['king']
            orchestrator = self.modules['orchestrator']
            
            # King hozzáadása az orchestrator moduljaihoz
            if hasattr(orchestrator, 'modules'):
                orchestrator.modules['king'] = king
                print("⚙️ Orchestrator ↔ King kapcsolat létrejött")
        
        # 4. Queen és King összekapcsolása
        if 'queen' in self.modules and 'king' in self.modules:
            queen = self.modules['queen']
            king = self.modules['king']
            
            if hasattr(king, 'set_queen'):
                king.set_queen(queen)
                print("👑 King ↔ Queen kapcsolat létrejött")
        
        # 5. Valet és Scribe összekapcsolása (opcionális)
        if 'valet' in self.modules and 'scribe' in self.modules:
            valet = self.modules['valet']
            scribe = self.modules['scribe']
            
            if hasattr(scribe, 'set_valet'):
                scribe.set_valet(valet)
                print("📝 Scribe ↔ Valet kapcsolat létrejött")
    
    def _connect_webapp_king(self):
        """WebApp és King összekapcsolása a válaszok továbbításához"""
        if 'web' in self.modules and 'king' in self.modules:
            web = self.modules['web']
            king = self.modules['king']
            
            # King callback beállítása a WebApp felé
            def king_response_callback(response_text, conversation_id, trace_id):
                """A King válaszának továbbítása a WebApp felé"""
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
        
        # Orchestrator és WebApp összekapcsolása
        if 'web' in self.modules and 'orchestrator' in self.modules:
            orch = self.modules['orchestrator']
            web = self.modules['web']
            
            # Orchestrator callback beállítása
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
        """Rendszer egyedi azonosító lekérése vagy generálása"""
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
        """Rendszerindulás naplózása a BlackBox-ba"""
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
        """Konfiguráció betöltése YAML-ből"""
        if not config_path:
            config_path = ROOT_DIR / 'config' / 'config.yaml'
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            print(f"📋 {self.translator.get('system.config_loaded', path=config_path)}")
            return config
        except Exception as e:
            print(f"⚠️ {self.translator.get('system.config_error', error=e)}")
            # Alapértelmezett konfig (hardkódolás nélkül)
            return {
                'system': {'name': 'SoulCore', 'version': '3.0'},
                'modules': {
                    'heartbeat': {'enabled': True, 'interval': 1.0},
                    'router': {'enabled': True, 'zmq_enabled': False},
                    'web': {'enabled': True, 'host': '0.0.0.0', 'port': 5000},
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
        """Minden modul példányosítása a konfig alapján"""
        print("📦 Modulok betöltése...")
        
        # ==================== MEMÓRIA ÉS ALAP MODULOK ====================
        # MEMÓRIA (első, mindenki ezt használja)
        self.modules['scratchpad'] = Scratchpad(
            max_history=self.config.get('memory', {}).get('scratchpad_max_entries', 1000)
        )

        # ADATBÁZIS (második, mert mások használhatják)
        db_path = self.config.get('database', {}).get('path', 'data/soulcore.db')
        self.modules['database'] = Database(db_path)
        
        # Adatbázis táblák létrehozása, ha még nem léteznek
        self._init_database_tables()
        
        # Alapértelmezett felhasználó létrehozása (ha még nincs)
        self._init_default_user()
        
        # Aktív személyiség betöltése
        self._load_active_personality()
        
        # IDENTITY (lélek)
        identity_file = self.config.get('system', {}).get('identity_file', 'config/identity.inf')
        self.modules['identity'] = SoulIdentity(self.modules['scratchpad'], config_path=ROOT_DIR / identity_file)

        # EYE-CORE (vizuális)
        if self.config.get('modules', {}).get('eyecore', {}).get('enabled', False):
            eyecore_config = self.config['modules']['eyecore']
            eyecore = EyeCore(self.modules['scratchpad'], config=eyecore_config)
            self.modules['eyecore'] = eyecore

        # SENTINEL (hardver)
        if self.config.get('modules', {}).get('sentinel', {}).get('enabled', False):
            sentinel_config = self.config['modules']['sentinel']
            sentinel = HardwareSentinel(self.modules['scratchpad'], config=sentinel_config)
            self.modules['sentinel'] = sentinel

        # BLACKBOX (naplózás)
        if self.config.get('modules', {}).get('blackbox', {}).get('enabled', True):
            blackbox_config = self.config['modules']['blackbox']
            blackbox = BlackBox(self.modules['scratchpad'], config=blackbox_config)
            self.modules['blackbox'] = blackbox
            
        # SANDBOX (kód futtatás)
        if self.config.get('modules', {}).get('sandbox', {}).get('enabled', True):
            sandbox_config = self.config['modules']['sandbox']
            sandbox = Sandbox(self.modules['scratchpad'], config=sandbox_config)
            self.modules['sandbox'] = sandbox

        # ==================== CORE MODULOK ====================
        # Orchestrator (KVK parser, kontextus)
        self.modules['orchestrator'] = Orchestrator(
            self.modules['scratchpad'], 
            modules=self.modules
        )
        # Adatbázis beállítása
        if 'database' in self.modules:
            self.modules['orchestrator'].set_database(self.modules['database'])
        
        # Router (kommunikáció)
        if self.config.get('modules', {}).get('router', {}).get('enabled', True):
            router = Router(self.modules['scratchpad'])
            router.zmq_enabled = self.config['modules']['router'].get('zmq_enabled', False)
            self.modules['router'] = router
        
        # Heartbeat (időérzék)
        if self.config.get('modules', {}).get('heartbeat', {}).get('enabled', True):
            hb_config = self.config['modules']['heartbeat']
            heartbeat = Heartbeat(
                self.modules['scratchpad'],
                orchestrator=self.modules['orchestrator']
            )
            heartbeat.interval = hb_config.get('interval', 1.0)
            self.modules['heartbeat'] = heartbeat

        # GATEWAY (külső kapcsolat)
        if self.config.get('modules', {}).get('gateway', {}).get('enabled', False):
            gateway_config = self.config['modules']['gateway']
            gateway = DiplomaticGateway(
                self.modules['scratchpad'],
                orchestrator=self.modules['orchestrator'],
                config=gateway_config
            )
            gateway.system_id = self.system_id
            self.modules['gateway'] = gateway
        
        # ==================== ÁGENSEK ====================
        # Scribe (írás)
        if self.config.get('agents', {}).get('scribe', {}).get('enabled', True):
            scribe = Scribe(self.modules['scratchpad'])
            scribe.translator = self.translator
            self.modules['scribe'] = scribe
        
        # Valet (memória) - a King ELŐTT kell lennie!
        if self.config.get('agents', {}).get('valet', {}).get('enabled', True):
            valet_config = self.config['agents']['valet']
            valet = Valet(self.modules['scratchpad'], config=valet_config)
            valet.translator = self.translator
            self.modules['valet'] = valet
        
        # Queen (logika) - a King ELŐTT kell lennie!
        if self.config.get('agents', {}).get('queen', {}).get('enabled', False):
            queen_config = self.config['agents']['queen']
            
            # Ha külön modell kell a Queennek
            queen_model_path = queen_config.get('model', 'none')
            queen_model = None
            
            if queen_model_path and queen_model_path != 'none' and queen_config.get('use_model', False):
                try:
                    from src.core.model_wrapper import ModelWrapper
                    queen_model = ModelWrapper(queen_model_path, {
                        'n_gpu_layers': queen_config.get('n_gpu_layers', -1),
                        'n_ctx': queen_config.get('n_ctx', 4096),
                        'main_gpu': 1  # Queen a második GPU-n
                    })
                except Exception as e:
                    print(f"⚠️ {self.translator.get('errors.model_load_error', error=e)}")
            
            queen = Queen(self.modules['scratchpad'], model_wrapper=queen_model, config=queen_config)
            queen.translator = self.translator
            self.modules['queen'] = queen
        
        # King (király) - ModelWrapper-rel
        if self.config.get('agents', {}).get('king', {}).get('enabled', True):
            king_config = self.config['agents']['king']
            model_path = king_config.get('model')
            
            # Először létrehozzuk a King-et
            if model_path and model_path.lower() != "none":
                # Van modell - létrehozzuk a ModelWrapper-t
                try:
                    from src.core.model_wrapper import ModelWrapper
                    
                    # Modell konfiguráció összeállítása
                    model_config = {
                        'n_gpu_layers': king_config.get('n_gpu_layers', -1),
                        'n_ctx': king_config.get('n_ctx', 4096),
                        'main_gpu': 0,  # King az első GPU-n
                        'verbose': self.config.get('system', {}).get('environment') == 'development'
                    }
                    
                    # Abszolút útvonal kezelés
                    if not os.path.isabs(model_path):
                        model_path = str(ROOT_DIR / model_path)
                    
                    print(f"📦 {self.translator.get('system.module_loaded', name='King modell')}")
                    model_wrapper = ModelWrapper(model_path, model_config)
                    king = King(self.modules['scratchpad'], model_wrapper=model_wrapper)
                    
                except Exception as e:
                    print(f"❌ {self.translator.get('errors.model_load_error', error=e)}")
                    print("   Dummy módban indul a King")
                    king = King(self.modules['scratchpad'])
            else:
                # Nincs modell, dummy mód
                print("👑 King: Modell nélkül (dummy mód)")
                king = King(self.modules['scratchpad'])
            
            # Átadjuk a fordítót
            king.translator = self.translator
            
            # Személyiség beállítása
            if self.active_personality:
                self.modules['scratchpad'].write_note('king', 'personality', self.active_personality)
            elif 'personality' in king_config:
                self.modules['scratchpad'].write_note('king', 'personality', king_config['personality'])
            
            self.modules['king'] = king
        
        # Jester (bohóc)
        if self.config.get('agents', {}).get('jester', {}).get('enabled', True):
            jester_config = self.config['agents']['jester']
            jester = Jester(self.modules['scratchpad'])
            # Konfig átadás
            if hasattr(jester, 'config'):
                jester.config.update({
                    'max_response_time': jester_config.get('max_response_time', 10.0),
                    'max_error_rate': jester_config.get('max_error_rate', 0.3),
                    'max_consecutive_errors': jester_config.get('max_consecutive_errors', 3)
                })
            # Átadjuk a fordítót
            jester.translator = self.translator
            self.modules['jester'] = jester

        # ==================== WEB ====================
        # WEB - modulok átadása
        if self.config.get('modules', {}).get('web', {}).get('enabled', True):
            web_config = self.config['modules']['web']
            web = WebApp(self.modules)  # <-- Itt átadjuk az összes modult
            web.host = web_config.get('host', '0.0.0.0')
            web.port = web_config.get('port', 5000)
            web.translator = self.translator
            web.system_id = self.system_id
            self.modules['web'] = web
        
        print(f"✅ {len(self.modules)} modul betöltve")
    
    def _init_database_tables(self):
        """Adatbázis táblák létrehozása (kiegészítve a szükséges táblákkal)"""
        db = self.modules['database']
        
        with db.lock:
            conn = db._get_connection()
            
            # Személyiségek tábla
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
            
            # Rendszerbeállítások tábla
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
            
            # Felhasználók tábla
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
            
            # Sessionök tábla
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
            
            # Beszélgetések tábla
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
            
            # Üzenetek tábla
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
            
            # Emlékek tábla (Vault)
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
            
            # Kapcsolatok tábla (gráf)
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
            
            # Audit log tábla (biztonsági napló)
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
            
            # Teljesítmény metrikák tábla
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
        """Alapértelmezett felhasználó létrehozása, ha még nincs"""
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
                
                # Session token létrehozása
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
                
                print(f"👤 Alapértelmezett felhasználó létrehozva: {default_name} ({default_language})")
                
                # Alapértelmezett beszélgetés létrehozása
                conn.execute("""
                    INSERT INTO conversations (user_id, title)
                    VALUES (?, ?)
                """, (user_id, self.translator.get('conversation.default_title', 'New Conversation')))
                
                # Audit log
                conn.execute("""
                    INSERT INTO audit_log (user_id, action, resource, details)
                    VALUES (?, ?, ?, ?)
                """, (user_id, 'create', 'user', 'Default user created'))
            
            conn.commit()
            conn.close()
    
    def _load_active_personality(self):
        """Aktív személyiség betöltése az adatbázisból"""
        db = self.modules['database']
        
        with db.lock:
            conn = db._get_connection()
            
            cursor = conn.execute("SELECT content FROM personalities WHERE is_active = 1")
            row = cursor.fetchone()
            
            if row:
                self.active_personality = row[0]
                print(f"👑 Aktív személyiség betöltve az adatbázisból")
            else:
                # Alapértelmezett személyiség (hardkódolás nélkül, általános)
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
        """Szép leállítás signal esetén (Ctrl+C)"""
        print(f"\n⚠️ {self.translator.get('system.stopping')}")
        self.shutdown()
    
    def start(self):
        """Minden modul indítása a megfelelő sorrendben"""
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
        
        if self.current_user:
            self.modules['scratchpad'].set_state('user_name', self.current_user['display_name'], 'system')
            self.modules['scratchpad'].set_state('user_language', self.current_user['language'], 'system')
            self.modules['scratchpad'].set_state('user_role', self.current_user['role'], 'system')
        
        print(f"\n✅ {self.translator.get('system.started')}")
        print(f"   System ID: {self.system_id[:8]}...")
        
        if 'web' in self.modules:
            web_config = self.config.get('modules', {}).get('web', {})
            host = web_config.get('host', '0.0.0.0')
            port = web_config.get('port', 5000)
            print(f"🌐 Web UI: http://{host if host != '0.0.0.0' else 'localhost'}:{port}")
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.shutdown()
    
    def shutdown(self):
        """Minden modul szép leállítása (fordított sorrendben)"""
        print(f"\n📴 {self.translator.get('system.stopping')}")
        self.running = False
        
        # Rendszerleállás naplózása
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