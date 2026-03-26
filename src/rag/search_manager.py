"""
Search Manager - Kereső funkciók cache-eléssel.
"""

import time
import hashlib
import threading
import json
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class SearchManager:
    """
    Kereső kezelő - keresési eredmények cache-elése (24 óra).
    
    Funkciók:
    - Keresési eredmények cache-elése
    - Különböző kereső back-end-ek támogatása
    - Keresési statisztikák
    """
    
    def __init__(self, config: Dict = None, search_function: Callable = None):
        self.config = config or {}
        self.search_function = search_function
        self.cache = {}
        self.cache_ttl = self.config.get('cache_ttl', 86400)  # 24 óra
        self.cache_lock = threading.RLock()
        
        # Kereső típusa (beépített vagy külső)
        self.search_type = self.config.get('search_type', 'internal')
        
        # Külső kereső API beállítások
        self.search_api_url = self.config.get('search_api_url')
        self.search_api_key = self.config.get('search_api_key')
        
        # Statisztikák
        self.stats = {
            'total_searches': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'avg_time_ms': 0
        }
        
        print(f"🔍 SearchManager: {self.search_type} kereső betöltve")
        print(f"   Cache TTL: {self.cache_ttl}s (24h)")
    
    def _get_cache_key(self, query: str, filters: Dict = None) -> str:
        """Cache kulcs generálása"""
        filters_str = json.dumps(filters or {}, sort_keys=True)
        return hashlib.md5(f"{query}_{filters_str}".encode()).hexdigest()
    
    def search(self, query: str, limit: int = 10, filters: Dict = None, 
               force_refresh: bool = False) -> List[Dict]:
        """
        Keresés végrehajtása cache-eléssel.
        
        Args:
            query: keresési lekérdezés
            limit: találatok száma
            filters: szűrők (opcionális)
            force_refresh: cache frissítés kényszerítése
            
        Returns:
            List of search results
        """
        cache_key = self._get_cache_key(query, filters)
        
        if not force_refresh:
            with self.cache_lock:
                if cache_key in self.cache:
                    entry = self.cache[cache_key]
                    if time.time() - entry['timestamp'] < self.cache_ttl:
                        self.stats['cache_hits'] += 1
                        return entry['results'][:limit]
                    else:
                        del self.cache[cache_key]
        
        self.stats['cache_misses'] += 1
        start_time = time.time()
        
        try:
            if self.search_type == 'internal':
                results = self._internal_search(query, limit, filters)
            elif self.search_type == 'api':
                results = self._api_search(query, limit, filters)
            else:
                results = []
            
            elapsed_ms = (time.time() - start_time) * 1000
            if self.stats['avg_time_ms'] == 0:
                self.stats['avg_time_ms'] = elapsed_ms
            else:
                self.stats['avg_time_ms'] = self.stats['avg_time_ms'] * 0.9 + elapsed_ms * 0.1
            
            self.stats['total_searches'] += 1
            
            # Cache mentés
            with self.cache_lock:
                self.cache[cache_key] = {
                    'results': results,
                    'timestamp': time.time(),
                    'query': query,
                    'filters': filters
                }
            
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Search hiba: {e}")
            return []
    
    def _internal_search(self, query: str, limit: int, filters: Dict) -> List[Dict]:
        """
        Belső kereső - a Valet-től kapott search_function-t használja.
        """
        # Ha van search_function, azt használjuk
        if self.search_function:
            try:
                results = self.search_function(query, limit, filters)
                if results is not None:
                    return results
            except Exception as e:
                logger.error(f"Search function hiba: {e}")
        
        # Fallback: üres lista
        return []
    
    def _api_search(self, query: str, limit: int, filters: Dict) -> List[Dict]:
        """
        Külső kereső API használata.
        """
        if not self.search_api_url:
            return []
        
        try:
            import requests
            params = {
                'q': query,
                'limit': limit,
                **filters
            }
            headers = {}
            if self.search_api_key:
                headers['Authorization'] = f'Bearer {self.search_api_key}'
            
            response = requests.get(
                self.search_api_url,
                params=params,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('results', [])
            else:
                logger.warning(f"API kereső hiba: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"API kereső hiba: {e}")
            return []
    
    def refresh_cache(self, query: str, filters: Dict = None):
        """Cache frissítése egy adott lekérdezésre"""
        self.search(query, filters=filters, force_refresh=True)
    
    def clear_cache(self):
        """Teljes cache törlése"""
        with self.cache_lock:
            self.cache.clear()
            print("🔍 SearchManager: Cache törölve")
    
    def get_cache_stats(self) -> Dict:
        """Cache statisztikák"""
        with self.cache_lock:
            cache_entries = len(self.cache)
            cache_age = 0
            if self.cache:
                oldest = min(entry['timestamp'] for entry in self.cache.values())
                cache_age = time.time() - oldest
            
            return {
                'entries': cache_entries,
                'max_entries': self.config.get('max_cache_entries', 1000),
                'oldest_age_seconds': round(cache_age),
                'oldest_age_hours': round(cache_age / 3600, 1)
            }
    
    def get_stats(self) -> Dict:
        """Statisztikák lekérése"""
        return {
            'total_searches': self.stats['total_searches'],
            'cache_hits': self.stats['cache_hits'],
            'cache_misses': self.stats['cache_misses'],
            'cache_hit_rate': self.stats['cache_hits'] / max(1, self.stats['cache_hits'] + self.stats['cache_misses']),
            'avg_time_ms': round(self.stats['avg_time_ms'], 2),
            'cache': self.get_cache_stats()
        }