#!/usr/bin/env python3
"""
SoulCore Statikus Webszerver
Csak statikus fájlokat szolgál ki a web/ mappából.
Teljes funkcionalitással: 404, 403, 500, cache, range, stb.
"""

import os
import sys
import time
import json
import email
import mimetypes
import threading
import signal
import socket
import argparse
from pathlib import Path
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import unquote, urlparse
from datetime import datetime
import logging

# ============================================================
# KONFIGURÁCIÓ
# ============================================================

# Web root könyvtár (a szkript helyéhez képest)
WEB_ROOT = Path(__file__).parent.parent / 'web'

# Szerver beállítások
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8080

# Logging beállítása
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================
# STATIKUS FÁJL HANDLER
# ============================================================

class StaticFileHandler(BaseHTTPRequestHandler):
    """
    Statikus fájlokat kiszolgáló handler.
    Teljes funkcionalitással: 404, 403, 500, cache, range, stb.
    """
    
    # Alapértelmezett MIME típus
    DEFAULT_MIME = 'application/octet-stream'
    
    # Cache méret
    MAX_CACHE_SIZE = 100
    _file_cache = {}  # path -> (content, mime, last_modified, size, etag)
    _cache_lock = threading.RLock()
    
    # Engedélyezett fájlok (whitelist)
    ALLOWED_EXTENSIONS = {
        '.html', '.htm', '.css', '.js', '.mjs', '.json', '.xml', '.txt',
        '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.webp',
        '.woff', '.woff2', '.ttf', '.eot', '.otf',
        '.mp3', '.mp4', '.webm', '.ogg',
        '.pdf', '.doc', '.docx', '.zip', '.tar', '.gz'
    }
    
    # Tiltott elérési utak (mappák, fájlok)
    FORBIDDEN_PATHS = {
        '.git', '.env', '.pyc', '__pycache__', '.DS_Store',
        'config', 'data', 'models', 'logs', 'src', 'server'
    }
    
    # Tiltott karakterek path-ban
    FORBIDDEN_CHARS = {'..', '//', '\\', '%00', '%2e', '%2f', ';', '&', '|', '`', '$'}
    
    def __init__(self, *args, **kwargs):
        self.web_root = WEB_ROOT
        super().__init__(*args, **kwargs)
    
    def log_message(self, format, *args):
        """Naplózás"""
        logger.info(f"{self.address_string()} - {format % args}")
    
    def log_error(self, format, *args):
        """Hiba naplózás"""
        logger.error(f"{self.address_string()} - {format % args}")
    
    # ========== KÉRELEM KEZELÉS ==========
    
    def do_GET(self):
        """GET kérés kezelése"""
        try:
            self._handle_request()
        except ConnectionResetError:
            pass  # Klient megszakította a kapcsolatot
        except Exception as e:
            logger.exception(f"Unexpected error: {e}")
            self.send_error(500, "Internal Server Error")
    
    def do_HEAD(self):
        """HEAD kérés kezelése (csak fejlécek)"""
        try:
            self._handle_request(head_only=True)
        except Exception as e:
            logger.exception(f"Unexpected error: {e}")
            self.send_error(500, "Internal Server Error")
    
    def do_POST(self):
        """POST kérés nem engedélyezett"""
        self.send_error(405, "Method Not Allowed")
    
    def do_PUT(self):
        """PUT kérés nem engedélyezett"""
        self.send_error(405, "Method Not Allowed")
    
    def do_DELETE(self):
        """DELETE kérés nem engedélyezett"""
        self.send_error(405, "Method Not Allowed")
    
    # ========== KÉRELEM FELDOLGOZÁS ==========
    
    def _handle_request(self, head_only=False):
        """Kérelem feldolgozása"""
        # URL dekódolás
        try:
            path = unquote(self.path)
        except Exception:
            self.send_error(400, "Bad Request")
            return
        
        # URL parsing
        parsed = urlparse(path)
        path = parsed.path
        
        # Egészségügyi ellenőrzés (monitoring)
        if path == '/health':
            self._handle_health()
            return
        
        # Root path
        if path == '' or path == '/':
            path = '/index.html'
        
        # Biztonsági ellenőrzések
        if not self._security_check(path):
            return
        
        # Fájl keresés
        file_path = self._find_file(path)
        if file_path is None:
            self._handle_404(path)
            return
        
        # Fájl kiszolgálás
        self._serve_file(file_path, head_only)
    
    # ========== BIZTONSÁGI ELLENŐRZÉSEK ==========
    
    def _security_check(self, path: str) -> bool:
        """
        Biztonsági ellenőrzések.
        Returns: True ha biztonságos, False ha tiltott.
        """
        # Tiltott karakterek
        for char in self.FORBIDDEN_CHARS:
            if char in path:
                self.send_error(403, "Forbidden")
                logger.warning(f"Forbidden path: {self.address_string()} - {path}")
                return False
        
        # Path traversal ellenőrzés
        try:
            # A kért útvonalat a web_root-hoz adjuk
            requested_path = self.web_root / path.lstrip('/')
            # Feloldjuk a valós útvonalat
            real_path = requested_path.resolve()
            web_root_resolved = self.web_root.resolve()
            
            # Ellenőrizzük, hogy a valós útvonal a web_root alatt van-e
            if web_root_resolved not in real_path.parents and real_path != web_root_resolved:
                self.send_error(403, "Forbidden")
                logger.warning(f"Path traversal attempt: {self.address_string()} - {path} -> {real_path}")
                return False
        except Exception as e:
            self.send_error(403, "Forbidden")
            logger.warning(f"Path check error: {e}")
            return False
        
        # Fájlkiterjesztés ellenőrzés
        ext = Path(path).suffix.lower()
        if ext and ext not in self.ALLOWED_EXTENSIONS:
            self.send_error(403, "Forbidden")
            logger.warning(f"Disallowed extension: {self.address_string()} - {path}")
            return False
        
        # Tiltott mappák
        path_parts = Path(path).parts
        for forbidden in self.FORBIDDEN_PATHS:
            if forbidden in path_parts:
                self.send_error(403, "Forbidden")
                logger.warning(f"Forbidden directory: {self.address_string()} - {path}")
                return False
        
        return True
    
    # ========== FÁJL KEZELÉS ==========
    
    def _find_file(self, path: str) -> Path:
        """
        Fájl keresése a web_root alatt.
        Returns: Path objektum vagy None.
        """
        # Normalizált útvonal
        clean_path = path.lstrip('/')
        file_path = self.web_root / clean_path
        
        # Létezik és fájl?
        if file_path.exists() and file_path.is_file():
            return file_path
        
        # Directory? -> index.html keresés
        if file_path.exists() and file_path.is_dir():
            index_path = file_path / 'index.html'
            if index_path.exists():
                return index_path
        
        # Nem található
        return None
    
    def _get_mime_type(self, file_path: Path) -> str:
        """MIME típus lekérése"""
        mime, _ = mimetypes.guess_type(str(file_path))
        return mime or self.DEFAULT_MIME
    
    def _generate_etag(self, stat) -> str:
        """ETag generálás (módosítási idő + méret alapján)"""
        return f'"{stat.st_mtime}-{stat.st_size}"'
    
    def _get_file_info(self, file_path: Path) -> dict:
        """
        Fájl info lekérése (cache-elve).
        Returns: dict with 'content', 'mime', 'size', 'last_modified', 'etag'
        """
        cache_key = str(file_path)
        
        with self._cache_lock:
            if cache_key in self._file_cache:
                cached = self._file_cache[cache_key]
                # Ellenőrizzük, hogy a fájl nem változott-e
                if cached['last_modified'] == file_path.stat().st_mtime:
                    return cached
        
        # Fájl beolvasása
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            
            stat = file_path.stat()
            mime = self._get_mime_type(file_path)
            size = stat.st_size
            last_modified = stat.st_mtime
            etag = self._generate_etag(stat)
            
            info = {
                'content': content,
                'mime': mime,
                'size': size,
                'last_modified': last_modified,
                'etag': etag
            }
            
            # Cache
            with self._cache_lock:
                if len(self._file_cache) >= self.MAX_CACHE_SIZE:
                    # Egyszerű LRU: töröljük a legrégebbit
                    oldest = min(self._file_cache.keys(), 
                                key=lambda k: self._file_cache[k]['last_modified'])
                    del self._file_cache[oldest]
                self._file_cache[cache_key] = info
            
            return info
            
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            raise
    
    def _check_cache(self, info: dict) -> bool:
        """
        Cache ellenőrzés (If-Modified-Since, If-None-Match).
        Returns: True ha cache-ből lehet tölteni (304).
        """
        # If-None-Match (ETag)
        if_none_match = self.headers.get('If-None-Match')
        if if_none_match and if_none_match == info['etag']:
            return True
        
        # If-Modified-Since
        if_modified_since = self.headers.get('If-Modified-Since')
        if if_modified_since:
            try:
                since = email.utils.parsedate_to_datetime(if_modified_since).timestamp()
                if since >= info['last_modified']:
                    return True
            except:
                pass
        
        return False
    
    # ========== VÁLASZ KÜLDÉS (JAVÍTVA - HTTP/1.1) ==========
    
    def _send_headers(self, status: int, headers: dict, extra_headers: list = None):
        """
        Egységes fejléc küldés HTTP/1.1 formátumban.
        """
        self.send_response(status)
        
        for key, value in headers.items():
            self.send_header(key, value)
        
        if extra_headers:
            for key, value in extra_headers:
                self.send_header(key, value)
        
        self.end_headers()
    
    def _serve_file(self, file_path: Path, head_only=False):
        """Fájl kiszolgálása - JAVÍTVA!"""
        try:
            info = self._get_file_info(file_path)
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
            self.send_error(500, "Internal Server Error")
            return
        
        # Cache ellenőrzés
        if self._check_cache(info):
            self.send_response(304)
            self.end_headers()
            return
        
        # Alap fejlécek
        content_type = info['mime']
        if content_type == 'text/html':
            content_type = 'text/html; charset=utf-8'
        
        headers = {
            'Content-Type': content_type,
            'Content-Length': str(info['size']),
            'Last-Modified': email.utils.formatdate(info['last_modified'], usegmt=True),
            'ETag': info['etag'],
            'Cache-Control': 'public, max-age=3600',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Connection': 'keep-alive'
        }
        
        # HEAD kérés esetén csak fejlécek
        if head_only:
            self._send_headers(200, headers)
            return
        
        # Range request kezelés
        range_header = self.headers.get('Range')
        if range_header:
            self._send_range_response(info, range_header)
            return
        
        # Teljes fájl küldése
        self._send_headers(200, headers)
        try:
            self.wfile.write(info['content'])
        except (BrokenPipeError, ConnectionResetError):
            pass
    
    def _send_range_response(self, info: dict, range_header: str):
        """
        Range request kezelése (részleges letöltés).
        """
        try:
            # Range: bytes=start-end
            range_str = range_header.split('=')[1]
            start, end = range_str.split('-')
            start = int(start) if start else 0
            end = int(end) if end else info['size'] - 1
            
            # Ellenőrzés
            if start < 0 or end >= info['size'] or start > end:
                self.send_error(416, "Range Not Satisfiable")
                return
            
            content = info['content'][start:end+1]
            content_length = len(content)
            
            content_type = info['mime']
            if content_type == 'text/html':
                content_type = 'text/html; charset=utf-8'
            
            headers = {
                'Content-Type': content_type,
                'Content-Length': str(content_length),
                'Content-Range': f'bytes {start}-{end}/{info["size"]}',
                'Last-Modified': email.utils.formatdate(info['last_modified'], usegmt=True),
                'ETag': info['etag'],
                'Cache-Control': 'public, max-age=3600',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Connection': 'keep-alive'
            }
            
            self._send_headers(206, headers)
            self.wfile.write(content)
            
        except Exception as e:
            logger.error(f"Range request error: {e}")
            self.send_error(500, "Internal Server Error")
    
    def _handle_health(self):
        """Egészségügyi ellenőrzés (monitoring)"""
        headers = {'Content-Type': 'application/json'}
        self._send_headers(200, headers)
        
        health_data = {
            'status': 'healthy',
            'timestamp': time.time(),
            'web_root': str(self.web_root),
            'server': 'SoulCore Static Server'
        }
        self.wfile.write(json.dumps(health_data).encode())
    
    def _handle_404(self, path: str):
        """404 kezelés - egyedi 404 oldal"""
        # Próbáljuk meg a custom 404 oldalt
        custom_404 = self.web_root / '404.html'
        if custom_404.exists():
            try:
                with open(custom_404, 'rb') as f:
                    content = f.read()
                
                headers = {
                    'Content-Type': 'text/html; charset=utf-8',
                    'Content-Length': str(len(content))
                }
                self._send_headers(404, headers)
                self.wfile.write(content)
                return
            except:
                pass
        
        # Alapértelmezett 404
        self.send_error(404, "File not found")
        logger.info(f"404: {self.address_string()} - {path}")
    
    def send_error(self, code, message=None):
        """Hiba küldése - felülírva a helyes HTTP/1.1 formátumhoz"""
        try:
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Connection', 'close')
            self.end_headers()
            
            error_body = json.dumps({
                'error': code,
                'message': message or self.responses.get(code, ('', ''))[0],
                'timestamp': time.time(),
                'path': self.path
            })
            self.wfile.write(error_body.encode())
        except:
            pass


