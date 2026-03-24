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
8. Valet kontextus integráció (RAG 2.1)
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
    
    def __init__(self, scratchpad, modules: Dict = None, config: Dict = None):
        self.scratchpad = scratchpad
        self.name = "orchestrator"
        self.modules = modules or {}  # modulok dictionary (king, valet, stb.)
        self.pending_responses = {}   # trace_id -> response callback vagy Queue
        self.webapp_callback = None   # opcionális callback a WebApp felé
        
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
        
        # Konfiguráció (alapértékek, felülírható)
        default_config = {
            'short_term_memory_minutes': 5,
            'max_context_length': 4096,      # token
            'backpressure_message': "Várj egy pillanatot, gondolkodom...",
            'enable_uuidv7': True,
            'enable_rag': True,               # RAG keresés bekapcsolása
            'max_history_messages': 10,       # Kontextusba kerülő üzenetek száma
            'response_timeout': 30,           # Válasz timeout másodpercben
        }
        
        self.config = default_config.copy()
        if config:
            self.config.update(config)
        
        # Statisztikák
        self.stats = {
            'packets_received': 0,
            'packets_processed': 0,
            'packets_dropped': 0,
            'avg_processing_time': 0,
            'queue_sizes': {0: 0, 1: 0, 2: 0},
            'rag_queries': 0,
            'context_builds': 0
        }
        
        # Adatbázis hivatkozás (később beállítva)
        self.db = None
        
        # Valet hivatkozás (könnyebb elérés)
        self.valet = self.modules.get('valet')
        
        print("⚙️ Orchestrator: Idegrendszer inicializálva.")
    
    def set_database(self, db):
        """Adatbázis kapcsolat beállítása"""
        self.db = db
    
    def set_valet(self, valet):
        """Valet modul beállítása"""
        self.valet = valet
        if valet:
            self.modules['valet'] = valet
    
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
    
    # ========== BEJÖVŐ CSOMAGOK FELDOLGOZÁSA ==========
    
    def process_raw_packet(self, raw_packet: str, priority: int = 1) -> Optional[Dict]:
        """
        Fő belépési pont.
        raw_packet formátum: "INTENT:GREET|USER:user|TIME:MORNING"
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
            
            self.stats['packets_received'] += 1
            self.stats['queue_sizes'][priority] = self.priority_queues[priority].qsize()
            
        except queue.Full:
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
        """KVK parser: "INTENT:GREET|USER:user" -> {"INTENT": "GREET", "USER": "user"}"""
        result = {}
        
        if not raw or not isinstance(raw, str):
            return result
        
        pairs = raw.split(self.KVK_PAIR_SEP)
        
        for pair in pairs:
            if not pair:
                continue
            
            if self.KVK_KEY_VALUE_SEP in pair:
                key, value = pair.split(self.KVK_KEY_VALUE_SEP, 1)
                key = key.strip().upper()
                value = value.strip()
                if key and value:
                    result[key] = value
        
        return result
    
    def _generate_uuidv7(self) -> str:
        """UUIDv7 generálás (időbeli sorrendet is kódol)"""
        if self.config['enable_uuidv7']:
            timestamp = int(time.time() * 1000)
            random_part = uuid.uuid4().hex[:8]
            return f"{timestamp:x}-{random_part}"
        else:
            return str(uuid.uuid4())
    
    def _handle_backpressure(self, priority: int):
        """Backpressure kezelés: ha tele a sor, küldünk egy "várj" üzenetet."""
        print(f"⚙️ Backpressure: {priority} prioritású sor tele")
        
        self.scratchpad.write(self.name, 
            {'message': self.config['backpressure_message'], 'priority': priority},
            'backpressure'
        )
    
    # ========== FELDOLGOZÓ CIKLUS ==========
    
    def _processing_loop(self):
        """Fő feldolgozó ciklus - prioritási sorokból dolgozik."""
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
    
    def _process_item(self, item: Dict):
        """Egy feldolgozási elem feldolgozása."""
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
        
        self.scratchpad.write(self.name, 
            {'trace_id': trace_id, 'intent': packet.get('INTENT')},
            'packet_processing'
        )
        
        processing_time = time.time() - start_time
        self.stats['packets_processed'] += 1
        
        if self.stats['avg_processing_time'] == 0:
            self.stats['avg_processing_time'] = processing_time
        else:
            self.stats['avg_processing_time'] = (
                self.stats['avg_processing_time'] * 0.9 + processing_time * 0.1
            )
        
        with self.lock:
            if trace_id in self.active_traces:
                self.active_traces[trace_id]['status'] = 'processed'
    
    def _get_short_term_context(self) -> Dict:
        """Rövid távú kontextus lekérése."""
        five_minutes_ago = time.time() - (self.config['short_term_memory_minutes'] * 60)
        
        recent = [
            p for p in self.recent_packets 
            if p['time'] > five_minutes_ago
        ]
        
        king_state = self.scratchpad.read_note('king', 'state', {})
        jester_state = self.scratchpad.read_note('jester', 'state', {})
        
        return {
            'recent_packets_count': len(recent),
            'recent_intents': [p['packet'].get('INTENT') for p in recent if p['packet'].get('INTENT')],
            'recent_priorities': [p.get('priority') for p in recent],
            'king_status': king_state.get('status', 'unknown'),
            'jester_warnings': len(jester_state.get('warnings', [])) if jester_state else 0,
            'uptime': time.time() - self.scratchpad.get_state('start_time', time.time())
        }
    
    # ========== MODELL BEMENET ÖSSZEÁLLÍTÁSA ==========
    
    def build_model_input(self, state: Dict, rag_context: Dict = None) -> str:
        """
        KVK állapotból tiszta szöveges bemenet készítése a modellnek.
        RAG kontextussal bővítve (ha van).
        """
        packet = state.get('packet', {})
        intent = packet.get('INTENT', 'UNKNOWN')
        user = packet.get('USER', self.scratchpad.get_state('user_name', 'user'))
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
        
        # RAG kontextus beillesztése (ha van)
        rag_section = ""
        if rag_context and self.config['enable_rag']:
            rag_parts = []
            
            if rag_context.get('graph_context'):
                rag_parts.append(f"## Kapcsolatok\n{rag_context['graph_context']}")
            
            if rag_context.get('vector_context'):
                rag_parts.append(f"## Ismert tények\n{rag_context['vector_context']}")
            
            if rag_context.get('emotional_context', {}).get('recent_mood'):
                mood = rag_context['emotional_context']['recent_mood']
                rag_parts.append(f"## Hangulat\nAz előző beszélgetések alapján a hangulat: {mood}")
            
            if rag_parts:
                rag_section = "\n".join(rag_parts) + "\n\n"
                self.stats['rag_queries'] += 1
        
        # Bemenet összeállítása
        model_input = f"""{rag_section}Idő: {time_of_day}.
