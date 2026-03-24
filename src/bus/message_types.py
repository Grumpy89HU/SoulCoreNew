"""
Message types for ZMQ broadcast communication.
All messages are JSON with this structure.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum


class MessageTarget(Enum):
    """Címzett típusok"""
    KERNEL = "kernel"
    KING = "king"
    SCRIBE = "scribe"
    VALET = "valet"
    QUEEN = "queen"
    JESTER = "jester"
    ALL = "all"
    WEBAPP = "webapp"


class MessageType(Enum):
    """Üzenet típusok"""
    ROYAL_DECREE = "royal_decree"      # King beszéde (broadcast)
    CONTEXT_RESPONSE = "context_response"   # Valet válasza
    LOG_COMPLETE = "log_complete"      # Scribe válasza
    LOGIC_RESPONSE = "logic_response"  # Queen válasza
    OBSERVATION = "observation"        # Jester válasza
    USER_MESSAGE = "user_message"      # Felhasználótól
    KING_RESPONSE = "king_response"    # King válasza felhasználónak


@dataclass
class MessageHeader:
    """Minden üzenet fejléce"""
    trace_id: str
    timestamp: float
    version: str = "3.0"
    sender: str = ""
    target: str = "kernel"
    broadcast: bool = False
    in_response_to: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class RoyalDecreePayload:
    """King beszéde (broadcast)"""
    type: str = "royal_decree"
    user_message: str = ""
    interpretation: Dict[str, Any] = None
    order: str = "prepare_context"
    required_agents: List[str] = None
    optional_agents: List[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class BroadcastMessage:
    """Teljes broadcast üzenet"""
    header: MessageHeader
    payload: Dict[str, Any]
    telemetry: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict:
        result = {"header": self.header.to_dict(), "payload": self.payload}
        if self.telemetry:
            result["telemetry"] = self.telemetry
        return result
    
    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False)