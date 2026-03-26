"""
Fekete Doboz (Black Box) - A rendszer naplózó és debug modulja.

Feladata:
1. Minden esemény naplózása - ki, mit, mikor
2. Token szintű visszajátszás - látni, hogy mit gondolt a modell
3. Hibakeresés - ha valami elromlik, vissza lehet nézni
4. Teljesítmény elemzés - válaszidők, tokenek száma
5. Playback funkció - visszajátszás idővonalon
"""

import time
import json
import os
import threading
import gzip
import uuid
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, Union
from pathlib import Path
from collections import defaultdict, deque
import hashlib

# i18n import (opcionális)
try:
    from src.i18n.translator import get_translator
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False


class BlackBox:
    """
    Fekete Doboz - mindent rögzít, semmit sem felejt.
    
    Képes:
    - Események naplózása (strukturált formátumban)
    - Visszajátszás (időpont alapján)
    - Token szintű nyomon követés
    - Teljesítmény statisztikák
    - Hibakeresés
    """
    
    # Esemény típusok
    EVENT_TYPES = {
        'system': 0,      # Rendszer események (indulás, leállás)
        'user': 1,        # Felhasználói üzenet
        'king': 2,        # King válasz
        'queen': 3,       # Queen gondolat
        'jester': 4,      # Jester megjegyzés
        'scribe': 5,      # Scribe intent
        'valet': 6,       # Valet kontextus
        'heartbeat': 7,   # Heartbeat esemény
        'hardware': 8,    # Hardver állapot
        'error': 9,       # Hiba
        'warning': 10,    # Figyelmeztetés
        'debug': 11,      # Debug üzenet
        'trace': 12,      # Nyomkövetés (token szint)
        'performance': 13 # Teljesítmény adat
    }
    
    def __init__(self, scratchpad, config: Dict = None):
        self.scratchpad = scratchpad
        self.name = "blackbox"
        self.config = config or {}
        
        # Fordító
        self.translator = None
        if I18N_AVAILABLE:
            self.translator = get_translator('en')
        
        # Alapértelmezett konfiguráció
        default_config = {
            'enabled': True,
            'log_dir': 'logs',
            'max_log_size': 100 * 1024 * 1024,  # 100 MB
            'max_log_age': 30,  # nap
            'compress': True,
            'log_level': 'info',
            'trace_token_level': False,
            'buffer_size': 10000,
            'auto_flush': True,
            'flush_interval': 5.0,
            'include_payload': True,
            'anonymize': False,
            'enable_playback': True,
            'max_playback_speed': 10,
            'quantum_logging': False,
            'retention_days': 30,
            'watchdog_interval': 60,  # másodperc
            'watchdog_threshold_errors': 10,  # hiba küszöb
            'watchdog_threshold_time': 300    # 5 perc
        }
        
        for key, value in default_config.items():
            if key not in self.config:
                self.config[key] = value
        
        # Napló mappa
        self.log_dir = Path(self.config['log_dir'])
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Aktuális naplófájl
        self.current_log = None
        self.current_log_path = None
        self.current_log_size = 0
        self.current_log_date = datetime.now().date()
        
        # Buffer
        self.buffer = deque(maxlen=self.config['buffer_size'])
        
        # Indexek
        self.index_by_trace = defaultdict(list)
        self.index_by_type = defaultdict(list)
        self.index_by_time = []
        self.index_by_module = defaultdict(list)
        self.index_by_level = defaultdict(list)
        
        # Visszajátszás
        self.playback_state = {
            'active': False,
            'speed': 1.0,
            'start_time': None,
            'current_position': None,
            'events': [],
            'subscribers': []
        }
        
        # Watchdog
        self.watchdog_last_check = time.time()
        self.watchdog_error_count = 0
        self.watchdog_warning_count = 0
        
        # Statisztikák
        self.stats = {
            'total_events': 0,
            'events_by_type': defaultdict(int),
            'events_by_level': defaultdict(int),
            'avg_response_time': 0,
            'total_tokens': 0,
            'errors': 0,
            'warnings': 0,
            'start_time': time.time(),
            'last_flush': time.time(),
            'log_files': 0,
            'disk_usage': 0,
            'watchdog_triggered': 0
        }
        
        # Szálkezelés
        self.running = False
        self.thread = None
        self.watchdog_thread = None
        self.lock = threading.RLock()
        
        # Régi log fájlok törlése
        self._cleanup_old_logs()
        
        print("📼 Fekete Doboz: Mindent rögzítek.")
    
    def set_language(self, language: str):
        if self.translator and I18N_AVAILABLE:
            self.translator.set_language(language)
    
    def start(self):
        with self.lock:
            if self.running:
                return
            
            self.running = True
            self._rotate_log()
            
            if self.config['auto_flush']:
                self.thread = threading.Thread(target=self._flush_loop, daemon=True)
                self.thread.start()
            
            # Watchdog szál
            self.watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True)
            self.watchdog_thread.start()
            
            self.log(
                event_type='system',
                source='blackbox',
                data={'action': 'start', 'config': self.config},
                level='info'
            )
            
            self.scratchpad.set_state('blackbox_status', 'running', self.name)
            print("📼 Fekete Doboz: Rögzítek.")
    
    def stop(self):
        with self.lock:
            self.running = False
        
        self.log(
            event_type='system',
            source='blackbox',
            data={'action': 'stop', 'uptime': time.time() - self.stats['start_time']},
            level='info'
        )
        
        self.flush()
        
        if self.thread:
            self.thread.join(timeout=2.0)
        
        if self.watchdog_thread:
            self.watchdog_thread.join(timeout=2.0)
        
        if self.current_log:
            self.current_log.close()
        
        self.scratchpad.set_state('blackbox_status', 'stopped', self.name)
        print("📼 Fekete Doboz: Leállt.")
    
    # ========== NAPLÓZÁS ==========
    
    def log(self, event_type: str, source: str, data: Any, level: str = 'info', trace_id: str = None):
        """Esemény naplózása"""
        if not self.config['enabled']:
            return
        
        # Szint ellenőrzés
        log_levels = {'debug': 0, 'info': 1, 'warning': 2, 'error': 3}
        config_level = log_levels.get(self.config['log_level'], 1)
        event_level = log_levels.get(level, 1)
        
        if event_level < config_level:
            return
        
        # Adat tisztítás
        if self.config['anonymize']:
            data = self._anonymize(data)
        
        if not trace_id:
            trace_id = self._generate_trace_id()
        
        event = {
            'id': self._generate_event_id(),
            'timestamp': time.time(),
            'datetime': datetime.now().isoformat(),
            'type': event_type,
            'type_code': self.EVENT_TYPES.get(event_type, 99),
            'source': source,
            'level': level,
            'trace_id': trace_id,
            'data': data if self.config['include_payload'] else None
        }
        
        with self.lock:
            self.buffer.append(event)
            self.index_by_trace[trace_id].append(event)
            self.index_by_type[event_type].append(event)
            self.index_by_time.append(event)
            self.index_by_module[source].append(event)
            self.index_by_level[level].append(event)
            
            self.stats['total_events'] += 1
            self.stats['events_by_type'][event_type] += 1
            self.stats['events_by_level'][level] += 1
            
            if level == 'error':
                self.stats['errors'] += 1
                self.watchdog_error_count += 1
            elif level == 'warning':
                self.stats['warnings'] += 1
                self.watchdog_warning_count += 1
            
            # Token számlálás
            if event_type == 'king' and isinstance(data, dict):
                if 'tokens_used' in data:
                    self.stats['total_tokens'] += data['tokens_used']
                elif 'response' in data and isinstance(data['response'], str):
                    self.stats['total_tokens'] += len(data['response'].split())
            
            # Válaszidő
            if event_type == 'king' and isinstance(data, dict) and 'response_time_ms' in data:
                rt = data['response_time_ms'] / 1000.0
                if self.stats['avg_response_time'] == 0:
                    self.stats['avg_response_time'] = rt
                else:
                    self.stats['avg_response_time'] = self.stats['avg_response_time'] * 0.9 + rt * 0.1
        
        if len(self.buffer) >= self.config['buffer_size']:
            self.flush()
    
    def _generate_event_id(self) -> str:
        return f"{int(time.time() * 1000)}_{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}"
    
    def _generate_trace_id(self) -> str:
        return f"trace_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    
    def _anonymize(self, data: Any) -> Any:
        """Személyes adatok elrejtése"""
        if not data:
            return data
        
        if isinstance(data, dict):
            sensitive_keys = ['user', 'name', 'email', 'phone', 'address', 'password', 'token', 'api_key']
            result = {}
            for k, v in data.items():
                if any(s in k.lower() for s in sensitive_keys):
                    result[k] = '[REDACTED]'
                else:
                    result[k] = self._anonymize(v)
            return result
        
        if isinstance(data, str):
            data = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '[EMAIL]', data)
            data = re.sub(r'(\+?[0-9]{1,3}[ -]?)?[0-9]{2,4}[ -]?[0-9]{3,4}[ -]?[0-9]{3,4}', '[PHONE]', data)
            data = re.sub(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', '[IP]', data)
            return data
        
        if isinstance(data, list):
            return [self._anonymize(item) for item in data]
        
        return data
    
    # ========== FÁJL KEZELÉS ==========
    
    def _rotate_log(self):
        """Naplófájl rotálása"""
        now = datetime.now()
        
        if now.date() != self.current_log_date and self.current_log:
            self.current_log.close()
        
        if not self.current_log or now.date() != self.current_log_date:
            log_filename = f"blackbox_{now.strftime('%Y%m%d_%H%M%S')}.log"
            if self.config['compress']:
                log_filename += '.gz'
            
            log_path = self.log_dir / log_filename
            
            try:
                if self.config['compress']:
                    self.current_log = gzip.open(log_path, 'wt', encoding='utf-8')
                else:
                    self.current_log = open(log_path, 'w', encoding='utf-8')
                
                self.current_log_path = log_path
                self.current_log_size = 0
                self.current_log_date = now.date()
                self.stats['log_files'] += 1
                
                self._cleanup_old_logs()
                
            except Exception as e:
                print(f"📼 Rotálási hiba: {e}")
    
    def _cleanup_old_logs(self):
        """Régi naplófájlok törlése"""
        try:
            now = time.time()
            max_age = self.config['max_log_age'] * 86400
            
            total_size = 0
            for f in self.log_dir.glob('blackbox_*.log*'):
                total_size += f.stat().st_size
                if now - f.stat().st_mtime > max_age:
                    f.unlink()
            
            self.stats['disk_usage'] = total_size
            
        except Exception as e:
            print(f"📼 Takarítási hiba: {e}")
    
    def _flush_loop(self):
        """Automatikus kiírás"""
        while self.running:
            time.sleep(self.config['flush_interval'])
            self.flush()
    
    def flush(self):
        """Buffer kiírása fájlba"""
        with self.lock:
            if not self.buffer:
                return
            
            if not self.current_log:
                self._rotate_log()
                if not self.current_log:
                    return
            
            try:
                self._rotate_log()
                
                while self.buffer:
                    event = self.buffer.popleft()
                    line = json.dumps(event, ensure_ascii=False) + '\n'
                    self.current_log.write(line)
                    self.current_log_size += len(line.encode('utf-8'))
                
                self.current_log.flush()
                self.stats['last_flush'] = time.time()
                
                if self.current_log_size > self.config['max_log_size']:
                    self.current_log.close()
                    self.current_log = None
                    self._rotate_log()
                    
            except Exception as e:
                print(f"📼 Kiírási hiba: {e}")
    
    # ========== WATCHDOG ==========
    
    def _watchdog_loop(self):
        """Watchdog ciklus - figyeli a hibákat"""
        while self.running:
            time.sleep(self.config['watchdog_interval'])
            
            if self.watchdog_error_count > self.config['watchdog_threshold_errors']:
                self.log(
                    event_type='warning',
                    source='blackbox',
                    data={
                        'message': f'High error rate detected',
                        'error_count': self.watchdog_error_count,
                        'threshold': self.config['watchdog_threshold_errors']
                    },
                    level='warning'
                )
                self.stats['watchdog_triggered'] += 1
                self.watchdog_error_count = 0
    
    def reset_watchdog(self):
        """Watchdog számlálók nullázása"""
        self.watchdog_error_count = 0
        self.watchdog_warning_count = 0
    
    # ========== VISSZAJÁTSZÁS ==========
    
    def replay(self, start_time: float = None, end_time: float = None, 
               trace_id: str = None, event_type: str = None, 
               source: str = None, level: str = None,
               speed: float = 1.0, limit: int = None) -> List[Dict]:
        """Események visszajátszása"""
        with self.lock:
            if trace_id:
                events = self.index_by_trace.get(trace_id, [])
            elif event_type:
                events = self.index_by_type.get(event_type, [])
            elif source:
                events = self.index_by_module.get(source, [])
            elif level:
                events = self.index_by_level.get(level, [])
            else:
                events = list(self.index_by_time)
            
            # Időszűrés
            if start_time is not None or end_time is not None:
                filtered = []
                for e in events:
                    t = e['timestamp']
                    if start_time is not None and t < start_time:
                        continue
                    if end_time is not None and t > end_time:
                        continue
                    filtered.append(e)
                events = filtered
            
            # Limit
            if limit:
                events = events[-limit:] if len(events) > limit else events
            
            # Sebesség
            if speed != 1.0 and self.config['enable_playback']:
                speed = min(speed, self.config['max_playback_speed'])
                self.playback_state['speed'] = speed
            
            return events
    
    def start_playback(self, events: List[Dict], speed: float = 1.0):
        """Visszajátszás indítása"""
        self.playback_state['active'] = True
        self.playback_state['speed'] = min(speed, self.config['max_playback_speed'])
        self.playback_state['start_time'] = time.time()
        self.playback_state['events'] = events
        self.playback_state['current_position'] = 0
        
        for callback in self.playback_state['subscribers']:
            try:
                callback('start', self.playback_state)
            except:
                pass
    
    def stop_playback(self):
        """Visszajátszás leállítása"""
        self.playback_state['active'] = False
        self.playback_state['current_position'] = None
        
        for callback in self.playback_state['subscribers']:
            try:
                callback('stop', self.playback_state)
            except:
                pass
    
    def subscribe_playback(self, callback: Callable):
        """Feliratkozás visszajátszási eseményekre"""
        self.playback_state['subscribers'].append(callback)
    
    def get_trace(self, trace_id: str) -> List[Dict]:
        """Egy teljes nyomkövetés lekérése"""
        return self.replay(trace_id=trace_id)
    
    def get_conversation(self, trace_id: str = None, limit: int = 50) -> List[Dict]:
        """Beszélgetés lekérése (user + king)"""
        if trace_id:
            events = self.get_trace(trace_id)
        else:
            events = self.replay(event_type='user') + self.replay(event_type='king')
            events.sort(key=lambda x: x['timestamp'])
        return events[-limit:]
    
    def search(self, query: str, limit: int = 50) -> List[Dict]:
        """Szöveges keresés a naplóban"""
        results = []
        query_lower = query.lower()
        
        with self.lock:
            for event in reversed(self.index_by_time):
                # Data keresés
                data_str = json.dumps(event.get('data', {}), ensure_ascii=False).lower()
                if query_lower in data_str:
                    results.append(event)
                    if len(results) >= limit:
                        break
                
                # Metadata keresés
                if query_lower in event.get('source', '').lower():
                    if event not in results:
                        results.append(event)
                        if len(results) >= limit:
                            break
        
        return results
    
    def get_errors(self, since: float = None, limit: int = 100) -> List[Dict]:
        """Hibák listázása"""
        return self.replay(event_type='error', start_time=since, limit=limit)
    
    def get_warnings(self, since: float = None, limit: int = 100) -> List[Dict]:
        """Figyelmeztetések listázása"""
        return self.replay(event_type='warning', start_time=since, limit=limit)
    
    def get_performance_report(self, period: str = 'hour') -> Dict:
        """Teljesítmény jelentés"""
        now = time.time()
        periods = {
            'hour': 3600,
            'day': 86400,
            'week': 604800,
            'month': 2592000
        }
        
        seconds = periods.get(period, 3600)
        start = now - seconds
        
        events = self.replay(start_time=start)
        
        # Statisztikák
        total_events = len(events)
        errors = len([e for e in events if e['level'] == 'error'])
        warnings = len([e for e in events if e['level'] == 'warning'])
        
        # Válaszidők
        king_events = [e for e in events if e['type'] == 'king']
        response_times = []
        for e in king_events:
            data = e.get('data', {})
            if isinstance(data, dict) and 'response_time_ms' in data:
                response_times.append(data['response_time_ms'])
        
        avg_response = sum(response_times) / len(response_times) if response_times else 0
        
        return {
            'period': period,
            'seconds': seconds,
            'total_events': total_events,
            'errors': errors,
            'warnings': warnings,
            'avg_response_time_ms': round(avg_response, 2),
            'total_tokens': self.stats['total_tokens'],
            'events_per_second': round(total_events / seconds, 2)
        }
    
    def get_summary(self) -> Dict:
        """Rövid összefoglaló"""
        last_hour = self.get_performance_report('hour')
        last_day = self.get_performance_report('day')
        
        return {
            'status': 'running' if self.running else 'stopped',
            'uptime': time.time() - self.stats['start_time'],
            'total_events': self.stats['total_events'],
            'total_errors': self.stats['errors'],
            'total_warnings': self.stats['warnings'],
            'total_tokens': self.stats['total_tokens'],
            'avg_response_time_ms': round(self.stats['avg_response_time'] * 1000, 2),
            'last_hour': last_hour,
            'last_day': last_day,
            'disk_usage_mb': round(self.stats['disk_usage'] / (1024 * 1024), 2),
            'log_files': self.stats['log_files'],
            'buffer_size': len(self.buffer),
            'watchdog_triggered': self.stats['watchdog_triggered']
        }
    
    # ========== STATISZTIKÁK ==========
    
    def get_stats(self) -> Dict:
        with self.lock:
            return {
                'total_events': self.stats['total_events'],
                'events_by_type': dict(self.stats['events_by_type']),
                'events_by_level': dict(self.stats['events_by_level']),
                'avg_response_time_ms': round(self.stats['avg_response_time'] * 1000, 2),
                'total_tokens': self.stats['total_tokens'],
                'errors': self.stats['errors'],
                'warnings': self.stats['warnings'],
                'uptime': time.time() - self.stats['start_time'],
                'buffer_size': len(self.buffer),
                'last_flush': datetime.fromtimestamp(self.stats['last_flush']).isoformat(),
                'log_file': str(self.current_log_path) if self.current_log_path else None,
                'log_files': self.stats['log_files'],
                'disk_usage_mb': round(self.stats['disk_usage'] / (1024 * 1024), 2),
                'watchdog_triggered': self.stats['watchdog_triggered']
            }
    
    def get_token_usage(self, period: str = 'hour') -> Dict:
        """Token használat statisztika"""
        now = time.time()
        periods = {
            'hour': 3600,
            'day': 86400,
            'week': 604800,
            'month': 2592000
        }
        
        seconds = periods.get(period, 3600)
        start = now - seconds
        
        events = self.replay(start_time=start, event_type='king')
        
        total = 0
        for e in events:
            data = e.get('data', {})
            if isinstance(data, dict):
                if 'tokens_used' in data:
                    total += data['tokens_used']
                elif 'response' in data and isinstance(data['response'], str):
                    total += len(data['response'].split())
        
        return {
            'period': period,
            'seconds': seconds,
            'tokens': total,
            'average_per_hour': total * (3600 / seconds) if seconds > 0 else 0
        }
    
    # ========== DEBUG ==========
    
    def trace_token(self, token: str, probability: float, source: str, context: Dict = None):
        """Token szintű nyomkövetés"""
        if not self.config['quantum_logging']:
            return
        
        self.log(
            event_type='trace',
            source=source,
            data={
                'token': token,
                'probability': probability,
                'context': context
            },
            level='debug'
        )
    
    def export(self, format: str = 'json', query: Dict = None, limit: int = 1000) -> str:
        """Események exportálása"""
        events = self.replay(**query) if query else list(self.index_by_time)
        events = events[-limit:] if len(events) > limit else events
        
        if format == 'json':
            return json.dumps(events, indent=2, default=str)
        elif format == 'csv':
            import csv
            import io
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['id', 'timestamp', 'datetime', 'type', 'source', 'level', 'trace_id'])
            for e in events:
                writer.writerow([
                    e['id'], e['timestamp'], e['datetime'],
                    e['type'], e['source'], e['level'], e['trace_id']
                ])
            return output.getvalue()
        else:
            return str(events)
    
    def get_state(self) -> Dict:
        return {
            'status': 'running' if self.running else 'stopped',
            'stats': self.get_stats(),
            'playback': {
                'active': self.playback_state['active'],
                'speed': self.playback_state['speed']
            },
            'config': {
                'log_dir': str(self.log_dir),
                'log_level': self.config['log_level'],
                'buffer_size': self.config['buffer_size'],
                'trace_token_level': self.config['quantum_logging']
            }
        }
    
    def clear_buffer(self):
        """Buffer törlése (vészhelyzet)"""
        with self.lock:
            self.buffer.clear()
            print("📼 Buffer törölve")


# Teszt
if __name__ == "__main__":
    from scratchpad import Scratchpad
    
    s = Scratchpad()
    bb = BlackBox(s)
    bb.start()
    
    # Teszt események
    bb.log('system', 'test', {'message': 'Starting'}, 'info')
    bb.log('user', 'web', {'text': 'Hello!'}, 'info')
    bb.log('king', 'king', {'response': 'Hi there!', 'tokens_used': 5}, 'info')
    bb.log('error', 'test', {'error': 'Something went wrong'}, 'error')
    
    time.sleep(1)
    
    print("\n--- Statisztikák ---")
    stats = bb.get_stats()
    for k, v in stats.items():
        if not isinstance(v, dict):
            print(f"{k}: {v}")
    
    print("\n--- Teljesítmény jelentés ---")
    report = bb.get_performance_report()
    for k, v in report.items():
        print(f"{k}: {v}")
    
    print("\n--- Hibák ---")
    errors = bb.get_errors()
    for e in errors:
        print(f"  {e['datetime']}: {e['data']}")
    
    bb.stop()