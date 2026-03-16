// Modell választó és kezelő komponens
const ModelSelector = {
    template: `
        <div class="model-selector">
            <div class="model-header">
                <h3>Elérhető modellek</h3>
                <button class="btn-primary" @click="scanModels" :disabled="loading">
                    <span v-if="!loading">🔍 Mappa átvizsgálása</span>
                    <span v-else>Keresés...</span>
                </button>
            </div>
            
            <div class="model-list">
                <div v-for="model in models" :key="model.id" class="model-card" 
                     :class="{ active: model.is_active }">
                    
                    <div class="model-card-header">
                        <span class="model-name">{{ model.name }}</span>
                        <span class="model-badge" v-if="model.is_active">Aktív</span>
                    </div>
                    
                    <div class="model-details">
                        <div class="model-detail">
                            <span class="detail-label">Méret:</span>
                            <span class="detail-value">{{ model.size || '?' }}</span>
                        </div>
                        <div class="model-detail">
                            <span class="detail-label">Kvantálás:</span>
                            <span class="detail-value">{{ model.quantization || '?' }}</span>
                        </div>
                        <div class="model-detail">
                            <span class="detail-label">Kontextus:</span>
                            <span class="detail-value">{{ model.n_ctx || 4096 }} token</span>
                        </div>
                        <div class="model-detail">
                            <span class="detail-label">GPU rétegek:</span>
                            <span class="detail-value">{{ model.n_gpu_layers == -1 ? 'Összes' : model.n_gpu_layers }}</span>
                        </div>
                    </div>
                    
                    <div class="model-actions" v-if="isAdmin">
                        <button class="control-btn" @click="activateModel(model.id)" 
                                v-if="!model.is_active" :disabled="loading">
                            Aktiválás
                        </button>
                        <button class="control-btn stop" @click="deleteModel(model.id)" 
                                v-if="!model.is_active" :disabled="loading">
                            Törlés
                        </button>
                    </div>
                    
                    <div class="model-path" :title="model.path">
                        {{ model.path }}
                    </div>
                </div>
                
                <div v-if="models.length === 0" class="empty-list">
                    Nincs még modell hozzáadva
                </div>
            </div>
            
            <!-- Új modell hozzáadása modal -->
            <div class="modal" v-if="showAddModal">
                <div class="modal-content">
                    <div class="modal-header">
                        <h3>Új modell hozzáadása</h3>
                        <button class="close-btn" @click="showAddModal = false">✕</button>
                    </div>
                    
                    <div class="modal-body">
                        <div v-if="scannedModels.length > 0" class="scanned-models">
                            <h4>Talált modellek:</h4>
                            <div v-for="m in scannedModels" :key="m.path" class="scanned-item">
                                <span>{{ m.name }}</span>
                                <span class="model-size">{{ m.size }}</span>
                                <button class="control-btn" @click="addFromScan(m)">Hozzáadás</button>
                            </div>
                        </div>
                        
                        <div class="form-group">
                            <label>Modell neve</label>
                            <input type="text" v-model="newModel.name" class="form-input">
                        </div>
                        
                        <div class="form-group">
                            <label>Fájl elérési út</label>
                            <input type="text" v-model="newModel.path" class="form-input">
                        </div>
                        
                        <div class="form-row">
                            <div class="form-group half">
                                <label>Kvantálás</label>
                                <input type="text" v-model="newModel.quantization" class="form-input">
                            </div>
                            <div class="form-group half">
                                <label>Méret</label>
                                <input type="text" v-model="newModel.size" class="form-input">
                            </div>
                        </div>
                        
                        <div class="form-row">
                            <div class="form-group half">
                                <label>Kontextus (token)</label>
                                <input type="number" v-model="newModel.n_ctx" class="form-input" value="4096">
                            </div>
                            <div class="form-group half">
                                <label>GPU rétegek</label>
                                <input type="number" v-model="newModel.n_gpu_layers" class="form-input" value="-1">
                            </div>
                        </div>
                        
                        <div class="form-group">
                            <label>Leírás</label>
                            <textarea v-model="newModel.description" class="form-input" rows="2"></textarea>
                        </div>
                    </div>
                    
                    <div class="modal-footer">
                        <button class="btn-secondary" @click="showAddModal = false">Mégse</button>
                        <button class="btn-primary" @click="addModel" :disabled="!newModel.name || !newModel.path">
                            Hozzáadás
                        </button>
                    </div>
                </div>
            </div>
            
            <button class="btn-secondary add-model-btn" @click="showAddModal = true" v-if="isAdmin">
                + Modell hozzáadása
            </button>
        </div>
    `,
    
    setup() {
        const models = Vue.computed(() => store.models);
        const isAdmin = Vue.computed(() => store.isAdmin);
        const loading = Vue.ref(false);
        const showAddModal = Vue.ref(false);
        const scannedModels = Vue.ref([]);
        
        const newModel = Vue.ref({
            name: '',
            path: '',
            size: '',
            quantization: '',
            n_ctx: 4096,
            n_gpu_layers: -1,
            description: ''
        });
        
        const scanModels = async () => {
            loading.value = true;
            try {
                const folder = prompt('Mappa elérési útja:', 'models');
                if (folder) {
                    const result = await api.fetch('/api/models/scan', {
                        method: 'POST',
                        body: JSON.stringify({ folder })
                    });
                    scannedModels.value = result.models || [];
                    showAddModal.value = true;
                }
            } catch (error) {
                alert('Hiba a mappa átvizsgálása közben: ' + error.message);
            } finally {
                loading.value = false;
            }
        };
        
        const addFromScan = (model) => {
            newModel.value = {
                name: model.name,
                path: model.path,
                size: model.size,
                quantization: '',
                n_ctx: 4096,
                n_gpu_layers: -1,
                description: ''
            };
        };
        
        const addModel = async () => {
            loading.value = true;
            try {
                await api.addModel(newModel.value);
                showAddModal.value = false;
                newModel.value = {
                    name: '', path: '', size: '', quantization: '',
                    n_ctx: 4096, n_gpu_layers: -1, description: ''
                };
                api.getModels();
            } catch (error) {
                alert('Hiba a modell hozzáadásakor: ' + error.message);
            } finally {
                loading.value = false;
            }
        };
        
        const activateModel = async (id) => {
            if (confirm('Biztosan aktiválod ezt a modellt? A King újratöltődik.')) {
                loading.value = true;
                try {
                    await api.activateModel(id);
                    api.getModels();
                } catch (error) {
                    alert('Hiba a modell aktiválásakor: ' + error.message);
                } finally {
                    loading.value = false;
                }
            }
        };
        
        const deleteModel = async (id) => {
            if (confirm('Biztosan törlöd ezt a modellt?')) {
                loading.value = true;
                try {
                    await api.deleteModel(id);
                    api.getModels();
                } catch (error) {
                    alert('Hiba a modell törlésekor: ' + error.message);
                } finally {
                    loading.value = false;
                }
            }
        };
        
        return {
            models,
            isAdmin,
            loading,
            showAddModal,
            scannedModels,
            newModel,
            scanModels,
            addFromScan,
            addModel,
            activateModel,
            deleteModel
        };
    }
};

window.ModelSelector = ModelSelector;
