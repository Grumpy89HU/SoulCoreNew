// ==============================================
// SOULCORE 3.0 - Fő Vue alkalmazás
// ==============================================

// ========================================================================
// GLOBÁLIS SEGÉDFÜGGVÉNYEK
// ========================================================================

window.getNotificationIcon = function(type) {
    const icons = {
        'success': '✅',
        'error': '❌',
        'warning': '⚠️',
        'info': 'ℹ️'
    };
    return icons[type] || '📢';
};

window.formatUptime = function(seconds) {
    if (seconds === undefined || seconds === null) return '0s';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    const parts = [];
    if (h > 0) parts.push(`${h}h`);
    if (m > 0) parts.push(`${m}m`);
    if (s > 0 || parts.length === 0) parts.push(`${s}s`);
    return parts.join(' ');
};

window.truncate = function(text, len = 100) {
    if (!text) return '';
    return text.length > len ? text.substring(0, len) + '...' : text;
};

// ========================================================================
// STORE - globális állapot
// ========================================================================

// Store létrehozása
window.store = {
    state: Vue.reactive({
        authenticated: true,
        user: { id: 1, username: 'admin', role: 'admin', email: 'admin@localhost' },
        connected: true,
        systemId: 'soulcore-' + Math.random().toString(36).substr(2, 8),
        conversations: [
            { id: 1, title: 'Első beszélgetés', last_message: 'Helló!', updated_at: Date.now() - 3600000, message_count: 3 },
            { id: 2, title: 'Második beszélgetés', last_message: 'Hogy vagy?', updated_at: Date.now() - 7200000, message_count: 2 }
        ],
        currentConversationId: 1,
        messages: {
            1: [
                { id: 1, role: 'user', content: 'Helló!', timestamp: Date.now() - 7200000 },
                { id: 2, role: 'assistant', content: 'Szia! Hogy segíthetek?', timestamp: Date.now() - 7190000 },
                { id: 3, role: 'user', content: 'Mi újság?', timestamp: Date.now() - 7180000 },
                { id: 4, role: 'assistant', content: 'Minden rendben, te hogy vagy?', timestamp: Date.now() - 7170000 }
            ],
            2: []
        },
        models: [],
        prompts: [],
        modules: {
            'orchestrator': 'running',
            'king': 'ready',
            'queen': 'ready',
            'jester': 'running',
            'scribe': 'running',
            'valet': 'ready',
            'sentinel': 'running',
            'heartbeat': 'running'
        },
        kingState: { status: 'ready', mood: 'neutral', model_loaded: true },
        heartbeat: { uptime_seconds: 124, running: true, beats: 42 },
        notifications: [],
        ui: {
            leftPanelVisible: true,
            rightPanelVisible: true,
            isMobile: window.innerWidth <= 768
        }
    }),
    
    // GETTEREK
    get authenticated() { return this.state.authenticated },
    get user() { return this.state.user },
    get connected() { return this.state.connected },
    get systemId() { return this.state.systemId },
    get conversations() { return this.state.conversations },
    get currentConversationId() { return this.state.currentConversationId },
    get messages() { 
        const id = this.state.currentConversationId;
        return id ? (this.state.messages[id] || []) : [];
    },
    get modules() { return this.state.modules },
    get kingState() { return this.state.kingState },
    get heartbeat() { return this.state.heartbeat },
    get notifications() { return this.state.ui.notifications },
    get leftPanelVisible() { return this.state.ui.leftPanelVisible },
    get rightPanelVisible() { return this.state.ui.rightPanelVisible },
    get isMobile() { return this.state.ui.isMobile },
    
    // METÓDUSOK
    setConversations(val) { this.state.conversations = val },
    setCurrentConversationId(id) { this.state.currentConversationId = id },
    setMessages(id, msgs) { this.state.messages[id] = msgs },
    addMessage(id, msg) {
        if (!this.state.messages[id]) this.state.messages[id] = [];
        this.state.messages[id].push(msg);
    },
    removeConversation(id) {
        this.state.conversations = this.state.conversations.filter(c => c.id !== id);
        if (this.state.currentConversationId === id) this.state.currentConversationId = null;
    },
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
    addNotification(type, message, title = null) {
        const id = Date.now() + Math.random();
        this.state.ui.notifications.push({ id, type, message, title });
        setTimeout(() => {
            this.state.ui.notifications = this.state.ui.notifications.filter(n => n.id !== id);
        }, 5000);
    },
    removeNotification(id) {
        this.state.ui.notifications = this.state.ui.notifications.filter(n => n.id !== id);
    },
    handleResize() {
        this.state.ui.isMobile = window.innerWidth <= 768;
        if (!this.state.ui.isMobile) {
            this.state.ui.leftPanelVisible = true;
            this.state.ui.rightPanelVisible = true;
        }
    }
};

