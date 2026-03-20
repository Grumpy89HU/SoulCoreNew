// ==============================================
// SOULCORE 3.0 - Globális állapotkezelés
// ==============================================

window.store = {
    state: Vue.reactive({
        // --- AUTH ---
        authenticated: false,
        user: null,
        token: null,
        
        // --- KAPCSOLAT ---
        connected: false,
        socketId: null,
        
        // --- RENDSZER ---
        systemId: null,
        uptime: 0,
        status: 'unknown',
        
        // --- MODULOK ---
        modules: {},
        kingState: {
            status: 'unknown',
            mood: 'neutral',
            model_loaded: false
        },
        sentinelState: {
            gpus: [],
            throttle_active: false
        },
        
        // --- BESZÉLGETÉSEK ---
        conversations: [],
        currentConversationId: null,
        messages: {},
        
        // --- MODELLEK ---
        models: [],
        currentModel: null,
        
        // --- PROMPTOK ---
        prompts: [],
        
        // --- BEÁLLÍTÁSOK ---
        settings: {},
        
        // --- UI ---
        ui: {
            leftPanelVisible: window.innerWidth > 768,
            rightPanelVisible: window.innerWidth > 768,
            isMobile: window.innerWidth <= 768,
            theme: 'dark',
            notifications: []
        },
        
        // --- HIBÁK ---
        error: null
    }),
    
    // ========================================================================
    // GETTEREK
    // ========================================================================
    
    get authenticated() { return this.state.authenticated },
    get user() { return this.state.user },
    get connected() { return this.state.connected },
    get systemId() { return this.state.systemId },
    get modules() { return this.state.modules },
    get kingState() { return this.state.kingState },
    get sentinelState() { return this.state.sentinelState },
    get conversations() { return this.state.conversations },
    get currentConversationId() { return this.state.currentConversationId },
    get currentConversation() {
        return this.state.conversations.find(c => c.id === this.state.currentConversationId);
    },
    get messages() {
        const id = this.state.currentConversationId;
        return id ? this.state.messages[id] || [] : [];
    },
    get models() { return this.state.models },
    get currentModel() { return this.state.currentModel },
    get prompts() { return this.state.prompts },
    get settings() { return this.state.settings },
    get leftPanelVisible() { return this.state.ui.leftPanelVisible },
    get rightPanelVisible() { return this.state.ui.rightPanelVisible },
    get isMobile() { return this.state.ui.isMobile },
    get theme() { return this.state.ui.theme },
    get notifications() { return this.state.ui.notifications },
    get error() { return this.state.error },
    
    // ========================================================================
    // AUTH MUTÁCIÓK
    // ========================================================================
    
    setAuth(user, token = null) {
        this.state.authenticated = true;
        this.state.user = user;
        this.state.token = token;
        localStorage.setItem('user', JSON.stringify(user));
        if (token) localStorage.setItem('token', token);
    },
    
    clearAuth() {
        this.state.authenticated = false;
        this.state.user = null;
        this.state.token = null;
        localStorage.removeItem('user');
        localStorage.removeItem('token');
    },
    
    // ========================================================================
    // KAPCSOLAT MUTÁCIÓK
    // ========================================================================
    
    setConnected(status) {
        this.state.connected = status;
    },
    
    setSocketId(id) {
        this.state.socketId = id;
    },
    
    // ========================================================================
    // RENDSZER MUTÁCIÓK
    // ========================================================================
    
    setSystemId(id) {
        this.state.systemId = id;
    },
    
    setUptime(seconds) {
        this.state.uptime = seconds;
    },
    
    setStatus(status) {
        this.state.status = status;
    },
    
    setKingState(state) {
        this.state.kingState = { ...this.state.kingState, ...state };
    },
    
    setSentinelState(state) {
        this.state.sentinelState = { ...this.state.sentinelState, ...state };
    },
    
    setModules(modules) {
        this.state.modules = modules;
    },
    
    updateModule(name, status) {
        this.state.modules[name] = status;
    },
    
    // ========================================================================
    // BESZÉLGETÉS MUTÁCIÓK
    // ========================================================================
    
    setConversations(conversations) {
        this.state.conversations = conversations;
    },
    
    addConversation(conversation) {
        this.state.conversations.unshift(conversation);
    },
    
    updateConversation(id, updates) {
        const index = this.state.conversations.findIndex(c => c.id === id);
        if (index !== -1) {
            this.state.conversations[index] = { ...this.state.conversations[index], ...updates };
        }
    },
    
    removeConversation(id) {
        this.state.conversations = this.state.conversations.filter(c => c.id !== id);
        if (this.state.currentConversationId === id) {
            this.state.currentConversationId = null;
        }
    },
    
    setCurrentConversationId(id) {
        this.state.currentConversationId = id;
        if (id && !this.state.messages[id]) {
            this.state.messages[id] = [];
        }
    },
    
    setMessages(conversationId, messages) {
        this.state.messages[conversationId] = messages;
    },
    
    addMessage(conversationId, message) {
        if (!this.state.messages[conversationId]) {
            this.state.messages[conversationId] = [];
        }
        this.state.messages[conversationId].push(message);
    },
    
    // ========================================================================
    // MODELL MUTÁCIÓK
    // ========================================================================
    
    setModels(models) {
        this.state.models = models;
        const active = models.find(m => m.is_active);
        if (active) {
            this.state.currentModel = active;
        }
    },
    
    setCurrentModel(model) {
        this.state.currentModel = model;
    },
    
    activateModel(modelId) {
        this.state.models = this.state.models.map(m => ({
            ...m,
            is_active: m.id === modelId
        }));
        const active = this.state.models.find(m => m.id === modelId);
        if (active) {
            this.state.currentModel = active;
        }
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
    // BEÁLLÍTÁS MUTÁCIÓK
    // ========================================================================
    
    setSettings(settings) {
        this.state.settings = { ...this.state.settings, ...settings };
    },
    
    updateSetting(key, value) {
        this.state.settings[key] = value;
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
    
    showChatOnly() {
        this.state.ui.leftPanelVisible = false;
        this.state.ui.rightPanelVisible = false;
    },
    
    closeAllPanels() {
        this.state.ui.leftPanelVisible = false;
        this.state.ui.rightPanelVisible = false;
    },
    
    setTheme(theme) {
        this.state.ui.theme = theme;
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
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
    // NOTIFIKÁCIÓK
    // ========================================================================
    
    addNotification(type, message, title = null, timeout = 5000) {
        const id = Date.now() + Math.random();
        const notification = { id, type, message, title };
        
        this.state.ui.notifications.push(notification);
        
        if (timeout > 0) {
            setTimeout(() => {
                this.removeNotification(id);
            }, timeout);
        }
        
        return id;
    },
    
    removeNotification(id) {
        this.state.ui.notifications = this.state.ui.notifications.filter(n => n.id !== id);
    },
    
    clearNotifications() {
        this.state.ui.notifications = [];
    },
    
    // ========================================================================
    // HIBAKEZELÉS
    // ========================================================================
    
    setError(error) {
        this.state.error = error;
        if (error) {
            console.error('Store error:', error);
        }
    },
    
    clearError() {
        this.state.error = null;
    },
    
    // ========================================================================
    // INICIALIZÁLÁS
    // ========================================================================
    
    init() {
        // Mentett adatok betöltése
        const savedUser = localStorage.getItem('user');
        if (savedUser) {
            try {
                this.state.user = JSON.parse(savedUser);
                this.state.authenticated = true;
            } catch (e) {
                console.error('Hiba a felhasználói adatok betöltésekor:', e);
            }
        }
        
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme) {
            this.state.ui.theme = savedTheme;
            document.documentElement.setAttribute('data-theme', savedTheme);
        }
        
        // Resize esemény figyelése
        window.addEventListener('resize', () => this.handleResize());
        
        console.log('✅ Store inicializálva');
    }
};

// Store inicializálása
window.store.init();

console.log('✅ Store modul betöltve');