"""
Scratchpad - A rendszer rövid távú memóriája és kommunikációs fala.
Ide írnak a modulok, innen olvasnak. Minden lát mindent, de senki sem zavar senkit.
"""

import time
import uuid
import threading
from datetime import datetime, timedelta
from collections import defaultdict, deque
from typing import Dict, List, Any, Optional, Union

class Scratchpad:
    """
    A közös memória fal. Minden modul ide írja a gondolatait,
    és innen olvassa mások gondolatait.
    """
    
    def __init__(self, max_history=1000):
        self.lock = threading.RLock()  # Újra beléphető lock a biztonságos íráshoz
        
        # Állapotok - aktuális értékek (felülíródnak)
        self.state = {
            'uptime_seconds': 0,
            'last_interaction': None,
            'current_mood': 'neutral',
            'active_trace_id': None,
            'system_status': 'starting'
        }
        
        # Rövid távú memória - időbélyeges bejegyzések
        self.entries = deque(maxlen=max_history)
        
        # Modul-specifikus jegyzettömbök (token-takarékos)
        self.notepads = defaultdict(dict)  # {modul: {kulcs: érték}}
        
        # Esemény figyelők (ha valaki vár egy adott eseményre)
        self.event_listeners = defaultdict(list)
        
        # Hibanapló (debug célra)
        self._debug_log = []
        
        print("📝 Scratchpad: Memóriafal inicializálva")
    
    # --- ÁLLAPOT KEZELÉS ---
    
    def set_state(self, key: str, value: Any, source: str = "system"):
        """Állapot beállítása (felülírja a régit)"""
        try:
            with self.lock:
                old = self.state.get(key)
                self.state[key] = value
                self._log_entry('state_change', {
                    'key': key,
                    'old': old,
                    'new': value,
                    'source': source
                })
        except Exception as e:
            self._debug(f"set_state hiba: {e}")
    
    def get_state(self, key: str, default=None):
        """Állapot lekérése"""
        try:
            with self.lock:
                return self.state.get(key, default)
        except Exception as e:
            self._debug(f"get_state hiba: {e}")
            return default
    
    # --- JEGYZETTÖMB KEZELÉS (token-takarékos memória) ---
    
    def write_note(self, module: str, key: str, value: Any):
        """
        Modul saját jegyzettömbjébe ír.
        Ezek az értékek nem évülnek el, amíg felül nem írják őket.
        """
        try:
            with self.lock:
                # Biztosítjuk, hogy a value serializálható legyen
                safe_value = self._make_serializable(value)
                self.notepads[module][key] = {
                    'value': safe_value,
                    'timestamp': time.time(),
                    'module': module
                }
        except Exception as e:
            self._debug(f"write_note hiba: {e}")
    
    def read_note(self, module: str, key: str, default=None):
        """Modul saját jegyzetének olvasása"""
        try:
            with self.lock:
                note = self.notepads.get(module, {}).get(key)
                if note and isinstance(note, dict):
                    return note.get('value', default)
                return default
        except Exception as e:
            self._debug(f"read_note hiba: {e}")
            return default
    
    def read_all_notes(self, module: str = None):
        """Modul összes jegyzetének olvasása (vagy az összes modulé)"""
        try:
            with self.lock:
                if module:
                    notes = self.notepads.get(module, {})
                    # Visszaadjuk az értékeket a metaadatok nélkül
                    return {k: v.get('value') if isinstance(v, dict) else v 
                            for k, v in notes.items()}
                # Minden modul összes jegyezete
                result = {}
                for mod, notes in self.notepads.items():
                    result[mod] = {k: v.get('value') if isinstance(v, dict) else v 
                                   for k, v in notes.items()}
                return result
        except Exception as e:
            self._debug(f"read_all_notes hiba: {e}")
            return {} if module else {}
    
    # --- IDŐBÉLYEGES BEJEGYZÉSEK (üzenetek, gondolatok) ---
    
    def write(self, module: str, content: Any, msg_type: str = "thought"):
        """
        Új bejegyzés írása a közös falra.
        Minden bejegyzés kap egy egyedi ID-t és időbélyeget.
        """
        try:
            with self.lock:
                # Biztosítjuk, hogy a content serializálható legyen
                safe_content = self._make_serializable(content)
                
                entry = {
                    'id': str(uuid.uuid4())[:8],
                    'time': datetime.now().isoformat(),
                    'timestamp': time.time(),
                    'module': str(module),
                    'type': str(msg_type),
                    'content': safe_content
                }
                self.entries.append(entry)
                
                # Ha van listener erre a típusra, értesítjük
                if msg_type in self.event_listeners:
                    for callback in self.event_listeners[msg_type]:
                        try:
                            callback(entry)
                        except Exception as e:
                            self._debug(f"Listener hiba: {e}")
                
                return entry['id']
        except Exception as e:
            self._debug(f"write hiba: {e}")
            return None
    
    def read(self, limit: int = 50, since: float = None, msg_type: str = None):
        """
        Bejegyzések olvasása.
        - limit: maximum szám
        - since: csak ennél újabbak (timestamp)
        - msg_type: csak adott típus
        """
        try:
            with self.lock:
                result = list(self.entries)
                
                # Szűrés
                if since is not None:
                    result = [e for e in result if e.get('timestamp', 0) > since]
                if msg_type is not None:
                    result = [e for e in result if e.get('type') == msg_type]
                
                # Visszafelé sorrend (újabb elöl)
                result.reverse()
                return result[:limit]
        except Exception as e:
            self._debug(f"read hiba: {e}")
            return []
    
    def read_last(self, msg_type: str = None):
        """Utolsó bejegyzés olvasása (opcionálisan típus szerint)"""
        try:
            with self.lock:
                for entry in reversed(self.entries):
                    if msg_type is None or entry.get('type') == msg_type:
                        return entry
                return None
        except Exception as e:
            self._debug(f"read_last hiba: {e}")
            return None
    
    # --- ESEMÉNYKEZELÉS (értesülések) ---
    
    def on(self, event_type: str, callback):
        """Esemény figyelő regisztrálása"""
        try:
            with self.lock:
                if callable(callback):
                    self.event_listeners[event_type].append(callback)
        except Exception as e:
            self._debug(f"on hiba: {e}")
    
    def off(self, event_type: str, callback):
        """Esemény figyelő eltávolítása"""
        try:
            with self.lock:
                if callback in self.event_listeners[event_type]:
                    self.event_listeners[event_type].remove(callback)
        except Exception as e:
            self._debug(f"off hiba: {e}")
    
    # --- BELSŐ SEGÉDFÜGGVÉNYEK ---
    
    def _log_entry(self, entry_type, data):
        """Belső események naplózása"""
        try:
            self.write('scratchpad', data, entry_type)
        except Exception as e:
            self._debug(f"_log_entry hiba: {e}")
    
    def _make_serializable(self, obj: Any) -> Any:
        """
        Objektum átalakítása biztonságosan tárolható formátumba.
        """
        if obj is None:
            return None
        if isinstance(obj, (str, int, float, bool)):
            return obj
        if isinstance(obj, (list, tuple)):
            return [self._make_serializable(item) for item in obj]
        if isinstance(obj, dict):
            return {str(k): self._make_serializable(v) for k, v in obj.items()}
        # Ha nem serializálható, stringgé alakítjuk
        try:
            # Próbáljuk meg JSON serializálni
            import json
            json.dumps(obj)
            return obj
        except:
            # Ha nem megy, stringgé alakítjuk
            return str(obj)
    
    def _debug(self, message: str):
        """Debug üzenet naplózása"""
        timestamp = datetime.now().isoformat()
        self._debug_log.append(f"[{timestamp}] {message}")
        # Csak az utolsó 100 üzenetet tartjuk meg
        if len(self._debug_log) > 100:
            self._debug_log = self._debug_log[-100:]
        print(f"📝 Scratchpad debug: {message}")
    
    def get_summary(self) -> Dict:
        """Összefoglaló a memória állapotáról"""
        try:
            with self.lock:
                return {
                    'state': dict(self.state),
                    'entry_count': len(self.entries),
                    'modules': list(self.notepads.keys()),
                    'last_entry': self.read_last(),
                    'debug_log_count': len(self._debug_log)
                }
        except Exception as e:
            self._debug(f"get_summary hiba: {e}")
            return {
                'state': {},
                'entry_count': 0,
                'modules': [],
                'last_entry': None,
                'error': str(e)
            }
    
    def cleanup_old(self, max_age_seconds: int = 3600):
        """Régebbi bejegyzések törlése (memóriatakarékosság)"""
        try:
            with self.lock:
                cutoff = time.time() - max_age_seconds
                # deque nem támogatja a szűrést, újat kell építeni
                new_entries = deque(maxlen=self.entries.maxlen)
                for e in self.entries:
                    if e.get('timestamp', 0) > cutoff:
                        new_entries.append(e)
                self.entries = new_entries
                self._debug(f"cleanup_old: {len(new_entries)} bejegyzés maradt")
        except Exception as e:
            self._debug(f"cleanup_old hiba: {e}")
    
    def get_debug_log(self) -> List[str]:
        """Debug napló lekérése"""
        return list(self._debug_log)

# Ha önállóan futtatjuk, teszteljük
if __name__ == "__main__":
    s = Scratchpad()
    
    # Teszt írás
    s.write('king', 'Gondolkodom...', 'internal_monologue')
    s.write('scribe', {'intent': 'greeting', 'confidence': 0.9}, 'intent')
    
    # Teszt olvasás
    print(s.read(limit=5))
    
    # Teszt jegyzet
    s.write_note('king', 'last_mood', 'curious')
    print(s.read_note('king', 'last_mood'))
    
    # Teszt állapot
    s.set_state('current_mood', 'happy', 'king')
    print(s.get_state('current_mood'))
    
    # Teszt nem serializálható objektum
    class TestClass:
        def __init__(self):
            self.x = 1
    
    s.write_note('test', 'object', TestClass())
    print(s.read_note('test', 'object'))
    
    # Összefoglaló
    print(s.get_summary())