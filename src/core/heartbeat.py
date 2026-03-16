"""
Heartbeat - A Vár szíve.

Feladata:
1. Rendszeres "PING" küldése (időérzék)
2. Időalapú események generálása
3. Inaktivitás detektálás
4. Proaktív gondolatok indítása - emlékeztetők és érdeklődés (nem zaklatás!)
"""

import time
import threading
import random
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable, List

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
        self.config = config or {}  # Konfiguráció (kívülről kapja)
        
        # Szálkezelés
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        
        # Alapértelmezett értékek (ha nincs config)
        default_config = {
            'interval': 1.0,
            'proactive': {
                'enabled': True,
                'min_idle_hours': 2,      # Minimum 2 óra csend után
                'max_idle_hours': 8,      # Maximum 8 óra után már ne
                'once_per_day': True,      # Csak napi egyszer
                'reminders': True,         # Emlékeztetők kezelése
                'check_interval': 300,      # 5 percenként ellenőrizze
                'chance': 0.3,              # 30% esély (ha több feltétel is teljesül)
                'topics': []                 # Ha üres, bármiről kérdezhet
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
        
        # Időzítők
        self.interval = self.config.get('interval', 1.0)
        self.last_beat = time.time()
        self.start_time = time.time()
        
        # Események (konfig alapján)
        proactive_interval = self.config.get('proactive', {}).get('check_interval', 300)
        self.events = {
            'status_check': 5.0,                    # 5 másodperc
            'idle_check': 60.0,                      # 1 perc
            'proactive_thought': proactive_interval, # konfigból
            'reminder_check': 3600.0,                 # 1 óránként emlékeztető ellenőrzés
            'deep_thought': 3600.0,                   # 1 óra
            'cleanup': 7200.0,                         # 2 óra
        }
        
        # Utolsó futási idők
        self.last_run = {event: 0 for event in self.events}
        
        # Állapot
        self.state = {
            'beats': 0,
            'uptime_seconds': 0,
            'last_interaction': None,
            'idle_since': None,
            'idle_seconds': 0,
            'proactive_count': 0,
            'last_proactive': 0,           # Mikor volt utoljára proaktív megszólalás
            'proactive_today': False,       # Volt-e már ma
            'last_proactive_date': None,    # Melyik nap volt utoljára
            'reminders_sent': []             # Elküldött emlékeztetők ID-i
        }
        
        # Időpont minták felismeréséhez (magyar nyelvű)
        self.time_patterns = [
            (r'(kedden|szerdán|csütörtökön|pénteken|szombaton|vasárnap|hétfőn)', self._parse_weekday),
            (r'(holnap|holnapután|ma|most)', self._parse_relative),
            (r'(\d{4}\.\s*\d{1,2}\.\s*\d{1,2})', self._parse_absolute),  # 2025. 03. 11
            (r'(\d{1,2})[-/](\d{1,2})', self._parse_short),               # 03/11
        ]
        
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
        
        # Uptime frissítése
        self.scratchpad.set_state('uptime_seconds', self.state['uptime_seconds'], self.name)
        
        # Utolsó interakció ellenőrzése
        last_interaction = self.scratchpad.get_state('last_interaction')
        if last_interaction:
            self.state['last_interaction'] = last_interaction
            idle = now - last_interaction
            self.state['idle_seconds'] = int(idle)
            
            if idle > 60 and not self.state['idle_since']:
                self.state['idle_since'] = last_interaction
                self.scratchpad.write(self.name, 
                    {'idle_seconds': int(idle)}, 
                    'idle_start'
                )
        
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
                'idle': self.state['idle_seconds'],
                'beats': self.state['beats'],
                'king_status': self.scratchpad.get_state('king_status', 'unknown'),
                'jester_status': self.scratchpad.get_state('jester_status', 'unknown'),
                'orchestrator_status': self.scratchpad.get_state('orchestrator_status', 'unknown'),
            }
            self.scratchpad.write(self.name, status, 'heartbeat_status')
            
        elif event == 'idle_check':
            if self.state['idle_seconds'] > 300:
                self.scratchpad.write(self.name, 
                    {'idle_minutes': self.state['idle_seconds'] // 60}, 
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
            self.scratchpad.write(self.name, 
                {'type': 'deep_thought', 'time': now}, 
                'heartbeat_deep'
            )
        
        elif event == 'cleanup':
            self.scratchpad.cleanup_old(max_age_seconds=3600)
    
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
                # Már volt ma
                return
            
            # Ellenőrizzük, hogy tényleg volt-e ma (lehet, hogy régi)
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
            'idle_hours': round(idle_hours, 1)
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
        
        for module, notes_dict in notes.items():
            for key, note in notes_dict.items():
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
                        topic = parts[2] if len(parts) > 2 else 'esemény'
                        note_text = note.get('value', '')
                        
                        self._send_proactive({
                            'type': 'reminder',
                            'topic': topic,
                            'note': note_text,
                            'reminder_id': reminder_id
                        })
                        
                        self.state['reminders_sent'].append(reminder_id)
                        
                except Exception as e:
                    print(f"💓 Hiba az emlékeztető feldolgozásában: {e}")
    
    def _get_last_topic(self) -> str:
        """Utolsó beszélgetési téma lekérése"""
        last_intent = self.scratchpad.read_last('intent')
        if last_intent:
            content = last_intent.get('content', {})
            return content.get('intent', {}).get('class', '')
        return ''
    
    def _send_proactive(self, data: Dict):
        """Proaktív üzenet küldése KVK formátumban"""
        if not self.orchestrator:
            return
        
        now = datetime.now()
        
        # Alap KVK csomag
        packet = {
            'INTENT': 'PROACTIVE',
            'TYPE': data.get('type', 'interest'),
            'TIME': now.strftime("%H:%M"),
            'DATE': now.strftime("%Y-%m-%d")
        }
        
        # Üzenet összeállítása típus alapján
        if data.get('type') == 'reminder':
            packet['MESSAGE'] = f"Emlékeztető: {data.get('note', data.get('topic', ''))}"
            packet['TOPIC'] = data.get('topic', '')
            packet['REMINDER_ID'] = data.get('reminder_id', '')
            
        else:  # interest
            topic = data.get('topic', 'dolog')
            hours = data.get('idle_hours', 2)
            
            # Különböző megfogalmazások, hogy ne legyen unalmas
            messages = [
                f"Már {hours} órája nem beszéltünk. Hogy haladsz a {topic} témával?",
                f"Figyelj, {hours} órája csend van. Mi a helyzet a {topic}-vel?",
                f"Az előbb még a {topic}-ről beszéltünk. Történt azóta valami?",
                f"Csak úgy érdeklődöm, {hours} órája nem szóltál. Minden oké a {topic} körül?"
            ]
            packet['MESSAGE'] = random.choice(messages)
            packet['TOPIC'] = topic
            packet['IDLE_HOURS'] = str(hours)
        
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
    
    def create_reminder(self, text: str, source: str = "user"):
        """
        Emlékeztető létrehozása egy szövegből.
        Kinyeri az időpontot és a témát.
        Példa: "kedden megyek videókártyát venni" -> reminder_20250311_videokartya
        """
        date = self._extract_date(text)
        if not date:
            return None
        
        # Téma kinyerése (a dátum utáni rész)
        topic = self._extract_topic(text)
        if not topic:
            topic = "emlékeztető"
        
        # Emlékeztető kulcs: reminder_YYYYMMDD_téma
        date_str = date.strftime("%Y%m%d")
        key = f"reminder_{date_str}_{topic}"
        
        # Mentés a scratchpadbe
        self.scratchpad.write_note('heartbeat', key, {
            'text': text,
            'date': date_str,
            'topic': topic,
            'source': source,
            'created': time.time()
        })
        
        print(f"💓 Emlékeztető létrehozva: {key}")
        return key
    
    def _extract_date(self, text: str) -> Optional[datetime]:
        """Dátum kinyerése szövegből"""
        text_lower = text.lower()
        
        for pattern, handler in self.time_patterns:
            match = re.search(pattern, text_lower)
            if match:
                return handler(match)
        
        return None
    
    def _parse_weekday(self, match) -> Optional[datetime]:
        """Hétnapok feldolgozása"""
        day_map = {
            'hétfőn': 0, 'kedden': 1, 'szerdán': 2, 
            'csütörtökön': 3, 'pénteken': 4, 'szombaton': 5, 'vasárnap': 6
        }
        day_name = match.group(1)
        target_weekday = day_map.get(day_name)
        
        if target_weekday is None:
            return None
        
        today = datetime.now()
        current_weekday = today.weekday()
        days_ahead = target_weekday - current_weekday
        if days_ahead <= 0:  # Ha már volt ezen a héten, jövő hét
            days_ahead += 7
            
        return today + timedelta(days=days_ahead)
    
    def _parse_relative(self, match) -> Optional[datetime]:
        """Relatív időpontok (ma, holnap)"""
        word = match.group(1)
        today = datetime.now()
        
        if word == 'ma':
            return today
        elif word == 'holnap':
            return today + timedelta(days=1)
        elif word == 'holnapután':
            return today + timedelta(days=2)
        elif word == 'most':
            return today
        
        return None
    
    def _parse_absolute(self, match) -> Optional[datetime]:
        """Abszolút dátum: 2025. 03. 11"""
        try:
            date_str = match.group(1)
            # Többféle formátum
            for fmt in ["%Y. %m. %d", "%Y.%m.%d", "%Y-%m-%d"]:
                try:
                    return datetime.strptime(date_str, fmt)
                except:
                    continue
        except:
            pass
        return None
    
    def _parse_short(self, match) -> Optional[datetime]:
        """Rövid dátum: 03/11"""
        try:
            month, day = match.groups()
            year = datetime.now().year
            date = datetime(year, int(month), int(day))
            if date < datetime.now():  # Ha már volt idén, jövő év
                date = datetime(year + 1, int(month), int(day))
            return date
        except:
            return None
    
    def _extract_topic(self, text: str) -> str:
        """Téma kinyerése a szövegből (egyszerű)"""
        # Dátum után következő szavak
        words = text.split()
        topic_words = []
        
        for word in words:
            if any(p in word.lower() for p in ['megyek', 'vásárol', 'csinál', 'hoz', 'visz']):
                continue
            if len(word) > 3 and word not in ['kedden', 'szerdán', 'csütörtökön', 'pénteken', 'szombaton', 'vasárnap', 'hétfőn']:
                topic_words.append(word)
        
        if topic_words:
            return '_'.join(topic_words[:2])  # Max 2 szó
        return "emlékeztető"
    
    # --- INTERAKCIÓK ---
    
    def register_interaction(self):
        """Felhasználói interakció regisztrálása"""
        now = time.time()
        self.scratchpad.set_state('last_interaction', now, self.name)
        self.state['last_interaction'] = now
        self.state['idle_since'] = None
        self.state['idle_seconds'] = 0
    
    # --- LEKÉRDEZÉSEK ---
    
    def get_state(self) -> Dict:
        """Heartbeat állapot lekérése"""
        return {
            'beats': self.state['beats'],
            'uptime': self._format_uptime(self.state['uptime_seconds']),
            'uptime_seconds': self.state['uptime_seconds'],
            'idle': self._format_uptime(self.state['idle_seconds']),
            'idle_seconds': self.state['idle_seconds'],
            'proactive_count': self.state['proactive_count'],
            'proactive_today': self.state['proactive_today'],
            'reminders_sent': len(self.state['reminders_sent']),
            'running': self.running,
            'events': self.events,
            'config': self.config.get('proactive', {})
        }
    
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
            'min_idle_hours': 0.01,  # Teszteléshez nagyon kicsi
            'max_idle_hours': 24,
            'once_per_day': False,     # Teszteléshez többször is
            'reminders': True,
            'check_interval': 5,
            'chance': 1.0,             # Mindig
            'topics': []
        }
    }
    
    hb = Heartbeat(s, orch, test_config)
    hb.start()
    
    # Emlékeztető teszt
    hb.create_reminder("kedden megyek videókártyát venni")
    
    # Várunk
    time.sleep(10)
    
    hb.stop()