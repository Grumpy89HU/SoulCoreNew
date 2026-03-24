"""
Memory module for SoulCore - handles short-term (Scratchpad), 
graph-based (Graph-Vault), and vector-based (Vector-Vault) memory.
"""

from .scratchpad import Scratchpad
from .graph_vault import GraphVault, RelationshipNode, RelationshipEdge
from .vector_vault import VectorVault

__all__ = ['Scratchpad', 'GraphVault', 'VectorVault', 'RelationshipNode', 'RelationshipEdge']