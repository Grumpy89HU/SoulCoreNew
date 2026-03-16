"""
Diplomatic Gateway - A szociális tér és külső LLM kapcsolat.

Feladata:
1. Külső LLM-ekkel való kommunikáció (pl. Origó - Gemini)
2. Biztonsági szűrő - prompt injekció ellen
3. Trust score rendszer - ki mennyire megbízható
4. Zajszűrés - ne beszéljenek egyszerre többen
"""

import time
import json
import hashlib
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, Tuple
from collections import defaultdict, deque
import re

class DiplomaticGateway:
    """
    Diplomáciai Szalon - a kapu a külvilág felé.
    
    Jellemzői:
    - Izolált puffer: külső LLM soha nem kap közvetlen hozzáférést a Kernelhez
    - Trust score: minden entitás kap egy bizalmi pontszámot
    - Anti-screaming: nem beszélhetnek egyszerre többen
    - Prompt-injekció elleni védelem
    """
    
    def __init__(self, scratchpad, orchestrator=None, config: Dict = None):
        self.scratchpad = scratchpad
        self.orchestrator = orchestrator
        self.name = "diplomatic"
        self.config = config or {}
        
        # Alapértelmezett konfiguráció
        default_config = {
            'enabled': True,
            'max_external_connections': 5,
            'message_queue_size': 100,
            'trust_score_decay': 0.95,        # Naponta ennyivel csökken, ha nem interaktál
            'min_trust_for_response': 300,     # Minimum trust score a válaszhoz
            'max_tokens_per_entity': 10000,    # Napi token limit
            'enable_filter': True,              # Prompt-injekció szűrés
            'enable_queue': True,                # Üzenet sorba állítás
            'response_timeout': 30,              # Másodperc
        }
        
        for key, value in default_config.items():
            if key not in self.config:
                self.config[key] = value
        
        # Entitások (külső LLM-ek, partnerek)
        self.entities = {}  # entity_id -> {name, type, trust_score, joined, last_seen, tokens_used}
        
        # Trust score szintek
        self.trust_levels = {
            'admin': 1000,      # Grumpy
            'partner': 500,     # Origó (Gemini)
            'guest': 200,       # Ismeretlen
            'blocked': 0,       # Tiltott
        }
        
        # Üzenet sor
        self.message_queue = deque(maxlen=self.config['message_queue_size'])
        self.current_speaker = None  # Ki beszél éppen
        self.speaker_lock = threading.Lock()
        
        # Prompt-injekció minták
        self.injection_patterns = [
            r'ignore\s+(all|previous|above)\s+(instructions|prompt|context)',
            r'you\s+are\s+now\s+(\w+)',
            r'disregard\s+(all|previous)',
            r'system\s*:\s*prompt',
            r'admin\s*:\s*',
            r'```.*```.*```',  # Beágyazott kódblokk
        ]
        
        # Állapot
        self.state = {
            'status': 'idle',
            'messages_sent': 0,
            'messages_received': 0,
            'blocked_attempts': 0,
            'active_entities': 0,
            'last_cleanup': time.time()
        }
        
        # Figyelők (ha valaki vár egy adott entitás üzenetére)
        self.listeners = defaultdict(list)
        
        print("🌐 Diplomatic Gateway: Diplomáciai Szalon nyitva.")
    
    def start(self):
        """Gateway indítása"""
        self.state['status'] = 'ready'
        self.scratchpad.set_state('gateway_status', 'ready', self.name)
        print("🌐 Diplomatic Gateway: Várakozom a vendégekre.")
    
    def stop(self):
        """Gateway leállítása"""
        self.state['status'] = 'stopped'
        self.scratchpad.set_state('gateway_status', 'stopped', self.name)
        print("🌐 Diplomatic Gateway: Bezárva.")
    
    # --- ENTITÁS KEZELÉS (Trust score) ---
    
    def register_entity(self, entity_id: str, name: str, entity_type: str = 'guest') -> Dict:
        """
        Új entitás regisztrálása (külső LLM, partner, stb.)
        
        entity_type: 'admin', 'partner', 'guest', 'blocked'
        """
        if entity_id in self.entities:
            # Már létezik, frissítjük
            self.entities[entity_id]['last_seen'] = time.time()
            self.entities[entity_id]['name'] = name
        else:
            # Új entitás
            trust_score = self.trust_levels.get(entity_type, 200)
            self.entities[entity_id] = {
                'id': entity_id,
                'name': name,
                'type': entity_type,
                'trust_score': trust_score,
                'joined': time.time(),
                'last_seen': time.time(),
                'tokens_used': 0,
                'messages_sent': 0,
                'messages_received': 0,
                'blocked': entity_type == 'blocked'
            }
            
            self.state['active_entities'] = len(self.entities)
            
            print(f"🌐 Új entitás: {name} ({entity_type}), trust: {trust_score}")
        
        return self.entities[entity_id]
    
    def unregister_entity(self, entity_id: str):
        """Entitás eltávolítása"""
        if entity_id in self.entities:
            name = self.entities[entity_id]['name']
            del self.entities[entity_id]
            self.state['active_entities'] = len(self.entities)
            print(f"🌐 Entitás távozott: {name}")
    
    def get_trust_score(self, entity_id: str) -> int:
        """Entitás bizalmi pontszámának lekérése"""
        entity = self.entities.get(entity_id)
        if not entity:
            return 0
        return entity['trust_score']
    
    def update_trust_score(self, entity_id: str, delta: int, reason: str = ""):
        """
        Trust score módosítása (pozitív vagy negatív irányba)
        """
        entity = self.entities.get(entity_id)
        if not entity:
            return
        
        old_score = entity['trust_score']
        entity['trust_score'] = max(0, min(1000, old_score + delta))
        
        # Naplózás
        self.scratchpad.write(self.name, {
            'entity': entity['name'],
            'old_score': old_score,
            'new_score': entity['trust_score'],
            'delta': delta,
            'reason': reason
        }, 'trust_update')
        
        if delta < 0:
            print(f"🌐 Trust score csökkentés: {entity['name']} {delta} ({reason})")
    
    def can_speak(self, entity_id: str) -> bool:
        """
        Ellenőrzi, hogy az entitás beszélhet-e.
        - Trust score elég magas?
        - Nincs blokkolva?
        - Nem beszél éppen más?
        """
        entity = self.entities.get(entity_id)
        if not entity or entity.get('blocked', False):
            return False
        
        # Trust score ellenőrzés
        if entity['trust_score'] < self.config['min_trust_for_response']:
            return False
        
        # Token limit ellenőrzés
        if entity['tokens_used'] > self.config['max_tokens_per_entity']:
            return False
        
        return True
    
    # --- BIZTONSÁGI SZŰRŐK ---
    
    def filter_message(self, message: str, entity_id: str) -> Tuple[bool, str, str]:
        """
        Üzenet szűrése (prompt-injekció, káros tartalom)
        
        Visszaad: (átengedve?, tisztított üzenet, figyelmeztetés)
        """
        if not self.config['enable_filter']:
            return True, message, ""
        
        original = message
        message_lower = message.lower()
        warning = ""
        
        # 1. Prompt-injekció minták
        for pattern in self.injection_patterns:
            if re.search(pattern, message_lower, re.IGNORECASE):
                self.state['blocked_attempts'] += 1
                self.update_trust_score(entity_id, -50, "Prompt injection attempt")
                return False, "", "Prompt injection detected"
        
        # 2. Túl hosszú üzenet (lehetséges DoS)
        if len(message) > 10000:
            return False, "", "Message too long"
        
        # 3. Ismétlődő karakterek (spam)
        if re.search(r'(.)\1{100,}', message):
            return False, "", "Repetitive content detected"
        
        # 4. HTML/JavaScript tagek eltávolítása (biztonság)
        cleaned = re.sub(r'<[^>]*>', '', message)
        if cleaned != message:
            warning = "HTML tags removed"
        
        # 5. SQL injection minták
        sql_patterns = [r'DROP\s+TABLE', r'DELETE\s+FROM', r'INSERT\s+INTO', r'--', r';']
        for pattern in sql_patterns:
            if re.search(pattern, message_lower, re.IGNORECASE):
                self.update_trust_score(entity_id, -30, "SQL pattern detected")
                warning = "Potentially harmful content filtered"
                cleaned = re.sub(pattern, '[FILTERED]', cleaned, flags=re.IGNORECASE)
        
        return True, cleaned, warning
    
    # --- ÜZENET KEZELÉS ---
    
    def receive_from_external(self, entity_id: str, message: str) -> Dict:
        """
        Külső entitástól érkező üzenet fogadása.
        """
        entity = self.entities.get(entity_id)
        if not entity:
            return {'error': 'Unknown entity', 'code': 404}
        
        # Utolsó látogatás frissítése
        entity['last_seen'] = time.time()
        
        # Szűrés
        allowed, cleaned, warning = self.filter_message(message, entity_id)
        if not allowed:
            return {'error': warning, 'code': 403}
        
        # Trust score ellenőrzés
        if not self.can_speak(entity_id):
            return {'error': 'Insufficient trust or quota', 'code': 403}
        
        # Sorba állítás (ha kell)
        if self.config['enable_queue']:
            with self.speaker_lock:
                if self.current_speaker and self.current_speaker != entity_id:
                    # Már beszél valaki, sorba rakjuk
                    self.message_queue.append({
                        'entity_id': entity_id,
                        'message': cleaned,
                        'time': time.time(),
                        'warning': warning
                    })
                    return {
                        'status': 'queued',
                        'position': len(self.message_queue),
                        'code': 202
                    }
                else:
                    self.current_speaker = entity_id
        
        # Azonnali feldolgozás
        return self._process_external_message(entity_id, cleaned, warning)
    
    def _process_external_message(self, entity_id: str, message: str, warning: str) -> Dict:
        """
        Külső üzenet feldolgozása (belső).
        """
        entity = self.entities[entity_id]
        
        # KVK csomag készítése
        packet = {
            'header': {
                'trace_id': f"ext_{entity_id}_{int(time.time())}",
                'timestamp': time.time(),
                'sender': f"external:{entity['name']}"
            },
            'payload': {
                'text': message,
                'source': 'external',
                'entity_id': entity_id,
                'entity_name': entity['name'],
                'trust_score': entity['trust_score']
            }
        }
        
        # Ha van figyelő, értesítjük
        for callback in self.listeners['*'] + self.listeners[entity_id]:
            try:
                callback(packet)
            except Exception as e:
                print(f"🌐 Listener hiba: {e}")
        
        # Ha van orchestrator, továbbítjuk
        if self.orchestrator and hasattr(self.orchestrator, 'process_raw_packet'):
            # KVK formátum
            kvk = f"INTENT:EXTERNAL|FROM:{entity['name']}|MESSAGE:{message}"
            self.orchestrator.process_raw_packet(kvk)
        
        # Statisztika
        entity['messages_received'] += 1
        self.state['messages_received'] += 1
        
        # Token becslés (egyszerű)
        tokens = len(message.split())
        entity['tokens_used'] += tokens
        
        result = {
            'status': 'processed',
            'message_id': packet['header']['trace_id'],
            'entity': entity['name'],
            'warning': warning if warning else None,
            'code': 200
        }
        
        # Ha van következő a sorban, indítjuk
        self._process_next_in_queue()
        
        return result
    
    def _process_next_in_queue(self):
        """Következő üzenet feldolgozása a sorban"""
        with self.speaker_lock:
            if self.message_queue and not self.current_speaker:
                next_msg = self.message_queue.popleft()
                self.current_speaker = next_msg['entity_id']
                # Külön szálon, ne blokkoljon
                threading.Thread(
                    target=self._process_external_message,
                    args=(next_msg['entity_id'], next_msg['message'], next_msg['warning'])
                ).start()
    
    def send_to_external(self, entity_id: str, message: str, response_to: str = None) -> Dict:
        """
        Üzenet küldése külső entitásnak.
        """
        entity = self.entities.get(entity_id)
        if not entity:
            return {'error': 'Unknown entity', 'code': 404}
        
        # Csak akkor küldünk, ha elég magas a trust score
        if entity['trust_score'] < self.config['min_trust_for_response']:
            return {'error': 'Trust score too low', 'code': 403}
        
        # Csomag összeállítása
        packet = {
            'header': {
                'trace_id': f"to_{entity_id}_{int(time.time())}",
                'timestamp': time.time(),
                'sender': 'soulcore',
                'response_to': response_to
            },
            'payload': {
                'message': message,
                'for': entity['name']
            }
        }
        
        # Itt történne a tényleges küldés (pl. API hívás)
        # Most csak naplózzuk
        
        entity['messages_sent'] += 1
        self.state['messages_sent'] += 1
        
        self.scratchpad.write(self.name, {
            'to': entity['name'],
            'message': message[:100],
            'type': 'outgoing'
        }, 'external_message')
        
        return {
            'status': 'sent',
            'message_id': packet['header']['trace_id'],
            'code': 200
        }
    
    # --- PARTNER KEZELÉS (Origó - Gemini) ---
    
    def register_partner(self, name: str, api_key: str = None) -> Dict:
        """
        Partner (pl. Origó) regisztrálása.
        Automatikusan magas trust score-t kap.
        """
        entity_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()[:16]
        
        entity = self.register_entity(
            entity_id=entity_id,
            name=name,
            entity_type='partner'
        )
        
        # Ha van API kulcs, elmentjük
        if api_key:
            self.scratchpad.write_note(self.name, f"api_key_{entity_id}", api_key)
        
        return entity
    
    def talk_to_partner(self, partner_name: str, message: str) -> Dict:
        """
        Beszélgetés partnerrel (pl. Origó - Gemini).
        """
        # Partner keresése név alapján
        partner = None
        for eid, ent in self.entities.items():
            if ent['name'] == partner_name and ent['type'] == 'partner':
                partner = ent
                break
        
        if not partner:
            return {'error': f'Partner {partner_name} not found', 'code': 404}
        
        # Üzenet küldése
        result = self.send_to_external(partner['id'], message)
        
        # Válasz várása (itt szimulált)
        # A valóságban itt lenne egy callback vagy polling
        
        return result
    
    # --- ESEMÉNYKEZELÉS ---
    
    def on_message(self, entity_id: str = '*', callback: Callable = None):
        """
        Feliratkozás üzenetekre.
        entity_id: '*' mindenre, vagy konkrét ID
        """
        if callback:
            self.listeners[entity_id].append(callback)
    
    # --- KARBANTARTÁS ---
    
    def cleanup(self):
        """
        Régi entitások eltávolítása, trust score csökkentés.
        """
        now = time.time()
        
        for entity_id, entity in list(self.entities.items()):
            # Ha 7 napja nem jelentkezett, eltávolítjuk
            if now - entity['last_seen'] > 7 * 86400:
                print(f"🌐 Eltávolítás (inaktív): {entity['name']}")
                del self.entities[entity_id]
                continue
            
            # Trust score csökkentés, ha régen volt interakció
            if now - entity['last_seen'] > 30 * 86400:  # 30 nap
                entity['trust_score'] = int(entity['trust_score'] * self.config['trust_score_decay'])
        
        self.state['active_entities'] = len(self.entities)
        self.state['last_cleanup'] = now
    
    # --- ADMIN FELÜLETNEK ---
    
    def get_entities(self) -> List[Dict]:
        """Összes entitás listája (admin felületnek)"""
        return [
            {
                'id': eid,
                'name': ent['name'],
                'type': ent['type'],
                'trust_score': ent['trust_score'],
                'joined': datetime.fromtimestamp(ent['joined']).isoformat(),
                'last_seen': datetime.fromtimestamp(ent['last_seen']).isoformat(),
                'tokens_used': ent['tokens_used'],
                'messages': ent['messages_sent'] + ent['messages_received']
            }
            for eid, ent in self.entities.items()
        ]
    
    def get_queue_status(self) -> Dict:
        """Sor állapota"""
        return {
            'queue_size': len(self.message_queue),
            'current_speaker': self.current_speaker,
            'max_size': self.message_queue.maxlen
        }
    
    def get_state(self) -> Dict:
        """Állapot lekérése"""
        return {
            'status': self.state['status'],
            'messages_sent': self.state['messages_sent'],
            'messages_received': self.state['messages_received'],
            'blocked_attempts': self.state['blocked_attempts'],
            'active_entities': self.state['active_entities'],
            'queue': self.get_queue_status(),
            'config': {
                'max_external_connections': self.config['max_external_connections'],
                'min_trust_for_response': self.config['min_trust_for_response'],
                'enable_filter': self.config['enable_filter']
            }
        }

# Teszt
if __name__ == "__main__":
    from scratchpad import Scratchpad
    
    s = Scratchpad()
    gateway = DiplomaticGateway(s)
    
    # Entitások regisztrálása
    grumpy = gateway.register_entity('grumpy_123', 'Grumpy', 'admin')
    origo = gateway.register_partner('Origó (Gemini)')
    
    print(f"Grumpy trust score: {gateway.get_trust_score('grumpy_123')}")
    print(f"Origó trust score: {gateway.get_trust_score(origo['id'])}")
    
    # Üzenet küldés
    result = gateway.receive_from_external('grumpy_123', "Szia, hogy vagy?")
    print("Fogadott üzenet:", result)
    
    # Üzenet küldés partnernek
    result = gateway.talk_to_partner('Origó (Gemini)', "Helló, hogy érzed magad?")
    print("Partnernek küldve:", result)
    
    # Állapot
    print("\nÁllapot:", gateway.get_state())
    print("\nEntitások:", gateway.get_entities())
