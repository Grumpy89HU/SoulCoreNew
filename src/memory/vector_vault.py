"""
Vector-Vault module for SoulCore - Qdrant based semantic memory and knowledge base.
"""

import os
import logging
import uuid
import random
import json
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timedelta

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models
    from qdrant_client.http.models import PointStruct, Distance, VectorParams, Filter, FieldCondition, MatchValue
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    logging.warning("Qdrant client not installed. Vector-Vault will be disabled.")

logger = logging.getLogger(__name__)


class VectorVault:
    """
    Vector database interface for semantic memory and knowledge retrieval.
    Uses Qdrant as backend for embedding-based search.
    """
    
    # Alapértelmezett collection-ök
    DEFAULT_COLLECTIONS = {
        'global_knowledge': 'General knowledge shared across all users',
        'personal_memories': 'User-specific memories and experiences',
        'conversations': 'Past conversations for context',
        'embeddings': 'General purpose embeddings'
    }
    
    def __init__(self, config: Dict[str, Any], embedding_function=None):
        """
        Initialize Vector-Vault.
        
        Args:
            config: Configuration dictionary
            embedding_function: Callable that takes text and returns embedding vector
        """
        self.config = config
        self.embedding_function = embedding_function
        self._client = None
        self._enabled = QDRANT_AVAILABLE
        
        if not self._enabled:
            logger.warning("Vector-Vault initialized in disabled mode (Qdrant client not installed)")
            return
        
        # Load Qdrant config
        vault_config = config.get('memory', {}).get('vault', {})
        qdrant_config = vault_config.get('qdrant', {})
        
        self.host = qdrant_config.get('host', 'localhost')
        self.port = qdrant_config.get('port', 6333)
        self.collection_name = qdrant_config.get('collection', 'soulcore_knowledge')
        self.vector_size = qdrant_config.get('vector_size', 1024)
        
        # Optional: gRPC port
        self.grpc_port = qdrant_config.get('grpc_port', 6334)
        self.prefer_grpc = qdrant_config.get('prefer_grpc', False)
        
        # API key if needed
        self.api_key = qdrant_config.get('api_key', None) or os.environ.get('QDRANT_API_KEY')
        
        # Timeout settings
        self.timeout = qdrant_config.get('timeout', 30)
        
        self._connect()
        self._ensure_collection()
    
    def _connect(self):
        """Establish connection to Qdrant"""
        if not self._enabled:
            return
        
        try:
            if self.prefer_grpc:
                self._client = QdrantClient(
                    host=self.host,
                    grpc_port=self.grpc_port,
                    prefer_grpc=True,
                    api_key=self.api_key,
                    timeout=self.timeout
                )
            else:
                self._client = QdrantClient(
                    host=self.host,
                    port=self.port,
                    api_key=self.api_key,
                    timeout=self.timeout
                )
            logger.info(f"Vector-Vault connected to {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to connect to Qdrant: {e}")
            self._enabled = False
            self._client = None
    
    def _ensure_collection(self, collection_name: str = None):
        """Create collection if it doesn't exist"""
        if not self._enabled or not self._client:
            return
        
        name = collection_name or self.collection_name
        
        try:
            collections = self._client.get_collections()
            existing_names = [c.name for c in collections.collections]
            
            if name not in existing_names:
                self._client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(
                        size=self.vector_size,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Created collection: {name}")
        except Exception as e:
            logger.error(f"Failed to ensure collection {name}: {e}")
    
    def _ensure_collections(self, collections: List[str]):
        """Ensure multiple collections exist"""
        for name in collections:
            self._ensure_collection(name)
    
    def close(self):
        """Close client connection"""
        if self._client:
            self._client.close()
    
    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """Get embedding vector for text using configured function"""
        if not self.embedding_function:
            logger.warning("No embedding function provided")
            return None
        
        try:
            embedding = self.embedding_function(text)
            if hasattr(embedding, 'tolist'):
                embedding = embedding.tolist()
            if isinstance(embedding, list) and len(embedding) != self.vector_size:
                logger.warning(f"Embedding size mismatch: expected {self.vector_size}, got {len(embedding)}")
                return None
            return embedding
        except Exception as e:
            logger.error(f"Failed to get embedding: {e}")
            return None
    
    def _get_embeddings_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """Get embeddings for multiple texts"""
        return [self._get_embedding(text) for text in texts]
    
    # ========== ALAP MŰVELETEK ==========
    
    def add_knowledge(self, text: str, metadata: Dict[str, Any], 
                      knowledge_id: Optional[str] = None,
                      collection_name: str = None) -> Optional[str]:
        """
        Add a knowledge entry to the vector vault.
        
        Args:
            text: The text content to store
            metadata: Additional metadata (source, timestamp, importance, etc.)
            knowledge_id: Optional ID, generated if not provided
            collection_name: Optional collection name (default: self.collection_name)
            
        Returns:
            str: ID of the stored point, or None if failed
        """
        if not self._enabled or not self._client:
            logger.warning("Vector-Vault not available, skipping knowledge addition")
            return None
        
        embedding = self._get_embedding(text)
        if not embedding:
            return None
        
        point_id = knowledge_id or str(uuid.uuid4())
        collection = collection_name or self.collection_name
        
        # Ensure collection exists
        self._ensure_collection(collection)
        
        # Add timestamp if not present
        if 'timestamp' not in metadata:
            metadata['timestamp'] = datetime.now().isoformat()
        
        try:
            self._client.upsert(
                collection_name=collection,
                points=[
                    PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload={
                            'text': text,
                            **metadata
                        }
                    )
                ]
            )
            logger.debug(f"Added knowledge: {point_id} to {collection}")
            return point_id
        except Exception as e:
            logger.error(f"Failed to add knowledge: {e}")
            return None
    
    def batch_add_knowledge(self, items: List[Tuple[str, Dict[str, Any]]],
                            collection_name: str = None) -> List[Optional[str]]:
        """
        Add multiple knowledge entries in batch.
        
        Args:
            items: List of (text, metadata) tuples
            collection_name: Optional collection name
            
        Returns:
            List of IDs (None for failed items)
        """
        if not self._enabled or not self._client:
            return [None] * len(items)
        
        collection = collection_name or self.collection_name
        self._ensure_collection(collection)
        
        points = []
        results = []
        
        for text, metadata in items:
            embedding = self._get_embedding(text)
            if not embedding:
                results.append(None)
                continue
            
            point_id = str(uuid.uuid4())
            if 'timestamp' not in metadata:
                metadata['timestamp'] = datetime.now().isoformat()
            
            points.append(PointStruct(
                id=point_id,
                vector=embedding,
                payload={'text': text, **metadata}
            ))
            results.append(point_id)
        
        if points:
            try:
                self._client.upsert(
                    collection_name=collection,
                    points=points
                )
                logger.info(f"Batch added {len(points)} knowledge entries")
            except Exception as e:
                logger.error(f"Failed to batch add knowledge: {e}")
                return [None] * len(items)
        
        return results
    
    def search(self, query: str, limit: int = 5, 
               score_threshold: Optional[float] = None,
               filter_conditions: Optional[Dict[str, Any]] = None,
               collection_name: str = None) -> List[Dict[str, Any]]:
        """
        Search for similar knowledge entries.
        
        Args:
            query: Search query text
            limit: Maximum number of results
            score_threshold: Minimum similarity score (0-1)
            filter_conditions: Optional metadata filters
            collection_name: Optional collection name
            
        Returns:
            List of search results with text and metadata
        """
        if not self._enabled or not self._client:
            logger.warning("Vector-Vault not available, returning empty results")
            return []
        
        query_embedding = self._get_embedding(query)
        if not query_embedding:
            return []
        
        collection = collection_name or self.collection_name
        
        try:
            search_filter = None
            if filter_conditions:
                conditions = []
                for key, value in filter_conditions.items():
                    conditions.append(
                        FieldCondition(
                            key=key,
                            match=MatchValue(value=value)
                        )
                    )
                if conditions:
                    search_filter = Filter(must=conditions)
            
            results = self._client.search(
                collection_name=collection,
                query_vector=query_embedding,
                limit=limit,
                score_threshold=score_threshold,
                query_filter=search_filter
            )
            
            return [
                {
                    'id': hit.id,
                    'text': hit.payload.get('text', ''),
                    'score': hit.score,
                    'metadata': {k: v for k, v in hit.payload.items() if k != 'text'}
                }
                for hit in results
            ]
        except Exception as e:
            logger.error(f"Failed to search: {e}")
            return []
    
    def search_by_vector(self, vector: List[float], limit: int = 5,
                         score_threshold: Optional[float] = None,
                         filter_conditions: Optional[Dict[str, Any]] = None,
                         collection_name: str = None) -> List[Dict[str, Any]]:
        """
        Search by vector directly.
        
        Args:
            vector: Query vector
            limit: Maximum number of results
            score_threshold: Minimum similarity score
            filter_conditions: Optional metadata filters
            collection_name: Optional collection name
            
        Returns:
            List of search results
        """
        if not self._enabled or not self._client:
            return []
        
        collection = collection_name or self.collection_name
        
        try:
            search_filter = None
            if filter_conditions:
                conditions = []
                for key, value in filter_conditions.items():
                    conditions.append(
                        FieldCondition(
                            key=key,
                            match=MatchValue(value=value)
                        )
                    )
                if conditions:
                    search_filter = Filter(must=conditions)
            
            results = self._client.search(
                collection_name=collection,
                query_vector=vector,
                limit=limit,
                score_threshold=score_threshold,
                query_filter=search_filter
            )
            
            return [
                {
                    'id': hit.id,
                    'text': hit.payload.get('text', ''),
                    'score': hit.score,
                    'metadata': {k: v for k, v in hit.payload.items() if k != 'text'}
                }
                for hit in results
            ]
        except Exception as e:
            logger.error(f"Failed to search by vector: {e}")
            return []
    
    def get_by_id(self, knowledge_id: str, collection_name: str = None) -> Optional[Dict[str, Any]]:
        """Retrieve a knowledge entry by ID"""
        if not self._enabled or not self._client:
            return None
        
        collection = collection_name or self.collection_name
        
        try:
            result = self._client.retrieve(
                collection_name=collection,
                ids=[knowledge_id],
                with_payload=True
            )
            if result:
                point = result[0]
                return {
                    'id': point.id,
                    'text': point.payload.get('text', ''),
                    'metadata': {k: v for k, v in point.payload.items() if k != 'text'}
                }
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve by ID: {e}")
            return None
    
    def delete_knowledge(self, knowledge_id: str, collection_name: str = None) -> bool:
        """Delete a knowledge entry"""
        if not self._enabled or not self._client:
            return False
        
        collection = collection_name or self.collection_name
        
        try:
            self._client.delete(
                collection_name=collection,
                points_selector=models.PointIdsList(points=[knowledge_id])
            )
            logger.debug(f"Deleted knowledge: {knowledge_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete knowledge: {e}")
            return False
    
    def delete_by_filter(self, filter_conditions: Dict[str, Any], 
                         collection_name: str = None) -> int:
        """Delete knowledge entries matching filter conditions"""
        if not self._enabled or not self._client:
            return 0
        
        collection = collection_name or self.collection_name
        
        try:
            conditions = []
            for key, value in filter_conditions.items():
                conditions.append(
                    FieldCondition(
                        key=key,
                        match=MatchValue(value=value)
                    )
                )
            
            if conditions:
                search_filter = Filter(must=conditions)
                
                result = self._client.delete(
                    collection_name=collection,
                    points_selector=models.FilterSelector(filter=search_filter)
                )
                return result.deleted_points_count if result else 0
            return 0
        except Exception as e:
            logger.error(f"Failed to delete by filter: {e}")
            return 0
    
    def update_metadata(self, knowledge_id: str, metadata: Dict[str, Any],
                        collection_name: str = None) -> bool:
        """Update metadata of a knowledge entry"""
        if not self._enabled or not self._client:
            return False
        
        collection = collection_name or self.collection_name
        
        try:
            # Add last_accessed timestamp
            metadata['last_accessed'] = datetime.now().isoformat()
            
            self._client.set_payload(
                collection_name=collection,
                payload=metadata,
                points=[knowledge_id]
            )
            return True
        except Exception as e:
            logger.error(f"Failed to update metadata: {e}")
            return False
    
    def update_importance(self, knowledge_id: str, importance_delta: float,
                          collection_name: str = None) -> bool:
        """Update importance score of a knowledge entry"""
        if not self._enabled or not self._client:
            return False
        
        collection = collection_name or self.collection_name
        
        try:
            result = self._client.retrieve(
                collection_name=collection,
                ids=[knowledge_id],
                with_payload=True
            )
            
            if not result:
                return False
            
            point = result[0]
            current_importance = point.payload.get('importance', 0.5)
            new_importance = max(0.0, min(1.0, current_importance + importance_delta))
            
            self._client.set_payload(
                collection_name=collection,
                payload={'importance': new_importance, 'last_accessed': datetime.now().isoformat()},
                points=[knowledge_id]
            )
            
            return True
        except Exception as e:
            logger.error(f"Failed to update importance: {e}")
            return False
    
    # ========== KOLLEKCIÓ MŰVELETEK ==========
    
    def create_collection(self, name: str, vector_size: int = None) -> bool:
        """Create a new collection"""
        if not self._enabled or not self._client:
            return False
        
        size = vector_size or self.vector_size
        
        try:
            self._client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(
                    size=size,
                    distance=Distance.COSINE
                )
            )
            logger.info(f"Created collection: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create collection {name}: {e}")
            return False
    
    def delete_collection(self, name: str) -> bool:
        """Delete a collection"""
        if not self._enabled or not self._client:
            return False
        
        try:
            self._client.delete_collection(collection_name=name)
            logger.info(f"Deleted collection: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection {name}: {e}")
            return False
    
    def list_collections(self) -> List[str]:
        """List all collections"""
        if not self._enabled or not self._client:
            return []
        
        try:
            collections = self._client.get_collections()
            return [c.name for c in collections.collections]
        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            return []
    
    def get_collection_info(self, collection_name: str = None) -> Dict[str, Any]:
        """Get collection information"""
        if not self._enabled or not self._client:
            return {'error': 'Vector-Vault not available'}
        
        collection = collection_name or self.collection_name
        
        try:
            info = self._client.get_collection(collection_name=collection)
            return {
                'name': collection,
                'points_count': info.points_count,
                'segments_count': info.segments_count,
                'vectors_count': info.vectors_count if hasattr(info, 'vectors_count') else 0,
                'status': info.status if hasattr(info, 'status') else 'unknown'
            }
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            return {'error': str(e)}
    
    def clear_collection(self, collection_name: str = None) -> bool:
        """Clear all points from a collection"""
        if not self._enabled or not self._client:
            return False
        
        collection = collection_name or self.collection_name
        
        try:
            # Get all points and delete
            scroll_result = self._client.scroll(
                collection_name=collection,
                limit=1000,
                with_payload=False
            )
            
            while scroll_result[0]:
                point_ids = [point.id for point in scroll_result[0]]
                self._client.delete(
                    collection_name=collection,
                    points_selector=models.PointIdsList(points=point_ids)
                )
                scroll_result = self._client.scroll(
                    collection_name=collection,
                    limit=1000,
                    offset=scroll_result[1],
                    with_payload=False
                )
            
            logger.info(f"Cleared collection: {collection}")
            return True
        except Exception as e:
            logger.error(f"Failed to clear collection: {e}")
            return False
    
    # ========== KERESÉSEK ==========
    
    def get_related_by_context(self, text: str, context_metadata: Dict[str, Any],
                                limit: int = 5, collection_name: str = None) -> List[Dict[str, Any]]:
        """Search for knowledge related to text with context-based filtering"""
        filter_conditions = {}
        for key in ['source', 'topic', 'importance']:
            if key in context_metadata:
                filter_conditions[key] = context_metadata[key]
        
        return self.search(
            query=text,
            limit=limit,
            filter_conditions=filter_conditions if filter_conditions else None,
            collection_name=collection_name
        )
    
    def get_random_knowledge(self, limit: int = 5, collection_name: str = None) -> List[Dict[str, Any]]:
        """Get random knowledge entries"""
        if not self._enabled or not self._client:
            return []
        
        collection = collection_name or self.collection_name
        
        try:
            info = self._client.get_collection(collection_name=collection)
            total_points = info.points_count if info.points_count else 0
            
            if total_points == 0:
                return []
            
            # Generate random offset
            offset = random.randint(0, max(0, total_points - limit))
            
            results = self._client.scroll(
                collection_name=collection,
                limit=limit,
                offset=offset,
                with_payload=True
            )
            
            return [
                {
                    'id': point.id,
                    'text': point.payload.get('text', ''),
                    'metadata': {k: v for k, v in point.payload.items() if k != 'text'}
                }
                for point in results[0]
            ]
        except Exception as e:
            logger.error(f"Failed to get random knowledge: {e}")
            return []
    
    def get_recent_knowledge(self, limit: int = 10, collection_name: str = None) -> List[Dict[str, Any]]:
        """Get most recent knowledge entries"""
        if not self._enabled or not self._client:
            return []
        
        collection = collection_name or self.collection_name
        
        try:
            # Scroll with order by timestamp
            results = self._client.scroll(
                collection_name=collection,
                limit=limit,
                with_payload=True
            )
            
            # Sort by timestamp descending
            entries = []
            for point in results[0]:
                timestamp = point.payload.get('timestamp', '')
                entries.append({
                    'id': point.id,
                    'text': point.payload.get('text', ''),
                    'timestamp': timestamp,
                    'metadata': {k: v for k, v in point.payload.items() if k != 'text'}
                })
            
            entries.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return entries[:limit]
        except Exception as e:
            logger.error(f"Failed to get recent knowledge: {e}")
            return []
    
    # ========== KARBANTARTÁS ==========
    
    def prune_old_knowledge(self, days_old: int = 90, collection_name: str = None) -> int:
        """Remove knowledge entries older than specified days"""
        if not self._enabled or not self._client:
            return 0
        
        collection = collection_name or self.collection_name
        cutoff = datetime.now() - timedelta(days=days_old)
        cutoff_timestamp = cutoff.timestamp()
        
        try:
            # Find points older than cutoff
            scroll_result = self._client.scroll(
                collection_name=collection,
                limit=1000,
                with_payload=True
            )
            
            to_delete = []
            while scroll_result[0]:
                for point in scroll_result[0]:
                    timestamp = point.payload.get('timestamp')
                    if timestamp:
                        try:
                            # Try ISO format
                            ts = datetime.fromisoformat(timestamp).timestamp()
                        except (ValueError, TypeError):
                            try:
                                # Try numeric timestamp
                                ts = float(timestamp)
                            except (ValueError, TypeError):
                                continue
                        
                        if ts < cutoff_timestamp:
                            to_delete.append(point.id)
                
                if to_delete:
                    self._client.delete(
                        collection_name=collection,
                        points_selector=models.PointIdsList(points=to_delete)
                    )
                    logger.info(f"Pruned {len(to_delete)} old knowledge entries")
                    to_delete = []
                
                scroll_result = self._client.scroll(
                    collection_name=collection,
                    limit=1000,
                    offset=scroll_result[1],
                    with_payload=True
                )
            
            return len(to_delete)
        except Exception as e:
            logger.error(f"Failed to prune old knowledge: {e}")
            return 0
    
    def prune_by_importance(self, threshold: float = 0.1, collection_name: str = None) -> int:
        """Remove knowledge entries with importance below threshold"""
        if not self._enabled or not self._client:
            return 0
        
        collection = collection_name or self.collection_name
        
        try:
            # Find points with low importance
            filter_conditions = Filter(
                must=[
                    FieldCondition(
                        key='importance',
                        range=models.Range(
                            lt=threshold
                        )
                    )
                ]
            )
            
            scroll_result = self._client.scroll(
                collection_name=collection,
                limit=1000,
                with_payload=False,
                scroll_filter=filter_conditions
            )
            
            to_delete = [point.id for point in scroll_result[0]]
            
            if to_delete:
                self._client.delete(
                    collection_name=collection,
                    points_selector=models.PointIdsList(points=to_delete)
                )
                logger.info(f"Pruned {len(to_delete)} low-importance knowledge entries")
            
            return len(to_delete)
        except Exception as e:
            logger.error(f"Failed to prune by importance: {e}")
            return 0
    
    # ========== STATISZTIKÁK ==========
    
    def get_stats(self) -> Dict[str, Any]:
        """Get vector vault statistics"""
        stats = {
            'enabled': self._enabled,
            'connected': self._client is not None,
            'collections': self.list_collections(),
            'collections_info': {}
        }
        
        for name in stats['collections']:
            stats['collections_info'][name] = self.get_collection_info(name)
        
        return stats
    
    def get_embedding_stats(self) -> Dict[str, Any]:
        """Get embedding function statistics"""
        return {
            'embedding_function_available': self.embedding_function is not None,
            'vector_size': self.vector_size,
            'model': getattr(self.embedding_function, '__name__', 'unknown')
        }


# Teszt
if __name__ == "__main__":
    # Mock embedding function
    def mock_embed(text):
        import hashlib
        import struct
        # Generate a deterministic 1024-dim vector
        hash_bytes = hashlib.sha256(text.encode()).digest()
        vector = []
        for i in range(0, len(hash_bytes), 4):
            val = struct.unpack('>I', hash_bytes[i:i+4])[0]
            vector.append(val / 4294967295.0)
        # Pad to 1024 dimensions
        while len(vector) < 1024:
            vector.append(0.0)
        return vector
    
    config = {
        'memory': {
            'vault': {
                'qdrant': {
                    'host': 'localhost',
                    'port': 6333
                }
            }
        }
    }
    
    vault = VectorVault(config, embedding_function=mock_embed)
    
    if vault._enabled:
        print("Vector-Vault connected")
        
        # Test add
        vault.add_knowledge(
            "This is a test knowledge entry",
            {'source': 'test', 'topic': 'testing', 'importance': 0.8}
        )
        
        # Test search
        results = vault.search("test")
        print(f"Search results: {results}")
        
        print(f"Stats: {vault.get_stats()}")
    else:
        print("Vector-Vault disabled (Qdrant not available)")
    
    vault.close()