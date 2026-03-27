"""
Graph-Vault module for SoulCore - Neo4j based relationship and emotional memory.
"""

import os
import json
import logging
import uuid
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

try:
    from neo4j import GraphDatabase, AsyncGraphDatabase
    from neo4j.exceptions import ServiceUnavailable, AuthError, SessionExpired
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
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "RelationshipNode":
        return cls(**data)


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
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "RelationshipEdge":
        return cls(**data)


class GraphVault:
    """
    Graph database interface for storing and querying relationship-based memory.
    Uses Neo4j as backend with emotional charge tracking.
    """
    
    # Node típusok
    NODE_TYPES = ['person', 'concept', 'memory', 'project', 'emotion', 'topic']
    
    # Relationship típusok
    REL_TYPES = ['MENTIONS', 'RELATED_TO', 'FEELS_ABOUT', 'DEVELOPED', 
                 'INTERACTS_WITH', 'KNOWS', 'CREATED', 'MODIFIED']
    
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
        
        try:
            with self._driver.session() as session:
                # Constraints
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:Memory) REQUIRE n.uuid IS UNIQUE")
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:Person) REQUIRE n.uuid IS UNIQUE")
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:Concept) REQUIRE n.uuid IS UNIQUE")
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:Topic) REQUIRE n.name IS UNIQUE")
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:Entity) REQUIRE n.name IS UNIQUE")
                
                # Indexes
                session.run("CREATE INDEX IF NOT EXISTS FOR (n:Person) ON (n.name)")
                session.run("CREATE INDEX IF NOT EXISTS FOR (n:Concept) ON (n.name)")
                session.run("CREATE INDEX IF NOT EXISTS FOR (n:Memory) ON (n.created_at)")
                session.run("CREATE INDEX IF NOT EXISTS FOR (n:Topic) ON (n.name)")
                session.run("CREATE INDEX IF NOT EXISTS FOR (n:Entity) ON (n.name)")
                session.run("CREATE INDEX IF NOT EXISTS FOR ()-[r:MENTIONS]-() ON (r.emotional_charge)")
                session.run("CREATE INDEX IF NOT EXISTS FOR ()-[r:RELATED_TO]-() ON (r.emotional_charge)")
                
        except Exception as e:
            logger.error(f"Failed to create constraints/indexes: {e}")
    
    def close(self):
        """Close database connections"""
        if self._driver:
            self._driver.close()
        if self._async_driver:
            self._async_driver.close()
    
    # ========== SEGÉDFÜGGVÉNYEK ==========
    
    def _safe_json_loads(self, data: Any, default: Dict = None) -> Dict:
        """Biztonságos JSON betöltés"""
        if default is None:
            default = {}
        if data is None:
            return default
        if isinstance(data, dict):
            return data
        if isinstance(data, str):
            try:
                return json.loads(data)
            except:
                return default
        return default
    
    def _safe_json_dumps(self, data: Any) -> str:
        """Biztonságos JSON mentés"""
        if data is None:
            return "{}"
        if isinstance(data, str):
            return data
        try:
            return json.dumps(data, default=str)
        except:
            return "{}"
    
    # ========== NODE MŰVELETEK ==========
    
    def create_node(self, node: RelationshipNode) -> bool:
        """Create a new node in the graph"""
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
                    properties=self._safe_json_dumps(node.properties),
                    created_at=node.created_at.isoformat(),
                    updated_at=node.updated_at.isoformat()
                )
                return result.single() is not None
        except Exception as e:
            logger.error(f"Failed to create node: {e}")
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
                    node_type = record['node_type'].lower() if record['node_type'] else 'unknown'
                    return RelationshipNode(
                        uuid=node_data.get('uuid', uuid),
                        name=node_data.get('name', ''),
                        node_type=node_type,
                        properties=self._safe_json_loads(node_data.get('properties')),
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
                    if node_type not in self.NODE_TYPES:
                        logger.warning(f"Invalid node type: {node_type}")
                        return None
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
                    node_type_val = record['node_type'].lower() if record['node_type'] else 'unknown'
                    return RelationshipNode(
                        uuid=node_data.get('uuid', ''),
                        name=node_data.get('name', ''),
                        node_type=node_type_val,
                        properties=self._safe_json_loads(node_data.get('properties')),
                        created_at=datetime.fromisoformat(node_data.get('created_at', datetime.now().isoformat())),
                        updated_at=datetime.fromisoformat(node_data.get('updated_at', datetime.now().isoformat()))
                    )
                return None
        except Exception as e:
            logger.error(f"Failed to get node by name: {e}")
            return None
    
    def get_all_nodes(self, node_type: Optional[str] = None, limit: int = 100) -> List[RelationshipNode]:
        """Get all nodes, optionally filtered by type"""
        if not self._enabled or not self._driver:
            return []
        
        try:
            with self._driver.session() as session:
                if node_type:
                    if node_type not in self.NODE_TYPES:
                        logger.warning(f"Invalid node type: {node_type}")
                        return []
                    query = """
                    MATCH (n:{node_type})
                    RETURN n, labels(n)[0] as node_type
                    ORDER BY n.created_at DESC
                    LIMIT $limit
                    """.format(node_type=node_type.capitalize())
                else:
                    query = """
                    MATCH (n)
                    RETURN n, labels(n)[0] as node_type
                    ORDER BY n.created_at DESC
                    LIMIT $limit
                    """
                
                result = session.run(query, limit=limit)
                nodes = []
                for record in result:
                    node_data = record['n']
                    node_type_val = record['node_type'].lower() if record['node_type'] else 'unknown'
                    nodes.append(RelationshipNode(
                        uuid=node_data.get('uuid', ''),
                        name=node_data.get('name', ''),
                        node_type=node_type_val,
                        properties=self._safe_json_loads(node_data.get('properties')),
                        created_at=datetime.fromisoformat(node_data.get('created_at', datetime.now().isoformat())),
                        updated_at=datetime.fromisoformat(node_data.get('updated_at', datetime.now().isoformat()))
                    ))
                return nodes
        except Exception as e:
            logger.error(f"Failed to get all nodes: {e}")
            return []
    
    def delete_node(self, uuid: str, cascade: bool = False) -> bool:
        """Delete a node and optionally its relationships"""
        if not self._enabled or not self._driver:
            return False
        
        try:
            with self._driver.session() as session:
                if cascade:
                    result = session.run(
                        """
                        MATCH (n {uuid: $uuid})
                        DETACH DELETE n
                        RETURN count(n) as deleted
                        """,
                        uuid=uuid
                    )
                else:
                    result = session.run(
                        """
                        MATCH (n {uuid: $uuid})
                        WHERE NOT (n)--()
                        DELETE n
                        RETURN count(n) as deleted
                        """,
                        uuid=uuid
                    )
                record = result.single()
                return record and record['deleted'] > 0
        except Exception as e:
            logger.error(f"Failed to delete node: {e}")
            return False
    
    # ========== EDGE MŰVELETEK ==========
    
    def create_edge(self, edge: RelationshipEdge) -> bool:
        """Create a relationship between two nodes"""
        if not self._enabled or not self._driver:
            logger.warning("Graph-Vault not available, skipping edge creation")
            return False
        
        rel_type = edge.relationship_type.upper()
        if rel_type not in self.REL_TYPES:
            logger.warning(f"Invalid relationship type: {rel_type}, using MENTIONS")
            rel_type = "MENTIONS"
        
        try:
            with self._driver.session() as session:
                result = session.run(
                    """
                    MATCH (source {uuid: $source_uuid})
                    MATCH (target {uuid: $target_uuid})
                    MERGE (source)-[r:{rel_type}]->(target)
                    SET r.emotional_charge = $emotional_charge,
                        r.weight = $weight,
                        r.properties = $properties,
                        r.created_at = $created_at,
                        r.last_accessed = $last_accessed
                    RETURN r
                    """.format(rel_type=rel_type),
                    source_uuid=edge.source_uuid,
                    target_uuid=edge.target_uuid,
                    emotional_charge=edge.emotional_charge,
                    weight=edge.weight,
                    properties=self._safe_json_dumps(edge.properties),
                    created_at=edge.created_at.isoformat(),
                    last_accessed=edge.last_accessed.isoformat()
                )
                return result.single() is not None
        except Exception as e:
            logger.error(f"Failed to create edge: {e}")
            return False
    
    def get_edges(self, node_uuid: str, relationship_type: Optional[str] = None, 
                  direction: str = 'both', limit: int = 50) -> List[Dict[str, Any]]:
        """Get edges connected to a node"""
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
                    rel_type = relationship_type.upper()
                    query = f"""
                    MATCH (n {{uuid: $uuid}}){dir_pattern}(connected)
                    WHERE type(r) = $rel_type
                    RETURN connected, r, type(r) as rel_type, 
                           startnode(r).uuid as source_uuid, 
                           endnode(r).uuid as target_uuid
                    ORDER BY r.last_accessed DESC
                    LIMIT $limit
                    """
                    params = {'uuid': node_uuid, 'rel_type': rel_type, 'limit': limit}
                else:
                    query = f"""
                    MATCH (n {{uuid: $uuid}}){dir_pattern}(connected)
                    RETURN connected, r, type(r) as rel_type, 
                           startnode(r).uuid as source_uuid, 
                           endnode(r).uuid as target_uuid
                    ORDER BY r.last_accessed DESC
                    LIMIT $limit
                    """
                    params = {'uuid': node_uuid, 'limit': limit}
                
                result = session.run(query, **params)
                edges = []
                for record in result:
                    rel_data = record['r']
                    connected = record['connected']
                    edges.append({
                        'connected_node': {
                            'uuid': connected.get('uuid'),
                            'name': connected.get('name'),
                            'labels': list(connected.labels) if connected.labels else []
                        },
                        'relationship_type': record['rel_type'],
                        'source_uuid': record['source_uuid'],
                        'target_uuid': record['target_uuid'],
                        'emotional_charge': rel_data.get('emotional_charge', 0.0),
                        'weight': rel_data.get('weight', 0.5),
                        'properties': self._safe_json_loads(rel_data.get('properties')),
                        'created_at': rel_data.get('created_at'),
                        'last_accessed': rel_data.get('last_accessed')
                    })
                return edges
        except Exception as e:
            logger.error(f"Failed to get edges: {e}")
            return []
    
    def delete_edge(self, source_uuid: str, target_uuid: str, relationship_type: str) -> bool:
        """Delete a specific relationship"""
        if not self._enabled or not self._driver:
            return False
        
        rel_type = relationship_type.upper()
        
        try:
            with self._driver.session() as session:
                result = session.run(
                    """
                    MATCH (source {uuid: $source_uuid})-[r:{rel_type}]->(target {uuid: $target_uuid})
                    DELETE r
                    RETURN count(r) as deleted
                    """.format(rel_type=rel_type),
                    source_uuid=source_uuid,
                    target_uuid=target_uuid
                )
                record = result.single()
                return record and record['deleted'] > 0
        except Exception as e:
            logger.error(f"Failed to delete edge: {e}")
            return False
    
    # ========== KERESÉSEK ==========
    
    def query_relationships(self, node_uuid: str, relationship_type: Optional[str] = None, 
                            direction: str = 'both', limit: int = 50) -> List[Dict[str, Any]]:
        """Query all relationships connected to a node (alias for get_edges)"""
        return self.get_edges(node_uuid, relationship_type, direction, limit)
    
    def get_emotional_context(self, concept_name: str, max_depth: int = 2) -> Dict[str, Any]:
        """Retrieve emotional context around a concept"""
        if not self._enabled or not self._driver:
            return {'emotional_charge': 0.0, 'related_concepts': [], 'confidence': 0.0}
        
        try:
            with self._driver.session() as session:
                # Először próbáljuk concept-ként
                concept = self.get_node_by_name(concept_name, 'concept')
                if not concept:
                    concept = self.get_node_by_name(concept_name, 'topic')
                if not concept:
                    return {'emotional_charge': 0.0, 'related_concepts': [], 'confidence': 0.0}
                
                query = """
                MATCH path = (c {uuid: $uuid})-[r*1..{max_depth}]-(connected)
                WHERE connected:Memory OR connected:Concept OR connected:Topic
                RETURN connected, 
                       reduce(charge = 0.0, rel IN r | charge + coalesce(rel.emotional_charge, 0.0)) / size(r) as avg_charge,
                       reduce(w = 0.0, rel IN r | w + coalesce(rel.weight, 0.0)) as total_weight
                LIMIT 20
                """.format(max_depth=max_depth)
                
                result = session.run(query, uuid=concept.uuid)
                
                charges = []
                related = []
                
                for record in result:
                    if record['avg_charge'] is not None:
                        charges.append(record['avg_charge'])
                    if record['connected']:
                        connected = record['connected']
                        rel_type = list(connected.labels)[0] if connected.labels else 'unknown'
                        related.append({
                            'name': connected.get('name', ''),
                            'uuid': connected.get('uuid', ''),
                            'type': rel_type.lower(),
                            'charge': record['avg_charge'] if record['avg_charge'] else 0.0
                        })
                
                avg_charge = sum(charges) / len(charges) if charges else 0.0
                
                return {
                    'emotional_charge': avg_charge,
                    'related_concepts': related[:10],
                    'confidence': min(1.0, len(charges) / 10) if charges else 0.0
                }
        except Exception as e:
            logger.error(f"Failed to get emotional context: {e}")
            return {'emotional_charge': 0.0, 'related_concepts': [], 'confidence': 0.0}
    
    def get_emotional_charge(self, topic: str) -> Optional[float]:
        """
        Egy adott téma érzelmi töltésének lekérése.
        A King ezt használja a hangulatfüggő válaszadáshoz.
        """
        context = self.get_emotional_context(topic, max_depth=1)
        return context.get('emotional_charge', 0.0)
    
    def get_related_topics(self, topic: str, limit: int = 5) -> List[str]:
        """
        Kapcsolódó témák lekérése.
        """
        context = self.get_emotional_context(topic, max_depth=1)
        related = context.get('related_concepts', [])
        return [r.get('name', '') for r in related[:limit] if r.get('name')]
    
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
                    memory = record['m']
                    rel = record['r']
                    interactions.append({
                        'memory': {
                            'uuid': memory.get('uuid'),
                            'content': memory.get('content', ''),
                            'type': memory.get('type', 'unknown'),
                            'created_at': memory.get('created_at')
                        },
                        'relationship': {
                            'type': rel.get('type'),
                            'emotional_charge': rel.get('emotional_charge', 0.0),
                            'weight': rel.get('weight', 0.5)
                        },
                        'timestamp': record['timestamp']
                    })
                return interactions
        except Exception as e:
            logger.error(f"Failed to get recent interactions: {e}")
            return []
    
    # ========== FRISSÍTÉSEK ==========
    
    def update_edge_weight(self, source_uuid: str, target_uuid: str, 
                           relationship_type: str, delta_weight: float) -> bool:
        """Update the weight of an existing relationship"""
        if not self._enabled or not self._driver:
            return False
        
        rel_type = relationship_type.upper()
        
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
                    """.format(rel_type=rel_type),
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
        """Update the emotional charge of a relationship"""
        if not self._enabled or not self._driver:
            return False
        
        rel_type = relationship_type.upper()
        
        try:
            with self._driver.session() as session:
                result = session.run(
                    """
                    MATCH (source {uuid: $source_uuid})-[r:{rel_type}]->(target {uuid: $target_uuid})
                    SET r.emotional_charge = $charge,
                        r.last_accessed = $now
                    RETURN r.emotional_charge
                    """.format(rel_type=rel_type),
                    source_uuid=source_uuid,
                    target_uuid=target_uuid,
                    charge=max(-1.0, min(1.0, new_charge)),
                    now=datetime.now().isoformat()
                )
                return result.single() is not None
        except Exception as e:
            logger.error(f"Failed to update emotional charge: {e}")
            return False
    
    # ========== KARBANTARTÁS ==========
    
    def prune_low_weight_edges(self, threshold: float = 0.1) -> int:
        """Remove relationships with weight below threshold"""
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
                removed = record['removed_count'] if record else 0
                if removed > 0:
                    logger.info(f"Pruned {removed} low-weight edges")
                return removed
        except Exception as e:
            logger.error(f"Failed to prune edges: {e}")
            return 0
    
    def prune_old_memories(self, days_old: int = 90) -> int:
        """Remove memories older than specified days (with low importance)"""
        if not self._enabled or not self._driver:
            return 0
        
        cutoff = datetime.now() - timedelta(days=days_old)
        
        try:
            with self._driver.session() as session:
                result = session.run(
                    """
                    MATCH (m:Memory)
                    WHERE m.created_at < $cutoff AND (m.importance IS NULL OR m.importance < 0.3)
                    DETACH DELETE m
                    RETURN count(m) as removed_count
                    """,
                    cutoff=cutoff.isoformat()
                )
                record = result.single()
                removed = record['removed_count'] if record else 0
                if removed > 0:
                    logger.info(f"Pruned {removed} old memories")
                return removed
        except Exception as e:
            logger.error(f"Failed to prune old memories: {e}")
            return 0
    
    def clear_database(self) -> bool:
        """Clear all nodes and relationships (for testing)"""
        if not self._enabled or not self._driver:
            return False
        
        try:
            with self._driver.session() as session:
                session.run("MATCH (n) DETACH DELETE n")
                logger.info("Database cleared")
                return True
        except Exception as e:
            logger.error(f"Failed to clear database: {e}")
            return False
    
    # ========== STATISZTIKÁK ==========
    
    def get_node_count(self, node_type: Optional[str] = None) -> int:
        """Get count of nodes, optionally filtered by type"""
        if not self._enabled or not self._driver:
            return 0
        
        try:
            with self._driver.session() as session:
                if node_type:
                    node_type_cap = node_type.capitalize()
                    query = f"MATCH (n:{node_type_cap}) RETURN count(n) as count"
                else:
                    query = "MATCH (n) RETURN count(n) as count"
                
                result = session.run(query)
                record = result.single()
                return record['count'] if record else 0
        except Exception as e:
            logger.error(f"Failed to get node count: {e}")
            return 0
    
    def get_edge_count(self, relationship_type: Optional[str] = None) -> int:
        """Get count of relationships, optionally filtered by type"""
        if not self._enabled or not self._driver:
            return 0
        
        try:
            with self._driver.session() as session:
                if relationship_type:
                    rel_type = relationship_type.upper()
                    query = f"MATCH ()-[r:{rel_type}]->() RETURN count(r) as count"
                else:
                    query = "MATCH ()-[r]->() RETURN count(r) as count"
                
                result = session.run(query)
                record = result.single()
                return record['count'] if record else 0
        except Exception as e:
            logger.error(f"Failed to get edge count: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        return {
            'enabled': self._enabled,
            'connected': self._driver is not None,
            'node_count': self.get_node_count(),
            'edge_count': self.get_edge_count(),
            'node_counts': {
                node_type: self.get_node_count(node_type)
                for node_type in self.NODE_TYPES
            }
        }


# Teszt
if __name__ == "__main__":
    # Mock config
    config = {
        'memory': {
            'vault': {
                'neo4j': {
                    'uri': 'bolt://localhost:7687',
                    'user': 'neo4j',
                    'password': 'soulcore2026'
                }
            }
        }
    }
    
    vault = GraphVault(config)
    
    if vault._enabled:
        print("Graph-Vault connected")
        print(f"Stats: {vault.get_stats()}")
    else:
        print("Graph-Vault disabled (Neo4j not available)")
    
    vault.close()