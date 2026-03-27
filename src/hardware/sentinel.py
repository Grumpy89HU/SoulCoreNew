"""
Hardver-Sentinel - A Vár fizikai integritásának őre.

Feladata:
1. GPU állapot figyelés - hőmérséklet, VRAM használat, kihasználtság
2. Throttle-logika - ha túl meleg, lassít
3. Emergency unload - ha kritikus, modell kiürítés
4. VRAM scheduler - modellek közötti memória megosztás (Dynamic Swap)
5. Termikus és erőforrás-gazdálkodás
6. Vészhelyzeti protokoll (Blackout & Recovery)
7. Fragmentation Shield - fix memóriacím-foglalás
"""

import time
import threading
from typing import Dict, Any, List, Optional, Tuple
from collections import deque
from datetime import datetime
import json
import os
import sys
import yaml

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

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
    - Modell kiürítés (ha kell VRAM) - Dynamic Swap
    - Fragmentation Shield (fix memóriacím)
    - Trend elemzés (hőmérséklet emelkedés előrejelzés)
    """
    
    # Hőmérséklet szintek (Celsius)
    TEMP_LEVELS = {
        'normal': (0, 70),
        'warm': (70, 80),
        'hot': (80, 85),
        'critical': (85, 100)
    }
    
    # Throttle okok (NVML)
    THROTTLE_REASONS = {
        0x00000001: 'Power',
        0x00000002: 'Temperature',
        0x00000004: 'GPU Clock',
        0x00000008: 'Memory Clock',
        0x00000010: 'Processor Clock',
        0x00000020: 'VRAM',
        0x00000040: 'Power Software',
        0x00000080: 'Power Hardware',
        0x00000100: 'Current',
    }
    
    def __init__(self, scratchpad=None, config: Dict = None, config_path: str = None):
        self.scratchpad = scratchpad
        self.name = "sentinel"
        
        # Konfiguráció betöltése
        self.config = self._load_config(config, config_path)
        
        # Fordító (később állítjuk be)
        self.translator = None
        if I18N_AVAILABLE:
            self.translator = get_translator('en')
        
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
                'throttle_reasons': [],
                'status': 'unknown',
                'last_seen': time.time(),
                'history': deque(maxlen=self.config['log_history']),
                'temperature_history': deque(maxlen=30),  # 30 minta a trendhez
                'consecutive_critical': 0
            }
        
        # Modell slotok (melyik GPU-n mi fut)
        self.slots = {}  # slot_name -> {gpu_index, priority, model_name, pid, loaded_time, vram_mb}
        
        # Fix memóriacím foglalások (Fragmentation Shield)
        self.fixed_memory_allocations = {}  # slot_name -> (start_address, size)
        
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
            'check_count': 0,
            'dynamic_swap_count': 0,
            'last_dynamic_swap': None
        }
        
        # Szálkezelés
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        
        # Callback-ek (Kernel értesítéséhez)
        self.callbacks = []
        
        print("🔧 Hardver-Sentinel: Őrszem ébred.")
    
    def _load_config(self, config: Dict = None, config_path: str = None) -> Dict:
        """Konfiguráció betöltése fájlból vagy dict-ből"""
        
        # Alapértelmezett konfiguráció
        default_config = {
            'enabled': True,
            'check_interval': 2.0,
            'temp_warning': 75,
            'temp_critical': 85,
            'vram_warning': 90,
            'vram_critical': 95,
            'emergency_unload_temp': 85,
            'throttle_temp': 80,
            'throttle_factor': 0.5,
            'auto_unload_priority': 3,
            'log_history': 100,
            'enable_emergency_protocol': True,
            'recovery_after_seconds': 300,
            'max_consecutive_critical': 3,
            'enable_throttle': True,
            'enable_dynamic_swap': True,
            'enable_fragmentation_shield': True,
            'temperature_trend_window': 60,
            'temperature_rise_warning': 5,
            'vram_reserve_mb': 512,
            'model_vram_estimates': {
                # Ezek a példa értékek, a config.yaml felülírja
                'default': 2000
            }
        }
        
        # Ha van átadott config dict, azzal bővítjük
        if config:
            default_config.update(config)
        
        # Ha van config fájl, betöltjük
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    file_config = yaml.safe_load(f)
                    if file_config and 'sentinel' in file_config:
                        default_config.update(file_config['sentinel'])
                    elif file_config:
                        default_config.update(file_config)
                print(f"🔧 Sentinel: Konfiguráció betöltve: {config_path}")
            except Exception as e:
                print(f"⚠️ Sentinel: Konfiguráció betöltési hiba: {e}")
        
        # Ha nincs config_path, próbáljuk az alapértelmezett helyen
        if not config_path:
            default_paths = [
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'config.yaml'),
                os.path.join(os.getcwd(), 'config', 'config.yaml'),
                os.path.join(os.getcwd(), 'config.yaml')
            ]
            for path in default_paths:
                if os.path.exists(path):
                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            file_config = yaml.safe_load(f)
                            if file_config and 'sentinel' in file_config:
                                default_config.update(file_config['sentinel'])
                            elif file_config:
                                default_config.update(file_config)
                        print(f"🔧 Sentinel: Konfiguráció betöltve: {path}")
                        break
                    except Exception as e:
                        print(f"⚠️ Sentinel: Konfiguráció betöltési hiba {path}: {e}")
        
        return default_config
    
    def register_callback(self, callback):
        """Callback regisztrálása (pl. Kernel értesítéséhez)"""
        self.callbacks.append(callback)
    
    def _notify(self, event_type: str, data: Dict):
        """Callback-ek értesítése"""
        for cb in self.callbacks:
            try:
                cb(event_type, data)
            except Exception as e:
                print(f"⚠️ Sentinel callback hiba: {e}")
    
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
            
            if self.scratchpad:
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
        
        if self.scratchpad:
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
    
    def _get_throttle_reasons(self, handle) -> List[str]:
        """Throttle okok lekérése"""
        if not self.nvml_available:
            return []
        
        try:
            reasons = self.nvml_handle.nvmlDeviceGetThrottleReasons(handle)
            active = []
            for mask, name in self.THROTTLE_REASONS.items():
                if reasons & mask:
                    active.append(name)
            return active
        except:
            return []
    
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
                
                # Throttle okok
                throttle_reasons = self._get_throttle_reasons(handle)
                state['throttled'] = len(throttle_reasons) > 0
                state['throttle_reasons'] = throttle_reasons
                
                state['status'] = 'ok'
            else:
                # Dummy adatok (teszteléshez)
                state['temperature'] = 45
                state['vram_used'] = 2048
                state['vram_total'] = 8192
                state['vram_percent'] = 25
                state['utilization'] = 10
                state['throttled'] = False
                state['throttle_reasons'] = []
                state['status'] = 'simulated'
            
            # History
            state['history'].append({
                'time': time.time(),
                'temp': state['temperature'],
                'vram': state['vram_percent']
            })
            
            # Temperature history a trend elemzéshez
            state['temperature_history'].append({
                'time': time.time(),
                'temp': state['temperature']
            })
            
            state['last_seen'] = time.time()
            
        except Exception as e:
            state['status'] = 'error'
            print(f"🔧 Sentinel: GPU{index} hiba: {e}")
        
        return state
    
    def _check_temperature_trend(self) -> List[str]:
        """Hőmérséklet trend elemzés"""
        warnings = []
        window_seconds = self.config['temperature_trend_window']
        rise_threshold = self.config['temperature_rise_warning']
        
        for i, state in self.gpu_states.items():
            temps = list(state['temperature_history'])
            if len(temps) < 5:
                continue
            
            # Időszűrés az ablakon belül
            now = time.time()
            recent = [t for t in temps if now - t['time'] <= window_seconds]
            
            if len(recent) >= 2:
                oldest_temp = recent[0]['temp']
                newest_temp = recent[-1]['temp']
                temp_rise = newest_temp - oldest_temp
                
                if temp_rise >= rise_threshold:
                    warnings.append(f"GPU{i} hőmérséklet emelkedés: +{temp_rise:.1f}°C az utolsó {window_seconds}s alatt")
        
        return warnings
    
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
        
        # Trend elemzés
        trend_warnings = self._check_temperature_trend()
        warnings.extend(trend_warnings)
        
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
            throttling_active = any(
                g['temperature'] >= self.config['throttle_temp'] or g['throttled'] 
                for g in self.gpu_states.values()
            )
            
            if throttling_active and not self.state['throttle_active']:
                print(f"🔧 Sentinel: Throttle aktiválva (hőmérséklet vagy GPU throttle)")
                self.state['throttle_active'] = True
                self._notify('throttle_active', {'factor': self.config['throttle_factor']})
            elif not throttling_active and self.state['throttle_active']:
                print(f"🔧 Sentinel: Throttle kikapcsolva")
                self.state['throttle_active'] = False
                self._notify('throttle_inactive', {})
        
        # Dynamic Swap ellenőrzés (VRAM scheduler)
        if self.config['enable_dynamic_swap']:
            self._check_dynamic_swap()
        
        # Vészhelyzet ellenőrzés
        if self.config['enable_emergency_protocol']:
            self._check_emergency(criticals)
        
        # Állapot mentése
        self.state['warnings'] = warnings[-10:]
        
        if self.scratchpad:
            self.scratchpad.write(self.name, {
                'gpus': self.gpu_states,
                'warnings': warnings,
                'criticals': criticals,
                'throttle': self.state['throttle_active']
            }, 'hardware_status')
    
    def _get_model_vram(self, slot_name: str, model_name: str = None) -> int:
        """
        Modell VRAM igényének lekérése a konfigurációból.
        Sorrend:
        1. Ha van konkrét modell névhez beállítás, azt használjuk
        2. Ha van slot névhez beállítás, azt használjuk
        3. Alapértelmezett érték
        """
        estimates = self.config.get('model_vram_estimates', {})
        
        # 1. Konkrét modell név
        if model_name and model_name in estimates:
            return estimates[model_name]
        
        # 2. Slot név
        if slot_name in estimates:
            return estimates[slot_name]
        
        # 3. Alapértelmezett
        return estimates.get('default', 2000)
    
    def _check_dynamic_swap(self):
        """
        Dynamic Swap Logic - VRAM scheduler.
        A dokumentum 1.3 szerint:
        "Ha a King (27B) futtatásához több VRAM kell, a Kernel kiadja az EVRICT_NON_CRITICAL parancsot."
        """
        # Számoljuk a betöltött slotok VRAM igényét
        loaded_vram = 0
        critical_slots = []  # King, Queen
        non_critical_slots = []  # Jester, Scribe, stb.
        
        for slot_name, slot in self.slots.items():
            if slot.get('loaded', False):
                vram_mb = slot.get('vram_mb', self._get_model_vram(slot_name, slot.get('model_name')))
                loaded_vram += vram_mb
                
                if slot['priority'] <= 1:  # King vagy Queen
                    critical_slots.append((slot_name, vram_mb))
                else:
                    non_critical_slots.append((slot_name, vram_mb))
        
        # Szabad VRAM kiszámítása
        free_vram = self.get_free_vram()
        
        # Van elég VRAM?
        vram_reserve = self.config['vram_reserve_mb']
        
        if free_vram < vram_reserve and non_critical_slots:
            # Nincs elég VRAM -> ki kell üríteni non-critical slotokat
            print(f"🔧 Sentinel: Dynamic Swap - VRAM kritikus: {free_vram}MB szabad, {vram_reserve}MB kell")
            self.state['dynamic_swap_count'] += 1
            self.state['last_dynamic_swap'] = time.time()
            
            # Kiürítjük a non-critical slotokat (prioritás szerint csökkenő)
            for slot_name, vram_mb in sorted(non_critical_slots, key=lambda x: x[1], reverse=True):
                if free_vram >= vram_reserve:
                    break
                
                self.unload_model(slot_name, emergency=True)
                free_vram += vram_mb
                print(f"🔧 Sentinel: Dynamic Swap - Kiürítve: {slot_name} ({vram_mb}MB)")
                self._notify('dynamic_swap', {'unloaded': slot_name, 'reason': 'vram_pressure'})
    
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
                self._notify('recovery_end', {})
            return
        
        if not criticals:
            return
        
        self.state['last_emergency'] = now
        self.state['emergency_count'] += 1
        
        print(f"🔧 Sentinel: VÉSZHELYZET! {criticals}")
        self._notify('emergency', {'criticals': criticals})
        
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
        
        if self.scratchpad:
            self.scratchpad.write(self.name, 
                {'action': 'emergency_unload_all', 'reason': 'critical temperature'},
                'emergency'
            )
        
        self._notify('emergency_unload_all', {'reason': 'critical_temperature'})
        
        for slot_name in list(self.slots.keys()):
            self.unload_model(slot_name, emergency=True)
    
    def _emergency_unload_low_priority(self):
        """Alacsony prioritású modellek kiürítése"""
        print("🔧 Sentinel: VÉSZKIÜRÍTÉS: Alacsony prioritású modellek")
        
        threshold = self.config['auto_unload_priority']
        self._notify('emergency_unload_low', {'threshold': threshold})
        
        for slot_name, slot in self.slots.items():
            if slot['priority'] > threshold and slot.get('loaded', False):  # Alacsony prioritás (nagyobb szám)
                self.unload_model(slot_name, emergency=True)
    
    def _emergency_shutdown(self):
        """Vészleállás (túl sok kritikus esemény)"""
        print("🔧 Sentinel: KRITIKUS VÉSZLEÁLLÁS!")
        
        self.state['recovery_mode'] = True
        self.state['recovery_until'] = time.time() + self.config['recovery_after_seconds']
        
        if self.scratchpad:
            self.scratchpad.write(self.name, 
                {'action': 'emergency_shutdown', 'reason': 'too many critical events'},
                'emergency_shutdown'
            )
        
        self._notify('emergency_shutdown', {'recovery_until': self.state['recovery_until']})
    
    # --- FRAGMENTATION SHIELD (fix memóriacím) ---
    
    def allocate_fixed_memory(self, slot_name: str, size_mb: int, preferred_address: int = None) -> Optional[int]:
        """
        Fix memóriacím foglalása (Fragmentation Shield).
        A dokumentum 1.3 szerint:
        "A modellek betöltésekor fix memóriacím-foglalást kérünk, hogy elkerüljük a memória töredezettségét."
        
        Returns:
            Allocated address vagy None ha sikertelen
        """
        if not self.config['enable_fragmentation_shield']:
            return None
        
        # Itt lenne a valódi memóriacím foglalás
        # Jelenleg csak szimuláció
        address = preferred_address or (hash(slot_name) % (1024 * 1024 * 1024))
        
        self.fixed_memory_allocations[slot_name] = (address, size_mb)
        print(f"🔧 Sentinel: Fragmentation Shield - Fix memóriacím foglalva: {slot_name} @ {address} ({size_mb}MB)")
        
        return address
    
    def release_fixed_memory(self, slot_name: str):
        """Fix memóriacím feloldása"""
        if slot_name in self.fixed_memory_allocations:
            del self.fixed_memory_allocations[slot_name]
            print(f"🔧 Sentinel: Fragmentation Shield - Memóriacím felszabadítva: {slot_name}")
    
    # --- SLOT KEZELÉS (modellek) ---
    
    def register_slot(self, slot_name: str, priority: int, model_name: str, 
                      gpu_index: int = 0, vram_mb: int = None):
        """
        Modell slot regisztrálása.
        priority: 0 (legmagasabb) - 4 (legalacsonyabb)
        vram_mb: ha None, akkor a konfigurációból lesz kiolvasva
        """
        with self.lock:
            # VRAM igény meghatározása
            if vram_mb is None:
                vram_mb = self._get_model_vram(slot_name, model_name)
            
            self.slots[slot_name] = {
                'name': slot_name,
                'priority': priority,
                'model_name': model_name,
                'gpu_index': gpu_index,
                'loaded': False,
                'loaded_time': None,
                'pid': None,
                'vram_mb': vram_mb,
                'last_used': None
            }
            
            print(f"🔧 Sentinel: Slot regisztrálva: {slot_name} (prio:{priority}, model:{model_name}, vram:{vram_mb}MB)")
    
    def load_model(self, slot_name: str, fixed_address: int = None) -> bool:
        """
        Modell betöltése egy slotba.
        fixed_address: opcionális fix memóriacím (Fragmentation Shield)
        """
        slot = self.slots.get(slot_name)
        if not slot:
            return False
        
        # VRAM ellenőrzés
        needed_mb = slot['vram_mb']
        if not self._check_vram_available(needed_mb):
            print(f"🔧 Sentinel: Nincs elég VRAM a {slot_name} betöltéséhez (szükséges: {needed_mb}MB)")
            return False
        
        # Fragmentation Shield - fix memóriacím foglalás
        if self.config['enable_fragmentation_shield']:
            allocated_addr = self.allocate_fixed_memory(slot_name, needed_mb, fixed_address)
            if allocated_addr is None and fixed_address is not None:
                print(f"🔧 Sentinel: Fix memóriacím foglalás sikertelen: {slot_name}")
                return False
        
        # Itt történne a tényleges betöltés
        slot['loaded'] = True
        slot['loaded_time'] = time.time()
        slot['last_used'] = time.time()
        
        print(f"🔧 Sentinel: Modell betöltve: {slot_name}")
        self._notify('model_loaded', {'slot': slot_name, 'vram_mb': needed_mb})
        
        return True
    
    def unload_model(self, slot_name: str, emergency: bool = False) -> bool:
        """
        Modell kiürítése egy slotból.
        """
        slot = self.slots.get(slot_name)
        if not slot or not slot.get('loaded', False):
            return False
        
        # Fragmentation Shield - memóriacím feloldás
        if self.config['enable_fragmentation_shield']:
            self.release_fixed_memory(slot_name)
        
        # Itt történne a tényleges kiürítés
        slot['loaded'] = False
        slot['loaded_time'] = None
        
        reason = "vészhelyzet" if emergency else "normál"
        print(f"🔧 Sentinel: Modell kiürítve: {slot_name} ({reason})")
        self._notify('model_unloaded', {'slot': slot_name, 'reason': reason})
        
        return True
    
    def use_model(self, slot_name: str):
        """Modell használatának jelzése (utolsó használat frissítése)"""
        slot = self.slots.get(slot_name)
        if slot:
            slot['last_used'] = time.time()
    
    def _check_vram_available(self, needed_mb: int) -> bool:
        """
        Ellenőrzi, hogy van-e elég szabad VRAM.
        Figyelembe veszi a fenntartott memóriát (vram_reserve_mb).
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
        
        # Fenntartott memória levonása
        available = total_free - self.config['vram_reserve_mb']
        
        return available >= needed_mb
    
    def get_free_vram(self) -> int:
        """Szabad VRAM összesen (MB)"""
        if not self.nvml_available:
            return 8192  # dummy
        
        total_free = 0
        for handle in self.gpu_handles:
            try:
                memory = self.nvml_handle.nvmlDeviceGetMemoryInfo(handle)
                total_free += memory.free // 1024 // 1024
            except:
                pass
        
        return total_free
    
    def get_used_vram(self) -> int:
        """Használt VRAM összesen (MB)"""
        if not self.nvml_available:
            return 4096  # dummy
        
        total_used = 0
        for handle in self.gpu_handles:
            try:
                memory = self.nvml_handle.nvmlDeviceGetMemoryInfo(handle)
                total_used += memory.used // 1024 // 1024
            except:
                pass
        
        return total_used
    
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
                'throttled': state['throttled'],
                'throttle_reasons': state['throttle_reasons']
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
                'vram_mb': slot['vram_mb'],
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
            'dynamic_swap_count': self.state['dynamic_swap_count'],
            'check_count': self.state['check_count'],
            'slots': len(self.slots),
            'loaded_slots': sum(1 for s in self.slots.values() if s['loaded']),
            'free_vram_mb': self.get_free_vram(),
            'used_vram_mb': self.get_used_vram(),
            'fixed_allocations': len(self.fixed_memory_allocations)
        }
    
    def get_summary(self) -> str:
        """Rövid összefoglaló a Kingnek"""
        gpu_summary = []
        for i, state in self.gpu_states.items():
            gpu_summary.append(
                f"GPU{i}: {state['temperature']}°C, "
                f"VRAM: {state['vram_percent']:.0f}%, "
                f"{'🔥 THROTTLED' if state['throttled'] else '✓'}"
            )
        
        return f"Hardver: {', '.join(gpu_summary)} | Throttle: {'BE' if self.state['throttle_active'] else 'KI'}"


