"""
Router - A Vár kommunikációs idegpályája.
ZeroMQ alapú üzenetküldés a modulok között - MOST A MESSAGEBUS RÉTEG.

Topológia:
- ROUTER socket (Kernel) a központban -> MESSAGEBUS
- DEALER socket (Slotok) a moduloknál -> MESSAGEBUS
- Heartbeat: minden slot 500ms-enként PING

Internal Heartbeat Protocol (IHP):
- Kernel 500ms-enként Ping csomagot küld minden slotnak
- Ha egy slot 3 másodpercig nem válaszol, "Frozen" státusz
- Jester-Doctor riasztást kap

Backpressure Handling:
- Ha a várakozási sor megtelik, "Várj egy pillanatot" üzenet

KOMMUNIKÁCIÓ:
- Minden üzenet JSON formátumban megy
- A MessageBus kezeli a ZMQ broadcast-ot
"""

import time
import threading
import json
from typing import Dict, Any, Callable, Optional, List
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class ModuleInfo:
    """Modul információ"""
    name: str
    module_type: str
    registered: float
    last_seen: float
    status: str = "active"
    address: str = None
    
    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'type': self.module_type,
            'registered': self.registered,
            'last_seen': self.last_seen,
            'status': self.status,
            'address': self.address
        }


class Router:
    """
    Router - Üzenetközpont.
    
    A MessageBus-t használja a broadcast-hoz, de saját heartbeat és
    modulregisztráció kezeléssel.
    """
    
    # Protokoll konstansok
    PING = "PING"
    PONG = "PONG"
    MSG = "MSG"
    CMD = "CMD"
    
    # Internal Heartbeat Protocol (IHP)
    HEARTBEAT_INTERVAL = 0.5  # 500 ms
    HEARTBEAT_TIMEOUT = 3.0    # 3 másodperc
    
    def __init__(self, scratchpad, message_bus):
        self.scratchpad = scratchpad
        self.bus = message_bus
        self.name = "router"
        
        # Futás állapota
        self.running = False
        self.threads = []
        
        # Regisztrált modulok (slotok)
        self.modules: Dict[str, ModuleInfo] = {}
        
        # Heartbeat tracking
        self.last_heartbeat: Dict[str, float] = {}  # module -> timestamp
        self.heartbeat_timeout = self.HEARTBEAT_TIMEOUT
        self.heartbeat_interval = self.HEARTBEAT_INTERVAL
        
        # Frozen modulok
        self.frozen_modules: set = set()
        
        # Handler-ek (üzenet típus alapján)
        self.handlers: Dict[str, List[Callable]] = defaultdict(list)
        
        # Statisztikák
        self.stats = {
            'messages_sent': 0,
            'messages_received': 0,
            'ping_sent': 0,
            'pong_received': 0,
            'timeouts': 0,
            'frozen_events': 0,
            'modules_registered': 0,
            'modules_unregistered': 0
        }
        
        # Feliratkozás a buszra
        self.bus.subscribe(self.name, self._on_message)
        
        print("🔌 Router: Kommunikációs pálya inicializálva. MessageBus rétegen.")
    
    def _on_message(self, message: Dict):
        """
        Hallja a buszon érkező üzeneteket.
        """
        header = message.get('header', {})
        payload = message.get('payload', {})
        sender = header.get('sender', '')
        
        # Heartbeat üzenetek
        if payload.get('type') == 'heartbeat':
            self._handle_heartbeat(sender, payload)
        
        # Modul regisztráció
        elif payload.get('type') == 'module_register':
            self._handle_module_register(sender, payload)
        
        # Modul deregisztráció
        elif payload.get('type') == 'module_unregister':
            self._handle_module_unregister(sender)
        
        # Egyéb üzenetek
        else:
            self._route_message(message)
    
    def _route_message(self, message: Dict):
        """
        Üzenet továbbítása a megfelelő handler-eknek.
        """
        header = message.get('header', {})
        payload = message.get('payload', {})
        msg_type = payload.get('type', 'unknown')
        
        self.stats['messages_received'] += 1
        
        # Specifikus handler-ek
        for handler in self.handlers.get(msg_type, []):
            try:
                handler(message)
            except Exception as e:
                print(f"🔌 Handler hiba ({msg_type}): {e}")
        
        # Általános handler-ek
        for handler in self.handlers.get('*', []):
            try:
                handler(message)
            except Exception as e:
                print(f"🔌 Handler hiba (*): {e}")
    
    # ========== HEARTBEAT KEZELÉS (Internal Heartbeat Protocol) ==========
    
    def _handle_heartbeat(self, sender: str, payload: Dict):
        """
        Heartbeat üzenet fogadása.
        """
        hb_type = payload.get('heartbeat_type', '')
        
        if hb_type == 'ping':
            # Ping fogadása -> PONG válasz
            self._send_pong(sender)
            self.stats['pong_received'] += 1
        
        elif hb_type == 'pong':
            # Pong fogadása -> utolsó látogatás frissítése
            self._update_last_seen(sender)
            self.stats['pong_received'] += 1
    
    def _send_ping(self, module_name: str):
        """
        PING küldése egy modulnak.
        """
        message = {
            "header": {
                "trace_id": f"ping_{module_name}_{int(time.time())}",
                "timestamp": time.time(),
                "sender": self.name,
                "target": module_name
            },
            "payload": {
                "type": "heartbeat",
                "heartbeat_type": "ping",
                "timestamp": time.time()
            }
        }
        self.bus.send_response(message)
        self.stats['ping_sent'] += 1
    
    def _send_pong(self, module_name: str):
        """
        PONG küldése egy modulnak.
        """
        message = {
            "header": {
                "trace_id": f"pong_{module_name}_{int(time.time())}",
                "timestamp": time.time(),
                "sender": self.name,
                "target": module_name
            },
            "payload": {
                "type": "heartbeat",
                "heartbeat_type": "pong",
                "timestamp": time.time()
            }
        }
        self.bus.send_response(message)
    
    def _update_last_seen(self, module_name: str):
        """
        Utolsó látogatás frissítése.
        """
        if module_name in self.modules:
            self.modules[module_name].last_seen = time.time()
            self.last_heartbeat[module_name] = time.time()
            
            # Ha frozen volt, most újra él
            if module_name in self.frozen_modules:
                self.frozen_modules.remove(module_name)
                self.modules[module_name].status = 'active'
                self._handle_module_revived(module_name)
    
    def _heartbeat_sender_loop(self):
        """
        Heartbeat küldő ciklus (IHP).
        500ms-enként PING küldése minden regisztrált modulnak.
        """
        while self.running:
            time.sleep(self.heartbeat_interval)
            
            if not self.modules:
                continue
            
            # Minden aktív modulnak küldünk PING-et
            for module_name, module_info in list(self.modules.items()):
                if module_info.status == 'frozen':
                    continue
                
                self._send_ping(module_name)
    
    def _heartbeat_check_loop(self):
        """
        Heartbeat ellenőrző ciklus.
        Figyeli, hogy mely modulok nem válaszoltak időben.
        """
        while self.running:
            time.sleep(1.0)
            
            now = time.time()
            newly_frozen = []
            
            for module, last_seen in list(self.last_heartbeat.items()):
                if now - last_seen > self.heartbeat_timeout:
                    if module not in self.frozen_modules:
                        newly_frozen.append(module)
                        self.frozen_modules.add(module)
                        
                        if module in self.modules:
                            self.modules[module].status = 'frozen'
                        
                        self.stats['frozen_events'] += 1
                        self.stats['timeouts'] += 1
                        
                        self._handle_module_frozen(module)
            
            # Újraéledt modulok ellenőrzése (már a _update_last_seen kezeli)
    
    def _handle_module_frozen(self, module: str):
        """
        Modul frozen állapotba került.
        """
        print(f"🔌 Modul frozen: {module}")
        
        # Esemény küldése a buszon
        message = {
            "header": {
                "trace_id": f"frozen_{module}_{int(time.time())}",
                "timestamp": time.time(),
                "sender": self.name,
                "target": "kernel",
                "broadcast": True
            },
            "payload": {
                "type": "module_frozen",
                "module": module,
                "timeout": self.heartbeat_timeout
            }
        }
        self.bus.broadcast(message)
        
        self.scratchpad.write(self.name, 
            {'module': module, 'timeout': self.heartbeat_timeout, 'status': 'frozen'}, 
            'module_frozen'
        )
    
    def _handle_module_revived(self, module: str):
        """
        Modul újraéledt.
        """
        print(f"🔌 Modul újraéledt: {module}")
        
        # Esemény küldése a buszon
        message = {
            "header": {
                "trace_id": f"revived_{module}_{int(time.time())}",
                "timestamp": time.time(),
                "sender": self.name,
                "target": "kernel",
                "broadcast": True
            },
            "payload": {
                "type": "module_revived",
                "module": module
            }
        }
        self.bus.broadcast(message)
        
        self.scratchpad.write(self.name, 
            {'module': module, 'status': 'active'}, 
            'module_revived'
        )
    
    # ========== MODUL REGISZTRÁCIÓ ==========
    
    def _handle_module_register(self, sender: str, payload: Dict):
        """
        Modul regisztráció fogadása.
        """
        module_type = payload.get('module_type', 'agent')
        
        self.modules[sender] = ModuleInfo(
            name=sender,
            module_type=module_type,
            registered=time.time(),
            last_seen=time.time(),
            status='active',
            address=payload.get('address')
        )
        self.last_heartbeat[sender] = time.time()
        
        self.stats['modules_registered'] += 1
        
        print(f"🔌 Modul regisztrálva: {sender} ({module_type})")
        
        # Visszaigazolás
        response = {
            "header": {
                "trace_id": f"reg_ack_{sender}_{int(time.time())}",
                "timestamp": time.time(),
                "sender": self.name,
                "target": sender
            },
            "payload": {
                "type": "module_registered",
                "status": "ok",
                "heartbeat_interval": self.heartbeat_interval
            }
        }
        self.bus.send_response(response)
    
    def _handle_module_unregister(self, sender: str):
        """
        Modul deregisztráció fogadása.
        """
        if sender in self.modules:
            del self.modules[sender]
        if sender in self.last_heartbeat:
            del self.last_heartbeat[sender]
        if sender in self.frozen_modules:
            self.frozen_modules.remove(sender)
        
        self.stats['modules_unregistered'] += 1
        
        print(f"🔌 Modul eltávolítva: {sender}")
    
    def register_module(self, name: str, module_type: str, address: str = None):
        """
        Modul regisztráció küldése a buszon (modulok hívják).
        """
        message = {
            "header": {
                "trace_id": f"register_{name}_{int(time.time())}",
                "timestamp": time.time(),
                "sender": name,
                "target": self.name
            },
            "payload": {
                "type": "module_register",
                "module_type": module_type,
                "address": address
            }
        }
        self.bus.send_response(message)
    
    def unregister_module(self, name: str):
        """
        Modul deregisztráció küldése a buszon.
        """
        message = {
            "header": {
                "trace_id": f"unregister_{name}_{int(time.time())}",
                "timestamp": time.time(),
                "sender": name,
                "target": self.name
            },
            "payload": {
                "type": "module_unregister"
            }
        }
        self.bus.send_response(message)
    
    # ========== PUBLIKUS API (MODULOKNAK) ==========
    
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
        message = {
            "header": {
                "trace_id": f"msg_{to}_{int(time.time())}",
                "timestamp": time.time(),
                "sender": self.name,
                "target": to
            },
            "payload": {
                "type": msg_type,
                "data": msg
            }
        }
        self.bus.send_response(message)
        self.stats['messages_sent'] += 1
    
    def broadcast(self, msg: Dict, msg_type: str = MSG):
        """
        Broadcast minden modulnak.
        """
        message = {
            "header": {
                "trace_id": f"broadcast_{int(time.time())}",
                "timestamp": time.time(),
                "sender": self.name,
                "target": "all",
                "broadcast": True
            },
            "payload": {
                "type": msg_type,
                "data": msg
            }
        }
        self.bus.broadcast(message)
        self.stats['messages_sent'] += 1
    
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
        
        # Üzenet küldése a felhasználónak
        self.scratchpad.write(self.name, 
            {'message': 'Várj egy pillanatot, gondolkodom...', 'target': target},
            'backpressure'
        )
    
    # ========== INDÍTÁS ÉS LEÁLLÍTÁS ==========
    
    def start(self):
        """Router indítása"""
        self.running = True
        
        # Heartbeat küldő szál
        hb_sender = threading.Thread(target=self._heartbeat_sender_loop, daemon=True)
        hb_sender.start()
        self.threads.append(hb_sender)
        
        # Heartbeat ellenőrző szál
        hb_checker = threading.Thread(target=self._heartbeat_check_loop, daemon=True)
        hb_checker.start()
        self.threads.append(hb_checker)
        
        self.scratchpad.set_state('router_status', 'running', self.name)
        print("🔌 Router: Aktív. Figyelek a buszon.")
    
    def stop(self):
        """Router leállítása"""
        self.running = False
        
        for t in self.threads:
            t.join(timeout=1.0)
        
        self.scratchpad.set_state('router_status', 'stopped', self.name)
        print("🔌 Router: Leállt.")
    
    # ========== LEKÉRDEZÉSEK ==========
    
    def get_status(self) -> Dict:
        """Router státusz"""
        now = time.time()
        
        # Modulok állapota
        modules_status = {}
        for name, info in self.modules.items():
            last_seen = self.last_heartbeat.get(name, info.last_seen)
            modules_status[name] = {
                'type': info.module_type,
                'registered': info.registered,
                'last_seen': last_seen,
                'age': now - last_seen,
                'status': 'frozen' if name in self.frozen_modules else info.status,
                'address': info.address
            }
        
        return {
            'running': self.running,
            'modules': len(self.modules),
            'frozen_modules': list(self.frozen_modules),
            'active_modules': len(self.modules) - len(self.frozen_modules),
            'handlers': len(self.handlers),
            'stats': dict(self.stats),
            'heartbeats': modules_status
        }
    
    def get_module_info(self, module_name: str) -> Optional[Dict]:
        """Egy modul információinak lekérése"""
        if module_name in self.modules:
            info = self.modules[module_name]
            last_seen = self.last_heartbeat.get(module_name, info.last_seen)
            return {
                'name': info.name,
                'type': info.module_type,
                'registered': info.registered,
                'last_seen': last_seen,
                'status': 'frozen' if module_name in self.frozen_modules else info.status,
                'address': info.address
            }
        return None


