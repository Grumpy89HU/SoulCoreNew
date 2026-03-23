"""
Orchestrator - A Vár központi idegrendszere.

Feladata:
1. Bejövő RawPacket (KVK formátum) fogadása
2. KVK parsing: "INTENT:GREET|USER:GRUMPY" -> dict
3. Kontextus összeállítása a modellnek (tiszta szöveg)
4. Prioritási sorok kezelése (0: Rendszer-riasztás, 1: Felhasználói parancs, 2: Heartbeat)
5. Backpressure handling (ha tele a sor, "Várj egy pillanatot" üzenet)
6. Trace ID generálás (UUIDv7)
7. Válasz fogadása a modelltől és akciók detektálása
"""

import time
import uuid
import re
from typing import Dict, List, Any, Optional, Tuple
from collections import deque, defaultdict
from datetime import datetime
import threading
import queue

class Orchestrator:
    """
    Az Orchestrator egy aktív állapotgép.
    Minden beérkező inger egy életciklust indít el.
    """
    
    # Prioritási szintek
    PRIORITY = {
        'SYSTEM_ALERT': 0,      # Legmagasabb prioritás
        'USER_COMMAND': 1,       # Közepes
        'HEARTBEAT': 2,          # Legalacsonyabb
        'PROACTIVE': 2           # Szintén alacsony
    }
    
    # KVK separator-ök
    KVK_PAIR_SEP = '|'
    KVK_KEY_VALUE_SEP = ':'
    
    # Akció detektáló minták (a válasz végén)
    ACTION_PATTERNS = {
        'save_note': r'//save$',
        'delete_note': r'//delete$',
        'search': r'//search',
        'execute': r'//run',
        'no_action': r'.*'
    }
    
    def __init__(self, scratchpad, modules=None):
        self.scratchpad = scratchpad
        self.name = "orchestrator"
        self.modules = modules or {}  # <-- HIÁNYZÓ: modulok dictionary
        self.pending_responses = {}  # trace_id -> response callback vagy Queue
        self.webapp_callback = None  # opcionális callback a WebApp felé
        
        # Prioritási sorok (queue per prioritás)
        self.priority_queues = {
            0: queue.Queue(maxsize=10),   # Rendszer-riasztás
            1: queue.Queue(maxsize=50),   # Felhasználói parancs
            2: queue.Queue(maxsize=100)   # Heartbeat / proaktív
        }
        
        # Aktív trace-ek
        self.active_traces = {}  # trace_id -> state
        self.recent_packets = deque(maxlen=100)  # utolsó 100 csomag
        
        # Feldolgozó szál
        self.processing_thread = None
        self.running = False
        self.lock = threading.RLock()
        
        # Statisztikák
        self.stats = {
            'packets_received': 0,
            'packets_processed': 0,
            'packets_dropped': 0,
            'avg_processing_time': 0,
            'queue_sizes': {0: 0, 1: 0, 2: 0}
        }
        
        # Konfiguráció (később configból)
        self.config = {
            'short_term_memory_minutes': 5,
            'max_context_length': 4096,  # token
            'backpressure_message': "Várj egy pillanatot, gondolkodom...",
            'enable_uuidv7': True
        }
        
        # Adatbázis hivatkozás (később beállítva)
        self.db = None
        
        print("⚙️ Orchestrator: Idegrendszer inicializálva.")
    
    def set_database(self, db):
        """Adatbázis kapcsolat beállítása"""
        self.db = db
    
    def start(self):
        """Orchestrator indítása"""
        self.running = True
        self.processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self.processing_thread.start()
        
        self.scratchpad.set_state('orchestrator_status', 'ready', self.name)
        print("⚙️ Orchestrator: Éber és figyel.")
        
    def set_webapp_callback(self, callback):
        """Beállítja a WebApp felé küldendő válasz callbacket."""
        self.webapp_callback = callback
    
    def stop(self):
        """Orchestrator leállítása"""
        self.running = False
        if self.processing_thread:
            self.processing_thread.join(timeout=2.0)
        
        self.scratchpad.set_state('orchestrator_status', 'stopped', self.name)
        print("⚙️ Orchestrator: Leállt.")
    
    # --- BEJÖVŐ CSOMAGOK FELDOLGOZÁSA ---
    
    def process_raw_packet(self, raw_packet: str, priority: int = 1) -> Optional[Dict]:
        """
        Fő belépési pont.
        raw_packet formátum: "INTENT:GREET|USER:GRUMPY|TIME:MORNING"
        """
        start_time = time.time()
        
        # 1. KVK parsing
        packet_dict = self._parse_kvk(raw_packet)
        if not packet_dict:
            self.scratchpad.write(self.name, 
                {'error': 'Invalid KVK packet', 'raw': raw_packet}, 
                'error'
            )
            return None
        
        # 2. Prioritás meghatározása
        intent = packet_dict.get('INTENT', '').upper()
        if intent == 'SYSTEM_ALERT':
            priority = self.PRIORITY['SYSTEM_ALERT']
        elif intent == 'PROACTIVE':
            priority = self.PRIORITY['PROACTIVE']
        else:
            priority = self.PRIORITY['USER_COMMAND']
        
        # 3. Trace ID generálás (UUIDv7)
        if 'TRACE' not in packet_dict:
            trace_id = self._generate_uuidv7()
            packet_dict['TRACE'] = trace_id
        else:
            trace_id = packet_dict['TRACE']
        
        # 4. Sorba helyezés prioritás alapján
        try:
            self.priority_queues[priority].put({
                'packet': packet_dict,
                'trace_id': trace_id,
                'timestamp': time.time(),
                'priority': priority,
                'raw': raw_packet
            }, timeout=1.0)
            
            # Statisztika
            self.stats['packets_received'] += 1
            self.stats['queue_sizes'][priority] = self.priority_queues[priority].qsize()
            
        except queue.Full:
            # Backpressure: ha tele a sor, jelezzük a felhasználónak
            self._handle_backpressure(priority)
            self.stats['packets_dropped'] += 1
            return None
        
        # 5. Naplózás
        self.scratchpad.write(self.name, 
            {'trace_id': trace_id, 'intent': packet_dict.get('INTENT'), 'priority': priority},
            'packet_queued'
        )
        
        return {'trace_id': trace_id, 'status': 'queued', 'priority': priority}
    
    def _parse_kvk(self, raw: str) -> Dict[str, str]:
        """
        KVK parser: "INTENT:GREET|USER:GRUMPY" -> {"INTENT": "GREET", "USER": "GRUMPY"}
        Hibátlan, gyors, emberi szemnek is olvasható.
        """
        result = {}
        
        # Üres vagy None esetén
        if not raw or not isinstance(raw, str):
            return result
        
        # Párok szétválasztása
        pairs = raw.split(self.KVK_PAIR_SEP)
        
        for pair in pairs:
            if not pair:
                continue
            
            # Key-Value szétválasztás
            if self.KVK_KEY_VALUE_SEP in pair:
                key, value = pair.split(self.KVK_KEY_VALUE_SEP, 1)
                key = key.strip().upper()
                value = value.strip()
                if key and value:
                    result[key] = value
        
        return result
    
    def _generate_uuidv7(self) -> str:
        """
        UUIDv7 generálás (időbeli sorrendet is kódol)
        """
        if self.config['enable_uuidv7']:
            # Egyszerűsített UUIDv7 (időbélyeg + random)
            timestamp = int(time.time() * 1000)  # ezredmásodperc
            random_part = uuid.uuid4().hex[:8]
            return f"{timestamp:x}-{random_part}"
        else:
            return str(uuid.uuid4())
    
    def _handle_backpressure(self, priority: int):
        """
        Backpressure kezelés: ha tele a sor, küldünk egy "várj" üzenetet.
        """
        print(f"⚙️ Backpressure: {priority} prioritású sor tele")
        
        # Üzenet küldése a felhasználónak (ha van Scribe)
        self.scratchpad.write(self.name, 
            {'message': self.config['backpressure_message'], 'priority': priority},
            'backpressure'
        )
    
    # --- FELDOLGOZÓ CIKLUS ---
    
    def _processing_loop(self):
        """
        Fő feldolgozó ciklus - prioritási sorokból dolgozik.
        """
        while self.running:
            try:
                # Először a legmagasabb prioritású sorokat nézzük
                for priority in [0, 1, 2]:
                    if not self.priority_queues[priority].empty():
                        item = self.priority_queues[priority].get(timeout=0.1)
                        self._process_item(item)
                        self.stats['queue_sizes'][priority] = self.priority_queues[priority].qsize()
                        break
                
                time.sleep(0.01)  # Kis szünet a CPU kímélése érdekében
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"⚙️ Feldolgozási hiba: {e}")
    
    def _process_item(self, item: Dict):
        """
        Egy feldolgozási elem feldolgozása.
        """
        start_time = time.time()
        packet = item['packet']
        trace_id = item['trace_id']
        
        # 1. Context Injection - rövid távú memória lekérése
        short_term = self._get_short_term_context()
        
        # 2. Teljes állapot összeállítása
        state = {
            'trace_id': trace_id,
            'packet': packet,
            'short_term': short_term,
            'timestamp': time.time(),
            'priority': item['priority'],
            'status': 'processing'
        }
        
        # 3. Aktív trace-ek közé felvétel
        with self.lock:
            self.active_traces[trace_id] = state
            self.recent_packets.append({
                'time': time.time(),
                'trace_id': trace_id,
                'packet': packet,
                'priority': item['priority']
            })
        
        # 4. Naplózás
        self.scratchpad.write(self.name, 
            {'trace_id': trace_id, 'intent': packet.get('INTENT')},
            'packet_processing'
        )
        
        # 5. Feldolgozási idő számítása
        processing_time = time.time() - start_time
        
        # 6. Statisztika frissítés
        self.stats['packets_processed'] += 1
        if self.stats['avg_processing_time'] == 0:
            self.stats['avg_processing_time'] = processing_time
        else:
            self.stats['avg_processing_time'] = (
                self.stats['avg_processing_time'] * 0.9 + processing_time * 0.1
            )
        
        # 7. Állapot frissítés
        with self.lock:
            if trace_id in self.active_traces:
                self.active_traces[trace_id]['status'] = 'processed'
    
    def _get_short_term_context(self) -> Dict:
        """
        Rövid távú kontextus lekérése:
        - Utolsó 5 perc eseményei
        - Aktuális állapotok
        """
        # Időbélyeg 5 perccel ezelőtt
        five_minutes_ago = time.time() - (self.config['short_term_memory_minutes'] * 60)
        
        # Utolsó 5 perc csomagjai
        recent = [
            p for p in self.recent_packets 
            if p['time'] > five_minutes_ago
        ]
        
        # Király állapota (ha van)
        king_state = self.scratchpad.read_note('king', 'state', {})
        
        # Jester állapota (ha van)
        jester_state = self.scratchpad.read_note('jester', 'state', {})
        
        return {
            'recent_packets_count': len(recent),
            'recent_intents': [p['packet'].get('INTENT') for p in recent if p['packet'].get('INTENT')],
            'recent_priorities': [p.get('priority') for p in recent],
            'king_status': king_state.get('status', 'unknown'),
            'jester_warnings': len(jester_state.get('warnings', [])) if jester_state else 0,
            'uptime': time.time() - self.scratchpad.get_state('start_time', time.time())
        }
    
    # --- MODELL BEMENET ÖSSZEÁLLÍTÁSA ---
    
    def build_model_input(self, state: Dict) -> str:
        """
        KVK állapotból tiszta szöveges bemenet készítése a modellnek.
        Ezt kapja majd a Király.
        """
        packet = state.get('packet', {})
        intent = packet.get('INTENT', 'UNKNOWN')
        user = packet.get('USER', self.scratchpad.get_state('user_name', 'User'))
        message = packet.get('MESSAGE', '')
        
        # Idő kontextus
        hour = time.localtime().tm_hour
        if hour < 6:
            time_of_day = "éjszaka"
        elif hour < 12:
            time_of_day = "reggel"
        elif hour < 18:
            time_of_day = "délután"
        else:
            time_of_day = "este"
        
        # Rövid távú memória összefoglaló
        short = state.get('short_term', {})
        recent_intents = short.get('recent_intents', [])
        recent_summary = ""
        if recent_intents:
            recent_summary = f"Az utóbbi időben ezekről beszéltetek: {', '.join(recent_intents[-3:])}."
        
        # Jester figyelmeztetések
        jester_warnings = short.get('jester_warnings', 0)
        warning_text = ""
        if jester_warnings > 0:
            warning_text = f"(Figyelmeztetések száma: {jester_warnings})"
        
        # Bemenet összeállítása - tiszta szöveg, semmi tag
        model_input = f"""Idő: {time_of_day}.
Felhasználó: {user}.
Szándék: {intent}.
{recent_summary}
{warning_text}

{user}: {message}

Válaszod:"""
        
        # Token limit ellenőrzés (egyszerű becslés)
        estimated_tokens = len(model_input.split())
        if estimated_tokens > self.config['max_context_length']:
            # Rövidítés
            model_input = model_input[:self.config['max_context_length'] * 4] + "..."
        
        return model_input.strip()
    
    # --- MODELL VÁLASZ FELDOLGOZÁSA ---
    
    def process_model_response(self, trace_id: str, response: str) -> Dict:
        """
        Modell válaszának feldolgozása.
        - Akciók detektálása a válasz végén
        - Eredmény KVK csomagba csomagolása
        """
        # Aktív trace megkeresése
        state = self.active_traces.get(trace_id)
        if not state:
            return {'ERROR': f'Unknown trace_id: {trace_id}'}
        
        # Akció detektálás
        action, clean_response = self._detect_action(response)
        
        # Eredmény KVK csomag
        result_packet = {
            'TRACE': trace_id,
            'RESPONSE': clean_response,
            'ACTION': action if action != 'no_action' else 'NONE',
            'STATUS': 'success'
        }
        
        # Állapot frissítés
        with self.lock:
            state['status'] = 'completed'
            state['response'] = clean_response
            state['action'] = action
        
        # Naplózás
        self.scratchpad.write(self.name, 
            {'trace_id': trace_id, 'action': action, 'response_length': len(clean_response)},
            'response_processed'
        )
        
        return result_packet
    
    def _detect_action(self, response: str) -> Tuple[str, str]:
        """
        Akció detektálás a válasz végén.
        Visszaadja (action, clean_response) párt.
        """
        response = response.strip()
        
        for action, pattern in self.ACTION_PATTERNS.items():
            if re.search(pattern, response):
                if action != 'no_action':
                    # Akció eltávolítása a válaszból
                    clean = re.sub(pattern, '', response).strip()
                    return action, clean
                break
        
        return 'no_action', response
    
    # --- KVK CSOMAG KÉSZÍTÉS ---
    
    def build_kvk_packet(self, data: Dict) -> str:
        """
        Dict -> KVK string
        {"INTENT": "GREET", "USER": "GRUMPY"} -> "INTENT:GREET|USER:GRUMPY"
        """
        pairs = []
        for key, value in data.items():
            if value is not None and value != '':
                # Csak felsőkulcsos, hogy egységes legyen
                key = str(key).strip().upper()
                value = str(value).strip()
                pairs.append(f"{key}{self.KVK_KEY_VALUE_SEP}{value}")
        
        return self.KVK_PAIR_SEP.join(pairs)
    
    # --- LEKÉRDEZÉSEK ---
    
    def get_active_traces(self) -> Dict:
        """Aktív trace-ek listája (admin felületnek)"""
        with self.lock:
            return {
                trace_id: {
                    'intent': state['packet'].get('INTENT'),
                    'age': time.time() - state['timestamp'],
                    'status': state['status'],
                    'priority': state.get('priority', 1)
                }
                for trace_id, state in self.active_traces.items()
                if state['status'] != 'completed'
            }
    
    def get_stats(self) -> Dict:
        """Statisztikák lekérése"""
        with self.lock:
            return {
                'packets_received': self.stats['packets_received'],
                'packets_processed': self.stats['packets_processed'],
                'packets_dropped': self.stats['packets_dropped'],
                'avg_processing_time_ms': round(self.stats['avg_processing_time'] * 1000, 2),
                'active_traces': len([s for s in self.active_traces.values() if s['status'] != 'completed']),
                'queue_sizes': self.stats['queue_sizes']
            }
    
    def cleanup_old_traces(self, max_age_seconds: int = 3600):
        """Régi trace-ek törlése"""
        now = time.time()
        to_delete = []
        
        with self.lock:
            for tid, state in self.active_traces.items():
                if now - state['timestamp'] > max_age_seconds:
                    to_delete.append(tid)
            
            for tid in to_delete:
                del self.active_traces[tid]
    
    # --- WEBBEL KAPCSOLATOS METÓDUS ---
    
    def process_user_message(self, text: str, conversation_id: int, user_id: int = 1) -> dict:
        """
        Egyszerű belépési pont a WebApp számára.
        Létrehoz egy kérést, elindítja a feldolgozást, és szinkron módon visszaadja a választ.
        """
        import uuid
        import time

        trace_id = str(uuid.uuid4())
        
        # 1. Mentjük a felhasználói üzenetet (user_id nélkül, mert a metódus nem várja)
        if self.db:
            try:
                # A Database.add_message() aláírása: add_message(conversation_id, role, content, tokens=0, metadata=None)
                self.db.add_message(conversation_id, "user", text)
            except Exception as e:
                print(f"⚠️ Orchestrator: Üzenet mentési hiba: {e}")
        
        # 2. Összeállítjuk a belső csomagot
        packet = {
            "header": {
                "trace_id": trace_id,
                "timestamp": time.time(),
                "version": "3.0",
                "sender": "webapp"
            },
            "payload": {
                "intent": {"class": "USER_MESSAGE", "confidence": 1.0},
                "entities": [{"type": "TEXT", "value": text}],
                "raw_text": text,
                "conversation_id": conversation_id
            }
        }
        
        # 3. King hívása
        king = None
        if self.modules:
            king = self.modules.get("king")
        
        if king:
            try:
                response = king.generate_response(text, trace_id, conversation_id)
                print(f"👑 Orchestrator: King válaszolt: {response[:50]}...")
                
                if response and self.webapp_callback:
                    self.webapp_callback(response, conversation_id, trace_id)
                
                # Asszisztens válasz mentése (user_id nélkül)
                if self.db and response:
                    try:
                        self.db.add_message(conversation_id, "assistant", response)
                    except Exception as e:
                        print(f"⚠️ Orchestrator: Válasz mentési hiba: {e}")
                
                return {"response": response, "trace_id": trace_id}
            except Exception as e:
                print(f"❌ Orchestrator: King hiba: {e}")
                error_response = f"Hiba a Király válaszadása közben: {e}"
                if self.webapp_callback:
                    self.webapp_callback(error_response, conversation_id, trace_id)
                return {"response": error_response, "trace_id": trace_id, "error": str(e)}
        
        error_msg = "A Király nem elérhető."
        print(f"❌ Orchestrator: {error_msg}")
        if self.webapp_callback:
            self.webapp_callback(error_msg, conversation_id, trace_id)
        return {"response": error_msg, "trace_id": trace_id}


# Teszt
if __name__ == "__main__":
    from scratchpad import Scratchpad
    
    s = Scratchpad()
    s.set_state('start_time', time.time())
    s.set_state('user_name', 'User')
    
    orch = Orchestrator(s)
    
    # Teszt KVK parsing
    print("--- KVK parsing teszt ---")
    test_packets = [
        "INTENT:GREET|USER:GRUMPY",
        "INTENT:QUESTION|USER:GRUMPY|MESSAGE:Mi a helyzet?",
        "COMMAND:READ|FILE:notes.txt",
        "SYSTEM_ALERT:CRITICAL|TEMP:85"
    ]
    
    for p in test_packets:
        print(f"\nBemenet: {p}")
        result = orch.process_raw_packet(p)
        if result:
            print(f"Trace ID: {result['trace_id']}")
            print(f"Prioritás: {result['priority']}")
    
    print(f"\nStatisztikák: {orch.get_stats()}")