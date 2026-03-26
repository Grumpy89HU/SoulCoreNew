"""
Scratchpad - A rendszer rövid távú memóriája és kommunikációs fala.
Ide írnak a modulok, innen olvasnak. Minden lát mindent, de senki sem zavar senkit.

Funkciók:
- Jegyzet tömb (token-takarékos memória)
- Rejtett piszkozat (belső monológ)
- Állapot kezelés
- Esemény figyelők
- Token-takarékos működés
"""

import time
import uuid
import threading
import json
from datetime import datetime, timedelta
from collections import defaultdict, deque
from typing import Dict, List, Any, Optional, Callable, Union

# i18n import (opcionális)
try:
    from src.i18n.translator import get_translator
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False


class Scratchpad:
    """
    A közös memória fal. Minden modul ide írja a gondolatait,
    és innen olvassa mások gondolatait.
    
    Token-takarékos működés:
    - Jegyzet tömb: modul-specifikus jegyzetek, nem évülnek el
    - Rejtett piszkozat: belső monológok, amik nem mennek a Kingnek
    - Állapotok: aktuális értékek, felülíródnak
    """
    
    def __init__(self, max_history=1000):
        self.lock = threading.RLock()
        
        # Állapotok - aktuális értékek (felülíródnak)
        self.state = {
            'uptime_seconds': 0,
            'uptime_formatted': '0s',
            'last_interaction': None,
            'current_mood': 'neutral',
            'active_trace_id': None,
            'system_status': 'starting',
            'user_name': 'User',
            'user_language': 'en',
            'user_role': 'user'
        }
        
        # Rövid távú memória - időbélyeges bejegyzések
        self.entries = deque(maxlen=max_history)
        
        # Modul-specifikus jegyzettömbök (token-takarékos)
        self.notepads = defaultdict(dict)  # {modul: {kulcs: érték}}
        
        # Rejtett piszkozatok (belső monológok)
        self.drafts = defaultdict(list)  # {modul: [piszkozatok]}
        
        # Esemény figyelők
        self.event_listeners = defaultdict(list)
        
        # Token számláló
        self.token_estimates = defaultdict(int)
        
        # Debug napló
        self._debug_log = deque(maxlen=100)
        
        print("📝 Scratchpad: Memóriafal inicializálva")
    
    # ========== ÁLLAPOT KEZELÉS ==========
    
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
                
                if isinstance(value, str):
                    self.token_estimates[f'state_{key}'] = len(value.split())
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
    
    def update_state(self, updates: Dict[str, Any], source: str = "system"):
        """Több állapot frissítése egyszerre"""
        try:
            with self.lock:
                for key, value in updates.items():
                    old = self.state.get(key)
                    self.state[key] = value
                    self._log_entry('state_change', {
                        'key': key,
                        'old': old,
                        'new': value,
                        'source': source
                    })
        except Exception as e:
            self._debug(f"update_state hiba: {e}")
    
    # ========== JEGYZETTÖMB KEZELÉS ==========
    
    def write_note(self, module: str, key: str, value: Any, ttl: int = None):
        """
        Modul saját jegyzettömbjébe ír.
        ttl: élettartam másodpercben (None = örök)
        """
        try:
            with self.lock:
                safe_value = self._make_serializable(value)
                self.notepads[module][key] = {
                    'value': safe_value,
                    'timestamp': time.time(),
                    'module': module,
                    'ttl': ttl
                }
                
                if isinstance(value, str):
                    self.token_estimates[f'note_{module}_{key}'] = len(value.split())
        except Exception as e:
            self._debug(f"write_note hiba: {e}")
    
    def read_note(self, module: str, key: str, default=None):
        """Modul saját jegyzetének olvasása (TTL ellenőrzéssel)"""
        try:
            with self.lock:
                note = self.notepads.get(module, {}).get(key)
                if note and isinstance(note, dict):
                    now = time.time()
                    ttl = note.get('ttl')
                    if ttl and now - note['timestamp'] > ttl:
                        # Lejárt, töröljük
                        del self.notepads[module][key]
                        return default
                    return note.get('value', default)
                return default
        except Exception as e:
            self._debug(f"read_note hiba: {e}")
            return default
    
    def read_all_notes(self, module: str = None):
        """Modul összes jegyzetének olvasása (TTL ellenőrzéssel)"""
        try:
            with self.lock:
                if module:
                    notes = self.notepads.get(module, {})
                    now = time.time()
                    result = {}
                    for k, v in list(notes.items()):
                        if isinstance(v, dict):
                            ttl = v.get('ttl')
                            if ttl and now - v['timestamp'] > ttl:
                                del notes[k]
                            else:
                                result[k] = v.get('value')
                        else:
                            result[k] = v
                    return result
                
                # Minden modul
                result = {}
                for mod, notes in self.notepads.items():
                    result[mod] = {}
                    now = time.time()
                    for k, v in list(notes.items()):
                        if isinstance(v, dict):
                            ttl = v.get('ttl')
                            if ttl and now - v['timestamp'] > ttl:
                                del notes[k]
                            else:
                                result[mod][k] = v.get('value')
                        else:
                            result[mod][k] = v
                return result
        except Exception as e:
            self._debug(f"read_all_notes hiba: {e}")
            return {} if module else {}
    
    def get_notes_by_prefix(self, module: str, prefix: str) -> Dict[str, Any]:
        """Prefix alapján keresés a jegyzetekben"""
        try:
            with self.lock:
                notes = self.notepads.get(module, {})
                result = {}
                for key, note in notes.items():
                    if key.startswith(prefix):
                        if isinstance(note, dict):
                            result[key] = note.get('value')
                        else:
                            result[key] = note
                return result
        except Exception as e:
            self._debug(f"get_notes_by_prefix hiba: {e}")
            return {}
    
    def clear_section(self, module: str):
        """Adott modul összes jegyzetének törlése"""
        try:
            with self.lock:
                if module in self.notepads:
                    # Token becslések törlése
                    for key in list(self.notepads[module].keys()):
                        token_key = f'note_{module}_{key}'
                        if token_key in self.token_estimates:
                            del self.token_estimates[token_key]
                    del self.notepads[module]
                    self._debug(f"clear_section: {module} jegyzetei törölve")
        except Exception as e:
            self._debug(f"clear_section hiba: {e}")
    
    def delete_note(self, module: str, key: str):
        """Jegyzet törlése"""
        try:
            with self.lock:
                if module in self.notepads and key in self.notepads[module]:
                    del self.notepads[module][key]
                    token_key = f'note_{module}_{key}'
                    if token_key in self.token_estimates:
                        del self.token_estimates[token_key]
        except Exception as e:
            self._debug(f"delete_note hiba: {e}")
    
    # ========== REJTETT PISZKOLAT ==========
    
    def write_draft(self, module: str, content: Any, draft_type: str = "internal"):
        """Rejtett piszkozat írása (belső monológ)"""
        try:
            with self.lock:
                draft = {
                    'id': str(uuid.uuid4())[:8],
                    'time': time.time(),
                    'datetime': datetime.now().isoformat(),
                    'module': module,
                    'type': draft_type,
                    'content': self._make_serializable(content)
                }
                self.drafts[module].append(draft)
                
                if len(self.drafts[module]) > 10:
                    self.drafts[module] = self.drafts[module][-10:]
                
                return draft['id']
        except Exception as e:
            self._debug(f"write_draft hiba: {e}")
            return None
    
    def read_drafts(self, module: str = None, limit: int = 10) -> List[Dict]:
        """Rejtett piszkozatok olvasása"""
        try:
            with self.lock:
                if module:
                    drafts = list(self.drafts.get(module, []))
                else:
                    drafts = []
                    for mod_drafts in self.drafts.values():
                        drafts.extend(mod_drafts)
                    drafts.sort(key=lambda x: x['time'], reverse=True)
                return drafts[:limit]
        except Exception as e:
            self._debug(f"read_drafts hiba: {e}")
            return []
    
    def clear_drafts(self, module: str = None):
        """Piszkozatok törlése"""
        try:
            with self.lock:
                if module:
                    if module in self.drafts:
                        self.drafts[module] = []
                else:
                    self.drafts.clear()
        except Exception as e:
            self._debug(f"clear_drafts hiba: {e}")
    
    # ========== IDŐBÉLYEGES BEJEGYZÉSEK ==========
    
    def write(self, module: str, content: Any, msg_type: str = "thought"):
        """Új bejegyzés írása a közös falra"""
        try:
            if not isinstance(content, dict):
                self._debug(f"Nem dict kerül a scratchpad-be! module={module}, type={type(content)}")
            
            with self.lock:
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
                
                # Token becslés
                if isinstance(content, str):
                    self.token_estimates[f'entry_{entry["id"]}'] = len(content.split())
                elif isinstance(content, dict):
                    total = 0
                    for k, v in content.items():
                        if isinstance(v, str):
                            total += len(v.split())
                    self.token_estimates[f'entry_{entry["id"]}'] = total
                
                # Eseménykibocsátás
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
    
    def read(self, limit: int = 50, since: float = None, msg_type: str = None, module: str = None):
        """Bejegyzések olvasása"""
        try:
            with self.lock:
                result = list(self.entries)
                
                if since is not None:
                    result = [e for e in result if e.get('timestamp', 0) > since]
                if msg_type is not None:
                    result = [e for e in result if e.get('type') == msg_type]
                if module is not None:
                    result = [e for e in result if e.get('module') == module]
                
                result.reverse()
                return result[:limit]
        except Exception as e:
            self._debug(f"read hiba: {e}")
            return []
    
    def read_last(self, msg_type: str = None, module: str = None):
        """Utolsó bejegyzés olvasása"""
        try:
            with self.lock:
                for entry in reversed(self.entries):
                    if msg_type and entry.get('type') != msg_type:
                        continue
                    if module and entry.get('module') != module:
                        continue
                    return entry
                return None
        except Exception as e:
            self._debug(f"read_last hiba: {e}")
            return None
    
    def search(self, query: str, limit: int = 10) -> List[Dict]:
        """Egyszerű szöveges keresés"""
        try:
            with self.lock:
                results = []
                query_lower = query.lower()
                
                for entry in reversed(self.entries):
                    content = entry.get('content', '')
                    content_str = str(content).lower()
                    
                    if query_lower in content_str:
                        results.append(entry)
                        if len(results) >= limit:
                            break
                
                return results
        except Exception as e:
            self._debug(f"search hiba: {e}")
            return []
    
    # ========== ESEMÉNYKEZELÉS ==========
    
    def on(self, event_type: str, callback: Callable):
        """Esemény figyelő regisztrálása"""
        try:
            with self.lock:
                if callable(callback):
                    self.event_listeners[event_type].append(callback)
        except Exception as e:
            self._debug(f"on hiba: {e}")
    
    def off(self, event_type: str, callback: Callable):
        """Esemény figyelő eltávolítása"""
        try:
            with self.lock:
                if callback in self.event_listeners[event_type]:
                    self.event_listeners[event_type].remove(callback)
        except Exception as e:
            self._debug(f"off hiba: {e}")
    
    def emit(self, event_type: str, data: Any):
        """Esemény kibocsátása"""
        try:
            with self.lock:
                for callback in self.event_listeners.get(event_type, []):
                    try:
                        callback(data)
                    except Exception as e:
                        self._debug(f"emit callback hiba: {e}")
        except Exception as e:
            self._debug(f"emit hiba: {e}")
    
    # ========== TOKEN TAKARÉKOSSÁG ==========
    
    def get_token_estimate(self, key: str = None) -> int:
        """Token becslés lekérése"""
        if key:
            return self.token_estimates.get(key, 0)
        return sum(self.token_estimates.values())
    
    def get_token_breakdown(self) -> Dict[str, int]:
        """Részletes token statisztika"""
        result = {
            'total': 0,
            'state': 0,
            'notes': 0,
            'entries': 0
        }
        
        for key, value in self.token_estimates.items():
            result['total'] += value
            if key.startswith('state_'):
                result['state'] += value
            elif key.startswith('note_'):
                result['notes'] += value
            elif key.startswith('entry_'):
                result['entries'] += value
        
        return result
    
    def prune_old_entries(self, max_age_seconds: int = 3600):
        """Régi bejegyzések törlése"""
        try:
            with self.lock:
                cutoff = time.time() - max_age_seconds
                new_entries = deque(maxlen=self.entries.maxlen)
                for e in self.entries:
                    if e.get('timestamp', 0) > cutoff:
                        new_entries.append(e)
                    else:
                        # Token becslés törlése
                        token_key = f'entry_{e.get("id", "")}'
                        if token_key in self.token_estimates:
                            del self.token_estimates[token_key]
                self.entries = new_entries
                self._debug(f"prune_old_entries: {len(new_entries)} bejegyzés maradt")
        except Exception as e:
            self._debug(f"prune_old_entries hiba: {e}")
    
    def cleanup_old(self, max_age_seconds: int = 3600):
        """Régi bejegyzések törlése (alias)"""
        self.prune_old_entries(max_age_seconds)
    
    # ========== MODUL KEZELÉS ==========
    
    def get_active_modules(self) -> List[str]:
        """Aktív modulok listázása (amelyek írtak már)"""
        try:
            with self.lock:
                modules = set()
                for e in self.entries:
                    if e.get('module'):
                        modules.add(e['module'])
                for mod in self.notepads.keys():
                    modules.add(mod)
                for mod in self.drafts.keys():
                    modules.add(mod)
                return sorted(list(modules))
        except Exception as e:
            self._debug(f"get_active_modules hiba: {e}")
            return []
    
    # ========== ÖSSZEFOGLALÓ ==========
    
    def get_summary(self) -> Dict:
        """Összefoglaló a memória állapotáról"""
        try:
            with self.lock:
                active_modules = set()
                for e in self.entries:
                    if e.get('module'):
                        active_modules.add(e['module'])
                
                return {
                    'state': dict(self.state),
                    'entry_count': len(self.entries),
                    'modules': list(active_modules),
                    'notepads': {mod: len(notes) for mod, notes in self.notepads.items()},
                    'drafts': {mod: len(d) for mod, d in self.drafts.items()},
                    'last_entry': self.read_last(),
                    'token_estimate': self.get_token_estimate(),
                    'token_breakdown': self.get_token_breakdown(),
                    'debug_log_count': len(self._debug_log)
                }
        except Exception as e:
            self._debug(f"get_summary hiba: {e}")
            return {
                'state': {},
                'entry_count': 0,
                'modules': [],
                'error': str(e)
            }
    
    def get_debug_log(self) -> List[str]:
        """Debug napló lekérése"""
        return list(self._debug_log)
    
    def clear(self):
        """Teljes memória törlése (vészhelyzet)"""
        with self.lock:
            self.entries.clear()
            self.notepads.clear()
            self.drafts.clear()
            self.token_estimates.clear()
            self._debug("Memória teljesen törölve")
    
    # ========== BELSŐ SEGÉDFÜGGVÉNYEK ==========
    
    def _log_entry(self, entry_type, data):
        """Belső események naplózása"""
        try:
            self.write('scratchpad', data, entry_type)
        except Exception as e:
            self._debug(f"_log_entry hiba: {e}")
    
    def _make_serializable(self, obj: Any) -> Any:
        """Objektum átalakítása tárolható formátumba"""
        if obj is None:
            return None
        if isinstance(obj, (str, int, float, bool)):
            return obj
        if isinstance(obj, (list, tuple)):
            return [self._make_serializable(item) for item in obj]
        if isinstance(obj, dict):
            return {str(k): self._make_serializable(v) for k, v in obj.items()}
        try:
            json.dumps(obj)
            return obj
        except:
            return str(obj)
    
    def _debug(self, message: str):
        """Debug üzenet naplózása"""
        timestamp = datetime.now().isoformat()
        self._debug_log.append(f"[{timestamp}] {message}")
        print(f"📝 Scratchpad debug: {message}")