# Teszt
if __name__ == "__main__":
    from scratchpad import Scratchpad
    from src.bus.message_bus import MessageBus
    
    s = Scratchpad()
    bus = MessageBus()
    bus.start()
    
    router = Router(s, bus)
    router.start()
    
    # Modul regisztráció teszt
    print("\n--- Modul regisztráció teszt ---")
    router.register_module('king', 'agent')
    router.register_module('jester', 'agent')
    router.register_module('scribe', 'agent')
    
    # Feliratkozás
    def on_message(msg):
        print(f"📨 Üzenet érkezett: {msg.get('header', {}).get('type', 'unknown')}")
    
    router.subscribe('*', on_message)
    
    # Küldés teszt
    print("\n--- Küldési teszt ---")
    router.send('king', {'data': 'INTENT:GREET|USER:USER'})
    
    # Ping teszt
    print("\n--- Ping teszt ---")
    router.ping_all()
    
    # Várakozás
    time.sleep(2)
    
    # Státusz
    print("\n--- Router státusz ---")
    status = router.get_status()
    for k, v in status.items():
        if k != 'heartbeats':
            print(f"{k}: {v}")
    
    print(f"\nHeartbeats: {len(status['heartbeats'])} modul")
    for name, info in status['heartbeats'].items():
        print(f"  {name}: {info['status']} (age: {info['age']:.1f}s)")
    
    router.stop()
    bus.stop()