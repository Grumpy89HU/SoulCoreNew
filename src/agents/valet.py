"""
Valet (Lakáj) - A memória-logisztika és a Tények Őre.

KOMMUNIKÁCIÓS PROTOKOLL:
- A Valet HALLJA a Király beszédét a buszon keresztül
- A Valet visszaszól a buszon (target: "king")
- A belső működés nyelvfüggetlen, a hatékonyság a lényeg

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
import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union
from collections import defaultdict, deque
from pathlib import Path

# RAG komponensek
try:
    from src.rag.embedding_manager import EmbeddingManager
    from src.rag.reranker_manager import RerankerManager
    from src.rag.search_manager import SearchManager
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    print("⚠️ Valet: RAG komponensek nem elérhetők.")

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

# i18n import
try:
    from src.i18n.translator import get_translator
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False


class Valet:
    """
    A Lakáj - a memória őre.
    
    KOMMUNIKÁCIÓ:
    - Feliratkozik a buszra, hallja a Király beszédét
    - Ha a Király royal_decree-je érkezik, kontextust gyűjt
    - Visszaszól a buszon a Kingnek
    """
    
    # Emlék típusok
    MEMORY_TYPES = {
        'fact': 1,
        'event': 2,
        'preference': 3,
        'relationship': 4,
        'concept': 5,
        'conversation': 6,
        'emotion': 7,
        'decision': 8,
    }
    
    def __init__(self, scratchpad, message_bus=None, config: Dict = None, config_path: str = None):
        self.scratchpad = scratchpad
        self.bus = message_bus
        self.name = "valet"
        
        # Konfiguráció betöltése
        self.config = self._load_config(config, config_path)
        
        # Fordító (i18n)
        self.translator = None
        if I18N_AVAILABLE:
            self.translator = get_translator('en')
        
        # ========== RÖVID TÁVÚ MEMÓRIA ==========
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
        
        # ========== ÁLLAPOT ==========
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
        
        # ========== RAG 2.1 KOMPONENSEK ==========
        self.embedding_manager = None
        self.reranker_manager = None
        self.search_manager = None
        
        # ========== HOSSZÚ TÁVÚ MEMÓRIA (Vault) ==========
        self.graph_driver = None
        self.graph_available = False
        self._init_graph_vault()
        
        self.qdrant_client = None
        self.qdrant_available = False
        self._init_vector_vault()
        
        self.embedder = None
        
        # Jelenlegi kérés trace_id (válaszokhoz)
        self.current_trace_id = None
        
        # RAG komponensek inicializálása (Vault után)
        self._init_embedding()
        self._init_reranker()
        self._init_search()
        
        # Ha van busz, feliratkozunk
        if self.bus:
            self.bus.subscribe(self.name, self._on_message)
        
        print("👔 Valet: Lakáj ébred. Őrzöm a tényeket.")
        self._report_vault_status()
        if self.bus:
            print("👔 Valet: Broadcast módban működöm, hallgatom a Király szavát.")
    
    def _load_config(self, config: Dict = None, config_path: str = None) -> Dict:
        """Konfiguráció betöltése fájlból vagy dict-ből"""
        
        # Alapértelmezett konfiguráció
        default_config = {
            'max_context_tokens': 1500,
            'max_recent_messages': 5,
            'summary_length': 200,
            'context_compression': True,
            'enable_tracking': True,
            'max_tracking_items': 1000,
            'enable_validation': True,
            'enable_rag': True,
            'vector_search_limit': 5,
            'graph_search_limit': 3,
            'similarity_threshold': 0.7,
            'emotional_weight': 0.3,
            'important_threshold': 0.7,
            'forget_after_days': 30,
            'enable_auto_archive': True,
            'archive_after_days': 90,
            'neo4j_uri': 'bolt://localhost:7687',
            'neo4j_user': 'neo4j',
            'neo4j_password': 'soulcore2026',
            'qdrant_host': 'localhost',
            'qdrant_port': 6333,
            'embedding_size': 1024,
            'embedding': {
                'enabled': True,
                'type': 'sentence-transformers',
                'model': 'all-MiniLM-L6-v2',
                'cache_ttl': 86400,
                'fallback_size': 384
            },
            'reranker': {
                'enabled': False,
                'type': 'cross-encoder',
                'model': 'cross-encoder/ms-marco-MiniLM-L-6-v2',
                'cache_ttl': 86400
            },
            'search': {
                'enabled': True,
                'search_type': 'internal',
                'cache_ttl': 86400,
                'max_cache_entries': 1000
            }
        }
        
        # Ha van átadott config dict, azzal bővítjük
        if config:
            for key, value in config.items():
                if key in default_config and isinstance(value, dict) and isinstance(default_config[key], dict):
                    default_config[key].update(value)
                else:
                    default_config[key] = value
        
        # Ha van config fájl, betöltjük
        if config_path and Path(config_path).exists():
            try:
                import yaml
                with open(config_path, 'r', encoding='utf-8') as f:
                    file_config = yaml.safe_load(f)
                    if file_config:
                        if 'valet' in file_config:
                            for key, value in file_config['valet'].items():
                                if key in default_config and isinstance(value, dict) and isinstance(default_config[key], dict):
                                    default_config[key].update(value)
                                else:
                                    default_config[key] = value
                        if 'vault' in file_config:
                            vault_config = file_config['vault']
                            if 'neo4j' in vault_config:
                                default_config['neo4j_uri'] = vault_config['neo4j'].get('uri', default_config['neo4j_uri'])
                                default_config['neo4j_user'] = vault_config['neo4j'].get('user', default_config['neo4j_user'])
                                default_config['neo4j_password'] = vault_config['neo4j'].get('password', default_config['neo4j_password'])
                            if 'qdrant' in vault_config:
                                default_config['qdrant_host'] = vault_config['qdrant'].get('host', default_config['qdrant_host'])
                                default_config['qdrant_port'] = vault_config['qdrant'].get('port', default_config['qdrant_port'])
                        if 'embedding' in file_config:
                            default_config['embedding'].update(file_config['embedding'])
                        if 'reranker' in file_config:
                            default_config['reranker'].update(file_config['reranker'])
                        if 'search' in file_config:
                            default_config['search'].update(file_config['search'])
                print(f"👔 Valet: Konfiguráció betöltve: {config_path}")
            except Exception as e:
                print(f"⚠️ Valet: Konfiguráció betöltési hiba: {e}")
        
        return default_config
    
    # ========== BUSZ KOMMUNIKÁCIÓ ==========
    
    def _on_message(self, message: Dict):
        """
        Hallja a buszon érkező üzeneteket.
        Ha a Király royal_decree-je érkezik, kontextust gyűjt.
        """
        header = message.get('header', {})
        payload = message.get('payload', {})
        
        # Csak a Király beszédére reagálunk
        if header.get('sender') != 'king':
            return
        
        # Csak royal_decree típusra
        if payload.get('type') != 'royal_decree':
            return
        
        # Ellenőrizzük, hogy kell-e a Valet
        required_agents = payload.get('required_agents', [])
        if self.name not in required_agents:
            return
        
        self.current_trace_id = header.get('trace_id', '')
        user_message = payload.get('user_message', '')
        interpretation = payload.get('interpretation', {})
        
        # Kontextus gyűjtése
        context = self.prepare_context_for_king(user_message, interpretation)
        
        # Válasz küldése a Kingnek
        response = {
            "header": {
                "trace_id": str(uuid.uuid4()),
                "timestamp": time.time(),
                "sender": self.name,
                "target": "king",
                "in_response_to": self.current_trace_id
            },
            "payload": {
                "type": "context_response",
                "context": context,
                "validation_warning": context.get('validation_warning')
            }
        }
        
        self.bus.send_response(response)
        
        # Naplózás ha van warning
        if context.get('validation_warning'):
            print(f"👔 Valet: ⚠️ Hallucináció-gát aktiválva - {context['validation_warning'][:50]}...")
        else:
            print(f"👔 Valet: Kontextus küldve a Kingnek ({self.current_trace_id[:8]})")
    
    # ========== KONTEXTUS ÖSSZEÁLLÍTÁS ==========
    
    def prepare_context_for_king(self, user_message: str, interpretation: Dict) -> Dict[str, Any]:
        """
        Kontextus összeállítása a King számára.
        """
        context = {
            'summary': '',
            'facts': [],
            'recent': [],
            'warnings': [],
            'rag_results': [],
            'graph_context': [],
            'vector_context': [],
            'emotional_context': {},
            'important_memories': [],
            'token_estimate': 0,
            'validation_warning': None,
            'timestamp': time.time()
        }
        
        try:
            # 1. Rövid távú memória (Scratchpad)
            context['recent'] = self._process_recent_messages(
                self.scratchpad.read(limit=self.config['max_recent_messages'])
            )
            
            # 2. Tények kinyerése
            facts = self._extract_facts(context['recent'])
            context['facts'] = facts[:5]
            
            # 3. Fontos emlékek
            important = self._get_important_memories(interpretation, 3)
            context['important_memories'] = important
            
            # 4. RAG keresés (ha be van kapcsolva)
            rag_context = {'graph': [], 'vector': [], 'combined': []}
            if self.config['enable_rag']:
                rag_context = self._rag_search(user_message, interpretation, facts, important)
                context['rag_results'] = rag_context.get('combined', [])[:3]
                context['graph_context'] = rag_context.get('graph', [])
                context['vector_context'] = rag_context.get('vector', [])
                self.state['rag_searches'] += 1
            
            # 5. Érzelmi kontextus
            context['emotional_context'] = self._get_emotional_context(interpretation)
            
            # 6. Összefoglaló
            if self.config['context_compression']:
                context['summary'] = self._create_compressed_summary(
                    user_message, facts, context.get('rag_results', []), important
                )
                self.state['context_compressions'] += 1
            else:
                context['summary'] = self._create_summary(user_message, facts)
            
            # 7. HALLUCINÁCIÓ-GÁT (aktív validáció)
            if self.config['enable_validation']:
                validation_result = self._validate_context(
                    user_message=user_message,
                    intent=interpretation.get('intent', {}),
                    facts=facts,
                    rag_results=rag_context.get('combined', []),
                    graph_context=rag_context.get('graph', [])
                )
                
                if validation_result:
                    context['validation_warning'] = validation_result.get('warning')
                    context['warnings'].append(validation_result.get('warning'))
                    
                    if validation_result.get('has_contradiction'):
                        self.state['warnings_issued'] += 1
                        context['summary'] = f"[VALIDATION] {validation_result.get('warning')}\n" + context['summary']
            
            # 8. Token becslés
            context['token_estimate'] = self._estimate_tokens(context)
            
        except Exception as e:
            error_msg = f"prepare_context hiba: {e}"
            self.state['errors'].append(error_msg)
            print(f"👔 Valet hiba: {error_msg}")
        
        return context
    
    def _rag_search(self, user_message: str, interpretation: Dict, 
                    facts: List[str], important_memories: List[str]) -> Dict[str, List[str]]:
        """
        RAG 2.1 keresés - kétkulcsos (vektor + gráf) + embedding + reranker + search cache
        """
        result = {
            'graph': [],
            'vector': [],
            'combined': []
        }
        
        try:
            intent = interpretation.get('intent', {}).get('class', 'unknown') if isinstance(interpretation, dict) else 'unknown'
            
            # 1. SEARCH CACHE (ha van) - KERESÉSI ELŐZMÉNYEK
            search_results = []
            if self.search_manager:
                search_results = self.search_manager.search(
                    query=user_message,
                    limit=self.config['vector_search_limit'] * 2,
                    filters={'intent': intent}
                )
            
            # 2. GRÁF KERESÉS (Neo4j)
            if self.graph_available:
                graph_results = self._graph_search(user_message, intent)
                result['graph'] = graph_results
            
            # 3. VEKTOROS KERESÉS (Qdrant) - embedding használatával
            if self.qdrant_available and self.embedding_manager:
                vector_results = self._vector_search_with_embedding(user_message)
                result['vector'] = vector_results
            
            # 4. ÖSSZES JELÖLT ÖSSZEGYŰJTÉSE (rerankerhez)
            all_candidates = []
            
            for r in result['graph']:
                if r:
                    all_candidates.append({'text': r, 'source': 'graph', 'score': 0.8})
            for r in result['vector']:
                if r:
                    all_candidates.append({'text': r, 'source': 'vector', 'score': 0.7})
            for f in facts:
                if f:
                    all_candidates.append({'text': f, 'source': 'facts', 'score': 0.6})
            for m in important_memories:
                if m:
                    all_candidates.append({'text': m, 'source': 'memory', 'score': 0.5})
            for sr in search_results:
                if isinstance(sr, dict) and sr.get('text'):
                    all_candidates.append({'text': sr['text'], 'source': 'cache', 'score': sr.get('score', 0.7)})
            
            # 5. RERANKER (ha van) VAGY EGYSZERŰ ÖSSZEFÉSÜLÉS
            if self.reranker_manager and len(all_candidates) > 1:
                reranked = self.reranker_manager.rerank_with_scores(
                    query=user_message,
                    documents=all_candidates,
                    top_k=self.config['vector_search_limit']
                )
                for item in reranked:
                    source_prefix = item.get('source', 'UNK').upper()
                    result['combined'].append(f"[{source_prefix}] {item.get('text', '')[:150]}")
            else:
                # Egyszerű összefésülés (reranker nélkül)
                all_results = []
                all_results.extend([f"[Gráf] {r[:150]}" for r in result['graph'] if r])
                all_results.extend([f"[Vektor] {r[:150]}" for r in result['vector'] if r])
                all_results.extend([f"[Tény] {f[:150]}" for f in facts if f])
                all_results.extend([f"[Emlék] {m[:150]}" for m in important_memories if m])
                for sr in search_results:
                    if isinstance(sr, dict) and sr.get('text'):
                        all_results.append(f"[Cache] {sr['text'][:150]}")
                
                # Duplikáció szűrés
                seen = set()
                for res in all_results:
                    key = hashlib.md5(res.encode()).hexdigest() if isinstance(res, str) else str(res)
                    if key not in seen:
                        seen.add(key)
                        result['combined'].append(res)
            
            self.state['rag_searches'] += 1
                
        except Exception as e:
            self.state['errors'].append(f"RAG keresési hiba: {e}")
        
        return result
    
    def _graph_search(self, text: str, intent: str) -> List[str]:
        """Gráf keresés Neo4j-ben"""
        results = []
        
        if not self.graph_available:
            return results
        
        try:
            with self.graph_driver.session() as session:
                query = """
                MATCH (t:Topic {name: $topic})<-[:MENTIONS]-(m:Memory)-[:MENTIONS]->(e:Entity)
                WHERE m.emotional_charge IS NOT NULL
                RETURN e.name as entity, m.emotional_charge as charge, 
                       m.created_at as created
                ORDER BY m.created_at DESC
                LIMIT 5
                """
                
                result = session.run(query, topic=intent if intent else text[:50])
                for record in result:
                    entity = record.get('entity', '')
                    charge = record.get('charge', 0) if record.get('charge') else 0
                    if entity:
                        charge_str = "😊" if charge > 0.3 else "😐" if charge > -0.3 else "😞"
                        results.append(f"{entity} {charge_str}")
                
                query2 = """
                MATCH (p:Person)-[r:RELATIONSHIP]-(e:Entity)
                WHERE r.emotional_charge IS NOT NULL
                RETURN e.name as entity, r.type as type, r.emotional_charge as charge
                ORDER BY r.updated_at DESC
                LIMIT 5
                """
                
                result = session.run(query2)
                for record in result:
                    entity = record.get('entity', '')
                    charge = record.get('charge', 0) if record.get('charge') else 0
                    if entity and abs(charge) > 0.3:
                        rel_type = record.get('type', 'kapcsolat')
                        results.append(f"{entity} ({rel_type})")
                    
        except Exception as e:
            self.state['errors'].append(f"Gráf keresési hiba: {e}")
        
        return results
    
    def _vector_search_with_embedding(self, text: str) -> List[str]:
        """
        Vektoros keresés az embedding manager használatával.
        """
        results = []
        
        if not self.qdrant_available or not self.embedding_manager:
            return results
        
        try:
            embedding = self.embedding_manager.embed(text)
            if not embedding:
                return results
            
            search_result = self.qdrant_client.search(
                collection_name='personal_memories',
                query_vector=embedding,
                limit=self.config['vector_search_limit'],
                score_threshold=self.config['similarity_threshold']
            )
            
            for hit in search_result:
                if hit.payload and 'content' in hit.payload:
                    content = hit.payload['content'][:150]
                    results.append(f"{content} (score: {hit.score:.2f})")
                    
        except Exception as e:
            self.state['errors'].append(f"Vektoros keresési hiba: {e}")
        
        return results
    
    def _vector_search_for_cache(self, query: str, limit: int, filters: Dict) -> List[Dict]:
        """
        Cache-elt kereséshez használt vektoros keresés.
        A SearchManager számára készített formátumban ad vissza eredményt.
        """
        results = []
        
        if not self.qdrant_available or not self.embedding_manager:
            return results
        
        try:
            embedding = self.embedding_manager.embed(query)
            if not embedding:
                return results
            
            search_result = self.qdrant_client.search(
                collection_name='personal_memories',
                query_vector=embedding,
                limit=limit,
                score_threshold=self.config['similarity_threshold']
            )
            
            for hit in search_result:
                if hit.payload:
                    results.append({
                        'text': hit.payload.get('content', '')[:200],
                        'score': hit.score,
                        'metadata': {k: v for k, v in hit.payload.items() if k != 'content'}
                    })
                    
        except Exception as e:
            self.state['errors'].append(f"Cache keresési hiba: {e}")
        
        return results
    
    def _vector_search(self, text: str) -> List[str]:
        """Régi vektoros keresés (kompatibilitás)"""
        return self._vector_search_with_embedding(text)
    
    def _get_emotional_context(self, interpretation: Dict) -> Dict:
        """Érzelmi kontextus lekérése"""
        emotional = {
            'current_charge': 0.0,
            'recent_mood': 'neutral'
        }
        
        try:
            intent = interpretation.get('intent', {}).get('class', 'unknown') if isinstance(interpretation, dict) else 'unknown'
            
            if intent in self.tracking['emotional_charge']:
                emotional['current_charge'] = self.tracking['emotional_charge'][intent]
            
            charge = emotional['current_charge']
            if charge > 0.3:
                emotional['recent_mood'] = 'positive'
            elif charge < -0.3:
                emotional['recent_mood'] = 'negative'
            
        except Exception as e:
            self.state['errors'].append(f"Érzelmi kontextus hiba: {e}")
        
        return emotional
    
    def _validate_context(self, user_message: str, intent: Dict, facts: List[str], 
                          rag_results: List[str], graph_context: List[str]) -> Optional[Dict]:
        """
        Hallucináció-gát - tények ellenőrzése és összevetése a szándékkal.
        
        A dokumentum 3.2 szerint:
        "Mielőtt a kérés továbbmegy a Királyi Trónra, a Valet összeveti a talált tényeket 
         a Scribe szándékával. Ha ellentmondást talál, egy WARNING flag-et szúr be a payload-ba."
        
        Returns:
            Dict with 'has_contradiction', 'warning', 'confidence' vagy None ha nincs gond
        """
        if not self.config['enable_validation']:
            return None
        
        contradictions = []
        warnings = []
        confidence = 1.0
        
        try:
            intent_class = intent.get('class', '').lower() if isinstance(intent, dict) else str(intent).lower()
            
            # 1. Szándék vs tények összevetése
            for fact in facts:
                if not isinstance(fact, str):
                    continue
                fact_lower = fact.lower()
                
                # Ellenőrizzük, hogy a tény ellentmond-e a szándéknak
                if intent_class == 'system_control' and 'nem' in fact_lower:
                    contradictions.append(f"System control requested but fact contradicts: {fact[:50]}")
                    confidence -= 0.2
                
                if intent_class == 'knowledge_retrieval' and 'nincs' in fact_lower and 'információ' in fact_lower:
                    warnings.append(f"Knowledge retrieval may be incomplete: {fact[:50]}")
                    confidence -= 0.1
            
            # 2. RAG eredmények vs szándék
            for result in rag_results:
                if not isinstance(result, str):
                    continue
                
                if 'error' in result.lower() or 'hiba' in result.lower():
                    warnings.append(f"RAG result indicates potential issue: {result[:50]}")
                    confidence -= 0.15
            
            # 3. Gráf kontextus ellenőrzése
            for ctx in graph_context:
                if not isinstance(ctx, str):
                    continue
                
                if '😞' in ctx or '😐' in ctx:
                    if intent_class in ['knowledge_retrieval', 'system_control']:
                        warnings.append(f"Emotional context may affect response quality: {ctx[:40]}")
                        confidence -= 0.1
            
            # 4. Duplikáció ellenőrzés
            seen_facts = set()
            for fact in facts:
                if isinstance(fact, str):
                    fact_hash = hashlib.md5(fact.encode()).hexdigest()[:8]
                    if fact_hash in seen_facts:
                        warnings.append(f"Duplicate fact detected: {fact[:30]}...")
                        confidence -= 0.05
                    seen_facts.add(fact_hash)
            
            # 5. Logikai ellentmondások keresése
            if len(facts) >= 2:
                for i, fact1 in enumerate(facts):
                    for fact2 in facts[i+1:]:
                        if self._check_logical_contradiction(fact1, fact2):
                            contradictions.append(f"Logical contradiction: '{fact1[:40]}' vs '{fact2[:40]}'")
                            confidence -= 0.3
            
            # Eredmény összeállítása
            if contradictions:
                return {
                    'has_contradiction': True,
                    'warning': f"⚠️ VALIDATION: Contradiction detected - {contradictions[0]}",
                    'confidence': max(0.0, confidence),
                    'contradictions': contradictions[:3],
                    'warnings': warnings[:3]
                }
            elif warnings:
                return {
                    'has_contradiction': False,
                    'warning': f"⚠️ CAUTION: {warnings[0]}",
                    'confidence': max(0.0, confidence),
                    'warnings': warnings[:3]
                }
            
            return None
            
        except Exception as e:
            self.state['errors'].append(f"Validálási hiba: {e}")
            return {
                'has_contradiction': False,
                'warning': f"Validation error: {e}",
                'confidence': 0.5
            }
    
    def _check_logical_contradiction(self, fact1: str, fact2: str) -> bool:
        """
        Két tény logikai ellentmondásának ellenőrzése.
        """
        if not isinstance(fact1, str) or not isinstance(fact2, str):
            return False
        
        fact1_lower = fact1.lower()
        fact2_lower = fact2.lower()
        
        # Igen/nem ellentmondások
        if ('nem' in fact1_lower and 'igen' in fact2_lower) or \
           ('igen' in fact1_lower and 'nem' in fact2_lower):
            words1 = set(fact1_lower.split())
            words2 = set(fact2_lower.split())
            common = words1 & words2
            if len(common) >= 2:
                return True
        
        return False
    
    # ========== MEMÓRIA TÁROLÁS ==========
    
    def remember(self, key: str, value: Any, memory_type: str = 'fact',
                 importance: float = 0.5, emotional_charge: float = 0.0,
                 entities: List[Dict] = None):
        """Információ elmentése a hosszú távú memóriába"""
        try:
            memory_id = f"{memory_type}_{int(time.time())}_{hashlib.md5(str(key).encode()).hexdigest()[:8]}"
            now = time.time()
            
            # 1. Neo4j (Graph-Vault)
            if self.graph_available:
                self._store_in_graph(key, value, memory_type, emotional_charge, entities)
            
            # 2. Qdrant (Vector-Vault)
            if self.qdrant_available and self.embedding_manager and isinstance(value, str):
                self._store_in_vector(key, value, memory_type, importance)
            
            # 3. Scratchpad
            if importance > self.config['important_threshold']:
                memory = {
                    'id': memory_id,
                    'key': key,
                    'value': value,
                    'type': memory_type,
                    'importance': importance,
                    'emotional_charge': emotional_charge,
                    'created': now
                }
                self.scratchpad.write_note(self.name, f"memory_{memory_id}", memory)
                self.state['memories_stored'] += 1
            
            # 4. Tracking
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
                session.run("""
                    CREATE (m:Memory {
                        uuid: $uuid,
                        key: $key,
                        content: $content,
                        type: $type,
                        emotional_charge: $emotional_charge,
                        created_at: datetime()
                    })
                """, uuid=hashlib.md5(str(key).encode()).hexdigest(),
                    key=str(key)[:200], content=str(value)[:500], type=memory_type,
                    emotional_charge=emotional_charge)
                
        except Exception as e:
            self.state['errors'].append(f"Graph tárolási hiba: {e}")
    
    def _store_in_vector(self, key: str, value: str, memory_type: str, importance: float):
        """Tárolás Qdrant-ben"""
        if not self.qdrant_available or not self.embedding_manager:
            return
        
        try:
            embedding = self.embedding_manager.embed(value)
            if not embedding:
                return
            
            self.qdrant_client.upsert(
                collection_name='personal_memories',
                points=[qdrant_models.PointStruct(
                    id=hashlib.md5(str(key).encode()).hexdigest(),
                    vector=embedding,
                    payload={
                        'key': str(key)[:200],
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
        """Tracking frissítése"""
        try:
            key_str = str(key)
            self.tracking['importance'][key_str] = max(
                self.tracking['importance'].get(key_str, 0), importance
            )
            self.tracking['emotional_charge'][key_str] = emotional_charge
            self.tracking['first_seen'].setdefault(key_str, time.time())
            self.tracking['mention_count'][key_str] += 1
            self.tracking['last_mentioned'][key_str] = time.time()
            
            if isinstance(key, str):
                for word in key.split():
                    if len(word) > 3:
                        self.similarity_index[word.lower()].add(key)
                        
        except Exception as e:
            self.state['errors'].append(f"Tracking frissítési hiba: {e}")
    
    def recall(self, key: str, default=None):
        """Információ előhívása"""
        try:
            if self.graph_available:
                with self.graph_driver.session() as session:
                    result = session.run("""
                        MATCH (m:Memory {key: $key})
                        RETURN m.content as content
                        LIMIT 1
                    """, key=str(key)[:200]).single()
                    if result:
                        return result['content']
            
            value = self.scratchpad.read_note(self.name, f"recent_{key}")
            if value is not None:
                return value
            
        except Exception as e:
            self.state['errors'].append(f"Hiba a felidézésben: {e}")
        
        return default
    
    # ========== GRAPH-VAULT INTEGRÁCIÓ (KING SZÁMÁRA) ==========
    
    def get_emotional_charge(self, topic: str) -> float:
        """
        Egy adott téma érzelmi töltésének lekérése.
        A King ezt használja a hangulatfüggő válaszadáshoz.
        """
        if not self.graph_available:
            return 0.0
        
        try:
            with self.graph_driver.session() as session:
                # Próbáljuk Topic-ként
                result = session.run(
                    """
                    MATCH (t:Topic {name: $topic})
                    OPTIONAL MATCH (t)<-[:MENTIONS]-(m:Memory)
                    RETURN avg(m.emotional_charge) as avg_charge
                    """,
                    topic=topic
                )
                record = result.single()
                if record and record['avg_charge'] is not None:
                    return float(record['avg_charge'])
                
                # Próbáljuk Entity-ként
                result = session.run(
                    """
                    MATCH (e:Entity {name: $topic})
                    OPTIONAL MATCH (e)<-[:MENTIONS]-(m:Memory)
                    RETURN avg(m.emotional_charge) as avg_charge
                    """,
                    topic=topic
                )
                record = result.single()
                if record and record['avg_charge'] is not None:
                    return float(record['avg_charge'])
                
                return 0.0
        except Exception as e:
            self.state['errors'].append(f"get_emotional_charge hiba: {e}")
            return 0.0
    
    def get_related_topics(self, topic: str, limit: int = 5) -> List[str]:
        """
        Kapcsolódó témák lekérése.
        """
        if not self.graph_available:
            return []
        
        try:
            with self.graph_driver.session() as session:
                result = session.run(
                    """
                    MATCH (t:Topic {name: $topic})
                    OPTIONAL MATCH (t)<-[:MENTIONS]-(m:Memory)-[:MENTIONS]->(related:Topic)
                    WHERE related.name <> $topic
                    RETURN related.name as name, count(m) as weight
                    ORDER BY weight DESC
                    LIMIT $limit
                    """,
                    topic=topic,
                    limit=limit
                )
                topics = []
                for record in result:
                    name = record.get('name')
                    if name:
                        topics.append(name)
                return topics
        except Exception as e:
            self.state['errors'].append(f"get_related_topics hiba: {e}")
            return []
    
    # ========== MEGLÉVŐ FUNKCIÓK (kompatibilitás) ==========
    
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
        """Tények kinyerése (nyelvfüggetlen)"""
        facts = []
        patterns = [
            (r'\b\d{4}[-.]\d{1,2}[-.]\d{1,2}\b', 'date'),
            (r'\b\d+\b', 'number'),
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
    
    def _get_important_memories(self, interpretation: Dict, limit: int = 3) -> List[str]:
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
                    important.append(str(memory))
        except Exception as e:
            self.state['errors'].append(f"Hiba a fontos emlékek lekérésében: {e}")
        return important
    
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
    
    def _create_summary(self, user_message: str, facts: List[str]) -> str:
        """Rövid összefoglaló"""
        if not facts:
            return f"User message: {user_message[:100]}"
        fact_summary = ". ".join(str(f) for f in facts[:3])
        return f"User: {user_message[:50]} | Facts: {fact_summary}"
    
    def _create_compressed_summary(self, user_message: str, facts: List[str],
                                   rag_results: List[str], important_memories: List[str]) -> str:
        """Tömörített összefoglaló"""
        parts = []
        
        if facts:
            important_facts = facts[:2]
            if important_facts:
                parts.append("📌 " + "; ".join(important_facts[:30]))
        if rag_results:
            parts.append("🔗 " + "; ".join(rag_results[:2]))
        if important_memories:
            parts.append("💭 " + "; ".join(important_memories))
        if user_message:
            parts.append(f"💬 {user_message[:30]}")
        
        summary = " | ".join(parts) if parts else "No context available"
        return summary[:self.config['summary_length']]
    
    def track_message(self, intent_packet: Dict):
        """Üzenet nyomon követése (kompatibilitás)"""
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
        """Érzelmi töltés becslése (nyelvfüggetlen)"""
        if not isinstance(text, str):
            return 0.0
        
        text_lower = text.lower()
        positive_words = ['good', 'great', 'love', 'like', 'happy', 'jó', 'szuper', 'remek', 'köszönöm', 'szíves']
        negative_words = ['bad', 'terrible', 'hate', 'error', 'rossz', 'szar', 'hiba', 'nem működik', 'dühös']
        
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
    
    # ========== VAULT INICIALIZÁLÁS ==========
    
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
            with self.graph_driver.session() as session:
                result = session.run("RETURN 1 as test")
                result.single()
            
            self.graph_available = True
            self.state['graph_connected'] = True
            print("   ✅ Neo4j Graph-Vault: kapcsolódva")
            self._ensure_graph_schema()
            
        except Exception as e:
            print(f"   ❌ Neo4j kapcsolat sikertelen: {e}")
            self.graph_available = False
            self.state['errors'].append(f"Neo4j: {e}")
    
    def _ensure_graph_schema(self):
        """Graph séma inicializálása"""
        if not self.graph_available:
            return
        
        try:
            with self.graph_driver.session() as session:
                # Constraints
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (m:Memory) REQUIRE m.uuid IS UNIQUE")
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (t:Topic) REQUIRE t.name IS UNIQUE")
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (e:Entity) REQUIRE e.name IS UNIQUE")
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (p:Person) REQUIRE p.uuid IS UNIQUE")
                
                # Indexes
                session.run("CREATE INDEX IF NOT EXISTS FOR (m:Memory) ON (m.created_at)")
                session.run("CREATE INDEX IF NOT EXISTS FOR (t:Topic) ON (t.name)")
                session.run("CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.name)")
                session.run("CREATE INDEX IF NOT EXISTS FOR ()-[r:MENTIONS]-() ON (r.emotional_charge)")
                session.run("CREATE INDEX IF NOT EXISTS FOR ()-[r:RELATIONSHIP]-() ON (r.emotional_charge)")
                
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
    
    # ========== RAG KOMPONENSEK INICIALIZÁLÁSA ==========
    
    def _init_embedding(self):
        """Embedding manager inicializálása"""
        if not RAG_AVAILABLE:
            self.embedding_manager = None
            self.embedder = None
            print("   ⚠️ RAG komponensek nem elérhetők.")
            return
            
        try:
            embedding_config = self.config.get('embedding', {})
            if embedding_config.get('enabled', True):
                self.embedding_manager = EmbeddingManager(embedding_config)
                self.embedder = self.embedding_manager.embed
                print("   ✅ Embedding Manager inicializálva")
            else:
                print("   ⚠️ Embedding kikapcsolva")
                self.embedding_manager = None
                self.embedder = None
        except Exception as e:
            print(f"   ❌ Embedding Manager hiba: {e}")
            self.embedding_manager = None
            self.embedder = None
    
    def _init_reranker(self):
        """Reranker manager inicializálása"""
        if not RAG_AVAILABLE:
            self.reranker_manager = None
            return
            
        try:
            reranker_config = self.config.get('reranker', {})
            if reranker_config.get('enabled', False):
                self.reranker_manager = RerankerManager(reranker_config)
                print("   ✅ Reranker Manager inicializálva")
            else:
                print("   ⚠️ Reranker kikapcsolva")
                self.reranker_manager = None
        except Exception as e:
            print(f"   ❌ Reranker Manager hiba: {e}")
            self.reranker_manager = None
    
    def _init_search(self):
        """Search manager inicializálása"""
        if not RAG_AVAILABLE:
            self.search_manager = None
            return
            
        try:
            search_config = self.config.get('search', {})
            if search_config.get('enabled', True):
                self.search_manager = SearchManager(
                    config=search_config,
                    search_function=self._vector_search_for_cache
                )
                print("   ✅ Search Manager inicializálva (24h cache)")
            else:
                print("   ⚠️ Search kikapcsolva")
                self.search_manager = None
        except Exception as e:
            print(f"   ❌ Search Manager hiba: {e}")
            self.search_manager = None
    
    # ========== PUBLIKUS API ==========
    
    def set_embedder(self, embedder):
        """Embedding modell beállítása (kompatibilitás)"""
        self.embedder = embedder
        print("   ✅ Embedding modell beállítva")
    
    def set_language(self, language: str):
        """Nyelv beállítása (i18n)"""
        if self.translator and I18N_AVAILABLE:
            self.translator.set_language(language)
    
    def start(self):
        """Valet indítása"""
        self.state['status'] = 'ready'
        if self.scratchpad:
            self.scratchpad.set_state('valet_status', 'ready', self.name)
        print("👔 Valet: Készen állok.")
    
    def stop(self):
        """Valet leállítása"""
        self.state['status'] = 'stopped'
        if self.scratchpad:
            self.scratchpad.set_state('valet_status', 'stopped', self.name)
        if self.graph_driver:
            self.graph_driver.close()
        print("👔 Valet: Leállt.")
    
    def prepare_context(self, intent_packet: Dict) -> Dict:
        """Régi API kompatibilitás"""
        payload = intent_packet.get('payload', {})
        user_message = payload.get('text', '')
        interpretation = payload.get('intent', {})
        return self.prepare_context_for_king(user_message, interpretation)
    
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
            'graph_connected': self.graph_available,
            'qdrant_connected': self.qdrant_available,
            'errors': self.state['errors'][-10:],
            'tracking': {
                'topics': len(self.tracking['topics']),
                'entities': len(self.tracking['entities']),
            },
            'rag': {
                'embedding': self.embedding_manager.get_stats() if self.embedding_manager else None,
                'reranker': self.reranker_manager.get_stats() if self.reranker_manager else None,
                'search': self.search_manager.get_stats() if self.search_manager else None
            }
        }


# Teszt
if __name__ == "__main__":
    from src.memory.scratchpad import Scratchpad
    
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