# Teszt
if __name__ == "__main__":
    s = Scratchpad()
    
    print("\n--- Teszt írás ---")
    s.write('king', 'Thinking...', 'internal_monologue')
    s.write('scribe', {'intent': 'greeting', 'confidence': 0.9}, 'intent')
    s.write('jester', 'Watching...', 'observation')
    
    print("Utolsó 5 bejegyzés:")
    for entry in s.read(limit=5):
        print(f"  [{entry['module']}] {entry['type']}: {entry['content']}")
    
    print("\n--- Jegyzet teszt ---")
    s.write_note('king', 'last_mood', 'curious')
    s.write_note('jester', 'last_warning', 'none', ttl=60)
    print(f"King mood: {s.read_note('king', 'last_mood')}")
    print(f"Jester warning: {s.read_note('jester', 'last_warning')}")
    
    print("\n--- Rejtett piszkozat ---")
    s.write_draft('king', 'I wonder what Grumpy is thinking...')
    drafts = s.read_drafts('king')
    print(f"Piszkozatok: {len(drafts)}")
    
    print("\n--- Állapot ---")
    s.set_state('current_mood', 'happy', 'king')
    print(f"Állapot: {s.get_state('current_mood')}")
    
    print("\n--- Token statisztika ---")
    print(f"Összes token: {s.get_token_estimate()}")
    print(f"Részletezés: {s.get_token_breakdown()}")
    
    print("\n--- Aktív modulok ---")
    print(f"Modulok: {s.get_active_modules()}")
    
    print("\n--- Összefoglaló ---")
    summary = s.get_summary()
    for k, v in summary.items():
        if k not in ['last_entry', 'state']:
            print(f"  {k}: {v}")