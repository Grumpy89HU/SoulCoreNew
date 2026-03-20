# ==============================================
# SoulCore 3.0 - Web App Backend (app.py)
# Open WebUI ihletésű, tiszta struktúra
# ==============================================

import os
import time
import json
import uuid
import hashlib
import traceback
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Dict, Any, Optional

from flask import (
    Flask, render_template, send_from_directory, request,
    jsonify, session, g, redirect, url_for, make_response
)
from flask_socketio import SocketIO, emit, join_room, leave_room

# Projekt gyökér és modulok elérési útja
ROOT_DIR = Path(__file__).parent.parent.parent

# ----------------------------------------------------------------------
# SEGÉDFÜGGVÉNYEK
# ----------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Jelszó hash-elése"""
    salt = b"soulcore_salt_2026"
    return hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt,
        100000
    ).hex()

def verify_password(password: str, hashed: str) -> bool:
    """Jelszó ellenőrzése"""
    return hash_password(password) == hashed

# ----------------------------------------------------------------------
# FŐ WEBAPP OSZTÁLY
# ----------------------------------------------------------------------

class WebApp:
    """
    SoulCore webes felülete.
    - Flask backend REST API-val
    - Socket.IO valós idejű kommunikáció
    - Felhasználókezelés (session, admin)
    - Többnyelvű támogatás (i18n)
    - Beszélgetések, modellek, promptok kezelése
    - Admin felület modulvezérléssel
    """
    
    def __init__(self, modules: Dict[str, Any] = None):
        self.modules = modules or {}
        self.name = "web"
        self.system_id = str(uuid.uuid4())[:8]
        
        # Flask app
        self.app = Flask(
            __name__,
            template_folder=str(ROOT_DIR / "src" / "web" / "templates"),
            static_folder=str(ROOT_DIR / "src" / "web" / "static")
        )
        
        # Konfiguráció
        self.app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
        self.app.config["SESSION_TYPE"] = "filesystem"
        self.app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)
        self.app.config["SESSION_COOKIE_NAME"] = "soulcore_session"
        
        # Hibakezelés - JSON válaszok minden hibára
        @self.app.errorhandler(Exception)
        def handle_exception(e):
            """Globális hibakezelő - JSON válasz"""
            print(f"❌ Hiba: {e}")
            traceback.print_exc()
            return jsonify({
                "error": str(e),
                "type": e.__class__.__name__
            }), 500
        
        @self.app.errorhandler(404)
        def handle_404(e):
            """404 hibakezelő - JSON válasz API hívásoknál"""
            if request.path.startswith('/api/'):
                return jsonify({"error": "Not found"}), 404
            return render_template("404.html"), 404
        
        # Socket.IO
        self.socketio = SocketIO(
            self.app,
            cors_allowed_origins="*",
            ping_timeout=60,
            ping_interval=25,
            manage_session=False
        )
        
        # --- ALAPÉRTELMEZETT FELHASZNÁLÓK ---
        admin_password_hash = hash_password("admin123")
        print(f"🔐 Admin jelszó hash: {admin_password_hash[:20]}...")
        
        self.users = {
            "admin": {
                "id": 1,
                "username": "admin",
                "password_hash": admin_password_hash,
                "role": "admin",
                "email": "admin@localhost",
                "created_at": time.time()
            }
        }
        
        # Aktív session-ök (socket kapcsolatok)
        self.sessions = {}
        
        # Szál
        self.thread = None
        self.running = False
        
        # FEJLESZTŐI MÓD
        self.dev_mode = os.environ.get("DEV_MODE", "true").lower() == "true"
        if self.dev_mode:
            print("⚠️ WebApp: FEJLESZTŐI MÓDBAN FUT - hitelesítés kikapcsolva!")
        
        # Útvonalak regisztrálása
        self._register_routes()
        
        # Socket események regisztrálása
        self._register_socket_events()
        
        print(f"🌐 WebApp inicializálva (system_id: {self.system_id})")
    
    # ----------------------------------------------------------------------
    # DEKORÁTOROK
    # ----------------------------------------------------------------------
    
    def login_required(self, f):
        """Dekorátor: bejelentkezés szükséges"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if self.dev_mode:
                if "user_id" not in session:
                    session.permanent = True
                    session["user_id"] = 1
                    session["username"] = "admin"
                    session["role"] = "admin"
                return f(*args, **kwargs)
            
            if "user_id" not in session:
                return jsonify({"error": "Authentication required", "code": "UNAUTHORIZED"}), 401
            return f(*args, **kwargs)
        return decorated_function
    
    def admin_required(self, f):
        """Dekorátor: admin jogosultság szükséges"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if self.dev_mode:
                if "user_id" not in session:
                    session.permanent = True
                    session["user_id"] = 1
                    session["username"] = "admin"
                    session["role"] = "admin"
                return f(*args, **kwargs)
            
            if "user_id" not in session:
                return jsonify({"error": "Authentication required", "code": "UNAUTHORIZED"}), 401
            
            user_id = session["user_id"]
            user = self._get_user_by_id(user_id)
            
            if not user or user.get("role") != "admin":
                return jsonify({"error": "Admin privileges required", "code": "FORBIDDEN"}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    
    # ----------------------------------------------------------------------
    # FELHASZNÁLÓ KEZELÉS (BELSŐ)
    # ----------------------------------------------------------------------
    
    def _get_user_by_id(self, user_id: int) -> Optional[Dict]:
        for user in self.users.values():
            if user["id"] == user_id:
                return user
        return None
    
    def _get_user_by_username(self, username: str) -> Optional[Dict]:
        return self.users.get(username)
    
    def _get_user_by_email(self, email: str) -> Optional[Dict]:
        for user in self.users.values():
            if user["email"] == email:
                return user
        return None
    
    # ----------------------------------------------------------------------
    # REST API ÚTVONALAK
    # ----------------------------------------------------------------------
    
    def _register_routes(self):
        """Flask útvonalak regisztrálása"""
        
        # --- STATIKUS OLDALAK ---

        @self.app.route("/")
        def index():
            """Főoldal - egyszerű HTML fájl"""
            # Visszaadjuk a fájlt HTML-ként
            with open(ROOT_DIR / "src" / "web" / "templates" / "index.html", "r", encoding="utf-8") as f:
                html_content = f.read()
            return html_content, 200, {'Content-Type': 'text/html'}
        
        @self.app.route("/admin")
        @self.admin_required
        def admin_page():
            return render_template("admin.html")
        
        @self.app.route("/login")
        def login_page():
            if "user_id" in session:
                return redirect(url_for("index"))
            return render_template("login.html")
        
        @self.app.route("/register")
        def register_page():
            if "user_id" in session:
                return redirect(url_for("index"))
            return render_template("register.html")
        
        @self.app.route("/profile")
        @self.login_required
        def profile_page():
            return render_template("profile.html")
        
        # --- API: AUTH ---
        
        @self.app.route("/api/auth/login", methods=["POST"])
        def api_auth_login():
            data = request.get_json() or {}
            
            username = data.get("username", "").strip()
            password = data.get("password", "")
            
            if not username or not password:
                return jsonify({"error": "Username and password required"}), 400
            
            user = self._get_user_by_username(username)
            
            if not user or not verify_password(password, user["password_hash"]):
                return jsonify({"error": "Invalid username or password"}), 401
            
            session.permanent = True
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            
            return jsonify({
                "id": user["id"],
                "username": user["username"],
                "role": user["role"],
                "email": user["email"]
            })
        
        @self.app.route("/api/auth/logout", methods=["POST"])
        def api_auth_logout():
            session.clear()
            return jsonify({"success": True})
        
        @self.app.route("/api/auth/register", methods=["POST"])
        def api_auth_register():
            data = request.get_json() or {}
            
            username = data.get("username", "").strip()
            email = data.get("email", "").strip()
            password = data.get("password", "")
            
            if not username or not email or not password:
                return jsonify({"error": "All fields required"}), 400
            
            if self._get_user_by_username(username):
                return jsonify({"error": "Username already exists"}), 409
            
            if self._get_user_by_email(email):
                return jsonify({"error": "Email already exists"}), 409
            
            user_id = max([u["id"] for u in self.users.values()] + [0]) + 1
            
            self.users[username] = {
                "id": user_id,
                "username": username,
                "email": email,
                "password_hash": hash_password(password),
                "role": "user",
                "created_at": time.time()
            }
            
            return jsonify({"success": True, "id": user_id})
        
        @self.app.route("/api/auth/me")
        def api_auth_me():
            if self.dev_mode:
                return jsonify({
                    "authenticated": True,
                    "id": 1,
                    "username": "admin",
                    "role": "admin",
                    "email": "admin@localhost"
                })
            
            if "user_id" not in session:
                return jsonify({"authenticated": False})
            
            user = self._get_user_by_id(session["user_id"])
            
            if not user:
                session.clear()
                return jsonify({"authenticated": False})
            
            return jsonify({
                "authenticated": True,
                "id": user["id"],
                "username": user["username"],
                "role": user["role"],
                "email": user["email"]
            })
        
        @self.app.route("/api/auth/test")
        def api_auth_test():
            users_list = []
            for username, user in self.users.items():
                users_list.append({
                    "username": username,
                    "role": user["role"],
                    "email": user["email"]
                })
            return jsonify({
                "users": users_list,
                "dev_mode": self.dev_mode,
                "session": dict(session)
            })
        
        # --- API: RENDSZER STÁTUSZ ---
        
        @self.app.route("/api/status")
        def api_status():
            heartbeat = self.modules.get("heartbeat", {})
            sentinel = self.modules.get("sentinel")
            
            return jsonify({
                "status": "running",
                "system_id": self.system_id,
                "time": time.time(),
                "uptime": heartbeat.get_state().get("uptime_seconds", 0) if heartbeat else 0,
                "version": "3.0",
                "modules": list(self.modules.keys()),
                "clients": len(self.sessions),
                "gpu": sentinel.get_gpu_status() if sentinel else []
            })
        
        @self.app.route("/api/king/state")
        def api_king_state():
            king = self.modules.get("king")
            if not king:
                return jsonify({"error": "King module not available"}), 404
            return jsonify(king.get_state())
        
        @self.app.route("/api/sentinel/status")
        def api_sentinel_status():
            sentinel = self.modules.get("sentinel")
            if not sentinel:
                return jsonify({"error": "Sentinel module not available"}), 404
            
            return jsonify({
                "gpus": sentinel.get_gpu_status(),
                "slots": sentinel.get_slots(),
                "state": sentinel.get_state(),
                "throttle_factor": sentinel.get_throttle_factor()
            })
        
        # --- API: BESZÉLGETÉSEK ---
        
        @self.app.route("/api/conversations", methods=["GET"])
        @self.login_required
        def api_get_conversations():
            db = self.modules.get("database")
            if not db:
                return jsonify({"conversations": []})
            
            try:
                user_id = session["user_id"]
                limit = request.args.get("limit", 50, type=int)
                offset = request.args.get("offset", 0, type=int)
                
                conversations = db.get_conversations(
                    user_id=user_id,
                    limit=limit,
                    offset=offset
                )
                
                return jsonify({
                    "conversations": conversations,
                    "total": len(conversations),
                    "limit": limit,
                    "offset": offset
                })
            except Exception as e:
                print(f"❌ Hiba a beszélgetések lekérésekor: {e}")
                traceback.print_exc()
                return jsonify({"error": str(e), "conversations": []}), 200
        
        @self.app.route("/api/conversations", methods=["POST"])
        @self.login_required
        def api_create_conversation():
            db = self.modules.get("database")
            if not db:
                return jsonify({"error": "Database not available"}), 500
            
            data = request.get_json() or {}
            user_id = session["user_id"]
            
            conv_id = db.create_conversation(
                title=data.get("title", f"Beszélgetés {datetime.now().strftime('%Y-%m-%d %H:%M')}"),
                model=data.get("model"),
                system_prompt=data.get("system_prompt"),
                metadata=data.get("metadata"),
                user_id=user_id
            )
            
            return jsonify({"id": conv_id, "success": True})
        
        @self.app.route("/api/conversations/<int:conv_id>", methods=["GET"])
        @self.login_required
        def api_get_conversation(conv_id):
            db = self.modules.get("database")
            if not db:
                return jsonify({"error": "Database not available"}), 500
            
            conv = db.get_conversation(conv_id)
            
            if not conv:
                return jsonify({"error": "Conversation not found"}), 404
            
            if conv.get("user_id") != session["user_id"]:
                return jsonify({"error": "Access denied"}), 403
            
            return jsonify(conv)
        
        @self.app.route("/api/conversations/<int:conv_id>/messages", methods=["GET"])
        @self.login_required
        def api_get_messages(conv_id):
            db = self.modules.get("database")
            if not db:
                return jsonify({"error": "Database not available"}), 500
            
            limit = request.args.get("limit", 100, type=int)
            before = request.args.get("before", type=int)
            
            messages = db.get_messages(conv_id, limit=limit)
            
            if before:
                messages = [m for m in messages if m.get("timestamp", 0) < before]
                messages = messages[-limit:]
            
            return jsonify({
                "messages": messages,
                "count": len(messages)
            })
        
        @self.app.route("/api/conversations/<int:conv_id>/messages", methods=["POST"])
        @self.login_required
        def api_add_message(conv_id):
            db = self.modules.get("database")
            if not db:
                return jsonify({"error": "Database not available"}), 500
            
            data = request.get_json() or {}
            
            msg_id = db.add_message(
                conversation_id=conv_id,
                role=data.get("role", "user"),
                content=data.get("content", ""),
                tokens=data.get("tokens", 0),
                metadata=data.get("metadata")
            )
            
            return jsonify({"id": msg_id, "success": True})
        
        @self.app.route("/api/conversations/<int:conv_id>", methods=["DELETE"])
        @self.login_required
        def api_delete_conversation(conv_id):
            db = self.modules.get("database")
            if not db:
                return jsonify({"error": "Database not available"}), 500
            
            conv = db.get_conversation(conv_id)
            if not conv:
                return jsonify({"error": "Conversation not found"}), 404
            
            if conv.get("user_id") != session["user_id"]:
                return jsonify({"error": "Access denied"}), 403
            
            db.delete_conversation(conv_id)
            return jsonify({"success": True})
        
        # --- API: MODELLEK ---
        
        @self.app.route("/api/models", methods=["GET"])
        def api_get_models():
            db = self.modules.get("database")
            if not db:
                return jsonify({"models": []})
            
            active_only = request.args.get("active_only", "false").lower() == "true"
            models = db.get_models(active_only=active_only)
            
            return jsonify({"models": models})
        
        @self.app.route("/api/models/<int:model_id>/activate", methods=["POST"])
        @self.admin_required
        def api_activate_model(model_id):
            db = self.modules.get("database")
            if not db:
                return jsonify({"error": "Database not available"}), 500
            
            db.set_active_model(model_id)
            
            king = self.modules.get("king")
            if king and hasattr(king, "reload_model"):
                king.reload_model()
            
            return jsonify({"success": True})
        
        # --- API: PROMPTOK ---
        
        @self.app.route("/api/prompts", methods=["GET"])
        def api_get_prompts():
            db = self.modules.get("database")
            if not db:
                return jsonify({"prompts": []})
            
            category = request.args.get("category")
            prompts = db.get_prompts(category=category)
            
            return jsonify({"prompts": prompts})
        
        @self.app.route("/api/prompts", methods=["POST"])
        @self.admin_required
        def api_save_prompt():
            db = self.modules.get("database")
            if not db:
                return jsonify({"error": "Database not available"}), 500
            
            data = request.get_json() or {}
            
            prompt_id = db.save_prompt(
                name=data.get("name"),
                content=data.get("content"),
                description=data.get("description", ""),
                category=data.get("category", "general"),
                is_default=data.get("is_default", False)
            )
            
            return jsonify({"id": prompt_id, "success": True})
        
        @self.app.route("/api/prompts/<int:prompt_id>", methods=["DELETE"])
        @self.admin_required
        def api_delete_prompt(prompt_id):
            db = self.modules.get("database")
            if not db:
                return jsonify({"error": "Database not available"}), 500
            
            db.delete_prompt(prompt_id)
            return jsonify({"success": True})
        
        # --- API: MODUL VEZÉRLÉS (ADMIN) ---
        
        @self.app.route("/api/modules/<module_name>/<action>", methods=["POST"])
        @self.admin_required
        def api_control_module(module_name, action):
            module = self.modules.get(module_name)
            
            if not module:
                return jsonify({"error": f"Module '{module_name}' not found"}), 404
            
            try:
                if action == "start" and hasattr(module, "start"):
                    module.start()
                elif action == "stop" and hasattr(module, "stop"):
                    module.stop()
                elif action == "restart":
                    if hasattr(module, "stop"):
                        module.stop()
                    time.sleep(1)
                    if hasattr(module, "start"):
                        module.start()
                else:
                    return jsonify({"error": f"Action '{action}' not supported"}), 400
                
                return jsonify({"success": True})
            
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        
        # --- EGÉSZSÉGÜGYI ELLENŐRZÉS ---
        
        @self.app.route("/health")
        def health_check():
            return jsonify({
                "status": "healthy",
                "system_id": self.system_id,
                "timestamp": time.time()
            })
    
    # ----------------------------------------------------------------------
    # SOCKET.IO ESEMÉNYEK
    # ----------------------------------------------------------------------
    
    def _register_socket_events(self):
        """Socket.IO események regisztrálása"""
        
        @self.socketio.on("connect")
        def handle_connect():
            client_id = request.sid
            user_id = session.get("user_id")
            
            self.sessions[client_id] = {
                "connected_at": time.time(),
                "user_id": user_id,
                "ip": request.remote_addr,
                "user_agent": request.headers.get("User-Agent", "unknown")
            }
            
            emit("connected", {
                "status": "ok",
                "client_id": client_id,
                "authenticated": user_id is not None
            })
        
        @self.socketio.on("disconnect")
        def handle_disconnect():
            client_id = request.sid
            if client_id in self.sessions:
                del self.sessions[client_id]
        
        @self.socketio.on("auth:get_session")
        def handle_get_session(data=None):
            if self.dev_mode:
                emit("auth:session", {
                    "authenticated": True,
                    "id": 1,
                    "username": "admin",
                    "role": "admin",
                    "email": "admin@localhost"
                })
                return
            
            if "user_id" not in session:
                emit("auth:session", {"authenticated": False})
                return
            
            user = self._get_user_by_id(session["user_id"])
            
            if not user:
                emit("auth:session", {"authenticated": False})
                return
            
            emit("auth:session", {
                "authenticated": True,
                "id": user["id"],
                "username": user["username"],
                "role": user["role"],
                "email": user["email"]
            })
        
        @self.socketio.on("chat:message")
        def handle_chat_message(data):
            text = data.get("text", "").strip() if data else ""
            conv_id = data.get("conversation_id") if data else None
            
            if not text or not conv_id:
                emit("chat:error", {"error": "Missing text or conversation_id"})
                return
            
            orch = self.modules.get("orchestrator")
            
            if not orch:
                emit("chat:error", {"error": "Orchestrator not available"})
                return
            
            username = session.get("username", "User")
            packet = f"INTENT:UNKNOWN|USER:{username}|MESSAGE:{text}"
            
            result = orch.process_raw_packet(packet)
            
            if result and isinstance(result, dict) and "trace_id" in result:
                king = self.modules.get("king")
                
                if king:
                    response = king.process({
                        "header": {
                            "trace_id": result["trace_id"],
                            "timestamp": time.time(),
                            "sender": "web"
                        },
                        "payload": {
                            "intent": {
                                "class": result.get("packet", {}).get("INTENT", "unknown")
                            },
                            "text": text
                        }
                    })
                    
                    if response:
                        emit("chat:response", {
                            "text": response.get("payload", {}).get("response", ""),
                            "trace_id": result["trace_id"],
                            "conversation_id": conv_id
                        })
                        
                        db = self.modules.get("database")
                        if db:
                            db.add_message(conv_id, "user", text)
                            db.add_message(conv_id, "assistant", response.get("payload", {}).get("response", ""))
            
            emit("chat:ack", {"received": True})
        
        @self.socketio.on("chat:typing_start")
        def handle_typing_start(data):
            room = data.get("conversation_id") if data else None
            if room:
                emit("chat:typing_start", {"user": session.get("username", "User")}, room=room)
        
        @self.socketio.on("chat:typing_stop")
        def handle_typing_stop(data):
            room = data.get("conversation_id") if data else None
            if room:
                emit("chat:typing_stop", {"user": session.get("username", "User")}, room=room)
    
    # ----------------------------------------------------------------------
    # INDIÍTÁS / LEÁLLÍTÁS
    # ----------------------------------------------------------------------
    
    # ----------------------------------------------------------------------
# INDIÍTÁS / LEÁLLÍTÁS
# ----------------------------------------------------------------------

    def start(self, host="0.0.0.0", port=5000, debug=False):
        """Web szerver indítása (blokkoló hívás)"""
        self.running = True
        print(f"🌐 WebApp indul: http://{host}:{port}")
        if self.dev_mode:
            print("⚠️ FEJLESZTŐI MÓD: Bejelentkezés automatikusan admin-ként történik")
            print("🔐 Teszteléshez: admin / admin123")
        
        # JAVÍTVA: ne használjuk az allow_unsafe_werkzeug paramétert debug módban
        if debug:
            print("🐛 Debug mód bekapcsolva")
            # Debug módban ne használjuk az allow_unsafe_werkzeug-t
            self.socketio.run(self.app, host=host, port=port, debug=True)
        else:
            self.socketio.run(self.app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True)
    
    def start_thread(self):
        import threading
        self.thread = threading.Thread(target=self.start, daemon=True)
        self.thread.start()
        return self.thread
    
    def stop(self):
        self.running = False
        self.socketio.stop()
        print("🌐 WebApp leállítva")
    
    def get_state(self) -> Dict[str, Any]:
        return {
            "status": "running" if self.running else "stopped",
            "clients": len(self.sessions),
            "system_id": self.system_id,
            "uptime": time.time() - getattr(self.thread, "start_time", time.time())
        }


# ----------------------------------------------------------------------
# EGYSZERŰ FŐ PROGRAM
# ----------------------------------------------------------------------

if __name__ == "__main__":
    app = WebApp()
    app.start(host="0.0.0.0", port=5000, debug=True)