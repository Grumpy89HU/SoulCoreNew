"""
Python-Sandbox - Dinamikus eszközhasználat.

Feladata:
1. Izolált környezet - resource limit, timeout, Docker
2. Kód futtatás - amit a King ír, azt lefuttatja
3. Eredmény visszajelzés - a King beépítheti a válaszába
4. Biztonsági szűrők - tiltott importok, végtelen ciklusok
5. Tool-Caller mechanizmus - script generálás, validáció, futtatás

Minden futás egy szigetelt környezetben történik, hogy ne fagyassza le a rendszert.
"""

import time
import ast
import sys
import io
import contextlib
import signal
import threading
import traceback
import resource
import tempfile
import os
from typing import Dict, Any, List, Optional, Tuple, Callable
from pathlib import Path

# Opcionális: Docker támogatás
try:
    import docker
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False

# i18n import (opcionális)
try:
    from src.i18n.translator import get_translator
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False

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
    - Docker izoláció (opcionális)
    - Tool-Caller mechanizmus
    """
    
    # Tiltott importok (biztonsági okokból)
    FORBIDDEN_IMPORTS = {
        'os', 'subprocess', 'socket', 'requests', 'urllib', 'httpx',
        'pickle', 'shelve', 'sqlite3', 'threading', 'multiprocessing',
        'signal', 'ctypes', 'pty', 'tty', 'fcntl', 'termios',
        'grp', 'pwd', 'crypt', 'curses', 'readline', 'rlcompleter',
        'shutil', 'tempfile', 'glob', 'fnmatch', 'linecache',
        'macpath', 'ntpath', 'posixpath', 'shlex', 'zipfile',
        'tarfile', 'gzip', 'bz2', 'lzma', 'zlib', 'importlib',
        'sys', 'os.path', 'pathlib', 'inspect', 'site'
    }
    
    # Engedélyezett importok
    ALLOWED_IMPORTS = {
        'math', 'random', 'datetime', 'time', 'json',
        'collections', 'itertools', 'functools', 'operator',
        'string', 're', 'statistics', 'decimal', 'fractions',
        'array', 'copy', 'enum', 'heapq', 'bisect', 'queue',
        'struct', 'weakref', 'types', 'typing', 'warnings',
        'hashlib', 'base64', 'binascii', 'codecs', 'uuid'
    }
    
    # Veszélyes függvények
    DANGEROUS_FUNCTIONS = {
        'eval', 'exec', 'compile', 'globals', 'locals',
        '__import__', 'open', 'input', 'getattr', 'setattr',
        'delattr', 'execfile', 'compile', 'eval', 'exec'
    }
    
    def __init__(self, scratchpad, config: Dict = None):
        self.scratchpad = scratchpad
        self.name = "sandbox"
        self.config = config or {}
        
        # Fordító (később állítjuk be)
        self.translator = None
        if I18N_AVAILABLE:
            self.translator = get_translator('en')
        
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
            'enable_filesystem': False,      # Fájlrendszer hozzáférés
            'enable_network': False,         # Hálózat hozzáférés
            'temp_dir': '/tmp/soulcore_sandbox',
            'enable_tool_caller': True,      # Tool-Caller engedélyezése
            'max_code_length': 10000,         # Max kód hossz (karakter)
            'validation_level': 'strict'      # strict, normal, permissive
        }
        
        for key, value in default_config.items():
            if key not in self.config:
                self.config[key] = value
        
        # Docker client (ha van)
        self.docker_client = None
        if self.config['use_docker'] and DOCKER_AVAILABLE:
            try:
                self.docker_client = docker.from_env()
                print("🐳 Sandbox: Docker sandbox elérhető")
            except Exception as e:
                print(f"⚠️ Sandbox: Docker hiba: {e}")
                self.config['use_docker'] = False
        
        # Tool registry (elérhető eszközök)
        self.tools = {}
        
        # Állapot
        self.state = {
            'status': 'idle',
            'executions': 0,
            'successful': 0,
            'failed': 0,
            'timeouts': 0,
            'blocked': 0,
            'last_execution': None,
            'errors': []
        }
        
        # Temp könyvtár létrehozása
        Path(self.config['temp_dir']).mkdir(parents=True, exist_ok=True)
        
        print("📦 Python-Sandbox: Izolált környezet készen áll.")
    
    def set_language(self, language: str):
        """Nyelv beállítása (i18n)"""
        if self.translator and I18N_AVAILABLE:
            self.translator.set_language(language)
    
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
        
        # 1. Hossz ellenőrzés
        if len(code) > self.config['max_code_length']:
            return False, f"Code too long: {len(code)} > {self.config['max_code_length']}", warnings
        
        # 2. Szintaxis ellenőrzés
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, f"Syntax error: {e}", warnings
        except Exception as e:
            return False, f"Parse error: {e}", warnings
        
        # 3. Tiltott importok keresése
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name.split('.')[0]
                    if module in self.config['forbidden_imports']:
                        return False, f"Forbidden import: {module}", warnings
                    if self.config['validation_level'] == 'strict':
                        if module not in self.config['allowed_imports']:
                            warnings.append(f"Non-allowed import: {module}")
            
            elif isinstance(node, ast.ImportFrom):
                module = node.module.split('.')[0] if node.module else ''
                if module in self.config['forbidden_imports']:
                    return False, f"Forbidden import: {module}", warnings
                if self.config['validation_level'] == 'strict':
                    if module and module not in self.config['allowed_imports']:
                        warnings.append(f"Non-allowed import: {module}")
        
        # 4. Veszélyes függvények keresése
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in self.DANGEROUS_FUNCTIONS:
                        warnings.append(f"Dangerous function: {node.func.id}")
        
        # 5. Végtelen ciklus gyanú
        loop_count = 0
        for node in ast.walk(tree):
            if isinstance(node, (ast.While, ast.For)):
                loop_count += 1
        if loop_count > 5:
            warnings.append(f"Many loops ({loop_count}), possible infinite loop")
        
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
            self.state['blocked'] += 1
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
            try:
                resource.setrlimit(resource.RLIMIT_CPU, 
                    (self.config['max_cpu_time'], self.config['max_cpu_time'] + 5))
                # Memória limit
                resource.setrlimit(resource.RLIMIT_AS,
                    (self.config['max_memory'], self.config['max_memory']))
            except:
                pass
        
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
            raise TimeoutException(f"Code execution timed out after {self.config['timeout']} seconds")
        
        # Ideiglenes fájl létrehozása (ha kell)
        temp_file = None
        if self.config['enable_filesystem']:
            temp_file = tempfile.NamedTemporaryFile(
                mode='w', 
                dir=self.config['temp_dir'],
                delete=False,
                suffix='.py'
            )
            temp_file.write(code)
            temp_file.close()
        
        try:
            # Resource limit beállítása
            set_limits()
            
            # Signal timeout (Unix only)
            if hasattr(signal, 'SIGALRM'):
                old_handler = signal.signal(signal.SIGALRM, timeout_handler)
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
                signal.signal(signal.SIGALRM, old_handler)
            
            result['success'] = True
            self.state['successful'] += 1
            
        except TimeoutException as e:
            result['error'] = str(e)
            self.state['timeouts'] += 1
            self.state['failed'] += 1
        except Exception as e:
            result['error'] = f"{e}\n{traceback.format_exc()}"
            self.state['failed'] += 1
        finally:
            # Timeout kikapcsolása
            if hasattr(signal, 'SIGALRM'):
                signal.alarm(0)
            
            # Temp fájl törlése
            if temp_file and os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
        
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
        
        temp_file = None
        try:
            # Kód fájlba írása
            temp_file = tempfile.NamedTemporaryFile(
                mode='w',
                dir=self.config['temp_dir'],
                delete=False,
                suffix='.py'
            )
            temp_file.write(code)
            temp_file.close()
            
            # Docker konténer futtatása
            container = self.docker_client.containers.run(
                image='python:3.11-slim',
                command=['python', '/script.py'],
                volumes={temp_file.name: {'bind': '/script.py', 'mode': 'ro'}},
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
                    result['error'] = f"Exit code: {result_container['StatusCode']}"
                    self.state['failed'] += 1
                    
            except Exception as e:
                container.kill()
                result['error'] = f"Docker timeout or error: {e}"
                self.state['timeouts'] += 1
                self.state['failed'] += 1
            finally:
                container.remove()
            
        except Exception as e:
            result['error'] = f"Docker error: {e}"
            self.state['failed'] += 1
        finally:
            if temp_file and os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
        
        result['execution_time'] = time.time() - start_time
        self.state['status'] = 'idle'
        
        return result
    
    # --- TOOL-CALLER MECHANIZMUS ---
    
    def register_tool(self, name: str, description: str, function: Callable, schema: Dict = None):
        """
        Eszköz regisztrálása a tool registry-be.
        
        Args:
            name: eszköz neve
            description: leírás (King számára)
            function: a függvény, ami meghívódik
            schema: paraméter séma (JSON Schema formátumban)
        """
        self.tools[name] = {
            'name': name,
            'description': description,
            'function': function,
            'schema': schema or {},
            'calls': 0
        }
        print(f"🔧 Sandbox: Tool registered: {name}")
    
    def call_tool(self, name: str, **kwargs) -> Any:
        """
        Eszköz meghívása név alapján.
        """
        tool = self.tools.get(name)
        if not tool:
            return f"Tool '{name}' not found"
        
        try:
            tool['calls'] += 1
            result = tool['function'](**kwargs)
            return result
        except Exception as e:
            return f"Tool execution error: {e}"
    
    def list_tools(self) -> List[Dict]:
        """
        Elérhető eszközök listázása.
        """
        return [
            {
                'name': t['name'],
                'description': t['description'],
                'schema': t['schema'],
                'calls': t['calls']
            }
            for t in self.tools.values()
        ]
    
    def generate_tool_code(self, tool_name: str, parameters: Dict) -> str:
        """
        Kód generálása egy eszköz meghívásához.
        """
        param_str = ', '.join([f"{k}={repr(v)}" for k, v in parameters.items()])
        return f"""
