"""
Graph-Vault module for SoulCore - Neo4j based relationship and emotional memory.
"""
import os
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

try:
    from neo4j import GraphDatabase, AsyncGraphDatabase
    from neo4j.exceptions import ServiceUnavailable, AuthError
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    logging.warning("Neo4j not installed. Graph-Vault will be disabled.")

logger = logging.getLogger(__name__)


@dataclass
class RelationshipNode:
    """Represents a node in the graph (entity, concept, memory)"""
    uuid: str
    name: str
    node_type: str  # 'person', 'concept', 'memory', 'project', 'emotion'
    properties: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


@dataclass
class RelationshipEdge:
    """Represents an edge/relationship between nodes"""
    source_uuid: str
    target_uuid: str
    relationship_type: str  # 'knows', 'mentions', 'feels_about', 'developed'
    emotional_charge: float  # -1.0 to +1.0
    weight: float  # 0.0 to 1.0, interaction frequency/importance
    properties: Dict[str, Any]
    created_at: datetime
    last_accessed: datetime


class GraphVault:
    """
    Graph database interface for storing and querying relationship-based memory.
    Uses Neo4j as backend with emotional charge tracking.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._driver = None
        self._async_driver = None
        self._enabled = NEO4J_AVAILABLE
        
        if not self._enabled:
            logger.warning("Graph-Vault initialized in disabled mode (Neo4j not installed)")
            return
        
        # Load Neo4j config
        vault_config = config.get('memory', {}).get('vault', {})
        neo4j_config = vault_config.get('neo4j', {})
        
        self.uri = neo4j_config.get('uri', 'bolt://localhost:7687')
        self.user = neo4j_config.get('user', 'neo4j')
        self.password = neo4j_config.get('password', '')
        
        # Fallback to environment variable if not in config
        if not self.password:
            self.password = os.environ.get('NEO4J_PASSWORD', 'neo4j')
        
        self.max_connection_pool_size = neo4j_config.get('max_connection_pool_size', 50)
        self.connection_timeout = neo4j_config.get('connection_timeout', 30)
        
        self._connect()
    
    def _connect(self):
        """Establish connection to Neo4j database"""
        if not self._enabled:
            return
        
        try:
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
                max_connection_pool_size=self.max_connection_pool_size,
                connection_timeout=self.connection_timeout
            )
            self._async_driver = AsyncGraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
                max_connection_pool_size=self.max_connection_pool_size,
                connection_timeout=self.connection_timeout
            )
            # Verify connection
            self._driver.verify_connectivity()
            logger.info(f"Graph-Vault connected to {self.uri}")
            self._ensure_constraints_and_indexes()
        except (ServiceUnavailable, AuthError, Exception) as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            self._enabled = False
            self._driver = None
    
    def _ensure_constraints_and_indexes(self):
        """Create necessary constraints and indexes if they don't exist"""
        if not self._enabled or not self._driver:
            return
        
        with self._driver.session() as session:
            # Constraints
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:Memory) REQUIRE n.uuid IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:Person) REQUIRE n.uuid IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:Concept) REQUIRE n.uuid IS UNIQUE")
            
            # Indexes
            session.run("CREATE INDEX IF NOT EXISTS FOR (n:Person) ON (n.name)")
            session.run("CREATE INDEX IF NOT EXISTS FOR (n:Concept) ON (n.name)")
            session.run("CREATE INDEX IF NOT EXISTS FOR (n:Memory) ON (n.created_at)")
    
    def close(self):
        """Close database connections"""
        if self._driver:
            self._driver.close()
        if self._async_driver:
            self._async_driver.close()
    
    def create_node(self, node: RelationshipNode) -> bool:
        """
        Create a new node in the graph.
        
        Args:
            node: RelationshipNode instance
            
        Returns:
            bool: Success status
        """
        if not self._enabled or not self._driver:
            logger.warning("Graph-Vault not available, skipping node creation")
            return False
        
        try:
            with self._driver.session() as session:
                result = session.run(
                    """
                    MERGE (n:{node_type} {{uuid: $uuid}})
                    SET n.name = $name,
                        n.properties = $properties,
                        n.created_at = $created_at,
                        n.updated_at = $updated_at
                    RETURN n
                    """.format(node_type=node.node_type.capitalize()),
                    uuid=node.uuid,
                    name=node.name,
                    properties=node.properties,
                    created_at=node.created_at.isoformat(),
                    updated_at=node.updated_at.isoformat()
                )
                return result.single() is not None
        except Exception as e:
            logger.error(f"Failed to create node: {e}")
            return False
    
    def create_edge(self, edge: RelationshipEdge) -> bool:
        """
        Create a relationship between two nodes.
        
        Args:
            edge: RelationshipEdge instance
            
        Returns:
            bool: Success status
        """
        if not self._enabled or not self._driver:
            logger.warning("Graph-Vault not available, skipping edge creation")
            return False
        
        try:
            with self._driver.session() as session:
                result = session.run(
                    """
                    MATCH (source {{uuid: $source_uuid}})
                    MATCH (target {{uuid: $target_uuid}})
                    MERGE (source)-[r:{rel_type}]->(target)
                    SET r.emotional_charge = $emotional_charge,
                        r.weight = $weight,
                        r.properties = $properties,
                        r.created_at = $created_at,
                        r.last_accessed = $last_accessed
                    RETURN r
                    """.format(rel_type=edge.relationship_type.upper()),
                    source_uuid=edge.source_uuid,
                    target_uuid=edge.target_uuid,
                    emotional_charge=edge.emotional_charge,
                    weight=edge.weight,
                    properties=edge.properties,
                    created_at=edge.created_at.isoformat(),
                    last_accessed=edge.last_accessed.isoformat()
                )
                return result.single() is not None
        except Exception as e:
            logger.error(f"Failed to create edge: {e}")
            return False
    
    def get_node(self, uuid: str) -> Optional[RelationshipNode]:
        """Retrieve a node by UUID"""
        if not self._enabled or not self._driver:
            return None
        
        try:
            with self._driver.session() as session:
                result = session.run(
                    """
                    MATCH (n)
                    WHERE n.uuid = $uuid
                    RETURN n, labels(n)[0] as node_type
                    """,
                    uuid=uuid
                )
                record = result.single()
                if record:
                    node_data = record['n']
                    node_type = record['node_type'].lower()
                    return RelationshipNode(
                        uuid=node_data['uuid'],
                        name=node_data.get('name', ''),
                        node_type=node_type,
                        properties=node_data.get('properties', {}),
                        created_at=datetime.fromisoformat(node_data.get('created_at', datetime.now().isoformat())),
                        updated_at=datetime.fromisoformat(node_data.get('updated_at', datetime.now().isoformat()))
                    )
                return None
        except Exception as e:
            logger.error(f"Failed to get node: {e}")
            return None
    
    def get_node_by_name(self, name: str, node_type: Optional[str] = None) -> Optional[RelationshipNode]:
        """Find a node by name, optionally filtered by type"""
        if not self._enabled or not self._driver:
            return None
        
        try:
            with self._driver.session() as session:
                if node_type:
                    query = """
                    MATCH (n:{node_type})
                    WHERE n.name = $name
                    RETURN n, labels(n)[0] as node_type
                    """.format(node_type=node_type.capitalize())
                else:
                    query = """
                    MATCH (n)
                    WHERE n.name = $name
                    RETURN n, labels(n)[0] as node_type
                    """
                
                result = session.run(query, name=name)
                record = result.single()
                if record:
                    node_data = record['n']
                    node_type_val = record['node_type'].lower()
                    return RelationshipNode(
                        uuid=node_data['uuid'],
                        name=node_data.get('name', ''),
                        node_type=node_type_val,
                        properties=node_data.get('properties', {}),
                        created_at=datetime.fromisoformat(node_data.get('created_at', datetime.now().isoformat())),
                        updated_at=datetime.fromisoformat(node_data.get('updated_at', datetime.now().isoformat()))
                    )
                return None
        except Exception as e:
            logger.error(f"Failed to get node by name: {e}")
            return None
    
    def query_relationships(self, node_uuid: str, relationship_type: Optional[str] = None, 
                            direction: str = 'both') -> List[Dict[str, Any]]:
        """
        Query all relationships connected to a node.
        
        Args:
            node_uuid: UUID of the central node
            relationship_type: Filter by relationship type (optional)
            direction: 'incoming', 'outgoing', or 'both'
            
        Returns:
            List of relationship dictionaries with source, target, and properties
        """
        if not self._enabled or not self._driver:
            return []
        
        try:
            with self._driver.session() as session:
                if direction == 'outgoing':
                    dir_pattern = '-[r]->'
                elif direction == 'incoming':
                    dir_pattern = '<-[r]-'
                else:
                    dir_pattern = '-[r]-'
                
                if relationship_type:
                    query = f"""
                    MATCH (n {{uuid: $uuid}}){dir_pattern}(connected)
                    WHERE type(r) = $rel_type
                    RETURN connected, r, type(r) as rel_type, startnode(r).uuid as source_uuid, endnode(r).uuid as target_uuid
                    """
                    params = {'uuid': node_uuid, 'rel_type': relationship_type.upper()}
                else:
                    query = f"""
                    MATCH (n {{uuid: $uuid}}){dir_pattern}(connected)
                    RETURN connected, r, type(r) as rel_type, startnode(r).uuid as source_uuid, endnode(r).uuid as target_uuid
                    """
                    params = {'uuid': node_uuid}
                
                result = session.run(query, **params)
                relationships = []
                for record in result:
                    rel_data = record['r']
                    relationships.append({
                        'connected_node': dict(record['connected']),
                        'relationship_type': record['rel_type'],
                        'source_uuid': record['source_uuid'],
                        'target_uuid': record['target_uuid'],
                        'emotional_charge': rel_data.get('emotional_charge', 0.0),
                        'weight': rel_data.get('weight', 0.5),
                        'properties': rel_data.get('properties', {}),
                        'created_at': rel_data.get('created_at'),
                        'last_accessed': rel_data.get('last_accessed')
                    })
                return relationships
        except Exception as e:
            logger.error(f"Failed to query relationships: {e}")
            return []
    
    def get_emotional_context(self, concept_name: str, max_depth: int = 2) -> Dict[str, Any]:
        """
        Retrieve emotional context around a concept for sentiment-aware responses.
        
        Args:
            concept_name: The concept to analyze
            max_depth: How many relationship hops to traverse
            
        Returns:
            Dictionary with aggregated emotional data
        """
        if not self._enabled or not self._driver:
            return {'emotional_charge': 0.0, 'related_concepts': [], 'confidence': 0.0}
        
        try:
            with self._driver.session() as session:
                # Find the concept node
                concept = self.get_node_by_name(concept_name, 'concept')
                if not concept:
                    return {'emotional_charge': 0.0, 'related_concepts': [], 'confidence': 0.0}
                
                # Get all relationships up to max_depth
                query = f"""
                MATCH (c {{uuid: $uuid}})-[r*1..{max_depth}]-(connected)
                RETURN connected, r, 
                       avg([rel in r | rel.emotional_charge]) as avg_charge,
                       sum([rel in r | rel.weight]) as total_weight
                """
                result = session.run(query, uuid=concept.uuid)
                
                charges = []
                related = []
                
                for record in result:
                    if record['avg_charge'] is not None:
                        charges.append(record['avg_charge'])
                    if record['connected']:
                        related.append({
                            'name': record['connected'].get('name', ''),
                            'type': list(record['connected'].labels)[0] if record['connected'].labels else 'unknown'
                        })
                
                avg_charge = sum(charges) / len(charges) if charges else 0.0
                
                return {
                    'emotional_charge': avg_charge,
                    'related_concepts': related[:10],  # Limit to 10
                    'confidence': min(1.0, len(charges) / 10) if charges else 0.0
                }
        except Exception as e:
            logger.error(f"Failed to get emotional context: {e}")
            return {'emotional_charge': 0.0, 'related_concepts': [], 'confidence': 0.0}
    
    def update_edge_weight(self, source_uuid: str, target_uuid: str, 
                           relationship_type: str, delta_weight: float) -> bool:
        """
        Update the weight of an existing relationship (e.g., interaction frequency).
        
        Args:
            source_uuid: Source node UUID
            target_uuid: Target node UUID
            relationship_type: Type of relationship
            delta_weight: Amount to add to weight (clamped 0-1)
            
        Returns:
            bool: Success status
        """
        if not self._enabled or not self._driver:
            return False
        
        try:
            with self._driver.session() as session:
                result = session.run(
                    """
                    MATCH (source {uuid: $source_uuid})-[r:{rel_type}]->(target {uuid: $target_uuid})
                    SET r.weight = CASE 
                                    WHEN r.weight + $delta > 1 THEN 1
                                    WHEN r.weight + $delta < 0 THEN 0
                                    ELSE r.weight + $delta
                                  END,
                        r.last_accessed = $now
                    RETURN r.weight as new_weight
                    """.format(rel_type=relationship_type.upper()),
                    source_uuid=source_uuid,
                    target_uuid=target_uuid,
                    delta=delta_weight,
                    now=datetime.now().isoformat()
                )
                return result.single() is not None
        except Exception as e:
            logger.error(f"Failed to update edge weight: {e}")
            return False
    
    def update_emotional_charge(self, source_uuid: str, target_uuid: str,
                                 relationship_type: str, new_charge: float) -> bool:
        """
        Update the emotional charge of a relationship.
        
        Args:
            source_uuid: Source node UUID
            target_uuid: Target node UUID
            relationship_type: Type of relationship
            new_charge: New emotional charge (-1.0 to +1.0)
            
        Returns:
            bool: Success status
        """
        if not self._enabled or not self._driver:
            return False
        
        try:
            with self._driver.session() as session:
                result = session.run(
                    """
                    MATCH (source {uuid: $source_uuid})-[r:{rel_type}]->(target {uuid: $target_uuid})
                    SET r.emotional_charge = $charge,
                        r.last_accessed = $now
                    RETURN r.emotional_charge
                    """.format(rel_type=relationship_type.upper()),
                    source_uuid=source_uuid,
                    target_uuid=target_uuid,
                    charge=max(-1.0, min(1.0, new_charge)),
                    now=datetime.now().isoformat()
                )
                return result.single() is not None
        except Exception as e:
            logger.error(f"Failed to update emotional charge: {e}")
            return False
    
    def get_recent_interactions(self, person_uuid: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent interactions involving a person"""
        if not self._enabled or not self._driver:
            return []
        
        try:
            with self._driver.session() as session:
                result = session.run(
                    """
                    MATCH (p:Person {uuid: $uuid})-[r:MENTIONS|INTERACTS_WITH]-(m:Memory)
                    RETURN m, r, r.created_at as timestamp
                    ORDER BY timestamp DESC
                    LIMIT $limit
                    """,
                    uuid=person_uuid,
                    limit=limit
                )
                interactions = []
                for record in result:
                    interactions.append({
                        'memory': dict(record['m']),
                        'relationship': dict(record['r']),
                        'timestamp': record['timestamp']
                    })
                return interactions
        except Exception as e:
            logger.error(f"Failed to get recent interactions: {e}")
            return []
    
    def prune_low_weight_edges(self, threshold: float = 0.1) -> int:
        """
        Remove relationships with weight below threshold (memory pruning).
        
        Args:
            threshold: Weight threshold (0-1)
            
        Returns:
            int: Number of edges removed
        """
        if not self._enabled or not self._driver:
            return 0
        
        try:
            with self._driver.session() as session:
                result = session.run(
                    """
                    MATCH ()-[r]->()
                    WHERE r.weight < $threshold
                    DELETE r
                    RETURN count(r) as removed_count
                    """,
                    threshold=threshold
                )
                record = result.single()
                return record['removed_count'] if record else 0
        except Exception as e:
            logger.error(f"Failed to prune edges: {e}")
            return 0