# ============================================================
# SZERVER KEZELŐ (ThreadingHTTPServer - graceful shutdown)
# ============================================================

class StaticServer:
    """
    Statikus webszerver kezelő.
    ThreadingHTTPServer-t használ a graceful shutdown-hoz.
    """
    
    def __init__(self, host=None, port=None, web_root=None):
        self.host = host or SERVER_HOST
        self.port = port or SERVER_PORT
        self.web_root = Path(web_root) if web_root else WEB_ROOT
        self.server = None
        self.running = False
        self.server_thread = None
    
    def _create_handler(self):
        """Handler osztály létrehozása a web_root beállítással"""
        class ConfiguredHandler(StaticFileHandler):
            web_root = self.web_root
        return ConfiguredHandler
    
    def start(self):
        """Szerver indítása"""
        # Web root ellenőrzés
        if not self.web_root.exists():
            logger.warning(f"Web root nem található: {self.web_root}")
            logger.info("Létrehozom...")
            self.web_root.mkdir(parents=True, exist_ok=True)
            
            # Alapértelmezett index.html
            index_path = self.web_root / 'index.html'
            if not index_path.exists():
                with open(index_path, 'w', encoding='utf-8') as f:
                    f.write("""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>SoulCore</title>
    <style>
        body {
            font-family: system-ui, -apple-system, sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
            background: #0a0a0a;
            color: #e0e0e0;
        }
        h1 {
            color: #ffd966;
        }
        .status {
            background: #1a1a1a;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #ffd966;
        }
        code {
            background: #2a2a2a;
            padding: 2px 6px;
            border-radius: 4px;
        }
    </style>
</head>
<body>
    <h1>🏰 SoulCore</h1>
    <div class="status">
        <p>✅ Statikus webszerver fut.</p>
        <p>🌐 A SoulCore API a következő címen érhető el: <code>http://localhost:5000</code></p>
        <p>📡 WebSocket: <code>ws://localhost:5000/ws</code></p>
    </div>
</body>
</html>""")
        
        # Szerver indítása (ThreadingHTTPServer)
        handler_class = self._create_handler()
        self.server = ThreadingHTTPServer((self.host, self.port), handler_class)
        self.running = True
        
        print("=" * 50)
        print("🏰 SoulCore Statikus Webszerver")
        print("=" * 50)
        print(f"   Host: {self.host}")
        print(f"   Port: {self.port}")
        print(f"   Web root: {self.web_root}")
        print(f"   MIME types: {len(StaticFileHandler.ALLOWED_EXTENSIONS)} engedélyezett")
        print("=" * 50)
        print("   Csak statikus fájlokat szolgál ki")
        print("   API végpontokat NEM kezel")
        print("=" * 50)
        print("🚀 Szerver indul...")
        print(f"🌐 http://{self.host}:{self.port}")
        print("=" * 50)
        
        try:
            self.server.serve_forever()
        except KeyboardInterrupt:
            self.stop()
        except Exception as e:
            logger.error(f"Szerver hiba: {e}")
            self.stop()
    
    def start_in_thread(self):
        """Szerver indítása külön szálban"""
        self.server_thread = threading.Thread(target=self.start, daemon=True)
        self.server_thread.start()
        return self.server_thread
    
    def stop(self):
        """Szerver leállítása (graceful)"""
        if not self.running:
            return
        
        print("\n🛑 Statikus webszerver leállítása...")
        self.running = False
        
        if self.server:
            # Shutdown a szervernek
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        
        # Várunk a szál befejeződésére
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=5.0)
        
        print("✅ Statikus webszerver leállítva")
    
    def is_running(self):
        """Szerver fut-e"""
        return self.running and self.server is not None


# ============================================================
# FŐ PROGRAM
# ============================================================

def main():
    """Fő program"""
    parser = argparse.ArgumentParser(description='SoulCore Statikus Webszerver')
    parser.add_argument('--host', default=SERVER_HOST, help=f'Host cím (alap: {SERVER_HOST})')
    parser.add_argument('--port', type=int, default=SERVER_PORT, help=f'Port szám (alap: {SERVER_PORT})')
    parser.add_argument('--web-root', help='Web root könyvtár (alap: ./web)')
    args = parser.parse_args()
    
    # Web root beállítás
    web_root = args.web_root
    if web_root:
        web_root = Path(web_root)
    else:
        web_root = WEB_ROOT
    
    # Szerver indítása
    server = StaticServer(
        host=args.host,
        port=args.port,
        web_root=web_root
    )
    
    # Signal kezelés
    def signal_handler(signum, frame):
        print("\n⚠️ Signal fogadva...")
        server.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    server.start()


if __name__ == "__main__":
    main()