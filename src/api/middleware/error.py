"""
Error handling middleware - Egységes hibakezelés
"""

import traceback
import logging
from typing import Dict, Any, Callable, Optional

from .base import Middleware

logger = logging.getLogger(__name__)


class ErrorMiddleware(Middleware):
    """
    Egységes hibakezelés middleware.
    
    Konfiguráció:
        - enabled: bool (alap: True)
        - debug: bool (alap: False) - részletes hibaüzenetek
        - log_errors: bool (alap: True)
        - expose_traceback: bool (alap: False)
    """
    
    def __init__(self, config: Dict = None):
        super().__init__(config)
        
        self.enabled = self.config.get('enabled', True)
        self.debug = self.config.get('debug', False)
        self.log_errors = self.config.get('log_errors', True)
        self.expose_traceback = self.config.get('expose_traceback', False)
    
    def process_request(self, request: Dict, handler: Callable) -> Dict:
        """Kérés feldolgozása hibakezeléssel"""
        if not self.enabled:
            return handler(request)
        
        try:
            response = handler(request)
            return response
        
        except Exception as e:
            return self._handle_error(request, e)
    
    def _handle_error(self, request: Dict, error: Exception) -> Dict:
        """Hiba kezelése"""
        path = request.get('path', '')
        method = request.get('method', '')
        
        if self.log_errors:
            logger.error(f"Error processing {method} {path}: {error}")
            if self.debug:
                logger.error(traceback.format_exc())
        
        # Hibakód meghatározása
        status = self._get_status_code(error)
        
        # Hibaüzenet összeállítása
        error_response = {
            'status': status,
            'error': self._get_error_type(error),
            'message': str(error) if self.debug else self._get_default_message(status),
            'timestamp': time.time(),
            'path': path,
            'method': method
        }
        
        if self.expose_traceback and self.debug:
            error_response['traceback'] = traceback.format_exc()
        
        return error_response
    
    def _get_status_code(self, error: Exception) -> int:
        """Hiba típus alapján HTTP státusz kód"""
        error_type = type(error).__name__
        
        # Gyakori hibák
        if error_type in ['ValueError', 'TypeError', 'KeyError']:
            return 400
        elif error_type == 'PermissionError':
            return 403
        elif error_type == 'FileNotFoundError':
            return 404
        elif error_type == 'TimeoutError':
            return 408
        elif error_type in ['RuntimeError', 'Exception']:
            return 500
        
        return 500
    
    def _get_error_type(self, error: Exception) -> str:
        """Hiba típus neve"""
        return type(error).__name__
    
    def _get_default_message(self, status: int) -> str:
        """Alapértelmezett hibaüzenet"""
        messages = {
            400: 'Bad Request',
            401: 'Unauthorized',
            403: 'Forbidden',
            404: 'Not Found',
            408: 'Request Timeout',
            429: 'Too Many Requests',
            500: 'Internal Server Error'
        }
        return messages.get(status, 'Unknown Error')