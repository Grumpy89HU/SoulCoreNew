"""
Embedding Manager - Univerzális embedding modell kezelő.
Támogatja a különböző embedding modelleket (Gemma, Qwen, Sentence-Transformers, stb.)
"""

import os
import time
import hashlib
import threading
import numpy as np
from typing import Dict, List, Any, Optional, Union, Callable
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)


class EmbeddingManager:
    """
    Embedding modell kezelő - univerzális interfész különböző embedding modellekhez.
    
    Támogatott modellek:
    - Sentence-Transformers (all-MiniLM-L6-v2, stb.)
    - Gemma embedding (gemma-embedding)
    - Qwen embedding (qwen-embedding)
    - OpenAI API (opcionális)
    - HuggingFace
    - Custom embedding függvény
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.model = None
        self.tokenizer = None
        self.model_type = None
        self.model_name = None
        self.embedding_size = None
        self.cache = {}
        self.cache_ttl = self.config.get('cache_ttl', 86400)  # 24 óra
        self.cache_lock = threading.RLock()
        
        # Statisztikák
        self.stats = {
            'total_embeddings': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'avg_time_ms': 0
        }
        
        # Modell betöltése
        self._load_model()
        
        print(f"🔢 EmbeddingManager: {self.model_type} modell betöltve")
        if self.model_name:
            print(f"   Modell: {self.model_name}")
        if self.embedding_size:
            print(f"   Dimenzió: {self.embedding_size}")
        print(f"   Cache: {self.cache_ttl}s")
    
    def _load_model(self):
        """Embedding modell betöltése a konfiguráció alapján"""
        # Beágyazott embedding konfiguráció (a vault alatt vagy külön)
        if 'embedding' in self.config:
            embedding_config = self.config.get('embedding', {})
        else:
            embedding_config = self.config
        
        model_type = embedding_config.get('type', 'sentence-transformers')
        model_name = embedding_config.get('model', 'all-MiniLM-L6-v2')
        
        self.model_type = model_type
        self.model_name = model_name
        
        try:
            if model_type == 'sentence-transformers':
                self._load_sentence_transformers(model_name)
            elif model_type == 'gemma':
                self._load_gemma(model_name)
            elif model_type == 'qwen':
                self._load_qwen(model_name)
            elif model_type == 'openai':
                self._load_openai(model_name)
            elif model_type == 'huggingface':
                self._load_huggingface(model_name)
            elif model_type == 'custom':
                self._load_custom(embedding_config.get('function'))
            else:
                raise ValueError(f"Ismeretlen embedding típus: {model_type}")
                
        except Exception as e:
            logger.error(f"Embedding modell betöltési hiba: {e}")
            # Fallback: dummy embedding
            self.embedding_size = embedding_config.get('fallback_size', 384)
            self.model = None
            self.model_type = 'dummy'
    
    def _load_sentence_transformers(self, model_name: str):
        """Sentence-Transformers modell betöltése"""
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(model_name)
            self.embedding_size = self.model.get_sentence_embedding_dimension()
        except ImportError:
            logger.error("sentence-transformers nincs telepítve")
            raise
    
    def _load_gemma(self, model_name: str):
        """Gemma embedding modell betöltése"""
        try:
            # Gemma embedding implementáció (llama.cpp alapú)
            from llama_cpp import Llama
            
            # Gemma embedding modell betöltése
            self.model = Llama(
                model_path=model_name,
                embedding=True,
                n_ctx=512,
                n_gpu_layers=-1,
                verbose=False
            )
            self.embedding_size = self.model.n_embd if hasattr(self.model, 'n_embd') else 768
            logger.info(f"Gemma embedding modell betöltve: {model_name}")
            
        except ImportError:
            logger.error("llama-cpp-python nincs telepítve a Gemma embeddinghez")
            raise
        except Exception as e:
            logger.error(f"Gemma embedding betöltési hiba: {e}")
            raise
    
    def _load_qwen(self, model_name: str):
        """Qwen embedding modell betöltése"""
        try:
            # Qwen embedding implementáció (llama.cpp alapú)
            from llama_cpp import Llama
            
            self.model = Llama(
                model_path=model_name,
                embedding=True,
                n_ctx=512,
                n_gpu_layers=-1,
                verbose=False
            )
            self.embedding_size = self.model.n_embd if hasattr(self.model, 'n_embd') else 1024
            logger.info(f"Qwen embedding modell betöltve: {model_name}")
            
        except ImportError:
            logger.error("llama-cpp-python nincs telepítve a Qwen embeddinghez")
            raise
        except Exception as e:
            logger.error(f"Qwen embedding betöltési hiba: {e}")
            raise
    
    def _load_openai(self, model_name: str):
        """OpenAI embedding API"""
        try:
            import openai
            
            api_key = self.config.get('openai_api_key', os.environ.get('OPENAI_API_KEY'))
            if not api_key:
                raise ValueError("OpenAI API key not found")
            
            openai.api_key = api_key
            self.model = openai
            
            # Dimenzió meghatározása
            if model_name == 'text-embedding-3-small':
                self.embedding_size = 1536
            elif model_name == 'text-embedding-3-large':
                self.embedding_size = 3072
            elif model_name == 'text-embedding-ada-002':
                self.embedding_size = 1536
            else:
                self.embedding_size = 1536
                
        except ImportError:
            logger.error("openai nincs telepítve")
            raise
        except Exception as e:
            logger.error(f"OpenAI embedding hiba: {e}")
            raise
    
    def _load_huggingface(self, model_name: str):
        """HuggingFace embedding modell"""
        try:
            from transformers import AutoModel, AutoTokenizer
            import torch
            
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModel.from_pretrained(model_name)
            self.model.eval()
            
            # Dimenzió meghatározása
            self.embedding_size = self.model.config.hidden_size
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            self.model.to(self.device)
            
            logger.info(f"HuggingFace embedding modell betöltve: {model_name}")
            
        except ImportError:
            logger.error("transformers nincs telepítve")
            raise
        except Exception as e:
            logger.error(f"HuggingFace embedding hiba: {e}")
            raise
    
    def _load_custom(self, func: Any):
        """Egyedi embedding függvény"""
        if func is None:
            logger.warning("Custom embedding function is None, using dummy")
            self.embedding_size = self.config.get('fallback_size', 384)
            self.model = None
            self.model_type = 'dummy'
            return
        
        if not callable(func):
            logger.warning(f"Custom embedding function is not callable: {type(func)}")
            self.embedding_size = self.config.get('fallback_size', 384)
            self.model = None
            self.model_type = 'dummy'
            return
        
        self.model = func
        self.model_type = 'custom'
        # A dimenziót a függvény első hívásakor határozzuk meg
        self.embedding_size = None
    
    def _get_cache_key(self, text: str) -> str:
        """Cache kulcs generálása a szöveghez"""
        return hashlib.md5(text.encode()).hexdigest()
    
    def embed(self, text: str) -> List[float]:
        """
        Szöveg embedding vektorának lekérése.
        Cache-elve (24 óra).
        """
        if not text:
            return []
        
        cache_key = self._get_cache_key(text)
        
        with self.cache_lock:
            if cache_key in self.cache:
                entry = self.cache[cache_key]
                if time.time() - entry['timestamp'] < self.cache_ttl:
                    self.stats['cache_hits'] += 1
                    return entry['vector']
                else:
                    del self.cache[cache_key]
            
            self.stats['cache_misses'] += 1
        
        start_time = time.time()
        
        try:
            vector = self._generate_embedding(text)
            
            # Dimenzió ellenőrzés
            if self.embedding_size is None:
                self.embedding_size = len(vector)
            
            # Normalizálás
            vector = self._normalize(vector)
            
            # Cache mentés
            with self.cache_lock:
                self.cache[cache_key] = {
                    'vector': vector,
                    'timestamp': time.time()
                }
            
            # Statisztika
            elapsed_ms = (time.time() - start_time) * 1000
            if self.stats['avg_time_ms'] == 0:
                self.stats['avg_time_ms'] = elapsed_ms
            else:
                self.stats['avg_time_ms'] = self.stats['avg_time_ms'] * 0.9 + elapsed_ms * 0.1
            
            self.stats['total_embeddings'] += 1
            
            return vector
            
        except Exception as e:
            logger.error(f"Embedding hiba: {e}")
            return []
    
    def _generate_embedding(self, text: str) -> List[float]:
        """Embedding generálása a betöltött modell alapján"""
        
        if self.model_type == 'sentence-transformers':
            return self.model.encode(text).tolist()
        
        elif self.model_type == 'gemma' or self.model_type == 'qwen':
            # Llama.cpp alapú embedding
            if hasattr(self.model, 'embed'):
                embedding = self.model.embed(text)
                if hasattr(embedding, 'tolist'):
                    return embedding.tolist()
                return embedding
            else:
                raise ValueError(f"Modell nem támogatja az embedding-et: {self.model_type}")
        
        elif self.model_type == 'openai':
            # OpenAI API
            response = self.model.Embedding.create(
                input=[text],
                model=self.model_name
            )
            return response['data'][0]['embedding']
        
        elif self.model_type == 'huggingface':
            # HuggingFace transformers
            import torch
            
            inputs = self.tokenizer(text, return_tensors='pt', truncation=True, max_length=512)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            with torch.no_grad():
                outputs = self.model(**inputs)
                # Mean pooling
                embeddings = outputs.last_hidden_state.mean(dim=1)
                vector = embeddings[0].cpu().numpy().tolist()
            return vector
        
        elif self.model_type == 'custom':
            result = self.model(text)
            if hasattr(result, 'tolist'):
                return result.tolist()
            return result
        
        elif self.model_type == 'dummy':
            import random
            random.seed(hashlib.md5(text.encode()).hexdigest())
            return [random.random() for _ in range(self.embedding_size)]
        
        else:
            raise ValueError(f"Ismeretlen modell típus: {self.model_type}")
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Több szöveg embeddingje (batch)"""
        results = []
        for text in texts:
            results.append(self.embed(text))
        return results
    
    def _normalize(self, vector: List[float]) -> List[float]:
        """Vektor normalizálása (L2)"""
        import math
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
            return [v / norm for v in vector]
        return vector
    
    def clear_cache(self):
        """Cache törlése"""
        with self.cache_lock:
            self.cache.clear()
            print("🔢 EmbeddingManager: Cache törölve")
    
    def get_stats(self) -> Dict:
        """Statisztikák lekérése"""
        return {
            'model_type': self.model_type,
            'model_name': self.model_name,
            'embedding_size': self.embedding_size,
            'cache_size': len(self.cache),
            'total_embeddings': self.stats['total_embeddings'],
            'cache_hits': self.stats['cache_hits'],
            'cache_misses': self.stats['cache_misses'],
            'cache_hit_rate': round(self.stats['cache_hits'] / max(1, self.stats['cache_hits'] + self.stats['cache_misses']), 3),
            'avg_time_ms': round(self.stats['avg_time_ms'], 2)
        }
    
    def get_embedding_dimension(self) -> int:
        """Embedding dimenzió lekérése"""
        return self.embedding_size or 0
    
    def is_available(self) -> bool:
        """Embedding elérhetősége"""
        return self.model is not None or self.model_type == 'dummy'