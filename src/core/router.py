"""
Router - A Vár kommunikációs idegpályája.
ZeroMQ alapú üzenetküldés a modulok között.

Topológia:
- ROUTER socket (Kernel) a központban
- DEALER socket (Slotok) a moduloknál
- Heartbeat: minden slot 500ms-enként PING

Internal Heartbeat Protocol (IHP):
- Kernel 500ms-enként Ping csomagot küld minden slotnak
- Ha egy slot 3 másodpercig nem válaszol, "Frozen" státusz
- Jester-Doctor riasztást kap

Backpressure Handling:
- Ha a várakozási sor megtelik, "Várj egy pillanatot" üzenet
"""

import time
import threading
import json
import queue
from typing import Dict, Any, Callable, Optional, List
from collections import defaultdict
from datetime import datetime

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
    
    # Internal Heartbeat Protocol (IHP)
    HEARTBEAT_INTERVAL = 0.5  # 500 ms
    HEARTBEAT_TIMEOUT = 3.0    # 3 másodperc
    
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
        self.modules = {}  # name -> {type, address, last_seen, status, queue_size}
        
        # Heartbeat tracking
        self.last_heartbeat = {}  # module -> timestamp
        self.heartbeat_timeout = self.HEARTBEAT_TIMEOUT
        self.heartbeat_interval = self.HEARTBEAT_INTERVAL
        
        # Frozen modulok (nem válaszolnak)
        self.frozen_modules = set()  # module name
        
        # Queue fallback (ha nincs ZMQ)
        self.message_queue = queue.Queue(maxsize=1000)
        self.handlers = defaultdict(list)  # message_type -> [callbacks]
        
        # Statisztikák
        self.stats = {
            'messages_sent': 0,
            'messages_received': 0,
            'ping_sent': 0,
            'pong_received': 0,
            'timeouts': 0,
            'queue_full_events': 0,
            'frozen_events': 0
        }
        
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
        
        # Heartbeat küldő szál indítása (IHP)
        hb_sender = threading.Thread(target=self._heartbeat_sender_loop, daemon=True)
        hb_sender.start()
        self.threads.append(hb_sender)
        
        # Heartbeat ellenőrző szál indítása (frozen detektálás)
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
            
            # Beállítások a latency csökkentéséhez
            self.zmq_socket.setsockopt(zmq.LINGER, 0)
            self.zmq_socket.setsockopt(zmq.SNDHWM, 1000)  # Küldési queue méret
            self.zmq_socket.setsockopt(zmq.RCVHWM, 1000)  # Fogadási queue méret
            
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
                self.stats['pong_received'] += 1
                return
            elif msg_str == self.PONG:
                # PONG fogadása (válasz a saját PING-ünkre)
                self._handle_pong(identity)
                self.stats['pong_received'] += 1
                return
            
            # KVK vagy JSON formátum
            if msg_str.startswith('{'):
                # JSON
                msg = json.loads(msg_str)
            else:
                # KVK (feltesszük)
                msg = {'type': self.MSG, 'data': msg_str}
            
            msg['_identity'] = identity
            msg['_received_at'] = time.time()
            self._process_message(msg)
            self.stats['messages_received'] += 1
            
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
    
    # --- HEARTBEAT KEZELÉS (Internal Heartbeat Protocol) ---
    
    def _heartbeat_sender_loop(self):
        """
        Heartbeat küldő ciklus (IHP).
        500ms-enként PING küldése minden regisztrált modulnak.
        """
        while self.running:
            time.sleep(self.heartbeat_interval)
            
            if not self.modules:
                continue
            
            # Minden modulnak küldünk PING-et
            for module_name, module_info in list(self.modules.items()):
                if module_info.get('status') == 'frozen':
                    # Frozen modulnak nem küldünk PING-et
                    continue
                
                self._send_ping(module_name)
                self.stats['ping_sent'] += 1
    
    def _heartbeat_check_loop(self):
        """
        Heartbeat ellenőrző ciklus.
        Figyeli, hogy mely modulok nem válaszoltak időben.
        """
        while self.running:
            time.sleep(1.0)  # másodpercenként
            
            now = time.time()
            newly_frozen = []
            
            for module, last_seen in list(self.last_heartbeat.items()):
                if now - last_seen > self.heartbeat_timeout:
                    # Modul nem válaszol
                    if module not in self.frozen_modules:
                        newly_frozen.append(module)
                        self.frozen_modules.add(module)
                        
                        # Modul státusz frissítése
                        if module in self.modules:
                            self.modules[module]['status'] = 'frozen'
                        
                        self.stats['frozen_events'] += 1
                        self.stats['timeouts'] += 1
                        
                        # Esemény küldése a rendszernek (Jester-Doctor riasztás)
                        self._handle_module_frozen(module)
            
            # Újraéledt modulok ellenőrzése
            for module in list(self.frozen_modules):
                if module in self.last_heartbeat:
                    last_seen = self.last_heartbeat[module]
                    if now - last_seen <= self.heartbeat_timeout:
                        # Újra válaszol
                        self.frozen_modules.remove(module)
                        if module in self.modules:
                            self.modules[module]['status'] = 'active'
                        
                        # Esemény küldése a rendszernek
                        self._handle_module_revived(module)
    
    def _send_ping(self, module_name: str):
        """PING küldése egy modulnak"""
        self.send(module_name, {}, self.PING)
    
    def _handle_ping(self, identity: bytes):
        """Ping fogadása és válasz"""
        module_name = self._get_module_name(identity)
        
        # Utolsó látogatás frissítése
        self.last_heartbeat[module_name] = time.time()
        
        # Ha frozen volt, most újra él
        if module_name in self.frozen_modules:
            self.frozen_modules.remove(module_name)
            if module_name in self.modules:
                self.modules[module_name]['status'] = 'active'
        
        # PONG válasz
        self._send_to_identity(identity, self.PONG)
    
    def _handle_pong(self, identity: bytes):
        """PONG fogadása (válasz a saját PING-ünkre)"""
        module_name = self._get_module_name(identity)
        
        # Utolsó látogatás frissítése
        self.last_heartbeat[module_name] = time.time()
        
        # Ha frozen volt, most újra él
        if module_name in self.frozen_modules:
            self.frozen_modules.remove(module_name)
            if module_name in self.modules:
                self.modules[module_name]['status'] = 'active'
    
    def _handle_module_frozen(self, module: str):
        """Modul frozen állapotba került"""
        print(f"🔌 Modul frozen: {module}")
        
        # Esemény küldése a rendszernek
        self.scratchpad.write(self.name, 
            {'module': module, 'timeout': self.heartbeat_timeout, 'status': 'frozen'}, 
            'module_frozen'
        )
    
    def _handle_module_revived(self, module: str):
        """Modul újraéledt"""
        print(f"🔌 Modul újraéledt: {module}")
        
        # Esemény küldése a rendszernek
        self.scratchpad.write(self.name, 
            {'module': module, 'status': 'active'}, 
            'module_revived'
        )
    
    def _get_module_name(self, identity: bytes) -> str:
        """Identity-ből modulnév (egyszerűsítve)"""
        try:
            name = identity.decode('utf-8').split('_')[0]
            # Ha nincs a modulok között, akkor generálunk egy nevet
            if name not in self.modules:
                return f"unknown_{hash(identity) % 1000}"
            return name
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
            self.stats['messages_sent'] += 1
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
            'last_seen': time.time(),
            'status': 'active',
            'queue_size': 0
        }
        self.last_heartbeat[name] = time.time()
        print(f"🔌 Modul regisztrálva: {name} ({module_type})")
    
    def unregister_module(self, name: str):
        """Modul eltávolítása"""
        if name in self.modules:
            del self.modules[name]
        if name in self.last_heartbeat:
            del self.last_heartbeat[name]
        if name in self.frozen_modules:
            self.frozen_modules.remove(name)
        print(f"🔌 Modul eltávolítva: {name}")
    
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
        msg['from'] = self.name
        msg['timestamp'] = time.time()
        
        if ZMQ_AVAILABLE and self.zmq_socket and to in self.modules:
            # ZMQ küldés (identity alapján)
            identity = to.encode('utf-8')
            
            if msg_type == self.MSG and 'data' in msg:
                data = msg.get('data', '')
            else:
                data = json.dumps(msg)
            
            self._send_to_identity(identity, data)
        else:
            # Queue küldés
            try:
                self.message_queue.put(msg, timeout=1.0)
            except queue.Full:
                # Backpressure: tele a sor
                self.stats['queue_full_events'] += 1
                self._handle_backpressure(to)
    
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
            self._send_ping(module)
    
    def _handle_backpressure(self, target: str):
        """
        Backpressure kezelés: ha tele a sor, "Várj egy pillanatot" üzenet.
        """
        print(f"🔌 Backpressure: {target} felé a sor tele")
        
        # Üzenet küldése a felhasználónak (ha van Scribe)
        self.scratchpad.write(self.name, 
            {'message': 'Várj egy pillanatot, gondolkodom...', 'target': target},
            'backpressure'
        )
    
    # --- LEKÉRDEZÉSEK ---
    
    def get_status(self) -> Dict:
        """Router státusz"""
        now = time.time()
        return {
            'running': self.running,
            'zmq_available': ZMQ_AVAILABLE,
            'zmq_connected': self.zmq_socket is not None,
            'modules': len(self.modules),
            'frozen_modules': list(self.frozen_modules),
            'active_modules': len(self.modules) - len(self.frozen_modules),
            'handlers': len(self.handlers),
            'queue_size': self.message_queue.qsize() if not ZMQ_AVAILABLE else 0,
            'queue_maxsize': self.message_queue.maxsize,
            'stats': dict(self.stats),
            'heartbeats': {
                module: {
                    'last_seen': last,
                    'age': now - last,
                    'status': 'frozen' if module in self.frozen_modules else 'active'
                }
                for module, last in self.last_heartbeat.items()
            }
        }
    
    def get_module_info(self, module_name: str) -> Optional[Dict]:
        """Egy modul információinak lekérése"""
        return self.modules.get(module_name)

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
        print(f"📨 Üzenet érkezett: {msg.get('type')} - {msg.get('data', '')[:50]}")
    
    router.subscribe('*', on_message)
    
    # Küldés teszt
    print("\n--- Küldési teszt ---")
    router.send('king', {'data': 'INTENT:GREET|USER:USER'})
    
    # Ping teszt
    print("\n--- Ping teszt ---")
    router.ping_all()
    
    # Várakozás a feldolgozásra
    time.sleep(2)
    
    # Státusz
    print("\n--- Router státusz ---")
    status = router.get_status()
    for k, v in status.items():
        if k != 'heartbeats' and k != 'stats':
            print(f"{k}: {v}")
    
    print(f"\nHeartbeats: {len(status['heartbeats'])} modul")
    print(f"Statisztikák: Ping elküldve: {status['stats']['ping_sent']}")
    
    # Leállítás
    router.stop()