// ==============================================
// SOULCORE 3.0 - Admin panel komponens (TELJES)
// ==============================================

window.AdminPanel = {
    name: 'AdminPanel',
    
    template: `
        <div class="admin-panel">
            <div class="admin-header">
                <div class="admin-title">
                    <span class="admin-icon">⚙️</span>
                    <span>{{ t('admin.title') }}</span>
                </div>
                <div class="admin-status">
                    <span class="status-dot online"></span>
                    <span>{{ t('admin.online') }}</span>
                </div>
            </div>
            
            <!-- Admin kategória fülek -->
            <div class="admin-tabs">
                <button v-for="tab in tabList" :key="tab.id" 
                        class="admin-tab" :class="{ active: activeTab === tab.id }"
                        @click="activeTab = tab.id">
                    <span class="tab-icon">{{ tab.icon }}</span>
                    <span>{{ tab.name }}</span>
                </button>
            </div>
            
            <!-- Tartalom -->
            <div class="admin-content">
                <div v-show="activeTab === 'modules'" class="tab-content">
                    <module-control></module-control>
                </div>
                <div v-show="activeTab === 'models'" class="tab-content">
                    <model-selector></model-selector>
                </div>
                <div v-show="activeTab === 'prompts'" class="tab-content">
                    <prompt-editor></prompt-editor>
                </div>
                <div v-show="activeTab === 'personalities'" class="tab-content">
                    <personality-manager></personality-manager>
                </div>
                <div v-show="activeTab === 'embedding'" class="tab-content">
                    <embedding-panel></embedding-panel>
                </div>
                <div v-show="activeTab === 'audio'" class="tab-content">
                    <audio-panel></audio-panel>
                </div>
                <div v-show="activeTab === 'vision'" class="tab-content">
                    <vision-upload></vision-upload>
                </div>
                <div v-show="activeTab === 'sandbox'" class="tab-content">
                    <sandbox-editor></sandbox-editor>
                </div>
                <div v-show="activeTab === 'gateway'" class="tab-content">
                    <gateway-panel></gateway-panel>
                </div>
                <div v-show="activeTab === 'audit'" class="tab-content">
                    <audit-log></audit-log>
                </div>
                <div v-show="activeTab === 'metrics'" class="tab-content">
                    <metrics-panel></metrics-panel>
                </div>
                <div v-show="activeTab === 'traces'" class="tab-content">
                    <trace-panel></trace-panel>
                </div>
                <div v-show="activeTab === 'settings'" class="tab-content">
                    <settings-panel></settings-panel>
                </div>
                <div v-show="activeTab === 'info'" class="tab-content">
                    <div class="system-info">
                        <div class="info-card">
                            <h4>{{ t('admin.system_info') }}</h4>
                            <div class="info-row"><span class="info-label">{{ t('admin.version') }}:</span><span>SoulCore 3.0</span></div>
                            <div class="info-row"><span class="info-label">{{ t('admin.system_id') }}:</span><code>{{ systemId }}</code></div>
                            <div class="info-row"><span class="info-label">{{ t('admin.uptime') }}:</span><span>{{ formatUptime(heartbeat?.uptime_seconds || 0) }}</span></div>
                        </div>
                        <div class="info-card">
                            <h4>{{ t('admin.modules_status') }}</h4>
                            <div class="modules-status-grid">
                                <div v-for="(status, name) in modules" :key="name" class="module-status-item">
                                    <span class="module-name">{{ formatModuleName(name) }}</span>
                                    <span class="module-status" :class="status">{{ formatStatus(status) }}</span>
                                </div>
                            </div>
                        </div>
                        <div class="info-card">
                            <h4>{{ t('admin.resources') }}</h4>
                            <div class="resource-item">
                                <span class="resource-label">CPU:</span>
                                <div class="resource-bar">
                                    <div class="resource-fill" :style="{ width: cpuUsage + '%' }"></div>
                                </div>
                                <span class="resource-value">{{ cpuUsage }}%</span>
                            </div>
                            <div class="resource-item">
                                <span class="resource-label">RAM:</span>
                                <div class="resource-bar">
                                    <div class="resource-fill" :style="{ width: ramUsage + '%' }"></div>
                                </div>
                                <span class="resource-value">{{ ramUsage }}%</span>
                            </div>
                            <div v-for="(gpu, idx) in gpuStatus" :key="idx" class="resource-item">
                                <span class="resource-label">GPU{{ idx }}:</span>
                                <div class="resource-bar">
                                    <div class="resource-fill" :style="{ width: (gpu.utilization || 0) + '%' }"></div>
                                </div>
                                <span class="resource-value">{{ gpu.utilization || 0 }}%</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="admin-footer">
                <div class="admin-info">
                    <span class="admin-badge">{{ t('admin.admin_access') }}</span>
                    <button class="logout-btn" @click="logout">🚪 {{ t('ui.logout') }}</button>
                </div>
            </div>
        </div>
    `,
    
    setup() {
        const systemId = Vue.computed(() => window.store.systemId);
        const heartbeat = Vue.computed(() => window.store.heartbeat);
        const modules = Vue.computed(() => window.store.modules || {});
        const gpuStatus = Vue.computed(() => window.store.gpuStatus || []);
        
        const activeTab = Vue.ref('modules');
        const clientCount = Vue.ref(0);
        const cpuUsage = Vue.ref(Math.floor(Math.random() * 40) + 20);
        const ramUsage = Vue.ref(Math.floor(Math.random() * 50) + 30);
        
        const t = (key, params = {}) => window.gettext(key, params);
        const formatUptime = (s) => window.formatUptime(s);
        const formatModuleName = (n) => {
            if (!n) return '';
            return String(n).split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
        };
        const formatStatus = (s) => window.formatStatus(s);
        
        // TABS - fix szövegek, nem t()!
        const tabList = [
            { id: 'modules', name: 'Modulok', icon: '🔧' },
            { id: 'models', name: 'Modellek', icon: '🤖' },
            { id: 'prompts', name: 'Promptok', icon: '📝' },
            { id: 'personalities', name: 'Személyiségek', icon: '🎭' },
            { id: 'embedding', name: 'Embedding', icon: '📊' },
            { id: 'audio', name: 'Hang (ASR/TTS)', icon: '🎤' },
            { id: 'vision', name: 'Képfeldolgozás', icon: '👁️' },
            { id: 'sandbox', name: 'Kódfuttató', icon: '🏖️' },
            { id: 'gateway', name: 'Gateway', icon: '🌐' },
            { id: 'audit', name: 'Audit napló', icon: '📋' },
            { id: 'metrics', name: 'Metrikák', icon: '📊' },
            { id: 'traces', name: 'Trace naplók', icon: '🔍' },
            { id: 'settings', name: 'Beállítások', icon: '⚙️' },
            { id: 'info', name: 'Rendszerinfo', icon: 'ℹ️' }
        ];
        
        const refreshSystemData = async () => {
            try {
                const status = await window.api.getStatus();
                clientCount.value = status.clients || 0;
            } catch (error) {
                console.error('Error refreshing system data:', error);
            }
        };
        
        const updateResources = () => {
            cpuUsage.value = Math.floor(Math.random() * 40) + 20;
            ramUsage.value = Math.floor(Math.random() * 50) + 30;
        };
        
        const logout = async () => {
            if (confirm(t('auth.confirm_logout'))) {
                await window.api.logout();
            }
        };
        
        let resourceInterval = null;
        
        Vue.onMounted(() => {
            refreshSystemData();
            resourceInterval = setInterval(updateResources, 5000);
        });
        
        Vue.onUnmounted(() => {
            if (resourceInterval) clearInterval(resourceInterval);
        });
        
        return {
            systemId,
            heartbeat,
            modules,
            gpuStatus,
            clientCount,
            cpuUsage,
            ramUsage,
            activeTab,
            tabList,
            t,
            formatUptime,
            formatModuleName,
            formatStatus,
            logout
        };
    }
};

console.log('✅ AdminPanel komponens betöltve (14 fül)');