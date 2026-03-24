"""
Graph-Vault: Neo4j alapú kapcsolati memória.
Tárolja a személyek, témák, emlékek közötti kapcsolatokat és érzelmi töltetüket.
"""

from neo4j import GraphDatabase, AsyncGraphDatabase
import asyncio
from typing import Dict, List, Optional, Any
import uuid
import json

class GraphVault:
    """
    Kapcsolati memória kezelése.
    
    - Személyek, témák, események csomópontjai
    - Kapcsolatok érzelmi töltéssel (emotional_charge: -1..+1)
    - Kontextuális keresés
    """
    
    def __init__(self, uri: str = "bolt://localhost:7687", 
                 user: str = "neo4j", 
                 password: str = "soulcore2026"):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self._init_constraints()
    
    def _init_constraints(self):
        """Indításkor biztosítja a constraint-ök létezését"""
        with self.driver.session() as session:
            session.run("""
                CREATE CONSTRAINT IF NOT EXISTS FOR (m:Memory) REQUIRE m.uuid IS UNIQUE
            """)
            session.run("""
                CREATE CONSTRAINT IF NOT EXISTS FOR (p:Person) REQUIRE p.name IS UNIQUE
            """)
    
    def add_memory(self, content: str, memory_type: str = "conversation",
                   entities: List[Dict] = None, emotional_charge: float = 0.0,
                   user_id: str = None) -> str:
        """
        Emlék tárolása a gráfban.
        
        Args:
            content: Az emlék szövege
            memory_type: conversation, fact, event, preference
            entities: [{"name": "Grumpy", "type": "person", "role": "user"}]
            emotional_charge: -1 (negatív) .. +1 (pozitív)
            user_id: Felhasználó azonosító
        
        Returns:
            memory_uuid
        """
        memory_uuid = str(uuid.uuid4())
        
        with self.driver.session() as session:
            # Memória csomópont létrehozása
            session.run("""
                CREATE (m:Memory {
                    uuid: $uuid,
                    content: $content,
                    type: $type,
                    emotional_charge: $emotional_charge,
                    created_at: datetime(),
                    user_id: $user_id
                })
                RETURN m
            """, uuid=memory_uuid, content=content, type=memory_type,
                emotional_charge=emotional_charge, user_id=user_id)
            
            # Entitások és kapcsolatok
            if entities:
                for entity in entities:
                    # Entitás csomópont (merge)
                    session.run("""
                        MERGE (e:Entity {name: $name})
                        ON CREATE SET e.type = $entity_type
                        RETURN e
                    """, name=entity['name'], entity_type=entity.get('type', 'unknown'))
                    
                    # Kapcsolat az emlék és az entitás között
                    session.run("""
                        MATCH (m:Memory {uuid: $uuid})
                        MATCH (e:Entity {name: $name})
                        CREATE (m)-[:MENTIONS {
                            role: $role,
                            emotional_charge: $emotional_charge
                        }]->(e)
                    """, uuid=memory_uuid, name=entity['name'],
                        role=entity.get('role', 'subject'),
                        emotional_charge=emotional_charge)
        
        return memory_uuid
    
    def add_relationship(self, source: str, target: str, 
                        relationship_type: str, 
                        emotional_charge: float = 0.0,
                        metadata: Dict = None):
        """
        Két entitás közötti kapcsolat létrehozása/frissítése.
        
        Args:
            source: Forrás entitás neve
            target: Cél entitás neve
            relationship_type: pl. "likes", "discussed", "has_issue"
            emotional_charge: -1..+1
            metadata: JSON adatok
        """
        with self.driver.session() as session:
            session.run("""
                MERGE (s:Entity {name: $source})
                MERGE (t:Entity {name: $target})
                MERGE (s)-[r:RELATIONSHIP {type: $rel_type}]->(t)
                SET r.emotional_charge = COALESCE(r.emotional_charge, 0) + $emotional_charge,
                    r.emotional_charge = CASE 
                        WHEN r.emotional_charge > 1 THEN 1
                        WHEN r.emotional_charge < -1 THEN -1
                        ELSE r.emotional_charge
                    END,
                    r.updated_at = datetime(),
                    r.metadata = $metadata
                RETURN r
            """, source=source, target=target, rel_type=relationship_type,
                emotional_charge=emotional_charge, metadata=json.dumps(metadata or {}))
    
    def get_context(self, user_id: str, topic: str = None, 
                   limit: int = 10) -> Dict:
        """
        Kontextus lekérése a King számára.
        
        Returns:
            {
                "relationships": [...],
                "recent_memories": [...],
                "emotional_state": {...}
            }
        """
        with self.driver.session() as session:
            # 1. Kapcsolatok a userhez és a témához
            if topic:
                relationships = session.run("""
                    MATCH (u:Entity {name: $user_id})
                    MATCH (t:Entity {name: $topic})
                    MATCH path = (u)-[r:RELATIONSHIP*1..2]-(t)
                    RETURN r.type as type, r.emotional_charge as charge, 
                           nodes(path) as nodes
                    LIMIT $limit
                """, user_id=user_id, topic=topic, limit=limit)
            else:
                relationships = session.run("""
                    MATCH (u:Entity {name: $user_id})-[r:RELATIONSHIP]-(e)
                    RETURN e.name as entity, r.type as type, r.emotional_charge as charge
                    ORDER BY r.updated_at DESC
                    LIMIT $limit
                """, user_id=user_id, limit=limit)
            
            # 2. Legutóbbi emlékek
            memories = session.run("""
                MATCH (m:Memory)
                WHERE m.user_id = $user_id
                RETURN m.content as content, m.type as type, 
                       m.emotional_charge as charge, m.created_at as created
                ORDER BY m.created_at DESC
                LIMIT $limit
            """, user_id=user_id, limit=limit)
            
            return {
                'relationships': [dict(r) for r in relationships],
                'recent_memories': [dict(m) for m in memories],
                'emotional_state': self._get_emotional_state(user_id)
            }
    
    def _get_emotional_state(self, user_id: str) -> Dict:
        """Összesített érzelmi állapot lekérése"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (m:Memory {user_id: $user_id})
                RETURN avg(m.emotional_charge) as avg_charge, 
                       count(m) as memory_count
            """, user_id=user_id)
            return dict(result.single())
    
    def close(self):
        self.driver.close()