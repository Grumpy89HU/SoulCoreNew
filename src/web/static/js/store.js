// ==============================================
// SOULCORE 3.0 - Globális állapotkezelés
// ==============================================

window.store = {
    state: Vue.reactive({
        // === AUTH ===
        authenticated: false,
        user: null,
        
        // === KAPCSOLAT ===
        connected: false,
        
        // === RENDSZER ===
        systemId: null,
        
        // === BESZÉLGETÉSEK ===
        conversations: [],
        currentConversationId: null,
        messages: {},
        _updateTrigger: 0,  // Force frissítéshez
        
        // === MODELLEK ===
        models: [],
        
        // === PROMPTOK ===
        prompts: [],
        
        // === SZEMÉLYISÉGEK ===
        personalities: [],
        activePersonalityId: null,
        
        // === MODULOK ===
        modules: {},
        
        // === KIRÁLY ===
        kingState: {
            status: 'unknown',
            mood: 'neutral',
            model_loaded: false,
            response_count: 0,
            avg_response_time: 0
        },
        
        // === HEARTBEAT ===
        heartbeat: {
            uptime_seconds: 0,
            running: true,
            beats: 0,
            proactive_count: 0,
            reminder_count: 0
        },
        
        // === GPU ===
        gpuStatus: [],
        
        // === SENTINEL ===
        sentinelState: {
            throttle_active: false,
            throttle_factor: 1.0,
            recovery_mode: false,
            warnings: []
        },
        
        // === BLACKBOX ===
        blackboxStats: {
            total_events: 0,
            trace_count: 0
        },
        traces: [],
        
        // === METRIKÁK ===
        metrics: {
            total_messages: 0,
            total_tokens: 0,
            avg_response_time: 0
        },
        
        // === AUDIT LOG ===
        auditLog: [],
        
        // === GATEWAY ===
        gateways: [],
        
        // === BEÁLLÍTÁSOK ===
        settings: {},
        
        // === ÉRTESÍTÉSEK ===
        notifications: [],
        
        // === UI ÁLLAPOTOK ===
        ui: {
			leftPanelVisible: window.innerWidth > 768,
			rightPanelVisible: window.innerWidth > 768,
			isMobile: window.innerWidth <= 768,
			theme: localStorage.getItem('theme') || 'dark',
			language: localStorage.getItem('language') || 'hu',
			notifications: []
		}
    }),
    
    // ========================================================================
    // GETTEREK
    // ========================================================================
    
    get authenticated() { return this.state.authenticated; },
    get user() { return this.state.user; },
    get connected() { return this.state.connected; },
    get systemId() { return this.state.systemId; },
    get conversations() { return this.state.conversations; },
    get currentConversationId() { return this.state.currentConversationId; },
    get currentConversation() { 
        if (!this.state.currentConversationId) return null;
        return this.state.conversations.find(c => c.id === this.state.currentConversationId); 
    },
    get messages() { 
        const id = this.state.currentConversationId;
        if (!id) return [];
        const msgs = this.state.messages[id];
        return msgs ? msgs : [];
    },
    get models() { return this.state.models; },
    get prompts() { return this.state.prompts; },
    get personalities() { return this.state.personalities; },
    get activePersonality() { return this.state.personalities.find(p => p.id === this.state.activePersonalityId); },
    get modules() { return this.state.modules; },
    get kingState() { return this.state.kingState; },
    get heartbeat() { return this.state.heartbeat; },
    get gpuStatus() { return this.state.gpuStatus; },
    get sentinelState() { return this.state.sentinelState; },
    get blackboxStats() { return this.state.blackboxStats; },
    get traces() { return this.state.traces; },
    get metrics() { return this.state.metrics; },
    get auditLog() { return this.state.auditLog; },
    get gateways() { return this.state.gateways; },
    get settings() { return this.state.settings; },
    get notifications() { return this.state.ui.notifications; },
    get leftPanelVisible() { return this.state.ui.leftPanelVisible; },
    get rightPanelVisible() { return this.state.ui.rightPanelVisible; },
    get isMobile() { return this.state.ui.isMobile; },
    get theme() { return this.state.ui.theme; },
    get language() { return this.state.ui.language; },
    
    // ========================================================================
    // AUTH MUTÁCIÓK
    // ========================================================================
    
    setAuth(user) {
        if (!user) return;
        this.state.authenticated = true;
        this.state.user = {
            id: user.id,
            username: user.username,
            role: user.role,
            email: user.email
        };
        console.log('✅ Felhasználó bejelentkezve:', user.username);
    },
    
    clearAuth() {
        this.state.authenticated = false;
        this.state.user = null;
    },
    
    // ========================================================================
    // KAPCSOLAT MUTÁCIÓK
    // ========================================================================
    
    setConnected(status) {
        this.state.connected = status;
        console.log('🔌 Kapcsolat állapot:', status);
    },
    
    // ========================================================================
    // RENDSZER MUTÁCIÓK
    // ========================================================================
    
    setSystemId(id) {
        this.state.systemId = id;
    },
    
    // ========================================================================
    // BESZÉLGETÉS MUTÁCIÓK
    // ========================================================================
    
    setConversations(convs) {
        this.state.conversations = convs;
        console.log('📋 Beszélgetések betöltve:', convs.length);
    },
    
    setCurrentConversationId(id) {
        console.log('🔄 Aktuális beszélgetés váltás:', id);
        this.state.currentConversationId = id;
        // Force frissítés
        this.state._updateTrigger++;
    },
    
    setMessages(id, msgs) {
        if (!this.state.messages) this.state.messages = {};
        // Új objektum létrehozása a reaktivitáshoz
        this.state.messages = {
            ...this.state.messages,
            [id]: msgs
        };
        console.log(`💬 Üzenetek beállítva conv ${id}:`, msgs.length);
    },
    
    addMessage(id, msg) {
        console.log('📝 store.addMessage hívva:', { id, msgPreview: msg.content?.substring(0, 50) });
        
        // Biztosítjuk, hogy a messages objektum létezik
        if (!this.state.messages) {
            this.state.messages = {};
        }
        
        // Aktuális üzenetek lekérése
        const currentMessages = this.state.messages[id] || [];
        
        // Új tömb létrehozása
        const newMessages = [...currentMessages, msg];
        
        // Reaktív frissítés - teljesen új messages objektum
        this.state.messages = {
            ...this.state.messages,
            [id]: newMessages
        };
        
        // Statisztika frissítés
        this.state.metrics.total_messages = (this.state.metrics.total_messages || 0) + 1;
        if (msg.role === 'assistant') {
            this.state.kingState.response_count = (this.state.kingState.response_count || 0) + 1;
        }
        
        // Force frissítés
        this.state._updateTrigger++;
        
        console.log(`✅ Üzenet hozzáadva conv ${id}, most ${newMessages.length} üzenet`);
        
        // Ha ez az aktuális beszélgetés, scroll trigger
        if (id === this.state.currentConversationId) {
            Vue.nextTick(() => {
                const container = document.querySelector('.chat-messages');
                if (container) container.scrollTop = container.scrollHeight;
            });
        }
    },
    
    removeConversation(id) {
		console.log(`🗑️ Beszélgetés törlése: ${id}`);
		
		// Töröljük a beszélgetést a listából
		const newConversations = this.state.conversations.filter(c => c.id !== id);
		this.state.conversations = newConversations;
		
		// Töröljük az üzeneteket
		const newMessages = { ...this.state.messages };
		delete newMessages[id];
		this.state.messages = newMessages;
		
		// Ha az aktuális beszélgetést töröltük
		if (this.state.currentConversationId === id) {
			if (newConversations.length > 0) {
				// Van másik beszélgetés, válasszuk az elsőt
				this.state.currentConversationId = newConversations[0].id;
				console.log(`📌 Új aktuális beszélgetés: ${this.state.currentConversationId}`);
			} else {
				// Nincs több beszélgetés, állítsuk null-ra (ne hozzunk létre automatikusan)
				this.state.currentConversationId = null;
				console.log('📌 Nincs aktuális beszélgetés');
			}
		}
		
		// Force frissítés
		this.state._updateTrigger = (this.state._updateTrigger || 0) + 1;
	}, 

	createNewConversation() {
		const newId = Date.now();
		const newConv = {
			id: newId,
			title: `Új beszélgetés`,
			created_at: Date.now(),
			updated_at: Date.now(),
			message_count: 0,
			last_message: null
		};
		
		this.state.conversations = [...this.state.conversations, newConv];
		this.state.messages = {
			...this.state.messages,
			[newId]: []
		};
		this.state.currentConversationId = newId;
		
		console.log(`✅ Új beszélgetés létrehozva: ${newId}`);
		
		// Force frissítés
		this.state._updateTrigger = (this.state._updateTrigger || 0) + 1;
		
		return newId;
	},
    
    // ========================================================================
    // MODELL MUTÁCIÓK
    // ========================================================================
    
    setModels(models) {
        this.state.models = models;
    },
    
    activateModel(id) {
        this.state.models = this.state.models.map(m => ({
            ...m,
            is_active: m.id === id
        }));
    },
    
    // ========================================================================
    // PROMPT MUTÁCIÓK
    // ========================================================================
    
    setPrompts(prompts) {
        this.state.prompts = prompts;
    },
    
    addPrompt(prompt) {
        this.state.prompts.push(prompt);
    },
    
    updatePrompt(id, updates) {
        const index = this.state.prompts.findIndex(p => p.id === id);
        if (index !== -1) {
            this.state.prompts[index] = { ...this.state.prompts[index], ...updates };
        }
    },
    
    removePrompt(id) {
        this.state.prompts = this.state.prompts.filter(p => p.id !== id);
    },
    
    // ========================================================================
    // SZEMÉLYISÉG MUTÁCIÓK
    // ========================================================================
    
    setPersonalities(personalities) {
        this.state.personalities = personalities;
    },
    
    addPersonality(personality) {
        this.state.personalities.push(personality);
    },
    
    updatePersonality(id, updates) {
        const index = this.state.personalities.findIndex(p => p.id === id);
        if (index !== -1) {
            this.state.personalities[index] = { ...this.state.personalities[index], ...updates };
        }
    },
    
    removePersonality(id) {
        this.state.personalities = this.state.personalities.filter(p => p.id !== id);
        if (this.state.activePersonalityId === id) {
            this.state.activePersonalityId = null;
        }
    },
    
    activatePersonality(id) {
        this.state.activePersonalityId = id;
    },
    
    // ========================================================================
    // MODUL MUTÁCIÓK
    // ========================================================================
    
    setModules(modules) {
        this.state.modules = modules;
    },
    
    updateModule(name, status) {
        this.state.modules[name] = status;
    },
    
    // ========================================================================
    // KIRÁLY MUTÁCIÓK
    // ========================================================================
    
    setKingState(state) {
        this.state.kingState = { ...this.state.kingState, ...state };
    },
    
    // ========================================================================
    // HEARTBEAT MUTÁCIÓK
    // ========================================================================
    
    setHeartbeat(hb) {
        this.state.heartbeat = { ...this.state.heartbeat, ...hb };
    },
    
    // ========================================================================
    // GPU MUTÁCIÓK
    // ========================================================================
    
    setGpuStatus(gpus) {
        this.state.gpuStatus = gpus.map(g => ({
            ...g,
            tempLevel: g.temperature < 60 ? 'normal' : (g.temperature < 80 ? 'warm' : 'hot'),
            vram_percent: g.vram_used && g.vram_total ? (g.vram_used / g.vram_total) * 100 : 0
        }));
    },
    
    // ========================================================================
    // SENTINEL MUTÁCIÓK
    // ========================================================================
    
    setSentinelState(state) {
        this.state.sentinelState = { ...this.state.sentinelState, ...state };
    },
    
    // ========================================================================
    // BLACKBOX MUTÁCIÓK
    // ========================================================================
    
    setBlackboxStats(stats) {
        this.state.blackboxStats = { ...this.state.blackboxStats, ...stats };
    },
    
    setTraces(traces) {
        this.state.traces = traces;
    },
    
    addTrace(trace) {
        this.state.traces.unshift(trace);
        if (this.state.traces.length > 1000) {
            this.state.traces.pop();
        }
    },
    
    // ========================================================================
    // METRIKA MUTÁCIÓK
    // ========================================================================
    
    setMetrics(metrics) {
        this.state.metrics = { ...this.state.metrics, ...metrics };
    },
    
    // ========================================================================
    // AUDIT LOG MUTÁCIÓK
    // ========================================================================
    
    setAuditLog(logs) {
        this.state.auditLog = logs;
    },
    
    addAuditEntry(entry) {
        this.state.auditLog.unshift(entry);
        if (this.state.auditLog.length > 1000) {
            this.state.auditLog.pop();
        }
    },
    
    // ========================================================================
    // GATEWAY MUTÁCIÓK
    // ========================================================================
    
    setGateways(gateways) {
        this.state.gateways = gateways;
    },
    
    updateGateway(id, updates) {
        const index = this.state.gateways.findIndex(g => g.id === id);
        if (index !== -1) {
            this.state.gateways[index] = { ...this.state.gateways[index], ...updates };
        }
    },
    
    // ========================================================================
    // BEÁLLÍTÁS MUTÁCIÓK
    // ========================================================================
    
    setSettings(settings) {
        this.state.settings = { ...this.state.settings, ...settings };
    },
    
    updateSetting(key, value) {
        this.state.settings[key] = value;
    },
    
    // ========================================================================
    // ÉRTESÍTÉS MUTÁCIÓK
    // ========================================================================
    
    addNotification(type, message, title = null) {
		// Biztosítjuk, hogy a notifications tömb létezik
		if (!this.state.ui.notifications || !Array.isArray(this.state.ui.notifications)) {
			this.state.ui.notifications = [];
		}
		
		const id = Date.now();
		const newNotifications = [...this.state.ui.notifications, { id, type, message, title }];
		this.state.ui.notifications = newNotifications;
		
		setTimeout(() => {
			if (this.state.ui.notifications && Array.isArray(this.state.ui.notifications)) {
				this.state.ui.notifications = this.state.ui.notifications.filter(n => n.id !== id);
			}
		}, 5000);
		return id;
	},
    
    removeNotification(id) {
        this.state.ui.notifications = this.state.ui.notifications.filter(n => n.id !== id);
    },
    
    clearNotifications() {
        this.state.ui.notifications = [];
    },
    
    // ========================================================================
    // UI MUTÁCIÓK
    // ========================================================================
    
    toggleLeftPanel() {
        this.state.ui.leftPanelVisible = !this.state.ui.leftPanelVisible;
        if (this.state.ui.isMobile && this.state.ui.leftPanelVisible) {
            this.state.ui.rightPanelVisible = false;
        }
    },
    
    toggleRightPanel() {
        this.state.ui.rightPanelVisible = !this.state.ui.rightPanelVisible;
        if (this.state.ui.isMobile && this.state.ui.rightPanelVisible) {
            this.state.ui.leftPanelVisible = false;
        }
    },
    
    closeAllPanels() {
        this.state.ui.leftPanelVisible = false;
        this.state.ui.rightPanelVisible = false;
    },
    
    showChatOnly() {
        this.state.ui.leftPanelVisible = false;
        this.state.ui.rightPanelVisible = false;
    },
    
    setTheme(theme) {
        this.state.ui.theme = theme;
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
    },
    
    setLanguage(lang) {
        this.state.ui.language = lang;
        localStorage.setItem('language', lang);
    },
    
    handleResize() {
        const wasMobile = this.state.ui.isMobile;
        this.state.ui.isMobile = window.innerWidth <= 768;
        if (wasMobile && !this.state.ui.isMobile) {
            this.state.ui.leftPanelVisible = true;
            this.state.ui.rightPanelVisible = true;
        }
        if (!wasMobile && this.state.ui.isMobile) {
            this.state.ui.leftPanelVisible = false;
            this.state.ui.rightPanelVisible = false;
        }
    },
    
    // ========================================================================
    // INICIALIZÁLÁS
    // ========================================================================
    
    init() {
        console.log('🔧 Store inicializálás...');
        
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme) this.setTheme(savedTheme);
        else this.setTheme('dark');
        
        const savedLang = localStorage.getItem('language');
        if (savedLang) this.setLanguage(savedLang);
        
        window.addEventListener('resize', () => this.handleResize());
        
        // ========== BIZTOSÍTSUK, HOGY VAN BESZÉLGETÉS ==========
        if (!this.state.conversations || this.state.conversations.length === 0) {
            console.log('📝 Nincs beszélgetés, létrehozok egyet...');
            const defaultConv = {
                id: 1,
                title: 'Új beszélgetés',
                created_at: Date.now(),
                updated_at: Date.now(),
                message_count: 0,
                last_message: null
            };
            this.state.conversations = [defaultConv];
        }
        
        // Biztosítsuk, hogy a messages objektum létezik
        if (!this.state.messages) {
            this.state.messages = {};
        }
        
        // Biztosítsuk, hogy van aktuális beszélgetés kiválasztva
        if (!this.state.currentConversationId && this.state.conversations.length > 0) {
            this.state.currentConversationId = this.state.conversations[0].id;
            console.log('✅ Aktuális beszélgetés beállítva:', this.state.currentConversationId);
        }
        
        // Biztosítsuk, hogy a kiválasztott beszélgetéshez van üzenet tömb
        if (this.state.currentConversationId && !this.state.messages[this.state.currentConversationId]) {
            this.state.messages[this.state.currentConversationId] = [];
        }
        
        console.log('✅ Store inicializálva', {
            conversations: this.state.conversations.length,
            currentId: this.state.currentConversationId,
            hasMessages: this.state.currentConversationId ? !!this.state.messages[this.state.currentConversationId] : false,
            messagesKeys: Object.keys(this.state.messages)
        });
        
        // Force frissítés
        this.state._updateTrigger++;
    }
};

// Store inicializálása
window.store.init();
console.log('✅ Store modul betöltve');