# ==============================================
# SoulCore 3.0 - Web App Backend
# Flask + Socket.IO, teljes API készlettel
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

# Projekt gyökér
ROOT_DIR = Path(__file__).parent.parent.parent

# ----------------------------------------------------------------------
# SEGÉDFÜGGVÉNYEK
# ----------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Jelszó hash-elése (PBKDF2)"""
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
    - Beszélgetések, modellek, promptok, személyiségek
    - Embedding/Reranker, Audio (ASR/TTS), Vision, Sandbox, Gateway
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
        self.app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)
        self.app.config["SESSION_COOKIE_NAME"] = "soulcore_session"
        
        # Hibakezelő
        @self.app.errorhandler(Exception)
        def handle_exception(e):
            traceback.print_exc()
            return jsonify({"error": str(e), "type": e.__class__.__name__}), 500
        
        @self.app.errorhandler(404)
        def handle_404(e):
            if request.path.startswith('/api/'):
                return jsonify({"error": "Not found"}), 404
            # Ha nincs 404.html, visszaadjuk a base.html-t
            try:
                return render_template("404.html"), 404
            except:
                return "<h1>404 - Page not found</h1><p>The page you are looking for does not exist.</p>", 404
        
        # Socket.IO
        self.socketio = SocketIO(
            self.app,
            cors_allowed_origins="*",
            ping_timeout=60,
            ping_interval=25,
            manage_session=False  # Fontos a session kezeléshez!
        )
        
        # --- ALAPÉRTELMEZETT FELHASZNÁLÓK ---
        admin_hash = hash_password("admin123")
        self.users = {
            "admin": {
                "id": 1,
                "username": "admin",
                "password_hash": admin_hash,
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
            print("⚠️ FEJLESZTŐI MÓD - automatikus admin bejelentkezés")
        
        # Beállítások tároló (memória)
        self.settings = {
            "embedding": {
                "engine": "sentence-transformers",
                "model": "all-MiniLM-L6-v2",
                "batch_size": 32,
                "enable_reranker": False,
                "reranker_engine": "cross-encoder",
                "reranker_model": "cross-encoder/ms-marco-MiniLM-L-6-v2",
                "top_k": 10,
                "vector_db": "qdrant",
                "qdrant_url": "http://localhost:6333",
                "collection_name": "soulcore_knowledge"
            },
            "asr": {
                "engine": "whisper",
                "whisper_model": "base",
                "language": "auto"
            },
            "tts": {
                "engine": "coqui",
                "coqui_model": "tts_models/hu/cess_cat",
                "voice": "default",
                "speed": 1.0
            },
            "gateways": []
        }
        
        # Útvonalak regisztrálása
        self._register_routes()
        
        # Socket események
        self._register_socket_events()
        
        print(f"🌐 WebApp inicializálva (system_id: {self.system_id})")
    
    # ----------------------------------------------------------------------
    # DEKORÁTOROK
    # ----------------------------------------------------------------------
    
    def login_required(self, f):
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
                return jsonify({"error": "Authentication required"}), 401
            
            user = self._get_user_by_id(session["user_id"])
            if not user or user.get("role") != "admin":
                return jsonify({"error": "Admin required"}), 403
            return f(*args, **kwargs)
        return decorated_function
    
    # ----------------------------------------------------------------------
    # FELHASZNÁLÓ KEZELÉS
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
            return render_template("base.html")
        
        @self.app.route("/admin")
        @self.admin_required
        def admin_page():
            return render_template("base.html")
        
        @self.app.route("/login")
        def login_page():
            if "user_id" in session:
                return redirect(url_for("index"))
            return render_template("base.html")
        
        @self.app.route("/register")
        def register_page():
            if "user_id" in session:
                return redirect(url_for("index"))
            return render_template("base.html")
        
        @self.app.route("/profile")
        @self.login_required
        def profile_page():
            return render_template("base.html")
        
        @self.app.route("/static/<path:filename>")
        def static_files(filename):
            return send_from_directory(str(ROOT_DIR / "src" / "web" / "static"), filename)
        
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
                return jsonify({"error": "Invalid credentials"}), 401
            
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
        
        # --- API: RENDSZER ---
        
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
                print(f"❌ Hiba: {e}")
                return jsonify({"conversations": [], "error": str(e)}), 200
        
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
        
        @self.app.route("/api/conversations/<int:conv_id>/messages", methods=["GET"])
        @self.login_required
        def api_get_messages(conv_id):
            db = self.modules.get("database")
            if not db:
                return jsonify({"error": "Database not available"}), 500
            
            limit = request.args.get("limit", 100, type=int)
            messages = db.get_messages(conv_id, limit=limit)
            
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
            
            db.delete_conversation(conv_id)
            return jsonify({"success": True})
        
        # --- API: MODELLEK ---
        
        @self.app.route("/api/models", methods=["GET"])
        def api_get_models():
            db = self.modules.get("database")
            if not db:
                return jsonify({"models": []})
            
            models = db.get_models()
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
        
        @self.app.route("/api/models", methods=["POST"])
        @self.admin_required
        def api_add_model():
            db = self.modules.get("database")
            if not db:
                return jsonify({"error": "Database not available"}), 500
            
            data = request.get_json() or {}
            
            model_id = db.add_model(
                name=data.get("name"),
                path=data.get("path"),
                quantization=data.get("quantization"),
                context_length=data.get("context_length", 4096),
                n_gpu_layers=data.get("n_gpu_layers", -1),
                description=data.get("description")
            )
            
            return jsonify({"id": model_id, "success": True})
        
        @self.app.route("/api/models/<int:model_id>", methods=["DELETE"])
        @self.admin_required
        def api_delete_model(model_id):
            db = self.modules.get("database")
            if not db:
                return jsonify({"error": "Database not available"}), 500
            
            db.delete_model(model_id)
            return jsonify({"success": True})
        
        # --- API: PROMPTOK ---
        
        @self.app.route("/api/prompts", methods=["GET"])
        def api_get_prompts():
            db = self.modules.get("database")
            if not db:
                return jsonify({"prompts": []})
            
            prompts = db.get_prompts()
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
        
        # --- API: SZEMÉLYISÉGEK ---
        
        @self.app.route("/api/personalities", methods=["GET"])
        def api_get_personalities():
            db = self.modules.get("database")
            if not db:
                return jsonify({"personalities": []})
            
            personalities = db.get_personalities()
            return jsonify({"personalities": personalities})
        
        @self.app.route("/api/personalities", methods=["POST"])
        @self.admin_required
        def api_save_personality():
            db = self.modules.get("database")
            if not db:
                return jsonify({"error": "Database not available"}), 500
            
            data = request.get_json() or {}
            
            personality_id = db.save_personality(
                name=data.get("name"),
                motto=data.get("motto"),
                description=data.get("description"),
                traits=data.get("traits", []),
                relationships=data.get("relationships", []),
                content=data.get("content"),
                is_default=data.get("is_default", False)
            )
            
            return jsonify({"id": personality_id, "success": True})
        
        @self.app.route("/api/personalities/<int:personality_id>/activate", methods=["POST"])
        @self.admin_required
        def api_activate_personality(personality_id):
            db = self.modules.get("database")
            if not db:
                return jsonify({"error": "Database not available"}), 500
            
            db.activate_personality(personality_id)
            return jsonify({"success": True})
        
        @self.app.route("/api/personalities/<int:personality_id>", methods=["DELETE"])
        @self.admin_required
        def api_delete_personality(personality_id):
            db = self.modules.get("database")
            if not db:
                return jsonify({"error": "Database not available"}), 500
            
            db.delete_personality(personality_id)
            return jsonify({"success": True})
        
        # --- API: EMBEDDING ---
        
        @self.app.route("/api/embedding/settings", methods=["GET"])
        def api_get_embedding_settings():
            return jsonify(self.settings.get("embedding", {}))
        
        @self.app.route("/api/embedding/settings", methods=["POST"])
        @self.admin_required
        def api_update_embedding_settings():
            data = request.get_json() or {}
            self.settings["embedding"] = {**self.settings.get("embedding", {}), **data}
            return jsonify({"success": True})
        
        @self.app.route("/api/embedding/test", methods=["POST"])
        @self.login_required
        def api_test_embedding():
            data = request.get_json() or {}
            text = data.get("text", "")
            settings = data.get("settings", self.settings.get("embedding", {}))
            
            if not text:
                return jsonify({"error": "Text required"}), 400
            
            # Demo válasz (valós implementáció később)
            return jsonify({
                "dimension": 384,
                "vector": [0.1, 0.2, 0.3, 0.4, 0.5] + [0.0] * 379
            })
        
        # --- API: AUDIO (ASR/TTS) ---
        
        @self.app.route("/api/audio/asr/settings", methods=["GET"])
        def api_get_asr_settings():
            return jsonify(self.settings.get("asr", {}))
        
        @self.app.route("/api/audio/asr/settings", methods=["POST"])
        @self.admin_required
        def api_update_asr_settings():
            data = request.get_json() or {}
            self.settings["asr"] = {**self.settings.get("asr", {}), **data}
            return jsonify({"success": True})
        
        @self.app.route("/api/audio/tts/settings", methods=["GET"])
        def api_get_tts_settings():
            return jsonify(self.settings.get("tts", {}))
        
        @self.app.route("/api/audio/tts/settings", methods=["POST"])
        @self.admin_required
        def api_update_tts_settings():
            data = request.get_json() or {}
            self.settings["tts"] = {**self.settings.get("tts", {}), **data}
            return jsonify({"success": True})
        
        @self.app.route("/api/audio/transcribe", methods=["POST"])
        @self.login_required
        def api_transcribe_audio():
            if 'audio' not in request.files:
                return jsonify({"error": "No audio file"}), 400
            
            file = request.files['audio']
            # Demo válasz (valós implementáció később)
            return jsonify({"text": "Ez egy demo beszédfelismerési eredmény."})
        
        @self.app.route("/api/audio/synthesize", methods=["POST"])
        @self.login_required
        def api_synthesize_speech():
            data = request.get_json() or {}
            text = data.get("text", "")
            settings = data.get("settings", self.settings.get("tts", {}))
            
            if not text:
                return jsonify({"error": "Text required"}), 400
            
            # Demo válasz (valós implementáció később)
            # Itt egy üres audio fájlt adunk vissza
            return jsonify({"success": True, "message": "Audio szintézis (demo)"})
        
        # --- API: VISION ---
        
        @self.app.route("/api/vision/process", methods=["POST"])
        @self.login_required
        def api_process_image():
            data = request.get_json() or {}
            image = data.get("image", "")
            settings = data.get("settings", {})
            
            if not image:
                return jsonify({"error": "No image data"}), 400
            
            # Demo válasz (valós implementáció később)
            return jsonify({
                "success": True,
                "description": "Ez egy demo képfeldolgozási eredmény.",
                "ocr_text": "Demo OCR szöveg",
                "entities": ["demo", "entity"]
            })
        
        # --- API: SANDBOX ---
        
        @self.app.route("/api/sandbox/execute", methods=["POST"])
        @self.admin_required
        def api_execute_code():
            data = request.get_json() or {}
            code = data.get("code", "")
            language = data.get("language", "python")
            timeout = data.get("timeout", 30)
            memory_limit = data.get("memory_limit", 512)
            network_access = data.get("network_access", False)
            
            if not code:
                return jsonify({"error": "No code to execute"}), 400
            
            # Demo válasz (valós implementáció később)
            return jsonify({
                "output": f"Demo kimenet a {language} kódhoz:\n{code[:100]}...",
                "error": None,
                "execution_time": 0.1,
                "memory_used": 10
            })
        
        # --- API: GATEWAY ---
        
        @self.app.route("/api/gateway/status", methods=["GET"])
        def api_get_gateways():
            return jsonify({"gateways": self.settings.get("gateways", [])})
        
        @self.app.route("/api/gateway", methods=["POST"])
        @self.admin_required
        def api_add_gateway():
            data = request.get_json() or {}
            gateways = self.settings.get("gateways", [])
            new_id = max([g.get("id", 0) for g in gateways] + [0]) + 1
            
            gateway = {
                "id": new_id,
                "name": data.get("name", ""),
                "type": data.get("type", "custom"),
                "endpoint": data.get("endpoint", ""),
                "api_key": data.get("api_key", ""),
                "model": data.get("model", ""),
                "status": "offline",
                "trust_score": 500,
                "created_at": time.time()
            }
            
            gateways.append(gateway)
            self.settings["gateways"] = gateways
            
            return jsonify({"id": new_id, "success": True})
        
        @self.app.route("/api/gateway/<int:gateway_id>", methods=["PUT"])
        @self.admin_required
        def api_update_gateway(gateway_id):
            data = request.get_json() or {}
            gateways = self.settings.get("gateways", [])
            
            for g in gateways:
                if g["id"] == gateway_id:
                    g.update(data)
                    break
            
            self.settings["gateways"] = gateways
            return jsonify({"success": True})
        
        @self.app.route("/api/gateway/<int:gateway_id>", methods=["DELETE"])
        @self.admin_required
        def api_delete_gateway(gateway_id):
            gateways = self.settings.get("gateways", [])
            self.settings["gateways"] = [g for g in gateways if g["id"] != gateway_id]
            return jsonify({"success": True})
        
        @self.app.route("/api/gateway/<int:gateway_id>/test", methods=["POST"])
        @self.admin_required
        def api_test_gateway(gateway_id):
            gateways = self.settings.get("gateways", [])
            gateway = next((g for g in gateways if g["id"] == gateway_id), None)
            
            if not gateway:
                return jsonify({"error": "Gateway not found"}), 404
            
            # Demo válasz
            gateway["status"] = "online"
            gateway["last_communication"] = time.time()
            gateway["trust_score"] = min(gateway.get("trust_score", 500) + 50, 1000)
            
            return jsonify({"success": True, "status": "online"})
        
        @self.app.route("/api/gateway/message", methods=["POST"])
        @self.login_required
        def api_gateway_message():
            data = request.get_json() or {}
            gateway_id = data.get("gateway_id")
            message = data.get("message", "")
            
            if not gateway_id or not message:
                return jsonify({"error": "Gateway ID and message required"}), 400
            
            # Demo válasz
            return jsonify({
                "text": f"Demo válasz a(z) {gateway_id} gateway-től: {message}"
            })
        
        # --- API: BEÁLLÍTÁSOK ---
        
        @self.app.route("/api/settings", methods=["GET"])
        def api_get_settings():
            category = request.args.get("category")
            if category:
                return jsonify(self.settings.get(category, {}))
            return jsonify(self.settings)
        
        @self.app.route("/api/settings/<category>", methods=["POST"])
        @self.admin_required
        def api_update_settings(category):
            data = request.get_json() or {}
            self.settings[category] = {**self.settings.get(category, {}), **data}
            return jsonify({"success": True})
        
        # --- API: AUDIT LOG (demo) ---
        
        @self.app.route("/api/audit", methods=["GET"])
        @self.admin_required
        def api_get_audit_log():
            limit = request.args.get("limit", 100, type=int)
            
            # Demo audit log
            logs = []
            for i in range(min(limit, 50)):
                logs.append({
                    "id": i,
                    "timestamp": time.time() - i * 3600,
                    "user": "admin" if i % 3 == 0 else "user1",
                    "action": ["login", "logout", "create_conversation", "delete_conversation"][i % 4],
                    "resource": f"resource_{i % 10}",
                    "details": {"key": "value"},
                    "ip": "127.0.0.1",
                    "level": ["info", "warning", "error"][i % 3]
                })
            
            return jsonify({"audit_log": logs})
        
        # --- API: METRIKÁK ---
        
        @self.app.route("/api/metrics", methods=["GET"])
        @self.admin_required
        def api_get_metrics():
            period = request.args.get("period", "day")
            limit = request.args.get("limit", 100, type=int)
            
            points = 24 if period == "day" else (7 if period == "week" else 30)
            
            # Demo metrikák
            timestamps = [time.time() - i * 3600 for i in range(points, 0, -1)]
            
            return jsonify({
                "total_messages": 1234,
                "total_tokens": 56789,
                "avg_response_time": 450,
                "active_users": 3,
                "timestamps": timestamps,
                "tokens": [100 + i * 10 for i in range(points)],
                "responses": [50 + i * 5 for i in range(points)],
                "conversations": [1 + i // 4 for i in range(points)],
                "gpu": [[20 + i % 30] for i in range(points)],
                "top_users": [
                    {"id": 1, "name": "admin", "messages": 450, "tokens": 12000, "avg_time": 400},
                    {"id": 2, "name": "user1", "messages": 320, "tokens": 8900, "avg_time": 520},
                    {"id": 3, "name": "user2", "messages": 180, "tokens": 4500, "avg_time": 380}
                ],
                "top_intents": [
                    {"name": "greeting", "count": 450, "percentage": 36},
                    {"name": "question", "count": 380, "percentage": 31},
                    {"name": "command", "count": 210, "percentage": 17}
                ]
            })
        
        # --- API: TRACE (BlackBox) ---
        
        @self.app.route("/api/blackbox/search", methods=["GET"])
        @self.admin_required
        def api_blackbox_search():
            query = request.args.get("q", "")
            limit = request.args.get("limit", 100, type=int)
            
            # Demo trace-ek
            traces = []
            modules = ["orchestrator", "king", "queen", "scribe", "valet", "jester"]
            levels = ["info", "debug", "warning", "error"]
            
            for i in range(min(limit, 50)):
                traces.append({
                    "id": i,
                    "trace_id": f"trace_{uuid.uuid4().hex[:16]}",
                    "timestamp": time.time() - i * 600,
                    "module": modules[i % len(modules)],
                    "level": levels[i % len(levels)],
                    "message": f"Demo trace message {i}",
                    "duration": 10 + i % 100,
                    "context": {"request_id": i, "user": "admin"}
                })
            
            return jsonify({"results": traces})
        
        @self.app.route("/api/blackbox/trace/<trace_id>", methods=["GET"])
        @self.admin_required
        def api_blackbox_trace(trace_id):
            return jsonify({
                "trace_id": trace_id,
                "timestamp": time.time(),
                "module": "orchestrator",
                "level": "info",
                "message": "Demo trace details",
                "context": {"full_data": "sample"}
            })
        
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
                "ip": request.remote_addr
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
            text = data.get("text", "").strip()
            conv_id = data.get("conversation_id")
            
            if not text or not conv_id:
                emit("chat:error", {"error": "Missing text or conversation_id"})
                return
            
            orch = self.modules.get("orchestrator")
            if not orch:
                emit("chat:error", {"error": "Orchestrator not available"})
                return
            
            print(f"📨 WebApp: Üzenet érkezett: '{text}' (conv: {conv_id})")
            
            # Mentés
            db = self.modules.get("database")
            if db:
                try:
                    db.add_message(conv_id, "user", text)
                    print(f"💾 WebApp: Üzenet elmentve (conv: {conv_id})")
                except Exception as e:
                    print(f"⚠️ WebApp: Üzenet mentési hiba: {e}")
            
            # Callback definiálása - EZ KÜLDI EL A VÁLASZT (csak egyszer)
            def on_response(response_text, conv_id, trace_id):
                print(f"📤 WebApp: Callback meghívva, válasz küldése frontendnek: {response_text[:50]}...")
                try:
                    self.socketio.emit("chat:response", {
                        "text": response_text,
                        "trace_id": trace_id,
                        "conversation_id": conv_id
                    })
                    print(f"✅ WebApp: chat:response elküldve")
                except Exception as e:
                    print(f"❌ WebApp: Hiba a válasz küldésekor: {e}")
            
            # Beállítjuk a callbacket az Orchestratorban
            if hasattr(orch, 'set_webapp_callback'):
                orch.set_webapp_callback(on_response)
                print(f"🔗 WebApp: Callback beállítva az Orchestratorban")
            
            # Elindítjuk a feldolgozást - NEM KÜLDÜNK ITT MÉG VÁLASZT!
            try:
                result = orch.process_user_message(text, conv_id)
                print(f"🔄 WebApp: Orchestrator.process_user_message visszatért")
                
                # MEGJEGYZÉS: Itt NEM küldünk chat:response-t, mert a callback fogja!
                # Ha a callback nem működik, akkor ez a biztonsági mentés:
                # if result and result.get("response") and not hasattr(orch, '_callback_called'):
                #     emit("chat:response", {...})
                
            except Exception as e:
                print(f"❌ WebApp: Orchestrator hiba: {e}")
                emit("chat:error", {"error": f"Processing error: {e}"})
            
            emit("chat:ack", {"received": True})
            print(f"✅ WebApp: chat:ack elküldve")
        
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
        
        @self.socketio.on("get_status")
        def handle_get_status():
            emit("status_update", {
                "heartbeat": self.modules.get("heartbeat", {}).get_state() if self.modules.get("heartbeat") else {},
                "king": self.modules.get("king", {}).get_state() if self.modules.get("king") else {},
                "modules": list(self.modules.keys()),
                "gpu": self.modules.get("sentinel", {}).get_gpu_status() if self.modules.get("sentinel") else []
            })
    
    # ----------------------------------------------------------------------
    # INDIÍTÁS / LEÁLLÍTÁS
    # ----------------------------------------------------------------------
    
    def start(self, host="0.0.0.0", port=5000, debug=False):
        self.running = True
        print(f"🌐 WebApp indul: http://{host}:{port}")
        if self.dev_mode:
            print("⚠️ FEJLESZTŐI MÓD - automatikus admin bejelentkezés")
            print("🔐 Admin jelszó: admin123")
        self.socketio.run(self.app, host=host, port=port, debug=debug)
    
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
            "system_id": self.system_id
        }


# ----------------------------------------------------------------------
# FŐ PROGRAM
# ----------------------------------------------------------------------

if __name__ == "__main__":
    app = WebApp()
    app.start(host="0.0.0.0", port=5000, debug=False)