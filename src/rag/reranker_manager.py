"""
Reranker Manager - Keresési eredmények újrarangsorolása.
Támogatja a különböző reranker modelleket (Cross-Encoder, Cohere, stb.)
"""

import time
import hashlib
import threading
import os
import random
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
import logging

logger = logging.getLogger(__name__)


class RerankerManager:
    """
    Reranker kezelő - a keresési eredmények pontosabbá tételéhez.
    
    Támogatott rerankerek:
    - Cross-Encoder (sentence-transformers)
    - Cohere Rerank API
    - HuggingFace reranker
    - Jina AI Reranker
    - Custom reranker
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.reranker = None
        self.reranker_type = None
        self.reranker_name = None
        self.cache = {}
        self.cache_ttl = self.config.get('cache_ttl', 86400)  # 24 óra
        self.cache_lock = threading.RLock()
        
        # Statisztikák
        self.stats = {
            'total_reranks': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'avg_time_ms': 0
        }
        
        # Reranker betöltése
        self._load_reranker()
        
        print(f"📊 RerankerManager: {self.reranker_type} reranker betöltve")
        if self.reranker_name:
            print(f"   Modell: {self.reranker_name}")
    
    def _load_reranker(self):
        """Reranker modell betöltése"""
        reranker_config = self.config.get('reranker', {})
        reranker_type = reranker_config.get('type', 'cross-encoder')
        reranker_name = reranker_config.get('model', 'cross-encoder/ms-marco-MiniLM-L-6-v2')
        
        self.reranker_type = reranker_type
        self.reranker_name = reranker_name
        
        try:
            if reranker_type == 'cross-encoder':
                self._load_cross_encoder(reranker_name)
            elif reranker_type == 'cohere':
                self._load_cohere(reranker_name)
            elif reranker_type == 'huggingface':
                self._load_huggingface(reranker_name)
            elif reranker_type == 'jina':
                self._load_jina(reranker_name)
            elif reranker_type == 'custom':
                self._load_custom(reranker_config.get('function'))
            else:
                raise ValueError(f"Ismeretlen reranker típus: {reranker_type}")
                
        except Exception as e:
            logger.error(f"Reranker betöltési hiba: {e}")
            self.reranker = None
            self.reranker_type = 'dummy'
    
    def _load_cross_encoder(self, model_name: str):
        """Cross-Encoder reranker betöltése"""
        try:
            from sentence_transformers import CrossEncoder
            self.reranker = CrossEncoder(model_name)
        except ImportError:
            logger.error("sentence-transformers nincs telepítve")
            raise
    
    def _load_cohere(self, model_name: str):
        """Cohere Rerank API"""
        try:
            import cohere
            api_key = self.config.get('cohere_api_key', os.environ.get('COHERE_API_KEY'))
            if not api_key:
                logger.warning("Cohere API kulcs nincs beállítva")
                self.reranker = None
                self.reranker_type = 'dummy'
                return
            self.reranker = cohere.Client(api_key)
        except ImportError:
            logger.error("cohere nincs telepítve")
            raise
    
    def _load_huggingface(self, model_name: str):
        """HuggingFace reranker"""
        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
            self.reranker = AutoModelForSequenceClassification.from_pretrained(model_name)
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        except ImportError:
            logger.error("transformers nincs telepítve")
            raise
    
    def _load_jina(self, model_name: str):
        """Jina AI Reranker"""
        try:
            from jina import Document, DocumentArray
            self.reranker = model_name
        except ImportError:
            logger.error("jina nincs telepítve")
            raise
    
    def _load_custom(self, func: Any):
        """Egyedi reranker függvény"""
        if func is None:
            logger.warning("Custom reranker function is None")
            self.reranker = None
            self.reranker_type = 'dummy'
            return
        
        if not callable(func):
            logger.warning(f"Custom reranker function is not callable: {type(func)}")
            self.reranker = None
            self.reranker_type = 'dummy'
            return
        
        self.reranker = func
        self.reranker_type = 'custom'
    
    def _get_cache_key(self, query: str, documents: List[str]) -> str:
        """Cache kulcs generálása"""
        if not documents:
            return hashlib.md5(f"{query}_empty".encode()).hexdigest()
        docs_hash = hashlib.md5(''.join(documents).encode()).hexdigest()
        return hashlib.md5(f"{query}_{docs_hash}".encode()).hexdigest()
    
    def rerank(self, query: str, documents: List[str], top_k: int = 5) -> List[Tuple[int, float]]:
        """
        Dokumentumok újrarangsorolása a query alapján.
        
        Args:
            query: keresési lekérdezés
            documents: dokumentumok listája
            top_k: hány eredményt adjon vissza
            
        Returns:
            List of (index, score) tuples, sorted by score descending
        """
        if not documents:
            return []
        
        cache_key = self._get_cache_key(query, documents)
        
        with self.cache_lock:
            if cache_key in self.cache:
                entry = self.cache[cache_key]
                if time.time() - entry['timestamp'] < self.cache_ttl:
                    self.stats['cache_hits'] += 1
                    return entry['results'][:top_k]
                else:
                    del self.cache[cache_key]
            
            self.stats['cache_misses'] += 1
        
        start_time = time.time()
        
        try:
            if self.reranker_type == 'cross-encoder' and self.reranker:
                pairs = [[query, doc] for doc in documents]
                scores = self.reranker.predict(pairs)
                results = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
                
            elif self.reranker_type == 'cohere' and self.reranker:
                response = self.reranker.rerank(
                    query=query,
                    documents=documents,
                    top_n=top_k,
                    model=self.reranker_name
                )
                results = [(r.index, r.relevance_score) for r in response.results]
                
            elif self.reranker_type == 'custom' and self.reranker:
                scores = self.reranker(query, documents)
                if isinstance(scores, list) and len(scores) == len(documents):
                    results = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
                else:
                    # Ha a custom függvény nem megfelelő formátumban ad vissza
                    results = [(i, 0.5) for i in range(len(documents))]
                
            elif self.reranker_type == 'dummy':
                # Dummy: véletlenszerű sorrend (de determinisztikus a cache miatt)
                random.seed(hashlib.md5(query.encode()).hexdigest())
                scores = [random.random() for _ in documents]
                results = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
                
            else:
                # Fallback: eredeti sorrend
                results = [(i, 0.5) for i in range(len(documents))]
            
            elapsed_ms = (time.time() - start_time) * 1000
            if self.stats['avg_time_ms'] == 0:
                self.stats['avg_time_ms'] = elapsed_ms
            else:
                self.stats['avg_time_ms'] = self.stats['avg_time_ms'] * 0.9 + elapsed_ms * 0.1
            
            self.stats['total_reranks'] += 1
            
            # Cache mentés
            with self.cache_lock:
                self.cache[cache_key] = {
                    'results': results,
                    'timestamp': time.time()
                }
            
            return results[:top_k]
            
        except Exception as e:
            logger.error(f"Reranking hiba: {e}")
            # Fallback: eredeti sorrend
            return [(i, 0.5) for i in range(len(documents))][:top_k]
    
    def rerank_with_scores(self, query: str, documents: List[Dict], 
                           top_k: int = 5) -> List[Dict]:
        """
        Dokumentumok újrarangsorolása, a score hozzáadásával.
        
        Args:
            query: keresési lekérdezés
            documents: dokumentumok listája (dict, text mezővel)
            top_k: hány eredményt adjon vissza
            
        Returns:
            Dokumentumok score-okkal kiegészítve
        """
        if not documents:
            return []
        
        texts = [doc.get('text', '') for doc in documents]
        reranked = self.rerank(query, texts, top_k)
        
        result = []
        for idx, score in reranked:
            if idx < len(documents):
                doc = documents[idx].copy()
                doc['rerank_score'] = score
                result.append(doc)
        
        return result
    
    def clear_cache(self):
        """Cache törlése"""
        with self.cache_lock:
            self.cache.clear()
            print("📊 RerankerManager: Cache törölve")
    
    def get_cache_stats(self) -> Dict:
        """Cache statisztikák lekérése"""
        with self.cache_lock:
            cache_entries = len(self.cache)
            cache_age = 0
            if self.cache:
                oldest = min(entry['timestamp'] for entry in self.cache.values())
                cache_age = time.time() - oldest
            
            return {
                'entries': cache_entries,
                'oldest_age_seconds': round(cache_age),
                'oldest_age_hours': round(cache_age / 3600, 1),
                'max_entries': self.config.get('max_cache_entries', 1000)
            }
    
    def get_stats(self) -> Dict:
        """Statisztikák lekérése"""
        return {
            'reranker_type': self.reranker_type,
            'reranker_name': self.reranker_name,
            'cache_size': len(self.cache),
            'total_reranks': self.stats['total_reranks'],
            'cache_hits': self.stats['cache_hits'],
            'cache_misses': self.stats['cache_misses'],
            'cache_hit_rate': round(self.stats['cache_hits'] / max(1, self.stats['cache_hits'] + self.stats['cache_misses']), 4),
            'avg_time_ms': round(self.stats['avg_time_ms'], 2),
            'cache_stats': self.get_cache_stats()
        }
    
    def is_available(self) -> bool:
        """Reranker elérhetőségének ellenőrzése"""
        return self.reranker is not None and self.reranker_type != 'dummy'
    
    def get_type(self) -> str:
        """Reranker típus lekérése"""
        return self.reranker_type