// ==============================================
// SOULCORE 3.0 - Admin panel komponens
// ==============================================

window.AdminPanel = {
    name: 'AdminPanel',
    
    template: `
        <div class="admin-panel">
            <div class="admin-tabs">
                <button 
                    class="tab-btn" 
                    :class="{ active: activeTab === 'modules' }"
                    @click="activeTab = 'modules'"
                >
                    {{ t('admin.modules') }}
                </button>
                <button 
                    class="tab-btn" 
                    :class="{ active: activeTab === 'models' }"
                    @click="activeTab = 'models'"
                >
                    {{ t('admin.models') }}
                </button>
                <button 
                    class="tab-btn" 
                    :class="{ active: activeTab === 'prompts' }"
                    @click="activeTab = 'prompts'"
                >
                    {{ t('admin.prompts') }}
                </button>
                <button 
                    class="tab-btn" 
                    :class="{ active: activeTab === 'settings' }"
                    @click="activeTab = 'settings'"
                >
                    {{ t('admin.settings') }}
                </button>
            </div>
            
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
                
                <div v-show="activeTab === 'settings'" class="tab-content">
                    <settings-panel></settings-panel>
                </div>
            </div>
        </div>
    `,
    
    setup() {
        const activeTab = Vue.ref('modules');
        
        const t = (key, params = {}) => {
            return window.gettext ? window.gettext(key, params) : key;
        };
        
        return {
            activeTab,
            t
        };
    }
};

console.log('✅ AdminPanel komponens betöltve');