// Resize esemény
window.addEventListener('resize', () => window.store.handleResize());

// ========================================================================
// KOMPONENSEK
// ========================================================================

// ConversationList komponens (NINCS VÉGTELEN CIKLUS!)
window.ConversationList = {
    name: 'ConversationList',
    template: `
        <div class="conversation-list">
            <button class="btn btn-primary new-conv-btn" @click="createNew" style="width: 100%; margin-bottom: 16px;">
                + Új beszélgetés
            </button>
            
            <div v-if="conversations.length === 0" class="empty-state">
                <div class="empty-icon">💬</div>
                <div class="empty-text">Nincs még beszélgetés</div>
                <button class="btn btn-primary" @click="createNew">Új beszélgetés</button>
            </div>
            
            <div v-else class="conv-list">
                <div v-for="conv in conversations" :key="conv.id" class="conv-item" :class="{ active: currentId === conv.id }" @click="select(conv.id)">
                    <div class="conv-title">{{ conv.title || 'Cím nélkül' }}</div>
                    <div class="conv-preview" v-if="conv.last_message">{{ truncate(conv.last_message, 50) }}</div>
                    <div class="conv-meta">
                        <span>{{ formatRelativeTime(conv.updated_at) }}</span>
                        <button class="delete-btn" @click.stop="deleteConv(conv.id)">🗑️</button>
                    </div>
                </div>
            </div>
        </div>
    `,
    setup() {
        const conversations = Vue.computed(() => window.store.conversations);
        const currentId = Vue.computed(() => window.store.currentConversationId);
        
        const formatRelativeTime = (ts) => {
            if (!ts) return '';
            const diff = Math.floor((Date.now() - new Date(ts).getTime()) / 60000);
            if (diff < 1) return 'most';
            if (diff < 60) return `${diff} perce`;
            if (diff < 1440) return `${Math.floor(diff / 60)} órája`;
            return new Date(ts).toLocaleDateString();
        };
        
        const createNew = () => {
            const title = prompt('Beszélgetés címe');
            if (title) {
                const newConv = {
                    id: Date.now(),
                    title: title,
                    last_message: null,
                    updated_at: Date.now(),
                    message_count: 0
                };
                window.store.setConversations([newConv, ...window.store.conversations]);
                window.store.setCurrentConversationId(newConv.id);
                window.store.setMessages(newConv.id, []);
            }
        };
        
        const select = (id) => {
            window.store.setCurrentConversationId(id);
        };
        
        const deleteConv = (id) => {
            if (confirm('Biztosan törli ezt a beszélgetést?')) {
                window.store.removeConversation(id);
            }
        };
        
        return { conversations, currentId, formatRelativeTime, truncate: window.truncate, createNew, select, deleteConv };
    }
};

// ChatBox komponens
window.ChatBox = {
    name: 'ChatBox',
    template: `
        <div class="chat-container">
            <div class="chat-header">
                <h3>{{ currentConversation?.title || 'Új beszélgetés' }}</h3>
            </div>
            <div class="chat-messages" ref="messagesContainer">
                <div v-if="messages.length === 0" class="empty-state">
                    <div class="empty-icon">💬</div>
                    <div class="empty-text">Kezdjen el beszélgetni!</div>
                </div>
                <div v-for="msg in messages" :key="msg.id" class="message" :class="msg.role">
                    <div class="sender">{{ msg.role === 'user' ? 'Te' : 'Kópé' }}</div>
                    <div class="content">{{ msg.content }}</div>
                    <div class="time">{{ formatTime(msg.timestamp) }}</div>
                </div>
                <div v-if="typing" class="typing-indicator">✍️ gépel...</div>
            </div>
            <div class="chat-input-area">
                <textarea v-model="inputMessage" @keydown.enter.exact.prevent="send" :placeholder="'Írja be üzenetét...'" rows="1"></textarea>
                <button class="send-btn" @click="send" :disabled="!inputMessage.trim()">📤</button>
            </div>
        </div>
    `,
    setup() {
        const currentConversation = Vue.computed(() => {
            const id = window.store.currentConversationId;
            return window.store.conversations.find(c => c.id === id);
        });
        const messages = Vue.computed(() => window.store.messages);
        const inputMessage = Vue.ref('');
        const typing = Vue.ref(false);
        const messagesContainer = Vue.ref(null);
        
        const formatTime = (ts) => ts ? new Date(ts).toLocaleTimeString() : '';
        
        const scrollToBottom = () => {
            Vue.nextTick(() => {
                if (messagesContainer.value) messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
            });
        };
        
        const send = () => {
            const text = inputMessage.value.trim();
            if (!text || !window.store.currentConversationId) return;
            
            // Felhasználói üzenet hozzáadása
            window.store.addMessage(window.store.currentConversationId, {
                id: Date.now(), role: 'user', content: text, timestamp: Date.now()
            });
            inputMessage.value = '';
            scrollToBottom();
            
            // Válasz szimulálása
            setTimeout(() => {
                window.store.addMessage(window.store.currentConversationId, {
                    id: Date.now() + 1, role: 'assistant', content: `Válasz erre: "${text}"`, timestamp: Date.now()
                });
                scrollToBottom();
            }, 500);
        };
        
        Vue.watch(messages, scrollToBottom, { deep: true });
        Vue.watch(() => window.store.currentConversationId, () => {
            Vue.nextTick(scrollToBottom);
        });
        
        return { currentConversation, messages, inputMessage, typing, messagesContainer, formatTime, send };
    }
};

