"""
Heartbeat - A Vár szíve.

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
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable, List
import re

class Heartbeat:
    """
    A Heartbeat egy külön szálon futó ütemező.
    Nem fogyaszt token-t, nem blokkol.
    
    Proaktív működés:
    - Emlékeztetők: ha a felhasználó mondott egy időpontot (pl. "kedden megyek...")
    - Érdeklődés: ha hosszabb ideje csend van, de volt értelmes téma
    - Soha nem zaklat: beállítható gyakoriság, csak naponta egyszer
    """
    
    def __init__(self, scratchpad, orchestrator=None, config: Dict = None):
        self.scratchpad = scratchpad
        self.orchestrator = orchestrator  # hogy tudjon packet-et küldeni
        self.name = "heartbeat"
        self.config = config or {}
        
        # Alapértelmezett konfiguráció
        default_config = {
            'interval': 1.0,
            'proactive': {
                'enabled': True,
                'min_idle_hours': 2,      # Minimum 2 óra csend után
                'max_idle_hours': 8,      # Maximum 8 óra után már ne
                'once_per_day': True,      # Csak napi egyszer
                'reminders': True,         # Emlékeztetők kezelése
                'check_interval': 300,     # 5 percenként ellenőrizze
                'chance': 0.3,             # 30% esély (ha több feltétel is teljesül)
                'topics': []                # Ha üres, bármiről kérdezhet
            },
            'events': {
                'status_check': 5.0,        # 5 másodperc
                'idle_check': 60.0,          # 1 perc
                'proactive_thought': 300.0,  # 5 perc
                'reminder_check': 3600.0,    # 1 óra
                'deep_thought': 3600.0,      # 1 óra
                'cleanup': 7200.0,            # 2 óra
                'state_snapshot': 300.0       # 5 perc (állapot mentés)
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
        
        # Események (konfig alapján)
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
            'last_proactive': 0,           # Mikor volt utoljára proaktív megszólalás
            'proactive_today': False,       # Volt-e már ma
            'last_proactive_date': None,    # Melyik nap volt utoljára
            'reminders_sent': [],            # Elküldött emlékeztetők ID-i
            'current_time': datetime.now().isoformat(),
            'time_of_day': self._get_time_of_day()
        }
        
        # Időpont minták felismeréséhez (többnyelvű támogatás)
        self.time_patterns = {
            'en': [
                (r'(monday|tuesday|wednesday|thursday|friday|saturday|sunday)', self._parse_weekday_en),
                (r'(tomorrow|today|now)', self._parse_relative),
                (r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})', self._parse_absolute),  # 2025-03-11
                (r'(\d{1,2})[/-](\d{1,2})', self._parse_short),               # 03/11
                (r'in (\d+) (hour|day|week)s?', self._parse_in_duration)
            ],
            'hu': [
                (r'(hétfő|kedd|szerda|csütörtök|péntek|szombat|vasárnap)', self._parse_weekday_hu),
                (r'(holnap|holnapután|ma|most)', self._parse_relative),
                (r'(\d{4}\.\s*\d{1,2}\.\s*\d{1,2})', self._parse_absolute_hu),  # 2025. 03. 11
                (r'(\d{1,2})[-/](\d{1,2})', self._parse_short),                 # 03/11
                (r'(\d+) (óra|nap|hét) múlva', self._parse_in_duration_hu)
            ]
        }
        
        print("💓 Heartbeat: Szív indul. Dobogok.")
    
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
            self.scratchpad.set_state('start_time', self.start_time, self.name)
            
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
        
        # Uptime frissítése a scratchpadben
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
                self.scratchpad.write(self.name, 
                    {'idle_seconds': int(idle), 'idle_formatted': self.state['idle_formatted']}, 
                    'idle_start'
                )
        else:
            # Ha nincs last_interaction, akkor nullázzuk
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
            # Rendszer státusz ellenőrzés
            status = {
                'uptime': self.state['uptime_seconds'],
                'uptime_formatted': self.state['uptime_formatted'],
                'idle': self.state['idle_seconds'],
                'idle_formatted': self.state['idle_formatted'],
                'beats': self.state['beats'],
                'time_of_day': self.state['time_of_day'],
                'king_status': self.scratchpad.get_state('king_status', 'unknown'),
                'jester_status': self.scratchpad.get_state('jester_status', 'unknown'),
                'orchestrator_status': self.scratchpad.get_state('orchestrator_status', 'unknown'),
            }
            self.scratchpad.write(self.name, status, 'heartbeat_status')
            
        elif event == 'idle_check':
            # Inaktivitás ellenőrzés (5 perc után)
            if self.state['idle_seconds'] > 300:  # 5 perc
                self.scratchpad.write(self.name, 
                    {'idle_minutes': self.state['idle_seconds'] // 60,
                     'idle_formatted': self.state['idle_formatted']}, 
                    'long_idle'
                )
        
        elif event == 'proactive_thought':
            # Érdeklődés típusú proaktív gondolat
            if self.config.get('proactive', {}).get('enabled', True):
                self._check_interest_proactive()
        
        elif event == 'reminder_check':
            # Emlékeztető típusú proaktív gondolat
            if self.config.get('proactive', {}).get('reminders', True):
                self._check_reminders()
        
        elif event == 'deep_thought':
            # Mély gondolat (ritkán) - rendszer optimalizálás
            self.scratchpad.write(self.name, 
                {'type': 'deep_thought', 'time': now}, 
                'heartbeat_deep'
            )
        
        elif event == 'cleanup':
            # Takarítás (régi trace-ek törlése)
            self.scratchpad.cleanup_old(max_age_seconds=3600)
        
        elif event == 'state_snapshot':
            # Állapot snapshot mentése (XVI. fejezet)
            self._save_state_snapshot()
    
    def _save_state_snapshot(self):
        """
        Állapot snapshot mentése (XVI. fejezet - Lélek-lenyomat)
        5 percenként menti a rendszer állapotát.
        """
        # Biztonságos lekérés - minden érték legyen string vagy szám, ne None
        king_status = self.scratchpad.get_state('king_status', 'unknown')
        if king_status is None:
            king_status = 'unknown'
        
        jester_status = self.scratchpad.get_state('jester_status', 'unknown')
        if jester_status is None:
            jester_status = 'unknown'
        
        orchestrator_status = self.scratchpad.get_state('orchestrator_status', 'unknown')
        if orchestrator_status is None:
            orchestrator_status = 'unknown'
        
        active_traces = self.scratchpad.get_state('active_traces', 0)
        if active_traces is None:
            active_traces = 0
        
        last_interaction = self.state.get('last_interaction')
        if last_interaction is None:
            last_interaction = 0
        
        snapshot = {
            'timestamp': time.time(),
            'uptime': self.state.get('uptime_seconds', 0),
            'last_interaction': last_interaction,
            'idle': self.state.get('idle_seconds', 0),
            'proactive_count': self.state.get('proactive_count', 0),
            'reminder_count': self.state.get('reminder_count', 0),
            'king_status': king_status,
            'jester_status': jester_status,
            'orchestrator_status': orchestrator_status,
            'active_traces': active_traces,
            'time_of_day': self.state.get('time_of_day', 'unknown'),
            'beats': self.state.get('beats', 0)
        }
        
        # Snapshot mentése
        snapshot_key = f"snapshot_{int(time.time())}"
        self.scratchpad.write_note(self.name, snapshot_key, snapshot)
        
        # Csak az utolsó 10 snapshotot tartjuk meg
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
    
    # --- PROAKTÍV ÉRDEKLŐDÉS (nem zaklatás!) ---
    
    def _check_interest_proactive(self):
        """
        Érdeklődés típusú proaktív gondolat.
        Feltételek (mindegyiknek teljesülnie kell):
        - Van kapcsolat az orchestratorral
        - Inaktivitás a konfigban megadott minimum és maximum között
        - Még nem volt ma proaktív megszólalás (ha once_per_day = true)
        - Van értelmes utolsó téma
        """
        if not self.orchestrator:
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
            
            # Ellenőrizzük, hogy tényleg volt-e ma
            if last_date and (today - last_date).days == 0:
                return
        
        # 3. Véletlenszerű esély (hogy ne legyen kiszámítható)
        chance = pro_config.get('chance', 0.3)
        if random.random() > chance:
            return
        
        # 4. Utolsó téma lekérése
        last_topic = self._get_last_topic()
        if not last_topic or last_topic == 'unknown':
            return
        
        # 5. Téma szűrés (ha vannak engedélyezett témák)
        allowed_topics = pro_config.get('topics', [])
        if allowed_topics and last_topic not in allowed_topics:
            return
        
        # MINDEN FELTÉTEL TELJESÜLT -> proaktív megszólalás
        self._send_proactive({
            'type': 'interest',
            'topic': last_topic,
            'idle_hours': round(idle_hours, 1),
            'idle_formatted': self.state['idle_formatted']
        })
    
    def _check_reminders(self):
        """
        Emlékeztetők ellenőrzése.
        Végignézi a scratchpad összes jegyzetét, és ha talál olyat,
        ami "reminder_" prefixű, és a dátum ma van, elküldi.
        """
        if not self.orchestrator:
            return
        
        notes = self.scratchpad.read_all_notes()
        today = datetime.now().strftime("%Y%m%d")
        user_language = self.scratchpad.get_state('user_language', 'en')
        if user_language is None:
            user_language = 'en'
        
        for module, notes_dict in notes.items():
            if not isinstance(notes_dict, dict):
                continue
                
            for key, note in notes_dict.items():
                if not key or not isinstance(key, str):
                    continue
                    
                # Csak az emlékeztetőket nézzük
                if not key.startswith('reminder_'):
                    continue
                
                # Formátum: reminder_YYYYMMDD_téma
                try:
                    parts = key.split('_')
                    if len(parts) < 2:
                        continue
                    
                    date_str = parts[1]
                    reminder_id = f"{module}_{key}"
                    
                    # Ha ma van az esemény, ÉS még nem küldtük el
                    if date_str == today and reminder_id not in self.state['reminders_sent']:
                        topic = parts[2] if len(parts) > 2 else 'event'
                        note_text = ''
                        if isinstance(note, dict):
                            note_text = note.get('value', '')
                        
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
                return content.get('intent', {}).get('class', '')
        return ''
    
    def _send_proactive(self, data: Dict):
        """Proaktív üzenet küldése KVK formátumban"""
        if not self.orchestrator:
            return
        
        now = datetime.now()
        user_language = data.get('language', self.scratchpad.get_state('user_language', 'en'))
        if user_language is None:
            user_language = 'en'
        
        # Alap KVK csomag
        packet = {
            'INTENT': 'PROACTIVE',
            'TYPE': data.get('type', 'interest'),
            'TIME': now.strftime("%H:%M"),
            'DATE': now.strftime("%Y-%m-%d"),
            'LANGUAGE': user_language
        }
        
        # Üzenet összeállítása típus alapján
        if data.get('type') == 'reminder':
            packet['MESSAGE'] = f"reminder:{data.get('topic', 'event')}:{data.get('note', '')}"
            packet['TOPIC'] = data.get('topic', '')
            packet['REMINDER_ID'] = data.get('reminder_id', '')
            
        else:  # interest
            topic = data.get('topic', 'life')
            hours = data.get('idle_hours', 2)
            idle_formatted = data.get('idle_formatted', f"{hours}h")
            
            packet['MESSAGE'] = f"interest:{topic}:{idle_formatted}"
            packet['TOPIC'] = topic
            packet['IDLE_HOURS'] = str(hours)
            packet['IDLE_FORMATTED'] = idle_formatted
        
        # KVK csomag készítése és elküldése
        if hasattr(self.orchestrator, 'build_kvk_packet'):
            kvk = self.orchestrator.build_kvk_packet(packet)
            self.scratchpad.write(self.name, 
                {
                    'proactive': kvk, 
                    'type': data.get('type'),
                    'topic': data.get('topic', '')
                }, 
                'proactive_trigger'
            )
            
            # Állapot frissítés
            self.state['proactive_count'] += 1
            self.state['last_proactive'] = time.time()
            self.state['last_proactive_date'] = datetime.now().date()
            self.state['proactive_today'] = True
    
    # --- EMLÉKEZTETŐ LÉTREHOZÁS (más modulok hívják) ---
    
    def create_reminder(self, text: str, source: str = "user", language: str = "en"):
        """
        Emlékeztető létrehozása egy szövegből.
        Kinyeri az időpontot és a témát.
        Példa: "kedden megyek videókártyát venni" -> reminder_20250311_videokartya
        """
        date = self._extract_date(text, language)
        if not date:
            return None
        
        # Téma kinyerése (a dátum utáni rész)
        topic = self._extract_topic(text)
        if not topic:
            topic = "reminder"
        
        # Emlékeztető kulcs: reminder_YYYYMMDD_téma
        date_str = date.strftime("%Y%m%d")
        key = f"reminder_{date_str}_{topic}"
        
        # Mentés a scratchpadbe
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
        """Dátum kinyerése szövegből a megadott nyelv alapján"""
        text_lower = text.lower()
        patterns = self.time_patterns.get(language, self.time_patterns['en'])
        
        for pattern, handler in patterns:
            match = re.search(pattern, text_lower)
            if match:
                return handler(match)
        
        return None
    
    def _parse_weekday_en(self, match):
        """Angol hétnapok feldolgozása"""
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
        """Magyar hétnapok feldolgozása"""
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
        """Relatív időpontok (ma, holnap, most)"""
        word = match.group(1)
        today = datetime.now()
        
        if word in ['today', 'ma', 'now', 'most']:
            return today
        elif word in ['tomorrow', 'holnap']:
            return today + timedelta(days=1)
        elif word in ['holnapután']:
            return today + timedelta(days=2)
        
        return None
    
    def _parse_absolute(self, match):
        """Abszolút dátum: 2025-03-11 vagy 2025/03/11"""
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
    
    def _parse_absolute_hu(self, match):
        """Magyar abszolút dátum: 2025. 03. 11"""
        try:
            date_str = match.group(1)
            # Eltávolítjuk a pontokat és szóközöket
            cleaned = re.sub(r'[.\s]+', '-', date_str)
            return datetime.strptime(cleaned, "%Y-%m-%d")
        except:
            return None
    
    def _parse_short(self, match):
        """Rövid dátum: 03/11"""
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
        """Angol: in 2 days, in 3 hours"""
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
        """Magyar: 2 nap múlva, 3 óra múlva"""
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
        """Téma kinyerése a szövegből (egyszerű)"""
        # Dátum után következő szavak
        words = text.split()
        topic_words = []
        
        # Szűrőszavak (magyar és angol)
        skip_words = [
            'megyek', 'vásárol', 'csinál', 'hoz', 'visz', 'lesz', 'van',
            'go', 'buy', 'do', 'bring', 'take', 'will', 'is', 'be'
        ]
        
        for word in words:
            word_lower = word.lower()
            if any(p in word_lower for p in skip_words):
                continue
            if len(word) > 3 and word_lower not in skip_words:
                topic_words.append(word_lower)
        
        if topic_words:
            return '_'.join(topic_words[:2])
        return "reminder"
    
    # --- INTERAKCIÓK ---
    
    def register_interaction(self):
        """Felhasználói interakció regisztrálása"""
        now = time.time()
        self.scratchpad.set_state('last_interaction', now, self.name)
        self.state['last_interaction'] = now
        self.state['idle_since'] = None
        self.state['idle_seconds'] = 0
        self.state['idle_formatted'] = '0s'
    
    # --- IDŐ SEGÉDFÜGGVÉNYEK ---
    
    def _get_time_of_day(self) -> str:
        """A napszak lekérése (reggel, délelőtt, délután, este, éjjel)"""
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
        """Másodpercek formázása olvashatóvá"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hours > 0:
            return f"{hours}h {minutes}m"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"
    
    # --- LEKÉRDEZÉSEK ---
    
    def get_state(self) -> Dict:
        """Heartbeat állapot lekérése"""
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
            'running': self.running,
            'events': self.events,
            'config': self.config.get('proactive', {})
        }

# Teszt
if __name__ == "__main__":
    from scratchpad import Scratchpad
    import time
    
    s = Scratchpad()
    
    class MockOrchestrator:
        def build_kvk_packet(self, data):
            pairs = [f"{k}:{v}" for k, v in data.items()]
            return "|".join(pairs)
    
    orch = MockOrchestrator()
    
    # Teszt konfiguráció
    test_config = {
        'interval': 1.0,
        'proactive': {
            'enabled': True,
            'min_idle_hours': 0.01,
            'max_idle_hours': 24,
            'once_per_day': False,
            'reminders': True,
            'check_interval': 5,
            'chance': 1.0,
            'topics': []
        }
    }
    
    hb = Heartbeat(s, orch, test_config)
    hb.start()
    
    # Emlékeztető teszt
    hb.create_reminder("Kedden megyek vásárolni", language="hu")
    hb.create_reminder("In 2 days buy groceries", language="en")
    
    # Várunk
    time.sleep(10)
    
    # Állapot lekérés
    print("\n--- Heartbeat állapot ---")
    state = hb.get_state()
    for k, v in state.items():
        print(f"{k}: {v}")
    
    hb.stop()