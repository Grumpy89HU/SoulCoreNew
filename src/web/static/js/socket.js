// Socket.IO kapcsolat - GLOBÁLISAN
window.socketManager = {
    socket: null,
    
    init() {
        this.socket = io();
        
        this.socket.on('connect', () => {
            if (window.store) window.store.setConnected(true);
            this.addSystemMessage('Kapcsolódva a Várhoz');
            this.socket.emit('get_initial_state');
            this.socket.emit('get_conversations');
        });
        
        this.socket.on('disconnect', () => {
            if (window.store) window.store.setConnected(false);
            this.addSystemMessage('Kapcsolat bontva');
        });
        
        this.socket.on('initial_state', (data) => {
            if (data.messages && window.store) {
                window.store.setMessages(data.messages);
            }
        });
        
        this.socket.on('king_response', (data) => {
            this.addMessage(data.response || '...', 'king', 'Kópé', data.mood);
        });
        
        this.socket.on('jester_note', (data) => {
            this.addMessage('🎭 ' + (data.note || ''), 'jester', 'Bohóc');
        });
        
        this.socket.on('vision_result', (data) => {
            this.addMessage(`🔍 ${data.description || 'Kép feldolgozva'}`, 'jester', 'Eye-Core');
        });
        
        this.socket.on('status_update', (data) => {
            if (!window.store) return;
            if (data.heartbeat) window.store.setHeartbeat(data.heartbeat);
            if (data.king) window.store.setKingState(data.king);
            if (data.gpu) window.store.setGpuStatus(data.gpu);
            if (data.modules) window.store.setModuleStatuses(data.modules);
        });
        
        this.socket.on('conversations_list', (data) => {
            if (window.store) window.store.setConversations(data.conversations || []);
        });
        
        this.socket.on('conversation_created', (data) => {
            this.loadConversation(data.id);
            if (this.socket) this.socket.emit('get_conversations');
        });
        
        this.socket.on('conversation_loaded', (data) => {
            if (!window.store) return;
            window.store.setCurrentConversationId(data.id);
            window.store.setMessages((data.messages || []).map(msg => ({
                id: msg.id,
                text: msg.content,
                sender: msg.role == 'user' ? 'user' : (msg.role == 'assistant' ? 'king' : msg.role),
                senderName: msg.role == 'user' ? 'Grumpy' : (msg.role == 'assistant' ? 'Kópé' : 'Rendszer'),
                time: new Date(msg.timestamp).toLocaleTimeString()
            })));
        });
        
        this.socket.on('prompts_list', (data) => {
            if (window.store) window.store.setPrompts(data.prompts || []);
        });
        
        this.socket.on('settings', (data) => {
            if (window.store) window.store.setSettings(data || {});
        });
        
        this.socket.on('models_list', (data) => {
            if (window.store) window.store.setModels(data.models || []);
        });
        
        this.socket.on('admin_login_result', (data) => {
            if (!window.store) return;
            if (data.success) {
                window.store.setIsAdmin(true);
                this.addSystemMessage('Admin mód aktiválva');
            } else {
                this.addSystemMessage('Sikertelen admin belépés', 'error');
            }
        });
        
        this.socket.on('module_control_result', (data) => {
            if (data.success) {
                this.addSystemMessage(data.message, 'system');
            } else {
                this.addSystemMessage('Hiba: ' + data.message, 'error');
            }
        });
    },
    
    addMessage(text, sender, senderName, mood = null) {
		if (!window.store) return;
		
		const msg = {
			id: Date.now() + Math.random(),
			text: text,
			sender: sender,
			senderName: senderName + (mood ? ` (${mood})` : ''),
			time: new Date().toLocaleTimeString()
		};
		window.store.addMessage(msg);
		
		// Scroll to bottom
		setTimeout(() => {
			const container = document.querySelector('.chat-messages');
			if (container) {
				container.scrollTop = container.scrollHeight;
			}
		}, 50);
	},
    
    addSystemMessage(text, type = 'system') {
        this.addMessage(text, 'system', 'Rendszer');
    },
    
    // Például a sendMessage-ben:
	sendMessage(text, conversationId = null) {
		if (!text.trim() || !window.store?.connected || !this.socket) return;
		
		this.addMessage(text, 'user', 'Grumpy');
		this.socket.emit('user_message', { 
			text: text, 
			conversation_id: conversationId || window.store.currentConversationId  // itt is getter!
		});
	},
    
    uploadImage(base64, filename) {
        this.addMessage(`[Kép feltöltve: ${filename}]`, 'user', 'Grumpy');
        if (this.socket) {
            this.socket.emit('image_upload', { image: base64, filename });
        }
    },
    
    createConversation(title) {
        if (this.socket) {
            this.socket.emit('create_conversation', { title });
        }
    },
    
    loadConversation(id) {
        if (this.socket) {
            this.socket.emit('load_conversation', { id });
        }
    },
    
    deleteConversation(id) {
        if (confirm('Biztosan törlöd ezt a beszélgetést?')) {
            if (this.socket) {
                this.socket.emit('delete_conversation', { id });
            }
        }
    },
    
    getPrompts() {
        if (this.socket) this.socket.emit('get_prompts');
    },
    
    savePrompt(prompt) {
        if (this.socket) this.socket.emit('save_prompt', prompt);
    },
    
    getSettings() {
        if (this.socket) this.socket.emit('get_settings');
    },
    
    updateSetting(key, value, type = null) {
        if (this.socket) this.socket.emit('update_setting', { key, value, type });
    },
    
    getModels() {
        if (this.socket) this.socket.emit('get_models');
    },
    
    activateModel(id) {
        if (this.socket) this.socket.emit('activate_model', { id });
    },
    
    controlModule(module, action) {
        if (this.socket) this.socket.emit('control_module', { module, action });
    },
    
    adminLogin(password) {
        if (this.socket) this.socket.emit('admin_login', { password });
    }
};

// Automatikus inicializálás
window.socketManager.init();

console.log('✅ SocketManager betöltve globálisan');