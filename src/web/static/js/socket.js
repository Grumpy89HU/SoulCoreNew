// ==============================================
// SOULCORE 3.0 - WebSocket kliens (Socket.IO)
// TELJES VERZIÓ - semmi sem hiányzik
// ==============================================

(function() {
    'use strict';
    
    console.log('🔧 socket.js betöltése...');
    
    window.socketManager = {
        socket: null,
        connected: false,
        typingActive: false,
        
        connect() {
            if (this.socket?.connected) {
                console.log('✅ Socket már csatlakozva');
                return;
            }
            
            if (!window.store) {
                console.log('⏳ Várakozás a store betöltődésére...');
                setTimeout(() => this.connect(), 200);
                return;
            }
            
            console.log('🔌 WebSocket kapcsolódás...');
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
                console.log('✅ WebSocket kapcsolódva');
                if (window.store && window.store.setConnected) {
                    window.store.setConnected(true);
                }
                this.emit('auth:get_session');
            });
            
            this.socket.on('disconnect', () => {
                this.connected = false;
                console.log('❌ WebSocket kapcsolat bontva');
                if (window.store && window.store.setConnected) {
                    window.store.setConnected(false);
                }
            });
            
            this.socket.on('connect_error', (error) => {
                console.error('❌ WebSocket kapcsolódási hiba:', error);
            });
            
            this.socket.on('auth:session', (data) => {
                console.log('🔐 Auth session:', data);
                if (data.authenticated && window.store && window.store.setAuth) {
                    window.store.setAuth(data);
                }
            });
            
			lastResponseId: null,
            // Chat üzenet válasz
            this.socket.on('chat:response', (data) => {
				console.log('📨 chat:response érkezett:', data);
				
				if (!data || !data.text) {
					console.warn('⚠️ chat:response üres vagy nincs text');
					return;
				}
				
				// Duplikáció szűrés - ha ugyanaz a trace_id, ne add hozzá kétszer
				if (this.lastResponseId === data.trace_id) {
					console.log('⚠️ Duplikált üzenet kihagyva:', data.trace_id);
					return;
				}
				this.lastResponseId = data.trace_id;
				
				if (!window.store) {
					console.warn('⚠️ store nincs betöltve');
					return;
				}
				
				const msg = {
					id: data.id || Date.now(),
					role: 'assistant',
					content: data.text,
					timestamp: data.timestamp || Date.now(),
					trace_id: data.trace_id
				};
				
				if (data.conversation_id && window.store.addMessage) {
					window.store.addMessage(data.conversation_id, msg);
					console.log('✅ Üzenet hozzáadva a store-hoz (conv:', data.conversation_id, ')');
				} else if (window.store.currentConversationId && window.store.addMessage) {
					window.store.addMessage(window.store.currentConversationId, msg);
					console.log('✅ Üzenet hozzáadva a store-hoz (current)');
				}
			});
            
            // Proaktív üzenet (entitás kezdeményez)
            this.socket.on('proactive_message', (data) => {
                console.log('📨 proactive_message érkezett:', data);
                if (!window.store) return;
                
                const msg = {
                    id: data.id || Date.now(),
                    role: 'assistant',
                    content: data.text,
                    timestamp: data.timestamp || Date.now(),
                    proactive: true
                };
                if (window.store.currentConversationId && window.store.addMessage) {
                    window.store.addMessage(window.store.currentConversationId, msg);
                }
                if (window.store.addNotification) {
                    window.store.addNotification('info', 'Proaktív üzenet érkezett', 'Kópé');
                }
            });
            
            // Chat hiba
            this.socket.on('chat:error', (data) => {
                console.error('❌ chat:error:', data);
                if (window.store && window.store.addNotification) {
                    window.store.addNotification('error', data.error || 'Hiba az üzenet küldésekor');
                }
            });
            
            // Chat ack (visszajelzés, hogy az üzenet megérkezett)
            this.socket.on('chat:ack', (data) => {
                console.log('✅ chat:ack:', data);
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
                console.warn('⚠️ Nincs WebSocket kapcsolat, esemény:', event);
                return false;
            }
            console.log(`📤 Emit: ${event}`, data);
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
            console.log(`📤 Üzenet küldése: "${text.substring(0, 50)}..." (conv: ${conversationId})`);
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
    
    // Inicializálás
    const init = () => {
        if (window.store && typeof window.store.setConnected === 'function') {
            window.socketManager.connect();
        } else {
            console.log('⏳ Várakozás a store-ra...');
            setTimeout(init, 200);
        }
    };
    
    setTimeout(init, 500);
    console.log('✅ SocketManager modul betöltve');
})();