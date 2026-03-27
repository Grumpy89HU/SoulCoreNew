"""
Request ID middleware - Egyedi azonosító generálás
"""

import uuid
import time
from typing import Dict, Any, Callable

from .base import Middleware


class RequestIDMiddleware(Middleware):
    """
    Egyedi request ID generálás middleware.
    
    Konfiguráció:
        - enabled: bool (alap: True)
        - header_name: str (alap: 'X-Request-ID')
        - response_header: bool (alap: True)
        - generate_if_missing: bool (alap: True)
    """
    
    def __init__(self, config: Dict = None):
        super().__init__(config)
        
        self.enabled = self.config.get('enabled', True)
        self.header_name = self.config.get('header_name', 'X-Request-ID')
        self.response_header = self.config.get('response_header', True)
        self.generate_if_missing = self.config.get('generate_if_missing', True)
    
    def process_request(self, request: Dict, next_handler: Callable) -> Dict:
        """Request ID generálása és hozzáadása a kéréshez"""
        if not self.enabled:
            return next_handler(request)
        
        # Request ID kinyerése a header-ből
        headers = request.get('headers', {})
        request_id = headers.get(self.header_name)
        
        # Ha nincs és kell, generálunk újat
        if not request_id and self.generate_if_missing:
            request_id = self._generate_request_id()
        
        # Hozzáadjuk a kéréshez
        request['request_id'] = request_id
        request['request_start_time'] = time.time()
        
        # Továbbadjuk a lánc következő elemének
        response = next_handler(request)
        
        # Válasz header hozzáadása
        if self.response_header and request_id and isinstance(response, dict):
            if 'headers' not in response:
                response['headers'] = {}
            response['headers'][self.header_name] = request_id
        
        return response
    
    def _generate_request_id(self) -> str:
        """Egyedi request ID generálása"""
        timestamp = int(time.time() * 1000)
        unique_part = uuid.uuid4().hex[:12]
        return f"req-{timestamp}-{unique_part}"