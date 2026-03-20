// ==============================================
// SOULCORE 3.0 - Modell választó komponens
// ==============================================

window.ModelSelector = {
    name: 'ModelSelector',
    
    template: `
        <div class="model-selector">
            <!-- Fejléc -->
            <div class="model-header">
                <div class="header-title">
                    <h3>{{ t('models.title') }}</h3>
                    <span class="model-count" v-if="models.length">({{ models.length }})</span>
                </div>
                <div class="header-actions">
                    <input 
                        type="text" 
                        v-model="searchQuery" 
                        :placeholder="t('models.search')"
                        class="search-input"
                    >
                    <select v-model="filterType" class="filter-select">
                        <option value="all">{{ t('models.all') }}</option>
                        <option value="quantized">{{ t('models.quantized') }}</option>
                        <option value="gguf">{{ t('models.gguf') }}</option>
                        <option value="exl2">{{ t('models.exl2') }}</option>
                    </select>
                    <button class="refresh-btn" @click="refreshModels" :disabled="refreshing">
                        <span :class="{ 'spin': refreshing }">🔄</span>
                    </button>
                    <button class="btn-primary" @click="showAddModal = true" v-if="isAdmin">
                        + {{ t('models.add') }}
                    </button>
                </div>
            </div>
            
            <!-- Modell lista -->
            <div class="model-list">
                <div v-for="model in filteredModels" :key="model.id" 
                     class="model-card" 
                     :class="{ 
                         active: currentModel?.id === model.id,
                         'has-warning': model.warning
                     }">
                    
                    <!-- Modell fejléc -->
                    <div class="model-card-header">
                        <div class="model-title">
                            <span class="model-name">{{ model.name }}</span>
                            <span class="model-badge" :class="{ warning: model.warning }">
                                {{ model.quantization || 'Unknown' }}
                            </span>
                        </div>
                        <div class="model-performance" v-if="model.performance">
                            <span class="perf-badge">⚡ {{ model.performance.tokens_per_sec || '?' }} t/s</span>
                            <span class="perf-badge">⏱️ {{ model.performance.load_time || '?' }}s</span>
                        </div>
                    </div>
                    
                    <!-- Modell részletek -->
                    <div class="model-details">
                        <div class="detail-row">
                            <span class="detail-label">{{ t('models.size') }}:</span>
                            <span class="detail-value">{{ model.size || 'Unknown' }}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">{{ t('models.context_length') }}:</span>
                            <span class="detail-value">{{ model.context_length || 4096 }}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">{{ t('models.vram') }}:</span>
                            <span class="detail-value">{{ model.vram_estimate || '?' }} MB</span>
                        </div>
                    </div>
                    
                    <!-- VRAM használat sáv (ha van) -->
                    <div class="vram-bar" v-if="model.vram_percent">
                        <div class="progress-label">
                            <span>{{ t('models.vram_usage') }}</span>
                            <span>{{ model.vram_percent }}%</span>
                        </div>
                        <div class="progress-bar">
                            <div class="progress-fill" 
                                 :class="getVramClass(model.vram_percent)"
                                 :style="{ width: model.vram_percent + '%' }"></div>
                        </div>
                    </div>
                    
                    <!-- Figyelmeztetések -->
                    <div class="model-warnings" v-if="model.warning">
                        <div class="warning-item">⚠️ {{ model.warning }}</div>
                    </div>
                    
                    <!-- Akciók -->
                    <div class="model-actions">
                        <button 
                            v-if="currentModel?.id !== model.id"
                            class="btn-primary" 
                            @click="activateModel(model.id)"
                            :disabled="activating === model.id"
                        >
                            <span v-if="activating !== model.id">{{ t('models.activate') }}</span>
                            <span v-else class="spinner-small"></span>
                        </button>
                        <span v-else class="active-badge">✓ {{ t('models.active') }}</span>
                        
                        <button 
                            v-if="isAdmin"
                            class="btn-secondary" 
                            @click="deleteModel(model.id)"
                            :disabled="deleting === model.id"
                        >
                            <span v-if="deleting !== model.id">🗑️ {{ t('models.delete') }}</span>
                            <span v-else class="spinner-small"></span>
                        </button>
                    </div>
                    
                    <!-- Modell útvonal (admin) -->
                    <div class="model-path" v-if="isAdmin && model.path">
                        📁 {{ model.path }}
                    </div>
                </div>
                
                <!-- Nincs találat -->
                <div v-if="filteredModels.length === 0" class="empty-list">
                    <div class="empty-icon">🔍</div>
                    <div class="empty-text">{{ t('models.no_models') }}</div>
                    <button class="btn-primary" @click="showAddModal = true" v-if="isAdmin">
                        + {{ t('models.add_first') }}
                    </button>
                </div>
            </div>
            
            <!-- Modell hozzáadása modal -->
            <div class="modal" v-if="showAddModal" @click.self="showAddModal = false">
                <div class="modal-content">
                    <div class="modal-header">
                        <h3>{{ t('models.add_model') }}</h3>
                        <button class="close-btn" @click="showAddModal = false">✕</button>
                    </div>
                    <div class="modal-body">
                        <div class="form-group">
                            <label>{{ t('models.model_path') }}</label>
                            <input type="text" v-model="newModel.path" class="form-input" 
                                   :placeholder="t('models.path_placeholder')">
                        </div>
                        <div class="form-group">
                            <label>{{ t('models.model_name') }}</label>
                            <input type="text" v-model="newModel.name" class="form-input" 
                                   :placeholder="t('models.name_placeholder')">
                        </div>
                        <div class="form-row">
                            <div class="form-group half">
                                <label>{{ t('models.quantization') }}</label>
                                <input type="text" v-model="newModel.quantization" class="form-input" 
                                       placeholder="Q4_K_M">
                            </div>
                            <div class="form-group half">
                                <label>{{ t('models.context_length') }}</label>
                                <input type="number" v-model="newModel.context_length" class="form-input" 
                                       placeholder="4096">
                            </div>
                        </div>
                        <div class="form-row">
                            <div class="form-group half">
                                <label>{{ t('models.n_gpu_layers') }}</label>
                                <input type="number" v-model="newModel.n_gpu_layers" class="form-input" 
                                       placeholder="-1 (all)">
                            </div>
                            <div class="form-group half">
                                <label>{{ t('models.description') }}</label>
                                <input type="text" v-model="newModel.description" class="form-input" 
                                       :placeholder="t('models.description_placeholder')">
                            </div>
                        </div>
                        
                        <!-- Scannelt modellek lista -->
                        <div class="scanned-models" v-if="scannedModels.length">
                            <h4>{{ t('models.scanned_models') }}</h4>
                            <div class="scanned-list">
                                <div v-for="scanned in scannedModels" :key="scanned.path" 
                                     class="scanned-item" @click="selectScannedModel(scanned)">
                                    <div class="scanned-info">
                                        <span class="scanned-name">{{ scanned.name }}</span>
                                        <span class="model-size">{{ scanned.size }}</span>
                                    </div>
                                    <button class="btn-sm btn-secondary">+ {{ t('models.select') }}</button>
                                </div>
                            </div>
                        </div>
                        
                        <div v-if="addError" class="auth-error">{{ addError }}</div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn-secondary" @click="showAddModal = false">
                            {{ t('ui.cancel') }}
                        </button>
                        <button class="btn-primary" @click="addModel" :disabled="adding">
                            <span v-if="!adding">{{ t('models.add') }}</span>
                            <span v-else class="spinner-small"></span>
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
        
        const models = Vue.computed(() => window.store.models);
        const isAdmin = Vue.computed(() => window.store.user?.role === 'admin');
        
        // UI állapotok
        const searchQuery = Vue.ref('');
        const filterType = Vue.ref('all');
        const refreshing = Vue.ref(false);
        const activating = Vue.ref(null);
        const deleting = Vue.ref(null);
        
        // Modál
        const showAddModal = Vue.ref(false);
        const adding = Vue.ref(false);
        const addError = Vue.ref('');
        
        // Új modell adatok
        const newModel = Vue.ref({
            path: '',
            name: '',
            quantization: '',
            context_length: 4096,
            n_gpu_layers: -1,
            description: ''
        });
        
        // Scannelt modellek
        const scannedModels = Vue.ref([]);
        
        // ====================================================================
        // COMPUTED PROPERTIES
        // ====================================================================
        
        const currentModel = Vue.computed(() => {
            return models.value.find(m => m.is_active);
        });
        
        const filteredModels = Vue.computed(() => {
            let filtered = [...models.value];
            
            // Keresés
            if (searchQuery.value) {
                const query = searchQuery.value.toLowerCase();
                filtered = filtered.filter(m => 
                    m.name?.toLowerCase().includes(query) ||
                    m.description?.toLowerCase().includes(query)
                );
            }
            
            // Szűrés típus szerint
            if (filterType.value !== 'all') {
                filtered = filtered.filter(m => {
                    if (filterType.value === 'quantized') {
                        return m.quantization && m.quantization !== 'Unknown';
                    }
                    if (filterType.value === 'gguf') {
                        return m.path?.toLowerCase().endsWith('.gguf');
                    }
                    if (filterType.value === 'exl2') {
                        return m.path?.toLowerCase().includes('exl2');
                    }
                    return true;
                });
            }
            
            return filtered;
        });
        
        // ====================================================================
        // SEGÉDFÜGGVÉNYEK
        // ====================================================================
        
        const t = (key, params = {}) => window.gettext(key, params);
        
        const getVramClass = (percent) => {
            if (percent < 70) return '';
            if (percent < 85) return 'warning';
            return 'critical';
        };
        
        /**
         * Modellek betöltése
         */
        const loadModels = async () => {
            try {
                await window.api.getModels();
            } catch (error) {
                console.error('Error loading models:', error);
                window.store.addNotification('error', t('models.load_error'));
            }
        };
        
        /**
         * Modellek frissítése
         */
        const refreshModels = async () => {
            refreshing.value = true;
            try {
                await loadModels();
                window.store.addNotification('success', t('models.refreshed'));
            } catch (error) {
                console.error('Error refreshing models:', error);
                window.store.addNotification('error', t('models.refresh_error'));
            } finally {
                refreshing.value = false;
            }
        };
        
        /**
         * Modell aktiválása
         */
        const activateModel = async (id) => {
            activating.value = id;
            try {
                await window.api.activateModel(id);
                window.store.addNotification('success', t('models.activated'));
                await loadModels();
            } catch (error) {
                console.error('Error activating model:', error);
                window.store.addNotification('error', t('models.activate_error'));
            } finally {
                activating.value = null;
            }
        };
        
        /**
         * Modell törlése
         */
        const deleteModel = async (id) => {
            const model = models.value.find(m => m.id === id);
            if (!model) return;
            
            if (!confirm(t('models.confirm_delete', { name: model.name }))) return;
            
            deleting.value = id;
            try {
                await window.api.deleteModel(id);
                window.store.addNotification('success', t('models.deleted'));
                await loadModels();
            } catch (error) {
                console.error('Error deleting model:', error);
                window.store.addNotification('error', t('models.delete_error'));
            } finally {
                deleting.value = null;
            }
        };
        
        /**
         * Modellek szkennelése a /models mappában
         */
        const scanModels = async () => {
            try {
                // Itt lehetne valós szkennelés
                scannedModels.value = [
                    { path: '/models/gemma-27b.Q4_K_M.gguf', name: 'Gemma 27B Q4_K_M', size: '15.2 GB' },
                    { path: '/models/llama-3-8b.Q4_K_M.gguf', name: 'Llama 3 8B Q4_K_M', size: '4.8 GB' },
                    { path: '/models/qwen-2.5-7b.Q4_K_M.gguf', name: 'Qwen 2.5 7B Q4_K_M', size: '4.2 GB' }
                ];
            } catch (error) {
                console.error('Error scanning models:', error);
            }
        };
        
        /**
         * Scannelt modell kiválasztása
         */
        const selectScannedModel = (scanned) => {
            newModel.value.path = scanned.path;
            newModel.value.name = scanned.name;
            // Automatikus kvantálás felismerés a fájlnévből
            const match = scanned.path.match(/Q\d_[KKA-Z]+/i);
            if (match) {
                newModel.value.quantization = match[0];
            }
            showAddModal.value = true;
        };
        
        /**
         * Modell hozzáadása
         */
        const addModel = async () => {
            if (!newModel.value.path) {
                addError.value = t('models.error_path_required');
                return;
            }
            if (!newModel.value.name) {
                newModel.value.name = newModel.value.path.split('/').pop().replace(/\.gguf$/, '');
            }
            
            adding.value = true;
            addError.value = '';
            
            try {
                await window.api.addModel(newModel.value);
                window.store.addNotification('success', t('models.added'));
                showAddModal.value = false;
                newModel.value = {
                    path: '',
                    name: '',
                    quantization: '',
                    context_length: 4096,
                    n_gpu_layers: -1,
                    description: ''
                };
                await loadModels();
            } catch (error) {
                console.error('Error adding model:', error);
                addError.value = error.message || t('models.add_error');
            } finally {
                adding.value = false;
            }
        };
        
        // ====================================================================
        // ÉLETCIKLUS
        // ====================================================================
        
        Vue.onMounted(() => {
            loadModels();
            scanModels();
        });
        
        // ====================================================================
        // RETURN
        // ====================================================================
        
        return {
            // Állapotok
            models,
            currentModel,
            isAdmin,
            searchQuery,
            filterType,
            refreshing,
            activating,
            deleting,
            filteredModels,
            
            // Modál
            showAddModal,
            adding,
            addError,
            newModel,
            scannedModels,
            
            // Segédfüggvények
            t,
            getVramClass,
            
            // Metódusok
            refreshModels,
            activateModel,
            deleteModel,
            selectScannedModel,
            addModel
        };
    }
};

console.log('✅ ModelSelector komponens betöltve');