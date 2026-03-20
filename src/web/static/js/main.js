// ==============================================
// SOULCORE 3.0 - Fő Vue alkalmazás (TELJES)
// ==============================================

// Globális segédfüggvények (biztonsági fallback)
if (!window.getNotificationIcon) {
    window.getNotificationIcon = function(type) {
        const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
        return icons[type] || '📢';
    };
}

// Vue alkalmazás létrehozása
const { createApp, ref, computed, onMounted, onUnmounted, nextTick, watch } = Vue;

const App = {
    setup() {
        // ====================================================================
        // REAKTÍV ÁLLAPOTOK
        // ====================================================================
        
        const authenticated = computed(() => window.store.authenticated);
        const user = computed(() => window.store.user);
        const isAdmin = computed(() => user.value?.role === 'admin');
        const connected = computed(() => window.store.connected);
        const systemId = computed(() => window.store.systemId);
        const heartbeat = computed(() => window.store.heartbeat);
        const kingState = computed(() => window.store.kingState);
        const notifications = computed(() => window.store.notifications);
        
        const leftPanelVisible = computed(() => window.store.leftPanelVisible);
        const rightPanelVisible = computed(() => window.store.rightPanelVisible);
        const isMobile = computed(() => window.store.isMobile);
        
        const currentTime = ref(new Date().toLocaleTimeString());
        const showAboutModal = ref(false);
        const showUserMenu = ref(false);
        
        // ====================================================================
        // SEGÉDFÜGGVÉNYEK
        // ====================================================================
        
        const t = (key, params = {}) => window.gettext(key, params);
        
        // ====================================================================
        // METÓDUSOK
        // ====================================================================
        
        const toggleLeftPanel = () => window.store.toggleLeftPanel();
        const toggleRightPanel = () => window.store.toggleRightPanel();
        const closeAllPanels = () => window.store.closeAllPanels();
        
        const logout = async () => {
            if (confirm(t('auth.confirm_logout'))) {
                await window.api.logout();
            }
        };
        
        const hideUserMenu = () => { showUserMenu.value = false; };
        const removeNotification = (id) => window.store.removeNotification(id);
        
        // ====================================================================
        // ÉLETCIKLUS - IDŐZÍTŐ CLEANUP-PAL
        // ====================================================================
        
        let timeInterval = null;
        
        onMounted(async () => {
            // Idő frissítése
            timeInterval = setInterval(() => {
                currentTime.value = new Date().toLocaleTimeString();
            }, 1000);
            
            try {
                await window.api.getCurrentUser();
                
                if (window.store.authenticated) {
                    await window.api.loadInitialData();
                }
            } catch (error) {
                console.error('Init error:', error);
            }
        });
        
        onUnmounted(() => {
            if (timeInterval) {
                clearInterval(timeInterval);
                timeInterval = null;
            }
        });
        
        // ====================================================================
        // RETURN
        // ====================================================================
        
        return {
            authenticated,
            user,
            isAdmin,
            connected,
            systemId,
            heartbeat,
            kingState,
            notifications,
            leftPanelVisible,
            rightPanelVisible,
            isMobile,
            currentTime,
            showAboutModal,
            showUserMenu,
            t,
            toggleLeftPanel,
            toggleRightPanel,
            closeAllPanels,
            logout,
            hideUserMenu,
            removeNotification,
            formatUptime: window.formatUptime,
            getNotificationIcon: window.getNotificationIcon
        };
    },
    
    template: `
        <div class="app">
            <!-- Fejléc -->
            <div class="header">
                <div class="header-left">
                    <button class="menu-toggle" @click="closeAllPanels" v-if="isMobile">☰</button>
                    <div class="logo">✦ SOULCORE 3.0</div>
                </div>
                <div class="header-right">
                    <div class="status-badge">
                        <div class="badge">💓 {{ formatUptime(heartbeat?.uptime_seconds || 0) }}</div>
                        <div class="badge">👑 {{ kingState?.status || 'unknown' }}</div>
                    </div>
                    <div class="user-menu" v-if="authenticated">
                        <button class="user-menu-btn" @click="showUserMenu = !showUserMenu">
                            👤 {{ user?.username }}
                        </button>
                        <div class="user-menu-dropdown" v-if="showUserMenu" v-click-outside="hideUserMenu">
                            <a href="/profile" class="dropdown-item">👤 Profil</a>
                            <a v-if="isAdmin" href="/admin" class="dropdown-item">⚙️ Admin</a>
                            <a href="#" @click.prevent="logout" class="dropdown-item">🚪 Kijelentkezés</a>
                        </div>
                    </div>
                    <a v-else href="/login" class="btn btn-primary">Bejelentkezés</a>
                    <button class="icon-btn" @click="showAboutModal = true">ℹ️</button>
                </div>
            </div>
            
            <!-- Értesítések -->
            <div class="notifications-container">
                <div v-for="n in notifications" :key="n.id" class="notification" :class="n.type" @click="removeNotification(n.id)">
                    <span class="notification-icon">{{ getNotificationIcon(n.type) }}</span>
                    <div class="notification-content"><div class="notification-message">{{ n.message }}</div></div>
                    <button class="notification-close" @click.stop="removeNotification(n.id)">✕</button>
                </div>
            </div>
            
            <!-- Névjegy modal -->
            <div class="modal" v-if="showAboutModal" @click.self="showAboutModal = false">
                <div class="modal-content small">
                    <div class="modal-header"><h3>{{ t('ui.about') }}</h3><button class="modal-close" @click="showAboutModal = false">✕</button></div>
                    <div class="modal-body" style="text-align:center">
                        <div style="font-size:48px">✦</div>
                        <h2>SoulCore 3.0</h2>
                        <p>ID: {{ systemId }}</p>
                        <p style="margin-top:16px">Szuverén AI rendszer</p>
                    </div>
                    <div class="modal-footer"><button class="btn btn-primary" @click="showAboutModal = false">{{ t('ui.close') }}</button></div>
                </div>
            </div>
            
            <!-- Fő tartalom -->
            <div class="main" v-if="authenticated">
                <!-- Bal panel -->
                <div class="left-panel" :class="{ 'mobile-visible': leftPanelVisible && isMobile }">
                    <div class="panel-section">
                        <div class="panel-header">{{ t('conversations.title') }}</div>
                        <div class="panel-content"><conversation-list></conversation-list></div>
                    </div>
                    <div class="panel-section">
                        <div class="panel-header">{{ t('telemetry.title') }}</div>
                        <div class="panel-content"><telemetry-panel></telemetry-panel></div>
                    </div>
                </div>
                
                <!-- Középső panel -->
                <div class="center-panel"><chat-box></chat-box></div>
                
                <!-- Jobb panel (admin) -->
                <div class="right-panel" v-if="isAdmin" :class="{ 'mobile-visible': rightPanelVisible && isMobile }">
                    <div class="panel-section">
                        <div class="panel-header">{{ t('admin.modules') }}</div>
                        <div class="panel-content"><admin-panel></admin-panel></div>
                    </div>
                </div>
                
                <!-- Mobil panel toggle gombok -->
                <button v-if="isMobile && !leftPanelVisible" class="panel-toggle left-toggle" @click="toggleLeftPanel">▶</button>
                <button v-if="isMobile && !rightPanelVisible && isAdmin" class="panel-toggle right-toggle" @click="toggleRightPanel">◀</button>
                <div v-if="isMobile && (leftPanelVisible || rightPanelVisible)" class="panel-overlay" @click="closeAllPanels"></div>
            </div>
            
            <!-- Bejelentkezési oldal (ha nincs bejelentkezve) -->
            <div class="main" v-else style="justify-content: center; align-items: center;">
                <login-form></login-form>
            </div>
            
            <!-- Lábléc -->
            <div class="footer">
                <div class="footer-left">v3.0.0<span v-if="systemId"> | ID: {{ systemId }}</span></div>
                <div class="connection-status">
                    <span class="status-dot" :class="{ connected }"></span>
                    {{ connected ? t('ui.connected') : t('ui.disconnected') }}
                </div>
                <div>{{ currentTime }}</div>
            </div>
        </div>
    `
};

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

