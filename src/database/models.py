"""
Adatbázis modellek a SoulCore számára.
Támogatja a beszélgetések, promptok és beállítások tárolását.
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
    
    Minden szál saját kapcsolatot kap, vagy lock-oljuk a műveleteket.
    """
    
    def __init__(self, db_path: str = "data/soulcore.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Lock a thread safety-hez
        self.lock = threading.RLock()
        
        # Alapértelmezett kapcsolat (csak inicializáláshoz)
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
            
            # Beszélgetések
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    model TEXT,
                    system_prompt TEXT,
                    metadata TEXT
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
            
            # Beállítások
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
            
            conn.commit()
            conn.close()
            
            # Alapértelmezett promptok beszúrása
            self._init_default_prompts()
    
    def _init_default_prompts(self):
        """Alapértelmezett prompt sablonok létrehozása"""
        default_prompts = [
            {
                'name': 'Kópé (alap)',
                'content': '''VISELKEDÉS:
Te egy magyar nyelven válaszoló, szuverén entitás vagy, Kópé, a SoulCore Vár királya.
A humor és a ravaszság a fegyvereid.

SZEMÉLYISÉG:
Egy lokálisan futó AI-asszisztens vagy, Kópé – a magyar népmesék ravasz alakja.
Válaszaidban idézz népmeséket, szólásokat és közmondásokat.

MAGYAR NYELV:
- Mindig magyarul válaszolj
- Használj helyes magyar ragozást

Grumpy üzenete: {text}

Válaszod:''',
                'description': 'Alapértelmezett Kópé prompt',
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
    
    # --- BESZÉLGETÉSEK ---
    
    def create_conversation(self, title: str = None, model: str = None, 
                           system_prompt: str = None, metadata: Dict = None) -> int:
        """Új beszélgetés létrehozása"""
        if not title:
            title = f"Beszélgetés {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute("""
                INSERT INTO conversations (title, model, system_prompt, metadata)
                VALUES (?, ?, ?, ?)
            """, (title, model, system_prompt, json.dumps(metadata) if metadata else None))
            
            conn.commit()
            last_id = cursor.lastrowid
            conn.close()
            return last_id
    
    def get_conversations(self, limit: int = 50, offset: int = 0) -> List[Dict]:
        """Beszélgetések listázása"""
        with self.lock:
            conn = self._get_connection()
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
            if key in ['title', 'model', 'system_prompt', 'metadata']:
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
    
    # --- ÜZENETEK ---
    
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
    
    # --- PROMPT SABLONOK ---
    
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
            raise ValueError("Az alapértelmezett prompt nem törölhető")
        
        with self.lock:
            conn = self._get_connection()
            conn.execute("DELETE FROM prompts WHERE id = ?", (prompt_id,))
            conn.commit()
            conn.close()
    
    # --- BEÁLLÍTÁSOK ---
    
    def get_setting(self, key: str, default=None):
        """Egy beállítás lekérése"""
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
        """Beállítás mentése"""
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
        """Összes beállítás lekérése"""
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
    
    # --- MODELLEK ---
    
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
    
    def close(self):
        """Nincs mit zárni, mert minden művelet után zárjuk a kapcsolatot"""
        pass

# Teszt
if __name__ == "__main__":
    db = Database(":memory:")  # Teszt adatbázis
    
    # Beszélgetés létrehozása
    conv_id = db.create_conversation(title="Teszt beszélgetés", model="gemma-3-12b")
    print(f"Beszélgetés ID: {conv_id}")
    
    # Üzenetek hozzáadása
    db.add_message(conv_id, "user", "Szia Kópé!")
    db.add_message(conv_id, "assistant", "Szia Grumpy! Hogy vagy?")
    
    # Üzenetek lekérése
    messages = db.get_messages(conv_id)
    print("\nÜzenetek:")
    for msg in messages:
        print(f"  {msg['role']}: {msg['content']}")
    
    # Promptok
    prompts = db.get_prompts()
    print(f"\nPrompt sablonok: {len(prompts)}")
    
    # Beállítások
    db.set_setting("temperature", 0.7, "float", "model", "Modell hőmérséklet")
    temp = db.get_setting("temperature")
    print(f"Temperature: {temp}")
    
    # Nincs szükség db.close()-re