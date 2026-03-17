"""
Hardver-Sentinel - A Vár fizikai integritásának őre.

Feladata:
1. GPU állapot figyelés - hőmérséklet, VRAM használat, kihasználtság
2. Throttle-logika - ha túl meleg, lassít
3. Emergency unload - ha kritikus, modell kiürítés
4. VRAM scheduler - modellek közötti memória megosztás
5. Termikus és erőforrás-gazdálkodás
6. Vészhelyzeti protokoll (Blackout & Recovery)
"""

import time
import threading
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict
from datetime import datetime
import json

# NVIDIA Management Library (ha van)
try:
    import pynvml
    NVML_AVAILABLE = True
except ImportError:
    NVML_AVAILABLE = False
    print("⚠️ Sentinel: pynvml nem elérhető. Korlátozott módban futok.")

# Psutil (CPU, RAM)
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# i18n import (opcionális)
try:
    from src.i18n.translator import get_translator
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False

class HardwareSentinel:
    """
    Hardver őrszem - figyeli a GPU-kat, CPU-t, memóriát.
    
    Képes:
    - GPU hőmérséklet, kihasználtság, VRAM lekérdezés
    - Throttling (ha meleg, lassít)
    - Vészleállás (ha kritikus)
    - Modell kiürítés (ha kell VRAM)
    """
    
    # Hőmérséklet szintek (Celsius)
    TEMP_LEVELS = {
        'normal': (0, 70),
        'warm': (70, 80),
        'hot': (80, 85),
        'critical': (85, 100)
    }
    
    # Prioritási szintek (0 = legmagasabb)
    PRIORITIES = {
        'king': 0,        # Soha nem törölhető aktív kérés alatt
        'queen': 1,       # Logika, de kiüríthető
        'jester': 2,      # Figyelő, könnyű
        'valet': 2,       # Memória, könnyű
        'scribe': 3,      # Értelmező, könnyű
        'vision': 4       # Képfeldolgozó, nehéz
    }
    
    def __init__(self, scratchpad, config: Dict = None):
        self.scratchpad = scratchpad
        self.name = "sentinel"
        self.config = config or {}
        
        # Fordító (később állítjuk be)
        self.translator = None
        if I18N_AVAILABLE:
            self.translator = get_translator('en')
        
        # Alapértelmezett konfiguráció
        default_config = {
            'enabled': True,
            'check_interval': 2.0,           # 2 másodperc
            'temp_warning': 75,                # Figyelmeztetés °C
            'temp_critical': 85,                # Kritikus °C
            'vram_warning': 90,                 # VRAM használat % figyelmeztetés
            'vram_critical': 95,                 # VRAM használat % kritikus
            'emergency_unload_temp': 85,         # Ennél a hőmérsékletnél vészkiürítés
            'throttle_temp': 80,                  # Ennél lassít
            'throttle_factor': 0.5,                # Lassítás mértéke (50%)
            'auto_unload_priority': 3,             # Automatikus kiürítés prioritás alatt
            'log_history': 100,                    # Hány mérés maradjon meg
            'enable_emergency_protocol': True,      # Vészhelyzeti protokoll
            'recovery_after_seconds': 300,          # 5 perc után próbál újra
            'max_consecutive_critical': 3,          # 3 kritikus után vészleállás
            'enable_throttle': True                  # Throttle engedélyezése
        }
        
        for key, value in default_config.items():
            if key not in self.config:
                self.config[key] = value
        
        # NVML inicializálás
        self.nvml_available = NVML_AVAILABLE
        self.nvml_handle = None
        self.gpu_count = 0
        self.gpu_handles = []
        
        if self.nvml_available:
            try:
                pynvml.nvmlInit()
                self.nvml_handle = pynvml
                self.gpu_count = pynvml.nvmlDeviceGetCount()
                
                for i in range(self.gpu_count):
                    handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                    self.gpu_handles.append(handle)
                
                print(f"🔧 Sentinel: NVML inicializálva, {self.gpu_count} GPU található")
            except Exception as e:
                print(f"⚠️ Sentinel: NVML hiba: {e}")
                self.nvml_available = False
        
        # GPU állapotok
        self.gpu_states = {}
        for i in range(self.gpu_count):
            self.gpu_states[i] = {
                'index': i,
                'temperature': 0,
                'vram_used': 0,
                'vram_total': 0,
                'vram_percent': 0,
                'utilization': 0,
                'power': 0,
                'throttled': False,
                'status': 'unknown',
                'last_seen': time.time(),
                'history': [],
                'consecutive_critical': 0
            }
        
        # Modell slotok (melyik GPU-n mi fut)
        self.slots = {}  # slot_name -> {gpu_index, priority, model_name, pid, loaded_time}
        
        # Állapot
        self.state = {
            'status': 'idle',
            'warnings': [],
            'critical_alerts': [],
            'throttle_active': False,
            'last_emergency': None,
            'emergency_count': 0,
            'recovery_mode': False,
            'recovery_until': 0,
            'check_count': 0
        }
        
        # Szálkezelés
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        
        print("🔧 Hardver-Sentinel: Őrszem ébred.")
    
    def set_language(self, language: str):
        """Nyelv beállítása (i18n)"""
        if self.translator and I18N_AVAILABLE:
            self.translator.set_language(language)
    
    def start(self):
        """Sentinel indítása külön szálon"""
        with self.lock:
            if self.running:
                return
            
            self.running = True
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
            
            self.scratchpad.set_state('sentinel_status', 'running', self.name)
            print("🔧 Sentinel: Figyelek.")
    
    def stop(self):
        """Sentinel leállítása"""
        with self.lock:
            self.running = False
        
        if self.thread:
            self.thread.join(timeout=2.0)
        
        if self.nvml_available and self.nvml_handle:
            try:
                self.nvml_handle.nvmlShutdown()
            except:
                pass
        
        self.scratchpad.set_state('sentinel_status', 'stopped', self.name)
        print("🔧 Sentinel: Leállt.")
    
    def _run(self):
        """Fő figyelő ciklus"""
        while self.running:
            try:
                self._check_hardware()
                time.sleep(self.config['check_interval'])
            except Exception as e:
                print(f"🔧 Sentinel hiba: {e}")
                time.sleep(self.config['check_interval'] * 2)
    
    def _check_hardware(self):
        """Hardver ellenőrzés"""
        self.state['check_count'] += 1
        warnings = []
        criticals = []
        
        # GPU-k ellenőrzése
        for i, handle in enumerate(self.gpu_handles):
            gpu_state = self._check_gpu(i, handle)
            
            # Hőmérséklet ellenőrzés
            if gpu_state['temperature'] >= self.config['temp_critical']:
                criticals.append(f"GPU{i} overheat: {gpu_state['temperature']}°C")
                self.gpu_states[i]['consecutive_critical'] += 1
                self.state['critical_alerts'].append({
                    'time': time.time(),
                    'gpu': i,
                    'type': 'overheat',
                    'value': gpu_state['temperature']
                })
            elif gpu_state['temperature'] >= self.config['temp_warning']:
                warnings.append(f"GPU{i} warm: {gpu_state['temperature']}°C")
                self.gpu_states[i]['consecutive_critical'] = 0
            else:
                self.gpu_states[i]['consecutive_critical'] = 0
            
            # VRAM ellenőrzés
            if gpu_state['vram_percent'] >= self.config['vram_critical']:
                criticals.append(f"GPU{i} VRAM critical: {gpu_state['vram_percent']:.1f}%")
            elif gpu_state['vram_percent'] >= self.config['vram_warning']:
                warnings.append(f"GPU{i} VRAM high: {gpu_state['vram_percent']:.1f}%")
        
        # CPU/RAM ellenőrzés
        if PSUTIL_AVAILABLE:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            ram = psutil.virtual_memory()
            
            if cpu_percent > 90:
                warnings.append(f"CPU high: {cpu_percent}%")
            
            if ram.percent > 90:
                warnings.append(f"RAM high: {ram.percent}%")
        
        # Throttle ellenőrzés
        if self.config['enable_throttle']:
            if any(g['temperature'] >= self.config['throttle_temp'] for g in self.gpu_states.values()):
                if not self.state['throttle_active']:
                    print(f"🔧 Sentinel: Throttle aktiválva (hőmérséklet)")
                    self.state['throttle_active'] = True
            else:
                if self.state['throttle_active']:
                    print(f"🔧 Sentinel: Throttle kikapcsolva")
                    self.state['throttle_active'] = False
        
        # Vészhelyzet ellenőrzés
        if self.config['enable_emergency_protocol']:
            self._check_emergency(criticals)
        
        # Állapot mentése
        self.state['warnings'] = warnings[-10:]
        self.scratchpad.write(self.name, {
            'gpus': self.gpu_states,
            'warnings': warnings,
            'criticals': criticals,
            'throttle': self.state['throttle_active']
        }, 'hardware_status')
    
    def _check_gpu(self, index: int, handle) -> Dict:
        """Egy GPU állapotának lekérése"""
        state = self.gpu_states[index]
        
        try:
            if self.nvml_available:
                # Hőmérséklet
                temp = self.nvml_handle.nvmlDeviceGetTemperature(
                    handle, self.nvml_handle.NVML_TEMPERATURE_GPU
                )
                state['temperature'] = temp
                
                # VRAM
                memory = self.nvml_handle.nvmlDeviceGetMemoryInfo(handle)
                state['vram_used'] = memory.used // 1024 // 1024  # MB
                state['vram_total'] = memory.total // 1024 // 1024  # MB
                state['vram_percent'] = (memory.used / memory.total) * 100
                
                # Kihasználtság
                util = self.nvml_handle.nvmlDeviceGetUtilizationRates(handle)
                state['utilization'] = util.gpu
                
                # Fogyasztás
                try:
                    power = self.nvml_handle.nvmlDeviceGetPowerUsage(handle)
                    state['power'] = power / 1000.0  # mW -> W
                except:
                    state['power'] = 0
                
                state['status'] = 'ok'
            else:
                # Dummy adatok (teszteléshez)
                state['temperature'] = 45
                state['vram_used'] = 2048
                state['vram_total'] = 8192
                state['vram_percent'] = 25
                state['utilization'] = 10
                state['status'] = 'simulated'
            
            # History
            state['history'].append({
                'time': time.time(),
                'temp': state['temperature'],
                'vram': state['vram_percent']
            })
            
            # Limit history
            if len(state['history']) > self.config['log_history']:
                state['history'] = state['history'][-self.config['log_history']:]
            
            state['last_seen'] = time.time()
            
        except Exception as e:
            state['status'] = 'error'
            print(f"🔧 Sentinel: GPU{index} hiba: {e}")
        
        return state
    
    def _check_emergency(self, criticals: List[str]):
        """
        Vészhelyzet ellenőrzése és kezelése.
        - Kritikus hőmérséklet -> vészkiürítés
        - VRAM kritikus -> alacsony prioritású modellek kiürítése
        - Túl sok egymás utáni kritikus -> vészleállás
        """
        now = time.time()
        
        # Ha recovery módban vagyunk, ne csináljunk semmit
        if self.state['recovery_mode']:
            if now > self.state['recovery_until']:
                self.state['recovery_mode'] = False
                print("🔧 Sentinel: Recovery mód vége")
            return
        
        if not criticals:
            return
        
        self.state['last_emergency'] = now
        self.state['emergency_count'] += 1
        
        print(f"🔧 Sentinel: VÉSZHELYZET! {criticals}")
        
        # 1. Kritikus hőmérséklet -> minden kiürítése
        if any('overheat' in c for c in criticals):
            self._emergency_unload_all()
            
            # Ellenőrizzük, hogy túl sokszor volt-e
            max_critical = self.config['max_consecutive_critical']
            if any(g['consecutive_critical'] >= max_critical for g in self.gpu_states.values()):
                self._emergency_shutdown()
        
        # 2. VRAM kritikus -> alacsony prioritásúak kiürítése
        elif any('VRAM critical' in c for c in criticals):
            self._emergency_unload_low_priority()
    
    def _emergency_unload_all(self):
        """Minden modell kiürítése (vészhelyzet)"""
        print("🔧 Sentinel: VÉSZKIÜRÍTÉS: Minden modell kiürítve")
        
        # Értesítés a Kingnek
        self.scratchpad.write(self.name, 
            {'action': 'emergency_unload_all', 'reason': 'critical temperature'},
            'emergency'
        )
        
        # Itt történne a modellek tényleges kiürítése
        for slot_name, slot in self.slots.items():
            self.unload_model(slot_name, emergency=True)
    
    def _emergency_unload_low_priority(self):
        """Alacsony prioritású modellek kiürítése"""
        print("🔧 Sentinel: VÉSZKIÜRÍTÉS: Alacsony prioritású modellek")
        
        threshold = self.config['auto_unload_priority']
        
        for slot_name, slot in self.slots.items():
            if slot['priority'] > threshold:  # Alacsony prioritás (nagyobb szám)
                self.unload_model(slot_name, emergency=True)
    
    def _emergency_shutdown(self):
        """Vészleállás (túl sok kritikus esemény)"""
        print("🔧 Sentinel: KRITIKUS VÉSZLEÁLLÁS!")
        
        self.state['recovery_mode'] = True
        self.state['recovery_until'] = time.time() + self.config['recovery_after_seconds']
        
        # Értesítés a Kingnek
        self.scratchpad.write(self.name, 
            {'action': 'emergency_shutdown', 'reason': 'too many critical events'},
            'emergency_shutdown'
        )
    
    # --- SLOT KEZELÉS (modellek) ---
    
    def register_slot(self, slot_name: str, priority: int, model_name: str, gpu_index: int = 0):
        """
        Modell slot regisztrálása.
        priority: 0 (legmagasabb) - 4 (legalacsonyabb)
        """
        with self.lock:
            self.slots[slot_name] = {
                'name': slot_name,
                'priority': priority,
                'model_name': model_name,
                'gpu_index': gpu_index,
                'loaded': False,
                'loaded_time': None,
                'pid': None,
                'vram_estimate': 0,  # MB
                'last_used': None
            }
            
            print(f"🔧 Sentinel: Slot regisztrálva: {slot_name} (prio:{priority})")
    
    def load_model(self, slot_name: str) -> bool:
        """
        Modell betöltése egy slotba.
        """
        slot = self.slots.get(slot_name)
        if not slot:
            return False
        
        # VRAM ellenőrzés (ha van)
        if not self._check_vram_available(slot.get('vram_estimate', 2048)):
            print(f"🔧 Sentinel: Nincs elég VRAM a {slot_name} betöltéséhez")
            return False
        
        # Itt történne a tényleges betöltés
        slot['loaded'] = True
        slot['loaded_time'] = time.time()
        slot['last_used'] = time.time()
        
        print(f"🔧 Sentinel: Modell betöltve: {slot_name}")
        return True
    
    def unload_model(self, slot_name: str, emergency: bool = False) -> bool:
        """
        Modell kiürítése egy slotból.
        """
        slot = self.slots.get(slot_name)
        if not slot or not slot['loaded']:
            return False
        
        # Itt történne a tényleges kiürítés
        slot['loaded'] = False
        
        reason = "vészhelyzet" if emergency else "normál"
        print(f"🔧 Sentinel: Modell kiürítve: {slot_name} ({reason})")
        
        return True
    
    def use_model(self, slot_name: str):
        """Modell használatának jelzése (utolsó használat frissítése)"""
        slot = self.slots.get(slot_name)
        if slot:
            slot['last_used'] = time.time()
    
    def _check_vram_available(self, needed_mb: int) -> bool:
        """
        Ellenőrzi, hogy van-e elég szabad VRAM.
        """
        if not self.nvml_available:
            return True
        
        total_free = 0
        for i, handle in enumerate(self.gpu_handles):
            try:
                memory = self.nvml_handle.nvmlDeviceGetMemoryInfo(handle)
                free_mb = memory.free // 1024 // 1024
                total_free += free_mb
            except:
                pass
        
        return total_free >= needed_mb
    
    # --- THROTTLE KEZELÉS ---
    
    def get_throttle_factor(self) -> float:
        """
        Throttle faktor lekérése (King használhatja a generálás sebességéhez).
        1.0 = normál, 0.5 = fél sebesség, 0.0 = leállás
        """
        if self.state['recovery_mode']:
            return 0.0
        
        if self.state['throttle_active']:
            return self.config['throttle_factor']
        
        # Ha kritikus, teljes leállás
        if self.state['critical_alerts']:
            return 0.0
        
        return 1.0
    
    def is_throttled(self) -> bool:
        """Visszaadja, hogy throttling van-e"""
        return self.state['throttle_active']
    
    def get_recommended_batch_size(self, original: int) -> int:
        """
        Throttling esetén kisebb batch méret javaslata.
        """
        if self.state['throttle_active']:
            return max(1, original // 2)
        return original
    
    # --- LEKÉRDEZÉSEK ---
    
    def get_gpu_status(self) -> List[Dict]:
        """GPU állapotok lekérése (UI-nak)"""
        return [
            {
                'index': i,
                'temperature': state['temperature'],
                'vram_used': state['vram_used'],
                'vram_total': state['vram_total'],
                'vram_percent': round(state['vram_percent'], 1),
                'utilization': state['utilization'],
                'status': state['status'],
                'throttled': state['throttled']
            }
            for i, state in self.gpu_states.items()
        ]
    
    def get_slots(self) -> List[Dict]:
        """Slotok lekérése"""
        return [
            {
                'name': slot['name'],
                'priority': slot['priority'],
                'model': slot['model_name'],
                'loaded': slot['loaded'],
                'last_used': datetime.fromtimestamp(slot['last_used']).isoformat() if slot['last_used'] else None
            }
            for slot in self.slots.values()
        ]
    
    def get_state(self) -> Dict:
        """Állapot lekérése"""
        return {
            'status': self.state['status'],
            'gpu_count': self.gpu_count,
            'nvml_available': self.nvml_available,
            'throttle_active': self.state['throttle_active'],
            'throttle_factor': self.get_throttle_factor(),
            'recovery_mode': self.state['recovery_mode'],
            'warnings': self.state['warnings'],
            'critical_alerts': len(self.state['critical_alerts']),
            'emergency_count': self.state['emergency_count'],
            'check_count': self.state['check_count'],
            'slots': len(self.slots),
            'loaded_slots': sum(1 for s in self.slots.values() if s['loaded'])
        }

# Teszt
if __name__ == "__main__":
    from scratchpad import Scratchpad
    
    s = Scratchpad()
    sentinel = HardwareSentinel(s)
    sentinel.start()
    
    # Slotok regisztrálása
    sentinel.register_slot('king', 0, 'gemma-12b')
    sentinel.register_slot('queen', 1, 'qwen-3b')
    sentinel.register_slot('jester', 2, 'tiny-llama')
    
    # Várunk
    time.sleep(5)
    
    # Állapot
    print("\n--- GPU állapot ---")
    for gpu in sentinel.get_gpu_status():
        print(f"GPU{gpu['index']}: {gpu['temperature']}°C, VRAM: {gpu['vram_percent']}%")
    
    print("\n--- Slotok ---")
    for slot in sentinel.get_slots():
        print(f"{slot['name']}: {slot['loaded']}")
    
    print(f"\nThrottle faktor: {sentinel.get_throttle_factor()}")
    
    sentinel.stop()