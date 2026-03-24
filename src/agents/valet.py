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

VAULT INTEGRÁCIÓ (végleges):
- Graph-Vault: Neo4j (kapcsolatok, érzelmi töltés, szociális térkép)
- Vector-Vault: Qdrant (szemantikus keresés, globális tudás)
- A meglévő tracking továbbra is működik, de a Vault az elsődleges tároló
"""

import time
import re
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union
from collections import defaultdict, Counter
from pathlib import Path

# Neo4j import
try:
    from neo4j import GraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False

# Qdrant import
try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qdrant_models
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False

# Numpy a vektorokhoz
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
    
    Rétegek:
    1. Rövid táv: Scratchpad (gyors memória)
    2. Közép táv: Tracking (in-memory, gyors keresés)
    3. Hosszú táv: Graph-Vault (Neo4j) - kapcsolatok, érzelmi töltés
    4. Hosszú táv: Vector-Vault (Qdrant) - szemantikus keresés
    """
    
    # Emlék típusok
    MEMORY_TYPES = {
        'fact': 1,          # Tényszerű információ
        'event': 2,         # Esemény
        'preference': 3,    # Preferencia
        'relationship': 4,  # Kapcsolat
        'concept': 5,       # Fogalom
        'conversation': 6,  # Beszélgetés részlet
        'emotion': 7,       # Érzelmi állapot
        'decision': 8,      # Döntés
    }
    
    def __init__(self, scratchpad, config: Dict = None):
        self.scratchpad = scratchpad
        self.name = "valet"
        self.config = config or {}
        
        # Fordító (később állítjuk be)
        self.translator = None
        if I18N_AVAILABLE:
            self.translator = get_translator('en')
        
        # ========== KONFIGURÁCIÓ ==========
        default_config = {
            # Token management
            'max_context_tokens': 1500,
            'max_recent_messages': 5,
            'summary_length': 200,
            'context_compression': True,
            
            # Tracking
            'enable_tracking': True,
            'max_tracking_items': 1000,
            
            # Validation
            'enable_validation': True,
            
            # RAG
            'enable_rag': True,
            'vector_search_limit': 5,
            'graph_search_limit': 3,
            'similarity_threshold': 0.7,
            'emotional_weight': 0.3,
            
            # Memory lifecycle
            'important_threshold': 0.7,
            'forget_after_days': 30,
            'enable_auto_archive': True,
            'archive_after_days': 90,
            
            # Vault kapcsolatok
            'neo4j_uri': 'bolt://localhost:7687',
            'neo4j_user': 'neo4j',
            'neo4j_password': 'soulcore2026',
            'qdrant_host': 'localhost',
            'qdrant_port': 6333,
            'embedding_size': 1024,
        }
        
        for key, value in default_config.items():
            if key not in self.config:
                self.config[key] = value
        
        # ========== RÖVID TÁVÚ MEMÓRIA (Tracking) ==========
        self.tracking = {
            'topics': defaultdict(int),
            'entities': defaultdict(int),
            'last_mentioned': {},
            'relationships': defaultdict(set),
            'emotional_charge': defaultdict(float),
            'importance': defaultdict(float),
            'first_seen': {},
            'mention_count': defaultdict(int),
        }
        
        self.memory_cache = {}
        self.memory_cache_ttl = 3600
        self.similarity_index = defaultdict(set)
        
        # ========== ÁLLAPOT (ELŐRE HOZVA - FONTOS!) ==========
        # Ezt a vault inicializálások ELŐTT kell létrehozni!
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
            'last_cleanup': time.time(),
            'graph_connected': False,
            'qdrant_connected': False,
        }
        
        # ========== HOSSZÚ TÁVÚ MEMÓRIA (Vault) ==========
        # Neo4j kapcsolat (Graph-Vault)
        self.graph_driver = None
        self.graph_available = False
        self._init_graph_vault()
        
        # Qdrant kapcsolat (Vector-Vault)
        self.qdrant_client = None
        self.qdrant_available = False
        self._init_vector_vault()
        
        # Embedding modell (később kapja meg)
        self.embedder = None
        
        print("👔 Valet: Lakáj ébred. Őrzöm a tényeket.")
        self._report_vault_status()
    
    def _init_graph_vault(self):
        """Neo4j Graph-Vault inicializálása"""
        if not NEO4J_AVAILABLE:
            print("   ⚠️ Neo4j driver nem elérhető. Graph-Vault kikapcsolva.")
            return
        
        try:
            self.graph_driver = GraphDatabase.driver(
                self.config['neo4j_uri'],
                auth=(self.config['neo4j_user'], self.config['neo4j_password'])
            )
            # Teszt kapcsolat
            with self.graph_driver.session() as session:
                result = session.run("RETURN 1 as test")
                result.single()
            
            self.graph_available = True
            self.state['graph_connected'] = True
            print("   ✅ Neo4j Graph-Vault: kapcsolódva")
            
            # Constraints és indexek biztosítása
            self._ensure_graph_schema()
            
        except Exception as e:
            print(f"   ❌ Neo4j kapcsolat sikertelen: {e}")
            self.graph_available = False
            self.state['errors'].append(f"Neo4j: {e}")
    
    def _ensure_graph_schema(self):
        """Graph séma inicializálása (egyszer)"""
        if not self.graph_available:
            return
        
        try:
            with self.graph_driver.session() as session:
                # Constraints
                session.run("""
                    CREATE CONSTRAINT IF NOT EXISTS FOR (m:Memory) REQUIRE m.uuid IS UNIQUE
                """)
                session.run("""
                    CREATE CONSTRAINT IF NOT EXISTS FOR (p:Person) REQUIRE p.name IS UNIQUE
                """)
                session.run("""
                    CREATE CONSTRAINT IF NOT EXISTS FOR (t:Topic) REQUIRE t.name IS UNIQUE
                """)
                
                # Indexek
                session.run("""
                    CREATE INDEX IF NOT EXISTS FOR (m:Memory) ON (m.created_at)
                """)
                session.run("""
                    CREATE INDEX IF NOT EXISTS FOR (r:Relationship) ON (r.type)
                """)
                
        except Exception as e:
            self.state['errors'].append(f"Graph séma hiba: {e}")
    
    def _init_vector_vault(self):
        """Qdrant Vector-Vault inicializálása"""
        if not QDRANT_AVAILABLE:
            print("   ⚠️ Qdrant client nem elérhető. Vector-Vault kikapcsolva.")
            return
        
        try:
            self.qdrant_client = QdrantClient(
                host=self.config['qdrant_host'],
                port=self.config['qdrant_port']
            )
            
            # Collection-ök ellenőrzése/létrehozása
            collections = ['global_knowledge', 'personal_memories']
            for name in collections:
                try:
                    self.qdrant_client.get_collection(name)
                except:
                    self.qdrant_client.create_collection(
                        collection_name=name,
                        vectors_config=qdrant_models.VectorParams(
                            size=self.config['embedding_size'],
                            distance=qdrant_models.Distance.COSINE
                        )
                    )
            
            self.qdrant_available = True
            self.state['qdrant_connected'] = True
            print("   ✅ Qdrant Vector-Vault: kapcsolódva")
            
        except Exception as e:
            print(f"   ❌ Qdrant kapcsolat sikertelen: {e}")
            self.qdrant_available = False
            self.state['errors'].append(f"Qdrant: {e}")
    
    def _report_vault_status(self):
        """Vault státusz jelentés"""
        status = []
        if self.graph_available:
            status.append("Graph-Vault (Neo4j) ✅")
        else:
            status.append("Graph-Vault (Neo4j) ❌")
        
        if self.qdrant_available:
            status.append("Vector-Vault (Qdrant) ✅")
        else:
            status.append("Vector-Vault (Qdrant) ❌")
        
        print(f"   Vault: {', '.join(status)}")
    
    def set_embedder(self, embedder):
        """Embedding modell beállítása (ModelWrapper)"""
        self.embedder = embedder
        print("   ✅ Embedding modell beállítva")
    
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
        
        # Kapcsolatok lezárása
        if self.graph_driver:
            self.graph_driver.close()
        
        print("👔 Valet: Leállt.")
    
    # ========== KONTEXTUS ÖSSZEÁLLÍTÁS (RAG 2.1) ==========
    
    def prepare_context(self, intent_packet: Dict) -> Dict[str, Any]:
        """
        Kontextus összeállítása a King számára.
        RAG 2.1: Graph-Vault + Vector-Vault + Tracking + Scratchpad
        """
        context = {
            'summary': '',
            'facts': [],
            'recent': [],
            'warnings': [],
            'tracking': {},
            'rag_results': [],
            'graph_context': [],
            'vector_context': [],
            'emotional_context': {},
            'important_memories': [],
            'token_estimate': 0,
            'timestamp': time.time()
        }
        
        try:
            if not isinstance(intent_packet, dict):
                error_msg = f"prepare_context: intent_packet nem dict, hanem {type(intent_packet)}"
                self.state['errors'].append(error_msg)
                return context
            
            # 1. Rövid távú memória (Scratchpad)
            context['recent'] = self._process_recent_messages(
                self.scratchpad.read(limit=self.config['max_recent_messages'])
            )
            
            # 2. Tények kinyerése a recent üzenetekből
            facts = self._extract_facts(context['recent'])
            context['facts'] = facts[:5]
            
            # 3. Fontos emlékek (tracking alapján)
            important = self._get_important_memories(intent_packet, 3)
            context['important_memories'] = important
            
            # 4. RAG 2.1 - Kétkulcsos keresés (ha be van kapcsolva)
            if self.config['enable_rag']:
                rag_context = self._rag_search_v2(intent_packet, facts, important)
                context['rag_results'] = rag_context.get('combined', [])[:3]
                context['graph_context'] = rag_context.get('graph', [])
                context['vector_context'] = rag_context.get('vector', [])
                self.state['rag_searches'] += 1
            
            # 5. Érzelmi kontextus (graph + tracking)
            context['emotional_context'] = self._get_emotional_context(intent_packet)
            
            # 6. Összefoglaló (Context Compression)
            if self.config['context_compression']:
                context['summary'] = self._create_compressed_summary(
                    intent_packet, facts, context['rag_results'], important
                )
                self.state['context_compressions'] += 1
            else:
                context['summary'] = self._create_summary(intent_packet, facts)
            
            # 7. Tracking adatok
            if self.config['enable_tracking']:
                context['tracking'] = self._get_tracking_summary(intent_packet)
            
            # 8. Hallucináció-gát
            if self.config['enable_validation']:
                warning = self._validate_intent_with_vault(
                    intent_packet, facts, context['graph_context'], context['vector_context']
                )
                if warning:
                    context['warnings'].append(warning)
                    self.state['warnings_issued'] += 1
            
            # 9. Token becslés
            context['token_estimate'] = self._estimate_tokens(context)
            
        except Exception as e:
            error_msg = f"prepare_context hiba: {e}"
            self.state['errors'].append(error_msg)
            print(f"👔 Valet hiba: {error_msg}")
        
        return context
    
    def _rag_search_v2(self, intent_packet: Dict, facts: List[str], 
                       important_memories: List[str]) -> Dict[str, List[str]]:
        """
        RAG 2.1 - Kétkulcsos keresés Vault-ban.
        
        Returns:
            {
                'graph': ['graph_result1', ...],
                'vector': ['vector_result1', ...],
                'combined': ['combined_result1', ...]
            }
        """
        result = {
            'graph': [],
            'vector': [],
            'combined': []
        }
        
        try:
            payload = intent_packet.get('payload', {})
            text = payload.get('text', '')
            intent = payload.get('intent', {}).get('class', 'unknown')
            
            # 1. GRÁF KERESÉS (Neo4j) - kapcsolatok, érzelmi töltés
            if self.graph_available:
                graph_results = self._graph_search(text, intent)
                result['graph'] = graph_results
            
            # 2. VEKTOROS KERESÉS (Qdrant) - szemantikus
            if self.qdrant_available and self.embedder:
                vector_results = self._vector_search(text)
                result['vector'] = vector_results
            
            # 3. Fallback: tracking alapú keresés (ha vault nem elérhető)
            if not result['graph'] and not result['vector']:
                fallback = self._tracking_search(text, intent, important_memories)
                result['combined'] = fallback
            else:
                # Eredmények összefésülése
                all_results = []
                all_results.extend([f"[Gráf] {r}" for r in result['graph']])
                all_results.extend([f"[Vektor] {r}" for r in result['vector']])
                all_results.extend([f"[Emlék] {m}" for m in important_memories])
                
                # Duplikáció szűrés
                seen = set()
                for res in all_results:
                    key = hashlib.md5(res.encode()).hexdigest()
                    if key not in seen:
                        seen.add(key)
                        result['combined'].append(res)
            
        except Exception as e:
            self.state['errors'].append(f"RAG keresési hiba: {e}")
        
        return result
    
    def _graph_search(self, text: str, intent: str) -> List[str]:
        """
        Gráf keresés Neo4j-ben.
        Kapcsolatok, érzelmi töltés, szociális térkép.
        """
        results = []
        
        if not self.graph_available:
            return results
        
        try:
            with self.graph_driver.session() as session:
                # 1. Kapcsolatok az aktuális témához
                query = """
                MATCH (t:Topic {name: $topic})<-[:MENTIONS]-(m:Memory)-[:MENTIONS]->(e:Entity)
                RETURN e.name as entity, m.emotional_charge as charge, 
                       m.created_at as created
                ORDER BY m.created_at DESC
                LIMIT 5
                """
                
                try:
                    result = session.run(query, topic=intent if intent else text[:50])
                    for record in result:
                        charge = record.get('charge', 0)
                        charge_str = "😊" if charge > 0.3 else "😐" if charge > -0.3 else "😞"
                        results.append(f"{record['entity']} {charge_str}")
                except:
                    pass
                
                # 2. Érzelmi állapot a felhasználóhoz
                query2 = """
                MATCH (p:Person {name: 'Grumpy'})-[r:RELATIONSHIP]-(e)
                RETURN e.name as entity, r.type as type, r.emotional_charge as charge
                ORDER BY r.updated_at DESC
                LIMIT 5
                """
                
                try:
                    result = session.run(query2)
                    for record in result:
                        charge = record.get('charge', 0)
                        if abs(charge) > 0.3:
                            results.append(f"Grumpy ↔ {record['entity']}: {record.get('type', 'kapcsolat')}")
                except:
                    pass
                
        except Exception as e:
            self.state['errors'].append(f"Gráf keresési hiba: {e}")
        
        return results
    
    def _vector_search(self, text: str) -> List[str]:
        """
        Vektoros keresés Qdrant-ben.
        Szemantikus hasonlóság alapján.
        """
        results = []
        
        if not self.qdrant_available or not self.embedder:
            return results
        
        try:
            # Embedding generálás
            embedding = self.embedder.embed(text)
            if not embedding:
                return results
            
            # Keresés a globális tudásban
            search_result = self.qdrant_client.search(
                collection_name='global_knowledge',
                query_vector=embedding,
                limit=self.config['vector_search_limit'],
                score_threshold=self.config['similarity_threshold']
            )
            
            for hit in search_result:
                if hit.payload and 'content' in hit.payload:
                    content = hit.payload['content'][:150]
                    results.append(f"{content} (relevancia: {hit.score:.2f})")
            
            # Keresés a személyes emlékekben
            personal_result = self.qdrant_client.search(
                collection_name='personal_memories',
                query_vector=embedding,
                limit=3,
                score_threshold=self.config['similarity_threshold']
            )
            
            for hit in personal_result:
                if hit.payload and 'content' in hit.payload:
                    content = hit.payload['content'][:150]
                    results.append(f"[Személyes] {content}")
                    
        except Exception as e:
            self.state['errors'].append(f"Vektoros keresési hiba: {e}")
        
        return results
    
    def _tracking_search(self, text: str, intent: str, 
                         important_memories: List[str]) -> List[str]:
        """
        Fallback: tracking alapú keresés (ha vault nem elérhető).
        """
        results = []
        
        try:
            # Kulcsszavas keresés a similarity_index-ben
            query_words = [w.lower() for w in text.split() if len(w) > 3]
            candidates = set()
            
            for word in query_words:
                candidates.update(self.similarity_index.get(word, set()))
            
            for key in list(candidates)[:3]:
                importance = self.tracking['importance'].get(key, 0)
                if importance > self.config['important_threshold']:
                    results.append(f"[Tracking] {key}")
            
            # Fontos emlékek
            for mem in important_memories[:2]:
                results.append(f"[Emlék] {mem}")
            
        except Exception as e:
            self.state['errors'].append(f"Tracking keresési hiba: {e}")
        
        return results
    
    def _get_emotional_context(self, intent_packet: Dict) -> Dict:
        """
        Érzelmi kontextus lekérése (graph + tracking).
        """
        emotional = {
            'current_charge': 0.0,
            'topic_trend': {},
            'recent_mood': 'neutral'
        }
        
        try:
            payload = intent_packet.get('payload', {})
            intent = payload.get('intent', {}).get('class', 'unknown')
            
            # Tracking alapján
            if intent in self.tracking['emotional_charge']:
                emotional['current_charge'] = self.tracking['emotional_charge'][intent]
            
            # Graph alapján (ha van)
            if self.graph_available:
                with self.graph_driver.session() as session:
                    query = """
                    MATCH (m:Memory)
                    WHERE m.emotional_charge IS NOT NULL
                    RETURN avg(m.emotional_charge) as avg_charge
                    """
                    result = session.run(query).single()
                    if result:
                        emotional['global_avg'] = result.get('avg_charge', 0)
            
            # Hangulat meghatározása
            charge = emotional['current_charge']
            if charge > 0.3:
                emotional['recent_mood'] = 'positive'
            elif charge < -0.3:
                emotional['recent_mood'] = 'negative'
            
        except Exception as e:
            self.state['errors'].append(f"Érzelmi kontextus hiba: {e}")
        
        return emotional
    
    def _validate_intent_with_vault(self, intent_packet: Dict, facts: List[str],
                                    graph_results: List[str], 
                                    vector_results: List[str]) -> Optional[str]:
        """
        Intent validálás a Vault adataival (hallucináció-gát).
        """
        contradictions = []
        
        try:
            # 1. Ellentmondás a gráf kapcsolatokkal
            for graph in graph_results:
                if 'ellentmondás' in graph.lower() or 'contradiction' in graph.lower():
                    contradictions.append(graph[:50])
            
            # 2. Ellentmondás a vektoros találatokkal
            for vec in vector_results:
                if 'ellentmondás' in vec.lower():
                    contradictions.append(vec[:50])
            
            # 3. Tracking alapú ellenőrzés
            for fact in facts:
                if 'nem' in fact or 'nincs' in fact:
                    for topic, charge in self.tracking['emotional_charge'].items():
                        if topic in fact and charge > 0.5:
                            contradictions.append(f"Ellentmondás: {fact} vs {topic}")
                            break
            
            if contradictions:
                return self._get_message('contradiction', details=contradictions[0])
                
        except Exception as e:
            self.state['errors'].append(f"Validálási hiba: {e}")
        
        return None
    
    # ========== MEMÓRIA TÁROLÁS (VAULT-BA) ==========
    
    def remember(self, key: str, value: Any, memory_type: str = 'fact',
                 importance: float = 0.5, emotional_charge: float = 0.0,
                 entities: List[Dict] = None):
        """
        Fontos információ elmentése a hosszú távú memóriába.
        - Vault-ba (Neo4j + Qdrant)
        - Tracking-be (in-memory)
        - Scratchpad-ba (rövid táv)
        """
        try:
            memory_id = f"{memory_type}_{int(time.time())}_{hashlib.md5(key.encode()).hexdigest()[:8]}"
            now = time.time()
            
            memory = {
                'id': memory_id,
                'key': key,
                'value': value,
                'type': memory_type,
                'type_code': self.MEMORY_TYPES.get(memory_type, 0),
                'importance': importance,
                'emotional_charge': emotional_charge,
                'created': now,
                'last_accessed': now,
                'access_count': 0
            }
            
            # 1. HOSSZÚ TÁV: Neo4j (Graph-Vault)
            if self.graph_available:
                self._store_in_graph(key, value, memory_type, emotional_charge, entities)
            
            # 2. HOSSZÚ TÁV: Qdrant (Vector-Vault)
            if self.qdrant_available and self.embedder and isinstance(value, str):
                self._store_in_vector(key, value, memory_type, importance)
            
            # 3. RÖVID TÁV: Scratchpad (ha nagyon fontos)
            if importance > self.config['important_threshold']:
                self.scratchpad.write_note(self.name, f"memory_{memory_id}", memory)
                self.state['memories_stored'] += 1
            
            # 4. KÖZÉP TÁV: Tracking (in-memory)
            self.scratchpad.write_note(self.name, f"recent_{key}", value)
            self._update_tracking(key, value, memory_type, importance, emotional_charge)
            
        except Exception as e:
            self.state['errors'].append(f"Hiba az emlékezésben: {e}")
    
    def _store_in_graph(self, key: str, value: Any, memory_type: str,
                        emotional_charge: float, entities: List[Dict] = None):
        """Tárolás Neo4j-ben"""
        if not self.graph_available:
            return
        
        try:
            with self.graph_driver.session() as session:
                # Memory csomópont létrehozása
                session.run("""
                    CREATE (m:Memory {
                        uuid: $uuid,
                        key: $key,
                        content: $content,
                        type: $type,
                        emotional_charge: $emotional_charge,
                        created_at: datetime()
                    })
                """, uuid=hashlib.md5(key.encode()).hexdigest(),
                    key=key, content=str(value)[:500], type=memory_type,
                    emotional_charge=emotional_charge)
                
                # Kapcsolatok entitásokkal
                if entities:
                    for entity in entities:
                        if isinstance(entity, dict):
                            entity_name = entity.get('value', entity.get('name', ''))
                            entity_type = entity.get('type', 'unknown')
                            if entity_name:
                                session.run("""
                                    MERGE (e:Entity {name: $name})
                                    ON CREATE SET e.type = $etype
                                """, name=entity_name, etype=entity_type)
                                
                                session.run("""
                                    MATCH (m:Memory {uuid: $uuid})
                                    MATCH (e:Entity {name: $name})
                                    CREATE (m)-[:MENTIONS {
                                        emotional_charge: $charge
                                    }]->(e)
                                """, uuid=hashlib.md5(key.encode()).hexdigest(),
                                    name=entity_name, charge=emotional_charge)
                                
        except Exception as e:
            self.state['errors'].append(f"Graph tárolási hiba: {e}")
    
    def _store_in_vector(self, key: str, value: str, memory_type: str, importance: float):
        """Tárolás Qdrant-ben"""
        if not self.qdrant_available or not self.embedder:
            return
        
        try:
            embedding = self.embedder.embed(value)
            if not embedding:
                return
            
            collection = 'global_knowledge' if memory_type == 'fact' else 'personal_memories'
            
            self.qdrant_client.upsert(
                collection_name=collection,
                points=[qdrant_models.PointStruct(
                    id=hashlib.md5(key.encode()).hexdigest(),
                    vector=embedding,
                    payload={
                        'key': key,
                        'content': value[:500],
                        'type': memory_type,
                        'importance': importance,
                        'created_at': time.time()
                    }
                )]
            )
            
        except Exception as e:
            self.state['errors'].append(f"Vector tárolási hiba: {e}")
    
    def _update_tracking(self, key: str, value: Any, memory_type: str,
                         importance: float, emotional_charge: float):
        """Tracking frissítése (in-memory)"""
        try:
            self.tracking['importance'][key] = max(
                self.tracking['importance'].get(key, 0), importance
            )
            self.tracking['emotional_charge'][key] = emotional_charge
            self.tracking['first_seen'].setdefault(key, time.time())
            self.tracking['mention_count'][key] += 1
            self.tracking['last_mentioned'][key] = time.time()
            
            # Hasonlósági index
            if isinstance(key, str):
                for word in key.split():
                    if len(word) > 3:
                        self.similarity_index[word.lower()].add(key)
                        
        except Exception as e:
            self.state['errors'].append(f"Tracking frissítési hiba: {e}")
    
    def recall(self, key: str, default=None):
        """Információ előhívása (először vault, majd tracking)"""
        try:
            # 1. Graph-Vault
            if self.graph_available:
                with self.graph_driver.session() as session:
                    result = session.run("""
                        MATCH (m:Memory {key: $key})
                        RETURN m.content as content
                        LIMIT 1
                    """, key=key).single()
                    if result:
                        return result['content']
            
            # 2. Vector-Vault (embedding alapú keresés)
            if self.qdrant_available and self.embedder and isinstance(key, str):
                embedding = self.embedder.embed(key)
                if embedding:
                    results = self.qdrant_client.search(
                        collection_name='personal_memories',
                        query_vector=embedding,
                        limit=1
                    )
                    if results and results[0].payload:
                        return results[0].payload.get('content')
            
            # 3. Tracking (in-memory)
            value = self.scratchpad.read_note(self.name, f"recent_{key}")
            if value is not None:
                return value
            
        except Exception as e:
            self.state['errors'].append(f"Hiba a felidézésben: {e}")
        
        return default
    
    # ========== MEGLÉVŐ FUNKCIÓK (megtartva, kibővítve) ==========
    
    def _process_recent_messages(self, recent_entries: List) -> List[str]:
        """Utolsó üzenetek feldolgozása"""
        processed = []
        for entry in recent_entries:
            try:
                if not isinstance(entry, dict):
                    continue
                if entry.get('type') == 'response':
                    content = entry.get('content', {})
                    text = self._safe_extract_text(content)
                    if text:
                        processed.append(text[:100])
            except Exception:
                continue
        return processed
    
    def _safe_extract_text(self, content: Any) -> str:
        """Biztonságos szövegkinyerés"""
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, dict):
            for key in ['response', 'text', 'content']:
                if key in content:
                    return self._safe_extract_text(content[key])
            return str(content)
        if isinstance(content, (list, tuple)):
            return " ".join([self._safe_extract_text(item) for item in content[:3]])
        try:
            return str(content)
        except:
            return ""
    
    def _extract_facts(self, recent_entries: List) -> List[str]:
        """Tények kinyerése"""
        facts = []
        patterns = [
            (r'(?:az?|the)\s+(\w+)\s+(?:van|nincs|lesz|volt)', 'state'),
            (r'(\d{4})[-.](\d{1,2})[-.](\d{1,2})', 'date'),
            (r'(?:szeret|love|like)\s+(\w+)', 'preference'),
        ]
        
        for entry in recent_entries:
            if not isinstance(entry, str):
                continue
            for pattern, fact_type in patterns:
                matches = re.findall(pattern, entry, re.IGNORECASE)
                for match in matches:
                    fact = f"{fact_type}: {match}" if isinstance(match, str) else f"{fact_type}: {' '.join(match)}"
                    if fact not in facts:
                        facts.append(fact)
        return facts
    
    def _get_important_memories(self, intent_packet: Dict, limit: int = 3) -> List[str]:
        """Fontos emlékek lekérése"""
        important = []
        try:
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
    
    def _get_tracking_summary(self, intent_packet: Dict) -> Dict:
        """Tracking adatok összefoglalója"""
        summary = {
            'topics': {},
            'entities': {},
            'emotional': {}
        }
        try:
            top_topics = sorted(
                self.tracking['topics'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
            summary['topics'] = {k: v for k, v in top_topics}
            summary['emotional'] = dict(list(self.tracking['emotional_charge'].items())[:5])
        except Exception as e:
            self.state['errors'].append(f"Tracking összefoglaló hiba: {e}")
        return summary
    
    def _estimate_tokens(self, context: Dict) -> int:
        """Token becslés"""
        total = 0
        for key, value in context.items():
            if isinstance(value, str):
                total += len(value.split())
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        total += len(item.split())
        return total
    
    def _create_summary(self, intent_packet: Dict, facts: List[str]) -> str:
        """Rövid összefoglaló"""
        try:
            payload = intent_packet.get('payload', {})
            text = payload.get('text', '') if isinstance(payload, dict) else ""
            if not facts:
                return self._get_message('user_message', text=text[:100])
            fact_summary = ". ".join(str(f) for f in facts[:3])
            return self._get_message('summary_with_facts', text=text[:50], facts=fact_summary)
        except:
            return "Felhasználói üzenet feldolgozva"
    
    def _create_compressed_summary(self, intent_packet: Dict, facts: List[str],
                                   rag_results: List[str], important_memories: List[str]) -> str:
        """Tömörített összefoglaló (token-takarékos)"""
        try:
            payload = intent_packet.get('payload', {})
            text = payload.get('text', '') if isinstance(payload, dict) else ""
            parts = []
            
            if facts:
                important_facts = sorted(
                    [(f, self.tracking['importance'].get(f, 0.5)) for f in facts[:5]],
                    key=lambda x: x[1],
                    reverse=True
                )[:2]
                if important_facts:
                    parts.append("📌 " + "; ".join([f[0][:30] for f in important_facts]))
            if rag_results:
                parts.append("🔗 " + "; ".join(rag_results[:2]))
            if important_memories:
                parts.append("💭 " + "; ".join(important_memories))
            if text:
                parts.append(f"💬 {text[:30]}")
            
            summary = " | ".join(parts) if parts else self._get_message('no_context')
            return summary[:self.config['summary_length']]
        except:
            return self._create_summary(intent_packet, facts)
    
    def track_message(self, intent_packet: Dict):
        """Üzenet nyomon követése (tracking frissítés)"""
        if not self.config['enable_tracking']:
            return
        
        try:
            payload = intent_packet.get('payload', {})
            if not isinstance(payload, dict):
                return
            
            text = payload.get('text', '')
            intent = payload.get('intent', {}).get('class', 'unknown')
            now = time.time()
            
            self.tracking['topics'][intent] += 1
            self.tracking['last_mentioned'][intent] = now
            self.tracking['first_seen'].setdefault(intent, now)
            self.tracking['mention_count'][intent] += 1
            
            emotional_charge = self._estimate_emotional_charge(text)
            self.tracking['emotional_charge'][intent] = (
                self.tracking['emotional_charge'].get(intent, 0) * 0.7 + emotional_charge * 0.3
            )
            self.tracking['importance'][intent] = min(
                1.0, 0.3 + (self.tracking['mention_count'][intent] * 0.05)
            )
            
            entities = payload.get('entities', [])
            for entity in entities:
                if isinstance(entity, dict):
                    evalue = entity.get('value', '')
                    if evalue:
                        self.tracking['entities'][evalue] += 1
                        self.tracking['last_mentioned'][evalue] = now
                        self.tracking['relationships'][intent].add(evalue)
            
            self._limit_tracking()
            
            # Emlék tárolása a Vault-ban (ha fontos)
            if self.tracking['importance'][intent] > self.config['important_threshold']:
                self.remember(
                    key=intent,
                    value=text,
                    memory_type='conversation',
                    importance=self.tracking['importance'][intent],
                    emotional_charge=emotional_charge,
                    entities=entities
                )
                
        except Exception as e:
            self.state['errors'].append(f"Hiba a trackelésben: {e}")
    
    def _estimate_emotional_charge(self, text: str) -> float:
        """Érzelmi töltés becslése"""
        if not isinstance(text, str):
            return 0.0
        
        text_lower = text.lower()
        positive_words = ['köszönöm', 'szuper', 'jó', 'remek', 'thank', 'great', 'good', 'love', 'like']
        negative_words = ['rossz', 'szar', 'utálom', 'hiba', 'bad', 'terrible', 'hate', 'error']
        
        positive_count = sum(1 for w in positive_words if w in text_lower)
        negative_count = sum(1 for w in negative_words if w in text_lower)
        total = positive_count + negative_count
        
        return (positive_count - negative_count) / total if total > 0 else 0.0
    
    def _limit_tracking(self):
        """Tracking limitálás"""
        max_items = self.config['max_tracking_items']
        if len(self.tracking['topics']) > max_items:
            sorted_items = sorted(
                self.tracking['topics'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:max_items]
            self.tracking['topics'] = defaultdict(int, sorted_items)
    
    def search_similar(self, query: str, limit: int = 5) -> List[Dict]:
        """Hasonló emlékek keresése"""
        results = []
        try:
            query_words = [w.lower() for w in query.split() if len(w) > 3]
            candidates = set()
            for word in query_words:
                candidates.update(self.similarity_index.get(word, set()))
            
            for key in list(candidates)[:limit]:
                importance = self.tracking['importance'].get(key, 0)
                results.append({
                    'key': key,
                    'importance': importance,
                    'score': importance
                })
            results.sort(key=lambda x: x['score'], reverse=True)
        except Exception as e:
            self.state['errors'].append(f"Hasonló keresési hiba: {e}")
        return results[:limit]
    
    def get_tracking(self, topic: str = None) -> Dict:
        """Tracking adatok lekérése"""
        try:
            if topic:
                return {
                    'count': self.tracking['topics'].get(topic, 0),
                    'last': self.tracking['last_mentioned'].get(topic),
                    'emotional_charge': self.tracking['emotional_charge'].get(topic, 0.0),
                    'importance': self.tracking['importance'].get(topic, 0.5)
                }
            return {
                'topics': dict(self.tracking['topics']),
                'entities': dict(self.tracking['entities']),
                'emotional_charge': dict(self.tracking['emotional_charge']),
                'importance': dict(self.tracking['importance'])
            }
        except Exception as e:
            self.state['errors'].append(f"Tracking lekérési hiba: {e}")
            return {}
    
    def cleanup(self, force: bool = False):
        """Régi memória tisztítása"""
        try:
            now = time.time()
            forget_after = self.config['forget_after_days'] * 86400
            
            for topic, last_time in list(self.tracking['last_mentioned'].items()):
                age = now - last_time
                if age > forget_after:
                    self._delete_memory(topic)
                elif age > forget_after // 2:
                    if topic in self.tracking['importance']:
                        self.tracking['importance'][topic] *= 0.8
            
            self.state['last_cleanup'] = now
            self.state['processed_messages'] += 1
            
        except Exception as e:
            self.state['errors'].append(f"Cleanup hiba: {e}")
    
    def _delete_memory(self, key: str):
        """Emlék törlése tracking-ből"""
        try:
            for dict_name in ['topics', 'entities', 'last_mentioned', 'relationships',
                              'emotional_charge', 'importance', 'first_seen', 'mention_count']:
                if hasattr(self.tracking, dict_name) and key in getattr(self.tracking, dict_name):
                    del getattr(self.tracking, dict_name)[key]
        except Exception as e:
            pass
    
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
            'graph_connected': self.graph_available,
            'qdrant_connected': self.qdrant_available,
            'errors': self.state['errors'][-10:],
            'tracking': {
                'topics': len(self.tracking['topics']),
                'entities': len(self.tracking['entities']),
            },
            'config': {
                'max_context_tokens': self.config['max_context_tokens'],
                'enable_rag': self.config['enable_rag'],
                'enable_tracking': self.config['enable_tracking']
            }
        }


# Teszt
if __name__ == "__main__":
    from scratchpad import Scratchpad
    
    s = Scratchpad()
    valet = Valet(s)
    
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
    
    valet.track_message(test_intent)
    context = valet.prepare_context(test_intent)
    print("Kontextus:", json.dumps(context, indent=2, default=str)[:500])
    print("\nÁllapot:", valet.get_state())