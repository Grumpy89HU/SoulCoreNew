// ==============================================
// SOULCORE 3.0 - Beállítások panel komponens
// ==============================================

window.SettingsPanel = {
    name: 'SettingsPanel',
    
    template: `
        <div class="settings-panel">
            <!-- Beállítások kategória fülek -->
            <div class="settings-tabs">
                <button 
                    v-for="tab in tabs" 
                    :key="tab.id"
                    class="tab-btn" 
                    :class="{ active: activeTab === tab.id }"
                    @click="activeTab = tab.id">
                    <span class="tab-icon">{{ tab.icon }}</span>
                    <span>{{ tab.name }}</span>
                </button>
            </div>
            
            <!-- Megjelenés beállítások -->
            <div v-show="activeTab === 'appearance'" class="settings-section">
                <div class="setting-item">
                    <div class="setting-info">
                        <div class="setting-name">{{ t('settings.theme_mode') }}</div>
                        <div class="setting-desc">{{ t('settings.theme_desc') }}</div>
                    </div>
                    <div class="setting-control">
                        <select v-model="theme" @change="changeTheme" class="setting-select">
                            <option value="dark">{{ t('settings.theme_dark') }}</option>
                            <option value="light">{{ t('settings.theme_light') }}</option>
                            <option value="system">{{ t('settings.theme_system') }}</option>
                        </select>
                    </div>
                </div>
                
                <div class="setting-item">
                    <div class="setting-info">
                        <div class="setting-name">{{ t('settings.font_size') }}</div>
                        <div class="setting-desc">{{ t('settings.font_size_desc') }}</div>
                    </div>
                    <div class="setting-control">
                        <select v-model="fontSize" @change="changeFontSize" class="setting-select">
                            <option value="small">{{ t('settings.font_small') }}</option>
                            <option value="medium">{{ t('settings.font_medium') }}</option>
                            <option value="large">{{ t('settings.font_large') }}</option>
                        </select>
                    </div>
                </div>
                
                <div class="setting-item">
                    <div class="setting-info">
                        <div class="setting-name">{{ t('settings.chat_density') }}</div>
                        <div class="setting-desc">{{ t('settings.chat_density_desc') }}</div>
                    </div>
                    <div class="setting-control">
                        <select v-model="chatDensity" @change="changeChatDensity" class="setting-select">
                            <option value="compact">{{ t('settings.density_compact') }}</option>
                            <option value="comfortable">{{ t('settings.density_comfortable') }}</option>
                            <option value="spacious">{{ t('settings.density_spacious') }}</option>
                        </select>
                    </div>
                </div>
            </div>
            
            <!-- Nyelv beállítások -->
            <div v-show="activeTab === 'language'" class="settings-section">
                <div class="setting-item">
                    <div class="setting-info">
                        <div class="setting-name">{{ t('settings.ui_language') }}</div>
                        <div class="setting-desc">{{ t('settings.ui_language_desc') }}</div>
                    </div>
                    <div class="setting-control">
                        <select v-model="language" @change="changeLanguage" class="setting-select">
                            <option v-for="lang in languages" :key="lang.code" :value="lang.code">
                                {{ lang.name }}
                            </option>
                        </select>
                    </div>
                </div>
                
                <div class="setting-item">
                    <div class="setting-info">
                        <div class="setting-name">{{ t('settings.time_format') }}</div>
                        <div class="setting-desc">{{ t('settings.time_format_desc') }}</div>
                    </div>
                    <div class="setting-control">
                        <select v-model="timeFormat" @change="changeTimeFormat" class="setting-select">
                            <option value="12h">12 {{ t('settings.hour_format') }}</option>
                            <option value="24h">24 {{ t('settings.hour_format') }}</option>
                        </select>
                    </div>
                </div>
                
                <div class="setting-item">
                    <div class="setting-info">
                        <div class="setting-name">{{ t('settings.date_format') }}</div>
                        <div class="setting-desc">{{ t('settings.date_format_desc') }}</div>
                    </div>
                    <div class="setting-control">
                        <select v-model="dateFormat" @change="changeDateFormat" class="setting-select">
                            <option value="YYYY-MM-DD">YYYY-MM-DD</option>
                            <option value="DD/MM/YYYY">DD/MM/YYYY</option>
                            <option value="MM/DD/YYYY">MM/DD/YYYY</option>
                        </select>
                    </div>
                </div>
            </div>
            
            <!-- Chat beállítások -->
            <div v-show="activeTab === 'chat'" class="settings-section">
                <div class="setting-item">
                    <div class="setting-info">
                        <div class="setting-name">{{ t('settings.default_model') }}</div>
                        <div class="setting-desc">{{ t('settings.default_model_desc') }}</div>
                    </div>
                    <div class="setting-control">
                        <select v-model="defaultModel" @change="changeDefaultModel" class="setting-select">
                            <option v-for="model in models" :key="model.id" :value="model.id">
                                {{ model.name }}
                            </option>
                        </select>
                    </div>
                </div>
                
                <div class="setting-item">
                    <div class="setting-info">
                        <div class="setting-name">{{ t('settings.default_prompt') }}</div>
                        <div class="setting-desc">{{ t('settings.default_prompt_desc') }}</div>
                    </div>
                    <div class="setting-control">
                        <select v-model="defaultPrompt" @change="changeDefaultPrompt" class="setting-select">
                            <option v-for="prompt in prompts" :key="prompt.id" :value="prompt.id">
                                {{ prompt.name }}
                            </option>
                        </select>
                    </div>
                </div>
                
                <div class="setting-item">
                    <div class="setting-info">
                        <div class="setting-name">{{ t('settings.default_personality') }}</div>
                        <div class="setting-desc">{{ t('settings.default_personality_desc') }}</div>
                    </div>
                    <div class="setting-control">
                        <select v-model="defaultPersonality" @change="changeDefaultPersonality" class="setting-select">
                            <option v-for="personality in personalities" :key="personality.id" :value="personality.id">
                                {{ personality.name }}
                            </option>
                        </select>
                    </div>
                </div>
                
                <div class="setting-item">
                    <div class="setting-info">
                        <div class="setting-name">{{ t('settings.temperature') }}</div>
                        <div class="setting-desc">{{ t('settings.temperature_desc') }}</div>
                    </div>
                    <div class="setting-control setting-with-value">
                        <input type="range" v-model="temperature" min="0.1" max="2.0" step="0.01" 
                               @change="changeTemperature" class="setting-range">
                        <span class="range-value">{{ temperature }}</span>
                    </div>
                </div>
                
                <div class="setting-item">
                    <div class="setting-info">
                        <div class="setting-name">{{ t('settings.top_p') }}</div>
                        <div class="setting-desc">{{ t('settings.top_p_desc') }}</div>
                    </div>
                    <div class="setting-control setting-with-value">
                        <input type="range" v-model="topP" min="0.1" max="1.0" step="0.01" 
                               @change="changeTopP" class="setting-range">
                        <span class="range-value">{{ topP }}</span>
                    </div>
                </div>
                
                <div class="setting-item">
                    <div class="setting-info">
                        <div class="setting-name">{{ t('settings.max_context') }}</div>
                        <div class="setting-desc">{{ t('settings.max_context_desc') }}</div>
                    </div>
                    <div class="setting-control">
                        <select v-model="maxContext" @change="changeMaxContext" class="setting-select">
                            <option value="2048">2048</option>
                            <option value="4096">4096</option>
                            <option value="8192">8192</option>
                            <option value="16384">16384</option>
                            <option value="32768">32768</option>
                        </select>
                    </div>
                </div>
            </div>
            
            <!-- Rendszer beállítások (admin) -->
            <div v-show="activeTab === 'system' && isAdmin" class="settings-section">
                <div class="setting-item">
                    <div class="setting-info">
                        <div class="setting-name">{{ t('settings.system_id') }}</div>
                        <div class="setting-desc">{{ t('settings.system_id_desc') }}</div>
                    </div>
                    <div class="setting-control">
                        <code class="setting-code">{{ systemId }}</code>
                    </div>
                </div>
                
                <div class="setting-item">
                    <div class="setting-info">
                        <div class="setting-name">{{ t('settings.dev_mode') }}</div>
                        <div class="setting-desc">{{ t('settings.dev_mode_desc') }}</div>
                    </div>
                    <div class="setting-control">
                        <label class="switch">
                            <input type="checkbox" v-model="devMode" @change="changeDevMode">
                            <span class="slider"></span>
                        </label>
                    </div>
                </div>
                
                <div class="setting-item">
                    <div class="setting-info">
                        <div class="setting-name">{{ t('settings.debug_mode') }}</div>
                        <div class="setting-desc">{{ t('settings.debug_mode_desc') }}</div>
                    </div>
                    <div class="setting-control">
                        <label class="switch">
                            <input type="checkbox" v-model="debugMode" @change="changeDebugMode">
                            <span class="slider"></span>
                        </label>
                    </div>
                </div>
                
                <div class="setting-item">
                    <div class="setting-info">
                        <div class="setting-name">{{ t('settings.auto_save') }}</div>
                        <div class="setting-desc">{{ t('settings.auto_save_desc') }}</div>
                    </div>
                    <div class="setting-control">
                        <label class="switch">
                            <input type="checkbox" v-model="autoSave" @change="changeAutoSave">
                            <span class="slider"></span>
                        </label>
                    </div>
                </div>
            </div>
            
            <!-- GPU beállítások (admin) -->
            <div v-show="activeTab === 'gpu' && isAdmin" class="settings-section">
                <div class="setting-item">
                    <div class="setting-info">
                        <div class="setting-name">{{ t('settings.throttle_temp') }}</div>
                        <div class="setting-desc">{{ t('settings.throttle_temp_desc') }}</div>
                    </div>
                    <div class="setting-control setting-with-value">
                        <input type="range" v-model="throttleTemp" min="60" max="95" step="1" 
                               @change="changeThrottleTemp" class="setting-range">
                        <span class="range-value">{{ throttleTemp }}°C</span>
                    </div>
                </div>
                
                <div class="setting-item">
                    <div class="setting-info">
                        <div class="setting-name">{{ t('settings.throttle_factor') }}</div>
                        <div class="setting-desc">{{ t('settings.throttle_factor_desc') }}</div>
                    </div>
                    <div class="setting-control setting-with-value">
                        <input type="range" v-model="throttleFactor" min="0.5" max="1.0" step="0.01" 
                               @change="changeThrottleFactor" class="setting-range">
                        <span class="range-value">{{ (throttleFactor * 100).toFixed(0) }}%</span>
                    </div>
                </div>
                
                <div class="setting-item">
                    <div class="setting-info">
                        <div class="setting-name">{{ t('settings.emergency_temp') }}</div>
                        <div class="setting-desc">{{ t('settings.emergency_temp_desc') }}</div>
                    </div>
                    <div class="setting-control setting-with-value">
                        <input type="range" v-model="emergencyTemp" min="85" max="100" step="1" 
                               @change="changeEmergencyTemp" class="setting-range">
                        <span class="range-value">{{ emergencyTemp }}°C</span>
                    </div>
                </div>
            </div>
            
            <!-- Mentés gomb -->
            <div class="settings-footer">
                <button class="btn-secondary" @click="resetSettings">
                    {{ t('settings.reset') }}
                </button>
                <button class="btn-primary" @click="saveAllSettings" :disabled="saving">
                    <span v-if="!saving">💾 {{ t('ui.save') }}</span>
                    <span v-else class="spinner-small"></span>
                </button>
            </div>
            
            <!-- Mentés üzenet -->
            <div v-if="saveMessage" class="save-message" :class="saveMessageType">
                {{ saveMessage }}
            </div>
        </div>
    `,
    
    setup() {
        // ====================================================================
        // REAKTÍV ÁLLAPOTOK
        // ====================================================================
        
        const isAdmin = Vue.computed(() => window.store.user?.role === 'admin');
        const systemId = Vue.computed(() => window.store.systemId);
        const models = Vue.computed(() => window.store.models);
        const prompts = Vue.computed(() => window.store.prompts);
        const personalities = Vue.computed(() => window.store.personalities);
        
        // UI állapotok
        const activeTab = Vue.ref('appearance');
        const saving = Vue.ref(false);
        const saveMessage = Vue.ref('');
        const saveMessageType = Vue.ref('');
        
        // Megjelenés beállítások
        const theme = Vue.ref(localStorage.getItem('theme') || 'dark');
        const fontSize = Vue.ref(localStorage.getItem('fontSize') || 'medium');
        const chatDensity = Vue.ref(localStorage.getItem('chatDensity') || 'comfortable');
        
        // Nyelv beállítások
        const language = Vue.ref(window.i18n?.language || 'hu');
        const timeFormat = Vue.ref(localStorage.getItem('timeFormat') || '24h');
        const dateFormat = Vue.ref(localStorage.getItem('dateFormat') || 'YYYY-MM-DD');
        
        // Chat beállítások
        const defaultModel = Vue.ref(null);
        const defaultPrompt = Vue.ref(null);
        const defaultPersonality = Vue.ref(null);
        const temperature = Vue.ref(0.7);
        const topP = Vue.ref(0.9);
        const maxContext = Vue.ref(4096);
        
        // Rendszer beállítások (admin)
        const devMode = Vue.ref(false);
        const debugMode = Vue.ref(false);
        const autoSave = Vue.ref(true);
        
        // GPU beállítások (admin)
        const throttleTemp = Vue.ref(80);
        const throttleFactor = Vue.ref(0.8);
        const emergencyTemp = Vue.ref(90);
        
        // Támogatott nyelvek
        const languages = window.i18n?.getSupportedLanguages() || [
            { code: 'hu', name: 'Magyar' },
            { code: 'en', name: 'English' }
        ];
        
        // Kategória fülek
        const tabs = [
            { id: 'appearance', name: t('settings.appearance'), icon: '🎨' },
            { id: 'language', name: t('settings.language'), icon: '🌐' },
            { id: 'chat', name: t('settings.chat'), icon: '💬' },
            { id: 'system', name: t('settings.system'), icon: '⚙️' },
            { id: 'gpu', name: t('settings.gpu'), icon: '🖥️' }
        ];
        
        // ====================================================================
        // SEGÉDFÜGGVÉNYEK
        // ====================================================================
        
        const t = (key, params = {}) => window.gettext(key, params);
        
        /**
         * Mentett beállítások betöltése
         */
        const loadSettings = async () => {
            try {
                const settings = await window.api.getSettings();
                
                // Chat beállítások
                if (settings.default_model) defaultModel.value = settings.default_model;
                if (settings.default_prompt) defaultPrompt.value = settings.default_prompt;
                if (settings.default_personality) defaultPersonality.value = settings.default_personality;
                if (settings.temperature) temperature.value = settings.temperature;
                if (settings.top_p) topP.value = settings.top_p;
                if (settings.max_context) maxContext.value = settings.max_context;
                
                // Rendszer beállítások
                if (settings.dev_mode) devMode.value = settings.dev_mode;
                if (settings.debug_mode) debugMode.value = settings.debug_mode;
                if (settings.auto_save) autoSave.value = settings.auto_save;
                
                // GPU beállítások
                if (settings.throttle_temp) throttleTemp.value = settings.throttle_temp;
                if (settings.throttle_factor) throttleFactor.value = settings.throttle_factor;
                if (settings.emergency_temp) emergencyTemp.value = settings.emergency_temp;
            } catch (error) {
                console.error('Error loading settings:', error);
            }
        };
        
        /**
         * Megjelenítés frissítése
         */
        const updateAppearance = () => {
            // Téma
            document.documentElement.setAttribute('data-theme', theme.value);
            localStorage.setItem('theme', theme.value);
            
            // Betűméret
            const fontSizeMap = { small: '12px', medium: '14px', large: '16px' };
            document.body.style.fontSize = fontSizeMap[fontSize.value];
            localStorage.setItem('fontSize', fontSize.value);
            
            // Chat sűrűség
            const densityMap = {
                compact: { padding: '8px', gap: '8px' },
                comfortable: { padding: '12px', gap: '12px' },
                spacious: { padding: '16px', gap: '16px' }
            };
            const density = densityMap[chatDensity.value];
            document.documentElement.style.setProperty('--chat-padding', density.padding);
            document.documentElement.style.setProperty('--chat-gap', density.gap);
            localStorage.setItem('chatDensity', chatDensity.value);
        };
        
        /**
         * Időformátum frissítése
         */
        const updateTimeFormat = () => {
            localStorage.setItem('timeFormat', timeFormat.value);
            // Itt lehetne frissíteni a globális formázót
        };
        
        /**
         * Dátumformátum frissítése
         */
        const updateDateFormat = () => {
            localStorage.setItem('dateFormat', dateFormat.value);
        };
        
        // ====================================================================
        // BEÁLLÍTÁS VÁLTOZTATÓK
        // ====================================================================
        
        const changeTheme = () => {
            updateAppearance();
        };
        
        const changeFontSize = () => {
            updateAppearance();
        };
        
        const changeChatDensity = () => {
            updateAppearance();
        };
        
        const changeLanguage = () => {
            window.i18n.setLanguage(language.value);
            window.store.setLanguage(language.value);
            saveMessage.value = t('settings.language_changed');
            saveMessageType.value = 'success';
            setTimeout(() => { saveMessage.value = ''; }, 3000);
        };
        
        const changeTimeFormat = () => {
            updateTimeFormat();
        };
        
        const changeDateFormat = () => {
            updateDateFormat();
        };
        
        const changeDefaultModel = async () => {
            if (defaultModel.value) {
                await window.api.updateSetting('default_model', defaultModel.value);
            }
        };
        
        const changeDefaultPrompt = async () => {
            if (defaultPrompt.value) {
                await window.api.updateSetting('default_prompt', defaultPrompt.value);
            }
        };
        
        const changeDefaultPersonality = async () => {
            if (defaultPersonality.value) {
                await window.api.updateSetting('default_personality', defaultPersonality.value);
            }
        };
        
        const changeTemperature = async () => {
            await window.api.updateSetting('temperature', temperature.value);
        };
        
        const changeTopP = async () => {
            await window.api.updateSetting('top_p', topP.value);
        };
        
        const changeMaxContext = async () => {
            await window.api.updateSetting('max_context', maxContext.value);
        };
        
        const changeDevMode = async () => {
            await window.api.updateSetting('dev_mode', devMode.value);
        };
        
        const changeDebugMode = async () => {
            await window.api.updateSetting('debug_mode', debugMode.value);
        };
        
        const changeAutoSave = async () => {
            await window.api.updateSetting('auto_save', autoSave.value);
        };
        
        const changeThrottleTemp = async () => {
            await window.api.updateSetting('throttle_temp', throttleTemp.value);
        };
        
        const changeThrottleFactor = async () => {
            await window.api.updateSetting('throttle_factor', throttleFactor.value);
        };
        
        const changeEmergencyTemp = async () => {
            await window.api.updateSetting('emergency_temp', emergencyTemp.value);
        };
        
        /**
         * Összes beállítás mentése
         */
        const saveAllSettings = async () => {
            saving.value = true;
            
            try {
                await Promise.all([
                    window.api.updateSetting('default_model', defaultModel.value),
                    window.api.updateSetting('default_prompt', defaultPrompt.value),
                    window.api.updateSetting('default_personality', defaultPersonality.value),
                    window.api.updateSetting('temperature', temperature.value),
                    window.api.updateSetting('top_p', topP.value),
                    window.api.updateSetting('max_context', maxContext.value),
                    window.api.updateSetting('dev_mode', devMode.value),
                    window.api.updateSetting('debug_mode', debugMode.value),
                    window.api.updateSetting('auto_save', autoSave.value),
                    window.api.updateSetting('throttle_temp', throttleTemp.value),
                    window.api.updateSetting('throttle_factor', throttleFactor.value),
                    window.api.updateSetting('emergency_temp', emergencyTemp.value)
                ]);
                
                saveMessage.value = t('settings.saved');
                saveMessageType.value = 'success';
                setTimeout(() => { saveMessage.value = ''; }, 3000);
            } catch (error) {
                console.error('Error saving settings:', error);
                saveMessage.value = t('settings.save_error');
                saveMessageType.value = 'error';
                setTimeout(() => { saveMessage.value = ''; }, 3000);
            } finally {
                saving.value = false;
            }
        };
        
        /**
         * Beállítások alaphelyzetbe állítása
         */
        const resetSettings = async () => {
            if (!confirm(t('settings.confirm_reset'))) return;
            
            // Alapértékek visszaállítása
            theme.value = 'dark';
            fontSize.value = 'medium';
            chatDensity.value = 'comfortable';
            language.value = 'hu';
            timeFormat.value = '24h';
            dateFormat.value = 'YYYY-MM-DD';
            temperature.value = 0.7;
            topP.value = 0.9;
            maxContext.value = 4096;
            devMode.value = false;
            debugMode.value = false;
            autoSave.value = true;
            throttleTemp.value = 80;
            throttleFactor.value = 0.8;
            emergencyTemp.value = 90;
            
            updateAppearance();
            updateTimeFormat();
            updateDateFormat();
            
            await saveAllSettings();
            
            saveMessage.value = t('settings.reset_done');
            saveMessageType.value = 'success';
            setTimeout(() => { saveMessage.value = ''; }, 3000);
        };
        
        // ====================================================================
        // ÉLETCIKLUS
        // ====================================================================
        
        Vue.onMounted(() => {
            loadSettings();
            updateAppearance();
            updateTimeFormat();
            updateDateFormat();
        });
        
        // ====================================================================
        // RETURN
        // ====================================================================
        
        return {
            // Állapotok
            isAdmin,
            systemId,
            models,
            prompts,
            personalities,
            activeTab,
            saving,
            saveMessage,
            saveMessageType,
            tabs,
            languages,
            
            // Megjelenés
            theme,
            fontSize,
            chatDensity,
            
            // Nyelv
            language,
            timeFormat,
            dateFormat,
            
            // Chat
            defaultModel,
            defaultPrompt,
            defaultPersonality,
            temperature,
            topP,
            maxContext,
            
            // Rendszer
            devMode,
            debugMode,
            autoSave,
            
            // GPU
            throttleTemp,
            throttleFactor,
            emergencyTemp,
            
            // Segédfüggvények
            t,
            
            // Metódusok
            changeTheme,
            changeFontSize,
            changeChatDensity,
            changeLanguage,
            changeTimeFormat,
            changeDateFormat,
            changeDefaultModel,
            changeDefaultPrompt,
            changeDefaultPersonality,
            changeTemperature,
            changeTopP,
            changeMaxContext,
            changeDevMode,
            changeDebugMode,
            changeAutoSave,
            changeThrottleTemp,
            changeThrottleFactor,
            changeEmergencyTemp,
            saveAllSettings,
            resetSettings
        };
    }
};

console.log('✅ SettingsPanel komponens betöltve');