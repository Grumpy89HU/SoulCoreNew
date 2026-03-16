"""
Orchestrator - A Vár központi idegrendszere.

Feladata:
1. Bejövő RawPacket (KVK formátum) fogadása
2. KVK parsing: "INTENT:GREET|USER:GRUMPY" -> dict
3. Kontextus összeállítása a modellnek (tiszta szöveg)
4. Válasz fogadása a modelltől
5. Akciók detektálása (pl. "//save" a válasz végén)
6. Kimenő KVK csomag küldése a többi modulnak
"""

import time
import re
from typing import Dict, List, Any, Optional, Tuple
from collections import deque

class Orchestrator:
    """
    Az Orchestrator egy aktív állapotgép.
    Minden beérkező inger egy életciklust indít el.
    """
    
    # KVK separator-ök
    KVK_PAIR_SEP = '|'
    KVK_KEY_VALUE_SEP = ':'
    
    # Akció detektáló minták (a válasz végén)
    ACTION_PATTERNS = {
        'save_note': r'//save$',
        'delete_note': r'//delete$',
        'search': r'//search',
        'execute': r'//run',
        'no_action': r'.*'  # minden más
    }
    
    def __init__(self, scratchpad):
        self.scratchpad = scratchpad
        self.name = "orchestrator"
        
        # Állapotok
        self.active_traces = {}  # trace_id -> state
        self.recent_packets = deque(maxlen=100)  # utolsó 100 csomag
        
        # Konfiguráció (később configból)
        self.config = {
            'short_term_memory_minutes': 5,
            'max_context_length': 4096,  # token
            'user_name': 'Grumpy'  # alapértelmezett
        }
        
        print("⚙️ Orchestrator: Idegrendszer inicializálva.")
    
    def start(self):
        """Orchestrator indítása"""
        self.scratchpad.set_state('orchestrator_status', 'ready', self.name)
        print("⚙️ Orchestrator: Éber és figyel.")
    
    def stop(self):
        """Orchestrator leállítása"""
        self.scratchpad.set_state('orchestrator_status', 'stopped', self.name)
        print("⚙️ Orchestrator: Leállt.")
    
    # --- BEJÖVŐ CSOMAGOK FELDOLGOZÁSA ---
    
    def process_raw_packet(self, raw_packet: str) -> Optional[Dict]:
        """
        Fő belépési pont.
        raw_packet formátum: "INTENT:GREET|USER:GRUMPY|TIME:MORNING"
        """
        # 1. KVK parsing
        packet_dict = self._parse_kvk(raw_packet)
        if not packet_dict:
            self.scratchpad.write(self.name, 
                {'error': 'Invalid KVK packet', 'raw': raw_packet}, 
                'error'
            )
            return None
        
        # 2. Trace ID generálás (ha nincs)
        if 'TRACE' not in packet_dict:
            trace_id = f"TRACE:{int(time.time())}:{hash(raw_packet) % 10000:04d}"
            packet_dict['TRACE'] = trace_id
        else:
            trace_id = packet_dict['TRACE']
        
        # 3. Context Injection - rövid távú memória lekérése
        short_term = self._get_short_term_context()
        
        # 4. Teljes állapot összeállítása
        state = {
            'trace_id': trace_id,
            'packet': packet_dict,
            'short_term': short_term,
            'timestamp': time.time(),
            'status': 'received'
        }
        
        # 5. Aktív trace-ek közé felvétel
        self.active_traces[trace_id] = state
        self.recent_packets.append({
            'time': time.time(),
            'trace_id': trace_id,
            'packet': packet_dict
        })
        
        # 6. Naplózás
        self.scratchpad.write(self.name, 
            {'trace_id': trace_id, 'intent': packet_dict.get('INTENT')},
            'packet_received'
        )
        
        return state
    
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
        
        return {
            'recent_packets_count': len(recent),
            'recent_intents': [p['packet'].get('INTENT') for p in recent if p['packet'].get('INTENT')],
            'king_status': king_state.get('status', 'unknown'),
            'uptime': time.time() - self.scratchpad.get_state('start_time', time.time())
        }
    
    # --- MODELL BEMENET ÖSSZEÁLLÍTÁSA (TISZTA SZÖVEG) ---
    
    def build_model_input(self, state: Dict) -> str:
        """
        KVK állapotból tiszta szöveges bemenet készítése a modellnek.
        Ezt kapja majd a Király.
        """
        packet = state.get('packet', {})
        intent = packet.get('INTENT', 'UNKNOWN')
        user = packet.get('USER', self.config['user_name'])
        entities = packet.get('ENTITIES', '')
        
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
        
        # Bemenet összeállítása - tiszta szöveg, semmi tag
        model_input = f"""Jelenlegi idő: {time_of_day}.
Felhasználó: {user}.
Szándék: {intent}.
{recent_summary}

{user} üzenete: {packet.get('MESSAGE', '')}

Válaszolj természetesen, mintha egy barátoddal beszélnél."""
        
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
    
    # --- SEGÉDFÜGGVÉNYEK ---
    
    def get_active_traces(self) -> Dict:
        """Aktív trace-ek listája (admin felületnek)"""
        return {
            trace_id: {
                'intent': state['packet'].get('INTENT'),
                'age': time.time() - state['timestamp'],
                'status': state['status']
            }
            for trace_id, state in self.active_traces.items()
            if state['status'] != 'completed'
        }
    
    def cleanup_old_traces(self, max_age_seconds: int = 3600):
        """Régi trace-ek törlése"""
        now = time.time()
        to_delete = [
            tid for tid, state in self.active_traces.items()
            if now - state['timestamp'] > max_age_seconds
        ]
        for tid in to_delete:
            del self.active_traces[tid]

# Teszt
if __name__ == "__main__":
    from scratchpad import Scratchpad
    
    s = Scratchpad()
    s.set_state('start_time', time.time())
    
    orch = Orchestrator(s)
    
    # Teszt KVK parsing
    print("--- KVK parsing teszt ---")
    test_packets = [
        "INTENT:GREET|USER:GRUMPY",
        "INTENT:QUESTION|USER:GRUMPY|MESSAGE:Mi a helyzet?",
        "COMMAND:READ|FILE:notes.txt",
    ]
    
    for p in test_packets:
        print(f"\nBemenet: {p}")
        state = orch.process_raw_packet(p)
        if state:
            print(f"Trace ID: {state['trace_id']}")
            print(f"Parsed: {state['packet']}")
            
            # Modell bemenet generálás
            model_input = orch.build_model_input(state)
            print(f"\nModell bemenet:\n{model_input}")
            
            # Szimulált modell válasz
            if 'GREET' in p:
                model_response = "Szia Grumpy! Hogy vagy? //save"
            else:
                model_response = "Értem. Gondolkodom rajta."
            
            print(f"\nModell válasz: {model_response}")
            
            # Válasz feldolgozás
            result = orch.process_model_response(state['trace_id'], model_response)
            print(f"Feldolgozott: {result}")
            
            # KVK vissza
            kvk_out = orch.build_kvk_packet(result)
            print(f"KVK kimenet: {kvk_out}")
