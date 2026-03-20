// Modell választó és kezelő komponens
window.ModelSelector = {
    template: `
        <div class="model-selector">
            <!-- Fejléc keresővel és szűrőkkel -->
            <div class="model-header">
                <div class="header-title">
                    <h3>{{ gettext('models.available') }}</h3>
                    <span class="model-count" v-if="filteredModels.length">({{ filteredModels.length }})</span>
                </div>
                
                <div class="header-actions">
                    <button class="btn-primary" @click="scanModels" :disabled="loading">
                        <span v-if="!loading">🔍 {{ gettext('models.scan') }}</span>
                        <span v-else class="loading-text">⏳ {{ gettext('models.scanning') }}</span>
                    </button>
                </div>
            </div>
            
            <!-- Keresés és szűrés -->
            <div class="model-filters">
                <input 
                    type="text" 
                    v-model="searchQuery" 
                    :placeholder="gettext('models.search')"
                    class="search-input"
                >
                
                <select v-model="filterType" class="filter-select">
                    <option value="all">{{ gettext('models.all') }}</option>
                    <option value="active">{{ gettext('models.active_only') }}</option>
                    <option value="inactive">{{ gettext('models.inactive_only') }}</option>
                </select>
                
                <select v-model="sortBy" class="sort-select">
                    <option value="name">{{ gettext('models.sort_name') }}</option>
                    <option value="size">{{ gettext('models.sort_size') }}</option>
                    <option value="date">{{ gettext('models.sort_date') }}</option>
                </select>
            </div>
            
            <!-- Modell lista -->
            <div class="model-list">
                <div v-for="model in filteredAndSortedModels" :key="model.id" 
                     class="model-card" 
                     :class="{ 
                         active: model.is_active,
                         'has-warning': model.warnings && model.warnings.length
                     }">
                    
                    <!-- Modell fejléc -->
                    <div class="model-card-header">
                        <div class="model-title">
                            <span class="model-name">{{ model.name }}</span>
                            <span class="model-badge" v-if="model.is_active">{{ gettext('models.active') }}</span>
                            <span class="model-badge warning" v-if="model.warnings && model.warnings.length">⚠️</span>
                        </div>
                        
                        <!-- Teljesítmény indikátorok -->
                        <div class="model-performance" v-if="model.stats">
                            <span class="perf-badge" :title="gettext('models.speed')">
                                ⚡ {{ formatSpeed(model.stats.average_speed) }}
                            </span>
                            <span class="perf-badge" :title="gettext('models.usage')">
                                🔤 {{ model.stats.inference_count || 0 }}
                            </span>
                        </div>
                    </div>
                    
                    <!-- Modell részletek -->
                    <div class="model-details">
                        <div class="detail-grid">
                            <div class="detail-item">
                                <span class="detail-label">{{ gettext('models.size') }}:</span>
                                <span class="detail-value">{{ formatSize(model) }}</span>
                            </div>
                            
                            <div class="detail-item">
                                <span class="detail-label">{{ gettext('models.quantization') }}:</span>
                                <span class="detail-value">{{ model.quantization || '?' }}</span>
                            </div>
                            
                            <div class="detail-item">
                                <span class="detail-label">{{ gettext('models.context') }}:</span>
                                <span class="detail-value">{{ model.n_ctx || 4096 }} tk</span>
                            </div>
                            
                            <div class="detail-item">
                                <span class="detail-label">{{ gettext('models.gpu_layers') }}:</span>
                                <span class="detail-value">{{ formatGPULayers(model.n_gpu_layers) }}</span>
                            </div>
                            
                            <div class="detail-item" v-if="model.vram_estimate">
                                <span class="detail-label">{{ gettext('models.vram') }}:</span>
                                <span class="detail-value">{{ formatBytes(model.vram_estimate) }}</span>
                            </div>
                            
                            <div class="detail-item" v-if="model.ram_estimate">
                                <span class="detail-label">{{ gettext('models.ram') }}:</span>
                                <span class="detail-value">{{ formatBytes(model.ram_estimate) }}</span>
                            </div>
                        </div>
                        
                        <!-- Progress bar VRAM (ha van adat) -->
                        <div class="vram-bar" v-if="model.vram_percent">
                            <div class="progress-label">
                                <span>{{ gettext('models.vram_usage') }}</span>
                                <span>{{ model.vram_percent }}%</span>
                            </div>
                            <div class="progress-bar">
                                <div class="progress-fill" 
                                     :style="{ width: model.vram_percent + '%' }"
                                     :class="{ 
                                         'warning': model.vram_percent > 80,
                                         'critical': model.vram_percent > 95
                                     }">
                                </div>
                            </div>
                        </div>
                        
                        <!-- Figyelmeztetések -->
                        <div v-if="model.warnings && model.warnings.length" class="model-warnings">
                            <div v-for="warning in model.warnings" class="warning-item">
                                ⚠️ {{ warning }}
                            </div>
                        </div>
                    </div>
                    
                    <!-- Modell akciók -->
                    <div class="model-actions" v-if="isAdmin">
                        <div class="action-group">
                            <button class="control-btn" @click="activateModel(model.id)" 
                                    v-if="!model.is_active" :disabled="loading">
                                {{ gettext('models.activate') }}
                            </button>
                            
                            <button class="control-btn" @click="testModel(model.id)" 
                                    v-if="model.is_active" :disabled="loading">
                                🧪 {{ gettext('models.test') }}
                            </button>
                            
                            <button class="control-btn" @click="editModel(model)" 
                                    v-if="!model.is_active" :disabled="loading">
                                ✏️ {{ gettext('models.edit') }}
                            </button>
                            
                            <button class="control-btn stop" @click="deleteModel(model.id)" 
                                    v-if="!model.is_active" :disabled="loading">
                                🗑️ {{ gettext('models.delete') }}
                            </button>
                        </div>
                        
                        <!-- Teljesítmény metrikák (ha van) -->
                        <div class="model-stats" v-if="model.stats">
                            <div class="stat" :title="gettext('models.last_used')">
                                🕒 {{ formatTimeAgo(model.stats.last_inference) }}
                            </div>
                            <div class="stat" :title="gettext('models.total_tokens')">
                                🔤 {{ formatNumber(model.stats.total_tokens || 0) }}
                            </div>
                        </div>
                    </div>
                    
                    <!-- Modell elérési út (tooltip) -->
                    <div class="model-path" :title="model.path">
                        📁 {{ truncatePath(model.path) }}
                    </div>
                </div>
                
                <div v-if="filteredModels.length === 0" class="empty-list">
                    <div class="empty-icon">🤔</div>
                    <div class="empty-text">{{ gettext('models.no_models') }}</div>
                    <button class="btn-primary" @click="showAddModal = true" v-if="isAdmin">
                        + {{ gettext('models.add_first') }}
                    </button>
                </div>
            </div>
            
            <!-- Új modell hozzáadása modal -->
            <div class="modal" v-if="showAddModal">
                <div class="modal-content large">
                    <div class="modal-header">
                        <h3>{{ editingModel ? gettext('models.edit') : gettext('models.add') }}</h3>
                        <button class="close-btn" @click="closeModal">✕</button>
                    </div>
                    
                    <div class="modal-body">
                        <!-- Talált modellek (ha van scan) -->
                        <div v-if="scannedModels.length > 0 && !editingModel" class="scanned-models">
                            <h4>{{ gettext('models.found') }}</h4>
                            <div class="scanned-list">
                                <div v-for="m in scannedModels" :key="m.path" class="scanned-item">
                                    <div class="scanned-info">
                                        <span class="scanned-name">{{ m.name }}</span>
                                        <span class="scanned-size">{{ m.size }}</span>
                                    </div>
                                    <button class="control-btn" @click="addFromScan(m)">
                                        {{ gettext('models.add') }}
                                    </button>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Modell adatok űrlap -->
                        <form @submit.prevent="saveModel" class="model-form">
                            <div class="form-group">
                                <label>{{ gettext('models.name') }} *</label>
                                <input type="text" v-model="formData.name" class="form-input" required>
                            </div>
                            
                            <div class="form-group">
                                <label>{{ gettext('models.path') }} *</label>
                                <input type="text" v-model="formData.path" class="form-input" required>
                                <small class="form-help">{{ gettext('models.path_help') }}</small>
                            </div>
                            
                            <div class="form-row">
                                <div class="form-group half">
                                    <label>{{ gettext('models.quantization') }}</label>
                                    <input type="text" v-model="formData.quantization" class="form-input">
                                </div>
                                
                                <div class="form-group half">
                                    <label>{{ gettext('models.size') }}</label>
                                    <input type="text" v-model="formData.size" class="form-input">
                                </div>
                            </div>
                            
                            <div class="form-row">
                                <div class="form-group half">
                                    <label>{{ gettext('models.context') }}</label>
                                    <input type="number" v-model.number="formData.n_ctx" class="form-input" min="512" max="32768" step="512">
                                </div>
                                
                                <div class="form-group half">
                                    <label>{{ gettext('models.gpu_layers') }}</label>
                                    <input type="number" v-model.number="formData.n_gpu_layers" class="form-input" min="-1" max="200">
                                </div>
                            </div>
                            
                            <div class="form-group">
                                <label>{{ gettext('models.description') }}</label>
                                <textarea v-model="formData.description" class="form-input" rows="2"></textarea>
                            </div>
                        </form>
                    </div>
                    
                    <div class="modal-footer">
                        <button class="btn-secondary" @click="closeModal">
                            {{ gettext('ui.cancel') }}
                        </button>
                        <button class="btn-primary" @click="saveModel" :disabled="!isFormValid">
                            <span v-if="!saving">{{ editingModel ? gettext('ui.save') : gettext('models.add') }}</span>
                            <span v-else>⏳ {{ gettext('ui.saving') }}</span>
                        </button>
                    </div>
                </div>
            </div>
            
            <!-- Gyors akció gomb (adminoknak) -->
            <button class="fab" @click="showAddModal = true" v-if="isAdmin" :title="gettext('models.add')">
                +
            </button>
        </div>
    `,
    
    setup() {
        // ====================================================================
        // REAKTÍV ÁLLAPOTOK
        // ====================================================================
        
        const models = Vue.computed(() => window.store?.models || []);
        const isAdmin = Vue.computed(() => window.store?.isAdmin || false);
        
        // UI állapotok
        const loading = Vue.ref(false);
        const saving = Vue.ref(false);
        const showAddModal = Vue.ref(false);
        const editingModel = Vue.ref(null);
        const scannedModels = Vue.ref([]);
        
        // Keresés és szűrés
        const searchQuery = Vue.ref('');
        const filterType = Vue.ref('all');
        const sortBy = Vue.ref('name');
        
        // Űrlap adatok
        const formData = Vue.ref({
            name: '',
            path: '',
            size: '',
            quantization: '',
            n_ctx: 4096,
            n_gpu_layers: -1,
            description: ''
        });
        
        // ====================================================================
        // COMPUTED PROPERTIES
        // ====================================================================
        
        // Szűrt modellek
        const filteredModels = Vue.computed(() => {
            let filtered = models.value;
            
            // Keresés
            if (searchQuery.value) {
                const query = searchQuery.value.toLowerCase();
                filtered = filtered.filter(m => 
                    m.name?.toLowerCase().includes(query) ||
                    m.path?.toLowerCase().includes(query) ||
                    m.quantization?.toLowerCase().includes(query)
                );
            }
            
            // Szűrés típus szerint
            if (filterType.value === 'active') {
                filtered = filtered.filter(m => m.is_active);
            } else if (filterType.value === 'inactive') {
                filtered = filtered.filter(m => !m.is_active);
            }
            
            return filtered;
        });
        
        // Rendezett modellek
        const filteredAndSortedModels = Vue.computed(() => {
            const sorted = [...filteredModels.value];
            
            switch (sortBy.value) {
                case 'name':
                    sorted.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
                    break;
                case 'size':
                    sorted.sort((a, b) => {
                        const aSize = parseSize(a.size);
                        const bSize = parseSize(b.size);
                        return bSize - aSize;
                    });
                    break;
                case 'date':
                    sorted.sort((a, b) => (b.created_at || 0) - (a.created_at || 0));
                    break;
            }
            
            return sorted;
        });
        
        // Űrlap validáció
        const isFormValid = Vue.computed(() => {
            return formData.value.name?.trim() && formData.value.path?.trim();
        });
        
        // ====================================================================
        // METÓDUSOK
        // ====================================================================
        
        // Modell lista frissítése
        const refreshModels = async () => {
            if (window.api) {
                await window.api.getModels();
            }
        };
        
        // Mappa átvizsgálása
        const scanModels = async () => {
            const folder = prompt(gettext('models.enter_path'), 'models');
            if (!folder) return;
            
            loading.value = true;
            try {
                const result = await window.api.fetch('/api/models/scan', {
                    method: 'POST',
                    body: JSON.stringify({ folder })
                });
                
                scannedModels.value = result.models || [];
                if (scannedModels.value.length) {
                    showAddModal.value = true;
                } else {
                    alert(gettext('models.no_models_found'));
                }
            } catch (error) {
                alert(gettext('models.scan_error', { error: error.message }));
            } finally {
                loading.value = false;
            }
        };
        
        // Modell hozzáadása scan-ből
        const addFromScan = (model) => {
            formData.value = {
                name: model.name,
                path: model.path,
                size: model.size,
                quantization: '',
                n_ctx: 4096,
                n_gpu_layers: -1,
                description: ''
            };
            scannedModels.value = [];
        };
        
        // Modell szerkesztése
        const editModel = (model) => {
            editingModel.value = model;
            formData.value = {
                name: model.name,
                path: model.path,
                size: model.size || '',
                quantization: model.quantization || '',
                n_ctx: model.n_ctx || 4096,
                n_gpu_layers: model.n_gpu_layers || -1,
                description: model.description || ''
            };
            showAddModal.value = true;
        };
        
        // Modell mentése
        const saveModel = async () => {
            if (!isFormValid.value) return;
            
            saving.value = true;
            try {
                if (editingModel.value) {
                    // Frissítés
                    await window.api.fetch(`/api/models/${editingModel.value.id}`, {
                        method: 'PUT',
                        body: JSON.stringify(formData.value)
                    });
                } else {
                    // Új modell
                    await window.api.addModel(formData.value);
                }
                
                closeModal();
                await refreshModels();
                
                window.socketManager?.addSystemMessage?.(
                    editingModel.value ? gettext('models.updated') : gettext('models.added'),
                    'success'
                );
            } catch (error) {
                alert(gettext('models.save_error', { error: error.message }));
            } finally {
                saving.value = false;
            }
        };
        
        // Modell aktiválása
        const activateModel = async (id) => {
            const model = models.value.find(m => m.id === id);
            const message = gettext('models.confirm_activate', { name: model?.name });
            
            if (!confirm(message)) return;
            
            loading.value = true;
            try {
                await window.api.activateModel(id);
                await refreshModels();
                
                window.socketManager?.addSystemMessage?.(
                    gettext('models.activated', { name: model?.name }),
                    'success'
                );
            } catch (error) {
                alert(gettext('models.activate_error', { error: error.message }));
            } finally {
                loading.value = false;
            }
        };
        
        // Modell törlése
        const deleteModel = async (id) => {
            const model = models.value.find(m => m.id === id);
            const message = gettext('models.confirm_delete', { name: model?.name });
            
            if (!confirm(message)) return;
            
            loading.value = true;
            try {
                await window.api.deleteModel(id);
                await refreshModels();
                
                window.socketManager?.addSystemMessage?.(
                    gettext('models.deleted', { name: model?.name }),
                    'success'
                );
            } catch (error) {
                alert(gettext('models.delete_error', { error: error.message }));
            } finally {
                loading.value = false;
            }
        };
        
        // Modell tesztelése
        const testModel = async (id) => {
            const model = models.value.find(m => m.id === id);
            
            loading.value = true;
            try {
                const result = await window.api.fetch('/api/models/test', {
                    method: 'POST',
                    body: JSON.stringify({ id })
                });
                
                if (result.success) {
                    window.socketManager?.addSystemMessage?.(
                        gettext('models.test_success', { name: model?.name }),
                        'success'
                    );
                }
            } catch (error) {
                alert(gettext('models.test_error', { error: error.message }));
            } finally {
                loading.value = false;
            }
        };
        
        // Modal bezárása
        const closeModal = () => {
            showAddModal.value = false;
            editingModel.value = null;
            scannedModels.value = [];
            formData.value = {
                name: '',
                path: '',
                size: '',
                quantization: '',
                n_ctx: 4096,
                n_gpu_layers: -1,
                description: ''
            };
        };
        
        // ====================================================================
        // SEGÉDFÜGGVÉNYEK
        // ====================================================================
        
        const gettext = (key, params = {}) => {
            return window.gettext ? window.gettext(key, params) : key;
        };
        
        const formatSize = (model) => {
            if (model.size) return model.size;
            
            if (model.vram_estimate) {
                return formatBytes(model.vram_estimate);
            }
            
            return '?';
        };
        
        const formatBytes = (bytes) => {
            if (!bytes) return '?';
            
            const units = ['B', 'KB', 'MB', 'GB', 'TB'];
            let size = bytes;
            let unitIndex = 0;
            
            while (size >= 1024 && unitIndex < units.length - 1) {
                size /= 1024;
                unitIndex++;
            }
            
            return `${size.toFixed(1)} ${units[unitIndex]}`;
        };
        
        const formatGPULayers = (layers) => {
            if (layers === -1) return gettext('models.all_gpu');
            if (layers === 0) return gettext('models.cpu_only');
            return `${layers} ${gettext('models.layers')}`;
        };
        
        const formatSpeed = (speed) => {
            if (!speed) return '? tk/s';
            return `${speed.toFixed(1)} tk/s`;
        };
        
        const formatNumber = (num) => {
            return num.toLocaleString();
        };
        
        const formatTimeAgo = (timestamp) => {
            if (!timestamp) return gettext('time.never');
            
            const seconds = Math.floor((Date.now() / 1000) - timestamp);
            
            if (seconds < 60) return gettext('time.just_now');
            if (seconds < 3600) return `${Math.floor(seconds / 60)} ${gettext('time.min_ago')}`;
            if (seconds < 86400) return `${Math.floor(seconds / 3600)} ${gettext('time.hours_ago')}`;
            
            return new Date(timestamp * 1000).toLocaleDateString();
        };
        
        const truncatePath = (path) => {
            if (!path) return '';
            if (path.length <= 40) return path;
            
            const parts = path.split('/');
            if (parts.length > 3) {
                return '.../' + parts.slice(-3).join('/');
            }
            return path;
        };
        
        const parseSize = (sizeStr) => {
            if (!sizeStr) return 0;
            
            const match = sizeStr.match(/^([\d.]+)\s*([GMK]B?)?$/i);
            if (!match) return 0;
            
            const value = parseFloat(match[1]);
            const unit = (match[2] || '').toUpperCase();
            
            if (unit.startsWith('G')) return value * 1024 * 1024 * 1024;
            if (unit.startsWith('M')) return value * 1024 * 1024;
            if (unit.startsWith('K')) return value * 1024;
            
            return value;
        };
        
        // ====================================================================
        // WATCHEREK
        // ====================================================================
        
        // Modell lista frissítése induláskor
        Vue.onMounted(refreshModels);
        
        return {
            // Állapotok
            models,
            isAdmin,
            loading,
            saving,
            showAddModal,
            editingModel,
            scannedModels,
            searchQuery,
            filterType,
            sortBy,
            formData,
            
            // Computed
            filteredModels,
            filteredAndSortedModels,
            isFormValid,
            
            // Metódusok
            scanModels,
            addFromScan,
            editModel,
            saveModel,
            activateModel,
            deleteModel,
            testModel,
            closeModal,
            
            // Segédfüggvények
            gettext,
            formatSize,
            formatBytes,
            formatGPULayers,
            formatSpeed,
            formatNumber,
            formatTimeAgo,
            truncatePath
        };
    }
};

window.ModelSelector = ModelSelector;
console.log('✅ ModelSelector betöltve globálisan');