// Alkalmazás létrehozása
const app = createApp(App);
app.directive('click-outside', vClickOutside);

// ========================================================================
// KOMPONENSEK REGISZTRÁLÁSA (BIZTONSÁGOS)
// ========================================================================

const safeRegister = (name, component) => {
    if (component && typeof component === 'object') {
        app.component(name, component);
        console.log(`✅ ${name} regisztrálva`);
    } else {
        console.warn(`⚠️ ${name} nem elérhető, dummy komponens`);
        app.component(name, {
            template: `<div class="component-placeholder">${name} (betöltés...)</div>`
        });
    }
};

// Alap komponensek
safeRegister('conversation-list', window.ConversationList);
safeRegister('chat-box', window.ChatBox);
safeRegister('telemetry-panel', window.TelemetryPanel);
safeRegister('module-control', window.ModuleControl);
safeRegister('model-selector', window.ModelSelector);
safeRegister('prompt-editor', window.PromptEditor);
safeRegister('personality-manager', window.PersonalityManager);
safeRegister('settings-panel', window.SettingsPanel);
safeRegister('admin-panel', window.AdminPanel);
safeRegister('login-form', window.LoginForm);
safeRegister('register-form', window.RegisterForm);

// További komponensek (ha hiányoznak, dummy)
safeRegister('audit-log', window.AuditLog);
safeRegister('metrics-panel', window.MetricsPanel);
safeRegister('trace-panel', window.TracePanel);
safeRegister('vision-upload', window.VisionUpload);
safeRegister('sandbox-editor', window.SandboxEditor);
safeRegister('gateway-panel', window.GatewayPanel);
safeRegister('embedding-panel', window.EmbeddingPanel);
safeRegister('audio-panel', window.AudioPanel);

console.log('✅ Vue alkalmazás elindult');

app.mount('#app');