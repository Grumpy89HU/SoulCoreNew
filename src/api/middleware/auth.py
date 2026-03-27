"""
Autentikáció middleware - Token alapú hitelesítés
"""

import time
import logging
from typing import Dict, Any, Callable, Optional

from .base import Middleware

logger = logging.getLogger(__name__)


class AuthMiddleware(Middleware):
    """
    Token alapú autentikáció middleware.
    
    Konfiguráció:
        - enabled: bool (alap: True)
        - header_name: str (alap: 'Authorization')
        - token_prefix: str (alap: 'Bearer ')
        - public_paths: list (alap: ['/health', '/api/status'])
        - token_validation: callable (opcionális)
    """
    
    def __init__(self, config: Dict = None, token_validator: Callable = None):
        super().__init__(config)
        self.token_validator = token_validator
        
        self.enabled = self.config.get('enabled', True)
        self.header_name = self.config.get('header_name', 'Authorization')
        self.token_prefix = self.config.get('token_prefix', 'Bearer ')
        self.public_paths = self.config.get('public_paths', ['/health', '/api/status'])
    
    def process_request(self, request: Dict, next_handler: Callable) -> Dict:
        """Kérés autentikációjának ellenőrzése"""
        if not self.enabled:
            return next_handler(request)
        
        path = request.get('path', '')
        
        # Publikus végpontok kivétele
        if self._is_public_path(path):
            return next_handler(request)
        
        # Token ellenőrzés
        auth_header = request.get('headers', {}).get(self.header_name, '')
        token = self._extract_token(auth_header)
        
        if not token:
            return {
                'status': 401,
                'error': 'Unauthorized',
                'message': 'Missing or invalid authentication token'
            }
        
        # Token validáció
        if self.token_validator:
            is_valid, user_data = self.token_validator(token)
            if not is_valid:
                return {
                    'status': 401,
                    'error': 'Unauthorized',
                    'message': 'Invalid or expired token'
                }
            request['user'] = user_data
        
        return next_handler(request)
    
    def _is_public_path(self, path: str) -> bool:
        for public in self.public_paths:
            if path == public or path.startswith(public):
                return True
        return False
    
    def _extract_token(self, auth_header: str) -> Optional[str]:
        if not auth_header:
            return None
        
        if self.token_prefix and auth_header.startswith(self.token_prefix):
            return auth_header[len(self.token_prefix):]
        
        return auth_header