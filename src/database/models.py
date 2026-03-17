"""
Adatbázis modellek a SoulCore számára.
Támogatja a beszélgetések, promptok, beállítások, személyiségek és felhasználók tárolását.
"""

import json
import time
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

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
    
    def __init__(self, db_path: str = "data/soulcore.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Lock a thread safety-hez
        self.lock = threading.RLock()
        
        # Inicializálás
        self._init_db()
    
    def _get_connection(self):
        """Új SQLite kapcsolat létrehozása (thread-safe)"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self):
        """Adatbázis inicializálása (táblák létrehozása)"""
        with self.lock:
            conn = self._get_connection()
            
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
                    user_id INTEGER
                )
            """)
            
            # Üzenetek
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER,
                    role TEXT CHECK(role IN ('user', 'assistant', 'system', 'jester')),
                    content TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    tokens INTEGER DEFAULT 0,
                    metadata TEXT,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
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
            
            # Beállítások (régi, átmeneti - kivezetésre kerül)
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
                    path TEXT,
                    size TEXT,
                    quantization TEXT,
                    n_ctx INTEGER DEFAULT 4096,
                    n_gpu_layers INTEGER DEFAULT -1,
                    description TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            
            # Rendszerbeállítások (config.yaml helyett)
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            
            conn.commit()
            conn.close()
            
            # Alapértelmezett promptok beszúrása (ha még nincsenek)
            self._init_default_prompts()
            
            # Alapértelmezett személyiség beszúrása (ha még nincs)
            self._init_default_personality()
    
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
                except:
                    pass
            conn.commit()
            conn.close()
    
    def _init_default_personality(self):
        """Alapértelmezett személyiség létrehozása, ha még nincs egy sem"""
        with self.lock:
            conn = self._get_connection()
            
            # Ellenőrizzük, van-e már személyiség
            cursor = conn.execute("SELECT COUNT(*) FROM personalities")
            count = cursor.fetchone()[0]
            
            if count == 0:
                # Alapértelmezett személyiség
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
                    INSERT INTO personalities (name, content, is_active)
                    VALUES (?, ?, 1)
                """, ("Default King", default_personality))
                
                print("📝 Alapértelmezett személyiség létrehozva")
            
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
    
    def get_conversations(self, limit: int = 50, offset: int = 0, user_id: int = None) -> List[Dict]:
        """Beszélgetések listázása (opcionálisan felhasználó szerint szűrve)"""
        with self.lock:
            conn = self._get_connection()
            
            if user_id:
                cursor = conn.execute("""
                    SELECT * FROM conversations 
                    WHERE user_id = ? 
                    ORDER BY updated_at DESC 
                    LIMIT ? OFFSET ?
                """, (user_id, limit, offset))
            else:
                cursor = conn.execute("""
                    SELECT * FROM conversations 
                    ORDER BY updated_at DESC 
                    LIMIT ? OFFSET ?
                """, (limit, offset))
            
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
    
    def update_conversation(self, conv_id: int, **kwargs):
        """Beszélgetés frissítése"""
        fields = []
        values = []
        
        for key, value in kwargs.items():
            if key in ['title', 'model', 'system_prompt', 'metadata', 'user_id']:
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
    
    def delete_conversation(self, conv_id: int):
        """Beszélgetés törlése"""
        with self.lock:
            conn = self._get_connection()
            conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
            conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
            conn.commit()
            conn.close()
    
    # ========== ÜZENETEK ==========
    
    def add_message(self, conversation_id: int, role: str, content: str, 
                   tokens: int = 0, metadata: Dict = None) -> int:
        """Üzenet hozzáadása"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute("""
                INSERT INTO messages (conversation_id, role, content, tokens, metadata)
                VALUES (?, ?, ?, ?, ?)
            """, (conversation_id, role, content, tokens, json.dumps(metadata) if metadata else None))
            
            # Beszélgetés frissítése
            conn.execute("""
                UPDATE conversations SET updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (conversation_id,))
            
            conn.commit()
            last_id = cursor.lastrowid
            conn.close()
            return last_id
    
    def get_messages(self, conversation_id: int, limit: int = 100) -> List[Dict]:
        """Üzenetek lekérése beszélgetésből"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute("""
                SELECT * FROM messages 
                WHERE conversation_id = ? 
                ORDER BY timestamp ASC
                LIMIT ?
            """, (conversation_id, limit))
            
            messages = []
            for row in cursor.fetchall():
                msg = dict(row)
                if msg['metadata']:
                    msg['metadata'] = json.loads(msg['metadata'])
                messages.append(msg)
            
            conn.close()
            return messages
    
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
        """Prompt mentése (új vagy meglévő frissítése)"""
        existing = self.get_prompt(name=name)
        
        with self.lock:
            conn = self._get_connection()
            if existing:
                # Frissítés
                conn.execute("""
                    UPDATE prompts 
                    SET content = ?, description = ?, category = ?, is_default = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE name = ?
                """, (content, description, category, is_default, name))
                result = existing['id']
            else:
                # Új beszúrás
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
        # Ne lehessen alapértelmezett promptot törölni
        prompt = self.get_prompt(prompt_id)
        if prompt and prompt['is_default']:
            raise ValueError("Alapértelmezett prompt nem törölhető")
        
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
        """Személyiség mentése (új vagy meglévő frissítése)"""
        existing = self.get_personality(name=name)
        
        with self.lock:
            conn = self._get_connection()
            if existing:
                # Frissítés
                conn.execute("""
                    UPDATE personalities 
                    SET content = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE name = ?
                """, (content, name))
                result = existing['id']
            else:
                # Új beszúrás
                cursor = conn.execute("""
                    INSERT INTO personalities (name, content)
                    VALUES (?, ?)
                """, (name, content))
                result = cursor.lastrowid
            
            # Ha aktiválni kell
            if activate:
                # Először minden más személyiséget inaktívvá teszünk
                conn.execute("UPDATE personalities SET is_active = 0")
                # Majd ezt aktívvá
                conn.execute("UPDATE personalities SET is_active = 1 WHERE id = ?", (result,))
            
            conn.commit()
            conn.close()
            return result
    
    def activate_personality(self, personality_id: int):
        """Személyiség aktiválása (a többi automatikusan inaktív lesz)"""
        with self.lock:
            conn = self._get_connection()
            # Először minden személyiséget inaktívvá teszünk
            conn.execute("UPDATE personalities SET is_active = 0")
            # Majd ezt aktívvá
            conn.execute("UPDATE personalities SET is_active = 1 WHERE id = ?", (personality_id,))
            conn.commit()
            conn.close()
    
    def delete_personality(self, personality_id: int):
        """Személyiség törlése"""
        # Ellenőrizzük, hogy nem aktív-e
        personality = self.get_personality(personality_id)
        if personality and personality['is_active']:
            raise ValueError("Aktív személyiség nem törölhető")
        
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
                INSERT INTO users (username, display_name, role, language, preferences)
                VALUES (?, ?, ?, ?, ?)
            """, (username, display_name, role, language, 
                  json.dumps(preferences) if preferences else None))
            
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
    
    def get_users(self) -> List[Dict]:
        """Összes felhasználó listázása"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute("SELECT * FROM users ORDER BY username")
            result = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return result
    
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
    
    # ========== RENDSZERBEÁLLÍTÁSOK ==========
    
    def get_system_setting(self, key: str, default=None):
        """Egy rendszerbeállítás lekérése"""
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
    
    def get_model(self, model_id: int = None, name: str = None) -> Optional[Dict]:
        """Egy modell lekérése"""
        with self.lock:
            conn = self._get_connection()
            if model_id:
                cursor = conn.execute("SELECT * FROM models WHERE id = ?", (model_id,))
            elif name:
                cursor = conn.execute("SELECT * FROM models WHERE name = ?", (name,))
            else:
                conn.close()
                return None
            
            row = cursor.fetchone()
            conn.close()
            return dict(row) if row else None
    
    def set_active_model(self, model_id: int):
        """Aktív modell beállítása"""
        with self.lock:
            conn = self._get_connection()
            # Minden modell inaktív
            conn.execute("UPDATE models SET is_active = 0")
            # A kiválasztott aktív
            conn.execute("UPDATE models SET is_active = 1 WHERE id = ?", (model_id,))
            conn.commit()
            conn.close()
    
    def delete_model(self, model_id: int):
        """Modell törlése"""
        with self.lock:
            conn = self._get_connection()
            conn.execute("DELETE FROM models WHERE id = ?", (model_id,))
            conn.commit()
            conn.close()
    
    # ========== RÉGI SETTINGS (ÁTMENETI) ==========
    
    def get_setting(self, key: str, default=None):
        """Régi típusú beállítás lekérése (kivezetésre kerül)"""
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
        """Régi típusú beállítás mentése (kivezetésre kerül)"""
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
        """Régi típusú összes beállítás lekérése (kivezetésre kerül)"""
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
        """Nincs mit zárni, mert minden művelet után zárjuk a kapcsolatot"""
        pass

# Teszt
if __name__ == "__main__":
    db = Database(":memory:")  # Teszt adatbázis
    
    # Beszélgetés létrehozása
    conv_id = db.create_conversation(title="Test conversation", model="test-model")
    print(f"Conversation ID: {conv_id}")
    
    # Üzenetek hozzáadása
    db.add_message(conv_id, "user", "Hello!", 5)
    db.add_message(conv_id, "assistant", "Hi there!", 10)
    
    # Üzenetek lekérése
    messages = db.get_messages(conv_id)
    print("\nMessages:")
    for msg in messages:
        print(f"  {msg['role']}: {msg['content']} ({msg['tokens']} tokens)")
    
    # Személyiség létrehozása
    pers_id = db.save_personality("Test Personality", "content here", activate=True)
    print(f"\nPersonality ID: {pers_id}")
    
    # Aktív személyiség lekérése
    active = db.get_active_personality()
    print(f"Active personality: {active['name']}")
    
    # Felhasználó létrehozása
    user_id = db.create_user("testuser", "Test User", role="admin")
    print(f"\nUser ID: {user_id}")
    
    # Felhasználó lekérése
    user = db.get_user(user_id)
    print(f"User: {user['username']} ({user['display_name']})")
    
    # Rendszerbeállítás
    db.set_system_setting("test_key", 42, "int", "test", "Test setting")
    value = db.get_system_setting("test_key")
    print(f"\nSystem setting: {value}")