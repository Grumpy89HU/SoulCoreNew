// Socket.IO kapcsolat - GLOBÁLISAN
window.socketManager = {
    socket: null,
    reconnectAttempts: 0,
    maxReconnectAttempts: 5,
    eventListeners: {},
    
    init() {
        this.socket = io({
            reconnection: true,
            reconnectionAttempts: this.maxReconnectAttempts,
            reconnectionDelay: 1000,
            reconnectionDelayMax: 5000,
            timeout: 20000
        });
        
        this._setupEventHandlers();
        this._setupHeartbeat();
        
        console.log('🔌 SocketManager: Inicializálva');
    },
    
    _setupEventHandlers() {
        // === ALAP ESEMÉNYEK ===
        this.socket.on('connect', () => {
            console.log('🔌 Socket: Kapcsolódva');
            this.reconnectAttempts = 0;
            if (window.store) {
                window.store.setConnected(true);
                window.store.addNotification('success', window.gettext?.('socket.connected') || 'Connected to server');
            }
            this._emit('connect');
            this._getInitialData();
        });
        
        this.socket.on('disconnect', (reason) => {
            console.log('🔌 Socket: Kapcsolat bontva', reason);
            if (window.store) {
                window.store.setConnected(false);
                if (reason !== 'io client disconnect') {
                    window.store.addNotification('warning', window.gettext?.('socket.disconnected') || 'Disconnected from server');
                }
            }
            this._emit('disconnect', reason);
        });
        
        this.socket.on('connect_error', (error) => {
            console.log('🔌 Socket: Kapcsolódási hiba', error);
            this.reconnectAttempts++;
            if (window.store) {
                window.store.setError(window.gettext?.('socket.connection_error') || 'Connection error');
            }
            this._emit('connect_error', error);
        });
        
        this.socket.on('reconnect', (attemptNumber) => {
            console.log('🔌 Socket: Újracsatlakozva', attemptNumber);
            if (window.store) {
                window.store.addNotification('success', window.gettext?.('socket.reconnected') || 'Reconnected to server');
            }
            this._getInitialData();
            this._emit('reconnect', attemptNumber);
        });
        
        this.socket.on('reconnect_attempt', (attemptNumber) => {
            console.log('🔌 Socket: Újracsatlakozási kísérlet', attemptNumber);
            this._emit('reconnect_attempt', attemptNumber);
        });
        
        this.socket.on('reconnect_error', (error) => {
            console.log('🔌 Socket: Újracsatlakozási hiba', error);
            this._emit('reconnect_error', error);
        });
        
        this.socket.on('reconnect_failed', () => {
            console.log('🔌 Socket: Újracsatlakozás sikertelen');
            if (window.store) {
                window.store.addNotification('error', window.gettext?.('socket.reconnect_failed') || 'Failed to reconnect');
            }
            this._emit('reconnect_failed');
        });
        
        // === RENDSZER ESEMÉNYEK ===
        this.socket.on('initial_state', (data) => {
            console.log('🔌 Socket: Kezdeti állapot érkezett');
            this._handleInitialState(data);
            this._emit('initial_state', data);
        });
        
        this.socket.on('status_update', (data) => {
            this._handleStatusUpdate(data);
            this._emit('status_update', data);
        });
        
        this.socket.on('error', (data) => {
            console.error('🔌 Socket: Szerver hiba', data);
            if (window.store) {
                window.store.setError(data.message || 'Unknown server error');
            }
            this._emit('error', data);
        });
        
        // === CHAT ESEMÉNYEK ===
        this.socket.on('king_response', (data) => {
            this.addMessage(
                data.response || '...', 
                'king', 
                window.store?.userName || 'Assistant', 
                data.mood
            );
            this._emit('king_response', data);
        });
        
        this.socket.on('jester_note', (data) => {
            const note = data.note || '';
            const icon = note.includes('CRITICAL') ? '🔥' : '🎭';
            this.addMessage(`${icon} ${note}`, 'jester', 'Jester');
            if (window.store) {
                window.store.addNotification('warning', note);
            }
            this._emit('jester_note', data);
        });
        
        this.socket.on('vision_result', (data) => {
            const icon = data.success ? '🔍' : '❌';
            this.addMessage(`${icon} ${data.description || 'Image processed'}`, 'system', 'Vision');
            if (data.ocr) {
                this.addMessage(`📝 OCR: ${data.ocr}`, 'system', 'Vision');
            }
            this._emit('vision_result', data);
        });
        
        // === ADATBÁZIS ESEMÉNYEK ===
        this.socket.on('conversations_list', (data) => {
            if (window.store) {
                window.store.setConversations(data.conversations || []);
            }
            this._emit('conversations_list', data);
        });
        
        this.socket.on('conversation_created', (data) => {
            this.loadConversation(data.id);
            this._getConversations();
            this._emit('conversation_created', data);
        });
        
        this.socket.on('conversation_loaded', (data) => {
            this._handleConversationLoaded(data);
            this._emit('conversation_loaded', data);
        });
        
        this.socket.on('conversation_deleted', (data) => {
            if (window.store && window.store.currentConversationId === data.id) {
                window.store.setCurrentConversationId(null);
                window.store.setMessages([]);
            }
            this._getConversations();
            this._emit('conversation_deleted', data);
        });
        
        this.socket.on('message_saved', (data) => {
            this._emit('message_saved', data);
        });
        
        // === PROMPT ESEMÉNYEK ===
        this.socket.on('prompts_list', (data) => {
            if (window.store) {
                window.store.setPrompts(data.prompts || []);
            }
            this._emit('prompts_list', data);
        });
        
        this.socket.on('prompt_saved', (data) => {
            this.getPrompts();
            if (window.store) {
                window.store.addNotification('success', window.gettext?.('prompts.saved') || 'Prompt saved');
            }
            this._emit('prompt_saved', data);
        });
        
        // === MODELL ESEMÉNYEK ===
        this.socket.on('models_list', (data) => {
            if (window.store) {
                window.store.setModels(data.models || []);
            }
            this._emit('models_list', data);
        });
        
        this.socket.on('model_activated', (data) => {
            this.getModels();
            if (window.store) {
                window.store.addNotification('success', window.gettext?.('model.activated') || 'Model activated');
            }
            this._emit('model_activated', data);
        });
        
        // === BEÁLLÍTÁS ESEMÉNYEK ===
        this.socket.on('settings', (data) => {
            if (window.store) {
                window.store.setSettings(data || {});
            }
            this._emit('settings', data);
        });
        
        this.socket.on('setting_updated', (data) => {
            this.getSettings();
            if (window.store) {
                window.store.addNotification('success', window.gettext?.('settings.updated') || 'Setting updated');
            }
            this._emit('setting_updated', data);
        });
        
        // === ADMIN ESEMÉNYEK ===
        this.socket.on('admin_login_result', (data) => {
            this._handleAdminLogin(data);
            this._emit('admin_login_result', data);
        });
        
        this.socket.on('module_control_result', (data) => {
            this._handleModuleControl(data);
            this._emit('module_control_result', data);
        });
        
        // === EGYÉB ESEMÉNYEK ===
        this.socket.on('notification', (data) => {
            if (window.store) {
                window.store.addNotification(data.type || 'info', data.message);
            }
            this._emit('notification', data);
        });
        
        this.socket.on('personalities_list', (data) => {
            if (window.store) {
                window.store.setPersonalities(data.personalities || []);
            }
            this._emit('personalities_list', data);
        });
    },
    
    _setupHeartbeat() {
        // Heartbeat a kapcsolat életben tartásához
        setInterval(() => {
            if (this.socket && this.socket.connected) {
                this.socket.emit('ping', { timestamp: Date.now() });
            }
        }, 30000); // 30 másodperc
    },
    
    _handleInitialState(data) {
        if (!window.store) return;
        
        if (data.messages) {
            window.store.setMessages(data.messages);
        }
        
        if (data.userName) {
            window.store.setUserName(data.userName);
        }
        
        if (data.userLanguage) {
            window.store.setUserLanguage(data.userLanguage);
        }
        
        if (data.server_time) {
            // Időszinkronizáció
            window.serverTimeDiff = Date.now() - data.server_time * 1000;
        }
    },
    
    _handleStatusUpdate(data) {
        if (!window.store) return;
        
        if (data.heartbeat) window.store.setHeartbeat(data.heartbeat);
        if (data.king) window.store.setKingState(data.king);
        if (data.queen) window.store.setQueenState(data.queen);
        if (data.jester) window.store.setJesterState(data.jester);
        if (data.valet) window.store.setValetState(data.valet);
        if (data.gpu) window.store.setGpuStatus(data.gpu);
        if (data.sentinel) window.store.setSentinelState(data.sentinel);
        if (data.modules) window.store.setModuleStatuses(data.modules);
        if (data.metrics) window.store.setMetrics(data.metrics);
    },
    
    _handleConversationLoaded(data) {
        if (!window.store) return;
        
        window.store.setCurrentConversationId(data.id);
        const messages = (data.messages || []).map(msg => ({
            id: msg.id,
            text: msg.content,
            sender: msg.role === 'user' ? 'user' : (msg.role === 'assistant' ? 'king' : msg.role),
            senderName: msg.role === 'user' 
                ? (window.store.userName || 'User')
                : (msg.role === 'assistant' 
                    ? (window.store.kingState?.name || 'Assistant')
                    : 'System'),
            time: new Date(msg.timestamp).toLocaleTimeString(window.store.userLanguage),
            timestamp: msg.timestamp,
            tokens: msg.tokens,
            metadata: msg.metadata
        }));
        
        window.store.setMessages(messages);
    },
    
    _handleAdminLogin(data) {
        if (!window.store) return;
        
        if (data.success) {
            window.store.setIsAdmin(true);
            this.addSystemMessage(window.gettext?.('admin.activated') || 'Admin mode activated', 'success');
            this._getAdminData();
        } else {
            this.addSystemMessage(
                data.message || (window.gettext?.('admin.login_failed') || 'Login failed'), 
                'error'
            );
        }
    },
    
    _handleModuleControl(data) {
        if (!window.store) return;
        
        if (data.success) {
            this.addSystemMessage(data.message, 'success');
            // Frissítjük a modul státuszokat
            setTimeout(() => this.getStatus(), 1000);
        } else {
            this.addSystemMessage(
                data.message || (window.gettext?.('module.control_failed') || 'Control failed'), 
                'error'
            );
        }
    },
    
    _getInitialData() {
        this.socket.emit('get_initial_state');
        this.socket.emit('get_conversations');
        this.socket.emit('get_prompts');
        this.socket.emit('get_settings');
        this.socket.emit('get_models');
        this.socket.emit('get_personalities');
        this.socket.emit('get_status');
    },
    
    _getAdminData() {
        this.socket.emit('get_audit_log');
        this.socket.emit('get_metrics');
    },
    
    _emit(event, data) {
        if (this.eventListeners[event]) {
            this.eventListeners[event].forEach(callback => {
                try {
                    callback(data);
                } catch (e) {
                    console.error(`Socket event listener error (${event}):`, e);
                }
            });
        }
    },
    
    // === PUBLIKUS METÓDUSOK ===
    
    on(event, callback) {
        if (!this.eventListeners[event]) {
            this.eventListeners[event] = [];
        }
        this.eventListeners[event].push(callback);
    },
    
    off(event, callback) {
        if (this.eventListeners[event]) {
            const index = this.eventListeners[event].indexOf(callback);
            if (index !== -1) {
                this.eventListeners[event].splice(index, 1);
            }
        }
    },
    
    emit(event, data) {
        if (this.socket && this.socket.connected) {
            this.socket.emit(event, data);
        } else {
            console.warn(`Socket not connected, cannot emit: ${event}`);
        }
    },
    
    addMessage(text, sender, senderName, mood = null) {
        if (!window.store) return;
        
        const msg = {
            id: Date.now() + Math.random(),
            text: text,
            sender: sender,
            senderName: senderName + (mood ? ` (${mood})` : ''),
            time: new Date().toLocaleTimeString(window.store.userLanguage),
            timestamp: Date.now()
        };
        
        window.store.addMessage(msg);
        this._scrollToBottom();
    },
    
    addSystemMessage(text, type = 'info') {
        const icon = {
            'success': '✅',
            'error': '❌',
            'warning': '⚠️',
            'info': 'ℹ️'
        }[type] || 'ℹ️';
        
        this.addMessage(`${icon} ${text}`, 'system', 'System');
        
        if (type === 'error' && window.store) {
            window.store.setError(text);
        }
    },
    
    _scrollToBottom() {
        setTimeout(() => {
            const container = document.querySelector('.chat-messages');
            if (container) {
                container.scrollTop = container.scrollHeight;
            }
        }, 50);
    },
    
    // === CHAT METÓDUSOK ===
    
    sendMessage(text, conversationId = null) {
        if (!text.trim() || !this.socket?.connected) {
            this.addSystemMessage(
                window.gettext?.('socket.not_connected') || 'Not connected to server',
                'error'
            );
            return;
        }
        
        const userName = window.store?.userName || 'User';
        this.addMessage(text, 'user', userName);
        
        this.socket.emit('user_message', { 
            text: text, 
            conversation_id: conversationId || window.store?.currentConversationId
        });
    },
    
    uploadImage(base64, filename) {
        if (!this.socket?.connected) {
            this.addSystemMessage(
                window.gettext?.('socket.not_connected') || 'Not connected to server',
                'error'
            );
            return;
        }
        
        const userName = window.store?.userName || 'User';
        this.addMessage(`📷 ${filename}`, 'user', userName);
        this.socket.emit('image_upload', { image: base64, filename });
    },
    
    // === BESZÉLGETÉS METÓDUSOK ===
    
    createConversation(title) {
        if (!this.socket?.connected) return;
        
        if (!title) {
            const date = new Date();
            title = `${window.gettext?.('conversation.default_title') || 'Conversation'} ${date.toLocaleDateString()} ${date.toLocaleTimeString()}`;
        }
        
        this.socket.emit('create_conversation', { title });
    },
    
    loadConversation(id) {
        if (!this.socket?.connected) return;
        this.socket.emit('load_conversation', { id });
    },
    
    deleteConversation(id) {
        if (!this.socket?.connected) return;
        
        const message = window.gettext?.('conversation.confirm_delete') || 'Are you sure you want to delete this conversation?';
        if (confirm(message)) {
            this.socket.emit('delete_conversation', { id });
        }
    },
    
    // === PROMPT METÓDUSOK ===
    
    getPrompts() {
        if (this.socket?.connected) this.socket.emit('get_prompts');
    },
    
    savePrompt(prompt) {
        if (!this.socket?.connected) return;
        
        if (!prompt.name || !prompt.content) {
            this.addSystemMessage(
                window.gettext?.('prompts.missing_fields') || 'Name and content are required',
                'error'
            );
            return;
        }
        
        this.socket.emit('save_prompt', prompt);
    },
    
    deletePrompt(id) {
        if (!this.socket?.connected) return;
        
        const message = window.gettext?.('prompts.confirm_delete') || 'Are you sure you want to delete this prompt?';
        if (confirm(message)) {
            this.socket.emit('delete_prompt', { id });
        }
    },
    
    // === MODELL METÓDUSOK ===
    
    getModels() {
        if (this.socket?.connected) this.socket.emit('get_models');
    },
    
    activateModel(id) {
        if (!this.socket?.connected) return;
        
        const message = window.gettext?.('model.confirm_activate') || 'Activate this model? The King will reload.';
        if (confirm(message)) {
            this.socket.emit('activate_model', { id });
        }
    },
    
    // === BEÁLLÍTÁS METÓDUSOK ===
    
    getSettings() {
        if (this.socket?.connected) this.socket.emit('get_settings');
    },
    
    updateSetting(key, value, type = null) {
        if (!this.socket?.connected) return;
        this.socket.emit('update_setting', { key, value, type });
    },
    
    // === ADMIN METÓDUSOK ===
    
    adminLogin(password) {
        if (!this.socket?.connected) return;
        this.socket.emit('admin_login', { password });
    },
    
    adminLogout() {
        if (!this.socket?.connected) return;
        this.socket.emit('admin_logout');
        if (window.store) {
            window.store.setIsAdmin(false);
        }
    },
    
    controlModule(module, action) {
        if (!this.socket?.connected) return;
        this.socket.emit('control_module', { module, action });
    },
    
    // === EGYÉB METÓDUSOK ===
    
    getStatus() {
        if (this.socket?.connected) this.socket.emit('get_status');
    },
    
    getPersonalities() {
        if (this.socket?.connected) this.socket.emit('get_personalities');
    },
    
    getAuditLog() {
        if (this.socket?.connected) this.socket.emit('get_audit_log');
    },
    
    getMetrics(period = 'hour') {
        if (this.socket?.connected) this.socket.emit('get_metrics', { period });
    },
    
    // === KAPCSOLAT KEZELÉS ===
    
    reconnect() {
        if (this.socket) {
            this.socket.connect();
        }
    },
    
    disconnect() {
        if (this.socket) {
            this.socket.disconnect();
        }
    },
    
    isConnected() {
        return this.socket?.connected || false;
    }
};

// Automatikus inicializálás
window.socketManager.init();

console.log('✅ SocketManager betöltve globálisan');