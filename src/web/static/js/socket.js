// ==============================================
// SOULCORE 3.0 - WebSocket kapcsolat (Socket.IO)
// ==============================================

window.socketManager = {
    socket: null,
    connected: false,
    reconnectAttempts: 0,
    maxReconnectAttempts: 5,
    reconnectDelay: 2000,
    
    /**
     * Kapcsolódás a szerverhez
     */
    connect() {
        if (this.socket?.connected) return;
        
        this.socket = io({
            path: '/socket.io',
            transports: ['websocket', 'polling'],
            reconnection: true,
            reconnectionAttempts: this.maxReconnectAttempts,
            reconnectionDelay: this.reconnectDelay
        });
        
        this._registerEvents();
    },
    
    /**
     * Események regisztrálása
     */
    _registerEvents() {
        this.socket.on('connect', () => {
            console.log('✅ WebSocket kapcsolódva');
            this.connected = true;
            this.reconnectAttempts = 0;
            window.store.setConnected(true);
            window.store.setSocketId(this.socket.id);
            
            // Session adatok lekérése
            this.emit('auth:get_session');
        });
        
        this.socket.on('disconnect', (reason) => {
            console.log('❌ WebSocket kapcsolat bontva:', reason);
            this.connected = false;
            window.store.setConnected(false);
        });
        
        this.socket.on('connect_error', (error) => {
            console.error('❌ WebSocket kapcsolódási hiba:', error);
            this.reconnectAttempts++;
        });
        
        this.socket.on('reconnect', (attemptNumber) => {
            console.log(`✅ WebSocket újrakapcsolódva (${attemptNumber})`);
            this.connected = true;
            window.store.setConnected(true);
        });
        
        // AUTH események
        this.socket.on('auth:session', (data) => {
            if (data.authenticated) {
                window.store.setAuth(data);
            }
        });
        
        // CHAT események
        this.socket.on('chat:response', (data) => {
            const message = {
                id: `msg_${Date.now()}`,
                role: 'assistant',
                content: data.text,
                timestamp: Date.now(),
                trace_id: data.trace_id
            };
            
            if (data.conversation_id) {
                window.store.addMessage(data.conversation_id, message);
            }
        });
        
        this.socket.on('chat:error', (data) => {
            window.store.addNotification('error', data.error);
        });
        
        this.socket.on('chat:ack', (data) => {
            console.log('Üzenet fogadva:', data);
        });
        
        // RENDSZER események
        this.socket.on('connected', (data) => {
            console.log('Szerver üdvözlet:', data);
        });
    },
    
    /**
     * Esemény küldése
     */
    emit(event, data = {}) {
        if (!this.socket?.connected) {
            console.warn('⚠️ Nincs WebSocket kapcsolat');
            return false;
        }
        
        this.socket.emit(event, data);
        return true;
    },
    
    /**
     * Esemény figyelése
     */
    on(event, callback) {
        if (this.socket) {
            this.socket.on(event, callback);
        }
    },
    
    /**
     * Esemény figyelés leállítása
     */
    off(event, callback) {
        if (this.socket) {
            this.socket.off(event, callback);
        }
    },
    
    /**
     * Kapcsolat bontása
     */
    disconnect() {
        if (this.socket) {
            this.socket.disconnect();
            this.socket = null;
            this.connected = false;
            window.store.setConnected(false);
        }
    },
    
    /**
     * Chat üzenet küldése
     */
    sendMessage(text, conversationId) {
        return this.emit('chat:message', { text, conversation_id: conversationId });
    },
    
    /**
     * Gépelés jelzés
     */
    startTyping(conversationId) {
        return this.emit('chat:typing_start', { conversation_id: conversationId });
    },
    
    stopTyping(conversationId) {
        return this.emit('chat:typing_stop', { conversation_id: conversationId });
    }
};

// Automatikus kapcsolódás
setTimeout(() => {
    window.socketManager.connect();
}, 500);

console.log('✅ SocketManager modul betöltve');