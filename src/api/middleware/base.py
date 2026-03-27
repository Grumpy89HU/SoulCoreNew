"""
Middleware alap osztály
"""

from typing import Dict, Any, Callable, Optional, List
import logging

logger = logging.getLogger(__name__)


class Middleware:
    """
    Middleware alap osztály.
    Minden middleware-nek implementálnia kell a process_request és process_response metódusokat.
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.name = self.__class__.__name__
    
    def process_request(self, request: Dict, next_handler: Callable) -> Dict:
        """
        Kérés feldolgozása a handler hívása előtt.
        
        Args:
            request: A kérés adatai (path, method, headers, body)
            next_handler: A következő handler (lehet middleware vagy végpont)
        
        Returns:
            A handler által visszaadott válasz
        """
        return next_handler(request)
    
    def process_response(self, request: Dict, response: Dict) -> Dict:
        """
        Válasz feldolgozása a handler hívása után.
        
        Args:
            request: Az eredeti kérés adatai
            response: A handler által visszaadott válasz
        
        Returns:
            Módosított válasz
        """
        return response
    
    def __repr__(self):
        return f"<{self.name}>"


class MiddlewareChain:
    """
    Middleware lánc – egymásba ágyazott middleware-ek kezelése.
    """
    
    def __init__(self, middlewares: List[Middleware] = None, config: Dict = None):
        self.middlewares = middlewares or []
        self.config = config or {}
    
    def add(self, middleware: Middleware):
        """Middleware hozzáadása a lánc végéhez"""
        self.middlewares.append(middleware)
    
    def insert(self, index: int, middleware: Middleware):
        """Middleware beszúrása adott pozícióba"""
        self.middlewares.insert(index, middleware)
    
    def remove(self, name: str):
        """Middleware eltávolítása név alapján"""
        self.middlewares = [m for m in self.middlewares if m.name != name]
    
    def clear(self):
        """Minden middleware eltávolítása"""
        self.middlewares.clear()
    
    def process_request(self, request: Dict, final_handler: Callable) -> Dict:
        """
        Kérés feldolgozása a teljes middleware láncon.
        
        A middleware-ek a hozzáadás sorrendjében futnak.
        Minden middleware meghívja a következőt a láncban.
        """
        if not self.middlewares:
            return final_handler(request)
        
        # Lánc felépítése rekurzívan
        def build_chain(index: int) -> Callable:
            if index >= len(self.middlewares):
                return final_handler
            
            middleware = self.middlewares[index]
            
            def handler(req):
                return middleware.process_request(req, build_chain(index + 1))
            
            return handler
        
        first_handler = build_chain(0)
        return first_handler(request)
    
    def __repr__(self):
        return f"<MiddlewareChain: {[m.name for m in self.middlewares]}>"