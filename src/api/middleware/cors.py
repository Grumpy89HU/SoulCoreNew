"""
CORS middleware - Cross-Origin Resource Sharing
"""

from typing import Dict, Any, Callable, List

from .base import Middleware


class CORSMiddleware(Middleware):
    """
    CORS fejlécek kezelése.
    
    Konfiguráció:
        - enabled: bool (alap: True)
        - allowed_origins: list (alap: ['*'])
        - allowed_methods: list (alap: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
        - allowed_headers: list (alap: ['Content-Type', 'Authorization'])
        - expose_headers: list (alap: [])
        - allow_credentials: bool (alap: False)
        - max_age: int (alap: 86400)
    """
    
    def __init__(self, config: Dict = None):
        super().__init__(config)
        
        self.enabled = self.config.get('enabled', True)
        self.allowed_origins = self.config.get('allowed_origins', ['*'])
        self.allowed_methods = self.config.get('allowed_methods', 
            ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
        self.allowed_headers = self.config.get('allowed_headers', 
            ['Content-Type', 'Authorization'])
        self.expose_headers = self.config.get('expose_headers', [])
        self.allow_credentials = self.config.get('allow_credentials', False)
        self.max_age = self.config.get('max_age', 86400)
    
    def process_response(self, request: Dict, response: Dict) -> Dict:
        """CORS fejlécek hozzáadása a válaszhoz"""
        if not self.enabled:
            return response
        
        origin = request.get('headers', {}).get('Origin', '')
        
        # Origin ellenőrzés
        if '*' in self.allowed_origins:
            response['headers']['Access-Control-Allow-Origin'] = '*'
        elif origin in self.allowed_origins:
            response['headers']['Access-Control-Allow-Origin'] = origin
        else:
            return response
        
        # További CORS fejlécek
        response['headers']['Access-Control-Allow-Methods'] = ', '.join(self.allowed_methods)
        response['headers']['Access-Control-Allow-Headers'] = ', '.join(self.allowed_headers)
        
        if self.expose_headers:
            response['headers']['Access-Control-Expose-Headers'] = ', '.join(self.expose_headers)
        
        if self.allow_credentials:
            response['headers']['Access-Control-Allow-Credentials'] = 'true'
        
        response['headers']['Access-Control-Max-Age'] = str(self.max_age)
        
        return response
    
    def process_request(self, request: Dict, handler: Callable) -> Dict:
        """
        OPTIONS kérések kezelése (preflight)
        """
        if not self.enabled:
            return handler(request)
        
        method = request.get('method', '')
        
        # OPTIONS preflight kérés
        if method == 'OPTIONS':
            return {
                'status': 204,
                'headers': {},
                'body': ''
            }
        
        return handler(request)