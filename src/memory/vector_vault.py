"""
Vector-Vault module for SoulCore - Qdrant based semantic memory and knowledge base.
"""
import os
import logging
import uuid
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models
    from qdrant_client.http.models import PointStruct, Distance, VectorParams
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
                    api_key=self.api_key
                )
            else:
                self._client = QdrantClient(
                    host=self.host,
                    port=self.port,
                    api_key=self.api_key
                )
            logger.info(f"Vector-Vault connected to {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to connect to Qdrant: {e}")
            self._enabled = False
            self._client = None
    
    def _ensure_collection(self):
        """Create collection if it doesn't exist"""
        if not self._enabled or not self._client:
            return
        
        try:
            collections = self._client.get_collections()
            existing_names = [c.name for c in collections.collections]
            
            if self.collection_name not in existing_names:
                self._client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Created collection: {self.collection_name}")
        except Exception as e:
            logger.error(f"Failed to ensure collection: {e}")
    
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
            # Ensure list of floats
            if hasattr(embedding, 'tolist'):
                embedding = embedding.tolist()
            return embedding
        except Exception as e:
            logger.error(f"Failed to get embedding: {e}")
            return None
    
    def add_knowledge(self, text: str, metadata: Dict[str, Any], 
                      knowledge_id: Optional[str] = None) -> Optional[str]:
        """
        Add a knowledge entry to the vector vault.
        
        Args:
            text: The text content to store
            metadata: Additional metadata (source, timestamp, importance, etc.)
            knowledge_id: Optional ID, generated if not provided
            
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
        
        # Add timestamp if not present
        if 'timestamp' not in metadata:
            metadata['timestamp'] = datetime.now().isoformat()
        
        try:
            self._client.upsert(
                collection_name=self.collection_name,
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
            return point_id
        except Exception as e:
            logger.error(f"Failed to add knowledge: {e}")
            return None
    
    def search(self, query: str, limit: int = 5, 
               score_threshold: Optional[float] = None,
               filter_conditions: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Search for similar knowledge entries.
        
        Args:
            query: Search query text
            limit: Maximum number of results
            score_threshold: Minimum similarity score (0-1)
            filter_conditions: Optional metadata filters
            
        Returns:
            List of search results with text and metadata
        """
        if not self._enabled or not self._client:
            logger.warning("Vector-Vault not available, returning empty results")
            return []
        
        query_embedding = self._get_embedding(query)
        if not query_embedding:
            return []
        
        try:
            # Build filter if provided
            search_filter = None
            if filter_conditions:
                conditions = []
                for key, value in filter_conditions.items():
                    conditions.append(
                        models.FieldCondition(
                            key=key,
                            match=models.MatchValue(value=value)
                        )
                    )
                if conditions:
                    search_filter = models.Filter(
                        must=conditions
                    )
            
            results = self._client.search(
                collection_name=self.collection_name,
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
    
    def get_by_id(self, knowledge_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a knowledge entry by ID"""
        if not self._enabled or not self._client:
            return None
        
        try:
            result = self._client.retrieve(
                collection_name=self.collection_name,
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
    
    def delete_knowledge(self, knowledge_id: str) -> bool:
        """Delete a knowledge entry"""
        if not self._enabled or not self._client:
            return False
        
        try:
            self._client.delete(
                collection_name=self.collection_name,
                points_selector=models.PointIdsList(points=[knowledge_id])
            )
            return True
        except Exception as e:
            logger.error(f"Failed to delete knowledge: {e}")
            return False
    
    def get_related_by_context(self, text: str, context_metadata: Dict[str, Any],
                                limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search for knowledge related to text with context-based filtering.
        
        Args:
            text: The text to find related knowledge for
            context_metadata: Metadata to filter by (e.g., source, topic)
            limit: Maximum number of results
            
        Returns:
            List of related knowledge entries
        """
        # Extract text from context if needed
        query_text = text
        
        # Build filter from context metadata
        filter_conditions = {}
        for key in ['source', 'topic', 'importance']:
            if key in context_metadata:
                filter_conditions[key] = context_metadata[key]
        
        return self.search(
            query=query_text,
            limit=limit,
            filter_conditions=filter_conditions if filter_conditions else None
        )
    
    def get_random_knowledge(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get random knowledge entries (for proactive responses)"""
        if not self._enabled or not self._client:
            return []
        
        try:
            # Get total count
            collection_info = self._client.get_collection(self.collection_name)
            total_points = collection_info.points_count if collection_info.points_count else 0
            
            if total_points == 0:
                return []
            
            # Scroll with random offset (simplified)
            offset = int(total_points * 0.7) if total_points > limit else 0
            
            results = self._client.scroll(
                collection_name=self.collection_name,
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
    
    def prune_old_knowledge(self, days_old: int = 90) -> int:
        """
        Remove knowledge entries older than specified days.
        
        Args:
            days_old: Age threshold in days
            
        Returns:
            int: Number of entries removed
        """
        if not self._enabled or not self._client:
            return 0
        
        try:
            cutoff = datetime.now().timestamp() - (days_old * 24 * 60 * 60)
            
            # Find points older than cutoff
            results = self._client.scroll(
                collection_name=self.collection_name,
                limit=1000,
                with_payload=True
            )
            
            to_delete = []
            for point in results[0]:
                timestamp = point.payload.get('timestamp')
                if timestamp:
                    try:
                        ts = datetime.fromisoformat(timestamp).timestamp()
                        if ts < cutoff:
                            to_delete.append(point.id)
                    except (ValueError, TypeError):
                        pass
            
            if to_delete:
                self._client.delete(
                    collection_name=self.collection_name,
                    points_selector=models.PointIdsList(points=to_delete)
                )
            
            return len(to_delete)
        except Exception as e:
            logger.error(f"Failed to prune old knowledge: {e}")
            return 0
    
    def update_importance(self, knowledge_id: str, importance_delta: float) -> bool:
        """
        Update importance score of a knowledge entry.
        
        Args:
            knowledge_id: ID of the knowledge entry
            importance_delta: Amount to add to importance
            
        Returns:
            bool: Success status
        """
        if not self._enabled or not self._client:
            return False
        
        try:
            # Get current point
            result = self._client.retrieve(
                collection_name=self.collection_name,
                ids=[knowledge_id],
                with_payload=True
            )
            
            if not result:
                return False
            
            point = result[0]
            current_importance = point.payload.get('importance', 0.5)
            new_importance = max(0.0, min(1.0, current_importance + importance_delta))
            
            # Update payload
            payload = dict(point.payload)
            payload['importance'] = new_importance
            payload['last_accessed'] = datetime.now().isoformat()
            
            self._client.set_payload(
                collection_name=self.collection_name,
                payload={'importance': new_importance, 'last_accessed': payload['last_accessed']},
                points=[knowledge_id]
            )
            
            return True
        except Exception as e:
            logger.error(f"Failed to update importance: {e}")
            return False