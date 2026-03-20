// ==============================================
// SOULCORE 3.0 - Modul vezérlő komponens
// ==============================================

window.ModuleControl = {
    name: 'ModuleControl',
    
    template: `
        <div class="module-control">
            <div class="module-list">
                <div 
                    v-for="(status, name) in modules" 
                    :key="name"
                    class="module-item"
                >
                    <div class="module-info">
                        <div class="module-name">
                            <span class="status-dot" :class="status"></span>
                            {{ formatModuleName(name) }}
                        </div>
                        <div class="module-status" :class="status">
                            {{ formatStatus(status) }}
                        </div>
                    </div>
                    
                    <div class="module-actions">
                        <button 
                            v-if="status === 'stopped'"
                            class="btn-icon" 
                            @click="controlModule(name, 'start')"
                            :disabled="loading[name]"
                            :title="t('modules.start')"
                        >
                            ▶️
                        </button>
                        <button 
                            v-else-if="status !== 'error'"
                            class="btn-icon" 
                            @click="controlModule(name, 'stop')"
                            :disabled="loading[name]"
                            :title="t('modules.stop')"
                        >
                            ⏹️
                        </button>
                        <button 
                            v-if="status !== 'stopped'"
                            class="btn-icon" 
                            @click="controlModule(name, 'restart')"
                            :disabled="loading[name]"
                            :title="t('modules.restart')"
                        >
                            🔄
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `,
    
    setup() {
        const modules = Vue.computed(() => window.store.modules);
        const loading = Vue.ref({});
        
        const t = (key, params = {}) => {
            return window.gettext ? window.gettext(key, params) : key;
        };
        
        const formatModuleName = (name) => {
            return name
                .split('_')
                .map(word => word.charAt(0).toUpperCase() + word.slice(1))
                .join(' ');
        };
        
        const formatStatus = (status) => {
            const translations = {
                'running': t('modules.status_running'),
                'ready': t('modules.status_ready'),
                'processing': t('modules.status_processing'),
                'idle': t('modules.status_idle'),
                'error': t('modules.status_error'),
                'stopped': t('modules.status_stopped')
            };
            return translations[status] || status;
        };
        
        const controlModule = async (module, action) => {
            loading.value[module] = true;
            
            try {
                await window.api.controlModule(module, action);
                window.store.addNotification('success', t('modules.action_success', { module, action }));
            } catch (error) {
                console.error('Hiba a modul vezérlésekor:', error);
                window.store.addNotification('error', t('modules.action_error', { error: error.message }));
            } finally {
                loading.value[module] = false;
            }
        };
        
        return {
            modules,
            loading,
            t,
            formatModuleName,
            formatStatus,
            controlModule
        };
    }
};

console.log('✅ ModuleControl komponens betöltve');