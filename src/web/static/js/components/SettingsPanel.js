// Beállítások panel
window.SettingsPanel = {
    template: `
        <div class="settings-panel">
            <div class="settings-tabs">
                <button class="tab-btn" :class="{ active: settingsTab == 'general' }" 
                        @click="settingsTab = 'general'">Általános</button>
                <button class="tab-btn" :class="{ active: settingsTab == 'model' }" 
                        @click="settingsTab = 'model'">Modell</button>
                <button class="tab-btn" :class="{ active: settingsTab == 'system' }" 
                        @click="settingsTab = 'system'">Rendszer</button>
                <button class="tab-btn" :class="{ active: settingsTab == 'memory' }" 
                        @click="settingsTab = 'memory'">Memória</button>
            </div>
            
            <div class="settings-content">
                <!-- Általános beállítások -->
                <div v-show="settingsTab == 'general'">
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">Felhasználónév</div>
                            <div class="setting-desc">A neved, ahogy Kópé szólít</div>
                        </div>
                        <input type="text" v-model="settings.user_name" 
                               @change="updateSetting('user_name', $event.target.value)"
                               class="setting-input">
                    </div>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">Nyelv</div>
                            <div class="setting-desc">Felület nyelve</div>
                        </div>
                        <select v-model="settings.language" @change="updateSetting('language', $event.target.value)">
                            <option value="hu">Magyar</option>
                            <option value="en">English</option>
                        </select>
                    </div>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">Időzóna</div>
                            <div class="setting-desc">Időzóna beállítás</div>
                        </div>
                        <select v-model="settings.timezone" @change="updateSetting('timezone', $event.target.value)">
                            <option value="Europe/Budapest">Budapest</option>
                            <option value="UTC">UTC</option>
                        </select>
                    </div>
                </div>
                
                <!-- Modell beállítások -->
                <div v-show="settingsTab == 'model'">
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">Temperature</div>
                            <div class="setting-desc">Kreativitás szintje (0.1 - 2.0)</div>
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
                            <div class="setting-desc">Mintavételezés (0.0 - 1.0)</div>
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
                            <div class="setting-name">Max tokens</div>
                            <div class="setting-desc">Maximális válasz hossz</div>
                        </div>
                        <input type="number" v-model="modelParams.max_tokens" 
                               min="64" max="4096" step="64"
                               @change="updateModelParam('max_tokens', modelParams.max_tokens)"
                               class="setting-input number">
                    </div>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">GPU rétegek</div>
                            <div class="setting-desc">-1 = összes, 0 = CPU</div>
                        </div>
                        <input type="number" v-model="modelParams.n_gpu_layers" 
                               min="-1" max="100"
                               @change="updateModelParam('n_gpu_layers', modelParams.n_gpu_layers)"
                               class="setting-input number">
                    </div>
                </div>
                
                <!-- Rendszer beállítások -->
                <div v-show="settingsTab == 'system'">
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">Automatikus mentés</div>
                            <div class="setting-desc">Beszélgetések automatikus mentése</div>
                        </div>
                        <label class="switch">
                            <input type="checkbox" v-model="settings.auto_save" 
                                   @change="updateSetting('auto_save', settings.auto_save, 'bool')">
                            <span class="slider"></span>
                        </label>
                    </div>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">Naplózás szintje</div>
                            <div class="setting-desc">Részletesség</div>
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
                            <div class="setting-name">Fejlesztői mód</div>
                            <div class="setting-desc">Részletesebb hibakeresés</div>
                        </div>
                        <label class="switch">
                            <input type="checkbox" v-model="settings.dev_mode" 
                                   @change="updateSetting('dev_mode', settings.dev_mode, 'bool')">
                            <span class="slider"></span>
                        </label>
                    </div>
                </div>
                
                <!-- Memória beállítások -->
                <div v-show="settingsTab == 'memory'">
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">Megőrzött üzenetek</div>
                            <div class="setting-desc">Hány üzenet maradjon a memóriában</div>
                        </div>
                        <input type="number" v-model="settings.max_messages" 
                               min="10" max="1000" step="10"
                               @change="updateSetting('max_messages', settings.max_messages, 'int')"
                               class="setting-input number">
                    </div>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">Kontextus hossz</div>
                            <div class="setting-desc">Maximális token a kontextusban</div>
                        </div>
                        <input type="number" v-model="settings.max_context" 
                               min="512" max="8192" step="512"
                               @change="updateSetting('max_context', settings.max_context, 'int')"
                               class="setting-input number">
                    </div>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <div class="setting-name">Automatikus takarítás</div>
                            <div class="setting-desc">Régi beszélgetések törlése</div>
                        </div>
                        <label class="switch">
                            <input type="checkbox" v-model="settings.auto_cleanup" 
                                   @change="updateSetting('auto_cleanup', settings.auto_cleanup, 'bool')">
                            <span class="slider"></span>
                        </label>
                    </div>
                </div>
            </div>
            
            <div class="settings-footer">
                <button class="btn-secondary" @click="exportSettings">Exportálás</button>
                <button class="btn-secondary" @click="importSettings">Importálás</button>
                <button class="btn-primary" @click="resetSettings" v-if="isAdmin">Alaphelyzet</button>
            </div>
        </div>
    `,
    
    setup() {
        const settingsTab = Vue.ref('general');
        const settings = Vue.ref({});
        const modelParams = Vue.ref({
            temperature: 0.7,
            top_p: 0.9,
            max_tokens: 256,
            n_gpu_layers: -1
        });
        
        // Javítás: window.store.isAdmin
        const isAdmin = Vue.computed(() => window.store?.isAdmin || false);
        
        // Beállítások betöltése
        const loadSettings = async () => {
            console.log('Settings betöltése...');
            if (window.api) {
                try {
                    const data = await window.api.getSettings();
                    settings.value = data;
                    
                    // Modell paraméterek külön
                    modelParams.value = {
                        temperature: parseFloat(data.temperature || 0.7),
                        top_p: parseFloat(data.top_p || 0.9),
                        max_tokens: parseInt(data.max_tokens || 256),
                        n_gpu_layers: parseInt(data.n_gpu_layers || -1)
                    };
                    console.log('Settings betöltve:', data);
                } catch (error) {
                    console.error('Hiba a settings betöltésekor:', error);
                }
            } else {
                console.error('API nem elérhető');
            }
        };
        
        const updateSetting = (key, value, type = null) => {
            console.log(`Beállítás módosítva: ${key} = ${value}`);
            if (window.api) {
                window.api.updateSetting(key, value, type).catch(err => 
                    console.error('Hiba a beállítás mentésekor:', err)
                );
            }
        };
        
        const updateModelParam = (key, value) => {
            console.log(`Modell paraméter módosítva: ${key} = ${value}`);
            updateSetting(key, value, 
                typeof value === 'number' ? (Number.isInteger(value) ? 'int' : 'float') : 'string'
            );
        };
        
        const exportSettings = () => {
            const data = {
                settings: settings.value,
                modelParams: modelParams.value,
                exported: new Date().toISOString()
            };
            
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `soulcore_settings_${new Date().toISOString().slice(0,10)}.json`;
            a.click();
        };
        
        const importSettings = () => {
            const input = document.createElement('input');
            input.type = 'file';
            input.accept = '.json';
            input.onchange = (e) => {
                const file = e.target.files[0];
                const reader = new FileReader();
                reader.onload = (e) => {
                    try {
                        const data = JSON.parse(e.target.result);
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
                        alert('Beállítások importálva!');
                        loadSettings();
                    } catch (error) {
                        alert('Hiba a fájl feldolgozása közben: ' + error.message);
                    }
                };
                reader.readAsText(file);
            };
            input.click();
        };
        
        const resetSettings = async () => {
            if (!isAdmin.value) return;
            
            if (confirm('Biztosan visszaállítod az alapértelmezett beállításokat?')) {
                // Alapértelmezett értékek
                const defaults = {
                    temperature: 0.7,
                    top_p: 0.9,
                    max_tokens: 256,
                    n_gpu_layers: -1,
                    user_name: 'Grumpy',
                    language: 'hu',
                    log_level: 'info',
                    auto_save: true,
                    dev_mode: false,
                    max_messages: 200,
                    max_context: 4096,
                    auto_cleanup: true
                };
                
                Object.entries(defaults).forEach(([key, value]) => {
                    updateSetting(key, value, 
                        typeof value === 'number' ? (Number.isInteger(value) ? 'int' : 'float') : 
                        typeof value === 'boolean' ? 'bool' : 'string'
                    );
                });
                
                await loadSettings();
            }
        };
        
        // Initial load
        loadSettings();
        
        return {
            settingsTab,
            settings,
            modelParams,
            isAdmin,
            updateSetting,
            updateModelParam,
            exportSettings,
            importSettings,
            resetSettings
        };
    }
};

console.log('✅ SettingsPanel betöltve');