"""
Valet (Lakáj) - A memória-logisztika és a Tények Őre.

Feladata:
1. Rövid távú memória (Scratchpad) kezelése és összegzése
2. Hosszú távú memória előkészítése (Vault: Gráf + Vektor)
3. RAG 2.1 - Kétkulcsos keresés (vektoros + gráf fázis)
4. Kontextus összeállítása a King számára (Context Briefing)
5. Hallucináció-gát - tények ellenőrzése (Active Validation)
6. Context Compression - Scratchpad titka (token-takarékosság)
7. i18n támogatás
8. Emlékek súlyozása és automatikus archiválás
"""

import time
import re
import json
import hashlib
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

# i18n import (opcionális)
try:
    from src.i18n.translator import get_translator
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False

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
    
    # Emlék típusok
    MEMORY_TYPES = {
        'fact': 1,      # Tényszerű információ
        'event': 2,     # Esemény
        'preference': 3, # Preferencia
        'relationship': 4, # Kapcsolat
        'concept': 5     # Fogalom
    }
    
    def __init__(self, scratchpad, config: Dict = None):
        self.scratchpad = scratchpad
        self.name = "valet"
        self.config = config or {}
        
        # Fordító (később állítjuk be)
        self.translator = None
        if I18N_AVAILABLE:
            self.translator = get_translator('en')
        
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
            'enable_auto_archive': True,        # Automatikus archiválás
            'archive_after_days': 90,           # 90 nap után archiválás
            'max_tracking_items': 1000,          # Maximum tracking elem
            'similarity_threshold': 0.7,         # Hasonlósági küszöb
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
            'first_seen': {},                     # Első említés
            'mention_count': defaultdict(int),    # Említések száma
        }
        
        # Emlékek gyorsítótára (Vault)
        self.memory_cache = {}
        self.memory_cache_ttl = 3600  # 1 óra
        
        # Hasonlósági index (egyszerű szó alapú)
        self.similarity_index = defaultdict(set)
        
        # Állapot (bővítve hibák tárolásával)
        self.state = {
            'status': 'idle',
            'processed_messages': 0,
            'summaries_created': 0,
            'warnings_issued': 0,
            'errors': [],
            'rag_searches': 0,
            'context_compressions': 0,
            'memories_stored': 0,
            'memories_archived': 0,
            'last_cleanup': time.time()
        }
        
        print("👔 Valet: Lakáj ébred. Őrzöm a tényeket.")
    
    def set_language(self, language: str):
        """Nyelv beállítása (i18n)"""
        if self.translator and I18N_AVAILABLE:
            self.translator.set_language(language)
    
    def _get_message(self, key: str, **kwargs) -> str:
        """Üzenet lekérése i18n-ből"""
        if self.translator and I18N_AVAILABLE:
            return self.translator.get(f'valet.{key}', **kwargs)
        return key
    
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
            'emotional_context': {'charge': 0.5, 'topic': '...'},
            'important_memories': ['emlék1', 'emlék2'],
            'token_estimate': 0
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
            'important_memories': [],
            'token_estimate': 0,
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
            
            # 2. Utolsó N üzenet - ROBOSZTUS KEZELÉS
            recent = self.scratchpad.read(limit=self.config['max_recent_messages'])
            context['recent'] = self._process_recent_messages(recent)
            
            # 3. Fontos tények kinyerése
            facts = self._extract_facts(recent)
            context['facts'] = facts[:5]  # Max 5 tény
            
            # 4. Fontos emlékek betöltése
            important_memories = self._get_important_memories(intent_packet, 3)
            context['important_memories'] = important_memories
            
            # 5. RAG keresés (ha be van kapcsolva)
            if self.config['enable_rag']:
                rag_results = self._rag_search(intent_packet, facts, important_memories)
                context['rag_results'] = rag_results[:3]
            
            # 6. Összefoglaló készítése (Context Compression)
            if self.config['context_compression']:
                context['summary'] = self._create_compressed_summary(
                    intent_packet, facts, context['rag_results'], important_memories
                )
                self.state['context_compressions'] += 1
            else:
                context['summary'] = self._create_summary(intent_packet, facts)
            
            # 7. Tracking adatok
            if self.config['enable_tracking']:
                context['tracking'] = self._get_tracking_summary(intent_packet)
            
            # 8. Token becslés
            context['token_estimate'] = self._estimate_tokens(context)
            
            # 9. Aktuális intent figyelmeztetések (Hallucináció-gát)
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
                
                # Tények keresése (bővített minták)
                patterns = [
                    (r'(?:az?|the)\s+(\w+)\s+(?:van|nincs|lesz|volt|is|is not|was|was not)', 'state'),
                    (r'(\w+)\s+(?:az?|a|the)\s+(\w+)', 'identity'),
                    (r'(\d{4})[-.](\d{1,2})[-.](\d{1,2})', 'date'),
                    (r'(?:szeret|love|like|prefer|enjoy)\s+(\w+)', 'preference'),
                    (r'(?:nem|not|don\'t|doesn\'t)\s+(?:szeret|love|like)\s+(\w+)', 'negative_preference'),
                    (r'(?:van|have|has|possess)\s+(\w+)', 'possession'),
                    (r'(?:akar|want|would like|szeretné)\s+(\w+)', 'desire'),
                    (r'(?:kell|need|must|have to)\s+(\w+)', 'necessity'),
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
    
    def _get_important_memories(self, intent_packet: Dict, limit: int = 3) -> List[str]:
        """
        Fontos emlékek lekérése a tracking adatokból.
        """
        important = []
        
        try:
            payload = intent_packet.get('payload', {})
            text = payload.get('text', '')
            
            # Fontosság alapján rendezés
            sorted_memories = sorted(
                self.tracking['importance'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:limit]
            
            for memory, importance in sorted_memories:
                if importance > self.config['important_threshold']:
                    important.append(f"{memory} (fontosság: {importance:.2f})")
            
        except Exception as e:
            self.state['errors'].append(f"Hiba a fontos emlékek lekérésében: {e}")
        
        return important
    
    def _rag_search(self, intent_packet: Dict, facts: List[str], important_memories: List[str]) -> List[str]:
        """
        RAG 2.1 - Kétkulcsos keresés.
        
        1. Vektoros fázis: szemantikai keresés a Vault-ban
        2. Gráf fázis: érzelmi és szociális kapcsolatok keresése
        3. Fontossági súlyozás
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
            
            # 3. Fontos emlékek
            memory_results = [f"[Emlék] {mem}" for mem in important_memories]
            
            # 4. Eredmények összefésülése (súlyozva)
            all_results = []
            all_results.extend([f"[Szemantikai] {res}" for res in vector_results])
            all_results.extend([f"[Kapcsolat] {res}" for res in graph_results])
            all_results.extend(memory_results)
            
            # Egyediek kiszűrése
            seen = set()
            for res in all_results:
                key = hashlib.md5(res.encode()).hexdigest()
                if key not in seen:
                    seen.add(key)
                    results.append(res)
            
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
        
        try:
            notes = self.scratchpad.read_all_notes()
            search_terms = text.lower().split()[:5]
            
            for module, notes_dict in notes.items():
                for key, note in notes_dict.items():
                    if isinstance(note, dict):
                        note_text = str(note.get('value', ''))
                    else:
                        note_text = str(note)
                    
                    note_lower = note_text.lower()
                    
                    # Kulcsszavas keresés
                    matches = sum(1 for term in search_terms if term in note_lower and len(term) > 3)
                    
                    if matches > 0:
                        similarity = matches / len(search_terms)
                        if similarity > self.config['similarity_threshold']:
                            results.append(f"{module}: {note_text[:100]} (hasonlóság: {similarity:.2f})")
                            
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
                    count = self.tracking['mention_count'].get(rel, 0)
                    results.append(f"{rel} {charge_str} ({count}x)")
            
            # Érzelmi töltés az aktuális témához
            if topic in self.tracking['emotional_charge']:
                charge = self.tracking['emotional_charge'][topic]
                if abs(charge) > 0.5:
                    mood = self._get_message('positive_mood') if charge > 0 else self._get_message('negative_mood')
                    results.append(f"{mood}: {charge:.2f}")
                    
        except Exception as e:
            self.state['errors'].append(f"Gráf keresési hiba: {e}")
        
        return results
    
    def _get_tracking_summary(self, intent_packet: Dict) -> Dict:
        """
        Tracking adatok összefoglalójának lekérése.
        """
        summary = {
            'topics': {},
            'entities': {},
            'emotional': {},
            'last': {}
        }
        
        try:
            # Top témák
            top_topics = sorted(
                self.tracking['topics'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
            summary['topics'] = {k: v for k, v in top_topics}
            
            # Top entitások
            top_entities = sorted(
                self.tracking['entities'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
            summary['entities'] = {k: v for k, v in top_entities}
            
            # Érzelmi töltés
            summary['emotional'] = dict(list(self.tracking['emotional_charge'].items())[:5])
            
            # Utolsó említések
            summary['last'] = self._format_last_mentioned(self.tracking['last_mentioned'])
            
            # Aktuális téma érzelmi kontextusa
            current_topic = intent_packet.get('payload', {}).get('intent', {}).get('class', 'unknown')
            if current_topic in self.tracking['emotional_charge']:
                summary['current_emotional'] = {
                    'topic': current_topic,
                    'charge': self.tracking['emotional_charge'][current_topic]
                }
            
        except Exception as e:
            self.state['errors'].append(f"Hiba a tracking összefoglaló készítésében: {e}")
        
        return summary
    
    def _estimate_tokens(self, context: Dict) -> int:
        """
        Tokenek számának becslése a kontextusban.
        """
        total = 0
        
        for key, value in context.items():
            if isinstance(value, str):
                total += len(value.split())
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        total += len(item.split())
            elif isinstance(value, dict):
                for k, v in value.items():
                    if isinstance(k, str):
                        total += len(k.split())
                    if isinstance(v, str):
                        total += len(v.split())
        
        return total
    
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
            
            if not facts:
                return self._get_message('user_message', text=text[:100])
            
            fact_summary = ". ".join(str(f) for f in facts[:3])
            return self._get_message('summary_with_facts', text=text[:50], facts=fact_summary)
            
        except Exception as e:
            self.state['errors'].append(f"Hiba az összefoglaló készítésében: {e}")
            return self._get_message('user_message_default')
    
    def _create_compressed_summary(self, intent_packet: Dict, facts: List[str], 
                                   rag_results: List[str], important_memories: List[str]) -> str:
        """
        Context Compression - Tömörített összefoglaló (token-takarékos).
        Csak a legfontosabb információkat tartja meg.
        """
        try:
            payload = intent_packet.get('payload', {})
            text = payload.get('text', '') if isinstance(payload, dict) else ""
            
            parts = []
            
            # Érzelmi kontextus
            current_topic = payload.get('intent', {}).get('class', 'unknown') if isinstance(payload, dict) else 'unknown'
            if current_topic in self.tracking['emotional_charge']:
                charge = self.tracking['emotional_charge'][current_topic]
                if abs(charge) > 0.3:
                    mood = "😊" if charge > 0 else "😞"
                    parts.append(mood)
            
            # Fontos tények
            if facts:
                important_facts = sorted(
                    [(f, self.tracking['importance'].get(f, 0.5)) for f in facts[:5]],
                    key=lambda x: x[1],
                    reverse=True
                )[:2]
                if important_facts:
                    parts.append("📌 " + "; ".join([f[0][:30] for f in important_facts]))
            
            # RAG eredmények
            if rag_results:
                parts.append("🔗 " + "; ".join(rag_results[:2]))
            
            # Fontos emlékek
            if important_memories:
                parts.append("💭 " + "; ".join(important_memories))
            
            # Aktuális üzenet
            if text:
                parts.append(f"💬 {text[:30]}")
            
            summary = " | ".join(parts) if parts else self._get_message('no_context')
            
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
                formatted[key] = f"{int(delta)}s"
            elif delta < 3600:
                formatted[key] = f"{int(delta/60)}m"
            elif delta < 86400:
                formatted[key] = f"{int(delta/3600)}h"
            else:
                formatted[key] = f"{int(delta/86400)}d"
        
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
            
            contradictions = []
            
            # 1. Ellentmondás a tényekkel
            for fact in facts:
                if not isinstance(fact, str):
                    continue
                    
                if 'nem' in fact or 'nincs' in fact or 'not' in fact:
                    fact_words = fact.split()
                    for word in fact_words[1:3]:
                        if word and word in text:
                            contradictions.append(f"📌 {fact[:50]}")
                            break
            
            # 2. Ellenőrzés a RAG eredményekkel
            for rag in rag_results:
                if isinstance(rag, str) and ('ellentmondás' in rag.lower() or 'contradiction' in rag.lower()):
                    contradictions.append(f"🔍 {rag[:50]}")
            
            if contradictions:
                return self._get_message('contradiction', details=contradictions[0])
                
        except Exception as e:
            self.state['errors'].append(f"Hiba az intent validálásában: {e}")
        
        return None
    
    # --- MEMÓRIA KEZELÉS ---
    
    def remember(self, key: str, value: Any, memory_type: str = 'fact', 
                 importance: float = 0.5, emotional_charge: float = 0.0):
        """
        Fontos információ elmentése a hosszú távú memóriába.
        """
        try:
            memory_id = f"{memory_type}_{int(time.time())}_{hashlib.md5(key.encode()).hexdigest()[:8]}"
            
            # Emlék adatok
            memory = {
                'id': memory_id,
                'key': key,
                'value': value,
                'type': memory_type,
                'type_code': self.MEMORY_TYPES.get(memory_type, 0),
                'importance': importance,
                'emotional_charge': emotional_charge,
                'created': time.time(),
                'last_accessed': time.time(),
                'access_count': 0
            }
            
            # Hosszú távú memória
            if importance > self.config['important_threshold']:
                self.scratchpad.write_note(self.name, f"memory_{memory_id}", memory)
                self.state['memories_stored'] += 1
            
            # Rövid távú memória
            self.scratchpad.write_note(self.name, f"recent_{key}", value)
            
            # Tracking frissítés
            self.tracking['importance'][key] = max(
                self.tracking['importance'].get(key, 0),
                importance
            )
            self.tracking['emotional_charge'][key] = emotional_charge
            self.tracking['first_seen'].setdefault(key, time.time())
            self.tracking['mention_count'][key] += 1
            
            # Hasonlósági index építés
            if isinstance(key, str):
                for word in key.split():
                    if len(word) > 3:
                        self.similarity_index[word.lower()].add(key)
            
        except Exception as e:
            self.state['errors'].append(f"Hiba az emlékezésben: {e}")
    
    def recall(self, key: str, default=None):
        """Információ előhívása a memóriából"""
        try:
            # Először rövid táv
            value = self.scratchpad.read_note(self.name, f"recent_{key}")
            if value is not None:
                return value
            
            # Aztán hosszú táv
            notes = self.scratchpad.read_all_notes(self.name)
            for note_key, note in notes.items():
                if note_key.startswith('memory_') and isinstance(note, dict):
                    if note.get('key') == key:
                        note['last_accessed'] = time.time()
                        note['access_count'] += 1
                        self.scratchpad.write_note(self.name, note_key, note)
                        return note.get('value')
            
        except Exception as e:
            self.state['errors'].append(f"Hiba a felidézésben: {e}")
        
        return default
    
    def search_similar(self, query: str, limit: int = 5) -> List[Dict]:
        """
        Hasonló emlékek keresése kulcsszavak alapján.
        """
        results = []
        
        try:
            query_words = [w.lower() for w in query.split() if len(w) > 3]
            candidates = set()
            
            for word in query_words:
                candidates.update(self.similarity_index.get(word, set()))
            
            for key in candidates:
                importance = self.tracking['importance'].get(key, 0)
                last_seen = self.tracking['last_mentioned'].get(key, 0)
                count = self.tracking['mention_count'].get(key, 0)
                
                results.append({
                    'key': key,
                    'importance': importance,
                    'last_seen': last_seen,
                    'count': count,
                    'score': importance * 0.5 + (count * 0.1) + (1 if last_seen > time.time() - 86400 else 0)
                })
            
            results.sort(key=lambda x: x['score'], reverse=True)
            
        except Exception as e:
            self.state['errors'].append(f"Hiba a hasonló keresésben: {e}")
        
        return results[:limit]
    
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
            now = time.time()
            
            # Téma hozzáadása
            self.tracking['topics'][intent] += 1
            self.tracking['last_mentioned'][intent] = now
            self.tracking['first_seen'].setdefault(intent, now)
            self.tracking['mention_count'][intent] += 1
            
            # Érzelmi töltés becslése
            emotional_charge = self._estimate_emotional_charge(text)
            self.tracking['emotional_charge'][intent] = (
                self.tracking['emotional_charge'].get(intent, 0) * 0.7 + emotional_charge * 0.3
            )
            
            # Fontosság számítás
            self.tracking['importance'][intent] = min(
                1.0,
                0.3 + (self.tracking['mention_count'][intent] * 0.05)
            )
            
            # Entitások keresése
            entities = payload.get('entities', [])
            for entity in entities:
                if isinstance(entity, dict):
                    etype = entity.get('type', 'unknown')
                    evalue = entity.get('value', '')
                    key = f"{etype}:{evalue}"
                    
                    self.tracking['entities'][key] += 1
                    self.tracking['last_mentioned'][key] = now
                    self.tracking['first_seen'].setdefault(key, now)
                    self.tracking['mention_count'][key] += 1
                    self.tracking['relationships'][intent].add(key)
                    
                    importance = min(1.0, 0.3 + (self.tracking['entities'][key] * 0.1))
                    self.tracking['importance'][key] = importance
                    
                    # Hasonlósági index
                    for word in evalue.split():
                        if len(word) > 3:
                            self.similarity_index[word.lower()].add(key)
            
            # Limitálás
            self._limit_tracking()
            
        except Exception as e:
            self.state['errors'].append(f"Hiba a trackelésben: {e}")
    
    def _estimate_emotional_charge(self, text: str) -> float:
        """
        Érzelmi töltés becslése szöveg alapján (-1.0 - +1.0).
        """
        if not isinstance(text, str):
            return 0.0
        
        text_lower = text.lower()
        
        # Pozitív szavak (bővített)
        positive_words = [
            'köszönöm', 'szuper', 'jó', 'remek', 'nagyszerű', 'örülök', 
            'thank', 'great', 'good', 'excellent', 'love', 'like', 'awesome',
            'fantastic', 'brilliant', 'wonderful', 'perfect', 'beautiful',
            '😊', '🙂', '👍', '❤️'
        ]
        
        # Negatív szavak (bővített)
        negative_words = [
            'rossz', 'szar', 'utálom', 'nem jó', 'hiba', 'baj van',
            'bad', 'terrible', 'awful', 'hate', 'error', 'problem',
            'shit', 'fuck', 'damn', 'stupid', 'idiot', '😞', '😠', '👎'
        ]
        
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        total = positive_count + negative_count
        if total == 0:
            return 0.0
        
        return (positive_count - negative_count) / total
    
    def _limit_tracking(self):
        """
        Tracking adatok limitálása (memóriatakarékosság).
        """
        max_items = self.config['max_tracking_items']
        
        # Ha túl sok a topic, ritkítjuk
        if len(self.tracking['topics']) > max_items:
            sorted_items = sorted(
                self.tracking['topics'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:max_items]
            self.tracking['topics'] = defaultdict(int, sorted_items)
        
        # Ha túl sok az entity
        if len(self.tracking['entities']) > max_items:
            sorted_items = sorted(
                self.tracking['entities'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:max_items]
            self.tracking['entities'] = defaultdict(int, sorted_items)
    
    def get_tracking(self, topic: str = None) -> Dict:
        """Tracking adatok lekérése"""
        try:
            if topic:
                return {
                    'count': self.tracking['topics'].get(topic, 0),
                    'last': self.tracking['last_mentioned'].get(topic),
                    'first': self.tracking['first_seen'].get(topic),
                    'mentions': self.tracking['mention_count'].get(topic, 0),
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
                'importance': dict(self.tracking['importance']),
                'mention_counts': dict(self.tracking['mention_count'])
            }
        except Exception as e:
            self.state['errors'].append(f"Hiba a tracking lekérésében: {e}")
            return {}
    
    # --- KARBANTARTÁS ---
    
    def cleanup(self, force: bool = False):
        """
        Régi memória tisztítása.
        - Ha egy téma régi, csökkentjük a súlyát
        - Ha nagyon régi, "archiváljuk"
        - Automatikus archiválás
        """
        try:
            now = time.time()
            forget_after = self.config['forget_after_days'] * 86400
            archive_after = self.config['archive_after_days'] * 86400
            
            archived = 0
            
            for topic, last_time in list(self.tracking['last_mentioned'].items()):
                age = now - last_time
                
                if age > archive_after and self.config['enable_auto_archive']:
                    # Archiválás
                    self._archive_memory(topic)
                    archived += 1
                    
                elif age > forget_after:
                    # Teljes törlés
                    self._delete_memory(topic)
                    
                elif age > forget_after // 2:
                    # Súly csökkentése
                    if topic in self.tracking['importance']:
                        self.tracking['importance'][topic] *= 0.8
            
            self.state['last_cleanup'] = now
            self.state['processed_messages'] += 1
            self.state['memories_archived'] += archived
            
        except Exception as e:
            self.state['errors'].append(f"Hiba a cleanup során: {e}")
    
    def _archive_memory(self, key: str):
        """
        Emlék archiválása (megtartjuk, de nem aktív).
        """
        try:
            memory_data = {
                'key': key,
                'importance': self.tracking['importance'].get(key, 0),
                'emotional_charge': self.tracking['emotional_charge'].get(key, 0),
                'mention_count': self.tracking['mention_count'].get(key, 0),
                'first_seen': self.tracking['first_seen'].get(key),
                'last_seen': self.tracking['last_mentioned'].get(key),
                'archived_at': time.time()
            }
            
            self.scratchpad.write_note(self.name, f"archived_{key}", memory_data)
            self._delete_memory(key)
            
        except Exception as e:
            self.state['errors'].append(f"Hiba az archiválásban: {e}")
    
    def _delete_memory(self, key: str):
        """
        Emlék teljes törlése.
        """
        try:
            if key in self.tracking['topics']:
                del self.tracking['topics'][key]
            if key in self.tracking['entities']:
                del self.tracking['entities'][key]
            if key in self.tracking['last_mentioned']:
                del self.tracking['last_mentioned'][key]
            if key in self.tracking['relationships']:
                del self.tracking['relationships'][key]
            if key in self.tracking['emotional_charge']:
                del self.tracking['emotional_charge'][key]
            if key in self.tracking['importance']:
                del self.tracking['importance'][key]
            if key in self.tracking['first_seen']:
                del self.tracking['first_seen'][key]
            if key in self.tracking['mention_count']:
                del self.tracking['mention_count'][key]
                
        except Exception as e:
            self.state['errors'].append(f"Hiba a törlésben: {e}")
    
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
            'memories_stored': self.state['memories_stored'],
            'memories_archived': self.state['memories_archived'],
            'errors': self.state['errors'][-10:],
            'tracking': {
                'topics': len(self.tracking['topics']),
                'entities': len(self.tracking['entities']),
                'relationships': sum(len(v) for v in self.tracking['relationships'].values())
            },
            'config': {
                'max_context_tokens': self.config['max_context_tokens'],
                'enable_rag': self.config['enable_rag'],
                'enable_tracking': self.config['enable_tracking'],
                'important_threshold': self.config['important_threshold']
            }
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