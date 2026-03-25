"""
Alap API handler-ek
"""

import time
import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class APIHandlers:
    """API végpontok kezelője"""
    
    def __init__(self, soulcore):
        self.soulcore = soulcore
        self.db = soulcore.modules.get('database') if soulcore else None
    
    # ========== RENDSZER ==========
    
    def get_status(self) -> Dict:
        """Rendszer állapot"""
        return {
            'status': 'running',
            'timestamp': time.time(),
            'version': '3.0',
            'api_port': 6000,
            'king_available': bool(self.soulcore and hasattr(self.soulcore, 'king') and self.soulcore.king),
            'modules': list(self.soulcore.modules.keys()) if self.soulcore else []
        }
    
    # ========== CHAT ==========
    
    def post_chat(self, data: Dict) -> Dict:
        """Chat üzenet küldése"""
        text = data.get('text', '')
        conv_id = data.get('conversation_id', 1)
        
        if not text:
            return {'error': 'No text provided'}
        
        logger.info(f"📨 Chat: '{text}' (conv: {conv_id})")
        
        # King hívása
        if self.soulcore and hasattr(self.soulcore, 'king') and self.soulcore.king:
            try:
                response = self.soulcore.king.generate_response(text, conv_id)
                logger.info(f"✅ King válaszolt: {response[:50]}...")
                return {
                    'response': response,
                    'conversation_id': conv_id,
                    'trace_id': f"api-{int(time.time())}"
                }
            except Exception as e:
                logger.error(f"King hiba: {e}")
                return {'error': str(e)}
        
        # Dummy válasz
        return {
            'response': f"Echo: {text} (King nem elérhető)",
            'conversation_id': conv_id,
            'trace_id': 'dummy'
        }
    
    # ========== BESZÉLGETÉSEK ==========
    
    def get_conversations(self, params: Dict) -> Dict:
        """Beszélgetések listája"""
        if not self.db:
            return {'conversations': [], 'error': 'Database not available'}
        
        limit = int(params.get('limit', [50])[0])
        offset = int(params.get('offset', [0])[0])
        
        try:
            conversations = self.db.get_conversations(limit=limit, offset=offset)
            return {'conversations': conversations, 'total': len(conversations)}
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
            return {'id': conv_id, 'success': True}
        except Exception as e:
            return {'error': str(e)}
    
    def get_messages(self, conv_id: int, params: Dict) -> Dict:
        """Beszélgetés üzenetei"""
        if not self.db:
            return {'messages': [], 'error': 'Database not available'}
        
        limit = int(params.get('limit', [100])[0])
        
        try:
            messages = self.db.get_messages(conv_id, limit=limit)
            return {'messages': messages, 'count': len(messages)}
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
            return {'id': msg_id, 'success': True}
        except Exception as e:
            return {'error': str(e)}
    
    def delete_conversation(self, conv_id: int) -> Dict:
        """Beszélgetés törlése"""
        if not self.db:
            return {'error': 'Database not available'}
        
        try:
            self.db.delete_conversation(conv_id)
            return {'success': True}
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
            # TODO: Modell betöltés implementálása
            return {'success': True, 'message': f'Model {model_id or model_path} loading...'}
        except Exception as e:
            return {'error': str(e)}
    
    def unload_model(self, data: Dict) -> Dict:
        """Modell leállítása"""
        return {'success': True, 'message': 'Model unloaded'}
    
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
            return {'success': True, 'message': f'{module_name} started'}
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
            return {'success': True, 'message': f'{module_name} stopped'}
        except Exception as e:
            return {'error': str(e)}
    
    # ========== KING ==========
    
    def get_king_state(self) -> Dict:
        """King állapota"""
        king = self.soulcore.king if self.soulcore else None
        if not king:
            return {'error': 'King not available'}
        
        try:
            return king.get_state()
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
            return jester.get_diagnosis()
        except Exception as e:
            return {'error': str(e)}
    
    # ========== HEARTBEAT ==========
    
    def get_heartbeat_state(self) -> Dict:
        """Heartbeat állapot"""
        heartbeat = self.soulcore.modules.get('heartbeat') if self.soulcore else None
        if not heartbeat:
            return {'error': 'Heartbeat not available'}
        
        try:
            return heartbeat.get_state()
        except Exception as e:
            return {'error': str(e)}
    
    # ========== SENTINEL ==========
    
    def get_sentinel_status(self) -> Dict:
        """Sentinel GPU állapot"""
        sentinel = self.soulcore.modules.get('sentinel') if self.soulcore else None
        if not sentinel:
            return {'available': False, 'message': 'Sentinel not available'}
        
        try:
            return sentinel.get_gpu_status() if hasattr(sentinel, 'get_gpu_status') else {'available': False}
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
            return {'success': True}
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
            return {'key': key, 'value': value}
        except Exception as e:
            return {'error': str(e)}
    
    def clean_memory(self, data: Dict) -> Dict:
        """Memória tisztítása"""
        valet = self.soulcore.modules.get('valet') if self.soulcore else None
        if not valet:
            return {'error': 'Valet not available'}
        
        try:
            valet.cleanup()
            return {'success': True}
        except Exception as e:
            return {'error': str(e)}
    
    # ========== KONFIGURÁCIÓ ==========
    
    def get_config(self) -> Dict:
        """Konfiguráció lekérése"""
        if not self.soulcore:
            return {'error': 'SoulCore not available'}
        
        return self.soulcore.config
    
    def update_config(self, data: Dict) -> Dict:
        """Konfiguráció frissítése"""
        if not self.soulcore:
            return {'error': 'SoulCore not available'}
        
        # TODO: Konfiguráció frissítés implementálása
        return {'success': True, 'message': 'Config update not implemented yet'}
    
    # ========== IDENTITÁS ==========
    
    def get_identity(self) -> Dict:
        """Személyiség lekérése"""
        identity = self.soulcore.modules.get('identity') if self.soulcore else None
        if not identity:
            return {'error': 'Identity not available'}
        
        try:
            return identity.get_state()
        except Exception as e:
            return {'error': str(e)}
    
    def update_identity(self, data: Dict) -> Dict:
        """Személyiség frissítése"""
        identity = self.soulcore.modules.get('identity') if self.soulcore else None
        if not identity:
            return {'error': 'Identity not available'}
        
        # TODO: Identitás frissítés implementálása
        return {'success': True, 'message': 'Identity update not implemented yet'}
    
    # ========== BLACKBOX ==========
    
    def search_blackbox(self, params: Dict) -> Dict:
        """BlackBox keresés"""
        blackbox = self.soulcore.modules.get('blackbox') if self.soulcore else None
        if not blackbox:
            return {'error': 'BlackBox not available'}
        
        query = params.get('q', [''])[0]
        limit = int(params.get('limit', [100])[0])
        
        # TODO: BlackBox keresés implementálása
        return {'results': [], 'query': query, 'limit': limit}