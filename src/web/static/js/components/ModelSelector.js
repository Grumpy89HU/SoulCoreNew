// ==============================================
// SOULCORE 3.0 - Modell választó komponens
// ==============================================

window.ModelSelector = {
    name: 'ModelSelector',
    
    template: `
        <div class="model-selector">
            <div class="model-list">
                <div 
                    v-for="model in models" 
                    :key="model.id"
                    class="model-item"
                    :class="{ active: currentModel?.id === model.id }"
                >
                    <div class="model-info">
                        <div class="model-name">{{ model.name }}</div>
                        <div class="model-details">
                            <span>{{ model.quantization || 'Unknown' }}</span>
                            <span>{{ model.size || 'Unknown' }}</span>
                        </div>
                    </div>
                    
                    <button 
                        v-if="currentModel?.id !== model.id"
                        class="btn btn-primary btn-sm" 
                        @click="activateModel(model.id)"
                        :disabled="activating === model.id"
                    >
                        <span v-if="activating !== model.id">{{ t('models.activate') }}</span>
                        <span v-else class="spinner-small"></span>
                    </button>
                    <span v-else class="badge badge-success">{{ t('models.active') }}</span>
                </div>
            </div>
        </div>
    `,
    
    setup() {
        const models = Vue.computed(() => window.store.models);
        const currentModel = Vue.computed(() => window.store.currentModel);
        const activating = Vue.ref(null);
        
        const t = (key, params = {}) => {
            return window.gettext ? window.gettext(key, params) : key;
        };
        
        const loadModels = async () => {
            try {
                await window.api.getModels();
            } catch (error) {
                console.error('Hiba a modellek betöltésekor:', error);
            }
        };
        
        const activateModel = async (id) => {
            activating.value = id;
            try {
                await window.api.activateModel(id);
                window.store.addNotification('success', t('models.activated'));
            } catch (error) {
                console.error('Hiba a modell aktiválásakor:', error);
                window.store.addNotification('error', t('models.activate_error'));
            } finally {
                activating.value = null;
            }
        };
        
        Vue.onMounted(() => {
            loadModels();
        });
        
        return {
            models,
            currentModel,
            activating,
            t,
            activateModel
        };
    }
};

console.log('✅ ModelSelector komponens betöltve');