# Tool call: {tool_name}
_result = sandbox.call_tool('{tool_name}', {param_str})
if _result:
    print(f"Result: {{_result}}")
"""
    
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
                output.append(f"Output:\n{result['output']}")
            if result['result'] is not None:
                output.append(f"Result: {result['result']}")
            if result['warnings']:
                output.append(f"Warnings: {', '.join(result['warnings'])}")
            
            return "\n".join(output) if output else "Code executed successfully, no output."
        else:
            return f"Execution failed:\n{result['error']}"
    
    # --- STATISZTIKA ---
    
    def get_state(self) -> Dict:
        """Állapot lekérése"""
        return {
            'status': self.state['status'],
            'executions': self.state['executions'],
            'successful': self.state['successful'],
            'failed': self.state['failed'],
            'timeouts': self.state['timeouts'],
            'blocked': self.state['blocked'],
            'last_execution': self.state['last_execution'],
            'tools': len(self.tools),
            'tool_calls': sum(t['calls'] for t in self.tools.values()),
            'config': {
                'timeout': self.config['timeout'],
                'use_docker': self.config['use_docker'],
                'docker_available': DOCKER_AVAILABLE,
                'allowed_imports': len(self.config['allowed_imports']),
                'validation_level': self.config['validation_level']
            },
            'errors': self.state['errors'][-5:]
        }

# Példa tool-ok (ha később kellenek)
def example_math_tool(operation: str, a: float, b: float) -> float:
    """Példa matematikai eszköz"""
    if operation == 'add':
        return a + b
    elif operation == 'subtract':
        return a - b
    elif operation == 'multiply':
        return a * b
    elif operation == 'divide':
        return a / b if b != 0 else float('inf')
    return 0.0

# Teszt
if __name__ == "__main__":
    from scratchpad import Scratchpad
    
    s = Scratchpad()
    sandbox = Sandbox(s)
    
    # Tool regisztráció példa
    sandbox.register_tool(
        'math',
        'Basic mathematical operations',
        example_math_tool,
        {
            'type': 'object',
            'properties': {
                'operation': {'type': 'string', 'enum': ['add', 'subtract', 'multiply', 'divide']},
                'a': {'type': 'number'},
                'b': {'type': 'number'}
            }
        }
    )
    
    # Teszt kódok
    test_codes = [
        "print('Hello, world!')",
        "import math\n_result = math.sqrt(16)",
        "import os\nprint('This should fail')",
        "while True: pass  # Infinite loop",
        """
def fibonacci(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a
_result = fibonacci(10)
print(f'Fibonacci 10: {_result}')
        """,
        """
# Tool call example
_result = sandbox.call_tool('math', operation='add', a=10, b=5)
print(f'10 + 5 = {_result}')
        """
    ]
    
    print("Elérhető tool-ok:", sandbox.list_tools())
    
    for code in test_codes:
        print(f"\n--- Futtatás: {code[:50]}... ---")
        result = sandbox.execute(code)
        print(f"Success: {result['success']}")
        print(f"Output: {result['output'][:100]}")
        print(f"Error: {result['error']}")
        print(f"Time: {result['execution_time']:.3f}s")