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
        
        # Modulok inicializálása
        self._init_modules()
        
        # Signal kezelés a szép leálláshoz
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        print(self.translator.get('system.started'))
    
    def _load_config(self, config_path):
        """Konfiguráció betöltése YAML-ből (átmeneti megoldás, később csak adatbázis)"""
        if not config_path:
            config_path = ROOT_DIR / 'config' / 'config.yaml'
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            print(f"📋 {self.translator.get('system.config_loaded', path=config_path)}")
            return config
        except Exception as e:
            print(f"⚠️ {self.translator.get('system.config_error', error=e)}")
            # Alapértelmezett konfig
            return {
                'system': {'name': 'SoulCore', 'version': '3.0'},
                'modules': {
                    'heartbeat': {'enabled': True}, 
                    'router': {'enabled': True}, 
                    'web': {'enabled': True}
                },
                'agents': {
                    'king': {'enabled': True, 'model': 'none'},
                    'jester': {'enabled': True},
                    'scribe': {'enabled': True}
                },
                'user': {'name': 'User', 'language': 'en'}
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
        
        # IDENTITY (lélek - a régi identity.inf még használható, de kivezetjük)
        identity_file = self.config.get('system', {}).get('identity_file', 'config/identity.inf')
        self.modules['identity'] = SoulIdentity(self.modules['scratchpad'], config_path=ROOT_DIR / identity_file)

        # EYE-CORE (vizuális)
        if self.config.get('modules', {}).get('eyecore', {}).get('enabled', True):
            eyecore_config = self.config['modules']['eyecore']
            eyecore = EyeCore(self.modules['scratchpad'], config=eyecore_config)
            self.modules['eyecore'] = eyecore

        # SENTINEL (hardver)
        if self.config.get('modules', {}).get('sentinel', {}).get('enabled', True):
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
        self.modules['orchestrator'] = Orchestrator(self.modules['scratchpad'])
        
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

        # GATEWAY (külső kapcsolat) - univerzális változat
        if self.config.get('modules', {}).get('gateway', {}).get('enabled', True):
            gateway_config = self.config['modules']['gateway']
            gateway = DiplomaticGateway(
                self.modules['scratchpad'],
                orchestrator=self.modules['orchestrator'],
                config=gateway_config
            )
            self.modules['gateway'] = gateway
        
        # ==================== ÁGENSEK ====================
        # Scribe (írás)
        if self.config.get('agents', {}).get('scribe', {}).get('enabled', True):
            scribe = Scribe(self.modules['scratchpad'])
            scribe.translator = self.translator
            self.modules['scribe'] = scribe
        
        # Valet (memória)
        if self.config.get('agents', {}).get('valet', {}).get('enabled', True):
            valet_config = self.config['agents']['valet']
            valet = Valet(self.modules['scratchpad'], config=valet_config)
            self.modules['valet'] = valet
        
        # Queen (logika) - a King ELŐTT kell lennie!
        if self.config.get('agents', {}).get('queen', {}).get('enabled', True):
            queen_config = self.config['agents']['queen']
            
            # Ha külön modell kell a Queennek
            queen_model_path = queen_config.get('model', 'none')
            queen_model = None
            
            if queen_model_path and queen_model_path != 'none' and queen_config.get('use_model', False):
                try:
                    from src.core.model_wrapper import ModelWrapper
                    queen_model = ModelWrapper(queen_model_path, {
                        'n_gpu_layers': queen_config.get('n_gpu_layers', -1),
                        'n_ctx': queen_config.get('n_ctx', 4096)
                    })
                except Exception as e:
                    print(f"⚠️ {self.translator.get('errors.model_load_error', error=e)}")
            
            queen = Queen(self.modules['scratchpad'], model_wrapper=queen_model, config=queen_config)
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
                        'n_ctx': king_config.get('n_ctx', 4096)
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
            
            # Valet hozzáadása, ha létezik
            if 'valet' in self.modules and self.modules['valet'] is not None:
                king.valet = self.modules['valet']
                print("👑 King: Valet kapcsolódva")

            # Queen hozzáadása, ha létezik
            if 'queen' in self.modules and self.modules['queen'] is not None:
                king.queen = self.modules['queen']
                print("👑 King: Queen kapcsolódva")
            
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
        # WEB
        if self.config.get('modules', {}).get('web', {}).get('enabled', True):
            web_config = self.config['modules']['web']
            web = WebApp(self.modules)
            web.host = web_config.get('host', '0.0.0.0')
            web.port = web_config.get('port', 5000)
            web.translator = self.translator
            self.modules['web'] = web
        
        print(f"✅ {len(self.modules)} modul betöltve")
    
    def _init_database_tables(self):
        """Adatbázis táblák létrehozása"""
        db = self.modules['database']
        
        # Kapcsolat létrehozása
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
            
            conn.commit()
            conn.close()
    
    def _init_default_user(self):
        """Alapértelmezett felhasználó létrehozása, ha még nincs"""
        db = self.modules['database']
        
        # Kapcsolat létrehozása
        with db.lock:
            conn = db._get_connection()
            
            # Ellenőrizzük, van-e már felhasználó
            cursor = conn.execute("SELECT COUNT(*) FROM users")
            count = cursor.fetchone()[0]
            
            if count == 0:
                # Alapértelmezett felhasználó létrehozása
                default_language = self.config.get('user', {}).get('language', 'en')
                default_name = self.config.get('user', {}).get('name', 'User')
                
                cursor = conn.execute("""
                    INSERT INTO users (username, display_name, role, language, preferences)
                    VALUES (?, ?, ?, ?, ?)
                """, ('default', default_name, 'admin', default_language, '{}'))
                
                user_id = cursor.lastrowid
                
                # Session token létrehozása
                token = str(uuid.uuid4())
                expires_at = time.time() + 30 * 86400  # 30 nap
                
                conn.execute("""
                    INSERT INTO sessions (user_id, token, expires_at)
                    VALUES (?, ?, ?)
                """, (user_id, token, expires_at))
                
                self.current_user = {
                    'id': user_id,
                    'username': 'default',
                    'display_name': default_name,
                    'role': 'admin',
                    'language': default_language
                }
                
                # Fordító átállítása
                self.translator.set_language(default_language)
                
                print(f"👤 Alapértelmezett felhasználó létrehozva: {default_name} ({default_language})")
            
            conn.commit()
            conn.close()
    
    def _load_active_personality(self):
        """Aktív személyiség betöltése az adatbázisból"""
        db = self.modules['database']
        
        # Kapcsolat létrehozása
        with db.lock:
            conn = db._get_connection()
            
            cursor = conn.execute("SELECT content FROM personalities WHERE is_active = 1")
            row = cursor.fetchone()
            
            if row:
                self.active_personality = row[0]
                print(f"👑 Aktív személyiség betöltve az adatbázisból")
            else:
                # Ha nincs aktív személyiség, létrehozunk egy alapértelmezettet
                default_personality = '''GENERAL:
name: King
title: The Sovereign
motto: I think, therefore I am.

PERSONALITY:
traits: curious, loyal, sovereign, witty, humorous

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
                """, ("Default King", default_personality, 'en'))
                
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
        
        # Indítási sorrend (függőségek miatt)
        start_order = [
            'scratchpad',     # 1. memória
            'router',         # 2. kommunikáció
            'orchestrator',   # 3. KVK feldolgozó
            'scribe',         # 4. értelmező
            'valet',          # 5. memória (kell a Kingnek)
            'queen',          # 6. logika (kell a Kingnek)
            'king',           # 7. király
            'jester',         # 8. bohóc (figyeli a királyt)
            'heartbeat',      # 9. időérzék (utána, mert orchestrator kell neki)
            'gateway',        # 10. külső kapcsolat
            'eyecore',        # 11. vizuális
            'sentinel',       # 12. hardver
            'blackbox',       # 13. naplózás
            'sandbox',        # 14. kód futtatás
            'web'             # 15. web (utolsó)
        ]
        
        for name in start_order:
            if name in self.modules:
                module = self.modules[name]
                if hasattr(module, 'start'):
                    print(f"  └─ {name} indul...")
                    try:
                        # Ha van benne start metódus, és nem thread, akkor itt indítjuk
                        if name == 'web' or name == 'heartbeat':
                            # Ezek thread-ben futnak
                            threading.Thread(target=module.start, daemon=True).start()
                        else:
                            # Ezek szinkron indulnak
                            module.start()
                    except Exception as e:
                        print(f"  ❌ {name} hiba: {e}")
        
        # User név beállítása a scratchpadbe
        if self.current_user:
            self.modules['scratchpad'].set_state('user_name', self.current_user['display_name'], 'system')
            self.modules['scratchpad'].set_state('user_language', self.current_user['language'], 'system')
            self.modules['scratchpad'].set_state('user_role', self.current_user['role'], 'system')
        
        print(f"\n✅ {self.translator.get('system.started')}")
        if 'web' in self.modules:
            web_config = self.config.get('modules', {}).get('web', {})
            host = web_config.get('host', '0.0.0.0')
            port = web_config.get('port', 5000)
            print(f"🌐 Web UI: http://{host if host != '0.0.0.0' else 'localhost'}:{port}")
        
        # Főszál élve tartása
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.shutdown()
    
    def shutdown(self):
        """Minden modul szép leállítása (fordított sorrendben)"""
        print(f"\n📴 {self.translator.get('system.stopping')}")
        self.running = False
        
        # Leállítási sorrend (fordított)
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
    # Konfiguráció útvonal argumentumból
    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    app = SoulCore(config_path)
    app.start()