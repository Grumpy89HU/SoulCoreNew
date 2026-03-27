"""
Logging middleware - Kérések/válaszok naplózása
"""

import time
import logging
from typing import Dict, Any, Callable

from .base import Middleware

logger = logging.getLogger(__name__)


class LoggingMiddleware(Middleware):
    """
    Kérés/válasz naplózás middleware.
    
    Konfiguráció:
        - enabled: bool (alap: True)
        - log_headers: bool (alap: False)
        - log_body: bool (alap: False)
        - log_response: bool (alap: True)
        - sensitive_headers: list (alap: ['authorization', 'cookie'])
    """
    
    def __init__(self, config: Dict = None):
        super().__init__(config)
        
        self.enabled = self.config.get('enabled', True)
        self.log_headers = self.config.get('log_headers', False)
        self.log_body = self.config.get('log_body', False)
        self.log_response = self.config.get('log_response', True)
        self.sensitive_headers = self.config.get('sensitive_headers', ['authorization', 'cookie'])
    
    def process_request(self, request: Dict, next_handler: Callable) -> Dict:
        """Kérés naplózása és időmérés"""
        if not self.enabled:
            return next_handler(request)
        
        start_time = time.time()
        
        # Kérés naplózása
        self._log_request(request)
        
        # Tovább a láncban
        response = next_handler(request)
        
        # Válasz naplózása
        elapsed = (time.time() - start_time) * 1000
        self._log_response(request, response, elapsed)
        
        return response
    
    def _log_request(self, request: Dict):
        """Kérés adatainak naplózása"""
        path = request.get('path', '')
        method = request.get('method', '')
        client_ip = request.get('client_ip', 'unknown')
        
        logger.info(f"Request: {method} {path} from {client_ip}")
        
        if self.log_headers:
            headers = request.get('headers', {}).copy()
            for sensitive in self.sensitive_headers:
                if sensitive in headers:
                    headers[sensitive] = '***REDACTED***'
            logger.debug(f"Request headers: {headers}")
        
        if self.log_body:
            body = request.get('body', {})
            logger.debug(f"Request body: {str(body)[:500]}")
    
    def _log_response(self, request: Dict, response: Dict, elapsed_ms: float):
        """Válasz adatainak naplózása"""
        path = request.get('path', '')
        method = request.get('method', '')
        status = response.get('status', 200) if isinstance(response, dict) else 200
        
        logger.info(f"Response: {method} {path} -> {status} ({elapsed_ms:.2f}ms)")
        
        if self.log_response and isinstance(response, dict):
            response_log = response.copy()
            if 'body' in response_log:
                response_log['body'] = str(response_log.get('body', ''))[:200]
            logger.debug(f"Response: {response_log}")