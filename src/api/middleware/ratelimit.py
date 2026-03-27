"""
Rate limiting middleware - Kérés limitálás
"""

import time
import threading
import logging
from collections import defaultdict
from typing import Dict, Any, Callable, Optional, Tuple
from datetime import datetime, timedelta

from .base import Middleware

logger = logging.getLogger(__name__)


class RateLimitMiddleware(Middleware):
    """
    Kérés limitálás middleware.
    
    Konfiguráció:
        - enabled: bool (alap: True)
        - per_user: int (alap: 60) - kérések per perc userenként
        - per_ip: int (alap: 30) - kérések per perc IP-nként
        - window_seconds: int (alap: 60) - időablak másodpercben
        - block_duration: int (alap: 300) - blokkolás időtartama (másodperc)
    """
    
    def __init__(self, config: Dict = None):
        super().__init__(config)
        
        # Alapértelmezett konfig
        self.enabled = self.config.get('enabled', True)
        self.per_user = self.config.get('per_user', 60)
        self.per_ip = self.config.get('per_ip', 30)
        self.window_seconds = self.config.get('window_seconds', 60)
        self.block_duration = self.config.get('block_duration', 300)
        
        # Rate limit tárolók
        self.user_requests = defaultdict(list)
        self.ip_requests = defaultdict(list)
        self.blocked_users = {}
        self.blocked_ips = {}
        self.lock = threading.RLock()
    
    def process_request(self, request: Dict, handler: Callable) -> Dict:
        """Kérés limitálás ellenőrzése"""
        if not self.enabled:
            return handler(request)
        
        user_id = request.get('user', {}).get('id') if request.get('user') else None
        client_ip = request.get('client_ip', 'unknown')
        
        # Ellenőrizzük, hogy blokkolva van-e
        if user_id and self._is_blocked('user', user_id):
            return self._rate_limit_response('User blocked due to rate limit')
        
        if self._is_blocked('ip', client_ip):
            return self._rate_limit_response('IP blocked due to rate limit')
        
        # User limit ellenőrzés
        if user_id and not self._check_limit('user', user_id, self.per_user):
            self._block('user', user_id)
            return self._rate_limit_response('Rate limit exceeded for user')
        
        # IP limit ellenőrzés
        if not self._check_limit('ip', client_ip, self.per_ip):
            self._block('ip', client_ip)
            return self._rate_limit_response('Rate limit exceeded for IP')
        
        return handler(request)
    
    def _check_limit(self, limit_type: str, identifier: str, limit: int) -> bool:
        """Ellenőrzi, hogy a limit nincs-e túllépve"""
        with self.lock:
            storage = self.user_requests if limit_type == 'user' else self.ip_requests
            now = time.time()
            window_start = now - self.window_seconds
            
            # Régi kérések eltávolítása
            storage[identifier] = [t for t in storage[identifier] if t > window_start]
            
            # Limit ellenőrzés
            if len(storage[identifier]) >= limit:
                return False
            
            storage[identifier].append(now)
            return True
    
    def _block(self, limit_type: str, identifier: str):
        """Azonosító blokkolása"""
        with self.lock:
            storage = self.blocked_users if limit_type == 'user' else self.blocked_ips
            storage[identifier] = time.time() + self.block_duration
    
    def _is_blocked(self, limit_type: str, identifier: str) -> bool:
        """Ellenőrzi, hogy az azonosító blokkolva van-e"""
        with self.lock:
            storage = self.blocked_users if limit_type == 'user' else self.blocked_ips
            
            if identifier not in storage:
                return False
            
            if time.time() > storage[identifier]:
                del storage[identifier]
                return False
            
            return True
    
    def _rate_limit_response(self, message: str) -> Dict:
        """Rate limit túllépés válasz"""
        return {
            'status': 429,
            'error': 'Too Many Requests',
            'message': message
        }
    
    def get_stats(self) -> Dict:
        """Rate limit statisztikák"""
        with self.lock:
            return {
                'active_users': len(self.user_requests),
                'active_ips': len(self.ip_requests),
                'blocked_users': len(self.blocked_users),
                'blocked_ips': len(self.blocked_ips),
                'window_seconds': self.window_seconds,
                'per_user': self.per_user,
                'per_ip': self.per_ip
            }