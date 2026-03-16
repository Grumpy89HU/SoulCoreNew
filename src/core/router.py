"""
Router - A Vár kommunikációs idegpályája.
ZeroMQ alapú üzenetküldés a modulok között.

Topológia:
- ROUTER socket (Kernel) a központban
- DEALER socket (Slotok) a moduloknál
- Heartbeat: minden slot 500ms-enként PING
"""

import time
import threading
import json
import queue
from typing import Dict, Any, Callable, Optional
from collections import defaultdict

# ZMQ import (ha nincs telepítve, nem törik el a rendszer)
try:
    import zmq
    ZMQ_AVAILABLE = True
except ImportError:
    ZMQ_AVAILABLE = False
    print("⚠️ ZMQ nem elérhető. A Router fallback módban fut (queue).")

class Router:
    """
    Router - Üzenetközpont.
    
    Ha van ZMQ: valódi socket kommunikáció
    Ha nincs ZMQ: belső queue (fejlesztéshez, teszteléshez)
    """
    
    # Protokoll konstansok
    PING = "PING"
    PONG = "PONG"
    MSG = "MSG"
    CMD = "CMD"
    
    def __init__(self, scratchpad):
        self.scratchpad = scratchpad
        self.name = "router"
        
        # Futás állapota
        self.running = False
        self.threads = []
        
        # ZMQ context (ha van)
        self.zmq_context = None
        self.zmq_socket = None
        
        # Regisztrált modulok (slotok)
        self.modules = {}  # name -> {type, address, last_seen, queue}
        
        # Heartbeat tracking
        self.last_heartbeat = {}  # module -> timestamp
        self.heartbeat_timeout = 3.0  # 3 másodperc
        
        # Queue fallback (ha nincs ZMQ)
        self.message_queue = queue.Queue()
        self.handlers = defaultdict(list)  # message_type -> [callbacks]
        
        print("🔌 Router: Kommunikációs pálya inicializálva.")
        if not ZMQ_AVAILABLE:
            print("   ⚠️ ZMQ nélkül (queue mód) futok.")
    
    def start(self):
        """Router indítása"""
        self.running = True
        
        # ZMQ indítás (ha van)
        if ZMQ_AVAILABLE:
            self._start_zmq()
        
        # Fogadó szál indítása
        receiver = threading.Thread(target=self._receiver_loop, daemon=True)
        receiver.start()
        self.threads.append(receiver)
        
        # Heartbeat ellenőrző szál indítása
        hb_checker = threading.Thread(target=self._heartbeat_check_loop, daemon=True)
        hb_checker.start()
        self.threads.append(hb_checker)
        
        self.scratchpad.set_state('router_status', 'running', self.name)
        print("🔌 Router: Aktív. Figyelek.")
    
    def stop(self):
        """Router leállítása"""
        self.running = False
        
        # ZMQ leállítás - csak ha valóban van ZMQ
        if ZMQ_AVAILABLE:
            try:
                if self.zmq_socket:
                    self.zmq_socket.close()
                if self.zmq_context:
                    self.zmq_context.term()
            except Exception as e:
                print(f"🔌 ZMQ leállítási hiba: {e}")
        
        # Szálak megvárása
        for t in self.threads:
            t.join(timeout=1.0)
        
        self.scratchpad.set_state('router_status', 'stopped', self.name)
        print("🔌 Router: Leállt.")
    
    # --- ZMQ INICIALIZÁLÁS ---
    
    def _start_zmq(self):
        """ZMQ socket inicializálása (ROUTER mód)"""
        try:
            self.zmq_context = zmq.Context()
            self.zmq_socket = self.zmq_context.socket(zmq.ROUTER)
            self.zmq_socket.bind("tcp://*:5555")  # Alap port
            print("🔌 ZMQ ROUTER fut a tcp://*:5555 címen")
        except Exception as e:
            print(f"🔌 ZMQ hiba: {e}")
            self.zmq_socket = None
            self.zmq_context = None
    
    # --- FŐ CIKLUSOK ---
    
    def _receiver_loop(self):
        """Fogadó ciklus (ZMQ vagy queue)"""
        poller = None
        if ZMQ_AVAILABLE and self.zmq_socket:
            try:
                poller = zmq.Poller()
                poller.register(self.zmq_socket, zmq.POLLIN)
            except Exception as e:
                print(f"🔌 Poller létrehozási hiba: {e}")
                poller = None
        
        while self.running:
            try:
                if poller and self.zmq_socket:
                    # ZMQ mód
                    try:
                        events = dict(poller.poll(100))  # 100ms timeout
                        if self.zmq_socket in events:
                            self._receive_zmq()
                    except Exception as e:
                        print(f"🔌 ZMQ poll hiba: {e}")
                        # Ha hiba van, kapcsoljunk át queue módra
                        poller = None
                else:
                    # Queue mód
                    try:
                        msg = self.message_queue.get(timeout=0.1)
                        self._process_message(msg)
                    except queue.Empty:
                        pass
            except Exception as e:
                print(f"🔌 Router hiba: {e}")
                time.sleep(0.1)
    
    def _receive_zmq(self):
        """Üzenet fogadása ZMQ-ról"""
        try:
            # ZMQ_ROUTER: [identity, delimiter, data]
            identity = self.zmq_socket.recv()
            delimiter = self.zmq_socket.recv()  # üres
            data = self.zmq_socket.recv()
            
            # Feldolgozás
            self._process_zmq_message(identity, data)
        except Exception as e:
            print(f"🔌 ZMQ receive hiba: {e}")
    
    def _process_zmq_message(self, identity: bytes, data: bytes):
        """ZMQ üzenet feldolgozása"""
        try:
            msg_str = data.decode('utf-8')
            
            # Heartbeat külön kezelés (leggyakoribb)
            if msg_str == self.PING:
                self._handle_ping(identity)
                return
            
            # KVK vagy JSON formátum
            if msg_str.startswith('{'):
                # JSON
                msg = json.loads(msg_str)
            else:
                # KVK (feltesszük)
                msg = {'type': self.MSG, 'data': msg_str}
            
            msg['_identity'] = identity
            self._process_message(msg)
            
        except Exception as e:
            print(f"🔌 Üzenet feldolgozási hiba: {e}")
    
    def _process_message(self, msg: Dict):
        """Üzenet feldolgozása (közös ZMQ és queue)"""
        if not isinstance(msg, dict):
            print(f"🔌 Érvénytelen üzenet típus: {type(msg)}")
            return
            
        msg_type = msg.get('type', self.MSG)
        
        # Handler-ek hívása
        for handler in self.handlers.get(msg_type, []):
            try:
                handler(msg)
            except Exception as e:
                print(f"🔌 Handler hiba ({msg_type}): {e}")
        
        # Általános handler
        for handler in self.handlers.get('*', []):
            try:
                handler(msg)
            except Exception as e:
                print(f"🔌 Handler hiba (*): {e}")
    
    def _handle_ping(self, identity: bytes):
        """Ping fogadása és válasz"""
        module_name = self._get_module_name(identity)
        self.last_heartbeat[module_name] = time.time()
        
        # PONG válasz
        self._send_to_identity(identity, self.PONG)
    
    def _heartbeat_check_loop(self):
        """Heartbeat ellenőrző ciklus"""
        while self.running:
            time.sleep(1.0)  # másodpercenként
            
            now = time.time()
            for module, last_seen in list(self.last_heartbeat.items()):
                if now - last_seen > self.heartbeat_timeout:
                    # Modul nem válaszol
                    self._handle_dead_module(module)
    
    def _handle_dead_module(self, module: str):
        """Nem válaszoló modul kezelése"""
        print(f"🔌 Modul nem válaszol: {module}")
        self.last_heartbeat.pop(module, None)
        
        # Esemény küldése a rendszernek
        self.scratchpad.write(self.name, 
            {'module': module, 'timeout': self.heartbeat_timeout}, 
            'module_dead'
        )
    
    def _get_module_name(self, identity: bytes) -> str:
        """Identity-ből modulnév (egyszerűsítve)"""
        try:
            return identity.decode('utf-8').split('_')[0]
        except:
            return f"unknown_{hash(identity) % 1000}"
    
    def _send_to_identity(self, identity: bytes, data: str):
        """Üzenet küldése adott identity-nek"""
        if not self.zmq_socket:
            return
        
        try:
            self.zmq_socket.send(identity, zmq.SNDMORE)
            self.zmq_socket.send(b"", zmq.SNDMORE)  # delimiter
            self.zmq_socket.send(data.encode('utf-8'))
        except Exception as e:
            print(f"🔌 Küldési hiba: {e}")
    
    # --- PUBLIKUS API (más moduloknak) ---
    
    def register_module(self, name: str, module_type: str, address: str = None):
        """
        Modul regisztrálása a routerben.
        """
        self.modules[name] = {
            'type': module_type,
            'address': address,
            'registered': time.time(),
            'last_seen': time.time()
        }
        print(f"🔌 Modul regisztrálva: {name} ({module_type})")
    
    def subscribe(self, msg_type: str, callback: Callable):
        """
        Feliratkozás üzenet típusra.
        """
        self.handlers[msg_type].append(callback)
    
    def unsubscribe(self, msg_type: str, callback: Callable):
        """
        Leiratkozás.
        """
        if callback in self.handlers[msg_type]:
            self.handlers[msg_type].remove(callback)
    
    def send(self, to: str, msg: Dict, msg_type: str = MSG):
        """
        Üzenet küldése egy modulnak.
        """
        msg['type'] = msg_type
        msg['to'] = to
        msg['from'] = 'router'
        msg['timestamp'] = time.time()
        
        if ZMQ_AVAILABLE and self.zmq_socket:
            # ZMQ küldés (identity alapján)
            identity = to.encode('utf-8')
            data = json.dumps(msg) if msg_type != self.MSG else msg.get('data', '')
            self._send_to_identity(identity, data)
        else:
            # Queue küldés
            self.message_queue.put(msg)
    
    def broadcast(self, msg: Dict, msg_type: str = MSG):
        """
        Broadcast minden modulnak.
        """
        for module in self.modules:
            self.send(module, msg, msg_type)
    
    def ping_all(self):
        """
        Minden modul pingelése.
        """
        for module in self.modules:
            self.send(module, {}, self.PING)
    
    def get_status(self) -> Dict:
        """Router státusz"""
        now = time.time()
        return {
            'running': self.running,
            'zmq_available': ZMQ_AVAILABLE,
            'zmq_connected': self.zmq_socket is not None,
            'modules': len(self.modules),
            'handlers': len(self.handlers),
            'queue_size': self.message_queue.qsize() if not ZMQ_AVAILABLE else 0,
            'heartbeats': {
                module: now - last
                for module, last in self.last_heartbeat.items()
            }
        }

# Teszt
if __name__ == "__main__":
    from scratchpad import Scratchpad
    
    s = Scratchpad()
    router = Router(s)
    
    # Indítás
    router.start()
    
    # Modul regisztráció
    router.register_module('king', 'agent')
    router.register_module('jester', 'agent')
    router.register_module('scribe', 'agent')
    
    # Feliratkozás
    def on_message(msg):
        print(f"📨 Üzenet érkezett: {msg}")
    
    router.subscribe('*', on_message)
    
    # Küldés teszt
    print("\n--- Küldési teszt ---")
    router.send('king', {'data': 'INTENT:GREET|USER:GRUMPY'})
    
    # Ping teszt
    print("\n--- Ping teszt ---")
    router.ping_all()
    
    # Várakozás a feldolgozásra
    time.sleep(1)
    
    # Státusz
    print("\n--- Router státusz ---")
    status = router.get_status()
    for k, v in status.items():
        print(f"{k}: {v}")
    
    # Leállítás
    router.stop()