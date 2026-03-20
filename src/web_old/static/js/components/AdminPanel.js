// Admin panel (jobb oldali fülek)
window.AdminPanel = {
    template: `
        <div class="admin-panel-container">
            <!-- Admin fejléc -->
            <div class="admin-header" v-if="isAdmin">
                <div class="admin-title">
                    <span class="admin-icon">⚙️</span>
                    {{ gettext('admin.title') }}
                </div>
                <div class="admin-status">
                    <span class="status-dot online"></span>
                    {{ gettext('admin.online') }}
                </div>
            </div>
            
            <!-- Fülek -->
            <div class="tabs" :class="{ 'admin-mode': isAdmin }">
                <div class="tab" 
                     :class="{ active: activeTab == 'modules' }" 
                     @click="activeTab = 'modules'"
                     :title="gettext('admin.tab_modules')">
                    📦 {{ gettext('admin.modules') }}
                </div>
                <div class="tab" 
                     :class="{ active: activeTab == 'models' }" 
                     @click="activeTab = 'models'"
                     :title="gettext('admin.tab_models')">
                    🤖 {{ gettext('admin.models') }}
                </div>
                <div class="tab" 
                     :class="{ active: activeTab == 'prompts' }" 
                     @click="activeTab = 'prompts'"
                     :title="gettext('admin.tab_prompts')">
                    📝 {{ gettext('admin.prompts') }}
                </div>
                <div class="tab" 
                     :class="{ active: activeTab == 'personalities' }" 
                     @click="activeTab = 'personalities'"
                     :title="gettext('admin.tab_personalities')">
                    🧠 {{ gettext('admin.personalities') }}
                </div>
                <div class="tab" 
                     :class="{ active: activeTab == 'settings' }" 
                     @click="activeTab = 'settings'"
                     :title="gettext('admin.tab_settings')">
                    ⚙️ {{ gettext('admin.settings') }}
                </div>
                <div class="tab" 
                     :class="{ active: activeTab == 'traces' }" 
                     @click="activeTab = 'traces'"
                     :title="gettext('admin.tab_traces')">
                    📋 {{ gettext('admin.traces') }}
                </div>
                <div class="tab" 
                     :class="{ active: activeTab == 'audit' }" 
                     @click="activeTab = 'audit'"
                     v-if="isAdmin"
                     :title="gettext('admin.tab_audit')">
                    🔍 {{ gettext('admin.audit') }}
                </div>
                <div class="tab" 
                     :class="{ active: activeTab == 'metrics' }" 
                     @click="activeTab = 'metrics'"
                     v-if="isAdmin"
                     :title="gettext('admin.tab_metrics')">
                    📊 {{ gettext('admin.metrics') }}
                </div>
            </div>
            
            <!-- Tab tartalom -->
            <div class="tab-content">
                <!-- Modulok -->
                <div v-show="activeTab == 'modules'">
                    <module-control></module-control>
                </div>
                
                <!-- Modellek -->
                <div v-show="activeTab == 'models'">
                    <model-selector></model-selector>
                </div>
                
                <!-- Promptok -->
                <div v-show="activeTab == 'prompts'">
                    <prompt-editor></prompt-editor>
                </div>
                
                <!-- Személyiségek -->
                <div v-show="activeTab == 'personalities'">
                    <personality-manager></personality-manager>
                </div>
                
                <!-- Beállítások -->
                <div v-show="activeTab == 'settings'">
                    <settings-panel></settings-panel>
                </div>
                
                <!-- Trace-ek -->
                <div v-show="activeTab == 'traces'">
                    <div class="trace-header">
                        <h3>{{ gettext('admin.live_traces') }}</h3>
                        <button class="clear-btn" @click="clearTraces" v-if="recentTraces.length">
                            🗑️
                        </button>
                    </div>
                    <div class="trace-list">
                        <div v-for="trace in recentTraces" :key="trace.id" 
                             class="trace-item" 
                             :class="'trace-' + trace.type">
                            <span class="trace-time">{{ formatTime(trace.time) }}</span>
                            <span class="trace-type" :title="trace.type">{{ getTraceIcon(trace.type) }}</span>
                            <span class="trace-text">{{ trace.text }}</span>
                        </div>
                        <div v-if="recentTraces.length === 0" class="empty-state">
                            {{ gettext('admin.no_traces') }}
                        </div>
                    </div>
                </div>
                
                <!-- Audit log -->
                <div v-show="activeTab == 'audit'">
                    <audit-log></audit-log>
                </div>
                
                <!-- Metrikák -->
                <div v-show="activeTab == 'metrics'">
                    <system-metrics></system-metrics>
                </div>
            </div>
            
            <!-- Admin footer (bejelentkezés / kijelentkezés) -->
            <div class="admin-footer">
                <div v-if="!isAdmin" class="login-prompt">
                    <button class="admin-login-btn" @click="showLogin">
                        🔐 {{ gettext('admin.login') }}
                    </button>
                </div>
                <div v-else class="admin-info">
                    <div class="admin-badge">
                        👑 {{ gettext('admin.authenticated') }}
                    </div>
                    <button class="logout-btn" @click="logout">
                        🚪 {{ gettext('admin.logout') }}
                    </button>
                </div>
            </div>
        </div>
    `,
    
    setup() {
        // ====================================================================
        // REAKTÍV ÁLLAPOTOK
        // ====================================================================
        
        const activeTab = Vue.ref('modules');
        const recentTraces = Vue.ref([]);
        const maxTraces = 50;
        
        // ====================================================================
        // COMPUTED PROPERTIES
        // ====================================================================
        
        const isAdmin = Vue.computed(() => window.store?.isAdmin || false);
        const userName = Vue.computed(() => window.store?.userName || 'User');
        
        // ====================================================================
        // METÓDUSOK - TRACE KEZELÉS
        // ====================================================================
        
        const addTrace = (data) => {
            const trace = {
                id: Date.now() + Math.random(),
                time: Date.now(),
                text: data.text || data.message || JSON.stringify(data),
                type: data.type || 'info',
                module: data.module,
                trace_id: data.trace_id
            };
            
            recentTraces.value.unshift(trace);
            
            // Limitálás
            if (recentTraces.value.length > maxTraces) {
                recentTraces.value = recentTraces.value.slice(0, maxTraces);
            }
        };
        
        const clearTraces = () => {
            recentTraces.value = [];
        };
        
        const getTraceIcon = (type) => {
            const icons = {
                'error': '❌',
                'warning': '⚠️',
                'success': '✅',
                'info': 'ℹ️',
                'debug': '🔧',
                'system': '⚙️',
                'user': '👤',
                'king': '👑',
                'queen': '👸',
                'jester': '🎭',
                'valet': '👔'
            };
            return icons[type] || '📌';
        };
        
        // ====================================================================
        // METÓDUSOK - AUTH
        // ====================================================================
        
        const showLogin = () => {
            const password = prompt(gettext('admin.enter_password'));
            if (password && window.socketManager) {
                window.socketManager.adminLogin(password);
            }
        };
        
        const logout = () => {
            if (window.socketManager) {
                window.socketManager.adminLogout();
            }
        };
        
        // ====================================================================
        // METÓDUSOK - EGYÉB
        // ====================================================================
        
        const formatTime = (timestamp) => {
            if (!timestamp) return '';
            
            const date = new Date(timestamp);
            const now = new Date();
            const diffMs = now - date;
            const diffMins = Math.floor(diffMs / 60000);
            
            if (diffMins < 1) return gettext('time.just_now');
            if (diffMins < 60) return `${diffMins} ${gettext('time.min_ago')}`;
            
            return date.toLocaleTimeString(window.store?.userLanguage || 'en');
        };
        
        const gettext = (key, params = {}) => {
            return window.gettext ? window.gettext(key, params) : key;
        };
        
        // ====================================================================
        // SOCKET ESEMÉNYEK
        // ====================================================================
        
        const setupSocketListeners = () => {
            if (!window.socketManager?.socket) return;
            
            // Trace események
            window.socketManager.socket.on('trace_event', addTrace);
            
            // Modul vezérlés eredmények
            window.socketManager.socket.on('module_control_result', (data) => {
                addTrace({
                    text: data.message,
                    type: data.success ? 'success' : 'error'
                });
            });
            
            // Admin login eredmény
            window.socketManager.socket.on('admin_login_result', (data) => {
                addTrace({
                    text: data.message || (data.success ? 'Login successful' : 'Login failed'),
                    type: data.success ? 'success' : 'error'
                });
            });
            
            // Rendszer események
            window.socketManager.socket.on('system_notification', (data) => {
                addTrace({
                    text: data.message,
                    type: data.type || 'info',
                    module: 'system'
                });
            });
            
            // Error események
            window.socketManager.socket.on('error', (data) => {
                addTrace({
                    text: data.message || 'Unknown error',
                    type: 'error'
                });
            });
        };
        
        // ====================================================================
        // ÉLETCIKLUS
        // ====================================================================
        
        Vue.onMounted(() => {
            setupSocketListeners();
            
            // Betöltünk néhány kezdeti trace-t a blackbox-ból
            if (window.api) {
                window.api.searchBlackbox('', 10).then(data => {
                    if (data.results) {
                        data.results.forEach(event => {
                            addTrace({
                                text: event.data || event.message,
                                type: event.type,
                                time: event.timestamp * 1000
                            });
                        });
                    }
                }).catch(() => {});
            }
        });
        
        Vue.onUnmounted(() => {
            if (window.socketManager?.socket) {
                window.socketManager.socket.off('trace_event', addTrace);
            }
        });
        
        return {
            // Állapotok
            activeTab,
            recentTraces,
            
            // Computed
            isAdmin,
            userName,
            
            // Metódusok
            showLogin,
            logout,
            formatTime,
            getTraceIcon,
            clearTraces,
            gettext
        };
    },
    
    components: {
        ModuleControl: window.ModuleControl,
        ModelSelector: window.ModelSelector,
        PromptEditor: window.PromptEditor,
        SettingsPanel: window.SettingsPanel,
        PersonalityManager: window.PersonalityManager,
        AuditLog: window.AuditLog,
        SystemMetrics: window.SystemMetrics
    }
};

window.AdminPanel = AdminPanel;
console.log('✅ AdminPanel betöltve globálisan');