"""
Alap API handler-ek
"""

import time
import json
import logging
import uuid
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class APIHandlers:
    """API végpontok kezelője"""
    
    def __init__(self, soulcore):
        self.soulcore = soulcore
        self.db = soulcore.modules.get('database') if soulcore else None
        self.config = soulcore.config if soulcore else {}
    
    # ========== SEGÉDFÜGGVÉNYEK ==========
    
    def _get_api_port(self) -> int:
        """API port lekérése a configból (hardkód eltávolítva)"""
        api_config = self.config.get('api', {})
        return api_config.get('port', 5001)
    
    def _get_trace_id(self) -> str:
        """Egyedi trace_id generálása"""
        return f"api_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
    
    def _parse_query_params(self, params: Dict, key: str, default: Any = None) -> Any:
        """Query paraméterek biztonságos parse-olása"""
        value = params.get(key, [default]) if isinstance(params.get(key), list) else params.get(key, default)
        return value[0] if isinstance(value, list) and value else value
    
    # ========== RENDSZER ==========
    
    def get_status(self) -> Dict:
        """Rendszer állapot"""
        return {
            'status': 'running',
            'timestamp': time.time(),
            'version': '3.0',
            'api_port': self._get_api_port(),
            'king_available': bool(self.soulcore and hasattr(self.soulcore, 'king') and self.soulcore.king),
            'modules': list(self.soulcore.modules.keys()) if self.soulcore else [],
            'ws_port': self.config.get('api', {}).get('ws_port', 5002)
        }
    
    # ========== CHAT ==========
    
    def post_chat(self, data: Dict) -> Dict:
        """Chat üzenet küldése"""
        text = data.get('text', '')
        conv_id = data.get('conversation_id')
        
        if not text:
            return {'error': 'No text provided'}
        
        # Ha nincs conversation_id, újat hozunk létre
        if conv_id is None and self.db:
            try:
                user_id = data.get('user_id')
                conv_id = self.db.create_conversation(title=text[:50], user_id=user_id)
                logger.info(f"📨 Új beszélgetés létrehozva: {conv_id}")
            except Exception as e:
                logger.warning(f"Beszélgetés létrehozási hiba: {e}")
                conv_id = int(time.time() * 1000)
        
        if conv_id is None:
            conv_id = int(time.time() * 1000)
        
        logger.info(f"📨 Chat: '{text[:50]}...' (conv: {conv_id})")
        
        # King hívása
        if self.soulcore and hasattr(self.soulcore, 'king') and self.soulcore.king:
            try:
                response = self.soulcore.king.generate_response(text, conv_id)
                logger.info(f"✅ King válaszolt: {response[:50]}...")
                return {
                    'response': response,
                    'conversation_id': conv_id,
                    'trace_id': self._get_trace_id(),
                    'timestamp': time.time()
                }
            except Exception as e:
                logger.error(f"King hiba: {e}")
                return {
                    'error': str(e),
                    'conversation_id': conv_id,
                    'trace_id': self._get_trace_id()
                }
        
        # Dummy válasz (csak ha tényleg nincs King)
        return {
            'response': f"Echo: {text} (King nem elérhető)",
            'conversation_id': conv_id,
            'trace_id': self._get_trace_id(),
            'warning': 'King not available'
        }
    
    # ========== BESZÉLGETÉSEK ==========
    
    def get_conversations(self, params: Dict) -> Dict:
        """Beszélgetések listája"""
        if not self.db:
            return {'conversations': [], 'error': 'Database not available'}
        
        limit = self._parse_query_params(params, 'limit', 50)
        offset = self._parse_query_params(params, 'offset', 0)
        
        try:
            limit = int(limit) if limit else 50
            offset = int(offset) if offset else 0
            conversations = self.db.get_conversations(limit=limit, offset=offset)
            total = len(conversations)
            return {'conversations': conversations, 'total': total, 'limit': limit, 'offset': offset}
        except Exception as e:
            return {'error': str(e)}
    
    def create_conversation(self, data: Dict) -> Dict:
        """Új beszélgetés létrehozása"""
        if not self.db:
            return {'error': 'Database not available'}
        
        title = data.get('title', 'New Conversation')
        user_id = data.get('user_id')
        
        try:
            conv_id = self.db.create_conversation(title=title, user_id=user_id)
            return {'id': conv_id, 'success': True, 'timestamp': time.time()}
        except Exception as e:
            return {'error': str(e)}
    
    def get_messages(self, conv_id: int, params: Dict) -> Dict:
        """Beszélgetés üzenetei"""
        if not self.db:
            return {'messages': [], 'error': 'Database not available'}
        
        limit = self._parse_query_params(params, 'limit', 100)
        
        try:
            limit = int(limit) if limit else 100
            messages = self.db.get_messages(conv_id, limit=limit)
            return {'messages': messages, 'count': len(messages), 'conversation_id': conv_id}
        except Exception as e:
            return {'error': str(e)}
    
    def add_message(self, conv_id: int, data: Dict) -> Dict:
        """Üzenet hozzáadása"""
        if not self.db:
            return {'error': 'Database not available'}
        
        role = data.get('role', 'user')
        content = data.get('content', '')
        tokens = data.get('tokens', 0)
        
        try:
            msg_id = self.db.add_message(conv_id, role, content, tokens)
            return {'id': msg_id, 'success': True, 'timestamp': time.time()}
        except Exception as e:
            return {'error': str(e)}
    
    def delete_conversation(self, conv_id: int) -> Dict:
        """Beszélgetés törlése"""
        if not self.db:
            return {'error': 'Database not available'}
        
        try:
            self.db.delete_conversation(conv_id)
            return {'success': True, 'timestamp': time.time()}
        except Exception as e:
            return {'error': str(e)}
    
    # ========== MODELLEK ==========
    
    def get_models(self) -> Dict:
        """Elérhető modellek"""
        if not self.db:
            return {'models': []}
        
        try:
            models = self.db.get_models()
            return {'models': models}
        except Exception as e:
            return {'error': str(e)}
    
    def load_model(self, data: Dict) -> Dict:
        """Modell betöltése"""
        model_id = data.get('model_id')
        model_path = data.get('model_path')
        
        if not model_id and not model_path:
            return {'error': 'model_id or model_path required'}
        
        king = self.soulcore.king if self.soulcore else None
        if not king:
            return {'error': 'King not available'}
        
        try:
            # Ha van model_wrapper, próbáljuk betölteni
            if hasattr(king, 'model') and king.model:
                success = king.model.load()
                if success:
                    return {'success': True, 'message': f'Model {model_id or model_path} loaded'}
                else:
                    return {'error': 'Model load failed'}
            
            return {'success': False, 'message': 'Model wrapper not available'}
        except Exception as e:
            return {'error': str(e)}
    
    def unload_model(self, data: Dict) -> Dict:
        """Modell leállítása"""
        king = self.soulcore.king if self.soulcore else None
        if not king:
            return {'error': 'King not available'}
        
        try:
            if hasattr(king, 'model') and king.model:
                king.model.unload()
            return {'success': True, 'message': 'Model unloaded'}
        except Exception as e:
            return {'error': str(e)}
    
    def delete_model(self, model_id: int) -> Dict:
        """Modell törlése"""
        if not self.db:
            return {'error': 'Database not available'}
        
        try:
            self.db.delete_model(model_id)
            return {'success': True}
        except Exception as e:
            return {'error': str(e)}
    
    # ========== MODULOK ==========
    
    def start_module(self, data: Dict) -> Dict:
        """Modul indítása"""
        module_name = data.get('module')
        
        if not module_name:
            return {'error': 'module name required'}
        
        module = self.soulcore.modules.get(module_name) if self.soulcore else None
        if not module:
            return {'error': f'Module {module_name} not found'}
        
        try:
            if hasattr(module, 'start'):
                module.start()
            return {'success': True, 'message': f'{module_name} started', 'timestamp': time.time()}
        except Exception as e:
            return {'error': str(e)}
    
    def stop_module(self, data: Dict) -> Dict:
        """Modul leállítása"""
        module_name = data.get('module')
        
        if not module_name:
            return {'error': 'module name required'}
        
        module = self.soulcore.modules.get(module_name) if self.soulcore else None
        if not module:
            return {'error': f'Module {module_name} not found'}
        
        try:
            if hasattr(module, 'stop'):
                module.stop()
            return {'success': True, 'message': f'{module_name} stopped', 'timestamp': time.time()}
        except Exception as e:
            return {'error': str(e)}
    
    # ========== KING ==========
    
    def get_king_state(self) -> Dict:
        """King állapota"""
        king = self.soulcore.king if self.soulcore else None
        if not king:
            return {'error': 'King not available'}
        
        try:
            state = king.get_state()
            if isinstance(state, dict):
                state['available'] = True
            return state
        except Exception as e:
            return {'error': str(e)}
    
    def set_king_parameters(self, data: Dict) -> Dict:
        """King paraméterek beállítása"""
        king = self.soulcore.king if self.soulcore else None
        if not king:
            return {'error': 'King not available'}
        
        try:
            return king.set_parameters(data)
        except Exception as e:
            return {'error': str(e)}
    
    # ========== JESTER ==========
    
    def get_jester_diagnosis(self) -> Dict:
        """Jester diagnózis"""
        jester = self.soulcore.modules.get('jester') if self.soulcore else None
        if not jester:
            return {'error': 'Jester not available'}
        
        try:
            return jester.get_diagnosis() if hasattr(jester, 'get_diagnosis') else {'diagnosis': 'Not available'}
        except Exception as e:
            return {'error': str(e)}
    
    # ========== HEARTBEAT ==========
    
    def get_heartbeat_state(self) -> Dict:
        """Heartbeat állapot"""
        heartbeat = self.soulcore.modules.get('heartbeat') if self.soulcore else None
        if not heartbeat:
            return {'error': 'Heartbeat not available'}
        
        try:
            return heartbeat.get_state() if hasattr(heartbeat, 'get_state') else {'state': heartbeat.state if hasattr(heartbeat, 'state') else {}}
        except Exception as e:
            return {'error': str(e)}
    
    # ========== SENTINEL ==========
    
    def get_sentinel_status(self) -> Dict:
        """Sentinel GPU állapot"""
        sentinel = self.soulcore.modules.get('sentinel') if self.soulcore else None
        if not sentinel:
            return {'available': False, 'message': 'Sentinel not available'}
        
        try:
            if hasattr(sentinel, 'get_gpu_status'):
                return {'available': True, 'gpus': sentinel.get_gpu_status()}
            elif hasattr(sentinel, 'get_state'):
                return {'available': True, 'state': sentinel.get_state()}
            return {'available': True, 'message': 'Sentinel active'}
        except Exception as e:
            return {'error': str(e)}
    
    # ========== MEMÓRIA (VAULT) ==========
    
    def remember_memory(self, data: Dict) -> Dict:
        """Emlék tárolása"""
        key = data.get('key')
        value = data.get('value')
        memory_type = data.get('type', 'fact')
        
        if not key or not value:
            return {'error': 'key and value required'}
        
        valet = self.soulcore.modules.get('valet') if self.soulcore else None
        if not valet:
            return {'error': 'Valet not available'}
        
        try:
            valet.remember(key, value, memory_type)
            return {'success': True, 'timestamp': time.time()}
        except Exception as e:
            return {'error': str(e)}
    
    def recall_memory(self, data: Dict) -> Dict:
        """Emlék előhívása"""
        key = data.get('key')
        
        if not key:
            return {'error': 'key required'}
        
        valet = self.soulcore.modules.get('valet') if self.soulcore else None
        if not valet:
            return {'error': 'Valet not available'}
        
        try:
            value = valet.recall(key)
            return {'key': key, 'value': value, 'timestamp': time.time()}
        except Exception as e:
            return {'error': str(e)}
    
    def clean_memory(self, data: Dict) -> Dict:
        """Memória tisztítása"""
        valet = self.soulcore.modules.get('valet') if self.soulcore else None
        if not valet:
            return {'error': 'Valet not available'}
        
        try:
            if hasattr(valet, 'cleanup'):
                valet.cleanup()
            return {'success': True, 'timestamp': time.time()}
        except Exception as e:
            return {'error': str(e)}
    
    # ========== KONFIGURÁCIÓ ==========
    
    def get_config(self) -> Dict:
        """Konfiguráció lekérése"""
        if not self.soulcore:
            return {'error': 'SoulCore not available'}
        
        # Biztonsági másolat – ne adjuk vissza a jelszavakat
        safe_config = self._sanitize_config(self.soulcore.config)
        return safe_config
    
    def _sanitize_config(self, config: Dict) -> Dict:
        """Konfiguráció másolása jelszavak nélkül"""
        if not isinstance(config, dict):
            return config
        
        safe = {}
        for key, value in config.items():
            if 'password' in key.lower() or 'secret' in key.lower() or 'token' in key.lower():
                safe[key] = '***HIDDEN***'
            elif isinstance(value, dict):
                safe[key] = self._sanitize_config(value)
            else:
                safe[key] = value
        return safe
    
    def update_config(self, data: Dict) -> Dict:
        """Konfiguráció frissítése (csak megengedett kulcsok)"""
        if not self.soulcore:
            return {'error': 'SoulCore not available'}
        
        # Engedélyezett módosítható kulcsok
        allowed_keys = ['user.language', 'user.name', 'agents.king.temperature', 
                       'agents.king.max_tokens', 'system.environment']
        
        try:
            # TODO: Konfiguráció frissítés implementálása
            # Jelenleg csak placeholder
            return {'success': True, 'message': 'Config update endpoint ready', 'allowed_keys': allowed_keys}
        except Exception as e:
            return {'error': str(e)}
    
    # ========== IDENTITÁS ==========
    
    def get_identity(self) -> Dict:
        """Személyiség lekérése"""
        identity = self.soulcore.modules.get('identity') if self.soulcore else None
        if not identity:
            return {'error': 'Identity not available'}
        
        try:
            if hasattr(identity, 'get_state'):
                return identity.get_state()
            elif hasattr(identity, 'state'):
                return identity.state
            return {'identity': 'Sovereign'}
        except Exception as e:
            return {'error': str(e)}
    
    def update_identity(self, data: Dict) -> Dict:
        """Személyiség frissítése"""
        identity = self.soulcore.modules.get('identity') if self.soulcore else None
        if not identity:
            return {'error': 'Identity not available'}
        
        personality = data.get('personality')
        name = data.get('name')
        style = data.get('style')
        
        try:
            if personality and hasattr(identity, 'set_personality'):
                identity.set_personality(personality)
            if name and hasattr(identity, 'set_name'):
                identity.set_name(name)
            if style and hasattr(identity, 'set_style'):
                identity.set_style(style)
            
            return {'success': True, 'message': 'Identity updated', 'timestamp': time.time()}
        except Exception as e:
            return {'error': str(e)}
    
    # ========== BLACKBOX ==========
    
    def search_blackbox(self, params: Dict) -> Dict:
        """BlackBox keresés"""
        blackbox = self.soulcore.modules.get('blackbox') if self.soulcore else None
        if not blackbox:
            return {'error': 'BlackBox not available'}
        
        query = self._parse_query_params(params, 'q', '')
        limit = self._parse_query_params(params, 'limit', 100)
        
        try:
            limit = int(limit) if limit else 100
            
            if hasattr(blackbox, 'search'):
                results = blackbox.search(query, limit=limit)
                return {'results': results, 'query': query, 'limit': limit, 'count': len(results)}
            elif hasattr(blackbox, 'get_logs'):
                logs = blackbox.get_logs(limit=limit)
                return {'results': logs, 'query': query, 'limit': limit, 'count': len(logs)}
            
            return {'results': [], 'query': query, 'limit': limit, 'message': 'Search not implemented'}
        except Exception as e:
            return {'error': str(e)}
    
    # ========== KONZOL CHAT (extra) ==========
    
    def console_chat(self, data: Dict) -> Dict:
        """
        Konzol chat végpont – egyszerű, streamelés nélküli kommunikáció
        CLI-hez vagy egyszerű teszteléshez
        """
        text = data.get('text', '')
        session_id = data.get('session_id')
        
        if not text:
            return {'error': 'No text provided'}
        
        # Session kezelés (egyszerű)
        if not session_id:
            session_id = f"console_{int(time.time())}"
        
        logger.info(f"💻 Console chat: '{text[:50]}...' (session: {session_id})")
        
        # King hívása
        if self.soulcore and hasattr(self.soulcore, 'king') and self.soulcore.king:
            try:
                # Konzol módban külön conversation_id-t használunk
                conv_id = int(hashlib.md5(session_id.encode()).hexdigest()[:8], 16) % 1000000
                response = self.soulcore.king.generate_response(text, conv_id)
                
                return {
                    'response': response,
                    'session_id': session_id,
                    'trace_id': self._get_trace_id(),
                    'timestamp': time.time(),
                    'mode': 'console'
                }
            except Exception as e:
                logger.error(f"King hiba: {e}")
                return {'error': str(e), 'session_id': session_id}
        
        return {'error': 'King not available', 'session_id': session_id}