Felhasználó: {user}.
Szándék: {intent}.
{recent_summary}

{user}: {message}

Válaszod:"""
        
        # Token limit ellenőrzés
        estimated_tokens = len(model_input.split())
        if estimated_tokens > self.config['max_context_length']:
            model_input = model_input[:self.config['max_context_length'] * 4] + "..."
        
        return model_input.strip()
    
    # ========== MODELL VÁLASZ FELDOLGOZÁSA ==========
    
    def process_model_response(self, trace_id: str, response: str) -> Dict:
        """Modell válaszának feldolgozása."""
        state = self.active_traces.get(trace_id)
        if not state:
            return {'ERROR': f'Unknown trace_id: {trace_id}'}
        
        action, clean_response = self._detect_action(response)
        
        result_packet = {
            'TRACE': trace_id,
            'RESPONSE': clean_response,
            'ACTION': action if action != 'no_action' else 'NONE',
            'STATUS': 'success'
        }
        
        with self.lock:
            state['status'] = 'completed'
            state['response'] = clean_response
            state['action'] = action
        
        self.scratchpad.write(self.name, 
            {'trace_id': trace_id, 'action': action, 'response_length': len(clean_response)},
            'response_processed'
        )
        
        return result_packet
    
    def _detect_action(self, response: str) -> Tuple[str, str]:
        """Akció detektálás a válasz végén."""
        response = response.strip()
        
        for action, pattern in self.ACTION_PATTERNS.items():
            if re.search(pattern, response):
                if action != 'no_action':
                    clean = re.sub(pattern, '', response).strip()
                    return action, clean
                break
        
        return 'no_action', response
    
    # ========== WEBBEL KAPCSOLATOS METÓDUS (FŐ BELÉPÉSI PONT) ==========
    
    def process_user_message(self, text: str, conversation_id: int, user_id: int = None) -> dict:
        """
        Egyszerű belépési pont a WebApp számára.
        Létrehoz egy kérést, összeállítja a kontextust a Valet segítségével,
        és elindítja a King feldolgozást.
        """
        trace_id = self._generate_uuidv7()
        
        # 1. Felhasználói üzenet mentése
        if self.db:
            try:
                self.db.add_message(conversation_id, "user", text)
            except Exception as e:
                print(f"⚠️ Orchestrator: Üzenet mentési hiba: {e}")
        
        # 2. Belső csomag összeállítása
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
        
        # 3. Beszélgetés előzmények lekérése
        conversation_history = []
        if self.db:
            try:
                messages = self.db.get_messages(conversation_id, limit=self.config['max_history_messages'])
                conversation_history = [
                    {"role": m.get("role", "user"), "content": m.get("content", "")}
                    for m in messages
                ]
            except Exception as e:
                print(f"⚠️ Orchestrator: Előzmények lekérési hiba: {e}")
        
        # 4. RAG kontextus lekérése a Valet-től
        rag_context = {}
        if self.valet and self.config['enable_rag']:
            try:
                context_result = self.valet.prepare_context(packet)
                rag_context = {
                    'graph_context': context_result.get('graph_context', []),
                    'vector_context': context_result.get('vector_context', []),
                    'emotional_context': context_result.get('emotional_context', {}),
                    'summary': context_result.get('summary', ''),
                    'facts': context_result.get('facts', [])
                }
                self.stats['context_builds'] += 1
            except Exception as e:
                print(f"⚠️ Orchestrator: Valet kontextus hiba: {e}")
        
        # 5. King hívása a kontextussal
        king = self.modules.get("king")
        
        if king:
            try:
                # King generálás (átadjuk a kontextust is)
                response = king.generate_response(
                    user_text=text,
                    trace_id=trace_id,
                    conversation_id=conversation_id,
                    conversation_history=conversation_history,
                    rag_context=rag_context
                )
                
                print(f"👑 Orchestrator: King válaszolt: {response[:50]}...")
                
                # Válasz mentése
                if self.db and response:
                    try:
                        self.db.add_message(conversation_id, "assistant", response)
                    except Exception as e:
                        print(f"⚠️ Orchestrator: Válasz mentési hiba: {e}")
                
                # WebApp callback
                if self.webapp_callback:
                    self.webapp_callback(response, conversation_id, trace_id)
                
                # Valet tracking frissítés (ha van)
                if self.valet:
                    try:
                        self.valet.track_message(packet)
                    except Exception as e:
                        print(f"⚠️ Orchestrator: Valet tracking hiba: {e}")
                
                return {"response": response, "trace_id": trace_id}
                
            except Exception as e:
                print(f"❌ Orchestrator: King hiba: {e}")
                error_response = f"Hiba a válaszadás közben: {e}"
                if self.webapp_callback:
                    self.webapp_callback(error_response, conversation_id, trace_id)
                return {"response": error_response, "trace_id": trace_id, "error": str(e)}
        
        error_msg = "A modell nem elérhető."
        print(f"❌ Orchestrator: {error_msg}")
        if self.webapp_callback:
            self.webapp_callback(error_msg, conversation_id, trace_id)
        return {"response": error_msg, "trace_id": trace_id}
    
    # ========== KVK CSOMAG KÉSZÍTÉS ==========
    
    def build_kvk_packet(self, data: Dict) -> str:
        """Dict -> KVK string"""
        pairs = []
        for key, value in data.items():
            if value is not None and value != '':
                key = str(key).strip().upper()
                value = str(value).strip()
                pairs.append(f"{key}{self.KVK_KEY_VALUE_SEP}{value}")
        
        return self.KVK_PAIR_SEP.join(pairs)
    
    # ========== LEKÉRDEZÉSEK ==========
    
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
                'queue_sizes': self.stats['queue_sizes'],
                'rag_queries': self.stats['rag_queries'],
                'context_builds': self.stats['context_builds']
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
    
    s = Scratchpad()
    s.set_state('start_time', time.time())
    s.set_state('user_name', 'user')
    
    orch = Orchestrator(s)
    
    # Teszt KVK parsing
    print("--- KVK parsing teszt ---")
    test_packets = [
        "INTENT:GREET|USER:user",
        "INTENT:QUESTION|USER:user|MESSAGE:Mi a helyzet?",
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