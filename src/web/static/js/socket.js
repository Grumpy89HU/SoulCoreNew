// ==============================================
// SOULCORE 3.0 - WebSocket kliens (Socket.IO)
// ==============================================

window.socketManager = {
    socket: null,
    connected: false,
    typingActive: false,
    
    connect() {
        if (this.socket?.connected) return;
        
        // Várjuk meg, amíg a store betöltődik
        if (!window.store || typeof window.store.setConnected !== 'function') {
            console.log('⏳ Várakozás a store betöltődésére...');
            setTimeout(() => this.connect(), 200);
            return;
        }
        
        this.socket = io({
            path: '/socket.io',
            transports: ['websocket', 'polling'],
            reconnection: true,
            reconnectionAttempts: 5,
            reconnectionDelay: 2000
        });
        
        this._registerEvents();
    },
    
    _registerEvents() {
        this.socket.on('connect', () => {
            this.connected = true;
            if (window.store && window.store.setConnected) {
                window.store.setConnected(true);
            }
            this.emit('auth:get_session');
            console.log('✅ WebSocket kapcsolódva');
        });
        
        this.socket.on('disconnect', () => {
            this.connected = false;
            if (window.store && window.store.setConnected) {
                window.store.setConnected(false);
            }
            console.log('❌ WebSocket kapcsolat bontva');
        });
        
        this.socket.on('auth:session', (data) => {
            if (data.authenticated && window.store && window.store.setAuth) {
                window.store.setAuth(data);
            }
        });
        
        // Chat üzenet válasz
        this.socket.on('chat:response', (data) => {
            if (!window.store) return;
            
            const msg = {
                id: data.id || Date.now(),
                role: 'assistant',
                content: data.text,
                timestamp: data.timestamp || Date.now(),
                trace_id: data.trace_id
            };
            if (data.conversation_id) {
                if (window.store.addMessage) {
                    window.store.addMessage(data.conversation_id, msg);
                }
            } else if (window.store.currentConversationId) {
                if (window.store.addMessage) {
                    window.store.addMessage(window.store.currentConversationId, msg);
                }
            }
        });
        
        // Proaktív üzenet (entitás kezdeményez)
        this.socket.on('proactive_message', (data) => {
            if (!window.store) return;
            
            const msg = {
                id: data.id || Date.now(),
                role: 'assistant',
                content: data.text,
                timestamp: data.timestamp || Date.now(),
                proactive: true
            };
            if (window.store.currentConversationId) {
                if (window.store.addMessage) {
                    window.store.addMessage(window.store.currentConversationId, msg);
                }
                if (window.store.addNotification) {
                    window.store.addNotification('info', 'Proaktív üzenet érkezett', 'Kópé');
                }
            }
        });
        
        // Chat hiba
        this.socket.on('chat:error', (data) => {
            if (window.store && window.store.addNotification) {
                window.store.addNotification('error', data.error || 'Hiba az üzenet küldésekor');
            }
        });
        
        // Státusz frissítés
        this.socket.on('status_update', (data) => {
            if (!window.store) return;
            
            if (data.heartbeat && window.store.setHeartbeat) {
                window.store.setHeartbeat(data.heartbeat);
            }
            if (data.king && window.store.setKingState) {
                window.store.setKingState(data.king);
            }
            if (data.modules && window.store.setModules) {
                window.store.setModules(data.modules);
            }
            if (data.gpu && window.store.setGpuStatus) {
                window.store.setGpuStatus(data.gpu);
            }
        });
        
        // Gépelés jelzés
        this.socket.on('typing_start', (data) => {
            if (data.conversation_id === window.store?.currentConversationId) {
                this.typingActive = true;
            }
        });
        
        this.socket.on('typing_stop', (data) => {
            if (data.conversation_id === window.store?.currentConversationId) {
                this.typingActive = false;
            }
        });
        
        // Új naplóbejegyzés
        this.socket.on('audit_entry', (data) => {
            if (window.store && window.store.addAuditEntry) {
                window.store.addAuditEntry(data);
            }
        });
        
        // Új trace
        this.socket.on('trace_entry', (data) => {
            if (window.store && window.store.addTrace) {
                window.store.addTrace(data);
            }
        });
        
        // Modul állapot változás
        this.socket.on('module_status', (data) => {
            if (data.name && data.status && window.store && window.store.updateModule) {
                window.store.updateModule(data.name, data.status);
            }
        });
        
        // Értesítés
        this.socket.on('notification', (data) => {
            if (window.store && window.store.addNotification) {
                window.store.addNotification(data.type || 'info', data.message, data.title);
            }
        });
    },
    
    disconnect() {
        if (this.socket) {
            this.socket.disconnect();
            this.socket = null;
            this.connected = false;
        }
    },
    
    emit(event, data = {}) {
        if (!this.socket?.connected) {
            console.warn('⚠️ Nincs WebSocket kapcsolat');
            return false;
        }
        this.socket.emit(event, data);
        return true;
    },
    
    on(event, callback) {
        if (this.socket) this.socket.on(event, callback);
    },
    
    off(event, callback) {
        if (this.socket) this.socket.off(event, callback);
    },
    
    // Chat metódusok
    sendMessage(text, conversationId) {
        return this.emit('chat:message', { text, conversation_id: conversationId });
    },
    
    startTyping(conversationId) {
        this.emit('chat:typing_start', { conversation_id: conversationId });
    },
    
    stopTyping(conversationId) {
        this.emit('chat:typing_stop', { conversation_id: conversationId });
    },
    
    // Admin metódusok
    getStatus() {
        this.emit('get_status');
    },
    
    getConversations() {
        this.emit('get_conversations');
    },
    
    getModels() {
        this.emit('get_models');
    },
    
    getPrompts() {
        this.emit('get_prompts');
    },
    
    getPersonalities() {
        this.emit('get_personalities');
    },
    
    getSettings() {
        this.emit('get_settings');
    },
    
    controlModule(module, action) {
        this.emit('control_module', { module, action });
    }
};

// Várjuk, amíg a store betöltődik, majd kapcsolódunk
const initSocket = () => {
    if (window.store && typeof window.store.setConnected === 'function') {
        window.socketManager.connect();
    } else {
        console.log('⏳ Várakozás a store-ra...');
        setTimeout(initSocket, 200);
    }
};

setTimeout(initSocket, 500);
console.log('✅ SocketManager modul betöltve');