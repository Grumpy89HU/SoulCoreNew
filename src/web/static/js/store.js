// Központi állapotkezelés (Vue reactive object) - GLOBÁLISAN
window.store = {
    state: Vue.reactive({
        connected: false,
        isAdmin: false,
        currentConversationId: null,
        conversations: [],
        messages: [],
        heartbeat: {
            uptime_seconds: 0,
            beats: 0,
            running: true
        },
        kingState: {
            status: 'unknown'
        },
        gpuStatus: [],
        moduleStatuses: {},
        settings: {},
        models: [],
        prompts: [],
        loading: false,
        error: null
    }),
    
    // Getterek
    get connected() { return this.state.connected },
    get isAdmin() { return this.state.isAdmin },
    get currentConversationId() { return this.state.currentConversationId },
    get conversations() { return this.state.conversations },
    get messages() { return this.state.messages },
    get heartbeat() { return this.state.heartbeat },
    get kingState() { return this.state.kingState },
    get gpuStatus() { return this.state.gpuStatus },
    get moduleStatuses() { return this.state.moduleStatuses },
    get settings() { return this.state.settings },
    get models() { return this.state.models },
    get prompts() { return this.state.prompts },
    get loading() { return this.state.loading },
    get error() { return this.state.error },
    
    // Setterek / Mutációk
    setConnected(value) { this.state.connected = value },
    setIsAdmin(value) { this.state.isAdmin = value },
    setCurrentConversationId(value) { this.state.currentConversationId = value },
    setConversations(value) { this.state.conversations = value },
    setMessages(value) { this.state.messages = value },
    addMessage(message) { 
        if (message) this.state.messages.push(message) 
    },
    setHeartbeat(value) { this.state.heartbeat = value || {} },
    setKingState(value) { this.state.kingState = value || {} },
    setGpuStatus(value) { 
        this.state.gpuStatus = (value || []).map(g => ({
            ...g,
            tempLevel: g.temperature < 70 ? 'normal' : (g.temperature < 80 ? 'warm' : 'hot')
        }))
    },
    setModuleStatuses(value) { this.state.moduleStatuses = value || {} },
    setSettings(value) { this.state.settings = value || {} },
    setModels(value) { this.state.models = value || [] },
    setPrompts(value) { this.state.prompts = value || [] },
    setLoading(value) { this.state.loading = value },
    setError(value) { this.state.error = value },
    
    // Segédfüggvények
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
        return date.toLocaleDateString();
    },
    
    formatTime(timestamp) {
        if (!timestamp) return '';
        const date = new Date(timestamp);
        return date.toLocaleTimeString();
    }
};

console.log('✅ Store betöltve globálisan');