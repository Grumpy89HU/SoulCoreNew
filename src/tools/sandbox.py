"""
Python-Sandbox - Dinamikus eszközhasználat.

Feladata:
1. Izolált környezet - resource limit, timeout
2. Kód futtatás - amit a King ír, azt lefuttatja
3. Eredmény visszajelzés - a King beépítheti a válaszába
4. Biztonsági szűrők - tiltott importok, végtelen ciklusok

Minden futás egy szigetelt környezetben történik, hogy ne fagyassza le a rendszert.
"""

import time
import ast
import sys
import io
import contextlib
import signal
import threading
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import traceback
import resource

# Opcionális: Docker támogatás
try:
    import docker
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False

class TimeoutException(Exception):
    """Timeout kivétel"""
    pass

class Sandbox:
    """
    Python Sandbox - biztonságos kód futtatás.
    
    Képes:
    - Python kód futtatása resource limit-ekkel
    - Tiltott importok szűrése
    - Időkorlát kezelés
    - Eredmény capture
    """
    
    # Tiltott importok (biztonsági okokból)
    FORBIDDEN_IMPORTS = {
        'os', 'subprocess', 'sys', 'socket', 'requests',
        'urllib', 'httpx', 'pickle', 'shelve', 'sqlite3',
        'threading', 'multiprocessing', 'signal', 'ctypes',
        'pty', 'tty', 'fcntl', 'termios', 'grp', 'pwd',
        'crypt', 'curses', 'readline', 'rlcompleter',
        'shutil', 'tempfile', 'glob', 'fnmatch', 'linecache',
        'macpath', 'ntpath', 'posixpath', 'pathlib', 'shlex',
        'zipfile', 'tarfile', 'gzip', 'bz2', 'lzma', 'zlib',
    }
    
    # Engedélyezett importok
    ALLOWED_IMPORTS = {
        'math', 'random', 'datetime', 'time', 'json',
        'collections', 'itertools', 'functools', 'operator',
        'string', 're', 'statistics', 'decimal', 'fractions',
        'array', 'copy', 'enum', 'heapq', 'bisect', 'queue',
        'struct', 'weakref', 'types', 'typing', 'warnings',
    }
    
    def __init__(self, scratchpad, config: Dict = None):
        self.scratchpad = scratchpad
        self.name = "sandbox"
        self.config = config or {}
        
        # Alapértelmezett konfiguráció
        default_config = {
            'enabled': True,
            'use_docker': False,           # Docker használata (ha van)
            'timeout': 30,                  # Maximum futási idő (másodperc)
            'max_memory': 512 * 1024 * 1024,  # 512 MB
            'max_cpu_time': 10,              # Maximum CPU idő (másodperc)
            'max_output_size': 1024 * 100,   # 100 KB
            'allowed_imports': list(self.ALLOWED_IMPORTS),
            'forbidden_imports': list(self.FORBIDDEN_IMPORTS),
            'enable_filesystem': False,       # Fájlrendszer hozzáférés
            'enable_network': False,          # Hálózat hozzáférés
            'temp_dir': '/tmp/soulcore_sandbox'
        }
        
        for key, value in default_config.items():
            if key not in self.config:
                self.config[key] = value
        
        # Docker client (ha van)
        self.docker_client = None
        if self.config['use_docker'] and DOCKER_AVAILABLE:
            try:
                self.docker_client = docker.from_env()
                print("🐳 Docker sandbox elérhető")
            except Exception as e:
                print(f"⚠️ Docker hiba: {e}")
                self.config['use_docker'] = False
        
        # Állapot
        self.state = {
            'status': 'idle',
            'executions': 0,
            'successful': 0,
            'failed': 0,
            'timeouts': 0,
            'last_execution': None
        }
        
        # Temp könyvtár létrehozása
        Path(self.config['temp_dir']).mkdir(parents=True, exist_ok=True)
        
        print("📦 Python-Sandbox: Izolált környezet készen áll.")
    
    def start(self):
        """Sandbox indítása"""
        self.state['status'] = 'ready'
        self.scratchpad.set_state('sandbox_status', 'ready', self.name)
        print("📦 Python-Sandbox: Várok a kódra.")
    
    def stop(self):
        """Sandbox leállítása"""
        self.state['status'] = 'stopped'
        self.scratchpad.set_state('sandbox_status', 'stopped', self.name)
        print("📦 Python-Sandbox: Leállt.")
    
    # --- KÓD ELLENŐRZÉS ---
    
    def validate_code(self, code: str) -> Tuple[bool, str, List[str]]:
        """
        Kód ellenőrzése biztonsági szempontból.
        
        Returns:
            (valid, error_message, warnings)
        """
        warnings = []
        
        # 1. Szintaxis ellenőrzés
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, f"Szintaktikai hiba: {e}", warnings
        
        # 2. Tiltott importok keresése
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name.split('.')[0]
                    if module in self.config['forbidden_imports']:
                        return False, f"Tiltott import: {module}", warnings
                    if module not in self.config['allowed_imports']:
                        warnings.append(f"Nem engedélyezett import: {module}")
            
            elif isinstance(node, ast.ImportFrom):
                module = node.module.split('.')[0] if node.module else ''
                if module in self.config['forbidden_imports']:
                    return False, f"Tiltott import: {module}", warnings
                if module and module not in self.config['allowed_imports']:
                    warnings.append(f"Nem engedélyezett import: {module}")
        
        # 3. Veszélyes függvények keresése
        dangerous_functions = {
            'eval', 'exec', 'compile', 'globals', 'locals',
            '__import__', 'open', 'input', 'print',  # print megengedett, de figyeljük
            'getattr', 'setattr', 'delattr', 'execfile'
        }
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in dangerous_functions:
                        warnings.append(f"Veszélyes függvény: {node.func.id}")
        
        # 4. Végtelen ciklus gyanú
        loop_count = 0
        for node in ast.walk(tree):
            if isinstance(node, (ast.While, ast.For)):
                loop_count += 1
        if loop_count > 3:
            warnings.append(f"Sok ciklus ({loop_count}), lehet végtelen ciklus")
        
        return True, "", warnings
    
    # --- KÓD FUTTATÁS (izolált) ---
    
    def execute(self, code: str, context: Dict = None) -> Dict:
        """
        Kód futtatása izolált környezetben.
        
        Args:
            code: Python kód
            context: Változók amiket átadunk a kódnak
            
        Returns:
            {
                'success': bool,
                'output': str,      # stdout
                'error': str,        # stderr / hibaüzenet
                'result': Any,        # Visszatérési érték (ha van)
                'execution_time': float,
                'warnings': List[str]
            }
        """
        start_time = time.time()
        self.state['executions'] += 1
        self.state['status'] = 'executing'
        
        result = {
            'success': False,
            'output': '',
            'error': '',
            'result': None,
            'execution_time': 0,
            'warnings': []
        }
        
        # 1. Kód ellenőrzés
        valid, error_msg, warnings = self.validate_code(code)
        result['warnings'] = warnings
        
        if not valid:
            result['error'] = error_msg
            self.state['failed'] += 1
            self.state['status'] = 'idle'
            result['execution_time'] = time.time() - start_time
            return result
        
        # 2. Docker használata (ha be van kapcsolva)
        if self.config['use_docker'] and self.docker_client:
            return self._execute_docker(code, context, result, start_time)
        
        # 3. Egyébként lokális sandbox
        return self._execute_local(code, context, result, start_time)
    
    def _execute_local(self, code: str, context: Dict, result: Dict, start_time: float) -> Dict:
        """
        Lokális sandbox futtatás (resource limit-ekkel).
        """
        # Resource limit beállítások
        def set_limits():
            # CPU idő limit
            resource.setrlimit(resource.RLIMIT_CPU, 
                (self.config['max_cpu_time'], self.config['max_cpu_time'] + 5))
            # Memória limit
            resource.setrlimit(resource.RLIMIT_AS,
                (self.config['max_memory'], self.config['max_memory']))
        
        # Output capture
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        # Környezet előkészítése
        local_context = {
            '__builtins__': __builtins__,
            '__name__': '__sandbox__',
        }
        
        # Engedélyezett modulok betöltése
        for module_name in self.config['allowed_imports']:
            try:
                module = __import__(module_name)
                local_context[module_name] = module
            except ImportError:
                pass
        
        # Felhasználói kontextus hozzáadása
        if context:
            local_context.update(context)
        
        # Timeout kezelés
        def timeout_handler(signum, frame):
            raise TimeoutException("A kód túl sokáig futott")
        
        try:
            # Resource limit beállítása
            set_limits()
            
            # Signal timeout (Unix only)
            if hasattr(signal, 'SIGALRM'):
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(self.config['timeout'])
            
            # Kód futtatása
            with contextlib.redirect_stdout(stdout_capture), \
                 contextlib.redirect_stderr(stderr_capture):
                
                exec_globals = local_context
                exec_locals = {}
                
                exec(code, exec_globals, exec_locals)
                
                # Ha van eredmény változó, visszaadjuk
                if '_result' in exec_locals:
                    result['result'] = exec_locals['_result']
                elif 'result' in exec_locals:
                    result['result'] = exec_locals['result']
            
            # Timeout kikapcsolása
            if hasattr(signal, 'SIGALRM'):
                signal.alarm(0)
            
            result['success'] = True
            self.state['successful'] += 1
            
        except TimeoutException as e:
            result['error'] = f"Timeout: {e}"
            self.state['timeouts'] += 1
            self.state['failed'] += 1
        except Exception as e:
            result['error'] = f"Hiba: {e}\n{traceback.format_exc()}"
            self.state['failed'] += 1
        finally:
            # Timeout kikapcsolása
            if hasattr(signal, 'SIGALRM'):
                signal.alarm(0)
        
        # Output összegyűjtése
        result['output'] = stdout_capture.getvalue()[:self.config['max_output_size']]
        stderr = stderr_capture.getvalue()
        if stderr and not result['error']:
            result['error'] = stderr[:self.config['max_output_size']]
        
        result['execution_time'] = time.time() - start_time
        self.state['status'] = 'idle'
        self.state['last_execution'] = result
        
        return result
    
    def _execute_docker(self, code: str, context: Dict, result: Dict, start_time: float) -> Dict:
        """
        Docker sandbox futtatás (ha van).
        """
        if not self.docker_client:
            return self._execute_local(code, context, result, start_time)
        
        try:
            # Kód fájlba írása
            code_file = Path(self.config['temp_dir']) / f"script_{int(time.time())}.py"
            with open(code_file, 'w') as f:
                f.write(code)
            
            # Docker konténer futtatása
            container = self.docker_client.containers.run(
                image='python:3.11-slim',
                command=['python', '/script.py'],
                volumes={str(code_file): {'bind': '/script.py', 'mode': 'ro'}},
                mem_limit=f"{self.config['max_memory']}b",
                cpu_period=100000,
                cpu_quota=int(100000 * self.config['max_cpu_time']),
                network_disabled=not self.config['enable_network'],
                read_only=True,
                detach=True
            )
            
            # Várakozás a befejeződésre
            try:
                result_container = container.wait(timeout=self.config['timeout'])
                logs = container.logs(stdout=True, stderr=True).decode('utf-8')
                
                result['output'] = logs[:self.config['max_output_size']]
                result['success'] = result_container['StatusCode'] == 0
                
                if result['success']:
                    self.state['successful'] += 1
                else:
                    result['error'] = f"Kilépési kód: {result_container['StatusCode']}"
                    self.state['failed'] += 1
                    
            except Exception as e:
                container.kill()
                result['error'] = f"Docker timeout vagy hiba: {e}"
                self.state['timeouts'] += 1
                self.state['failed'] += 1
            finally:
                container.remove()
                code_file.unlink()
            
        except Exception as e:
            result['error'] = f"Docker hiba: {e}"
            self.state['failed'] += 1
        
        result['execution_time'] = time.time() - start_time
        self.state['status'] = 'idle'
        
        return result
    
    # --- KING INTEGRÁCIÓ ---
    
    def execute_for_king(self, code: str, context: Dict = None) -> str:
        """
        Egyszerűsített kimenet a King számára.
        A King ezt a szöveget építheti be a válaszába.
        """
        result = self.execute(code, context)
        
        if result['success']:
            output = []
            if result['output']:
                output.append(f"Kimenet:\n{result['output']}")
            if result['result'] is not None:
                output.append(f"Eredmény: {result['result']}")
            if result['warnings']:
                output.append(f"Figyelmeztetések: {', '.join(result['warnings'])}")
            
            return "\n".join(output) if output else "A kód sikeresen lefutott, de nem volt kimenet."
        else:
            return f"Hiba a kód futtatásakor:\n{result['error']}"
    
    # --- STATISZTIKA ---
    
    def get_state(self) -> Dict:
        """Állapot lekérése"""
        return {
            'status': self.state['status'],
            'executions': self.state['executions'],
            'successful': self.state['successful'],
            'failed': self.state['failed'],
            'timeouts': self.state['timeouts'],
            'last_execution': self.state['last_execution'],
            'config': {
                'timeout': self.config['timeout'],
                'use_docker': self.config['use_docker'],
                'docker_available': DOCKER_AVAILABLE,
                'allowed_imports': len(self.config['allowed_imports'])
            }
        }

# Teszt
if __name__ == "__main__":
    from scratchpad import Scratchpad
    
    s = Scratchpad()
    sandbox = Sandbox(s)
    
    # Teszt kódok
    test_codes = [
        "print('Hello, világ!')",
        "import math\n_result = math.sqrt(16)",
        "import os\nprint('Ha van os, ez nem futna le')",
        "while True: pass  # Végtelen ciklus",
        """
def fibonacci(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a
_result = fibonacci(10)
print(f'Fibonacci 10: {_result}')
        """
    ]
    
    for code in test_codes:
        print(f"\n--- Futtatás: {code[:50]}... ---")
        result = sandbox.execute(code)
        print(f"Success: {result['success']}")
        print(f"Output: {result['output'][:100]}")
        print(f"Error: {result['error']}")
        print(f"Time: {result['execution_time']:.3f}s")
