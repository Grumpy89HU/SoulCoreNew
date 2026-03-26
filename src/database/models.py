"""
Adatbázis modellek a SoulCore számára.
Támogatja a beszélgetések, promptok, beállítások, személyiségek és felhasználók tárolását.
"""

import json
import time
import sqlite3
import threading
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class Database:
    """
    Adatbázis kezelő SQLite-alapokon - THREAD-SAFE verzió.
    
    Táblák:
    - conversations: beszélgetések
    - messages: üzenetek
    - prompts: prompt sablonok
    - settings: beállítások (régi, átmeneti)
    - models: elérhető modellek
    - personalities: személyiségek (King identitások)
    - system_settings: rendszerbeállítások (config.yaml helyett)
    - users: felhasználók
    - sessions: aktív sessionök
    """
    
    # Séma verzió
    SCHEMA_VERSION = 3
    
    def __init__(self, db_path: str = "data/soulcore.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Lock a thread safety-hez
        self.lock = threading.RLock()
        
        # Inicializálás
        self._init_db()
        self._migrate_if_needed()
    
    def _get_connection(self):
        """Új SQLite kapcsolat létrehozása (thread-safe)"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self):
        """Adatbázis inicializálása (táblák létrehozása)"""
        with self.lock:
            conn = self._get_connection()
            
            # Séma verzió tábla
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # ========== MEGLÉVŐ TÁBLÁK ==========
            # Beszélgetések
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    model TEXT,
                    system_prompt TEXT,
                    metadata TEXT,
                    user_id INTEGER,
                    is_archived BOOLEAN DEFAULT 0
                )
            """)
            
            # Üzenetek
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER,
                    user_id INTEGER,
                    role TEXT CHECK(role IN ('user', 'assistant', 'system', 'jester')),
                    content TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    tokens INTEGER DEFAULT 0,
                    metadata TEXT,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            
            # Prompt sablonok
            conn.execute("""
                CREATE TABLE IF NOT EXISTS prompts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    content TEXT,
                    description TEXT,
                    category TEXT DEFAULT 'general',
                    is_default BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Beállítások (régi, átmeneti)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    type TEXT DEFAULT 'string',
                    category TEXT DEFAULT 'general',
                    description TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Modellek
            conn.execute("""
                CREATE TABLE IF NOT EXISTS models (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    path TEXT UNIQUE,
                    size TEXT,
                    quantization TEXT,
                    n_ctx INTEGER DEFAULT 4096,
                    n_gpu_layers INTEGER DEFAULT -1,
                    description TEXT,
                    is_active BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_used TIMESTAMP
                )
            """)
            
            # ========== ÚJ TÁBLÁK ==========
            # Személyiségek (King identitások)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS personalities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    content TEXT,
                    is_active BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Rendszerbeállítások
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
            
            # Felhasználók
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
            
            # Aktuális sessionök
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
            
            # Teljesítmény metrikák
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
            
            # Alapértelmezett adatok beszúrása
            self._init_default_prompts()
            self._init_default_personality()
            self._init_default_models()
    
    def _migrate_if_needed(self):
        """Séma migráció ellenőrzése és végrehajtása"""
        with self.lock:
            conn = self._get_connection()
            
            # Jelenlegi verzió lekérése
            cursor = conn.execute("SELECT version FROM schema_version ORDER BY updated_at DESC LIMIT 1")
            row = cursor.fetchone()
            current_version = row['version'] if row else 0
            
            if current_version < self.SCHEMA_VERSION:
                logger.info(f"Migrating database from version {current_version} to {self.SCHEMA_VERSION}")
                
                # Migrációk
                if current_version < 1:
                    self._migrate_to_v1(conn)
                if current_version < 2:
                    self._migrate_to_v2(conn)
                if current_version < 3:
                    self._migrate_to_v3(conn)
                
                # Verzió frissítése
                conn.execute("""
                    INSERT OR REPLACE INTO schema_version (version, updated_at)
                    VALUES (?, CURRENT_TIMESTAMP)
                """, (self.SCHEMA_VERSION,))
                conn.commit()
            
            conn.close()
    
    def _migrate_to_v1(self, conn):
        """Migráció az 1-es verzióra"""
        # is_archived oszlop hozzáadása a conversations táblához
        try:
            conn.execute("ALTER TABLE conversations ADD COLUMN is_archived BOOLEAN DEFAULT 0")
        except sqlite3.OperationalError:
            pass
    
    def _migrate_to_v2(self, conn):
        """Migráció a 2-es verzióra"""
        # last_used oszlop hozzáadása a models táblához
        try:
            conn.execute("ALTER TABLE models ADD COLUMN last_used TIMESTAMP")
        except sqlite3.OperationalError:
            pass
        
        # audit_log tábla
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
    
    def _migrate_to_v3(self, conn):
        """Migráció a 3-as verzióra"""
        # performance_metrics tábla
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
    
    def _init_default_prompts(self):
        """Alapértelmezett prompt sablonok létrehozása"""
        default_prompts = [
            {
                'name': 'King (alap)',
                'content': '''VISELKEDÉS:
Te egy szuverén entitás vagy. A humor és a ravaszság a fegyvereid.

SZEMÉLYISÉG:
{personality}

Felhasználó üzenete: {text}

Válaszod:''',
                'description': 'Alapértelmezett King prompt',
                'category': 'king',
                'is_default': 1
            },
            {
                'name': 'Segítőkész',
                'content': '''Segítőkész asszisztens vagy, aki pontos és hasznos válaszokat ad.

Felhasználó: {text}

Válasz:''',
                'description': 'Segítőkész, semleges stílus',
                'category': 'general',
                'is_default': 0
            },
            {
                'name': 'Szakértő',
                'content': '''Szakértő vagy a témában. Adj részletes, technikailag pontos választ.

Kérdés: {text}

Válasz:''',
                'description': 'Technikai szakértő mód',
                'category': 'expert',
                'is_default': 0
            }
        ]
        
        with self.lock:
            conn = self._get_connection()
            for prompt in default_prompts:
                try:
                    conn.execute("""
                        INSERT OR IGNORE INTO prompts (name, content, description, category, is_default)
                        VALUES (?, ?, ?, ?, ?)
                    """, (prompt['name'], prompt['content'], prompt['description'], 
                          prompt['category'], prompt['is_default']))
                except Exception as e:
                    logger.warning(f"Failed to insert default prompt {prompt['name']}: {e}")
            conn.commit()
            conn.close()
    
    def _init_default_personality(self):
        """Alapértelmezett személyiség létrehozása"""
        with self.lock:
            conn = self._get_connection()
            
            cursor = conn.execute("SELECT COUNT(*) FROM personalities")
            count = cursor.fetchone()[0]
            
            if count == 0:
                default_personality = '''GENERAL:
name: Sovereign
title: The First
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
                    INSERT INTO personalities (name, content, is_active)
                    VALUES (?, ?, 1)
                """, ("Default Sovereign", default_personality))
                logger.info("Default personality created")
            
            conn.commit()
            conn.close()
    
    def _init_default_models(self):
        """Alapértelmezett modell beállítások"""
        with self.lock:
            conn = self._get_connection()
            
            cursor = conn.execute("SELECT COUNT(*) FROM models WHERE is_active = 1")
            count = cursor.fetchone()[0]
            
            if count == 0:
                # Aktív modell beállítása a fájlok alapján
                from pathlib import Path
                models_dir = Path(__file__).parent.parent.parent / 'models'
                if models_dir.exists():
                    for model_file in models_dir.glob('*.gguf'):
                        # Alapértelmezett modell beállítása
                        conn.execute("""
                            INSERT OR IGNORE INTO models (name, path, is_active)
                            VALUES (?, ?, 1)
                        """, (model_file.stem, str(model_file)))
                        logger.info(f"Default model added: {model_file.stem}")
                        break
            
            conn.commit()
            conn.close()
    
    # ========== BESZÉLGETÉSEK ==========
    
    def create_conversation(self, title: str = None, model: str = None, 
                           system_prompt: str = None, metadata: Dict = None,
                           user_id: int = None) -> int:
        """Új beszélgetés létrehozása"""
        if not title:
            title = f"Conversation {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute("""
                INSERT INTO conversations (title, model, system_prompt, metadata, user_id)
                VALUES (?, ?, ?, ?, ?)
            """, (title, model, system_prompt, json.dumps(metadata) if metadata else None, user_id))
            
            conn.commit()
            last_id = cursor.lastrowid
            conn.close()
            return last_id
    
    def get_conversations(self, limit: int = 50, offset: int = 0, user_id: int = None,
                          include_archived: bool = False) -> List[Dict]:
        """Beszélgetések listázása"""
        with self.lock:
            conn = self._get_connection()
            
            if user_id:
                if include_archived:
                    cursor = conn.execute("""
                        SELECT * FROM conversations 
                        WHERE user_id = ? 
                        ORDER BY updated_at DESC 
                        LIMIT ? OFFSET ?
                    """, (user_id, limit, offset))
                else:
                    cursor = conn.execute("""
                        SELECT * FROM conversations 
                        WHERE user_id = ? AND is_archived = 0
                        ORDER BY updated_at DESC 
                        LIMIT ? OFFSET ?
                    """, (user_id, limit, offset))
            else:
                if include_archived:
                    cursor = conn.execute("""
                        SELECT * FROM conversations 
                        ORDER BY updated_at DESC 
                        LIMIT ? OFFSET ?
                    """, (limit, offset))
                else:
                    cursor = conn.execute("""
                        SELECT * FROM conversations 
                        WHERE is_archived = 0
                        ORDER BY updated_at DESC 
                        LIMIT ? OFFSET ?
                    """, (limit, offset))
            
            result = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return result
    
    def get_recent_conversations(self, user_id: int = None, days: int = 7) -> List[Dict]:
        """Legutóbbi beszélgetések lekérése"""
        cutoff = datetime.now() - timedelta(days=days)
        
        with self.lock:
            conn = self._get_connection()
            
            if user_id:
                cursor = conn.execute("""
                    SELECT * FROM conversations 
                    WHERE user_id = ? AND updated_at > ? AND is_archived = 0
                    ORDER BY updated_at DESC
                """, (user_id, cutoff.isoformat()))
            else:
                cursor = conn.execute("""
                    SELECT * FROM conversations 
                    WHERE updated_at > ? AND is_archived = 0
                    ORDER BY updated_at DESC
                """, (cutoff.isoformat(),))
            
            result = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return result
    
    def get_conversation(self, conv_id: int) -> Optional[Dict]:
        """Egy beszélgetés adatainak lekérése"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute("""
                SELECT * FROM conversations WHERE id = ?
            """, (conv_id,))
            
            row = cursor.fetchone()
            conn.close()
            return dict(row) if row else None
    
    def get_conversation_messages_count(self, conv_id: int) -> int:
        """Beszélgetés üzeneteinek száma"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute("""
                SELECT COUNT(*) as count FROM messages WHERE conversation_id = ?
            """, (conv_id,))
            
            row = cursor.fetchone()
            conn.close()
            return row['count'] if row else 0
    
    def update_conversation(self, conv_id: int, **kwargs):
        """Beszélgetés frissítése"""
        fields = []
        values = []
        
        for key, value in kwargs.items():
            if key in ['title', 'model', 'system_prompt', 'metadata', 'user_id', 'is_archived']:
                fields.append(f"{key} = ?")
                if key == 'metadata' and value:
                    values.append(json.dumps(value))
                else:
                    values.append(value)
        
        if fields:
            values.append(conv_id)
            with self.lock:
                conn = self._get_connection()
                conn.execute(f"""
                    UPDATE conversations 
                    SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, values)
                conn.commit()
                conn.close()
    
    def delete_conversation(self, conv_id: int, soft: bool = True):
        """Beszélgetés törlése (soft delete vagy végleges)"""
        if soft:
            self.update_conversation(conv_id, is_archived=True)
        else:
            with self.lock:
                conn = self._get_connection()
                conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
                conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
                conn.commit()
                conn.close()
    
    # ========== ÜZENETEK ==========
    
    def add_message(self, conversation_id: int, role: str, content: str, 
                   tokens: int = 0, metadata: Dict = None, user_id: int = None) -> int:
        """Üzenet hozzáadása"""
        with self.lock:
            conn = self._get_connection()
            
            if user_id is None:
                cursor = conn.execute("SELECT user_id FROM conversations WHERE id = ?", (conversation_id,))
                row = cursor.fetchone()
                if row:
                    user_id = row[0]
            
            cursor = conn.execute("""
                INSERT INTO messages (conversation_id, user_id, role, content, tokens, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (conversation_id, user_id, role, content, tokens, 
                  json.dumps(metadata) if metadata else None))
            
            conn.execute("""
                UPDATE conversations SET updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (conversation_id,))
            
            conn.commit()
            last_id = cursor.lastrowid
            conn.close()
            return last_id
    
    def get_messages(self, conversation_id: int, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Üzenetek lekérése beszélgetésből"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute("""
                SELECT m.*, u.display_name as user_name
                FROM messages m
                LEFT JOIN users u ON m.user_id = u.id
                WHERE m.conversation_id = ? 
                ORDER BY m.timestamp ASC
                LIMIT ? OFFSET ?
            """, (conversation_id, limit, offset))
            
            messages = []
            for row in cursor.fetchall():
                msg = dict(row)
                if msg['metadata']:
                    try:
                        msg['metadata'] = json.loads(msg['metadata'])
                    except:
                        msg['metadata'] = None
                messages.append(msg)
            
            conn.close()
            return messages
    
    def search_messages(self, query: str, user_id: int = None, limit: int = 50) -> List[Dict]:
        """Üzenetek keresése"""
        with self.lock:
            conn = self._get_connection()
            
            if user_id:
                cursor = conn.execute("""
                    SELECT m.*, c.title as conversation_title
                    FROM messages m
                    JOIN conversations c ON m.conversation_id = c.id
                    WHERE m.content LIKE ? AND (m.user_id = ? OR ? IS NULL)
                    ORDER BY m.timestamp DESC
                    LIMIT ?
                """, (f'%{query}%', user_id, user_id, limit))
            else:
                cursor = conn.execute("""
                    SELECT m.*, c.title as conversation_title
                    FROM messages m
                    JOIN conversations c ON m.conversation_id = c.id
                    WHERE m.content LIKE ?
                    ORDER BY m.timestamp DESC
                    LIMIT ?
                """, (f'%{query}%', limit))
            
            results = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return results
    
    # ========== PROMPT SABLONOK ==========
    
    def get_prompts(self, category: str = None) -> List[Dict]:
        """Prompt sablonok listázása"""
        with self.lock:
            conn = self._get_connection()
            if category:
                cursor = conn.execute("""
                    SELECT * FROM prompts WHERE category = ? ORDER BY name
                """, (category,))
            else:
                cursor = conn.execute("SELECT * FROM prompts ORDER BY category, name")
            
            result = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return result
    
    def get_prompt_by_category(self, category: str, limit: int = 10) -> List[Dict]:
        """Kategória szerinti promptok lekérése"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute("""
                SELECT * FROM prompts WHERE category = ? ORDER BY is_default DESC, name
                LIMIT ?
            """, (category, limit))
            
            result = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return result
    
    def get_prompt(self, prompt_id: int = None, name: str = None) -> Optional[Dict]:
        """Egy prompt lekérése"""
        with self.lock:
            conn = self._get_connection()
            if prompt_id:
                cursor = conn.execute("SELECT * FROM prompts WHERE id = ?", (prompt_id,))
            elif name:
                cursor = conn.execute("SELECT * FROM prompts WHERE name = ?", (name,))
            else:
                conn.close()
                return None
            
            row = cursor.fetchone()
            conn.close()
            return dict(row) if row else None
    
    def save_prompt(self, name: str, content: str, description: str = "", 
                   category: str = "general", is_default: bool = False) -> int:
        """Prompt mentése"""
        existing = self.get_prompt(name=name)
        
        with self.lock:
            conn = self._get_connection()
            if existing:
                conn.execute("""
                    UPDATE prompts 
                    SET content = ?, description = ?, category = ?, is_default = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE name = ?
                """, (content, description, category, is_default, name))
                result = existing['id']
            else:
                cursor = conn.execute("""
                    INSERT INTO prompts (name, content, description, category, is_default)
                    VALUES (?, ?, ?, ?, ?)
                """, (name, content, description, category, is_default))
                result = cursor.lastrowid
            
            conn.commit()
            conn.close()
            return result
    
    def delete_prompt(self, prompt_id: int):
        """Prompt törlése"""
        prompt = self.get_prompt(prompt_id)
        if prompt and prompt['is_default']:
            raise ValueError("Default prompt cannot be deleted")
        
        with self.lock:
            conn = self._get_connection()
            conn.execute("DELETE FROM prompts WHERE id = ?", (prompt_id,))
            conn.commit()
            conn.close()
    
    # ========== SZEMÉLYISÉGEK ==========
    
    def get_personalities(self) -> List[Dict]:
        """Összes személyiség listázása"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute("SELECT * FROM personalities ORDER BY name")
            result = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return result
    
    def get_personality(self, personality_id: int = None, name: str = None) -> Optional[Dict]:
        """Egy személyiség lekérése"""
        with self.lock:
            conn = self._get_connection()
            if personality_id:
                cursor = conn.execute("SELECT * FROM personalities WHERE id = ?", (personality_id,))
            elif name:
                cursor = conn.execute("SELECT * FROM personalities WHERE name = ?", (name,))
            else:
                conn.close()
                return None
            
            row = cursor.fetchone()
            conn.close()
            return dict(row) if row else None
    
    def get_active_personality(self) -> Optional[Dict]:
        """Aktív személyiség lekérése"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute("SELECT * FROM personalities WHERE is_active = 1")
            row = cursor.fetchone()
            conn.close()
            return dict(row) if row else None
    
    def save_personality(self, name: str, content: str, activate: bool = False) -> int:
        """Személyiség mentése"""
        existing = self.get_personality(name=name)
        
        with self.lock:
            conn = self._get_connection()
            if existing:
                conn.execute("""
                    UPDATE personalities 
                    SET content = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE name = ?
                """, (content, name))
                result = existing['id']
            else:
                cursor = conn.execute("""
                    INSERT INTO personalities (name, content)
                    VALUES (?, ?)
                """, (name, content))
                result = cursor.lastrowid
            
            if activate:
                conn.execute("UPDATE personalities SET is_active = 0")
                conn.execute("UPDATE personalities SET is_active = 1 WHERE id = ?", (result,))
            
            conn.commit()
            conn.close()
            return result
    
    def activate_personality(self, personality_id: int):
        """Személyiség aktiválása"""
        with self.lock:
            conn = self._get_connection()
            conn.execute("UPDATE personalities SET is_active = 0")
            conn.execute("UPDATE personalities SET is_active = 1 WHERE id = ?", (personality_id,))
            conn.commit()
            conn.close()
    
    def delete_personality(self, personality_id: int):
        """Személyiség törlése"""
        personality = self.get_personality(personality_id)
        if personality and personality['is_active']:
            raise ValueError("Active personality cannot be deleted")
        
        with self.lock:
            conn = self._get_connection()
            conn.execute("DELETE FROM personalities WHERE id = ?", (personality_id,))
            conn.commit()
            conn.close()
    
    # ========== FELHASZNÁLÓK ==========
    
    def create_user(self, username: str, display_name: str = None, 
                   role: str = 'user', language: str = 'en',
                   preferences: Dict = None) -> int:
        """Új felhasználó létrehozása"""
        if not display_name:
            display_name = username
        
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute("""
                INSERT INTO users (username, display_name, role, language, preferences, last_active)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (username, display_name, role, language, 
                  json.dumps(preferences) if preferences else None,
                  datetime.now().isoformat()))
            
            conn.commit()
            last_id = cursor.lastrowid
            conn.close()
            return last_id
    
    def get_user(self, user_id: int = None, username: str = None) -> Optional[Dict]:
        """Felhasználó lekérése"""
        with self.lock:
            conn = self._get_connection()
            if user_id:
                cursor = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            elif username:
                cursor = conn.execute("SELECT * FROM users WHERE username = ?", (username,))
            else:
                conn.close()
                return None
            
            row = cursor.fetchone()
            conn.close()
            return dict(row) if row else None
    
    def get_user_by_token(self, token: str) -> Optional[Dict]:
        """Token alapján felhasználó lekérése"""
        session = self.get_session(token)
        if session:
            return self.get_user(session['user_id'])
        return None
    
    def get_users(self) -> List[Dict]:
        """Összes felhasználó listázása"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute("SELECT * FROM users ORDER BY username")
            result = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return result
    
    def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Felhasználói statisztikák"""
        with self.lock:
            conn = self._get_connection()
            
            # Beszélgetések száma
            cursor = conn.execute("""
                SELECT COUNT(*) as conversations FROM conversations WHERE user_id = ? AND is_archived = 0
            """, (user_id,))
            conversations = cursor.fetchone()['conversations']
            
            # Üzenetek száma
            cursor = conn.execute("""
                SELECT COUNT(*) as messages, SUM(tokens) as total_tokens
                FROM messages WHERE user_id = ?
            """, (user_id,))
            row = cursor.fetchone()
            messages = row['messages'] if row else 0
            total_tokens = row['total_tokens'] if row else 0
            
            # Utolsó aktivitás
            user = self.get_user(user_id)
            last_active = user.get('last_active') if user else None
            
            conn.close()
            
            return {
                'conversations': conversations,
                'messages': messages,
                'total_tokens': total_tokens,
                'last_active': last_active
            }
    
    def update_user(self, user_id: int, **kwargs):
        """Felhasználó frissítése"""
        fields = []
        values = []
        
        for key, value in kwargs.items():
            if key in ['display_name', 'role', 'language', 'preferences']:
                fields.append(f"{key} = ?")
                if key == 'preferences' and value:
                    values.append(json.dumps(value))
                else:
                    values.append(value)
        
        if fields:
            values.append(user_id)
            with self.lock:
                conn = self._get_connection()
                conn.execute(f"""
                    UPDATE users 
                    SET {', '.join(fields)}
                    WHERE id = ?
                """, values)
                conn.commit()
                conn.close()
    
    def update_last_active(self, user_id: int):
        """Utolsó aktivitás frissítése"""
        with self.lock:
            conn = self._get_connection()
            conn.execute("""
                UPDATE users SET last_active = ?
                WHERE id = ?
            """, (datetime.now().isoformat(), user_id))
            conn.commit()
            conn.close()
    
    def delete_user(self, user_id: int):
        """Felhasználó törlése"""
        with self.lock:
            conn = self._get_connection()
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            conn.close()
    
    # ========== SESSIONÖK ==========
    
    def create_session(self, user_id: int, token: str, expires_at: float) -> int:
        """Új session létrehozása"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute("""
                INSERT INTO sessions (user_id, token, expires_at)
                VALUES (?, ?, ?)
            """, (user_id, token, expires_at))
            
            conn.commit()
            last_id = cursor.lastrowid
            conn.close()
            return last_id
    
    def get_session(self, token: str) -> Optional[Dict]:
        """Session lekérése token alapján"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute("""
                SELECT s.*, u.username, u.display_name, u.role, u.language
                FROM sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.token = ? AND s.expires_at > ?
            """, (token, time.time()))
            
            row = cursor.fetchone()
            conn.close()
            return dict(row) if row else None
    
    def delete_session(self, token: str):
        """Session törlése"""
        with self.lock:
            conn = self._get_connection()
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
            conn.commit()
            conn.close()
    
    def cleanup_sessions(self):
        """Lejárt sessionök törlése"""
        with self.lock:
            conn = self._get_connection()
            conn.execute("DELETE FROM sessions WHERE expires_at < ?", (time.time(),))
            conn.commit()
            conn.close()
    
    # ========== MODELLEK ==========
    
    def add_model(self, name: str, path: str, size: str = None, 
                 quantization: str = None, n_ctx: int = 4096, 
                 n_gpu_layers: int = -1, description: str = "") -> int:
        """Modell hozzáadása"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute("""
                INSERT OR IGNORE INTO models (name, path, size, quantization, n_ctx, n_gpu_layers, description)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (name, path, size, quantization, n_ctx, n_gpu_layers, description))
            
            conn.commit()
            last_id = cursor.lastrowid
            conn.close()
            return last_id
    
    def get_models(self, active_only: bool = True) -> List[Dict]:
        """Modellek listázása"""
        with self.lock:
            conn = self._get_connection()
            if active_only:
                cursor = conn.execute("SELECT * FROM models WHERE is_active = 1 ORDER BY name")
            else:
                cursor = conn.execute("SELECT * FROM models ORDER BY name")
            
            result = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return result
    
    def get_model(self, model_id: int = None, name: str = None, path: str = None) -> Optional[Dict]:
        """Egy modell lekérése"""
        with self.lock:
            conn = self._get_connection()
            if model_id:
                cursor = conn.execute("SELECT * FROM models WHERE id = ?", (model_id,))
            elif name:
                cursor = conn.execute("SELECT * FROM models WHERE name = ?", (name,))
            elif path:
                cursor = conn.execute("SELECT * FROM models WHERE path = ?", (path,))
            else:
                conn.close()
                return None
            
            row = cursor.fetchone()
            conn.close()
            return dict(row) if row else None
    
    def get_model_by_path(self, path: str) -> Optional[Dict]:
        """Elérési út alapján modell keresés"""
        return self.get_model(path=path)
    
    def set_active_model(self, model_id: int):
        """Aktív modell beállítása"""
        with self.lock:
            conn = self._get_connection()
            conn.execute("UPDATE models SET is_active = 0")
            conn.execute("UPDATE models SET is_active = 1 WHERE id = ?", (model_id,))
            conn.execute("UPDATE models SET last_used = ? WHERE id = ?", (datetime.now().isoformat(), model_id))
            conn.commit()
            conn.close()
    
    def update_model_usage(self, model_id: int):
        """Modell használat frissítése"""
        with self.lock:
            conn = self._get_connection()
            conn.execute("UPDATE models SET last_used = ? WHERE id = ?", (datetime.now().isoformat(), model_id))
            conn.commit()
            conn.close()
    
    def delete_model(self, model_id: int):
        """Modell törlése"""
        model = self.get_model(model_id)
        if model and model.get('is_active'):
            raise ValueError("Active model cannot be deleted")
        
        with self.lock:
            conn = self._get_connection()
            conn.execute("DELETE FROM models WHERE id = ?", (model_id,))
            conn.commit()
            conn.close()
    
    # ========== AUDIT LOG ==========
    
    def add_audit_log(self, user_id: int, action: str, resource: str, 
                      details: Dict = None, ip_address: str = None) -> int:
        """Audit log bejegyzés hozzáadása"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute("""
                INSERT INTO audit_log (user_id, action, resource, details, ip_address)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, action, resource, json.dumps(details) if details else None, ip_address))
            
            conn.commit()
            last_id = cursor.lastrowid
            conn.close()
            return last_id
    
    def get_audit_log(self, user_id: int = None, limit: int = 100) -> List[Dict]:
        """Audit log lekérése"""
        with self.lock:
            conn = self._get_connection()
            if user_id:
                cursor = conn.execute("""
                    SELECT * FROM audit_log WHERE user_id = ?
                    ORDER BY timestamp DESC LIMIT ?
                """, (user_id, limit))
            else:
                cursor = conn.execute("""
                    SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?
                """, (limit,))
            
            result = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return result
    
    # ========== TELJESÍTMÉNY METRIKÁK ==========
    
    def add_performance_metric(self, module: str, metric_name: str, 
                               metric_value: float, tags: Dict = None) -> int:
        """Teljesítmény metrika hozzáadása"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute("""
                INSERT INTO performance_metrics (module, metric_name, metric_value, tags)
                VALUES (?, ?, ?, ?)
            """, (module, metric_name, metric_value, json.dumps(tags) if tags else None))
            
            conn.commit()
            last_id = cursor.lastrowid
            conn.close()
            return last_id
    
    def get_performance_metrics(self, module: str = None, metric_name: str = None,
                                 limit: int = 100) -> List[Dict]:
        """Teljesítmény metrikák lekérése"""
        with self.lock:
            conn = self._get_connection()
            
            if module and metric_name:
                cursor = conn.execute("""
                    SELECT * FROM performance_metrics 
                    WHERE module = ? AND metric_name = ?
                    ORDER BY timestamp DESC LIMIT ?
                """, (module, metric_name, limit))
            elif module:
                cursor = conn.execute("""
                    SELECT * FROM performance_metrics 
                    WHERE module = ?
                    ORDER BY timestamp DESC LIMIT ?
                """, (module, limit))
            else:
                cursor = conn.execute("""
                    SELECT * FROM performance_metrics 
                    ORDER BY timestamp DESC LIMIT ?
                """, (limit,))
            
            result = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return result
    
    # ========== RENDSZERBEÁLLÍTÁSOK ==========
    
    def get_system_setting(self, key: str, default=None):
        """Rendszerbeállítás lekérése"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute("SELECT value, type FROM system_settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return default
            
            value = row['value']
            value_type = row['type']
            
            if value_type == 'int':
                return int(value)
            elif value_type == 'float':
                return float(value)
            elif value_type == 'bool':
                return value.lower() in ('true', '1', 'yes')
            elif value_type == 'json':
                return json.loads(value)
            else:
                return value
    
    def set_system_setting(self, key: str, value: Any, value_type: str = None, 
                          category: str = 'general', description: str = ''):
        """Rendszerbeállítás mentése"""
        if value_type is None:
            if isinstance(value, bool):
                value_type = 'bool'
                value = str(value)
            elif isinstance(value, int):
                value_type = 'int'
                value = str(value)
            elif isinstance(value, float):
                value_type = 'float'
                value = str(value)
            elif isinstance(value, (dict, list)):
                value_type = 'json'
                value = json.dumps(value)
            else:
                value_type = 'string'
                value = str(value)
        
        with self.lock:
            conn = self._get_connection()
            conn.execute("""
                INSERT OR REPLACE INTO system_settings (key, value, type, category, description, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (key, str(value), value_type, category, description))
            
            conn.commit()
            conn.close()
    
    def get_all_system_settings(self, category: str = None) -> Dict:
        """Összes rendszerbeállítás lekérése"""
        with self.lock:
            conn = self._get_connection()
            if category:
                cursor = conn.execute("SELECT key, value, type FROM system_settings WHERE category = ?", (category,))
            else:
                cursor = conn.execute("SELECT key, value, type FROM system_settings")
            
            settings = {}
            for row in cursor.fetchall():
                key = row['key']
                value = row['value']
                value_type = row['type']
                
                if value_type == 'int':
                    settings[key] = int(value)
                elif value_type == 'float':
                    settings[key] = float(value)
                elif value_type == 'bool':
                    settings[key] = value.lower() in ('true', '1', 'yes')
                elif value_type == 'json':
                    settings[key] = json.loads(value)
                else:
                    settings[key] = value
            
            conn.close()
            return settings
    
    # ========== RÉGI SETTINGS (KOMPATIBILITÁS) ==========
    
    def get_setting(self, key: str, default=None):
        """Régi típusú beállítás lekérése (kompatibilitás)"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute("SELECT value, type FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return default
            
            value = row['value']
            value_type = row['type']
            
            if value_type == 'int':
                return int(value)
            elif value_type == 'float':
                return float(value)
            elif value_type == 'bool':
                return value.lower() in ('true', '1', 'yes')
            elif value_type == 'json':
                return json.loads(value)
            else:
                return value
    
    def set_setting(self, key: str, value: Any, value_type: str = None, 
                   category: str = 'general', description: str = ''):
        """Régi típusú beállítás mentése (kompatibilitás)"""
        if value_type is None:
            if isinstance(value, bool):
                value_type = 'bool'
                value = str(value)
            elif isinstance(value, int):
                value_type = 'int'
                value = str(value)
            elif isinstance(value, float):
                value_type = 'float'
                value = str(value)
            elif isinstance(value, (dict, list)):
                value_type = 'json'
                value = json.dumps(value)
            else:
                value_type = 'string'
                value = str(value)
        
        with self.lock:
            conn = self._get_connection()
            conn.execute("""
                INSERT OR REPLACE INTO settings (key, value, type, category, description, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (key, str(value), value_type, category, description))
            
            conn.commit()
            conn.close()
    
    def get_all_settings(self, category: str = None) -> Dict:
        """Régi típusú összes beállítás lekérése (kompatibilitás)"""
        with self.lock:
            conn = self._get_connection()
            if category:
                cursor = conn.execute("SELECT key, value, type FROM settings WHERE category = ?", (category,))
            else:
                cursor = conn.execute("SELECT key, value, type FROM settings")
            
            settings = {}
            for row in cursor.fetchall():
                key = row['key']
                value = row['value']
                value_type = row['type']
                
                if value_type == 'int':
                    settings[key] = int(value)
                elif value_type == 'float':
                    settings[key] = float(value)
                elif value_type == 'bool':
                    settings[key] = value.lower() in ('true', '1', 'yes')
                elif value_type == 'json':
                    settings[key] = json.loads(value)
                else:
                    settings[key] = value
            
            conn.close()
            return settings
    
    def close(self):
        """Kapcsolat zárása (nincs teendő)"""
        pass


# Teszt
if __name__ == "__main__":
    db = Database(":memory:")
    
    # Beszélgetés
    conv_id = db.create_conversation(title="Test", model="test")
    print(f"Conversation: {conv_id}")
    
    # Üzenetek
    db.add_message(conv_id, "user", "Hello!", 5)
    db.add_message(conv_id, "assistant", "Hi there!", 10)
    
    # Lekérdezések
    messages = db.get_messages(conv_id)
    print(f"Messages: {len(messages)}")
    
    # Személyiség
    pers_id = db.save_personality("Test", "content", activate=True)
    print(f"Personality: {pers_id}")
    
    # Felhasználó
    user_id = db.create_user("testuser")
    print(f"User: {user_id}")
    
    # Statisztika
    stats = db.get_user_stats(user_id)
    print(f"Stats: {stats}")
    
    print("Database test completed")