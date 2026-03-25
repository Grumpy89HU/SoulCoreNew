// ==============================================
// SOULCORE 3.0 - Modul vezérlő komponens
// ==============================================

window.ModuleControl = {
    name: 'ModuleControl',
    
    template: `
        <div class="module-control">
            <!-- Fejléc keresővel és szűrőkkel -->
            <div class="module-header">
                <div class="header-title">
                    <h3>{{ t('modules.title') }}</h3>
                    <span class="module-count" v-if="filteredModules.length">({{ filteredModules.length }})</span>
                </div>
                <div class="header-actions">
                    <input 
                        type="text" 
                        v-model="searchQuery" 
                        :placeholder="t('modules.search')"
                        class="search-input"
                    >
                    <select v-model="filterStatus" class="filter-select">
                        <option value="all">{{ t('modules.all') }}</option>
                        <option value="running">{{ t('modules.running') }}</option>
                        <option value="stopped">{{ t('modules.stopped') }}</option>
                        <option value="error">{{ t('modules.error') }}</option>
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
                            <span class="info-label">{{ t('modules.status') }}:</span>
                            <span class="info-value" :class="getStatusClass(status)">
                                {{ formatStatus(status) }}
                            </span>
                        </div>
                        <div class="info-row" v-if="getModuleDetails(name)">
                            <span class="info-label">{{ t('modules.details') }}:</span>
                            <span class="info-value">{{ getModuleDetails(name) }}</span>
                        </div>
                        <div class="info-row" v-if="getModuleMetrics(name)">
                            <span class="info-label">{{ t('modules.metrics') }}:</span>
                            <span class="info-value">{{ getModuleMetrics(name) }}</span>
                        </div>
                    </div>
                    
                    <!-- Vezérlő gombok -->
                    <div class="module-actions" v-if="isAdmin">
                        <div class="action-group">
                            <!-- Indítás (ha stopped) -->
                            <button class="action-btn start" 
                                    @click="controlModule(name, 'start')" 
                                    v-if="status === 'stopped'"
                                    :disabled="loading[name]"
                                    :title="t('modules.start')">
                                <span v-if="!loading[name]">▶️ {{ t('modules.start') }}</span>
                                <span v-else class="spinner-small"></span>
                            </button>
                            
                            <!-- Leállítás (ha running) -->
                            <button class="action-btn stop" 
                                    @click="controlModule(name, 'stop')" 
                                    v-if="status !== 'stopped' && status !== 'error'"
                                    :disabled="loading[name]"
                                    :title="t('modules.stop')">
                                <span v-if="!loading[name]">⏹️ {{ t('modules.stop') }}</span>
                                <span v-else class="spinner-small"></span>
                            </button>
                            
                            <!-- Újraindítás (ha running) -->
                            <button class="action-btn restart" 
                                    @click="controlModule(name, 'restart')" 
                                    v-if="status !== 'stopped'"
                                    :disabled="loading[name]"
                                    :title="t('modules.restart')">
                                <span v-if="!loading[name]">↻ {{ t('modules.restart') }}</span>
                                <span v-else class="spinner-small"></span>
                            </button>
                            
                            <!-- Újratöltés (ha error) -->
                            <button class="action-btn reload" 
                                    @click="controlModule(name, 'reload')" 
                                    v-if="status === 'error'"
                                    :disabled="loading[name]"
                                    :title="t('modules.reload')">
                                <span v-if="!loading[name]">🔄 {{ t('modules.reload') }}</span>
                                <span v-else class="spinner-small"></span>
                            </button>
                        </div>
                        
                        <!-- További akciók -->
                        <div class="action-group extra">
                            <button class="icon-btn" @click="showModuleLogs(name)" 
                                    :title="t('modules.logs')" v-if="status !== 'stopped'">
                                📋
                            </button>
                            <button class="icon-btn" @click="showModuleConfig(name)" 
                                    :title="t('modules.config')" v-if="isAdmin">
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
                    <div class="empty-text">{{ t('modules.no_modules') }}</div>
                </div>
            </div>
            
            <!-- Modul naplók modal -->
            <div class="modal" v-if="showLogsModal" @click.self="showLogsModal = false">
                <div class="modal-content large">
                    <div class="modal-header">
                        <h3>{{ t('modules.logs') }} - {{ selectedModule }}</h3>
                        <button class="close-btn" @click="showLogsModal = false">✕</button>
                    </div>
                    <div class="modal-body">
                        <div class="log-controls">
                            <select v-model="logLevel" class="filter-select">
                                <option value="all">{{ t('logs.all') }}</option>
                                <option value="error">{{ t('logs.error') }}</option>
                                <option value="warning">{{ t('logs.warning') }}</option>
                                <option value="info">{{ t('logs.info') }}</option>
                                <option value="debug">{{ t('logs.debug') }}</option>
                            </select>
                            <button class="refresh-btn" @click="refreshLogs" :disabled="refreshingLogs">
                                <span :class="{ 'spin': refreshingLogs }">🔄</span>
                            </button>
                            <button class="btn-secondary" @click="exportLogs">
                                📥 {{ t('logs.export') }}
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
                                {{ t('logs.no_logs') }}
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn-primary" @click="showLogsModal = false">
                            {{ t('ui.close') }}
                        </button>
                    </div>
                </div>
            </div>
            
            <!-- Modul konfiguráció modal -->
            <div class="modal" v-if="showConfigModal" @click.self="showConfigModal = false">
                <div class="modal-content">
                    <div class="modal-header">
                        <h3>{{ t('modules.config') }} - {{ selectedModule }}</h3>
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
                        <div v-else class="empty-list">
                            {{ t('modules.no_config') }}
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn-secondary" @click="showConfigModal = false">
                            {{ t('ui.cancel') }}
                        </button>
                        <button class="btn-primary" @click="saveConfig">
                            {{ t('ui.save') }}
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
        
        const modules = Vue.computed(() => window.store.modules);
        const isAdmin = Vue.computed(() => window.store.user?.role === 'admin');
        
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
            let mods = { ...modules.value };
            
            // Keresés
            if (searchQuery.value) {
                const query = searchQuery.value.toLowerCase();
                mods = Object.fromEntries(
                    Object.entries(mods).filter(([name]) => 
                        name.toLowerCase().includes(query)
                    )
                );
            }
            
            // Szűrés státusz szerint
            if (filterStatus.value !== 'all') {
                mods = Object.fromEntries(
                    Object.entries(mods).filter(([_, status]) => 
                        getStatusCategory(status) === filterStatus.value
                    )
                );
            }
            
            return mods;
        });
        
        // Szűrt naplók
        const filteredLogs = Vue.computed(() => {
            if (logLevel.value === 'all') return moduleLogs.value;
            return moduleLogs.value.filter(log => log.level === logLevel.value);
        });
        
        // ====================================================================
        // SEGÉDFÜGGVÉNYEK
        // ====================================================================
        
        const t = (key, params = {}) => window.gettext(key, params);
        const formatUptime = (s) => window.formatUptime(s);
        const formatBytes = (b) => window.formatBytes(b);
        const formatTime = (ts) => window.formatTime(ts);
        
        /**
         * Státusz kategória meghatározása (szűréshez)
         */
        const getStatusCategory = (status) => {
            const runningStates = ['running', 'ready', 'active', 'watching', 'processing'];
            const stoppedStates = ['stopped', 'idle', 'inactive'];
            const errorStates = ['error', 'frozen', 'crash'];
            
            if (runningStates.includes(status)) return 'running';
            if (stoppedStates.includes(status)) return 'stopped';
            if (errorStates.includes(status)) return 'error';
            return 'other';
        };
        
        /**
         * Modul osztály meghatározása (kártya stílushoz)
         */
        const getModuleClass = (status) => {
            if (status === 'running' || status === 'ready' || status === 'active') return 'module-running';
            if (status === 'error' || status === 'frozen') return 'module-error';
            if (status === 'stopped' || status === 'idle') return 'module-stopped';
            return '';
        };
        
        /**
         * Státusz osztály meghatározása (status dot-hoz)
         */
        const getStatusClass = (status) => {
            if (status === 'running' || status === 'ready' || status === 'active') return 'status-running';
            if (status === 'error' || status === 'frozen') return 'status-error';
            if (status === 'processing') return 'status-processing';
            if (status === 'stopped' || status === 'idle') return 'status-stopped';
            return 'status-unknown';
        };
        
        /**
         * Modul név formázása
         */
        const formatModuleName = (name) => window.formatModuleName(name);
        
        /**
         * Státusz szöveg formázása
         */
        const formatStatus = (status) => window.formatStatus(status);
        
        /**
         * Modul típus ikon
         */
        const getModuleType = (name) => {
            if (name.includes('core')) return '⚙️';
            if (name.includes('agent')) return '🤖';
            if (name.includes('gateway')) return '🌐';
            if (name.includes('vision') || name.includes('eye')) return '👁️';
            if (name.includes('hardware') || name.includes('sentinel')) return '🔧';
            if (name.includes('debug') || name.includes('blackbox')) return '📼';
            if (name.includes('tools') || name.includes('sandbox')) return '🔨';
            if (name.includes('memory') || name.includes('vault')) return '💾';
            if (name.includes('web')) return '🌍';
            if (name.includes('king')) return '👑';
            if (name.includes('queen')) return '👸';
            if (name.includes('jester')) return '🎭';
            if (name.includes('scribe')) return '📝';
            if (name.includes('valet')) return '🧹';
            return '';
        };
        
        /**
         * Modul uptime lekérése (mock)
         */
        const getModuleUptime = (name) => {
            // Itt lehetne lekérni a valós uptime-ot
            return null;
        };
        
        /**
         * Modul részletes információk (mock)
         */
        const getModuleDetails = (name) => {
            // Itt lehetne lekérni részletes infókat
            return null;
        };
        
        /**
         * Modul metrikák (mock)
         */
        const getModuleMetrics = (name) => {
            // Itt lehetne lekérni metrikákat
            return null;
        };
        
        /**
         * Modul memória használat (mock)
         */
        const getModuleMemory = (name) => {
            // Itt lehetne lekérni memória használatot
            return null;
        };
        
        /**
         * Modul CPU használat (mock)
         */
        const getModuleCpu = (name) => {
            // Itt lehetne lekérni CPU használatot
            return null;
        };
        
        /**
         * Modul szálak száma (mock)
         */
        const getModuleThreads = (name) => {
            // Itt lehetne lekérni szálak számát
            return null;
        };
        
        // ====================================================================
        // MODUL VEZÉRLÉS
        // ====================================================================
        
        /**
         * Modul vezérlése (start/stop/restart/reload)
         */
        const controlModule = async (module, action) => {
            loading.value[module] = true;
            
            try {
                await window.api.controlModule(module, action);
                window.store.addNotification('success', t('modules.action_success', { module, action }));
                
                // Státusz frissítése
                setTimeout(() => {
                    window.api.getStatus();
                }, 500);
            } catch (error) {
                console.error(`Error controlling module ${module}:`, error);
                window.store.addNotification('error', t('modules.action_error', { error: error.message }));
            } finally {
                loading.value[module] = false;
            }
        };
        
        /**
         * Modulok frissítése
         */
        const refreshModules = async () => {
            refreshing.value = true;
            try {
                await window.api.getStatus();
                window.store.addNotification('success', t('modules.refreshed'));
            } catch (error) {
                console.error('Error refreshing modules:', error);
                window.store.addNotification('error', t('modules.refresh_error'));
            } finally {
                refreshing.value = false;
            }
        };
        
        // ====================================================================
        // MODUL NAPLÓK
        // ====================================================================
        
        /**
         * Modul naplók megjelenítése
         */
        const showModuleLogs = async (module) => {
            selectedModule.value = module;
            showLogsModal.value = true;
            await loadModuleLogs(module);
        };
        
        /**
         * Modul naplók betöltése
         */
        const loadModuleLogs = async (module) => {
            refreshingLogs.value = true;
            try {
                const result = await window.api.searchBlackbox(`module:${module}`, 200);
                moduleLogs.value = result.results || generateDemoLogs(module);
            } catch (error) {
                console.error('Error loading module logs:', error);
                moduleLogs.value = generateDemoLogs(module);
            } finally {
                refreshingLogs.value = false;
            }
        };
        
        /**
         * Naplók frissítése
         */
        const refreshLogs = () => {
            loadModuleLogs(selectedModule.value);
        };
        
        /**
         * Naplók exportálása
         */
        const exportLogs = () => {
            const data = {
                module: selectedModule.value,
                exported: new Date().toISOString(),
                logs: filteredLogs.value
            };
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${selectedModule.value}_logs_${Date.now()}.json`;
            a.click();
            URL.revokeObjectURL(url);
            window.store.addNotification('success', t('logs.exported'));
        };
        
        /**
         * Demo naplók generálása
         */
        const generateDemoLogs = (module) => {
            const levels = ['info', 'debug', 'warning', 'error'];
            const messages = [
                `${module} module started`,
                `${module} processing request`,
                `${module} connection established`,
                `${module} memory usage: 256MB`,
                `${module} warning: high CPU usage`,
                `${module} error: timeout occurred`,
                `${module} debug: cache hit`,
                `${module} info: 10 requests processed`
            ];
            
            return Array.from({ length: 20 }, (_, i) => ({
                id: i,
                timestamp: Date.now() - i * 60000,
                level: levels[Math.floor(Math.random() * levels.length)],
                message: messages[Math.floor(Math.random() * messages.length)]
            }));
        };
        
        // ====================================================================
        // MODUL KONFIGURÁCIÓ
        // ====================================================================
        
        /**
         * Modul konfiguráció megjelenítése
         */
        const showModuleConfig = async (module) => {
            selectedModule.value = module;
            showConfigModal.value = true;
            await loadModuleConfig(module);
        };
        
        /**
         * Modul konfiguráció betöltése
         */
        const loadModuleConfig = async (module) => {
            try {
                // Itt lehetne lekérni a valós konfigurációt
                moduleConfig.value = getDefaultConfig(module);
            } catch (error) {
                console.error('Error loading config:', error);
                moduleConfig.value = null;
            }
        };
        
        /**
         * Alapértelmezett konfiguráció
         */
        const getDefaultConfig = (module) => {
            return {
                enabled: true,
                auto_start: false,
                log_level: 'info',
                timeout: 30,
                retries: 3,
                max_memory: 1024
            };
        };
        
        /**
         * Konfiguráció frissítése
         */
        const updateConfig = (key, value) => {
            // Itt lehetne frissíteni a konfigurációt (valós idejű)
        };
        
        /**
         * Konfiguráció mentése
         */
        const saveConfig = async () => {
            try {
                // Itt lehetne menteni a konfigurációt
                window.store.addNotification('success', t('modules.config_saved'));
                showConfigModal.value = false;
            } catch (error) {
                console.error('Error saving config:', error);
                window.store.addNotification('error', t('modules.config_save_error'));
            }
        };
        
        // ====================================================================
        // RETURN
        // ====================================================================
        
        return {
            // Állapotok
            modules,
            isAdmin,
            searchQuery,
            filterStatus,
            refreshing,
            loading,
            filteredModules,
            
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
            
            // Segédfüggvények
            t,
            formatUptime,
            formatBytes,
            formatTime,
            getModuleClass,
            getStatusClass,
            formatModuleName,
            formatStatus,
            getModuleType,
            getModuleUptime,
            getModuleDetails,
            getModuleMetrics,
            getModuleMemory,
            getModuleCpu,
            getModuleThreads,
            
            // Metódusok
            controlModule,
            refreshModules,
            showModuleLogs,
            refreshLogs,
            exportLogs,
            showModuleConfig,
            updateConfig,
            saveConfig
        };
    }
};

console.log('✅ ModuleControl komponens betöltve');