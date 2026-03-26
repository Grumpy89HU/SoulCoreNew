"""
Message Bus - ZMQ based broadcast system.
King speaks once, everyone hears it.
"""

import json
import threading
import time
import logging
from typing import Dict, Any, Callable, List, Optional
from queue import Queue, Empty

try:
    import zmq
    ZMQ_AVAILABLE = True
except ImportError:
    ZMQ_AVAILABLE = False
    print("⚠️ ZMQ not available, falling back to in-memory bus")

from src.bus.message_types import BroadcastMessage, MessageHeader, MessageTarget, MessageType

logger = logging.getLogger(__name__)


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
        self.pending_lock = threading.RLock()
        
        # Cleanup thread
        self.cleanup_interval = 60  # 1 perc
        self.last_cleanup = time.time()
        
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
            self.router_socket.setsockopt(zmq.RCVTIMEO, 1000)  # 1 second timeout
            self.router_socket.setsockopt(zmq.LINGER, 0)
            
            # DEALER socket (for responses)
            self.dealer_socket = self.context.socket(zmq.DEALER)
            self.dealer_socket.bind(f"tcp://*:{self.dealer_port}")
            self.dealer_socket.setsockopt(zmq.RCVTIMEO, 1000)
            self.dealer_socket.setsockopt(zmq.LINGER, 0)
            
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
                    try:
                        message = self.router_socket.recv_json()
                        self._handle_broadcast(message)
                    except json.JSONDecodeError as e:
                        print(f"📡 JSON decode hiba (broadcast): {e}")
                    except Exception as e:
                        print(f"📡 Broadcast recv hiba: {e}")
                
                # DEALER socket - responses
                if self.dealer_socket in socks:
                    try:
                        message = self.dealer_socket.recv_json()
                        self._handle_response(message)
                    except json.JSONDecodeError as e:
                        print(f"📡 JSON decode hiba (response): {e}")
                    except Exception as e:
                        print(f"📡 Response recv hiba: {e}")
                
                # Időzített takarítás
                if time.time() - self.last_cleanup > self.cleanup_interval:
                    self._cleanup_old_requests()
                    self.last_cleanup = time.time()
                    
            except Exception as e:
                print(f"📡 Message Bus hiba: {e}")
    
    def _handle_broadcast(self, message: Dict):
        """Handle broadcast from King"""
        header = message.get('header', {})
        payload = message.get('payload', {})
        
        trace_id = header.get('trace_id', 'unknown')
        required_agents = payload.get('required_agents', [])
        
        # Biztosítsuk, hogy lista legyen
        if not isinstance(required_agents, list):
            if isinstance(required_agents, str):
                required_agents = [required_agents]
            else:
                required_agents = []
        
        with self.pending_lock:
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
        
        if not in_response_to:
            return
        
        with self.pending_lock:
            if in_response_to in self.pending_requests:
                pending = self.pending_requests[in_response_to]
                sender = header.get('sender', 'unknown')
                pending['received'].add(sender)
                pending['responses'][sender] = message
                
                # Put in response queue for King
                self.response_queue.put({
                    'trace_id': in_response_to,
                    'sender': sender,
                    'message': message,
                    'timestamp': time.time()
                })
    
    def _cleanup_old_requests(self):
        """Régi pending request-ek törlése (5 percnél régebbiek)"""
        now = time.time()
        to_delete = []
        
        with self.pending_lock:
            for trace_id, pending in self.pending_requests.items():
                if now - pending['timestamp'] > 300:  # 5 perc
                    to_delete.append(trace_id)
            
            for trace_id in to_delete:
                del self.pending_requests[trace_id]
            
            if to_delete:
                print(f"📡 {len(to_delete)} régi pending request törölve")
    
    def broadcast(self, message: Dict):
        """
        Broadcast a message to all agents.
        King calls this.
        """
        if not self.running:
            print("📡 Broadcast: busz nem fut")
            return
        
        if not ZMQ_AVAILABLE:
            # In-memory fallback
            self._handle_broadcast(message)
            return
        
        try:
            self.router_socket.send_json(message, flags=zmq.NOBLOCK)
        except zmq.ZMQError as e:
            print(f"📡 Broadcast hiba: {e}")
            # Fallback in-memory
            self._handle_broadcast(message)
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
    
    def unsubscribe(self, agent_name: str, callback: Callable = None):
        """
        Unsubscribe an agent from the bus.
        """
        if agent_name in self.subscribers:
            if callback is None:
                # Remove all callbacks for this agent
                self.subscribers[agent_name] = []
                print(f"📡 {agent_name} összes callback eltávolítva")
            else:
                # Remove specific callback
                if callback in self.subscribers[agent_name]:
                    self.subscribers[agent_name].remove(callback)
                    print(f"📡 {agent_name} callback eltávolítva")
    
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
                
                time.sleep(0.05)
                
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
        if not self.running:
            print("📡 send_response: busz nem fut")
            return
        
        if not ZMQ_AVAILABLE:
            self._handle_response(message)
            return
        
        try:
            self.dealer_socket.send_json(message, flags=zmq.NOBLOCK)
        except zmq.ZMQError as e:
            print(f"📡 Response hiba: {e}")
            self._handle_response(message)
        except Exception as e:
            print(f"📡 Response hiba: {e}")
    
    def get_pending_requests(self) -> Dict:
        """Aktív pending request-ek lekérése"""
        with self.pending_lock:
            return {
                trace_id: {
                    'required': list(pending['required']),
                    'received': list(pending['received']),
                    'age': time.time() - pending['timestamp'],
                    'timestamp': pending['timestamp']
                }
                for trace_id, pending in self.pending_requests.items()
            }
    
    def get_stats(self) -> Dict:
        """Statisztikák lekérése"""
        with self.pending_lock:
            return {
                'running': self.running,
                'zmq_available': ZMQ_AVAILABLE,
                'subscribers': len(self.subscribers),
                'pending_requests': len(self.pending_requests),
                'queue_size': self.response_queue.qsize(),
                'config': {
                    'router_port': self.router_port,
                    'dealer_port': self.dealer_port
                }
            }
    
    def stop(self):
        """Stop the message bus"""
        print("📡 Message Bus: leállítás...")
        self.running = False
        
        if self.thread:
            self.thread.join(timeout=2)
        
        if self.context:
            try:
                self.context.term()
            except:
                pass
        
        self.subscribers.clear()
        
        with self.pending_lock:
            self.pending_requests.clear()
        
        # Clear queue
        while not self.response_queue.empty():
            try:
                self.response_queue.get_nowait()
            except Empty:
                break
        
        print("📡 Message Bus: leállt")
    
    def is_running(self) -> bool:
        """Visszaadja, hogy a busz fut-e"""
        return self.running


# Teszt
if __name__ == "__main__":
    bus = MessageBus()
    bus.start()
    
    # Teszt callback
    def on_message(msg):
        print(f"📨 Üzenet érkezett: {msg.get('payload', {}).get('type', 'unknown')}")
    
    bus.subscribe("test_agent", on_message)
    
    # Teszt broadcast
    test_message = {
        "header": {
            "trace_id": "test_001",
            "timestamp": time.time(),
            "sender": "test",
            "target": "kernel",
            "broadcast": True
        },
        "payload": {
            "type": "test_message",
            "data": "Hello, world!"
        }
    }
    
    print("\n--- Broadcast teszt ---")
    bus.broadcast(test_message)
    
    time.sleep(0.5)
    
    print("\n--- Statisztika ---")
    print(bus.get_stats())
    
    bus.stop()