// TelemetryPanel komponens
window.TelemetryPanel = {
    name: 'TelemetryPanel',
    template: `
        <div class="telemetry">
            <div class="metric-group">
                <div class="metric-group-title">Rendszer</div>
                <div class="metric"><label>🔧 Státusz</label><span>fut</span></div>
                <div class="metric"><label>💓 Üzemidő</label><span>{{ formatUptime(heartbeat.uptime_seconds) }}</span></div>
                <div class="metric"><label>🆔 Rendszerazonosító</label><span><code>{{ systemId }}</code></span></div>
            </div>
            <div class="metric-group">
                <div class="metric-group-title">Király</div>
                <div class="metric"><label>👑 Státusz</label><span>{{ kingState.status }}</span></div>
                <div class="metric"><label>😊 Hangulat</label><span>{{ kingState.mood }}</span></div>
            </div>
            <div class="metric-group">
                <div class="metric-group-title">Modulok</div>
                <div v-for="(status, name) in modules" :key="name" class="metric">
                    <label>{{ formatModuleName(name) }}</label>
                    <span class="status-badge" :class="status">{{ status }}</span>
                </div>
            </div>
        </div>
    `,
    setup() {
        const systemId = Vue.computed(() => window.store.systemId);
        const kingState = Vue.computed(() => window.store.kingState);
        const heartbeat = Vue.computed(() => window.store.heartbeat);
        const modules = Vue.computed(() => window.store.modules);
        
        const formatModuleName = (name) => {
            return name.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
        };
        
        return { systemId, kingState, heartbeat, modules, formatModuleName, formatUptime: window.formatUptime };
    }
};

// ModuleControl komponens
window.ModuleControl = {
    name: 'ModuleControl',
    template: `
        <div class="module-control">
            <div v-for="(status, name) in modules" :key="name" class="module-item">
                <div class="module-info">
                    <span class="module-name">{{ formatModuleName(name) }}</span>
                    <span class="module-status" :class="status">{{ status }}</span>
                </div>
                <div class="module-actions">
                    <button v-if="status === 'stopped'" class="btn-icon" @click="control(name, 'start')">▶️</button>
                    <button v-else-if="status !== 'error'" class="btn-icon" @click="control(name, 'stop')">⏹️</button>
                    <button v-if="status !== 'stopped'" class="btn-icon" @click="control(name, 'restart')">🔄</button>
                </div>
            </div>
        </div>
    `,
    setup() {
        const modules = Vue.computed(() => window.store.modules);
        
        const formatModuleName = (name) => {
            return name.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
        };
        
        const control = async (module, action) => {
            window.store.addNotification('info', `${module} - ${action} parancs küldve`);
        };
        
        return { modules, formatModuleName, control };
    }
};

// ========================================================================
// VUE ALKALMAZÁS
// ========================================================================

