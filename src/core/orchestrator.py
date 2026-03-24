"""
Orchestrator - A Vár központi idegrendszere.

KOMMUNIKÁCIÓS PROTOKOLL:
- Az Orchestrator a KERNEL - központi ZMQ_ROUTER
- Bejövő JSON csomagokat fogad, szétosztja a slotoknak
- Prioritási sorok kezelése (0: Rendszer-riasztás, 1: Felhasználói parancs, 2: Heartbeat)
- Backpressure handling (ha tele a sor, "Várj egy pillanatot" üzenet)

Feladata:
1. Bejövő JSON csomagok fogadása
2. Prioritási sorok kezelése
3. Broadcast küldése a buszon
4. Válaszok fogadása a slotoktól
5. Trace ID generálás (UUIDv7)
"""

import time
import uuid
import threading
import queue
from typing import Dict, List, Any, Optional, Tuple
from collections import deque, defaultdict
from datetime import datetime


class Orchestrator:
    """
    Az Orchestrator egy aktív állapotgép - a KERNEL.
    ZMQ_ROUTER szerepben működik, szétosztja az üzeneteket.
    """
    
    # Prioritási szintek
    PRIORITY = {
        'SYSTEM_ALERT': 0,      # Legmagasabb prioritás
        'USER_COMMAND': 1,       # Közepes
        'HEARTBEAT': 2,          # Legalacsonyabb
        'PROACTIVE': 2           # Szintén alacsony
    }
    
    def __init__(self, scratchpad, message_bus, modules: Dict = None, config: Dict = None):
        self.scratchpad = scratchpad
        self.bus = message_bus
        self.name = "orchestrator"
        self.modules = modules or {}  # <-- HIÁNYZOTT!
        self.config = config or {}
        
        # Prioritási sorok
        self.priority_queues = {
            0: queue.Queue(maxsize=10),   # Rendszer-riasztás
            1: queue.Queue(maxsize=50),   # Felhasználói parancs
            2: queue.Queue(maxsize=100)   # Heartbeat / proaktív
        }
        
        # Aktív trace-ek
        self.active_traces: Dict[str, Dict] = {}
        self.recent_packets = deque(maxlen=100)
        self.lock = threading.RLock()
        
        # Feldolgozó szál
        self.processing_thread = None
        self.running = False
        
        # WebApp callback
        self.webapp_callback = None
        
        # Valet hivatkozás
        self.valet = None
        
        # Konfiguráció
        default_config = {
            'short_term_memory_minutes': 5,
            'max_context_length': 4096,
            'backpressure_message': "Várj egy pillanatot, gondolkodom...",
            'enable_uuidv7': True,
            'enable_rag': True,
            'max_history_messages': 10,
            'response_timeout': 30
        }
        
        for key, value in default_config.items():
            if key not in self.config:
                self.config[key] = value
        
        # Statisztikák
        self.stats = {
            'packets_received': 0,
            'packets_processed': 0,
            'packets_dropped': 0,
            'avg_processing_time': 0,
            'queue_sizes': {0: 0, 1: 0, 2: 0},
            'rag_queries': 0,
            'context_builds': 0,
            'broadcasts': 0
        }
        
        # Adatbázis hivatkozás
        self.db = None
        
        # Feliratkozás a buszra (hogy hallja a válaszokat)
        if self.bus:
            self.bus.subscribe(self.name, self._on_message)
        
        print("⚙️ Orchestrator: Kernel inicializálva. ZMQ_ROUTER módban.")
    
    # ========== BUSZ KOMMUNIKÁCIÓ ==========
    
    def _on_message(self, message: Dict):
        """
        Hallja a buszon érkező üzeneteket.
        A slotok válaszait dolgozza fel.
        """
        header = message.get('header', {})
        payload = message.get('payload', {})
        
        # Válasz a King-től
        if header.get('sender') == 'king' and payload.get('type') == 'king_response':
            trace_id = header.get('in_response_to', '')
            if trace_id and trace_id in self.active_traces:
                self._handle_king_response(trace_id, payload)
        
        # Válasz a Valet-től
        elif header.get('sender') == 'valet' and payload.get('type') == 'context_response':
            trace_id = header.get('in_response_to', '')
            if trace_id and trace_id in self.active_traces:
                self.active_traces[trace_id]['rag_context'] = payload.get('context', {})
        
        # Válasz a Queen-től
        elif header.get('sender') == 'queen' and payload.get('type') == 'logic_response':
            trace_id = header.get('in_response_to', '')
            if trace_id and trace_id in self.active_traces:
                self.active_traces[trace_id]['logic'] = payload.get('logic', {})
        
        # Válasz a Jester-től
        elif header.get('sender') == 'jester' and payload.get('type') == 'jester_report':
            trace_id = header.get('in_response_to', '')
            if trace_id and trace_id in self.active_traces:
                self.active_traces[trace_id]['jester_observation'] = payload
    
    def _handle_king_response(self, trace_id: str, payload: Dict):
        """King válaszának feldolgozása"""
        response_text = payload.get('response', '')
        conversation_id = self.active_traces[trace_id].get('conversation_id')
        
        # Válasz mentése adatbázisba
        if self.db and response_text and conversation_id:
            try:
                self.db.add_message(conversation_id, "assistant", response_text)
            except Exception as e:
                print(f"⚠️ Orchestrator: Válasz mentési hiba: {e}")
        
        # WebApp callback
        if self.webapp_callback:
            self.webapp_callback(response_text, conversation_id, trace_id)
        
        # Állapot frissítés
        with self.lock:
            if trace_id in self.active_traces:
                self.active_traces[trace_id]['status'] = 'completed'
                self.active_traces[trace_id]['response'] = response_text
        
        print(f"⚙️ Orchestrator: Válasz elküldve a WebApp-nek ({trace_id[:8]})")
    
    # ========== FŐ BELÉPÉSI PONT (WEBBŐL) ==========
    
    def process_user_message(self, text: str, conversation_id: int, user_id: int = None) -> dict:
        """
        Egyszerű belépési pont a WebApp számára.
        Közvetlenül hívja a King-et (bus nélkül a hibaelhárításhoz).
        """
        trace_id = self._generate_uuidv7()
        
        # 1. Felhasználói üzenet mentése
        if self.db:
            try:
                self.db.add_message(conversation_id, "user", text)
            except Exception as e:
                print(f"⚠️ Orchestrator: Üzenet mentési hiba: {e}")
        
        # 2. Beszélgetés előzmények lekérése
        conversation_history = []
        if self.db:
            try:
                messages = self.db.get_messages(conversation_id, limit=self.config.get('max_history_messages', 10))
                conversation_history = [
                    {"role": m.get("role", "user"), "content": m.get("content", "")}
                    for m in messages
                ]
            except Exception as e:
                print(f"⚠️ Orchestrator: Előzmények lekérési hiba: {e}")
        
        # 3. King közvetlen hívása
        king = self.modules.get("king") if self.modules else None
        if not king:
            error_msg = "King module not available"
            print(f"❌ Orchestrator: {error_msg}")
            if self.webapp_callback:
                self.webapp_callback(error_msg, conversation_id, trace_id)
            return {"response": error_msg, "trace_id": trace_id}
        
        try:
            print(f"👑 Orchestrator: King hívása: '{text[:50]}...' (conv: {conversation_id})")
            
            # King válasz generálása
            response = king.generate_response(
                user_text=text,
                trace_id=trace_id,
                conversation_id=conversation_id,
                conversation_history=conversation_history,
                rag_context={}  # RAG kontextus később
            )
            
            print(f"✅ Orchestrator: King válaszolt: {response[:50]}...")
            
            # Válasz mentése
            if self.db and response:
                try:
                    self.db.add_message(conversation_id, "assistant", response)
                except Exception as e:
                    print(f"⚠️ Orchestrator: Válasz mentési hiba: {e}")
            
            # WebApp callback
            if self.webapp_callback:
                self.webapp_callback(response, conversation_id, trace_id)
            
            # Valet tracking (ha van)
            if self.valet:
                try:
                    intent_packet = {
                        'payload': {
                            'text': text,
                            'intent': {'class': 'USER_MESSAGE'},
                            'entities': []
                        }
                    }
                    self.valet.track_message(intent_packet)
                except Exception as e:
                    print(f"⚠️ Orchestrator: Valet tracking hiba: {e}")
            
            return {"response": response, "trace_id": trace_id}
            
        except Exception as e:
            print(f"❌ Orchestrator: King hiba: {e}")
            import traceback
            traceback.print_exc()
            error_response = f"Hiba a válaszadás közben: {e}"
            if self.webapp_callback:
                self.webapp_callback(error_response, conversation_id, trace_id)
            return {"response": error_response, "trace_id": trace_id, "error": str(e)}
    
    def _create_royal_decree(self, trace_id: str, text: str, conversation_history: List) -> Dict:
        """
        Királyi rendelet összeállítása - ezt hallja minden slot.
        """
        # Intent és entities meghatározása (egyszerű heurisztika)
        intent_class = self._detect_intent(text)
        
        return {
            "header": {
                "trace_id": trace_id,
                "timestamp": time.time(),
                "version": "3.0",
                "sender": self.name,
                "target": "kernel",
                "broadcast": True
            },
            "payload": {
                "type": "royal_decree",
                "user_message": text,
                "interpretation": {
                    "intent": {"class": intent_class, "confidence": 0.8},
                    "entities": self._extract_entities(text),
                    "language": self._detect_language(text)
                },
                "conversation_history": conversation_history,
                "order": "prepare_context",
                "required_agents": self._determine_required_agents(intent_class),
                "optional_agents": ["jester"]
            },
            "telemetry": {
                "source": "webapp",
                "conversation_id": self.active_traces.get(trace_id, {}).get('conversation_id')
            }
        }
    
    def _detect_intent(self, text: str) -> str:
        """Egyszerű intent detektálás (alapértelmezett)"""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['hello', 'hi', 'szia', 'jó reggelt']):
            return 'greeting'
        elif any(word in text_lower for word in ['bye', 'viszlát', 'később']):
            return 'farewell'
        elif '?' in text or any(word in text_lower for word in ['mi', 'ki', 'hol', 'mikor', 'hogyan']):
            return 'question'
        elif any(word in text_lower for word in ['csinálj', 'írj', 'mutasd', 'add', 'create', 'write']):
            return 'command'
        elif any(word in text_lower for word in ['kösz', 'thank', 'köszi']):
            return 'gratitude'
        
        return 'unknown'
    
    def _extract_entities(self, text: str) -> List[Dict]:
        """Egyszerű entitás kinyerés"""
        entities = []
        
        # Egyszerű minták
        patterns = [
            (r'\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b', 'DATE'),
            (r'\b\d{1,2}[:.]\d{2}\b', 'TIME'),
            (r'\b[\w\-]+\.\w+\b', 'FILE'),
            (r'\bhttps?://[^\s]+\b', 'URL'),
            (r'[\w\.-]+@[\w\.-]+\.\w+', 'EMAIL')
        ]
        
        import re
        for pattern, etype in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                entities.append({'type': etype, 'value': match, 'confidence': 0.7})
        
        return entities
    
    def _detect_language(self, text: str) -> str:
        """Egyszerű nyelvdetektálás"""
        for char in text:
            code = ord(char)
            if 0x4E00 <= code <= 0x9FFF or 0x3040 <= code <= 0x30FF or 0xAC00 <= code <= 0xD7AF:
                return 'cjk'
            if 0x0400 <= code <= 0x04FF:
                return 'cyrillic'
        
        # Magyar karakterek ellenőrzése
        hungarian_chars = ['á', 'é', 'í', 'ó', 'ö', 'ő', 'ú', 'ü', 'ű']
        if any(c in text.lower() for c in hungarian_chars):
            return 'hu'
        
        return 'en'
    
    def _determine_required_agents(self, intent_class: str) -> List[str]:
        """Meghatározza, kikre van szükség"""
        required = ['scribe', 'king']
        
        if intent_class in ['question', 'command', 'knowledge']:
            required.append('valet')
        
        if intent_class == 'knowledge':
            required.append('queen')
        
        return required
    
    def _wait_for_response(self, trace_id: str, timeout: float = 30.0):
        """Vár a King válaszára (timeout-tal)"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            with self.lock:
                if trace_id in self.active_traces:
                    if self.active_traces[trace_id].get('status') == 'completed':
                        return
            
            time.sleep(0.1)
        
        # Timeout esetén
        print(f"⚠️ Orchestrator: Timeout a válaszra ({trace_id[:8]})")
        with self.lock:
            if trace_id in self.active_traces:
                self.active_traces[trace_id]['status'] = 'timeout'
        
        if self.webapp_callback:
            self.webapp_callback(
                self.config['backpressure_message'],
                self.active_traces.get(trace_id, {}).get('conversation_id'),
                trace_id
            )
    
    # ========== BEJÖVŐ CSOMAGOK FELDOLGOZÁSA (KVK kompatibilitás) ==========
    
    def process_raw_packet(self, raw_packet: str, priority: int = 1) -> Optional[Dict]:
        """
        Régi KVK formátumú csomagok feldolgozása (kompatibilitás).
        Átalakítja JSON formátumba és broadcast-olja.
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
        
        # 3. Trace ID
        if 'TRACE' not in packet_dict:
            trace_id = self._generate_uuidv7()
            packet_dict['TRACE'] = trace_id
        else:
            trace_id = packet_dict['TRACE']
        
        # 4. Sorba helyezés
        try:
            self.priority_queues[priority].put({
                'packet': packet_dict,
                'trace_id': trace_id,
                'timestamp': time.time(),
                'priority': priority,
                'raw': raw_packet
            }, timeout=1.0)
            
            self.stats['packets_received'] += 1
            self.stats['queue_sizes'][priority] = self.priority_queues[priority].qsize()
            
        except queue.Full:
            self._handle_backpressure(priority)
            self.stats['packets_dropped'] += 1
            return None
        
        # 5. Feldolgozás indítása
        self._process_item({
            'packet': packet_dict,
            'trace_id': trace_id,
            'timestamp': time.time(),
            'priority': priority,
            'raw': raw_packet
        })
        
        processing_time = time.time() - start_time
        self.stats['packets_processed'] += 1
        
        if self.stats['avg_processing_time'] == 0:
            self.stats['avg_processing_time'] = processing_time
        else:
            self.stats['avg_processing_time'] = (
                self.stats['avg_processing_time'] * 0.9 + processing_time * 0.1
            )
        
        return {'trace_id': trace_id, 'status': 'queued', 'priority': priority}
    
    def _parse_kvk(self, raw: str) -> Dict[str, str]:
        """KVK parser: "INTENT:GREET|USER:user" -> {"INTENT": "GREET", "USER": "user"}"""
        result = {}
        
        if not raw or not isinstance(raw, str):
            return result
        
        pairs = raw.split('|')
        
        for pair in pairs:
            if not pair:
                continue
            
            if ':' in pair:
                key, value = pair.split(':', 1)
                key = key.strip().upper()
                value = value.strip()
                if key and value:
                    result[key] = value
        
        return result
    
    def _process_item(self, item: Dict):
        """Egy feldolgozási elem feldolgozása"""
        packet = item['packet']
        trace_id = item['trace_id']
        
        # Aktív trace-ek közé felvétel
        with self.lock:
            self.active_traces[trace_id] = {
                'trace_id': trace_id,
                'packet': packet,
                'timestamp': time.time(),
                'priority': item['priority'],
                'status': 'processing'
            }
            self.recent_packets.append({
                'time': time.time(),
                'trace_id': trace_id,
                'packet': packet,
                'priority': item['priority']
            })
        
        # JSON csomaggá alakítás és broadcast
        decree = self._kvk_to_decree(packet, trace_id)
        if self.bus:
            self.bus.broadcast(decree)
        self.stats['broadcasts'] += 1
    
    def _kvk_to_decree(self, packet: Dict, trace_id: str) -> Dict:
        """KVK csomag átalakítása royal_decree-vé"""
        intent = packet.get('INTENT', 'unknown')
        user = packet.get('USER', '')
        message = packet.get('MESSAGE', '')
        
        return {
            "header": {
                "trace_id": trace_id,
                "timestamp": time.time(),
                "sender": self.name,
                "target": "kernel",
                "broadcast": True
            },
            "payload": {
                "type": "royal_decree",
                "user_message": message or user,
                "interpretation": {
                    "intent": {"class": intent.lower(), "confidence": 0.8},
                    "entities": [],
                    "language": "en"
                },
                "order": "prepare_context",
                "required_agents": self._determine_required_agents(intent.lower())
            }
        }
    
    def _handle_backpressure(self, priority: int):
        """Backpressure kezelés"""
        print(f"⚙️ Backpressure: {priority} prioritású sor tele")
        self.scratchpad.write(self.name, 
            {'message': self.config['backpressure_message'], 'priority': priority},
            'backpressure'
        )
    
    # ========== SEGÉDFÜGGVÉNYEK ==========
    
    def _generate_uuidv7(self) -> str:
        """UUIDv7 generálás"""
        if self.config['enable_uuidv7']:
            timestamp = int(time.time() * 1000)
            random_part = uuid.uuid4().hex[:8]
            return f"{timestamp:x}-{random_part}"
        else:
            return str(uuid.uuid4())
    
    # ========== ADATBÁZIS ÉS CALLBACK BEÁLLÍTÁS ==========
    
    def set_database(self, db):
        """Adatbázis kapcsolat beállítása"""
        self.db = db
    
    def set_webapp_callback(self, callback):
        """WebApp callback beállítása"""
        self.webapp_callback = callback
    
    def set_valet(self, valet):
        """Valet modul beállítása"""
        self.valet = valet
    
    # ========== INDIÍTÁS ÉS LEÁLLÍTÁS ==========
    
    def start(self):
        """Orchestrator indítása"""
        self.running = True
        self.processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self.processing_thread.start()
        
        self.scratchpad.set_state('orchestrator_status', 'ready', self.name)
        print("⚙️ Orchestrator: Éber és figyel. ZMQ_ROUTER módban.")
    
    def stop(self):
        """Orchestrator leállítása"""
        self.running = False
        if self.processing_thread:
            self.processing_thread.join(timeout=2.0)
        
        self.scratchpad.set_state('orchestrator_status', 'stopped', self.name)
        print("⚙️ Orchestrator: Leállt.")
    
    def _processing_loop(self):
        """Feldolgozó ciklus"""
        while self.running:
            try:
                for priority in [0, 1, 2]:
                    if not self.priority_queues[priority].empty():
                        item = self.priority_queues[priority].get(timeout=0.1)
                        self._process_item(item)
                        self.stats['queue_sizes'][priority] = self.priority_queues[priority].qsize()
                        break
                
                time.sleep(0.01)
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"⚙️ Feldolgozási hiba: {e}")
    
    # ========== LEKÉRDEZÉSEK ==========
    
    def get_active_traces(self) -> Dict:
        """Aktív trace-ek listája"""
        with self.lock:
            return {
                trace_id: {
                    'intent': state.get('packet', {}).get('INTENT', state.get('user_text', '')[:30]),
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
                'queue_sizes': self.stats['queue_sizes'],
                'rag_queries': self.stats['rag_queries'],
                'context_builds': self.stats['context_builds'],
                'broadcasts': self.stats['broadcasts']
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


# Teszt
if __name__ == "__main__":
    from scratchpad import Scratchpad
    from src.bus.message_bus import MessageBus
    
    s = Scratchpad()
    bus = MessageBus()
    bus.start()
    
    orch = Orchestrator(s, bus)
    orch.start()
    
    print("\n--- Orchestrator teszt ---")
    
    # Teszt KVK parsing
    test_packets = [
        "INTENT:GREET|USER:user",
        "INTENT:QUESTION|USER:user|MESSAGE:Mi a helyzet?",
        "COMMAND:READ|FILE:notes.txt",
        "SYSTEM_ALERT:CRITICAL|TEMP:85"
    ]
    
    for p in test_packets:
        print(f"\n📥 Bemenet: {p}")
        result = orch.process_raw_packet(p)
        if result:
            print(f"   Trace ID: {result['trace_id']}")
            print(f"   Prioritás: {result['priority']}")
    
    print(f"\n📊 Statisztikák: {orch.get_stats()}")
    
    orch.stop()
    bus.stop()