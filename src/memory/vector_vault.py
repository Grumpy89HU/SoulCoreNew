"""
Vector-Vault: Qdrant alapú szemantikus memória.
Vektoros keresés a globális tudásbázisban.
"""

from qdrant_client import QdrantClient
from qdrant_client.http import models
from typing import List, Dict, Optional
import uuid
import numpy as np

class VectorVault:
    """
    Vektoros memória kezelése.
    
    - Szemantikus keresés
    - Globális tudás (AI Wikipédia)
    - Lokális emlékek vektoros formában
    """
    
    def __init__(self, host: str = "localhost", port: int = 6333,
                 vector_size: int = 1024):
        self.client = QdrantClient(host=host, port=port)
        self.vector_size = vector_size
        
        # Collection-ök inicializálása
        self._init_collections()
    
    def _init_collections(self):
        """Szükséges collection-ök létrehozása"""
        collections = ['global_knowledge', 'personal_memories']
        
        for name in collections:
            try:
                self.client.get_collection(name)
            except:
                self.client.create_collection(
                    collection_name=name,
                    vectors_config=models.VectorParams(
                        size=self.vector_size,
                        distance=models.Distance.COSINE
                    )
                )
    
    def add_knowledge(self, content: str, embedding: List[float],
                      metadata: Dict = None, collection: str = "global_knowledge"):
        """
        Tudás hozzáadása a vektoros tárba.
        
        Args:
            content: Szöveges tartalom
            embedding: 1024 dimenziós vektor
            metadata: JSON adatok (topic, source, importance)
            collection: global_knowledge vagy personal_memories
        """
        point_id = str(uuid.uuid4())
        
        self.client.upsert(
            collection_name=collection,
            points=[
                models.PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={
                        "content": content,
                        "metadata": metadata or {},
                        "created_at": "2026-03-23"
                    }
                )
            ]
        )
        
        return point_id
    
    def search(self, query_embedding: List[float], 
               collection: str = "global_knowledge",
               limit: int = 5,
               score_threshold: float = 0.7) -> List[Dict]:
        """
        Szemantikus keresés.
        
        Returns:
            [{"content": "...", "score": 0.95, "metadata": {...}}]
        """
        results = self.client.search(
            collection_name=collection,
            query_vector=query_embedding,
            limit=limit,
            score_threshold=score_threshold
        )
        
        return [
            {
                "content": r.payload.get("content", ""),
                "score": r.score,
                "metadata": r.payload.get("metadata", {})
            }
            for r in results
        ]
    
    def search_by_topic(self, topic: str, collection: str = "global_knowledge",
                        limit: int = 5) -> List[Dict]:
        """
        Filteres keresés topic alapján.
        """
        results = self.client.scroll(
            collection_name=collection,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="metadata.topic",
                        match=models.MatchValue(value=topic)
                    )
                ]
            ),
            limit=limit
        )
        
        return [
            {
                "content": r.payload.get("content", ""),
                "metadata": r.payload.get("metadata", {})
            }
            for r in results[0]
        ]