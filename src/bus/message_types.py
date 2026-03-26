"""
Message types for ZMQ broadcast communication.
All messages are JSON with this structure.
"""

from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict, field
from enum import Enum
import json


class MessageTarget(Enum):
    """Címzett típusok"""
    KERNEL = "kernel"
    KING = "king"
    SCRIBE = "scribe"
    VALET = "valet"
    QUEEN = "queen"
    JESTER = "jester"
    HEARTBEAT = "heartbeat"
    ORCHESTRATOR = "orchestrator"
    ROUTER = "router"
    ALL = "all"
    WEBAPP = "webapp"


class MessageType(Enum):
    """Üzenet típusok"""
    # Broadcast típusok
    ROYAL_DECREE = "royal_decree"           # King beszéde (broadcast)
    PROACTIVE_MESSAGE = "proactive_message" # Heartbeat proaktív üzenete
    
    # Válasz típusok
    CONTEXT_RESPONSE = "context_response"   # Valet válasza
    LOGIC_RESPONSE = "logic_response"       # Queen válasza
    JESTER_REPORT = "jester_report"         # Jester jelentése
    KING_RESPONSE = "king_response"         # King válasza
    LOG_COMPLETE = "log_complete"           # Scribe válasza
    
    # Esemény típusok
    MODULE_FROZEN = "module_frozen"         # Router: modul befagyott
    MODULE_REVIVED = "module_revived"       # Router: modul újraéledt
    MODULE_REGISTERED = "module_registered" # Router: modul regisztrálva
    MODULE_UNREGISTERED = "module_unregistered"  # Router: modul eltávolítva
    
    # Heartbeat típusok
    HEARTBEAT = "heartbeat"                 # Heartbeat ping/pong
    
    # User típusok
    USER_MESSAGE = "user_message"           # Felhasználótól


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
    
    @classmethod
    def from_dict(cls, data: Dict) -> "MessageHeader":
        return cls(**data)


@dataclass
class Intent:
    """Szándék struktúrája"""
    class_name: str = "unknown"
    confidence: float = 0.0
    target: str = "king"
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Intent":
        return cls(**data)


@dataclass
class Entity:
    """Entitás struktúrája"""
    type: str
    value: str
    confidence: float = 0.8
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Entity":
        return cls(**data)


@dataclass
class SafetyResult:
    """Biztonsági ellenőrzés eredménye"""
    is_safe: bool = True
    score: float = 0.0
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "SafetyResult":
        return cls(**data)


@dataclass
class RoyalDecreePayload:
    """King beszéde (broadcast)"""
    type: str = "royal_decree"
    user_message: str = ""
    interpretation: Dict[str, Any] = field(default_factory=dict)
    conversation_history: List[Dict] = field(default_factory=list)
    rag_context: Dict[str, Any] = field(default_factory=dict)
    order: str = "prepare_context"
    required_agents: List[str] = field(default_factory=list)
    optional_agents: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "RoyalDecreePayload":
        return cls(**data)


@dataclass
class ContextResponsePayload:
    """Valet válasza"""
    type: str = "context_response"
    context: Dict[str, Any] = field(default_factory=dict)
    summary: str = ""
    facts: List[str] = field(default_factory=list)
    emotional_charge: float = 0.0
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ContextResponsePayload":
        return cls(**data)


@dataclass
class LogicResponsePayload:
    """Queen válasza"""
    type: str = "logic_response"
    logic: Dict[str, Any] = field(default_factory=dict)
    thought: List[str] = field(default_factory=list)
    facts: List[str] = field(default_factory=list)
    conclusion: str = ""
    confidence: float = 0.0
    warnings: List[str] = field(default_factory=list)
    contradictions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "LogicResponsePayload":
        return cls(**data)


@dataclass
class JesterReportPayload:
    """Jester jelentése"""
    type: str = "jester_report"
    problems: List[Dict] = field(default_factory=list)
    interventions: List[str] = field(default_factory=list)
    king_mood: str = "neutral"
    recommendations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "JesterReportPayload":
        return cls(**data)


@dataclass
class KingResponsePayload:
    """King válasza"""
    type: str = "king_response"
    response: str = ""
    confidence: float = 0.0
    response_time_ms: int = 0
    tokens_used: int = 0
    mood: str = "neutral"
    rag_used: bool = False
    error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "KingResponsePayload":
        return cls(**data)


@dataclass
class ProactiveMessagePayload:
    """Heartbeat proaktív üzenete"""
    type: str = "proactive_message"
    subtype: str = "interest"  # interest, reminder
    topic: str = ""
    idle_hours: float = 0.0
    idle_formatted: str = ""
    reminder_id: str = ""
    note: str = ""
    language: str = "en"
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ProactiveMessagePayload":
        return cls(**data)


@dataclass
class HeartbeatPayload:
    """Heartbeat ping/pong üzenet"""
    type: str = "heartbeat"
    heartbeat_type: str = "ping"  # ping, pong
    timestamp: float = 0.0
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "HeartbeatPayload":
        return cls(**data)


