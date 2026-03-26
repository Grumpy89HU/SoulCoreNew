"""
Python-Sandbox - Dinamikus eszközhasználat.

Feladata:
1. Izolált környezet - resource limit, timeout, Docker
2. Kód futtatás - amit a King ír, azt lefuttatja
3. Eredmény visszajelzés - a King beépítheti a válaszába
4. Biztonsági szűrők - tiltott importok, végtelen ciklusok
5. Tool-Caller mechanizmus - script generálás, validáció, futtatás
6. KARANTÉN RENDSZER - kód csak ellenőrzés után kerülhet élesbe
7. BIZTONSÁGI AUDITOR - független AI vizsgálja a kódot
8. IDŐZÍTETT BEKERÜLÉS - 1 hét problémamentes futás után

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
import hashlib
import json
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Callable
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, asdict

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


class CodeStatus(Enum):
    """Kód állapotok"""
    PENDING = "pending"           # Várakozik az auditorra
    AUDITING = "auditing"         # Éppen vizsgálják
    APPROVED = "approved"         # Engedélyezve (még nem éles)
    QUARANTINED = "quarantined"   # Karanténban (hibát okozott)
    REJECTED = "rejected"         # Elutasítva (kártékony)
    ACTIVE = "active"             # Élesben fut (1 hét után)
    DELETED = "deleted"           # Törölve


@dataclass
class CodeEntry:
    """Kód bejegyzés a karantén rendszerben"""
    id: str
    code: str
    status: CodeStatus
    created_at: float
    last_execution: float
    execution_count: int
    error_count: int
    audit_result: Dict[str, Any]
    audit_by: str
    activated_at: Optional[float] = None
    warnings: List[str] = None
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        data['status'] = self.status.value
        return data


class TimeoutException(Exception):
    """Timeout kivétel"""
    pass


class Sandbox:
    """
    Python Sandbox - biztonságos kód futtatás karantén rendszerrel.
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
        'sys', 'os.path', 'pathlib', 'inspect', 'site', 'builtins'
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
        'delattr', 'execfile', 'compile', 'eval', 'exec',
        '__builtins__', '__dict__', '__class__', '__bases__',
        '__subclasses__', '__globals__', '__code__'
    }
    
    # SoulCore veszélyeztető minták
    SOULCORE_HAZARDOUS_PATTERNS = [
        r'soulcore\s*\.\s*shutdown',
        r'soulcore\s*\.\s*stop',
        r'soulcore\s*\.\s*delete',
        r'soulcore\s*\.\s*remove',
        r'king\s*\.\s*stop',
        r'orchestrator\s*\.\s*stop',
        r'heartbeat\s*\.\s*stop',
        r'modules\s*\[\s*[\'"]',
        r'config\s*\[\s*[\'"]',
        r'write_note\s*\(\s*[\'"]king',
        r'delete_conversation',
        r'drop\s+table',
        r'rm\s+-rf',
        r'format\s+',
        r'dd\s+if=',
        r'chmod\s+777',
        r'chown\s+root',
        r'sudo\s+',
        r'os\.system',
        r'subprocess\.call',
        r'__import__\s*\(\s*[\'"]os'
    ]
    
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
            'use_docker': False,
            'timeout': 30,
            'max_memory': 512 * 1024 * 1024,
            'max_cpu_time': 10,
            'max_output_size': 1024 * 100,
            'allowed_imports': list(self.ALLOWED_IMPORTS),
            'forbidden_imports': list(self.FORBIDDEN_IMPORTS),
            'enable_filesystem': False,
            'enable_network': False,
            'temp_dir': '/tmp/soulcore_sandbox',
            'enable_tool_caller': True,
            'max_code_length': 10000,
            'validation_level': 'strict',
            'quarantine_days': 7,
            'max_execution_errors': 3,
            'auto_activate_after_days': 7,
            'require_audit': True,
            'audit_timeout_hours': 24,
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
        
        # Tool registry
        self.tools = {}
        
        # Karantén rendszer
        self.codes: Dict[str, CodeEntry] = {}
        self.quarantine_dir = Path(self.config['temp_dir']) / 'quarantine'
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        
        # Auditor (független AI)
        self.auditor = None
        
        # Állapot
        self.state = {
            'status': 'idle',
            'executions': 0,
            'successful': 0,
            'failed': 0,
            'timeouts': 0,
            'blocked': 0,
            'quarantined': 0,
            'rejected': 0,
            'active': 0,
            'last_execution': None,
            'errors': []
        }
        
        # Karantén bejegyzések betöltése
        self._load_quarantine()
        
        # Időzítő a karantén ellenőrzéshez
        self._start_quarantine_checker()
        
        print("📦 Python-Sandbox: Izolált környezet karantén rendszerrel.")
    
    def _load_quarantine(self):
        """Karantén bejegyzések betöltése a lemezről"""
        try:
            quarantine_file = self.quarantine_dir / 'codes.json'
            if quarantine_file.exists():
                with open(quarantine_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for code_id, entry in data.items():
                        entry['status'] = CodeStatus(entry['status'])
                        self.codes[code_id] = CodeEntry(**entry)
                print(f"📦 Sandbox: {len(self.codes)} karantén bejegyzés betöltve")
        except Exception as e:
            print(f"⚠️ Sandbox: Karantén betöltési hiba: {e}")
    
    def _save_quarantine(self):
        """Karantén bejegyzések mentése a lemezre"""
        try:
            data = {}
            for code_id, entry in self.codes.items():
                data[code_id] = entry.to_dict()
            
            quarantine_file = self.quarantine_dir / 'codes.json'
            with open(quarantine_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️ Sandbox: Karantén mentési hiba: {e}")
    
    def _start_quarantine_checker(self):
        """Karantén ellenőrző indítása (háttérszál)"""
        def check_loop():
            while True:
                time.sleep(3600)
                self._check_quarantine_expiry()
        
        thread = threading.Thread(target=check_loop, daemon=True)
        thread.start()
    
    def _check_quarantine_expiry(self):
        """Karantén lejárat ellenőrzése - 1 hét után aktiválás"""
        now = time.time()
        for code_id, entry in list(self.codes.items()):
            if entry.status == CodeStatus.QUARANTINED:
                age_days = (now - entry.created_at) / 86400
                if age_days >= self.config['auto_activate_after_days']:
                    self._auto_delete(code_id, "Karantén idő lejárt, automatikus törlés")
            
            elif entry.status == CodeStatus.APPROVED:
                age_days = (now - entry.created_at) / 86400
                if age_days >= self.config['quarantine_days']:
                    self._activate_code(code_id)
    
    def _auto_delete(self, code_id: str, reason: str):
        """Kód automatikus törlése"""
        if code_id in self.codes:
            entry = self.codes[code_id]
            entry.status = CodeStatus.DELETED
            self.state['quarantined'] -= 1
            self._save_quarantine()
            print(f"🗑️ Sandbox: Kód törölve ({reason}): {code_id}")
    
    def _activate_code(self, code_id: str):
        """Kód aktiválása (élesbe kerülés)"""
        if code_id in self.codes:
            entry = self.codes[code_id]
            entry.status = CodeStatus.ACTIVE
            entry.activated_at = time.time()
            self.state['active'] += 1
            self._save_quarantine()
            print(f"✅ Sandbox: Kód aktiválva (1 hét után): {code_id}")
    
    def set_auditor(self, auditor):
        """Független AI auditor beállítása"""
        self.auditor = auditor
        print("🔍 Sandbox: Auditor beállítva")
    
    def _check_soulcore_hazards(self, code: str) -> List[str]:
        """SoulCore-ot veszélyeztető minták ellenőrzése"""
        hazards = []
        for pattern in self.SOULCORE_HAZARDOUS_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                hazards.append(pattern)
        return hazards
    
    def _audit_with_ai(self, code: str, code_id: str) -> Dict:
        """Független AI auditor vizsgálata"""
        if not self.auditor:
            return {
                'approved': True,
                'confidence': 0.5,
                'notes': 'No auditor available, manual review required',
                'hazards': []
            }
        
        try:
            prompt = f"""You are a security auditor. Analyze this Python code for:
1. Malicious intent (viruses, worms, system damage)
2. SoulCore-specific threats (stopping modules, deleting data)
3. Resource abuse (infinite loops, memory bombs)
4. Privacy violations (accessing user data)
5. Network abuse (external connections)

Code to analyze:
[CODE_START]
{code[:2000]}
[CODE_END]

Respond with JSON:
{{
    "approved": true/false,
    "confidence": 0.0-1.0,
    "hazards": ["hazard1", "hazard2"],
    "notes": "explanation"
}}"""
            
            response = self.auditor.generate(prompt, max_tokens=500, temperature=0.1)
            
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    'approved': result.get('approved', False),
                    'confidence': result.get('confidence', 0.0),
                    'notes': result.get('notes', ''),
                    'hazards': result.get('hazards', [])
                }
        except Exception as e:
            print(f"⚠️ Sandbox: Auditor hiba: {e}")
        
        return {
            'approved': False,
            'confidence': 0.0,
            'notes': f'Audit failed: {e}',
            'hazards': []
        }
    
    def submit_code(self, code: str, source: str = "king") -> str:
        """Kód benyújtása a karantén rendszerbe"""
        valid, error_msg, warnings = self.validate_code(code)
        
        if not valid:
            code_id = hashlib.md5(f"{code}_{time.time()}".encode()).hexdigest()[:16]
            entry = CodeEntry(
                id=code_id,
                code=code,
                status=CodeStatus.REJECTED,
                created_at=time.time(),
                last_execution=time.time(),
                execution_count=0,
                error_count=0,
                audit_result={'error': error_msg},
                audit_by=source,
                warnings=warnings
            )
            self.codes[code_id] = entry
            self.state['rejected'] += 1
            self._save_quarantine()
            return code_id
        
        hazards = self._check_soulcore_hazards(code)
        code_id = hashlib.md5(f"{code}_{time.time()}".encode()).hexdigest()[:16]
        audit_result = {'hazards': hazards, 'warnings': warnings}
        
        if self.config['require_audit'] and self.auditor:
            audit = self._audit_with_ai(code, code_id)
            audit_result.update(audit)
            
            if not audit.get('approved', False):
                status = CodeStatus.REJECTED
                self.state['rejected'] += 1
            else:
                status = CodeStatus.APPROVED
        else:
            status = CodeStatus.APPROVED
            audit_result['notes'] = 'No auditor, manual review required'
        
        entry = CodeEntry(
            id=code_id,
            code=code,
            status=status,
            created_at=time.time(),
            last_execution=time.time(),
            execution_count=0,
            error_count=0,
            audit_result=audit_result,
            audit_by=source,
            warnings=warnings
        )
        
        self.codes[code_id] = entry
        self.state['quarantined'] += 1
        self._save_quarantine()
        
        print(f"📦 Sandbox: Kód karanténba helyezve: {code_id} (status: {status.value})")
        
        return code_id
    
    def execute_code(self, code_id: str, context: Dict = None) -> Dict:
        """Karantánban lévő kód futtatása"""
        if code_id not in self.codes:
            return {
                'success': False,
                'error': f'Code {code_id} not found',
                'output': '',
                'result': None,
                'execution_time': 0,
                'warnings': []
            }
        
        entry = self.codes[code_id]
        entry.last_execution = time.time()
        entry.execution_count += 1
        
        if entry.status == CodeStatus.REJECTED:
            entry.error_count += 1
            self._save_quarantine()
            return {
                'success': False,
                'error': 'Code rejected by security audit',
                'output': '',
                'result': None,
                'execution_time': 0,
                'warnings': entry.warnings or []
            }
        
        if entry.status == CodeStatus.QUARANTINED:
            entry.error_count += 1
            self._save_quarantine()
            return {
                'success': False,
                'error': 'Code is quarantined due to errors',
                'output': '',
                'result': None,
                'execution_time': 0,
                'warnings': entry.warnings or []
            }
        
        result = self.execute(entry.code, context)
        
        if not result['success']:
            entry.error_count += 1
            if entry.error_count >= self.config['max_execution_errors']:
                entry.status = CodeStatus.QUARANTINED
                self.state['quarantined'] += 1
                print(f"⚠️ Sandbox: Kód karanténba került (túl sok hiba): {code_id}")
        
        self._save_quarantine()
        return result
    
    def validate_code(self, code: str) -> Tuple[bool, str, List[str]]:
        """Kód ellenőrzése biztonsági szempontból"""
        warnings = []
        
        if len(code) > self.config['max_code_length']:
            return False, f"Code too long: {len(code)} > {self.config['max_code_length']}", warnings
        
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, f"Syntax error: {e}", warnings
        except Exception as e:
            return False, f"Parse error: {e}", warnings
        
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
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in self.DANGEROUS_FUNCTIONS:
                        warnings.append(f"Dangerous function: {node.func.id}")
        
        loop_count = 0
        for node in ast.walk(tree):
            if isinstance(node, (ast.While, ast.For)):
                loop_count += 1
        if loop_count > 5:
            warnings.append(f"Many loops ({loop_count}), possible infinite loop")
        
        hazards = self._check_soulcore_hazards(code)
        if hazards:
            return False, f"Hazardous patterns detected: {', '.join(hazards)}", warnings
        
        return True, "", warnings
    
    def execute(self, code: str, context: Dict = None) -> Dict:
        """Kód futtatása izolált környezetben"""
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
        
        valid, error_msg, warnings = self.validate_code(code)
        result['warnings'] = warnings
        
        if not valid:
            result['error'] = error_msg
            self.state['failed'] += 1
            self.state['blocked'] += 1
            self.state['status'] = 'idle'
            result['execution_time'] = time.time() - start_time
            return result
        
        if self.config['use_docker'] and self.docker_client:
            return self._execute_docker(code, context, result, start_time)
        
        return self._execute_local(code, context, result, start_time)
    
    def _execute_local(self, code: str, context: Dict, result: Dict, start_time: float) -> Dict:
        """Lokális sandbox futtatás"""
        def set_limits():
            try:
                resource.setrlimit(resource.RLIMIT_CPU, 
                    (self.config['max_cpu_time'], self.config['max_cpu_time'] + 5))
                resource.setrlimit(resource.RLIMIT_AS,
                    (self.config['max_memory'], self.config['max_memory']))
            except:
                pass
        
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        local_context = {
            '__builtins__': __builtins__,
            '__name__': '__sandbox__',
        }
        
        for module_name in self.config['allowed_imports']:
            try:
                module = __import__(module_name)
                local_context[module_name] = module
            except ImportError:
                pass
        
        if context:
            local_context.update(context)
        
        def timeout_handler(signum, frame):
            raise TimeoutException(f"Code execution timed out after {self.config['timeout']} seconds")
        
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
            set_limits()
            
            if hasattr(signal, 'SIGALRM'):
                old_handler = signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(self.config['timeout'])
            
            with contextlib.redirect_stdout(stdout_capture), \
                 contextlib.redirect_stderr(stderr_capture):
                
                exec_globals = local_context
                exec_locals = {}
                exec(code, exec_globals, exec_locals)
                
                if '_result' in exec_locals:
                    result['result'] = exec_locals['_result']
                elif 'result' in exec_locals:
                    result['result'] = exec_locals['result']
            
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
            if hasattr(signal, 'SIGALRM'):
                signal.alarm(0)
            
            if temp_file and os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
        
        result['output'] = stdout_capture.getvalue()[:self.config['max_output_size']]
        stderr = stderr_capture.getvalue()
        if stderr and not result['error']:
            result['error'] = stderr[:self.config['max_output_size']]
        
        result['execution_time'] = time.time() - start_time
        self.state['status'] = 'idle'
        self.state['last_execution'] = result
        
        return result
    
    def _execute_docker(self, code: str, context: Dict, result: Dict, start_time: float) -> Dict:
        """Docker sandbox futtatás"""
        if not self.docker_client:
            return self._execute_local(code, context, result, start_time)
        
        temp_file = None
        try:
            temp_file = tempfile.NamedTemporaryFile(
                mode='w',
                dir=self.config['temp_dir'],
                delete=False,
                suffix='.py'
            )
            temp_file.write(code)
            temp_file.close()
            
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
    
    # --- TOOL-CALLER ---
    
    def register_tool(self, name: str, description: str, function: Callable, schema: Dict = None):
        """Eszköz regisztrálása"""
        self.tools[name] = {
            'name': name,
            'description': description,
            'function': function,
            'schema': schema or {},
            'calls': 0
        }
        print(f"🔧 Sandbox: Tool registered: {name}")
    
    def call_tool(self, name: str, **kwargs) -> Any:
        """Eszköz meghívása"""
        tool = self.tools.get(name)
        if not tool:
            return f"Tool '{name}' not found"
        
        try:
            tool['calls'] += 1
            return tool['function'](**kwargs)
        except Exception as e:
            return f"Tool execution error: {e}"
    
    def list_tools(self) -> List[Dict]:
        """Elérhető eszközök"""
        return [
            {
                'name': t['name'],
                'description': t['description'],
                'schema': t['schema'],
                'calls': t['calls']
            }
            for t in self.tools.values()
        ]
    
    # --- KING INTEGRÁCIÓ ---
    
    def execute_for_king(self, code: str, context: Dict = None) -> str:
        """Egyszerűsített kimenet a King számára"""
        code_id = self.submit_code(code, source="king")
        entry = self.codes[code_id]
        
        if entry.status == CodeStatus.REJECTED:
            return f"Code rejected: {entry.audit_result.get('notes', 'Security violation detected')}"
        
        if entry.status == CodeStatus.APPROVED:
            age_days = (time.time() - entry.created_at) / 86400
            remaining_days = self.config['quarantine_days'] - age_days
            
            if remaining_days > 0:
                return f"Code approved, but in quarantine for {remaining_days:.0f} more days."
        
        if entry.status == CodeStatus.ACTIVE:
            result = self.execute(entry.code, context)
            
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
        
        return f"Code status: {entry.status.value}. Waiting for review."
    
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
            'quarantined': self.state['quarantined'],
            'rejected': self.state['rejected'],
            'active': self.state['active'],
            'last_execution': self.state['last_execution'],
            'tools': len(self.tools),
            'tool_calls': sum(t['calls'] for t in self.tools.values()),
            'quarantine_codes': len(self.codes),
            'config': {
                'timeout': self.config['timeout'],
                'quarantine_days': self.config['quarantine_days'],
                'use_docker': self.config['use_docker'],
                'docker_available': DOCKER_AVAILABLE,
                'allowed_imports': len(self.config['allowed_imports']),
                'validation_level': self.config['validation_level']
            },
            'errors': self.state['errors'][-5:]
        }


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


if __name__ == "__main__":
    from scratchpad import Scratchpad
    
    s = Scratchpad()
    sandbox = Sandbox(s)
    
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
    
    test_codes = [
        "print('Hello, world!')",
        "import math\n_result = math.sqrt(16)",
        "import os\nprint('This should be rejected')",
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
_result = sandbox.call_tool('math', operation='add', a=10, b=5)
print(f'10 + 5 = {_result}')
        """
    ]
    
    print("\n" + "="*50)
    print("Sandbox Karantén Teszt")
    print("="*50)
    
    for code in test_codes:
        print(f"\n--- Kód: {code[:50]}... ---")
        code_id = sandbox.submit_code(code)
        print(f"Kód ID: {code_id}")
        status = sandbox.get_code_status(code_id)
        if status:
            print(f"Állapot: {status['status']}")