const App = {
    setup() {
        const user = Vue.computed(() => window.store.user);
        const isAdmin = Vue.computed(() => user.value?.role === 'admin');
        const leftPanelVisible = Vue.computed(() => window.store.leftPanelVisible);
        const rightPanelVisible = Vue.computed(() => window.store.rightPanelVisible);
        const isMobile = Vue.computed(() => window.store.isMobile);
        const connected = Vue.computed(() => window.store.connected);
        const systemId = Vue.computed(() => window.store.systemId);
        const heartbeat = Vue.computed(() => window.store.heartbeat);
        const kingState = Vue.computed(() => window.store.kingState);
        const notifications = Vue.computed(() => window.store.notifications);
        const currentTime = Vue.ref(new Date().toLocaleTimeString());
        const showAboutModal = Vue.ref(false);
        const showUserMenu = Vue.ref(false);
        
        setInterval(() => { currentTime.value = new Date().toLocaleTimeString(); }, 1000);
        
        const toggleLeft = () => window.store.toggleLeftPanel();
        const toggleRight = () => window.store.toggleRightPanel();
        const closeAll = () => window.store.closeAllPanels();
        const hideUserMenu = () => { showUserMenu.value = false; };
        const removeNotification = (id) => window.store.removeNotification(id);
        
        return {
            user, isAdmin, leftPanelVisible, rightPanelVisible, isMobile,
            connected, systemId, heartbeat, kingState, notifications, currentTime,
            showAboutModal, showUserMenu, toggleLeft, toggleRight, closeAll, hideUserMenu, removeNotification,
            formatUptime: window.formatUptime, getNotificationIcon: window.getNotificationIcon
        };
    },
    template: `
        <div class="header">
            <div class="header-left">
                <button class="menu-toggle" @click="closeAll" v-if="isMobile">☰</button>
                <div class="logo">✦ SOULCORE 3.0</div>
            </div>
            <div class="header-right">
                <div class="status-badge">
                    <div class="badge">💓 {{ formatUptime(heartbeat?.uptime_seconds || 0) }}</div>
                    <div class="badge">👑 {{ kingState?.status || 'unknown' }}</div>
                </div>
                <div class="user-menu">
                    <button class="user-menu-btn" @click="showUserMenu = !showUserMenu">👤 {{ user?.username }}</button>
                    <div class="user-menu-dropdown" v-if="showUserMenu" v-click-outside="hideUserMenu">
                        <a href="/profile" class="dropdown-item">Profil</a>
                        <a href="/login" class="dropdown-item">Kijelentkezés</a>
                    </div>
                </div>
                <button class="icon-btn" @click="showAboutModal = true">ℹ️</button>
            </div>
        </div>
        
        <div class="notifications-container">
            <div v-for="n in notifications" :key="n.id" class="notification" :class="n.type" @click="removeNotification(n.id)">
                <span class="notification-icon">{{ getNotificationIcon(n.type) }}</span>
                <div class="notification-content"><div class="notification-message">{{ n.message }}</div></div>
                <button class="notification-close" @click.stop="removeNotification(n.id)">✕</button>
            </div>
        </div>
        
        <div class="modal" v-if="showAboutModal" @click.self="showAboutModal = false">
            <div class="modal-content small">
                <div class="modal-header"><h3>Névjegy</h3><button class="modal-close" @click="showAboutModal = false">✕</button></div>
                <div class="modal-body" style="text-align:center"><div style="font-size:48px">✦</div><h2>SoulCore 3.0</h2><p>ID: {{ systemId }}</p></div>
                <div class="modal-footer"><button class="btn btn-primary" @click="showAboutModal = false">Bezárás</button></div>
            </div>
        </div>
        
        <div class="main">
            <div class="left-panel" :class="{ 'mobile-visible': leftPanelVisible && isMobile }">
                <div class="panel-section"><div class="panel-header">Beszélgetések</div><div class="panel-content"><conversation-list></conversation-list></div></div>
                <div class="panel-section"><div class="panel-header">Rendszerállapot</div><div class="panel-content"><telemetry-panel></telemetry-panel></div></div>
            </div>
            <div class="center-panel"><chat-box></chat-box></div>
            <div class="right-panel" v-if="isAdmin" :class="{ 'mobile-visible': rightPanelVisible && isMobile }">
                <div class="panel-section"><div class="panel-header">Modulok</div><div class="panel-content"><module-control></module-control></div></div>
            </div>
            <button v-if="isMobile && !leftPanelVisible" class="panel-toggle left-toggle" @click="toggleLeft">▶</button>
            <button v-if="isMobile && !rightPanelVisible && isAdmin" class="panel-toggle right-toggle" @click="toggleRight">◀</button>
            <div v-if="isMobile && (leftPanelVisible || rightPanelVisible)" class="panel-overlay" @click="closeAll"></div>
        </div>
        
        <div class="footer">
            <div class="footer-left"><span>v3.0.0</span><span v-if="systemId">ID: {{ systemId }}</span></div>
            <div class="footer-center"><div class="connection-status"><span class="status-dot" :class="{ connected }"></span>{{ connected ? 'Kapcsolódva' : 'Nincs kapcsolat' }}</div></div>
            <div class="footer-right">{{ currentTime }}</div>
        </div>
    `
};

// ========================================================================
// ALKALMAZÁS INDÍTÁSA
// ========================================================================

// Click outside direktíva
const vClickOutside = {
    beforeMount: (el, binding) => {
        el.clickOutsideEvent = (event) => {
            if (!(el === event.target || el.contains(event.target))) {
                binding.value(event);
            }
        };
        document.addEventListener('click', el.clickOutsideEvent);
    },
    unmounted: (el) => {
        document.removeEventListener('click', el.clickOutsideEvent);
    }
};

const app = Vue.createApp(App);
app.directive('click-outside', vClickOutside);

// Komponensek regisztrálása
app.component('conversation-list', window.ConversationList);
app.component('chat-box', window.ChatBox);
app.component('telemetry-panel', window.TelemetryPanel);
app.component('module-control', window.ModuleControl);

app.mount('#app');

console.log('✅ Vue alkalmazás elindult');