// ==============================================
// SOULCORE 3.0 - Személyiségkezelő komponens
// ==============================================

window.PersonalityManager = {
    name: 'PersonalityManager',
    
    template: `
        <div class="personality-manager">
            <!-- Fejléc -->
            <div class="manager-header">
                <div class="header-title">
                    <h3>{{ t('personalities.title') }}</h3>
                    <span class="personality-count" v-if="personalities.length">({{ personalities.length }})</span>
                </div>
                <div class="header-actions">
                    <input 
                        type="text" 
                        v-model="searchQuery" 
                        :placeholder="t('personalities.search')"
                        class="search-input"
                    >
                    <button class="refresh-btn" @click="refreshPersonalities" :disabled="refreshing">
                        <span :class="{ 'spin': refreshing }">🔄</span>
                    </button>
                    <button class="btn-primary" @click="createNew" v-if="isAdmin">
                        + {{ t('personalities.new') }}
                    </button>
                </div>
            </div>
            
            <!-- Személyiségek lista -->
            <div class="personality-list">
                <div v-for="personality in filteredPersonalities" :key="personality.id" 
                     class="personality-card" 
                     :class="{ 
                         active: activePersonalityId === personality.id,
                         selected: selectedPersonality?.id === personality.id
                     }"
                     @click="selectPersonality(personality)">
                    
                    <!-- Kártya fejléc -->
                    <div class="card-header">
                        <div class="card-title">
                            <span class="personality-name">{{ personality.name }}</span>
                            <span v-if="activePersonalityId === personality.id" class="active-badge">
                                🟢 {{ t('personalities.active') }}
                            </span>
                        </div>
                        <div class="card-actions" @click.stop>
                            <button v-if="isAdmin" class="icon-btn" @click="editPersonality(personality)" :title="t('ui.edit')">
                                ✏️
                            </button>
                            <button v-if="isAdmin && activePersonalityId !== personality.id" 
                                    class="icon-btn" @click="deletePersonality(personality.id)" 
                                    :title="t('ui.delete')">
                                🗑️
                            </button>
                        </div>
                    </div>
                    
                    <!-- Tulajdonságok -->
                    <div class="personality-traits" v-if="personality.traits && personality.traits.length">
                        <span v-for="trait in personality.traits.slice(0, 3)" :key="trait" class="trait-badge">
                            #{{ trait }}
                        </span>
                        <span v-if="personality.traits.length > 3" class="trait-badge">
                            +{{ personality.traits.length - 3 }}
                        </span>
                    </div>
                    
                    <!-- Mottó -->
                    <div class="personality-motto" v-if="personality.motto">
                        "{{ truncate(personality.motto, 60) }}"
                    </div>
                    
                    <!-- Leírás előnézet -->
                    <div class="personality-preview" v-if="personality.description">
                        {{ truncate(personality.description, 80) }}
                    </div>
                    
                    <!-- Meta adatok -->
                    <div class="personality-meta">
                        <span class="meta-item">🕒 {{ formatRelativeTime(personality.updated_at) }}</span>
                        <span class="meta-item" v-if="personality.usage_count">
                            📊 {{ personality.usage_count }} {{ t('personalities.uses') }}
                        </span>
                    </div>
                    
                    <!-- Aktiválás gomb -->
                    <button v-if="activePersonalityId !== personality.id" 
                            class="activate-btn" 
                            @click.stop="activatePersonality(personality.id)"
                            :disabled="activating === personality.id">
                        <span v-if="activating !== personality.id">🎭 {{ t('personalities.activate') }}</span>
                        <span v-else class="spinner-small"></span>
                    </button>
                </div>
                
                <!-- Nincs találat -->
                <div v-if="filteredPersonalities.length === 0" class="empty-list">
                    <div class="empty-icon">🎭</div>
                    <div class="empty-text">{{ t('personalities.no_personalities') }}</div>
                    <button class="btn-primary" @click="createNew" v-if="isAdmin">
                        + {{ t('personalities.create_first') }}
                    </button>
                </div>
            </div>
            
            <!-- Szerkesztő modal -->
            <div class="modal" v-if="showEditorModal" @click.self="showEditorModal = false">
                <div class="modal-content large">
                    <div class="modal-header">
                        <h3>{{ editingPersonality ? t('personalities.edit') : t('personalities.create') }}</h3>
                        <button class="close-btn" @click="showEditorModal = false">✕</button>
                    </div>
                    <div class="modal-body">
                        <div class="form-group">
                            <label>{{ t('personalities.name') }} *</label>
                            <input type="text" v-model="editForm.name" class="form-input" 
                                   :placeholder="t('personalities.name_placeholder')">
                        </div>
                        
                        <div class="form-group">
                            <label>{{ t('personalities.motto') }}</label>
                            <input type="text" v-model="editForm.motto" class="form-input" 
                                   :placeholder="t('personalities.motto_placeholder')">
                        </div>
                        
                        <div class="form-group">
                            <label>{{ t('personalities.description') }}</label>
                            <textarea v-model="editForm.description" rows="2" class="form-input" 
                                      :placeholder="t('personalities.description_placeholder')"></textarea>
                        </div>
                        
                        <!-- Tulajdonságok szerkesztése -->
                        <div class="form-group">
                            <label>{{ t('personalities.traits') }}</label>
                            <div class="traits-editor">
                                <div v-for="(trait, idx) in editForm.traits" :key="idx" class="trait-row">
                                    <input type="text" v-model="editForm.traits[idx]" class="trait-input" 
                                           :placeholder="t('personalities.trait_placeholder')">
                                    <button class="remove-trait" @click="removeTrait(idx)">✕</button>
                                </div>
                                <button class="add-trait-btn" @click="addTrait">
                                    + {{ t('personalities.add_trait') }}
                                </button>
                            </div>
                        </div>
                        
                        <!-- Kapcsolatok szerkesztése -->
                        <div class="form-group">
                            <label>{{ t('personalities.relationships') }}</label>
                            <div class="relationships-editor">
                                <div v-for="(rel, idx) in editForm.relationships" :key="idx" class="relationship-row">
                                    <input type="text" v-model="editForm.relationships[idx].target" class="relationship-input" 
                                           :placeholder="t('personalities.relationship_target')">
                                    <input type="text" v-model="editForm.relationships[idx].description" class="relationship-input" 
                                           :placeholder="t('personalities.relationship_desc')">
                                    <button class="remove-relationship" @click="removeRelationship(idx)">✕</button>
                                </div>
                                <button class="add-relationship-btn" @click="addRelationship">
                                    + {{ t('personalities.add_relationship') }}
                                </button>
                            </div>
                        </div>
                        
                        <!-- Teljes prompt tartalom -->
                        <div class="form-group">
                            <label>{{ t('personalities.content') }}</label>
                            <div class="variables-hint">
                                <span class="hint-text">💡 {{ t('personalities.variables_hint') }}</span>
                                <div class="variables-list-small">
                                    <code v-for="v in contentVariables" :key="v" class="variable-hint" 
                                          @click="insertContentVariable(v)">{{ '{' + v + '}' }}</code>
                                </div>
                            </div>
                            <textarea v-model="editForm.content" rows="8" class="form-input" 
                                      :placeholder="t('personalities.content_placeholder')"></textarea>
                        </div>
                        
                        <!-- Előnézet -->
                        <div class="form-group">
                            <label>{{ t('personalities.preview') }}</label>
                            <div class="content-preview">{{ editForm.content || t('personalities.no_content') }}</div>
                        </div>
                        
                        <div v-if="editorError" class="auth-error">{{ editorError }}</div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn-secondary" @click="showEditorModal = false">
                            {{ t('ui.cancel') }}
                        </button>
                        <button class="btn-primary" @click="savePersonality" :disabled="saving">
                            <span v-if="!saving">💾 {{ t('ui.save') }}</span>
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
        
        const personalities = Vue.computed(() => window.store.personalities);
        const activePersonalityId = Vue.computed(() => window.store.activePersonalityId);
        const isAdmin = Vue.computed(() => window.store.user?.role === 'admin');
        
        // UI állapotok
        const searchQuery = Vue.ref('');
        const refreshing = Vue.ref(false);
        const activating = Vue.ref(null);
        const saving = Vue.ref(false);
        
        // Kiválasztott személyiség
        const selectedPersonality = Vue.ref(null);
        
        // Szerkesztő modal
        const showEditorModal = Vue.ref(false);
        const editingPersonality = Vue.ref(null);
        const editForm = Vue.ref({
            id: null,
            name: '',
            motto: '',
            description: '',
            traits: [],
            relationships: [],
            content: '',
            is_default: false
        });
        const editorError = Vue.ref('');
        
        // Változók a tartalomhoz
        const contentVariables = ['name', 'motto', 'traits', 'description', 'user', 'date', 'time'];
        
        // ====================================================================
        // COMPUTED PROPERTIES
        // ====================================================================
        
        const filteredPersonalities = Vue.computed(() => {
            let filtered = [...personalities.value];
            
            if (searchQuery.value) {
                const query = searchQuery.value.toLowerCase();
                filtered = filtered.filter(p => 
                    p.name?.toLowerCase().includes(query) ||
                    p.description?.toLowerCase().includes(query) ||
                    p.motto?.toLowerCase().includes(query) ||
                    p.traits?.some(t => t.toLowerCase().includes(query))
                );
            }
            
            return filtered;
        });
        
        // ====================================================================
        // SEGÉDFÜGGVÉNYEK
        // ====================================================================
        
        const t = (key, params = {}) => window.gettext(key, params);
        const truncate = (text, length) => window.truncate(text, length);
        const formatRelativeTime = (ts) => window.formatRelativeTime(ts);
        
        /**
         * Személyiség kiválasztása
         */
        const selectPersonality = (personality) => {
            selectedPersonality.value = personality;
        };
        
        /**
         * Személyiségek betöltése
         */
        const loadPersonalities = async () => {
            try {
                await window.api.getPersonalities();
            } catch (error) {
                console.error('Error loading personalities:', error);
                window.store.addNotification('error', t('personalities.load_error'));
            }
        };
        
        /**
         * Személyiségek frissítése
         */
        const refreshPersonalities = async () => {
            refreshing.value = true;
            try {
                await loadPersonalities();
                window.store.addNotification('success', t('personalities.refreshed'));
            } catch (error) {
                console.error('Error refreshing personalities:', error);
                window.store.addNotification('error', t('personalities.refresh_error'));
            } finally {
                refreshing.value = false;
            }
        };
        
        /**
         * Személyiség aktiválása
         */
        const activatePersonality = async (id) => {
            activating.value = id;
            try {
                await window.api.activatePersonality(id);
                window.store.addNotification('success', t('personalities.activated'));
                await loadPersonalities();
            } catch (error) {
                console.error('Error activating personality:', error);
                window.store.addNotification('error', t('personalities.activate_error'));
            } finally {
                activating.value = null;
            }
        };
        
        /**
         * Új személyiség létrehozása
         */
        const createNew = () => {
            editingPersonality.value = null;
            editForm.value = {
                id: null,
                name: '',
                motto: '',
                description: '',
                traits: [],
                relationships: [],
                content: '',
                is_default: false
            };
            editorError.value = '';
            showEditorModal.value = true;
        };
        
        /**
         * Személyiség szerkesztése
         */
        const editPersonality = (personality) => {
            editingPersonality.value = personality;
            editForm.value = {
                id: personality.id,
                name: personality.name || '',
                motto: personality.motto || '',
                description: personality.description || '',
                traits: personality.traits ? [...personality.traits] : [],
                relationships: personality.relationships ? [...personality.relationships] : [],
                content: personality.content || '',
                is_default: personality.is_default || false
            };
            editorError.value = '';
            showEditorModal.value = true;
        };
        
        /**
         * Tulajdonság hozzáadása
         */
        const addTrait = () => {
            editForm.value.traits.push('');
        };
        
        /**
         * Tulajdonság eltávolítása
         */
        const removeTrait = (index) => {
            editForm.value.traits.splice(index, 1);
        };
        
        /**
         * Kapcsolat hozzáadása
         */
        const addRelationship = () => {
            editForm.value.relationships.push({ target: '', description: '' });
        };
        
        /**
         * Kapcsolat eltávolítása
         */
        const removeRelationship = (index) => {
            editForm.value.relationships.splice(index, 1);
        };
        
        /**
         * Változó beszúrása a tartalomba
         */
        const insertContentVariable = (varName) => {
            const textarea = document.querySelector('.modal-body textarea:last-of-type');
            if (!textarea) return;
            
            const start = textarea.selectionStart;
            const end = textarea.selectionEnd;
            const text = editForm.value.content;
            
            editForm.value.content = 
                text.substring(0, start) + 
                '{' + varName + '}' + 
                text.substring(end);
            
            Vue.nextTick(() => {
                textarea.selectionStart = textarea.selectionEnd = start + varName.length + 2;
                textarea.focus();
            });
        };
        
        /**
         * Személyiség mentése
         */
        const savePersonality = async () => {
            if (!editForm.value.name.trim()) {
                editorError.value = t('personalities.error_name_required');
                return;
            }
            
            saving.value = true;
            editorError.value = '';
            
            try {
                await window.api.savePersonality(editForm.value);
                window.store.addNotification('success', t('personalities.saved'));
                showEditorModal.value = false;
                await loadPersonalities();
                
                // Ha az aktív személyiség változott, frissítsük
                if (editForm.value.id === activePersonalityId.value) {
                    window.store.activatePersonality(editForm.value.id);
                }
            } catch (error) {
                console.error('Error saving personality:', error);
                editorError.value = error.message || t('personalities.save_error');
            } finally {
                saving.value = false;
            }
        };
        
        /**
         * Személyiség törlése
         */
        const deletePersonality = async (id) => {
            const personality = personalities.value.find(p => p.id === id);
            if (!personality) return;
            
            if (!confirm(t('personalities.confirm_delete', { name: personality.name }))) return;
            
            try {
                await window.api.deletePersonality(id);
                window.store.addNotification('success', t('personalities.deleted'));
                await loadPersonalities();
                
                if (selectedPersonality.value?.id === id) {
                    selectedPersonality.value = null;
                }
            } catch (error) {
                console.error('Error deleting personality:', error);
                window.store.addNotification('error', t('personalities.delete_error'));
            }
        };
        
        // ====================================================================
        // ÉLETCIKLUS
        // ====================================================================
        
        Vue.onMounted(() => {
            loadPersonalities();
        });
        
        // ====================================================================
        // RETURN
        // ====================================================================
        
        return {
            // Állapotok
            personalities,
            activePersonalityId,
            isAdmin,
            searchQuery,
            refreshing,
            activating,
            saving,
            selectedPersonality,
            filteredPersonalities,
            
            // Szerkesztő
            showEditorModal,
            editingPersonality,
            editForm,
            editorError,
            contentVariables,
            
            // Segédfüggvények
            t,
            truncate,
            formatRelativeTime,
            
            // Metódusok
            selectPersonality,
            refreshPersonalities,
            activatePersonality,
            createNew,
            editPersonality,
            addTrait,
            removeTrait,
            addRelationship,
            removeRelationship,
            insertContentVariable,
            savePersonality,
            deletePersonality
        };
    }
};

console.log('✅ PersonalityManager komponens betöltve');