# Teszt
if __name__ == "__main__":
    # Mock scratchpad a teszteléshez
    class MockScratchpad:
        def set_state(self, *args, **kwargs):
            pass
        def write(self, *args, **kwargs):
            pass
    
    s = MockScratchpad()
    
    # Sentinel indítása konfigurációval
    sentinel = HardwareSentinel(s)
    sentinel.start()
    
    # Slotok regisztrálása - itt már nincs hardkódolt VRAM!
    # A VRAM értékek a config.yaml-ból vagy a default configból jönnek
    sentinel.register_slot('king', 0, 'gemma-12b')
    sentinel.register_slot('queen', 1, 'qwen-3b')
    sentinel.register_slot('jester', 2, 'tiny-llama')
    sentinel.register_slot('scribe', 3, 'phi-2')
    
    # Várunk
    time.sleep(5)
    
    # Állapot
    print("\n" + "="*50)
    print("GPU állapot:")
    for gpu in sentinel.get_gpu_status():
        print(f"  GPU{gpu['index']}: {gpu['temperature']}°C, VRAM: {gpu['vram_percent']}%, Throttled: {gpu['throttled']}")
    
    print("\nSlotok (VRAM a konfigurációból):")
    for slot in sentinel.get_slots():
        print(f"  {slot['name']}: loaded={slot['loaded']}, vram={slot['vram_mb']}MB")
    
    print(f"\nThrottle faktor: {sentinel.get_throttle_factor()}")
    print(f"Szabad VRAM: {sentinel.get_free_vram()}MB")
    print(f"Használt VRAM: {sentinel.get_used_vram()}MB")
    print(f"\nÖsszefoglaló: {sentinel.get_summary()}")
    print(f"\nTeljes állapot: {sentinel.get_state()}")
    
    sentinel.stop()