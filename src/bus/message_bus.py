"""
Message Bus - ZMQ based broadcast system.
King speaks once, everyone hears it.
"""

import json
import threading
import time
from typing import Dict, Any, Callable, List, Optional
from queue import Queue, Empty

try:
    import zmq
    ZMQ_AVAILABLE = True
except ImportError:
    ZMQ_AVAILABLE = False
    print("⚠️ ZMQ not available, falling back to in-memory bus")

from src.bus.message_types import BroadcastMessage, MessageHeader, MessageTarget, MessageType


class MessageBus:
    """
    ZMQ based broadcast bus.
    
    Usage:
        bus = MessageBus()
        bus.start()
        
        # King speaks
        bus.broadcast(message)
        
        # Others listen
        bus.subscribe("scribe", callback)
        bus.subscribe("valet", callback)
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.name = "message_bus"
        
        # ZMQ settings
        self.router_port = self.config.get('router_port', 5555)
        self.dealer_port = self.config.get('dealer_port', 5556)
        
        # ZMQ context and sockets
        self.context = None
        self.router_socket = None
        self.dealer_socket = None
        
        # Callback registry
        self.subscribers: Dict[str, List[Callable]] = {}
        
        # Running state
        self.running = False
        self.thread = None
        
        # Message queue for responses
        self.response_queue = Queue()
        
        # Track pending requests (trace_id -> set of required agents)
        self.pending_requests: Dict[str, Dict] = {}
        
        print("📡 Message Bus: ZMQ broadcast bus inicializálva")
    
    def start(self):
        """Start the message bus"""
        if not ZMQ_AVAILABLE:
            print("📡 Message Bus: ZMQ nem elérhető, memóriabeli módban futok")
            self.running = True
            return
        
        try:
            self.context = zmq.Context()
            
            # ROUTER socket (for broadcasting to all)
            self.router_socket = self.context.socket(zmq.ROUTER)
            self.router_socket.bind(f"tcp://*:{self.router_port}")
            
            # DEALER socket (for responses)
            self.dealer_socket = self.context.socket(zmq.DEALER)
            self.dealer_socket.bind(f"tcp://*:{self.dealer_port}")
            
            self.running = True
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
            
            print(f"📡 Message Bus: ZMQ fut - ROUTER:{self.router_port}, DEALER:{self.dealer_port}")
            
        except Exception as e:
            print(f"📡 Message Bus: ZMQ indítási hiba: {e}")
            self.running = False
    
    def _run(self):
        """Main loop - receives and distributes messages"""
        if not ZMQ_AVAILABLE:
            return
        
        poller = zmq.Poller()
        poller.register(self.router_socket, zmq.POLLIN)
        poller.register(self.dealer_socket, zmq.POLLIN)
        
        while self.running:
            try:
                socks = dict(poller.poll(timeout=100))
                
                # ROUTER socket - broadcast messages
                if self.router_socket in socks:
                    message = self.router_socket.recv_json()
                    self._handle_broadcast(message)
                
                # DEALER socket - responses
                if self.dealer_socket in socks:
                    message = self.dealer_socket.recv_json()
                    self._handle_response(message)
                    
            except Exception as e:
                print(f"📡 Message Bus hiba: {e}")
    
    def _handle_broadcast(self, message: Dict):
        """Handle broadcast from King"""
        header = message.get('header', {})
        payload = message.get('payload', {})
        
        trace_id = header.get('trace_id', 'unknown')
        required_agents = payload.get('required_agents', [])
        
        # Register pending request
        self.pending_requests[trace_id] = {
            'required': set(required_agents),
            'received': set(),
            'responses': {},
            'timestamp': time.time()
        }
        
        # Notify subscribers
        for agent_name, callbacks in self.subscribers.items():
            for callback in callbacks:
                try:
                    callback(message)
                except Exception as e:
                    print(f"📡 Callback hiba {agent_name}: {e}")
    
    def _handle_response(self, message: Dict):
        """Handle response from agents"""
        header = message.get('header', {})
        in_response_to = header.get('in_response_to', '')
        
        if in_response_to in self.pending_requests:
            pending = self.pending_requests[in_response_to]
            sender = header.get('sender', 'unknown')
            pending['received'].add(sender)
            pending['responses'][sender] = message
            
            # Put in response queue for King
            self.response_queue.put({
                'trace_id': in_response_to,
                'sender': sender,
                'message': message
            })
    
    def broadcast(self, message: Dict):
        """
        Broadcast a message to all agents.
        King calls this.
        """
        if not ZMQ_AVAILABLE:
            # In-memory fallback
            self._handle_broadcast(message)
            return
        
        try:
            self.router_socket.send_json(message)
        except Exception as e:
            print(f"📡 Broadcast hiba: {e}")
    
    def subscribe(self, agent_name: str, callback: Callable):
        """
        Subscribe an agent to the bus.
        Agent calls this to register.
        """
        if agent_name not in self.subscribers:
            self.subscribers[agent_name] = []
        self.subscribers[agent_name].append(callback)
        print(f"📡 {agent_name} feliratkozott a buszra")
    
    def wait_for_responses(self, trace_id: str, required_agents: List[str], 
                           timeout: float = 5.0) -> Dict[str, Any]:
        """
        Wait for all required agents to respond.
        King calls this after broadcasting.
        
        Returns:
            Dict of responses from agents
        """
        start_time = time.time()
        required_set = set(required_agents)
        responses = {}
        
        while time.time() - start_time < timeout:
            try:
                # Check queue for responses
                while True:
                    try:
                        resp = self.response_queue.get_nowait()
                        if resp['trace_id'] == trace_id:
                            responses[resp['sender']] = resp['message']
                    except Empty:
                        break
                
                # Check if we have all responses
                if set(responses.keys()) >= required_set:
                    break
                
                time.sleep(0.05)  # Small wait
                
            except Exception as e:
                print(f"📡 Várakozási hiba: {e}")
        
        # Log missing agents
        missing = required_set - set(responses.keys())
        if missing:
            print(f"📡 Időtúllépés: {missing} nem válaszolt")
        
        return responses
    
    def send_response(self, message: Dict):
        """
        Send response to King.
        Agents call this.
        """
        if not ZMQ_AVAILABLE:
            self._handle_response(message)
            return
        
        try:
            self.dealer_socket.send_json(message)
        except Exception as e:
            print(f"📡 Response hiba: {e}")
    
    def stop(self):
        """Stop the message bus"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        
        if self.context:
            self.context.term()
        
        print("📡 Message Bus: leállt")