// Központi állapotkezelés (Vue reactive object) - GLOBÁLISAN
window.store = {
    state: Vue.reactive({
        // === ALAP ÁLLAPOTOK ===
        connected: false,
        isAdmin: false,
        currentUserId: null,
        currentConversationId: null,
        conversations: [],
        messages: [],
        loading: false,
        error: null,
        
        // === RENDSZER ÁLLAPOTOK ===
        heartbeat: {
            uptime_seconds: 0,
            uptime_formatted: '0s',
            beats: 0,
            running: true,
            proactive_count: 0,
            reminder_count: 0
        },
        kingState: {
            status: 'unknown',
            mood: 'neutral',
            model_loaded: false,
            response_count: 0,
            average_response_time: 0
        },
        queenState: {
            status: 'unknown',
            thoughts_count: 0,
            contradictions_found: 0
        },
        jesterState: {
            status: 'unknown',
            warnings: [],
            issues: []
        },
        valetState: {
            status: 'unknown',
            memories_stored: 0,
            rag_searches: 0
        },
        
        // === HARDVER ÁLLAPOTOK ===
        gpuStatus: [],
        sentinelState: {
            throttle_active: false,
            throttle_factor: 1.0,
            recovery_mode: false,
            warnings: []
        },
        
        // === MODULOK ===
        moduleStatuses: {},
        
        // === BEÁLLÍTÁSOK ===
        settings: {},
        models: [],
        prompts: [],
        personalities: [],
        
        // === FELHASZNÁLÓ ===
        user: {
            name: 'User',
            language: 'en',
            role: 'user',
            preferences: {}
        },
        
        // === METRIKÁK ===
        metrics: {
            total_messages: 0,
            total_tokens: 0,
            avg_response_time: 0,
            uptime: 0
        },
        
        // === UI ÁLLAPOTOK ===
        ui: {
            sidebarOpen: true,
            theme: 'dark',
            notifications: [],
            modals: {
                login: false,
                confirm: false,
                settings: false
            }
        }
    }),
    
    // ========================================================================
    // GETTEREK
    // ========================================================================
    
    // --- ALAP ---
    get connected() { return this.state.connected },
    get isAdmin() { return this.state.isAdmin },
    get currentUserId() { return this.state.currentUserId },
    get currentConversationId() { return this.state.currentConversationId },
    get conversations() { return this.state.conversations },
    get messages() { return this.state.messages },
    get loading() { return this.state.loading },
    get error() { return this.state.error },
    
    // --- RENDSZER ---
    get heartbeat() { return this.state.heartbeat },
    get kingState() { return this.state.kingState },
    get queenState() { return this.state.queenState },
    get jesterState() { return this.state.jesterState },
    get valetState() { return this.state.valetState },
    
    // --- HARDVER ---
    get gpuStatus() { return this.state.gpuStatus },
    get sentinelState() { return this.state.sentinelState },
    
    // --- MODULOK ---
    get moduleStatuses() { return this.state.moduleStatuses },
    
    // --- BEÁLLÍTÁSOK ---
    get settings() { return this.state.settings },
    get models() { return this.state.models },
    get prompts() { return this.state.prompts },
    get personalities() { return this.state.personalities },
    
    // --- FELHASZNÁLÓ ---
    get user() { return this.state.user },
    get userName() { return this.state.user.name },
    get userLanguage() { return this.state.user.language },
    get userRole() { return this.state.user.role },
    
    // --- METRIKÁK ---
    get metrics() { return this.state.metrics },
    
    // --- UI ---
    get ui() { return this.state.ui },
    
    // ========================================================================
    // SETTEREK / MUTÁCIÓK
    // ========================================================================
    
    // --- ALAP ---
    setConnected(value) { this.state.connected = value },
    setIsAdmin(value) { this.state.isAdmin = value },
    setCurrentUserId(value) { this.state.currentUserId = value },
    setCurrentConversationId(value) { this.state.currentConversationId = value },
    setConversations(value) { this.state.conversations = value },
    setMessages(value) { this.state.messages = value },
    
    addMessage(message) { 
        if (message) {
            this.state.messages.push(message);
            this.state.metrics.total_messages++;
        }
    },
    
    clearMessages() { this.state.messages = [] },
    
    setLoading(value) { this.state.loading = value },
    setError(value) { 
        this.state.error = value;
        if (value) {
            this.addNotification('error', value);
        }
    },
    clearError() { this.state.error = null },
    
    // --- RENDSZER ---
    setHeartbeat(value) { 
        this.state.heartbeat = { ...this.state.heartbeat, ...(value || {}) };
    },
    
    setKingState(value) { 
        this.state.kingState = { ...this.state.kingState, ...(value || {}) };
    },
    
    setQueenState(value) { 
        this.state.queenState = { ...this.state.queenState, ...(value || {}) };
    },
    
    setJesterState(value) { 
        this.state.jesterState = { ...this.state.jesterState, ...(value || {}) };
    },
    
    setValetState(value) { 
        this.state.valetState = { ...this.state.valetState, ...(value || {}) };
    },
    
    // --- HARDVER ---
    setGpuStatus(value) { 
        this.state.gpuStatus = (value || []).map(g => ({
            ...g,
            tempLevel: g.temperature < 70 ? 'normal' : (g.temperature < 80 ? 'warm' : 'hot'),
            tempFormatted: `${g.temperature}°C`,
            vramFormatted: `${g.vram_used}/${g.vram_total} MB`
        }));
    },
    
    setSentinelState(value) { 
        this.state.sentinelState = { ...this.state.sentinelState, ...(value || {}) };
    },
    
    // --- MODULOK ---
    setModuleStatuses(value) { this.state.moduleStatuses = value || {} },
    
    updateModuleStatus(module, status) { 
        this.state.moduleStatuses[module] = status;
    },
    
    // --- BEÁLLÍTÁSOK ---
    setSettings(value) { this.state.settings = value || {} },
    
    updateSetting(key, value) { 
        this.state.settings[key] = value;
    },
    
    setModels(value) { this.state.models = value || [] },
    
    addModel(model) { 
        this.state.models.push(model);
    },
    
    updateModel(modelId, updates) {
        const index = this.state.models.findIndex(m => m.id === modelId);
        if (index !== -1) {
            this.state.models[index] = { ...this.state.models[index], ...updates };
        }
    },
    
    setPrompts(value) { this.state.prompts = value || [] },
    
    addPrompt(prompt) { 
        this.state.prompts.push(prompt);
    },
    
    updatePrompt(promptId, updates) {
        const index = this.state.prompts.findIndex(p => p.id === promptId);
        if (index !== -1) {
            this.state.prompts[index] = { ...this.state.prompts[index], ...updates };
        }
    },
    
    setPersonalities(value) { this.state.personalities = value || [] },
    
    // --- FELHASZNÁLÓ ---
    setUser(value) { 
        this.state.user = { ...this.state.user, ...(value || {}) };
    },
    
    setUserName(value) { this.state.user.name = value },
    setUserLanguage(value) { 
        this.state.user.language = value;
        localStorage.setItem('language', value);
    },
    setUserRole(value) { this.state.user.role = value },
    
    // --- METRIKÁK ---
    setMetrics(value) { 
        this.state.metrics = { ...this.state.metrics, ...(value || {}) };
    },
    
    updateMetrics(updates) {
        this.state.metrics = { ...this.state.metrics, ...updates };
    },
    
    // --- UI ---
    setUiState(value) { 
        this.state.ui = { ...this.state.ui, ...(value || {}) };
    },
    
    toggleSidebar() { 
        this.state.ui.sidebarOpen = !this.state.ui.sidebarOpen;
    },
    
    setTheme(theme) { 
        if (['dark', 'light', 'system'].includes(theme)) {
            this.state.ui.theme = theme;
            localStorage.setItem('theme', theme);
            this._applyTheme(theme);
        }
    },
    
    addNotification(type, message, timeout = 5000) {
        const id = Date.now() + Math.random();
        this.state.ui.notifications.push({ id, type, message, timeout });
        
        // Automatikus eltávolítás timeout után
        if (timeout > 0) {
            setTimeout(() => {
                this.removeNotification(id);
            }, timeout);
        }
        
        return id;
    },
    
    removeNotification(id) {
        const index = this.state.ui.notifications.findIndex(n => n.id === id);
        if (index !== -1) {
            this.state.ui.notifications.splice(index, 1);
        }
    },
    
    clearNotifications() {
        this.state.ui.notifications = [];
    },
    
    showModal(modal, data = null) {
        this.state.ui.modals[modal] = { visible: true, data };
    },
    
    hideModal(modal) {
        this.state.ui.modals[modal] = { visible: false, data: null };
    },
    
    // ========================================================================
    // SEGÉDFÜGGVÉNYEK
    // ========================================================================
    
    formatUptime(seconds) {
        if (!seconds) return '0s';
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = Math.floor(seconds % 60);
        if (h > 0) return `${h}h ${m}m`;
        if (m > 0) return `${m}m ${s}s`;
        return `${s}s`;
    },
    
    formatDate(dateStr) {
        if (!dateStr) return '';
        const date = new Date(dateStr);
        return date.toLocaleDateString(this.state.user.language);
    },
    
    formatTime(timestamp) {
        if (!timestamp) return '';
        const date = new Date(timestamp);
        return date.toLocaleTimeString(this.state.user.language);
    },
    
    formatDateTime(timestamp) {
        if (!timestamp) return '';
        const date = new Date(timestamp);
        return date.toLocaleString(this.state.user.language);
    },
    
    formatBytes(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },
    
    formatNumber(num) {
        return new Intl.NumberFormat(this.state.user.language).format(num);
    },
    
    formatPercent(num) {
        return new Intl.NumberFormat(this.state.user.language, {
            style: 'percent',
            minimumFractionDigits: 1,
            maximumFractionDigits: 1
        }).format(num / 100);
    },
    
    // ========================================================================
    // KOMPLEX MŰVELETEK
    // ========================================================================
    
    updateFromStatus(status) {
        if (status.heartbeat) this.setHeartbeat(status.heartbeat);
        if (status.king) this.setKingState(status.king);
        if (status.gpu) this.setGpuStatus(status.gpu);
        if (status.modules) this.setModuleStatuses(status.modules);
        if (status.sentinel) this.setSentinelState(status.sentinel);
        if (status.memory) {
            // memory update
        }
    },
    
    reset() {
        this.state.connected = false;
        this.state.isAdmin = false;
        this.state.currentUserId = null;
        this.state.currentConversationId = null;
        this.state.conversations = [];
        this.state.messages = [];
        this.state.loading = false;
        this.state.error = null;
        this.state.moduleStatuses = {};
        this.clearNotifications();
    },
    
    // ========================================================================
    // PRIVÁT SEGÉDFÜGGVÉNYEK
    // ========================================================================
    
    _applyTheme(theme) {
        if (theme === 'system') {
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            document.documentElement.setAttribute('data-theme', prefersDark ? 'dark' : 'light');
        } else {
            document.documentElement.setAttribute('data-theme', theme);
        }
    }
};

// Mentett beállítások betöltése
const savedLanguage = localStorage.getItem('language');
if (savedLanguage) {
    window.store.setUserLanguage(savedLanguage);
}

const savedTheme = localStorage.getItem('theme');
if (savedTheme) {
    window.store.setTheme(savedTheme);
} else {
    window.store.setTheme('dark');
}

console.log('✅ Store betöltve globálisan');