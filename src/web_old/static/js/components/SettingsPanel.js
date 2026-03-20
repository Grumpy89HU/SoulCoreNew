// Beállítások panel
window.SettingsPanel = {
    template: `
        <div class="settings-panel">
            <!-- Fejléc keresővel -->
            <div class="settings-header">
                <h3>{{ gettext('settings.title') }}</h3>
                <div class="header-actions">
                    <input 
                        type="text" 
                        v-model="searchQuery" 
                        :placeholder="gettext('settings.search')"
                        class="search-input"
                    >
                    <button class="refresh-btn" @click="loadSettings" :disabled="loading">
                        <span :class="{ 'spin': loading }">🔄</span>
                    </button>
                </div>
            </div>
            
            <!-- Fülek -->
            <div class="settings-tabs">
                <button class="tab-btn" :class="{ active: settingsTab == 'general' }" 
                        @click="settingsTab = 'general'">
                    🏠 {{ gettext('settings.general') }}
                </button>
                <button class="tab-btn" :class="{ active: settingsTab == 'model' }" 
                        @click="settingsTab = 'model'">
                    🤖 {{ gettext('settings.model') }}
                </button>
                <button class="tab-btn" :class="{ active: settingsTab == 'generation' }" 
                        @click="settingsTab = 'generation'">
                    ✨ {{ gettext('settings.generation') }}
                </button>
                <button class="tab-btn" :class="{ active: settingsTab == 'system' }" 
                        @click="settingsTab = 'system'">
                    ⚙️ {{ gettext('settings.system') }}
                </button>
                <button class="tab-btn" :class="{ active: settingsTab == 'memory' }" 
                        @click="settingsTab = 'memory'">
                    💾 {{ gettext('settings.memory') }}
                </button>
                <button class="tab-btn" :class="{ active: settingsTab == 'hardware' }" 
                        @click="settingsTab = 'hardware'">
                    🔧 {{ gettext('settings.hardware') }}
                </button>
                <button class="tab-btn" :class="{ active: settingsTab == 'network' }" 
                        @click="settingsTab = 'network'">
                    🌐 {{ gettext('settings.network') }}
                </button>
            </div>
            
            <!-- Keresési eredmények -->
            <div v-if="searchQuery && searchResults.length" class="search-results">
                <div class="search-header">
                    {{ gettext('settings.search_results') }} ({{ searchResults.length }})
                </div>
                <div class="search-list">
                    <div v-for="result in searchResults" :key="result.key" 
                         class="search-item" @click="jumpToSetting(result)">
                        <span class="search-category">{{ result.category }}</span>
                        <span class="search-name">{{ result.name }}</span>
                        <span class="search-value">{{ displayValue(result.value) }}</span>
                    </div>
                </div>
            </div>
            
            <!-- Beállítások tartalom -->
            <div class="settings-content" v-else>
                <!-- Általános beállítások -->
                <div v-show="settingsTab == 'general'" class="settings-section">
                    <h4>{{ gettext('settings.general') }}</h4>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">{{ gettext('settings.user_name') }}</div>
                            <div class="setting-desc">{{ gettext('settings.user_name_desc') }}</div>
                        </div>
                        <input type="text" v-model="settings.user_name" 
                               @change="updateSetting('user_name', $event.target.value)"
                               class="setting-input">
                    </div>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">{{ gettext('settings.language') }}</div>
                            <div class="setting-desc">{{ gettext('settings.language_desc') }}</div>
                        </div>
                        <select v-model="settings.language" @change="updateLanguage">
                            <option value="hu">Magyar</option>
                            <option value="en">English</option>
                            <option value="de">Deutsch</option>
                            <option value="fr">Français</option>
                            <option value="es">Español</option>
                        </select>
                    </div>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">{{ gettext('settings.timezone') }}</div>
                            <div class="setting-desc">{{ gettext('settings.timezone_desc') }}</div>
                        </div>
                        <select v-model="settings.timezone" @change="updateSetting('timezone', $event.target.value)">
                            <option value="local">{{ gettext('settings.timezone_local') }}</option>
                            <option value="UTC">UTC</option>
                            <option value="Europe/Budapest">Europe/Budapest</option>
                            <option value="Europe/London">Europe/London</option>
                            <option value="America/New_York">America/New_York</option>
                            <option value="Asia/Tokyo">Asia/Tokyo</option>
                        </select>
                    </div>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">{{ gettext('settings.theme') }}</div>
                            <div class="setting-desc">{{ gettext('settings.theme_desc') }}</div>
                        </div>
                        <select v-model="settings.theme" @change="updateTheme">
                            <option value="dark">🌙 {{ gettext('settings.theme_dark') }}</option>
                            <option value="light">☀️ {{ gettext('settings.theme_light') }}</option>
                            <option value="system">💻 {{ gettext('settings.theme_system') }}</option>
                        </select>
                    </div>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">{{ gettext('settings.date_format') }}</div>
                            <div class="setting-desc">{{ gettext('settings.date_format_desc') }}</div>
                        </div>
                        <select v-model="settings.date_format" @change="updateSetting('date_format', $event.target.value)">
                            <option value="locale">{{ gettext('settings.date_locale') }}</option>
                            <option value="YYYY-MM-DD">YYYY-MM-DD</option>
                            <option value="MM/DD/YYYY">MM/DD/YYYY</option>
                            <option value="DD/MM/YYYY">DD/MM/YYYY</option>
                        </select>
                    </div>
                </div>
                
                <!-- Modell beállítások -->
                <div v-show="settingsTab == 'model'" class="settings-section">
                    <h4>{{ gettext('settings.model') }}</h4>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">{{ gettext('settings.default_model') }}</div>
                            <div class="setting-desc">{{ gettext('settings.default_model_desc') }}</div>
                        </div>
                        <select v-model="settings.default_model" @change="updateSetting('default_model', $event.target.value)">
                            <option v-for="model in availableModels" :key="model.id" :value="model.id">
                                {{ model.name }}
                            </option>
                        </select>
                    </div>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">{{ gettext('settings.context_length') }}</div>
                            <div class="setting-desc">{{ gettext('settings.context_length_desc') }}</div>
                        </div>
                        <input type="number" v-model="settings.context_length" 
                               min="512" max="32768" step="512"
                               @change="updateSetting('context_length', settings.context_length, 'int')"
                               class="setting-input number">
                    </div>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">{{ gettext('settings.batch_size') }}</div>
                            <div class="setting-desc">{{ gettext('settings.batch_size_desc') }}</div>
                        </div>
                        <input type="number" v-model="settings.batch_size" 
                               min="1" max="512"
                               @change="updateSetting('batch_size', settings.batch_size, 'int')"
                               class="setting-input number">
                    </div>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">{{ gettext('settings.model_cache') }}</div>
                            <div class="setting-desc">{{ gettext('settings.model_cache_desc') }}</div>
                        </div>
                        <label class="switch">
                            <input type="checkbox" v-model="settings.model_cache" 
                                   @change="updateSetting('model_cache', settings.model_cache, 'bool')">
                            <span class="slider"></span>
                        </label>
                    </div>
                </div>
                
                <!-- Generálási beállítások -->
                <div v-show="settingsTab == 'generation'" class="settings-section">
                    <h4>{{ gettext('settings.generation') }}</h4>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">Temperature</div>
                            <div class="setting-desc">{{ gettext('settings.temperature_desc') }}</div>
                        </div>
                        <div class="setting-with-value">
                            <input type="range" v-model="modelParams.temperature" 
                                   min="0.1" max="2.0" step="0.1"
                                   @change="updateModelParam('temperature', modelParams.temperature)">
                            <span class="range-value">{{ modelParams.temperature }}</span>
                        </div>
                    </div>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">Top P</div>
                            <div class="setting-desc">{{ gettext('settings.top_p_desc') }}</div>
                        </div>
                        <div class="setting-with-value">
                            <input type="range" v-model="modelParams.top_p" 
                                   min="0.0" max="1.0" step="0.05"
                                   @change="updateModelParam('top_p', modelParams.top_p)">
                            <span class="range-value">{{ modelParams.top_p }}</span>
                        </div>
                    </div>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">Top K</div>
                            <div class="setting-desc">{{ gettext('settings.top_k_desc') }}</div>
                        </div>
                        <input type="number" v-model="modelParams.top_k" 
                               min="1" max="100" step="1"
                               @change="updateModelParam('top_k', modelParams.top_k)"
                               class="setting-input number">
                    </div>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">{{ gettext('settings.max_tokens') }}</div>
                            <div class="setting-desc">{{ gettext('settings.max_tokens_desc') }}</div>
                        </div>
                        <input type="number" v-model="modelParams.max_tokens" 
                               min="64" max="4096" step="64"
                               @change="updateModelParam('max_tokens', modelParams.max_tokens)"
                               class="setting-input number">
                    </div>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">{{ gettext('settings.repeat_penalty') }}</div>
                            <div class="setting-desc">{{ gettext('settings.repeat_penalty_desc') }}</div>
                        </div>
                        <div class="setting-with-value">
                            <input type="range" v-model="modelParams.repeat_penalty" 
                                   min="1.0" max="2.0" step="0.1"
                                   @change="updateModelParam('repeat_penalty', modelParams.repeat_penalty)">
                            <span class="range-value">{{ modelParams.repeat_penalty }}</span>
                        </div>
                    </div>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">{{ gettext('settings.frequency_penalty') }}</div>
                            <div class="setting-desc">{{ gettext('settings.frequency_penalty_desc') }}</div>
                        </div>
                        <div class="setting-with-value">
                            <input type="range" v-model="modelParams.frequency_penalty" 
                                   min="0.0" max="2.0" step="0.1"
                                   @change="updateModelParam('frequency_penalty', modelParams.frequency_penalty)">
                            <span class="range-value">{{ modelParams.frequency_penalty }}</span>
                        </div>
                    </div>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">{{ gettext('settings.presence_penalty') }}</div>
                            <div class="setting-desc">{{ gettext('settings.presence_penalty_desc') }}</div>
                        </div>
                        <div class="setting-with-value">
                            <input type="range" v-model="modelParams.presence_penalty" 
                                   min="0.0" max="2.0" step="0.1"
                                   @change="updateModelParam('presence_penalty', modelParams.presence_penalty)">
                            <span class="range-value">{{ modelParams.presence_penalty }}</span>
                        </div>
                    </div>
                </div>
                
                <!-- Rendszer beállítások -->
                <div v-show="settingsTab == 'system'" class="settings-section">
                    <h4>{{ gettext('settings.system') }}</h4>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">{{ gettext('settings.auto_save') }}</div>
                            <div class="setting-desc">{{ gettext('settings.auto_save_desc') }}</div>
                        </div>
                        <label class="switch">
                            <input type="checkbox" v-model="settings.auto_save" 
                                   @change="updateSetting('auto_save', settings.auto_save, 'bool')">
                            <span class="slider"></span>
                        </label>
                    </div>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">{{ gettext('settings.log_level') }}</div>
                            <div class="setting-desc">{{ gettext('settings.log_level_desc') }}</div>
                        </div>
                        <select v-model="settings.log_level" @change="updateSetting('log_level', $event.target.value)">
                            <option value="debug">Debug</option>
                            <option value="info">Info</option>
                            <option value="warning">Warning</option>
                            <option value="error">Error</option>
                        </select>
                    </div>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">{{ gettext('settings.dev_mode') }}</div>
                            <div class="setting-desc">{{ gettext('settings.dev_mode_desc') }}</div>
                        </div>
                        <label class="switch">
                            <input type="checkbox" v-model="settings.dev_mode" 
                                   @change="updateSetting('dev_mode', settings.dev_mode, 'bool')">
                            <span class="slider"></span>
                        </label>
                    </div>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">{{ gettext('settings.auto_start') }}</div>
                            <div class="setting-desc">{{ gettext('settings.auto_start_desc') }}</div>
                        </div>
                        <label class="switch">
                            <input type="checkbox" v-model="settings.auto_start" 
                                   @change="updateSetting('auto_start', settings.auto_start, 'bool')">
                            <span class="slider"></span>
                        </label>
                    </div>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">{{ gettext('settings.telemetry') }}</div>
                            <div class="setting-desc">{{ gettext('settings.telemetry_desc') }}</div>
                        </div>
                        <label class="switch">
                            <input type="checkbox" v-model="settings.telemetry" 
                                   @change="updateSetting('telemetry', settings.telemetry, 'bool')">
                            <span class="slider"></span>
                        </label>
                    </div>
                </div>
                
                <!-- Memória beállítások -->
                <div v-show="settingsTab == 'memory'" class="settings-section">
                    <h4>{{ gettext('settings.memory') }}</h4>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">{{ gettext('settings.max_messages') }}</div>
                            <div class="setting-desc">{{ gettext('settings.max_messages_desc') }}</div>
                        </div>
                        <input type="number" v-model="settings.max_messages" 
                               min="10" max="10000" step="10"
                               @change="updateSetting('max_messages', settings.max_messages, 'int')"
                               class="setting-input number">
                    </div>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">{{ gettext('settings.max_context') }}</div>
                            <div class="setting-desc">{{ gettext('settings.max_context_desc') }}</div>
                        </div>
                        <input type="number" v-model="settings.max_context" 
                               min="512" max="32768" step="512"
                               @change="updateSetting('max_context', settings.max_context, 'int')"
                               class="setting-input number">
                    </div>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">{{ gettext('settings.auto_cleanup') }}</div>
                            <div class="setting-desc">{{ gettext('settings.auto_cleanup_desc') }}</div>
                        </div>
                        <label class="switch">
                            <input type="checkbox" v-model="settings.auto_cleanup" 
                                   @change="updateSetting('auto_cleanup', settings.auto_cleanup, 'bool')">
                            <span class="slider"></span>
                        </label>
                    </div>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">{{ gettext('settings.cleanup_days') }}</div>
                            <div class="setting-desc">{{ gettext('settings.cleanup_days_desc') }}</div>
                        </div>
                        <input type="number" v-model="settings.cleanup_days" 
                               min="1" max="365" step="1"
                               @change="updateSetting('cleanup_days', settings.cleanup_days, 'int')"
                               class="setting-input number">
                    </div>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">{{ gettext('settings.enable_search') }}</div>
                            <div class="setting-desc">{{ gettext('settings.enable_search_desc') }}</div>
                        </div>
                        <label class="switch">
                            <input type="checkbox" v-model="settings.enable_search" 
                                   @change="updateSetting('enable_search', settings.enable_search, 'bool')">
                            <span class="slider"></span>
                        </label>
                    </div>
                </div>
                
                <!-- Hardver beállítások -->
                <div v-show="settingsTab == 'hardware'" class="settings-section">
                    <h4>{{ gettext('settings.hardware') }}</h4>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">{{ gettext('settings.gpu_layers') }}</div>
                            <div class="setting-desc">{{ gettext('settings.gpu_layers_desc') }}</div>
                        </div>
                        <input type="number" v-model="modelParams.n_gpu_layers" 
                               min="-1" max="200"
                               @change="updateModelParam('n_gpu_layers', modelParams.n_gpu_layers)"
                               class="setting-input number">
                    </div>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">{{ gettext('settings.threads') }}</div>
                            <div class="setting-desc">{{ gettext('settings.threads_desc') }}</div>
                        </div>
                        <input type="number" v-model="settings.threads" 
                               min="1" max="32"
                               @change="updateSetting('threads', settings.threads, 'int')"
                               class="setting-input number">
                    </div>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">{{ gettext('settings.batch_threads') }}</div>
                            <div class="setting-desc">{{ gettext('settings.batch_threads_desc') }}</div>
                        </div>
                        <input type="number" v-model="settings.batch_threads" 
                               min="1" max="32"
                               @change="updateSetting('batch_threads', settings.batch_threads, 'int')"
                               class="setting-input number">
                    </div>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">{{ gettext('settings.mlock') }}</div>
                            <div class="setting-desc">{{ gettext('settings.mlock_desc') }}</div>
                        </div>
                        <label class="switch">
                            <input type="checkbox" v-model="settings.mlock" 
                                   @change="updateSetting('mlock', settings.mlock, 'bool')">
                            <span class="slider"></span>
                        </label>
                    </div>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">{{ gettext('settings.mmap') }}</div>
                            <div class="setting-desc">{{ gettext('settings.mmap_desc') }}</div>
                        </div>
                        <label class="switch">
                            <input type="checkbox" v-model="settings.mmap" 
                                   @change="updateSetting('mmap', settings.mmap, 'bool')">
                            <span class="slider"></span>
                        </label>
                    </div>
                </div>
                
                <!-- Hálózati beállítások -->
                <div v-show="settingsTab == 'network'" class="settings-section">
                    <h4>{{ gettext('settings.network') }}</h4>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">{{ gettext('settings.api_enabled') }}</div>
                            <div class="setting-desc">{{ gettext('settings.api_enabled_desc') }}</div>
                        </div>
                        <label class="switch">
                            <input type="checkbox" v-model="settings.api_enabled" 
                                   @change="updateSetting('api_enabled', settings.api_enabled, 'bool')">
                            <span class="slider"></span>
                        </label>
                    </div>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">{{ gettext('settings.api_port') }}</div>
                            <div class="setting-desc">{{ gettext('settings.api_port_desc') }}</div>
                        </div>
                        <input type="number" v-model="settings.api_port" 
                               min="1024" max="65535"
                               @change="updateSetting('api_port', settings.api_port, 'int')"
                               class="setting-input number">
                    </div>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">{{ gettext('settings.cors_enabled') }}</div>
                            <div class="setting-desc">{{ gettext('settings.cors_enabled_desc') }}</div>
                        </div>
                        <label class="switch">
                            <input type="checkbox" v-model="settings.cors_enabled" 
                                   @change="updateSetting('cors_enabled', settings.cors_enabled, 'bool')">
                            <span class="slider"></span>
                        </label>
                    </div>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">{{ gettext('settings.vps_enabled') }}</div>
                            <div class="setting-desc">{{ gettext('settings.vps_enabled_desc') }}</div>
                        </div>
                        <label class="switch">
                            <input type="checkbox" v-model="settings.vps_enabled" 
                                   @change="updateSetting('vps_enabled', settings.vps_enabled, 'bool')">
                            <span class="slider"></span>
                        </label>
                    </div>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">{{ gettext('settings.vps_url') }}</div>
                            <div class="setting-desc">{{ gettext('settings.vps_url_desc') }}</div>
                        </div>
                        <input type="text" v-model="settings.vps_url" 
                               @change="updateSetting('vps_url', $event.target.value)"
                               class="setting-input">
                    </div>
                </div>
            </div>
            
            <!-- Lábléc gombok -->
            <div class="settings-footer">
                <button class="btn-secondary" @click="exportSettings" :disabled="loading">
                    📥 {{ gettext('settings.export') }}
                </button>
                <button class="btn-secondary" @click="importSettings" :disabled="loading">
                    📤 {{ gettext('settings.import') }}
                </button>
                <button class="btn-primary" @click="resetSettings" v-if="isAdmin" :disabled="loading">
                    🔄 {{ gettext('settings.reset') }}
                </button>
                <button class="btn-success" @click="saveAllSettings" v-if="hasUnsavedChanges" :disabled="loading">
                    💾 {{ gettext('ui.save') }}
                </button>
            </div>
            
            <!-- Mentés visszajelzés -->
            <div v-if="saveMessage" class="save-message" :class="saveMessageType">
                {{ saveMessage }}
            </div>
        </div>
    `,
    
    setup() {
        // ====================================================================
        // REAKTÍV ÁLLAPOTOK
        // ====================================================================
        
        const settingsTab = Vue.ref('general');
        const settings = Vue.ref({});
        const originalSettings = Vue.ref({});
        const modelParams = Vue.ref({
            temperature: 0.7,
            top_p: 0.9,
            top_k: 40,
            max_tokens: 256,
            n_gpu_layers: -1,
            repeat_penalty: 1.1,
            frequency_penalty: 0.0,
            presence_penalty: 0.0
        });
        
        // UI állapotok
        const loading = Vue.ref(false);
        const saving = Vue.ref(false);
        const searchQuery = Vue.ref('');
        const saveMessage = Vue.ref('');
        const saveMessageType = Vue.ref('');
        
        // Computed
        const isAdmin = Vue.computed(() => window.store?.isAdmin || false);
        
        const availableModels = Vue.computed(() => window.store?.models || []);
        
        const hasUnsavedChanges = Vue.computed(() => {
            return JSON.stringify(settings.value) !== JSON.stringify(originalSettings.value);
        });
        
        // Keresési eredmények
        const searchResults = Vue.computed(() => {
            if (!searchQuery.value) return [];
            
            const query = searchQuery.value.toLowerCase();
            const results = [];
            
            const allSettings = {
                ...settings.value,
                ...modelParams.value
            };
            
            Object.entries(allSettings).forEach(([key, value]) => {
                if (key.toLowerCase().includes(query) || 
                    String(value).toLowerCase().includes(query)) {
                    results.push({
                        key,
                        name: getSettingName(key),
                        value,
                        category: getSettingCategory(key)
                    });
                }
            });
            
            return results.slice(0, 20);
        });
        
        // ====================================================================
        // SEGÉDFÜGGVÉNYEK
        // ====================================================================
        
        const gettext = (key, params = {}) => {
            return window.gettext ? window.gettext(key, params) : key;
        };
        
        const getSettingName = (key) => {
            const names = {
                user_name: gettext('settings.user_name'),
                language: gettext('settings.language'),
                timezone: gettext('settings.timezone'),
                theme: gettext('settings.theme'),
                temperature: 'Temperature',
                top_p: 'Top P',
                max_tokens: gettext('settings.max_tokens'),
                n_gpu_layers: gettext('settings.gpu_layers'),
                auto_save: gettext('settings.auto_save'),
                log_level: gettext('settings.log_level'),
                dev_mode: gettext('settings.dev_mode'),
                max_messages: gettext('settings.max_messages'),
                max_context: gettext('settings.max_context'),
                auto_cleanup: gettext('settings.auto_cleanup')
            };
            return names[key] || key;
        };
        
        const getSettingCategory = (key) => {
            if (['user_name', 'language', 'timezone', 'theme'].includes(key)) return 'general';
            if (['temperature', 'top_p', 'max_tokens'].includes(key)) return 'model';
            if (['auto_save', 'log_level', 'dev_mode'].includes(key)) return 'system';
            if (['max_messages', 'max_context', 'auto_cleanup'].includes(key)) return 'memory';
            return 'other';
        };
        
        const displayValue = (value) => {
            if (typeof value === 'boolean') return value ? '✓' : '✗';
            if (value === null || value === undefined) return '-';
            return String(value);
        };
        
        const showSaveMessage = (message, type = 'success') => {
            saveMessage.value = message;
            saveMessageType.value = type;
            setTimeout(() => {
                saveMessage.value = '';
            }, 3000);
        };
        
        // ====================================================================
        // BEÁLLÍTÁSOK KEZELÉSE
        // ====================================================================
        
        const loadSettings = async () => {
            loading.value = true;
            
            try {
                if (window.api) {
                    const data = await window.api.getSettings();
                    settings.value = data;
                    originalSettings.value = JSON.parse(JSON.stringify(data));
                    
                    // Modell paraméterek külön
                    modelParams.value = {
                        temperature: parseFloat(data.temperature || 0.7),
                        top_p: parseFloat(data.top_p || 0.9),
                        top_k: parseInt(data.top_k || 40),
                        max_tokens: parseInt(data.max_tokens || 256),
                        n_gpu_layers: parseInt(data.n_gpu_layers || -1),
                        repeat_penalty: parseFloat(data.repeat_penalty || 1.1),
                        frequency_penalty: parseFloat(data.frequency_penalty || 0.0),
                        presence_penalty: parseFloat(data.presence_penalty || 0.0)
                    };
                    
                    console.log('Settings loaded:', data);
                }
            } catch (error) {
                console.error('Error loading settings:', error);
                showSaveMessage(gettext('settings.load_error'), 'error');
            } finally {
                loading.value = false;
            }
        };
        
        const updateSetting = async (key, value, type = null) => {
            if (!isAdmin.value) return;
            
            try {
                await window.api.updateSetting(key, value, type);
                showSaveMessage(gettext('settings.saved'), 'success');
                
                // Speciális esetek kezelése
                if (key === 'language') {
                    window.changeLanguage?.(value);
                }
                if (key === 'theme') {
                    updateTheme(value);
                }
                
            } catch (error) {
                console.error('Error updating setting:', error);
                showSaveMessage(gettext('settings.save_error'), 'error');
            }
        };
        
        const updateModelParam = (key, value) => {
            updateSetting(key, value, 
                typeof value === 'number' ? (Number.isInteger(value) ? 'int' : 'float') : 'string'
            );
        };
        
        const saveAllSettings = async () => {
            if (!isAdmin.value) return;
            
            saving.value = true;
            
            try {
                // Összes beállítás mentése
                const allSettings = {
                    ...settings.value,
                    ...modelParams.value
                };
                
                for (const [key, value] of Object.entries(allSettings)) {
                    await window.api.updateSetting(key, value);
                }
                
                originalSettings.value = JSON.parse(JSON.stringify(settings.value));
                showSaveMessage(gettext('settings.all_saved'), 'success');
                
            } catch (error) {
                console.error('Error saving all settings:', error);
                showSaveMessage(gettext('settings.save_error'), 'error');
            } finally {
                saving.value = false;
            }
        };
        
        const updateLanguage = (event) => {
            const lang = event.target.value;
            updateSetting('language', lang);
            window.changeLanguage?.(lang);
        };
        
        const updateTheme = (theme) => {
            if (theme === 'system') {
                const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
                document.documentElement.setAttribute('data-theme', prefersDark ? 'dark' : 'light');
            } else {
                document.documentElement.setAttribute('data-theme', theme);
            }
        };
        
        // ====================================================================
        // EXPORT/IMPORT
        // ====================================================================
        
        const exportSettings = () => {
            const data = {
                settings: settings.value,
                modelParams: modelParams.value,
                exported: new Date().toISOString(),
                version: '3.0'
            };
            
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `soulcore_settings_${new Date().toISOString().slice(0,10)}.json`;
            a.click();
            
            showSaveMessage(gettext('settings.exported'), 'success');
        };
        
        const importSettings = () => {
            const input = document.createElement('input');
            input.type = 'file';
            input.accept = '.json';
            
            input.onchange = (e) => {
                const file = e.target.files[0];
                const reader = new FileReader();
                
                reader.onload = async (e) => {
                    try {
                        const data = JSON.parse(e.target.result);
                        
                        if (data.version !== '3.0') {
                            if (!confirm(gettext('settings.version_mismatch'))) return;
                        }
                        
                        if (data.settings) {
                            Object.entries(data.settings).forEach(([key, value]) => {
                                updateSetting(key, value);
                            });
                        }
                        
                        if (data.modelParams) {
                            Object.entries(data.modelParams).forEach(([key, value]) => {
                                updateModelParam(key, value);
                            });
                        }
                        
                        await loadSettings();
                        showSaveMessage(gettext('settings.imported'), 'success');
                        
                    } catch (error) {
                        alert(gettext('settings.import_error') + ': ' + error.message);
                    }
                };
                
                reader.readAsText(file);
            };
            
            input.click();
        };
        
        const resetSettings = async () => {
            if (!isAdmin.value) return;
            
            if (!confirm(gettext('settings.confirm_reset'))) return;
            
            const defaults = {
                user_name: window.store?.userName || 'User',
                language: 'en',
                timezone: 'local',
                theme: 'dark',
                auto_save: true,
                log_level: 'info',
                dev_mode: false,
                auto_start: true,
                telemetry: false,
                max_messages: 1000,
                max_context: 4096,
                auto_cleanup: true,
                cleanup_days: 30,
                enable_search: true,
                threads: 4,
                batch_threads: 2,
                mlock: false,
                mmap: true,
                api_enabled: true,
                api_port: 5000,
                cors_enabled: true,
                vps_enabled: false,
                vps_url: '',
                temperature: 0.7,
                top_p: 0.9,
                top_k: 40,
                max_tokens: 256,
                n_gpu_layers: -1,
                repeat_penalty: 1.1,
                frequency_penalty: 0.0,
                presence_penalty: 0.0
            };
            
            for (const [key, value] of Object.entries(defaults)) {
                await updateSetting(key, value, 
                    typeof value === 'number' ? (Number.isInteger(value) ? 'int' : 'float') : 
                    typeof value === 'boolean' ? 'bool' : 'string'
                );
            }
            
            await loadSettings();
            showSaveMessage(gettext('settings.reseted'), 'success');
        };
        
        const jumpToSetting = (result) => {
            settingsTab.value = result.category;
            searchQuery.value = '';
            // Görgetés a beállításhoz (később)
        };
        
        // ====================================================================
        // ÉLETCIKLUS
        // ====================================================================
        
        Vue.onMounted(() => {
            loadSettings();
            
            // Téma betöltése
            const savedTheme = localStorage.getItem('theme') || 'dark';
            updateTheme(savedTheme);
        });
        
        return {
            // Állapotok
            settingsTab,
            settings,
            modelParams,
            loading,
            saving,
            searchQuery,
            searchResults,
            saveMessage,
            saveMessageType,
            
            // Computed
            isAdmin,
            availableModels,
            hasUnsavedChanges,
            
            // Metódusok
            gettext,
            displayValue,
            loadSettings,
            updateSetting,
            updateModelParam,
            saveAllSettings,
            updateLanguage,
            exportSettings,
            importSettings,
            resetSettings,
            jumpToSetting
        };
    }
};

console.log('✅ SettingsPanel betöltve');