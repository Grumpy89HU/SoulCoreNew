"""
Valet (Lakáj) - A memória-logisztika és a Tények Őre.

Feladata:
1. Rövid távú memória (Scratchpad) kezelése és összegzése
2. Hosszú távú memória előkészítése (Vault: Gráf + Vektor)
3. RAG 2.1 - Kétkulcsos keresés (vektoros + gráf fázis)
4. Kontextus összeállítása a King számára (Context Briefing)
5. Hallucináció-gát - tények ellenőrzése (Active Validation)
6. Context Compression - Scratchpad titka (token-takarékosság)
"""

import time
import re
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union
from collections import defaultdict, Counter
from pathlib import Path

# Opcionális importok (vektoros kereséshez)
try:
    import numpy as np
    NP_AVAILABLE = True
except ImportError:
    NP_AVAILABLE = False

class Valet:
    """
    A Lakáj - a memória őre.
    
    Felépítése:
    - Rövid táv: Scratchpad (gyors memória)
    - Hosszú táv: Vektor DB (később) + Gráf DB (később)
    
    RAG 2.1:
    1. Vektoros fázis (Qdrant) - szemantikai keresés
    2. Gráf fázis (Neo4j) - érzelmi és szociális kapcsolatok
    """
    
    def __init__(self, scratchpad, config: Dict = None):
        self.scratchpad = scratchpad
        self.name = "valet"
        self.config = config or {}
        
        # Konfiguráció (alapértékek)
        default_config = {
            'max_context_tokens': 1500,      # Maximum kontextus hossz (token)
            'max_recent_messages': 5,         # Ennyi üzenet megy a kontextusba
            'summary_length': 200,             # Összefoglaló hossza (karakter)
            'enable_tracking': True,           # Tracking bekapcsolása
            'enable_validation': True,         # Tényellenőrzés bekapcsolása
            'enable_rag': True,                 # RAG keresés bekapcsolása
            'forget_after_days': 30,           # Ennyi nap után "archiválás"
            'important_threshold': 0.7,         # Fontossági küszöb
            'vector_search_limit': 5,           # Ennyi vektoros találat
            'graph_search_limit': 3,            # Ennyi gráf kapcsolat
            'emotional_weight': 0.3,            # Érzelmi töltés súlya a keresésben
            'context_compression': True,        # Kontextus tömörítés bekapcsolása
        }
        
        for key, value in default_config.items():
            if key not in self.config:
                self.config[key] = value
        
        # Tracking adatok (ki miről beszélt, mikor)
        self.tracking = {
            'topics': defaultdict(int),        # Témák gyakorisága
            'entities': defaultdict(int),       # Entitások gyakorisága
            'last_mentioned': {},                # Utolsó említés (időbélyeg)
            'relationships': defaultdict(set),   # Kapcsolatok (ki-mihez kötődik)
            'emotional_charge': defaultdict(float),  # Érzelmi töltés (-1.0 - +1.0)
            'importance': defaultdict(float),     # Fontosság (0.0 - 1.0)
        }
        
        # Emlékek gyorsítótára (Vault)
        self.memory_cache = {}
        self.memory_cache_ttl = 3600  # 1 óra
        
        # Állapot (bővítve hibák tárolásával)
        self.state = {
            'status': 'idle',
            'processed_messages': 0,
            'summaries_created': 0,
            'warnings_issued': 0,
            'errors': [],
            'rag_searches': 0,
            'context_compressions': 0,
            'last_cleanup': time.time()
        }
        
        print("👔 Valet: Lakáj ébred. Őrzöm a tényeket.")
    
    def start(self):
        """Valet indítása"""
        self.state['status'] = 'ready'
        self.scratchpad.set_state('valet_status', 'ready', self.name)
        print("👔 Valet: Készen állok.")
    
    def stop(self):
        """Valet leállítása"""
        self.state['status'] = 'stopped'
        self.scratchpad.set_state('valet_status', 'stopped', self.name)
        print("👔 Valet: Leállt.")
    
    # --- KONTEXTUS ÖSSZEÁLLÍTÁS (Context Briefing) ---
    
    def prepare_context(self, intent_packet: Dict) -> Dict[str, Any]:
        """
        Kontextus összeállítása a King számára.
        Ezt kapja majd a King a prompt építéshez.
        
        Visszaad:
        {
            'summary': 'rövid összefoglaló',
            'facts': ['tény1', 'tény2'],
            'recent': ['üzenet1', 'üzenet2'],
            'warnings': ['figyelmeztetés1'],
            'tracking': {'topics': {...}, 'entities': {...}},
            'rag_results': ['találat1', 'találat2'],
            'emotional_context': {'charge': 0.5, 'topic': '...'}
        }
        """
        # Alapértelmezett context (mindenképpen dict)
        context = {
            'summary': '',
            'facts': [],
            'recent': [],
            'warnings': [],
            'tracking': {},
            'rag_results': [],
            'emotional_context': {},
            'timestamp': time.time()
        }
        
        try:
            # Ellenőrizzük az intent_packet típusát
            if not isinstance(intent_packet, dict):
                error_msg = f"prepare_context: intent_packet nem dict, hanem {type(intent_packet)}"
                self.state['errors'].append(error_msg)
                return context
            
            # 1. Rövid távú memória (Scratchpad)
            scratchpad_summary = self.scratchpad.get_summary()
            
            # 2. Utolsó N üzenet - ROBOSZTUS KEZELÉS (itt volt a hiba!)
            recent = self.scratchpad.read(limit=self.config['max_recent_messages'])
            context['recent'] = self._process_recent_messages(recent)
            
            # 3. Fontos tények kinyerése
            facts = self._extract_facts(recent)
            context['facts'] = facts[:5]  # Max 5 tény
            
            # 4. RAG keresés (ha be van kapcsolva)
            if self.config['enable_rag']:
                rag_results = self._rag_search(intent_packet, facts)
                context['rag_results'] = rag_results[:3]  # Max 3 találat
            
            # 5. Összefoglaló készítése (Context Compression)
            if self.config['context_compression']:
                context['summary'] = self._create_compressed_summary(intent_packet, facts, context['rag_results'])
                self.state['context_compressions'] += 1
            else:
                context['summary'] = self._create_summary(intent_packet, facts)
            
            # 6. Tracking adatok
            if self.config['enable_tracking']:
                context['tracking'] = {
                    'topics': dict(list(self.tracking['topics'].items())[:5]),
                    'last_mentioned': self._format_last_mentioned(self.tracking['last_mentioned']),
                    'emotional_charge': dict(list(self.tracking['emotional_charge'].items())[:5])
                }
                
                # Érzelmi kontextus az aktuális témához
                current_topic = intent_packet.get('payload', {}).get('intent', {}).get('class', 'unknown')
                if current_topic in self.tracking['emotional_charge']:
                    context['emotional_context'] = {
                        'topic': current_topic,
                        'charge': self.tracking['emotional_charge'][current_topic]
                    }
            
            # 7. Aktuális intent figyelmeztetések (Hallucináció-gát)
            if self.config['enable_validation']:
                warning = self._validate_intent(intent_packet, facts, context['rag_results'])
                if warning:
                    context['warnings'].append(warning)
                    self.state['warnings_issued'] += 1
                    
        except Exception as e:
            error_msg = f"prepare_context általános hiba: {e}"
            self.state['errors'].append(error_msg)
            print(f"👔 Valet hiba: {error_msg}")
        
        return context
    
    def _process_recent_messages(self, recent_entries: List) -> List[str]:
        """
        Utolsó üzenetek feldolgozása - ROBOSZTUS VERZIÓ.
        Ez a függvény kezeli a nem dict típusú bejegyzéseket is.
        """
        processed = []
        
        for entry in recent_entries:
            try:
                # Ha string, akkor nem tudjuk feldolgozni, de naplózzuk
                if isinstance(entry, str):
                    self.state['errors'].append(f"String entry a scratchpad-ben: {entry[:100]}")
                    continue
                
                # Ha nem dict, akkor sem
                if not isinstance(entry, dict):
                    self.state['errors'].append(f"Érvénytelen entry típus: {type(entry)}")
                    continue
                
                # Csak a response típusúakat vesszük
                if entry.get('type') == 'response':
                    sender = entry.get('module', 'unknown')
                    content = entry.get('content', {})
                    
                    # Biztonságos szövegkinyerés
                    text = self._safe_extract_text(content)
                    
                    if text:
                        processed.append(f"{sender}: {text[:100]}")
                        
            except Exception as e:
                self.state['errors'].append(f"Hiba a recent üzenet feldolgozásakor: {e}")
                continue
        
        return processed
    
    def _safe_extract_text(self, content: Any) -> str:
        """
        Biztonságos szövegkinyerés bármilyen típusú content-ből.
        """
        if content is None:
            return ""
        
        if isinstance(content, str):
            return content
        
        if isinstance(content, dict):
            # Többféle kulcs lehet
            if 'response' in content:
                return str(content['response'])
            elif 'text' in content:
                return str(content['text'])
            elif 'content' in content:
                return self._safe_extract_text(content['content'])
            else:
                return str(content)
        
        if isinstance(content, (list, tuple)):
            return " ".join([self._safe_extract_text(item) for item in content[:3]])
        
        # Minden más esetben stringgé alakítjuk
        try:
            return str(content)
        except:
            return ""
    
    def _extract_facts(self, recent_entries: List) -> List[str]:
        """
        Tények kinyerése a legutóbbi üzenetekből - ROBOSZTUS VERZIÓ.
        """
        facts = []
        
        for entry in recent_entries:
            try:
                # Ha string, kihagyjuk
                if isinstance(entry, str):
                    continue
                    
                if not isinstance(entry, dict):
                    continue
                
                content = entry.get('content', {})
                text = self._safe_extract_text(content)
                
                if not text:
                    continue
                
                # Tények keresése (pl. "az X az Y", "X van", stb.)
                patterns = [
                    (r'(?:az?|the)\s+(\w+)\s+(?:van|nincs|lesz|volt|is|is not)', 'állapot'),
                    (r'(\w+)\s+(?:az?|a|the)\s+(\w+)', 'azonosság'),
                    (r'(\d{4})[-.](\d{1,2})[-.](\d{1,2})', 'dátum'),
                    (r'(?:szeret|love|like|prefer)\s+(\w+)', 'preferencia'),
                    (r'(?:nem|not)\s+(?:szeret|love|like)\s+(\w+)', 'negatív preferencia'),
                ]
                
                for pattern, fact_type in patterns:
                    try:
                        matches = re.findall(pattern, text, re.IGNORECASE)
                        for match in matches:
                            if isinstance(match, tuple):
                                fact = f"{fact_type}: {' '.join(match)}"
                            else:
                                fact = f"{fact_type}: {match}"
                            if fact not in facts:
                                facts.append(fact)
                    except Exception as e:
                        self.state['errors'].append(f"Regex hiba a mintában '{pattern}': {e}")
                        continue
                        
            except Exception as e:
                self.state['errors'].append(f"Hiba a ténykinyerésben: {e}")
                continue
        
        return facts
    
    def _rag_search(self, intent_packet: Dict, facts: List[str]) -> List[str]:
        """
        RAG 2.1 - Kétkulcsos keresés.
        
        1. Vektoros fázis: szemantikai keresés a Vault-ban
        2. Gráf fázis: érzelmi és szociális kapcsolatok keresése
        """
        results = []
        self.state['rag_searches'] += 1
        
        try:
            payload = intent_packet.get('payload', {})
            text = payload.get('text', '')
            intent = payload.get('intent', {}).get('class', 'unknown')
            
            # 1. Vektoros keresés (szemantikai)
            vector_results = self._vector_search(text, facts)
            
            # 2. Gráf keresés (kapcsolatok)
            graph_results = self._graph_search(intent, text)
            
            # 3. Eredmények összefésülése (súlyozva)
            combined = []
            
            for res in vector_results:
                combined.append(f"[Szemantikai] {res}")
            
            for res in graph_results:
                combined.append(f"[Kapcsolat] {res}")
            
            results = combined
            
        except Exception as e:
            self.state['errors'].append(f"RAG keresési hiba: {e}")
        
        return results
    
    def _vector_search(self, text: str, facts: List[str]) -> List[str]:
        """
        Vektoros keresés (szemantikai).
        Itt majd a Qdrant vagy más vektor DB jön.
        Jelenleg egyszerű kulcsszavas helyettesítés.
        """
        results = []
        
        # Ha nincs vektoros keresés, akkor egyszerű kulcsszavas keresés a memóriában
        try:
            # Az utolsó emlékek között keresünk
            notes = self.scratchpad.read_all_notes()
            
            search_terms = text.lower().split()[:5]  # Első 5 szó
            
            for module, notes_dict in notes.items():
                for key, note in notes_dict.items():
                    if isinstance(note, dict):
                        note_text = str(note.get('value', ''))
                    else:
                        note_text = str(note)
                    
                    note_lower = note_text.lower()
                    
                    # Ha bármelyik keresési kifejezés szerepel
                    if any(term in note_lower for term in search_terms if len(term) > 3):
                        results.append(f"{module}: {note_text[:100]}")
                        if len(results) >= self.config['vector_search_limit']:
                            break
                
                if len(results) >= self.config['vector_search_limit']:
                    break
                    
        except Exception as e:
            self.state['errors'].append(f"Vektoros keresési hiba: {e}")
        
        return results
    
    def _graph_search(self, topic: str, text: str) -> List[str]:
        """
        Gráf keresés (kapcsolatok, érzelmi töltés).
        Itt majd a Neo4j jön.
        Jelenleg a tracking adatokat használja.
        """
        results = []
        
        try:
            # Kapcsolatok keresése a tracking-ben
            if topic in self.tracking['relationships']:
                related = list(self.tracking['relationships'][topic])[:3]
                for rel in related:
                    charge = self.tracking['emotional_charge'].get(rel, 0)
                    charge_str = "😊" if charge > 0.3 else "😐" if charge > -0.3 else "😞"
                    results.append(f"{rel} {charge_str}")
            
            # Érzelmi töltés az aktuális témához
            if topic in self.tracking['emotional_charge']:
                charge = self.tracking['emotional_charge'][topic]
                if abs(charge) > 0.5:
                    mood = "pozitív" if charge > 0 else "negatív"
                    results.append(f"Érzelmi kontextus: {mood} ({charge:.2f})")
                    
        except Exception as e:
            self.state['errors'].append(f"Gráf keresési hiba: {e}")
        
        return results
    
    def _create_summary(self, intent_packet: Dict, facts: List[str]) -> str:
        """
        Rövid összefoglaló készítése a King számára.
        """
        try:
            payload = intent_packet.get('payload', {})
            if not isinstance(payload, dict):
                payload = {}
            
            text = payload.get('text', '')
            if not isinstance(text, str):
                text = str(text)
            
            # Ha nincs tény, egyszerű összefoglaló
            if not facts:
                return f"User üzenete: {text[:100]}..."
            
            # Tények összefoglalása
            fact_summary = ". ".join(str(f) for f in facts[:3])
            
            return f"User: {text[:50]}... Előzmények: {fact_summary}"
            
        except Exception as e:
            self.state['errors'].append(f"Hiba az összefoglaló készítésében: {e}")
            return "User üzenetet küldött."
    
    def _create_compressed_summary(self, intent_packet: Dict, facts: List[str], rag_results: List[str]) -> str:
        """
        Context Compression - Tömörített összefoglaló (token-takarékos).
        Csak a legfontosabb információkat tartja meg.
        """
        try:
            payload = intent_packet.get('payload', {})
            text = payload.get('text', '') if isinstance(payload, dict) else ""
            
            # 1. Az utolsó 5 tény (ha van)
            fact_part = ""
            if facts:
                # Csak a legfontosabb tények (fontosság alapján)
                important_facts = sorted(
                    [(f, self.tracking['importance'].get(f, 0.5)) for f in facts[:5]],
                    key=lambda x: x[1],
                    reverse=True
                )[:2]
                if important_facts:
                    fact_part = "Tények: " + "; ".join([f[0] for f in important_facts]) + ". "
            
            # 2. RAG eredmények (ha vannak)
            rag_part = ""
            if rag_results:
                rag_part = "Kapcsolódó: " + "; ".join(rag_results[:2]) + ". "
            
            # 3. Érzelmi kontextus (ha van)
            emotional_part = ""
            current_topic = payload.get('intent', {}).get('class', 'unknown') if isinstance(payload, dict) else 'unknown'
            if current_topic in self.tracking['emotional_charge']:
                charge = self.tracking['emotional_charge'][current_topic]
                if abs(charge) > 0.3:
                    mood = "😊" if charge > 0 else "😞"
                    emotional_part = f"Hangulat: {mood} "
            
            # Végeredmény összeállítása
            summary = f"{emotional_part}{fact_part}{rag_part}Üzenet: {text[:30]}..."
            
            return summary[:self.config['summary_length']]
            
        except Exception as e:
            return self._create_summary(intent_packet, facts)
    
    def _format_last_mentioned(self, last_mentioned: Dict) -> Dict:
        """
        Utolsó említések formázása olvashatóvá.
        """
        formatted = {}
        now = time.time()
        
        for key, timestamp in list(last_mentioned.items())[:10]:
            delta = now - timestamp
            if delta < 60:
                formatted[key] = f"{int(delta)} másodperce"
            elif delta < 3600:
                formatted[key] = f"{int(delta/60)} perce"
            elif delta < 86400:
                formatted[key] = f"{int(delta/3600)} órája"
            else:
                formatted[key] = f"{int(delta/86400)} napja"
        
        return formatted
    
    def _validate_intent(self, intent_packet: Dict, facts: List[str], rag_results: List[str]) -> Optional[str]:
        """
        Intent ellenőrzése a tények alapján (Hallucináció-gát).
        Ha ellentmondást talál, figyelmeztetést ad.
        """
        try:
            payload = intent_packet.get('payload', {})
            if not isinstance(payload, dict):
                return None
                
            text = payload.get('text', '')
            if not isinstance(text, str):
                text = str(text)
            
            # 1. Ellentmondás a tényekkel
            for fact in facts:
                if not isinstance(fact, str):
                    continue
                    
                # Ha a tény tagadást tartalmaz
                if 'nincs' in fact or 'nem' in fact or 'not' in fact:
                    # És a szöveg állítja az ellenkezőjét
                    fact_words = fact.split()
                    for word in fact_words[1:3]:
                        if word and word in text:
                            return f"Ellentmondás a korábbiakkal: {fact[:50]}"
            
            # 2. Ellenőrzés a RAG eredményekkel
            for rag in rag_results:
                if isinstance(rag, str) and 'ellentmondás' in rag.lower():
                    return f"RAG ellentmondás: {rag[:50]}"
                
        except Exception as e:
            self.state['errors'].append(f"Hiba az intent validálásában: {e}")
        
        return None
    
    # --- MEMÓRIA KEZELÉS ---
    
    def remember(self, key: str, value: Any, importance: float = 0.5, emotional_charge: float = 0.0):
        """
        Fontos információ elmentése a hosszú távú memóriába.
        """
        try:
            # Fontosság alapján döntjük el, hogy megy-e a hosszú távúba
            if importance > self.config['important_threshold']:
                # Hosszú távú memória (később)
                self.scratchpad.write_note(self.name, f"longterm_{key}", {
                    'value': value,
                    'importance': importance,
                    'emotional_charge': emotional_charge,
                    'time': time.time()
                })
                
                # Tracking frissítés
                if isinstance(key, str):
                    self.tracking['importance'][key] = importance
                    self.tracking['emotional_charge'][key] = emotional_charge
            
            # Mindig megy a rövid távúba
            self.scratchpad.write_note(self.name, key, value)
            
        except Exception as e:
            self.state['errors'].append(f"Hiba az emlékezésben: {e}")
    
    def recall(self, key: str, default=None):
        """Információ előhívása a memóriából"""
        try:
            # Először rövid táv
            value = self.scratchpad.read_note(self.name, key)
            if value is not None:
                return value
            
            # Aztán hosszú táv (később)
            value = self.scratchpad.read_note(self.name, f"longterm_{key}")
            if value is not None:
                if isinstance(value, dict):
                    return value.get('value') if isinstance(value, dict) else value
                return value
        except Exception as e:
            self.state['errors'].append(f"Hiba a felidézésben: {e}")
        
        return default
    
    # --- TRACKING (ki miről beszélt) ---
    
    def track_message(self, intent_packet: Dict):
        """
        Üzenet nyomon követése.
        Kinyeri a témákat és entitásokat, érzelmi töltést számol.
        """
        if not self.config['enable_tracking']:
            return
        
        try:
            payload = intent_packet.get('payload', {})
            if not isinstance(payload, dict):
                return
                
            text = payload.get('text', '')
            intent = payload.get('intent', {}).get('class', 'unknown')
            
            # Téma hozzáadása
            self.tracking['topics'][intent] += 1
            self.tracking['last_mentioned'][intent] = time.time()
            
            # Érzelmi töltés becslése (egyszerű szólista alapján)
            emotional_charge = self._estimate_emotional_charge(text)
            self.tracking['emotional_charge'][intent] = (
                self.tracking['emotional_charge'].get(intent, 0) * 0.7 + emotional_charge * 0.3
            )
            
            # Entitások keresése (ha van)
            entities = payload.get('entities', [])
            for entity in entities:
                if isinstance(entity, dict):
                    etype = entity.get('type', 'unknown')
                    evalue = entity.get('value', '')
                    key = f"{etype}:{evalue}"
                    self.tracking['entities'][key] += 1
                    self.tracking['last_mentioned'][key] = time.time()
                    
                    # Kapcsolat a témával
                    self.tracking['relationships'][intent].add(key)
                    
                    # Fontosság számítás
                    importance = min(1.0, 0.3 + (self.tracking['entities'][key] * 0.1))
                    self.tracking['importance'][key] = importance
                    
        except Exception as e:
            self.state['errors'].append(f"Hiba a trackelésben: {e}")
    
    def _estimate_emotional_charge(self, text: str) -> float:
        """
        Érzelmi töltés becslése szöveg alapján (-1.0 - +1.0).
        """
        if not isinstance(text, str):
            return 0.0
        
        text_lower = text.lower()
        
        # Pozitív szavak
        positive_words = ['köszönöm', 'szuper', 'jó', 'remek', 'nagyszerű', 'örülök', 
                          'thank', 'great', 'good', 'excellent', 'love', 'like']
        
        # Negatív szavak
        negative_words = ['rossz', 'szar', 'utálom', 'nem jó', 'hiba', 'baj van',
                          'bad', 'terrible', 'awful', 'hate', 'error', 'problem']
        
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        total = positive_count + negative_count
        if total == 0:
            return 0.0
        
        return (positive_count - negative_count) / total
    
    def get_tracking(self, topic: str = None) -> Dict:
        """Tracking adatok lekérése"""
        try:
            if topic:
                return {
                    'count': self.tracking['topics'].get(topic, 0),
                    'last': self.tracking['last_mentioned'].get(topic),
                    'related': list(self.tracking['relationships'].get(topic, [])),
                    'emotional_charge': self.tracking['emotional_charge'].get(topic, 0.0),
                    'importance': self.tracking['importance'].get(topic, 0.5)
                }
            
            return {
                'topics': dict(self.tracking['topics']),
                'entities': dict(self.tracking['entities']),
                'relationships': {
                    k: list(v) for k, v in self.tracking['relationships'].items()
                },
                'emotional_charge': dict(self.tracking['emotional_charge']),
                'importance': dict(self.tracking['importance'])
            }
        except Exception as e:
            self.state['errors'].append(f"Hiba a tracking lekérésében: {e}")
            return {}
    
    # --- KARBANTARTÁS ---
    
    def cleanup(self, force: bool = False):
        """
        Régi memória tisztítása.
        - Ha egy téma/téma régi, csökkentjük a súlyát
        - Ha nagyon régi, "archiváljuk"
        """
        try:
            now = time.time()
            forget_after = self.config['forget_after_days'] * 86400
            
            # Régi témák súlyozása
            for topic, last_time in list(self.tracking['last_mentioned'].items()):
                age = now - last_time
                if age > forget_after:
                    # Archiválás (később)
                    if topic in self.tracking['topics']:
                        del self.tracking['topics'][topic]
                    del self.tracking['last_mentioned'][topic]
                    if topic in self.tracking['relationships']:
                        del self.tracking['relationships'][topic]
                    if topic in self.tracking['emotional_charge']:
                        del self.tracking['emotional_charge'][topic]
                    if topic in self.tracking['importance']:
                        del self.tracking['importance'][topic]
                elif age > forget_after // 2:
                    # Súly csökkentése
                    if topic in self.tracking['topics']:
                        self.tracking['topics'][topic] = max(
                            1, self.tracking['topics'][topic] // 2
                        )
                    if topic in self.tracking['importance']:
                        self.tracking['importance'][topic] *= 0.8
            
            self.state['last_cleanup'] = now
            self.state['processed_messages'] += 1
            
        except Exception as e:
            self.state['errors'].append(f"Hiba a cleanup során: {e}")
    
    # --- ÁLLAPOT ---
    
    def get_state(self) -> Dict:
        """Állapot lekérése"""
        return {
            'status': self.state['status'],
            'processed': self.state['processed_messages'],
            'summaries': self.state['summaries_created'],
            'warnings': self.state['warnings_issued'],
            'rag_searches': self.state['rag_searches'],
            'context_compressions': self.state['context_compressions'],
            'errors': self.state['errors'][-10:],  # Utolsó 10 hiba
            'tracking': {
                'topics': len(self.tracking['topics']),
                'entities': len(self.tracking['entities']),
                'relationships': sum(len(v) for v in self.tracking['relationships'].values())
            },
            'config': self.config
        }

# Teszt
if __name__ == "__main__":
    from scratchpad import Scratchpad
    
    s = Scratchpad()
    valet = Valet(s)
    
    # Teszt intent
    test_intent = {
        'payload': {
            'text': 'Holnap megyek Budapestre a konferenciára',
            'intent': {'class': 'travel'},
            'entities': [
                {'type': 'LOCATION', 'value': 'Budapest'},
                {'type': 'DATE', 'value': 'holnap'}
            ]
        }
    }
    
    # Tracking
    valet.track_message(test_intent)
    
    # Kontextus
    context = valet.prepare_context(test_intent)
    print("Kontextus:", json.dumps(context, indent=2, default=str))
    
    # Állapot
    print("\nÁllapot:", valet.get_state())