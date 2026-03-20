// ==============================================
// SOULCORE 3.0 - Beállítások panel komponens
// ==============================================

window.SettingsPanel = {
    name: 'SettingsPanel',
    
    template: `
        <div class="settings-panel">
            <div class="settings-section">
                <h4>{{ t('settings.theme') }}</h4>
                <div class="setting-item">
                    <span class="setting-label">{{ t('settings.theme_mode') }}</span>
                    <select v-model="theme" class="form-input" @change="changeTheme">
                        <option value="dark">{{ t('settings.theme_dark') }}</option>
                        <option value="light">{{ t('settings.theme_light') }}</option>
                    </select>
                </div>
            </div>
            
            <div class="settings-section">
                <h4>{{ t('settings.language') }}</h4>
                <div class="setting-item">
                    <span class="setting-label">{{ t('settings.ui_language') }}</span>
                    <select v-model="language" class="form-input" @change="changeLanguage">
                        <option v-for="lang in supportedLanguages" :key="lang.code" :value="lang.code">
                            {{ lang.name }}
                        </option>
                    </select>
                </div>
            </div>
            
            <div class="settings-section">
                <h4>{{ t('settings.system') }}</h4>
                <div class="setting-item">
                    <span class="setting-label">{{ t('settings.system_id') }}</span>
                    <span class="setting-value"><code>{{ systemId }}</code></span>
                </div>
            </div>
        </div>
    `,
    
    setup() {
        const theme = Vue.ref(window.store.theme || 'dark');
        const language = Vue.ref(window.i18n?.language || 'hu');
        const systemId = Vue.computed(() => window.store.systemId);
        
        const supportedLanguages = window.i18n?.getSupportedLanguages() || [
            { code: 'hu', name: 'Magyar' },
            { code: 'en', name: 'English' }
        ];
        
        const t = (key, params = {}) => {
            return window.gettext ? window.gettext(key, params) : key;
        };
        
        const changeTheme = () => {
            window.store.setTheme(theme.value);
        };
        
        const changeLanguage = () => {
            window.i18n.setLanguage(language.value);
            window.store.setUserLanguage(language.value);
            window.store.addNotification('success', t('settings.language_changed'));
        };
        
        return {
            theme,
            language,
            systemId,
            supportedLanguages,
            t,
            changeTheme,
            changeLanguage
        };
    }
};

console.log('✅ SettingsPanel komponens betöltve');