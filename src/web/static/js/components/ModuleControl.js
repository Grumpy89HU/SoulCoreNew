// Modulvezérlő komponens
window.ModuleControl = {
    template: `
        <div class="module-control">
            <!-- Fejléc keresővel és szűrőkkel -->
            <div class="module-header">
                <div class="header-title">
                    <h3>{{ gettext('modules.title') }}</h3>
                    <span class="module-count" v-if="filteredModules.length">({{ filteredModules.length }})</span>
                </div>
                
                <div class="header-actions">
                    <input 
                        type="text" 
                        v-model="searchQuery" 
                        :placeholder="gettext('modules.search')"
                        class="search-input"
                    >
                    
                    <select v-model="filterStatus" class="filter-select">
                        <option value="all">{{ gettext('modules.all') }}</option>
                        <option value="running">{{ gettext('modules.running') }}</option>
                        <option value="stopped">{{ gettext('modules.stopped') }}</option>
                        <option value="error">{{ gettext('modules.error') }}</option>
                    </select>
                    
                    <button class="refresh-btn" @click="refreshModules" :disabled="refreshing">
                        <span :class="{ 'spin': refreshing }">🔄</span>
                    </button>
                </div>
            </div>
            
            <!-- Modul lista -->
            <div class="module-list">
                <div v-for="(status, name) in filteredModules" :key="name" 
                     class="module-card" 
                     :class="getModuleClass(status)">
                    
                    <!-- Modul fejléc -->
                    <div class="module-card-header">
                        <div class="module-title">
                            <span class="status-dot" :class="getStatusClass(status)"></span>
                            <span class="module-name">{{ formatModuleName(name) }}</span>
                            <span class="module-badge" v-if="getModuleType(name)">{{ getModuleType(name) }}</span>
                        </div>
                        
                        <div class="module-uptime" v-if="getModuleUptime(name)">
                            🕒 {{ formatUptime(getModuleUptime(name)) }}
                        </div>
                    </div>
                    
                    <!-- Modul információk -->
                    <div class="module-info">
                        <div class="info-row">
                            <span class="info-label">{{ gettext('modules.status') }}:</span>
                            <span class="info-value" :class="getStatusClass(status)">
                                {{ formatStatus(status) }}
                            </span>
                        </div>
                        
                        <div class="info-row" v-if="getModuleDetails(name)">
                            <span class="info-label">{{ gettext('modules.details') }}:</span>
                            <span class="info-value">{{ getModuleDetails(name) }}</span>
                        </div>
                        
                        <div class="info-row" v-if="getModuleMetrics(name)">
                            <span class="info-label">{{ gettext('modules.metrics') }}:</span>
                            <span class="info-value">{{ getModuleMetrics(name) }}</span>
                        </div>
                    </div>
                    
                    <!-- Vezérlő gombok -->
                    <div class="module-actions" v-if="isAdmin">
                        <div class="action-group">
                            <!-- Indítás (ha stopped) -->
                            <button class="action-btn start" 
                                    @click="controlModule(name, 'start')" 
                                    v-if="status == 'stopped'"
                                    :disabled="loading[name]"
                                    :title="gettext('modules.start')">
                                <span v-if="!loading[name]">▶️ {{ gettext('modules.start') }}</span>
                                <span v-else class="spinner-small"></span>
                            </button>
                            
                            <!-- Leállítás (ha running) -->
                            <button class="action-btn stop" 
                                    @click="controlModule(name, 'stop')" 
                                    v-if="status != 'stopped' && status != 'error'"
                                    :disabled="loading[name]"
                                    :title="gettext('modules.stop')">
                                <span v-if="!loading[name]">⏹️ {{ gettext('modules.stop') }}</span>
                                <span v-else class="spinner-small"></span>
                            </button>
                            
                            <!-- Újraindítás (ha running) -->
                            <button class="action-btn restart" 
                                    @click="controlModule(name, 'restart')" 
                                    v-if="status != 'stopped'"
                                    :disabled="loading[name]"
                                    :title="gettext('modules.restart')">
                                <span v-if="!loading[name]">↻ {{ gettext('modules.restart') }}</span>
                                <span v-else class="spinner-small"></span>
                            </button>
                            
                            <!-- Újratöltés (ha error) -->
                            <button class="action-btn reload" 
                                    @click="controlModule(name, 'reload')" 
                                    v-if="status == 'error'"
                                    :disabled="loading[name]"
                                    :title="gettext('modules.reload')">
                                <span v-if="!loading[name]">🔄 {{ gettext('modules.reload') }}</span>
                                <span v-else class="spinner-small"></span>
                            </button>
                        </div>
                        
                        <!-- További akciók -->
                        <div class="action-group extra">
                            <button class="icon-btn" @click="showModuleLogs(name)" 
                                    :title="gettext('modules.logs')" v-if="status != 'stopped'">
                                📋
                            </button>
                            <button class="icon-btn" @click="showModuleConfig(name)" 
                                    :title="gettext('modules.config')" v-if="isAdmin">
                                ⚙️
                            </button>
                        </div>
                    </div>
                    
                    <!-- Modul státusz (adminoknak) -->
                    <div class="module-footer" v-if="isAdmin">
                        <div class="footer-stats">
                            <span class="stat" v-if="getModuleMemory(name)">
                                💾 {{ formatBytes(getModuleMemory(name)) }}
                            </span>
                            <span class="stat" v-if="getModuleCpu(name)">
                                ⚡ {{ getModuleCpu(name) }}%
                            </span>
                            <span class="stat" v-if="getModuleThreads(name)">
                                🧵 {{ getModuleThreads(name) }}
                            </span>
                        </div>
                    </div>
                </div>
                
                <!-- Nincs találat -->
                <div v-if="Object.keys(filteredModules).length === 0" class="empty-list">
                    <div class="empty-icon">🔍</div>
                    <div class="empty-text">{{ gettext('modules.no_modules') }}</div>
                </div>
            </div>
            
            <!-- Modul naplók modal -->
            <div class="modal" v-if="showLogsModal">
                <div class="modal-content large">
                    <div class="modal-header">
                        <h3>{{ gettext('modules.logs') }} - {{ selectedModule }}</h3>
                        <button class="close-btn" @click="showLogsModal = false">✕</button>
                    </div>
                    
                    <div class="modal-body">
                        <div class="log-controls">
                            <select v-model="logLevel" class="filter-select">
                                <option value="all">{{ gettext('logs.all') }}</option>
                                <option value="error">{{ gettext('logs.error') }}</option>
                                <option value="warning">{{ gettext('logs.warning') }}</option>
                                <option value="info">{{ gettext('logs.info') }}</option>
                                <option value="debug">{{ gettext('logs.debug') }}</option>
                            </select>
                            
                            <button class="refresh-btn" @click="refreshLogs" :disabled="refreshingLogs">
                                <span :class="{ 'spin': refreshingLogs }">🔄</span>
                            </button>
                        </div>
                        
                        <div class="log-list">
                            <div v-for="log in filteredLogs" :key="log.id" 
                                 class="log-item" :class="'log-' + log.level">
                                <span class="log-time">{{ formatTime(log.timestamp) }}</span>
                                <span class="log-level">{{ log.level }}</span>
                                <span class="log-message">{{ log.message }}</span>
                            </div>
                            
                            <div v-if="filteredLogs.length === 0" class="empty-list">
                                {{ gettext('logs.no_logs') }}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Modul konfiguráció modal -->
            <div class="modal" v-if="showConfigModal">
                <div class="modal-content">
                    <div class="modal-header">
                        <h3>{{ gettext('modules.config') }} - {{ selectedModule }}</h3>
                        <button class="close-btn" @click="showConfigModal = false">✕</button>
                    </div>
                    
                    <div class="modal-body">
                        <div v-if="moduleConfig" class="config-editor">
                            <div v-for="(value, key) in moduleConfig" :key="key" class="config-row">
                                <span class="config-key">{{ key }}:</span>
                                <input 
                                    type="text" 
                                    v-model="moduleConfig[key]" 
                                    class="config-input"
                                    @change="updateConfig(key, value)"
                                >
                            </div>
                        </div>
                    </div>
                    
                    <div class="modal-footer">
                        <button class="btn-primary" @click="saveConfig">
                            {{ gettext('ui.save') }}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `,
    
    setup() {
        // ====================================================================
        // REAKTÍV ÁLLAPOTOK
        // ====================================================================
        
        const moduleStatuses = Vue.computed(() => window.store?.state?.moduleStatuses || {});
        const isAdmin = Vue.computed(() => window.store?.state?.isAdmin || false);
        
        // UI állapotok
        const searchQuery = Vue.ref('');
        const filterStatus = Vue.ref('all');
        const refreshing = Vue.ref(false);
        
        // Modul akciók állapota
        const loading = Vue.ref({});
        
        // Naplók
        const showLogsModal = Vue.ref(false);
        const selectedModule = Vue.ref(null);
        const moduleLogs = Vue.ref([]);
        const logLevel = Vue.ref('all');
        const refreshingLogs = Vue.ref(false);
        
        // Konfiguráció
        const showConfigModal = Vue.ref(false);
        const moduleConfig = Vue.ref(null);
        
        // ====================================================================
        // COMPUTED PROPERTIES
        // ====================================================================
        
        // Szűrt modulok
        const filteredModules = Vue.computed(() => {
            let modules = { ...moduleStatuses.value };
            
            // Keresés
            if (searchQuery.value) {
                const query = searchQuery.value.toLowerCase();
                modules = Object.fromEntries(
                    Object.entries(modules).filter(([name]) => 
                        name.toLowerCase().includes(query)
                    )
                );
            }
            
            // Szűrés státusz szerint
            if (filterStatus.value !== 'all') {
                modules = Object.fromEntries(
                    Object.entries(modules).filter(([_, status]) => 
                        getStatusCategory(status) === filterStatus.value
                    )
                );
            }
            
            return modules;
        });
        
        // Szűrt naplók
        const filteredLogs = Vue.computed(() => {
            if (logLevel.value === 'all') return moduleLogs.value;
            return moduleLogs.value.filter(log => log.level === logLevel.value);
        });
        
        // ====================================================================
        // METÓDUSOK
        // ====================================================================
        
        const statusClass = (status) => {
            return {
                'status-running': status == 'running' || status == 'ready' || status == 'watching',
                'status-warning': status == 'idle' || status == 'processing',
                'status-error': status == 'error' || status == 'stopped'
            };
        };
        
        const getStatusCategory = (status) => {
            if (status == 'running' || status == 'ready' || status == 'watching') return 'running';
            if (status == 'error') return 'error';
            if (status == 'stopped') return 'stopped';
            return 'other';
        };
        
        const getModuleClass = (status) => {
            return {
                'module-running': status == 'running' || status == 'ready' || status == 'watching',
                'module-warning': status == 'idle' || status == 'processing',
                'module-error': status == 'error' || status == 'stopped'
            };
        };
        
        const formatModuleName = (name) => {
            return name
                .split('_')
                .map(word => word.charAt(0).toUpperCase() + word.slice(1))
                .join(' ');
        };
        
        const getModuleType = (name) => {
            if (name.includes('core')) return '⚙️';
            if (name.includes('agent')) return '🤖';
            if (name.includes('gateway')) return '🌐';
            if (name.includes('vision')) return '👁️';
            if (name.includes('hardware')) return '🔧';
            if (name.includes('debug')) return '📼';
            if (name.includes('tools')) return '🔨';
            if (name.includes('memory')) return '💾';
            if (name.includes('web')) return '🌍';
            return '';
        };
        
        const getModuleUptime = (name) => {
            // Itt lehetne lekérni a modul uptime-ot a store-ból
            return null;
        };
        
        const getModuleDetails = (name) => {
            // Itt lehetne lekérni részletes infókat
            return null;
        };
        
        const getModuleMetrics = (name) => {
            // Itt lehetne lekérni metrikákat
            return null;
        };
        
        const getModuleMemory = (name) => {
            // Itt lehetne lekérni memória használatot
            return null;
        };
        
        const getModuleCpu = (name) => {
            // Itt lehetne lekérni CPU használatot
            return null;
        };
        
        const getModuleThreads = (name) => {
            // Itt lehetne lekérni szálak számát
            return null;
        };
        
        const formatStatus = (status) => {
            const translations = {
                'running': gettext('modules.status_running'),
                'ready': gettext('modules.status_ready'),
                'watching': gettext('modules.status_watching'),
                'idle': gettext('modules.status_idle'),
                'processing': gettext('modules.status_processing'),
                'error': gettext('modules.status_error'),
                'stopped': gettext('modules.status_stopped')
            };
            return translations[status] || status;
        };
        
        const formatUptime = (seconds) => {
            if (!seconds) return '';
            
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            
            if (hours > 0) {
                return `${hours}h ${minutes}m`;
            } else if (minutes > 0) {
                return `${minutes}m`;
            } else {
                return '< 1m';
            }
        };
        
        const formatBytes = (bytes) => {
            if (!bytes) return '';
            
            const units = ['B', 'KB', 'MB', 'GB'];
            let size = bytes;
            let unitIndex = 0;
            
            while (size >= 1024 && unitIndex < units.length - 1) {
                size /= 1024;
                unitIndex++;
            }
            
            return `${size.toFixed(1)} ${units[unitIndex]}`;
        };
        
        const formatTime = (timestamp) => {
            if (!timestamp) return '';
            const date = new Date(timestamp);
            return date.toLocaleTimeString();
        };
        
        const gettext = (key, params = {}) => {
            return window.gettext ? window.gettext(key, params) : key;
        };
        
        const controlModule = async (module, action) => {
            loading.value[module] = true;
            
            try {
                if (window.socketManager && window.socketManager.controlModule) {
                    await window.socketManager.controlModule(module, action);
                    
                    // Kis késleltetés a státusz frissüléshez
                    setTimeout(() => {
                        if (window.socketManager.getStatus) {
                            window.socketManager.getStatus();
                        }
                    }, 500);
                }
            } catch (error) {
                console.error(`Error controlling module ${module}:`, error);
                alert(gettext('modules.control_error', { error: error.message }));
            } finally {
                loading.value[module] = false;
            }
        };
        
        const refreshModules = async () => {
            refreshing.value = true;
            
            try {
                if (window.socketManager && window.socketManager.getStatus) {
                    await window.socketManager.getStatus();
                }
            } finally {
                refreshing.value = false;
            }
        };
        
        const showModuleLogs = async (module) => {
            selectedModule.value = module;
            showLogsModal.value = true;
            await loadModuleLogs(module);
        };
        
        const loadModuleLogs = async (module) => {
            refreshingLogs.value = true;
            
            try {
                // Itt lehetne lekérni a modul naplóit a blackbox-ból
                if (window.api) {
                    const result = await window.api.searchBlackbox(`module:${module}`, 100);
                    moduleLogs.value = result.results || [];
                } else {
                    // Demo adatok
                    moduleLogs.value = generateDemoLogs(module);
                }
            } finally {
                refreshingLogs.value = false;
            }
        };
        
        const refreshLogs = () => {
            loadModuleLogs(selectedModule.value);
        };
        
        const showModuleConfig = async (module) => {
            selectedModule.value = module;
            showConfigModal.value = true;
            await loadModuleConfig(module);
        };
        
        const loadModuleConfig = async (module) => {
            try {
                // Itt lehetne lekérni a modul konfigurációját
                moduleConfig.value = {
                    enabled: true,
                    timeout: 30,
                    retries: 3
                };
            } catch (error) {
                console.error('Error loading config:', error);
            }
        };
        
        const updateConfig = (key, value) => {
            // Itt lehetne frissíteni a konfigurációt
        };
        
        const saveConfig = () => {
            // Itt lehetne menteni a konfigurációt
            showConfigModal.value = false;
        };
        
        // Demo naplók generálása
        const generateDemoLogs = (module) => {
            const levels = ['info', 'debug', 'warning', 'error'];
            const messages = [
                'Module started',
                'Processing request',
                'Connection established',
                'Memory usage: 256MB',
                'Warning: High CPU usage',
                'Error: Timeout',
                'Debug: Cache hit',
                'Info: 10 requests processed'
            ];
            
            return Array.from({ length: 20 }, (_, i) => ({
                id: i,
                timestamp: Date.now() - i * 60000,
                level: levels[Math.floor(Math.random() * levels.length)],
                message: messages[Math.floor(Math.random() * messages.length)]
            }));
        };
        
        return {
            // Állapotok
            moduleStatuses,
            isAdmin,
            searchQuery,
            filterStatus,
            refreshing,
            loading,
            
            // Naplók
            showLogsModal,
            selectedModule,
            moduleLogs,
            logLevel,
            refreshingLogs,
            filteredLogs,
            
            // Konfiguráció
            showConfigModal,
            moduleConfig,
            
            // Computed
            filteredModules,
            
            // Metódusok
            statusClass,
            getModuleClass,
            formatModuleName,
            getModuleType,
            getModuleUptime,
            getModuleDetails,
            getModuleMetrics,
            getModuleMemory,
            getModuleCpu,
            getModuleThreads,
            formatStatus,
            formatUptime,
            formatBytes,
            formatTime,
            gettext,
            controlModule,
            refreshModules,
            showModuleLogs,
            refreshLogs,
            showModuleConfig,
            saveConfig
        };
    }
};

window.ModuleControl = ModuleControl;
console.log('✅ ModuleControl betöltve globálisan');