@dataclass
class ModuleEventPayload:
    """Router modul esemény"""
    type: str = "module_frozen"  # module_frozen, module_revived, module_registered, module_unregistered
    module: str = ""
    timeout: Optional[float] = None
    last_seen: Optional[float] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ModuleEventPayload":
        return cls(**data)


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
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "BroadcastMessage":
        header = MessageHeader.from_dict(data.get("header", {}))
        payload = data.get("payload", {})
        telemetry = data.get("telemetry")
        return cls(header=header, payload=payload, telemetry=telemetry)
    
    @classmethod
    def from_json(cls, json_str: str) -> "BroadcastMessage":
        data = json.loads(json_str)
        return cls.from_dict(data)


# ========== SEGÉDFÜGGVÉNYEK ==========

def create_royal_decree(
    trace_id: str,
    user_message: str,
    interpretation: Dict,
    required_agents: List[str],
    conversation_history: List[Dict] = None,
    rag_context: Dict = None,
    optional_agents: List[str] = None
) -> Dict:
    """Királyi rendelet létrehozása"""
    return {
        "header": {
            "trace_id": trace_id,
            "timestamp": time.time(),
            "version": "3.0",
            "sender": "king",
            "target": "kernel",
            "broadcast": True
        },
        "payload": {
            "type": "royal_decree",
            "user_message": user_message,
            "interpretation": interpretation,
            "conversation_history": conversation_history or [],
            "rag_context": rag_context or {},
            "order": "prepare_context",
            "required_agents": required_agents,
            "optional_agents": optional_agents or ["jester"]
        },
        "telemetry": {
            "temperature": 0.7
        }
    }


def create_context_response(
    trace_id: str,
    in_response_to: str,
    context: Dict
) -> Dict:
    """Valet kontextus válasz létrehozása"""
    return {
        "header": {
            "trace_id": trace_id,
            "timestamp": time.time(),
            "sender": "valet",
            "target": "king",
            "in_response_to": in_response_to
        },
        "payload": {
            "type": "context_response",
            "context": context
        }
    }


def create_logic_response(
    trace_id: str,
    in_response_to: str,
    thought: List[str],
    conclusion: str,
    confidence: float
) -> Dict:
    """Queen logikai válasz létrehozása"""
    return {
        "header": {
            "trace_id": trace_id,
            "timestamp": time.time(),
            "sender": "queen",
            "target": "king",
            "in_response_to": in_response_to
        },
        "payload": {
            "type": "logic_response",
            "logic": {
                "thought": thought,
                "conclusion": conclusion,
                "confidence": confidence
            }
        }
    }


def create_jester_report(
    trace_id: str,
    in_response_to: str,
    problems: List[Dict],
    king_mood: str
) -> Dict:
    """Jester jelentés létrehozása"""
    return {
        "header": {
            "trace_id": trace_id,
            "timestamp": time.time(),
            "sender": "jester",
            "target": "king",
            "in_response_to": in_response_to
        },
        "payload": {
            "type": "jester_report",
            "problems": problems,
            "interventions": [],
            "king_mood": king_mood,
            "recommendations": []
        }
    }


def create_king_response(
    trace_id: str,
    in_response_to: str,
    response_text: str,
    confidence: float = 0.95,
    mood: str = "neutral"
) -> Dict:
    """King válasz létrehozása"""
    return {
        "header": {
            "trace_id": trace_id,
            "timestamp": time.time(),
            "sender": "king",
            "target": "orchestrator",
            "in_response_to": in_response_to
        },
        "payload": {
            "type": "king_response",
            "response": response_text,
            "confidence": confidence,
            "response_time_ms": 0,
            "tokens_used": 0,
            "mood": mood,
            "rag_used": False
        }
    }


def create_proactive_message(
    trace_id: str,
    subtype: str,
    topic: str,
    idle_hours: float = 0,
    note: str = "",
    language: str = "en"
) -> Dict:
    """Proaktív üzenet létrehozása (Heartbeat)"""
    return {
        "header": {
            "trace_id": trace_id,
            "timestamp": time.time(),
            "sender": "heartbeat",
            "target": "kernel",
            "broadcast": True
        },
        "payload": {
            "type": "proactive_message",
            "subtype": subtype,
            "topic": topic,
            "idle_hours": idle_hours,
            "note": note,
            "language": language
        }
    }


# Import time a segédfüggvényekhez
import time


# Teszt
if __name__ == "__main__":
    # Teszt üzenet létrehozása
    decree = create_royal_decree(
        trace_id="test_001",
        user_message="Hello!",
        interpretation={"intent": {"class": "greeting"}},
        required_agents=["scribe", "valet"]
    )
    
    print("Royal Decree:")
    print(json.dumps(decree, indent=2, ensure_ascii=False))
    
    # Teszt beolvasás
    msg = BroadcastMessage.from_dict(decree)
    print(f"\nParsed: {msg.header.trace_id} - {msg.payload.get('type')}")