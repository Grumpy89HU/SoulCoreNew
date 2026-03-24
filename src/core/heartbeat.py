"""
Heartbeat - A Vár szíve.

KOMMUNIKÁCIÓS PROTOKOLL:
- A Heartbeat HALLJA a buszon az eseményeket
- Proaktív gondolatok küldése a buszon keresztül (broadcast)
- JSON formátumú üzenetek a rendszer többi része felé

Feladata:
1. Rendszeres "PING" küldése (időérzék)
2. Időalapú események generálása
3. Inaktivitás detektálás
4. Proaktív gondolatok indítása (emlékeztetők, érdeklődés)
5. A rendszer időtudatosságának fenntartása
"""

import time
import threading
import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable, List
import re


class Heartbeat:
    """
    A Heartbeat egy külön szálon futó ütemező.
    Nem fogyaszt token-t, nem blokkol.
    
    KOMMUNIKÁCIÓ:
    - Proaktív üzeneteket küld a buszon (broadcast)
    - Hallja a buszon a felhasználói interakciókat
    """
    
    def __init__(self, scratchpad, message_bus=None, config: Dict = None):
        self.scratchpad = scratchpad
        self.bus = message_bus  # Opcionális - broadcast módhoz
        self.name = "heartbeat"
        self.config = config or {}
        
        # Alapértelmezett konfiguráció
        default_config = {
            'interval': 1.0,
            'proactive': {
                'enabled': True,
                'min_idle_hours': 2,
                'max_idle_hours': 8,
                'once_per_day': True,
                'reminders': True,
                'check_interval': 300,
                'chance': 0.3,
                'topics': []
            },
            'events': {
                'status_check': 5.0,
                'idle_check': 60.0,
                'proactive_thought': 300.0,
                'reminder_check': 3600.0,
                'deep_thought': 3600.0,
                'cleanup': 7200.0,
                'state_snapshot': 300.0
            }
        }
        
        # Konfiguráció összefésülése
        for key, value in default_config.items():
            if key not in self.config:
                self.config[key] = value
            elif isinstance(value, dict) and key in self.config:
                for subkey, subvalue in value.items():
                    if subkey not in self.config[key]:
                        self.config[key][subkey] = subvalue
        
        # Szálkezelés
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        
        # Időzítők
        self.interval = self.config.get('interval', 1.0)
        self.last_beat = time.time()
        self.start_time = time.time()
        
        # Események
        self.events = self.config.get('events', {})
        
        # Utolsó futási idők
        self.last_run = {event: 0 for event in self.events}
        
        # Állapot
        self.state = {
            'beats': 0,
            'uptime_seconds': 0,
            'uptime_formatted': '0s',
            'last_interaction': None,
            'idle_since': None,
            'idle_seconds': 0,
            'idle_formatted': '0s',
            'proactive_count': 0,
            'reminder_count': 0,
            'last_proactive': 0,
            'proactive_today': False,
            'last_proactive_date': None,
            'reminders_sent': [],
            'current_time': datetime.now().isoformat(),
            'time_of_day': self._get_time_of_day()
        }
        
        # Ha van busz, feliratkozunk
        if self.bus:
            self.bus.subscribe(self.name, self._on_message)
        
        print("💓 Heartbeat: Szív indul. Dobogok.")
        if self.bus:
            print("💓 Heartbeat: Broadcast módban működöm, hallgatom az eseményeket.")
    
    # ========== BUSZ KOMMUNIKÁCIÓ ==========
    
    def _on_message(self, message: Dict):
        """
        Hallja a buszon érkező üzeneteket.
        Felhasználói interakciók regisztrálása.
        """
        header = message.get('header', {})
        payload = message.get('payload', {})
        
        # Felhasználói interakció regisztrálása
        if payload.get('type') == 'royal_decree':
            self.register_interaction()
        
        # Emlékeztető létrehozása (ha van)
        if payload.get('type') == 'create_reminder':
            text = payload.get('text', '')
            language = payload.get('language', 'en')
            self.create_reminder(text, 'system', language)
    
    def _send_proactive(self, data: Dict):
        """
        Proaktív üzenet küldése a buszon.
        """
        if not self.bus:
            return
        
        trace_id = str(uuid.uuid4())
        
        message = {
            "header": {
                "trace_id": trace_id,
                "timestamp": time.time(),
                "sender": self.name,
                "target": "kernel",
                "broadcast": True
            },
            "payload": {
                "type": "proactive_message",
                "subtype": data.get('type', 'interest'),
                "topic": data.get('topic', ''),
                "idle_hours": data.get('idle_hours', 0),
                "idle_formatted": data.get('idle_formatted', ''),
                "reminder_id": data.get('reminder_id', ''),
                "note": data.get('note', ''),
                "language": data.get('language', 'en')
            }
        }
        
        self.bus.broadcast(message)
        
        # Állapot frissítés
        self.state['proactive_count'] += 1
        self.state['last_proactive'] = time.time()
        self.state['last_proactive_date'] = datetime.now().date()
        self.state['proactive_today'] = True
        
        print(f"💓 Proaktív üzenet küldve: {data.get('type')} - {data.get('topic')}")
    
    # ========== FŐ CIKLUS ==========
    
    def start(self):
        """Heartbeat indítása külön szálon"""
        with self.lock:
            if self.running:
                return
            
            self.running = True
            self.start_time = time.time()
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
            
            self.scratchpad.set_state('heartbeat_status', 'running', self.name)
            print("💓 Heartbeat: Dobogok...")
    
    def stop(self):
        """Heartbeat leállítása"""
        with self.lock:
            self.running = False
        
        if self.thread:
            self.thread.join(timeout=2.0)
        
        self.scratchpad.set_state('heartbeat_status', 'stopped', self.name)
        print("💓 Heartbeat: Csend.")
    
    def _run(self):
        """Fő ciklus (külön szálon fut)"""
        while self.running:
            try:
                self._beat()
                time.sleep(self.interval)
            except Exception as e:
                print(f"💓 Heartbeat hiba: {e}")
                time.sleep(self.interval * 2)
    
    def _beat(self):
        """Egy szívdobbanás"""
        now = time.time()
        self.last_beat = now
        self.state['beats'] += 1
        self.state['uptime_seconds'] = int(now - self.start_time)
        self.state['uptime_formatted'] = self._format_uptime(self.state['uptime_seconds'])
        self.state['current_time'] = datetime.now().isoformat()
        self.state['time_of_day'] = self._get_time_of_day()
        
        # Uptime frissítése
        self.scratchpad.set_state('uptime_seconds', self.state['uptime_seconds'], self.name)
        self.scratchpad.set_state('uptime_formatted', self.state['uptime_formatted'], self.name)
        
        # Utolsó interakció ellenőrzése
        last_interaction = self.scratchpad.get_state('last_interaction')
        if last_interaction is not None:
            self.state['last_interaction'] = last_interaction
            idle = now - last_interaction
            self.state['idle_seconds'] = int(idle)
            self.state['idle_formatted'] = self._format_uptime(self.state['idle_seconds'])
            
            if idle > 60 and not self.state['idle_since']:
                self.state['idle_since'] = last_interaction
        else:
            self.state['last_interaction'] = None
            self.state['idle_seconds'] = 0
            self.state['idle_formatted'] = '0s'
        
        # Események futtatása
        self._run_events(now)
    
    def _run_events(self, now: float):
        """Időzített események futtatása"""
        for event, interval in self.events.items():
            if now - self.last_run[event] >= interval:
                try:
                    self._handle_event(event, now)
                except Exception as e:
                    print(f"💓 Heartbeat event error {event}: {e}")
                self.last_run[event] = now
    
    def _handle_event(self, event: str, now: float):
        """Egy esemény kezelése"""
        
        if event == 'status_check':
            status = {
                'uptime': self.state['uptime_seconds'],
                'uptime_formatted': self.state['uptime_formatted'],
                'idle': self.state['idle_seconds'],
                'idle_formatted': self.state['idle_formatted'],
                'beats': self.state['beats'],
                'time_of_day': self.state['time_of_day']
            }
            self.scratchpad.write(self.name, status, 'heartbeat_status')
            
        elif event == 'idle_check':
            if self.state['idle_seconds'] > 300:
                self.scratchpad.write(self.name, 
                    {'idle_minutes': self.state['idle_seconds'] // 60,
                     'idle_formatted': self.state['idle_formatted']}, 
                    'long_idle'
                )
        
        elif event == 'proactive_thought':
            if self.config.get('proactive', {}).get('enabled', True):
                self._check_interest_proactive()
        
        elif event == 'reminder_check':
            if self.config.get('proactive', {}).get('reminders', True):
                self._check_reminders()
        
        elif event == 'deep_thought':
            self.scratchpad.write(self.name, 
                {'type': 'deep_thought', 'time': now}, 
                'heartbeat_deep'
            )
        
        elif event == 'cleanup':
            self.scratchpad.cleanup_old(max_age_seconds=3600)
        
        elif event == 'state_snapshot':
            self._save_state_snapshot()
    
    # ========== PROAKTÍV ÉRDEKLŐDÉS ==========
    
    def _check_interest_proactive(self):
        """
        Érdeklődés típusú proaktív gondolat.
        """
        if not self.bus:
            return
        
        pro_config = self.config.get('proactive', {})
        
        # 1. Inaktivitás ellenőrzés
        idle_hours = self.state['idle_seconds'] / 3600
        min_hours = pro_config.get('min_idle_hours', 2)
        max_hours = pro_config.get('max_idle_hours', 8)
        
        if idle_hours < min_hours or idle_hours > max_hours:
            return
        
        # 2. Napi egyszeri korlátozás
        if pro_config.get('once_per_day', True):
            today = datetime.now().date()
            last_date = self.state.get('last_proactive_date')
            if last_date == today:
                return
        
        # 3. Véletlenszerű esély
        chance = pro_config.get('chance', 0.3)
        if random.random() > chance:
            return
        
        # 4. Utolsó téma lekérése
        last_topic = self._get_last_topic()
        if not last_topic:
            return
        
        # 5. Téma szűrés
        allowed_topics = pro_config.get('topics', [])
        if allowed_topics and last_topic not in allowed_topics:
            return
        
        # Proaktív megszólalás
        self._send_proactive({
            'type': 'interest',
            'topic': last_topic,
            'idle_hours': round(idle_hours, 1),
            'idle_formatted': self.state['idle_formatted']
        })
    
    def _check_reminders(self):
        """
        Emlékeztetők ellenőrzése.
        """
        if not self.bus:
            return
        
        notes = self.scratchpad.read_all_notes()
        today = datetime.now().strftime("%Y%m%d")
        user_language = self.scratchpad.get_state('user_language', 'en')
        
        for module, notes_dict in notes.items():
            if not isinstance(notes_dict, dict):
                continue
                
            for key, note in notes_dict.items():
                if not key or not isinstance(key, str):
                    continue
                    
                if not key.startswith('reminder_'):
                    continue
                
                try:
                    parts = key.split('_')
                    if len(parts) < 2:
                        continue
                    
                    date_str = parts[1]
                    reminder_id = f"{module}_{key}"
                    
                    if date_str == today and reminder_id not in self.state['reminders_sent']:
                        topic = parts[2] if len(parts) > 2 else 'event'
                        note_text = ''
                        if isinstance(note, dict):
                            note_text = note.get('text', '')
                        
                        self._send_proactive({
                            'type': 'reminder',
                            'topic': topic,
                            'note': note_text,
                            'reminder_id': reminder_id,
                            'language': user_language
                        })
                        
                        self.state['reminders_sent'].append(reminder_id)
                        self.state['reminder_count'] += 1
                        
                except Exception as e:
                    print(f"💓 Hiba az emlékeztető feldolgozásában: {e}")
    
    def _get_last_topic(self) -> str:
        """Utolsó beszélgetési téma lekérése"""
        last_intent = self.scratchpad.read_last('intent')
        if last_intent:
            content = last_intent.get('content', {})
            if isinstance(content, dict):
                intent = content.get('payload', {}).get('intent', {})
                return intent.get('class', '')
        return ''
    
    # ========== EMLÉKEZTETŐ LÉTREHOZÁS ==========
    
    def create_reminder(self, text: str, source: str = "user", language: str = "en"):
        """
        Emlékeztető létrehozása.
        """
        date = self._extract_date(text, language)
        if not date:
            return None
        
        topic = self._extract_topic(text)
        if not topic:
            topic = "reminder"
        
        date_str = date.strftime("%Y%m%d")
        key = f"reminder_{date_str}_{topic}"
        
        self.scratchpad.write_note('heartbeat', key, {
            'text': text,
            'date': date_str,
            'date_iso': date.isoformat(),
            'topic': topic,
            'source': source,
            'language': language,
            'created': time.time()
        })
        
        print(f"💓 Emlékeztető létrehozva: {key}")
        return key
    
    def _extract_date(self, text: str, language: str = "en"):
        """Dátum kinyerése szövegből"""
        text_lower = text.lower()
        
        # Egyszerű minták (nyelvfüggetlen)
        patterns = [
            (r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})', self._parse_absolute),
            (r'(\d{1,2})[-/](\d{1,2})', self._parse_short),
            (r'(tomorrow|holnap)', self._parse_relative),
            (r'(today|ma)', self._parse_relative),
        ]
        
        # Nyelvfüggő minták
        if language == 'hu':
            patterns.extend([
                (r'(hétfő|kedd|szerda|csütörtök|péntek|szombat|vasárnap)', self._parse_weekday_hu),
                (r'(\d+) (óra|nap|hét) múlva', self._parse_in_duration_hu)
            ])
        else:
            patterns.extend([
                (r'(monday|tuesday|wednesday|thursday|friday|saturday|sunday)', self._parse_weekday_en),
                (r'in (\d+) (hour|day|week)s?', self._parse_in_duration)
            ])
        
        for pattern, handler in patterns:
            match = re.search(pattern, text_lower)
            if match:
                return handler(match)
        
        return None
    
    def _parse_weekday_en(self, match):
        day_map = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2,
            'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6
        }
        day_name = match.group(1)
        target_weekday = day_map.get(day_name)
        
        if target_weekday is None:
            return None
        
        today = datetime.now()
        current_weekday = today.weekday()
        days_ahead = target_weekday - current_weekday
        if days_ahead <= 0:
            days_ahead += 7
            
        return today + timedelta(days=days_ahead)
    
    def _parse_weekday_hu(self, match):
        day_map = {
            'hétfő': 0, 'kedd': 1, 'szerda': 2,
            'csütörtök': 3, 'péntek': 4, 'szombat': 5, 'vasárnap': 6
        }
        day_name = match.group(1)
        target_weekday = day_map.get(day_name)
        
        if target_weekday is None:
            return None
        
        today = datetime.now()
        current_weekday = today.weekday()
        days_ahead = target_weekday - current_weekday
        if days_ahead <= 0:
            days_ahead += 7
            
        return today + timedelta(days=days_ahead)
    
    def _parse_relative(self, match):
        word = match.group(1)
        today = datetime.now()
        
        if word in ['today', 'ma']:
            return today
        elif word in ['tomorrow', 'holnap']:
            return today + timedelta(days=1)
        
        return None
    
    def _parse_absolute(self, match):
        try:
            date_str = match.group(1)
            for fmt in ["%Y-%m-%d", "%Y/%m/%d"]:
                try:
                    return datetime.strptime(date_str, fmt)
                except:
                    continue
        except:
            pass
        return None
    
    def _parse_short(self, match):
        try:
            month, day = match.groups()
            year = datetime.now().year
            date = datetime(year, int(month), int(day))
            if date < datetime.now():
                date = datetime(year + 1, int(month), int(day))
            return date
        except:
            return None
    
    def _parse_in_duration(self, match):
        try:
            amount = int(match.group(1))
            unit = match.group(2)
            today = datetime.now()
            
            if unit.startswith('hour'):
                return today + timedelta(hours=amount)
            elif unit.startswith('day'):
                return today + timedelta(days=amount)
            elif unit.startswith('week'):
                return today + timedelta(weeks=amount)
        except:
            pass
        return None
    
    def _parse_in_duration_hu(self, match):
        try:
            amount = int(match.group(1))
            unit = match.group(2)
            today = datetime.now()
            
            if unit in ['óra', 'órát']:
                return today + timedelta(hours=amount)
            elif unit in ['nap', 'napot']:
                return today + timedelta(days=amount)
            elif unit in ['hét', 'hetet']:
                return today + timedelta(weeks=amount)
        except:
            pass
        return None
    
    def _extract_topic(self, text: str) -> str:
        """Téma kinyerése"""
        words = text.split()
        topic_words = []
        
        skip_words = ['megyek', 'vásárol', 'csinál', 'hoz', 'visz', 'lesz', 'van',
                      'go', 'buy', 'do', 'bring', 'take', 'will', 'is', 'be']
        
        for word in words:
            word_lower = word.lower()
            if any(p in word_lower for p in skip_words):
                continue
            if len(word) > 3 and word_lower not in skip_words:
                topic_words.append(word_lower)
        
        if topic_words:
            return '_'.join(topic_words[:2])
        return "reminder"
    
    # ========== INTERAKCIÓK ==========
    
    def register_interaction(self):
        """Felhasználói interakció regisztrálása"""
        now = time.time()
        self.scratchpad.set_state('last_interaction', now, self.name)
        self.state['last_interaction'] = now
        self.state['idle_since'] = None
        self.state['idle_seconds'] = 0
        self.state['idle_formatted'] = '0s'
    
    # ========== ÁLLAPOT SNAPSHOT ==========
    
    def _save_state_snapshot(self):
        """Állapot snapshot mentése"""
        snapshot = {
            'timestamp': time.time(),
            'uptime': self.state.get('uptime_seconds', 0),
            'last_interaction': self.state.get('last_interaction', 0),
            'idle': self.state.get('idle_seconds', 0),
            'proactive_count': self.state.get('proactive_count', 0),
            'reminder_count': self.state.get('reminder_count', 0),
            'time_of_day': self.state.get('time_of_day', 'unknown'),
            'beats': self.state.get('beats', 0)
        }
        
        snapshot_key = f"snapshot_{int(time.time())}"
        self.scratchpad.write_note(self.name, snapshot_key, snapshot)
        self._cleanup_old_snapshots(10)
    
    def _cleanup_old_snapshots(self, keep: int = 10):
        """Régi snapshotok törlése"""
        try:
            notes = self.scratchpad.read_all_notes(self.name)
            if not notes:
                return
            
            snapshots = []
            for k, v in notes.items():
                if k and k.startswith('snapshot_') and isinstance(v, dict):
                    snapshots.append((k, v.get('timestamp', 0)))
            
            snapshots.sort(key=lambda x: x[1])
            
            for key, _ in snapshots[:-keep]:
                self.scratchpad.write_note(self.name, key, None)
        except Exception as e:
            print(f"💓 Snapshot cleanup hiba: {e}")
    
    # ========== IDŐ SEGÉDFÜGGVÉNYEK ==========
    
    def _get_time_of_day(self) -> str:
        hour = time.localtime().tm_hour
        if 5 <= hour < 9:
            return "morning"
        elif 9 <= hour < 12:
            return "late_morning"
        elif 12 <= hour < 17:
            return "afternoon"
        elif 17 <= hour < 21:
            return "evening"
        else:
            return "night"
    
    def _format_uptime(self, seconds: int) -> str:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hours > 0:
            return f"{hours}h {minutes}m"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"
    
    # ========== LEKÉRDEZÉSEK ==========
    
    def get_state(self) -> Dict:
        return {
            'beats': self.state['beats'],
            'uptime': self.state['uptime_formatted'],
            'uptime_seconds': self.state['uptime_seconds'],
            'idle': self.state['idle_formatted'],
            'idle_seconds': self.state['idle_seconds'],
            'proactive_count': self.state['proactive_count'],
            'reminder_count': self.state['reminder_count'],
            'proactive_today': self.state['proactive_today'],
            'time_of_day': self.state['time_of_day'],
            'current_time': self.state['current_time'],
            'reminders_sent': len(self.state['reminders_sent']),
            'running': self.running
        }


# Teszt
if __name__ == "__main__":
    from scratchpad import Scratchpad
    import time
    
    s = Scratchpad()
    
    class MockBus:
        def subscribe(self, name, callback):
            self.callback = callback
        
        def broadcast(self, message):
            print(f"📡 Broadcast: {message.get('payload', {}).get('type')}")
    
    bus = MockBus()
    
    hb = Heartbeat(s, bus)
    hb.start()
    
    # Emlékeztető teszt
    hb.create_reminder("Kedden megyek vásárolni", language="hu")
    
    time.sleep(2)
    
    print("\n--- Heartbeat állapot ---")
    state = hb.get_state()
    for k, v in state.items():
        print(f"{k}: {v}")
    
    hb.stop()