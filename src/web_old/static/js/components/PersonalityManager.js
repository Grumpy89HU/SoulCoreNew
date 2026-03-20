// Személyiség kezelő komponens
window.PersonalityManager = {
    template: `
        <div class="personality-manager">
            <!-- Fejléc keresővel -->
            <div class="manager-header">
                <div class="header-title">
                    <h3>{{ gettext('personalities.title') }}</h3>
                    <span class="personality-count" v-if="filteredPersonalities.length">
                        ({{ filteredPersonalities.length }})
                    </span>
                </div>
                
                <div class="header-actions">
                    <input 
                        type="text" 
                        v-model="searchQuery" 
                        :placeholder="gettext('personalities.search')"
                        class="search-input"
                    >
                    
                    <button class="btn-primary" @click="createNew" v-if="isAdmin" :disabled="loading">
                        <span v-if="!loading">+ {{ gettext('personalities.new') }}</span>
                        <span v-else class="spinner-small"></span>
                    </button>
                </div>
            </div>
            
            <!-- Szűrők -->
            <div class="filter-bar">
                <select v-model="filterActive" class="filter-select">
                    <option value="all">{{ gettext('personalities.all') }}</option>
                    <option value="active">{{ gettext('personalities.active_only') }}</option>
                    <option value="inactive">{{ gettext('personalities.inactive_only') }}</option>
                </select>
                
                <select v-model="sortBy" class="sort-select">
                    <option value="name">{{ gettext('personalities.sort_name') }}</option>
                    <option value="date">{{ gettext('personalities.sort_date') }}</option>
                    <option value="usage">{{ gettext('personalities.sort_usage') }}</option>
                </select>
            </div>
            
            <!-- Személyiség lista -->
            <div class="personality-list">
                <div v-for="personality in filteredAndSortedPersonalities" 
                     :key="personality.id" 
                     class="personality-card"
                     :class="{ 
                         active: personality.is_active,
                         selected: selectedPersonality?.id == personality.id
                     }"
                     @click="selectPersonality(personality)">
                    
                    <!-- Kártya fejléc -->
                    <div class="card-header">
                        <div class="card-title">
                            <span class="personality-name">{{ personality.name }}</span>
                            <span class="active-badge" v-if="personality.is_active">
                                👑 {{ gettext('personalities.active') }}
                            </span>
                        </div>
                        
                        <div class="card-actions" v-if="isAdmin" @click.stop>
                            <button class="icon-btn" @click="editPersonality(personality)" 
                                    :title="gettext('ui.edit')">
                                ✏️
                            </button>
                            <button class="icon-btn" @click="duplicatePersonality(personality)" 
                                    :title="gettext('personalities.duplicate')">
                                📋
                            </button>
                            <button class="icon-btn" @click="exportPersonality(personality)" 
                                    :title="gettext('personalities.export')">
                                📤
                            </button>
                        </div>
                    </div>
                    
                    <!-- Személyiség előnézet -->
                    <div class="personality-preview">
                        <div class="preview-traits">
                            <span v-for="trait in getTraits(personality)" 
                                  :key="trait" class="trait-badge">
                                {{ trait }}
                            </span>
                        </div>
                        <div class="preview-motto" v-if="personality.motto">
                            "{{ personality.motto }}"
                        </div>
                    </div>
                    
                    <!-- Meta információk -->
                    <div class="personality-meta">
                        <div class="meta-item" :title="gettext('personalities.language')">
                            🌐 {{ personality.language || 'en' }}
                        </div>
                        <div class="meta-item" :title="gettext('personalities.created')">
                            🕒 {{ formatDate(personality.created_at) }}
                        </div>
                        <div class="meta-item" v-if="personality.usage_count">
                            📊 {{ personality.usage_count }} {{ gettext('personalities.uses') }}
                        </div>
                    </div>
                    
                    <!-- Aktiválás gomb (ha nem aktív) -->
                    <button class="activate-btn" 
                            v-if="isAdmin && !personality.is_active"
                            @click.stop="activatePersonality(personality.id)">
                        ⚡ {{ gettext('personalities.activate') }}
                    </button>
                </div>
                
                <!-- Üres állapot -->
                <div v-if="filteredPersonalities.length === 0" class="empty-list">
                    <div class="empty-icon">🧠</div>
                    <div class="empty-text">{{ gettext('personalities.no_personalities') }}</div>
                    <button class="btn-primary" @click="createNew" v-if="isAdmin">
                        + {{ gettext('personalities.create_first') }}
                    </button>
                </div>
            </div>
            
            <!-- Szerkesztő modal -->
            <div class="modal" v-if="showEditor">
                <div class="modal-content large">
                    <div class="modal-header">
                        <h3>{{ editingPersonality ? gettext('personalities.edit') : gettext('personalities.new') }}</h3>
                        <button class="close-btn" @click="closeEditor">✕</button>
                    </div>
                    
                    <div class="modal-body">
                        <!-- Alapadatok -->
                        <div class="form-section">
                            <h4>{{ gettext('personalities.basic_info') }}</h4>
                            
                            <div class="form-row">
                                <div class="form-group">
                                    <label>{{ gettext('personalities.name') }} *</label>
                                    <input type="text" v-model="editForm.name" class="form-input">
                                </div>
                                
                                <div class="form-group">
                                    <label>{{ gettext('personalities.language') }}</label>
                                    <select v-model="editForm.language" class="form-input">
                                        <option value="en">English</option>
                                        <option value="hu">Magyar</option>
                                        <option value="de">Deutsch</option>
                                        <option value="fr">Français</option>
                                    </select>
                                </div>
                            </div>
                            
                            <div class="form-group">
                                <label>{{ gettext('personalities.title') }}</label>
                                <input type="text" v-model="editForm.title" class="form-input">
                            </div>
                            
                            <div class="form-group">
                                <label>{{ gettext('personalities.motto') }}</label>
                                <input type="text" v-model="editForm.motto" class="form-input">
                            </div>
                        </div>
                        
                        <!-- Személyiségjegyek -->
                        <div class="form-section">
                            <h4>{{ gettext('personalities.traits') }}</h4>
                            
                            <div class="traits-editor">
                                <div v-for="(trait, index) in editForm.traits" :key="index" 
                                     class="trait-row">
                                    <input type="text" v-model="editForm.traits[index]" 
                                           class="trait-input">
                                    <button class="remove-trait" @click="removeTrait(index)">✕</button>
                                </div>
                                
                                <button class="add-trait-btn" @click="addTrait">
                                    + {{ gettext('personalities.add_trait') }}
                                </button>
                            </div>
                        </div>
                        
                        <!-- Kedvel / Nem kedvel -->
                        <div class="form-row">
                            <div class="form-group half">
                                <label>{{ gettext('personalities.likes') }}</label>
                                <textarea v-model="editForm.likes" class="form-input" 
                                          rows="3" placeholder="{{ gettext('personalities.likes_placeholder') }}"></textarea>
                            </div>
                            
                            <div class="form-group half">
                                <label>{{ gettext('personalities.dislikes') }}</label>
                                <textarea v-model="editForm.dislikes" class="form-input" 
                                          rows="3" placeholder="{{ gettext('personalities.dislikes_placeholder') }}"></textarea>
                            </div>
                        </div>
                        
                        <!-- Morális iránytű -->
                        <div class="form-section">
                            <h4>{{ gettext('personalities.moral_compass') }}</h4>
                            
                            <div class="rules-editor">
                                <div v-for="(rule, index) in editForm.moral_compass" :key="index" 
                                     class="rule-row">
                                    <input type="text" v-model="editForm.moral_compass[index]" 
                                           class="rule-input">
                                    <button class="remove-rule" @click="removeRule(index)">✕</button>
                                </div>
                                
                                <button class="add-rule-btn" @click="addRule">
                                    + {{ gettext('personalities.add_rule') }}
                                </button>
                            </div>
                        </div>
                        
                        <!-- Kapcsolatok -->
                        <div class="form-section">
                            <h4>{{ gettext('personalities.relationships') }}</h4>
                            
                            <div class="relationships-editor">
                                <div v-for="(value, key) in editForm.relationships" :key="key" 
                                     class="relationship-row">
                                    <input type="text" v-model="editForm.relationships[key]" 
                                           :placeholder="key" class="relationship-value">
                                    <button class="remove-relationship" @click="removeRelationship(key)">✕</button>
                                </div>
                                
                                <div class="add-relationship">
                                    <input type="text" v-model="newRelationshipKey" 
                                           :placeholder="gettext('personalities.relationship_key')"
                                           class="relationship-key">
                                    <button class="add-relationship-btn" @click="addRelationship">
                                        + {{ gettext('personalities.add_relationship') }}
                                    </button>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Teljes tartalom előnézet -->
                        <div class="form-section">
                            <h4>{{ gettext('personalities.preview') }}</h4>
                            <pre class="content-preview">{{ formatContent(editForm) }}</pre>
                        </div>
                    </div>
                    
                    <div class="modal-footer">
                        <button class="btn-secondary" @click="closeEditor">
                            {{ gettext('ui.cancel') }}
                        </button>
                        <button class="btn-primary" @click="savePersonality" :disabled="!isFormValid">
                            <span v-if="!saving">{{ gettext('ui.save') }}</span>
                            <span v-else class="spinner-small"></span>
                        </button>
                    </div>
                </div>
            </div>
            
            <!-- Részletek modal (olvasásra) -->
            <div class="modal" v-if="showDetails">
                <div class="modal-content">
                    <div class="modal-header">
                        <h3>{{ selectedPersonality?.name }}</h3>
                        <button class="close-btn" @click="showDetails = false">✕</button>
                    </div>
                    
                    <div class="modal-body">
                        <pre class="personality-details">{{ formatContent(selectedPersonality) }}</pre>
                    </div>
                    
                    <div class="modal-footer">
                        <button class="btn-primary" @click="activatePersonality(selectedPersonality.id)" 
                                v-if="!selectedPersonality?.is_active">
                            ⚡ {{ gettext('personalities.activate') }}
                        </button>
                        <button class="btn-secondary" @click="showDetails = false">
                            {{ gettext('ui.close') }}
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
        
        const personalities = Vue.computed(() => window.store?.personalities || []);
        const isAdmin = Vue.computed(() => window.store?.isAdmin || false);
        
        // UI állapotok
        const loading = Vue.ref(false);
        const saving = Vue.ref(false);
        const searchQuery = Vue.ref('');
        const filterActive = Vue.ref('all');
        const sortBy = Vue.ref('name');
        
        // Kiválasztott személyiség
        const selectedPersonality = Vue.ref(null);
        const showDetails = Vue.ref(false);
        const showEditor = Vue.ref(false);
        const editingPersonality = Vue.ref(false);
        
        // Új kapcsolat hozzáadásához
        const newRelationshipKey = Vue.ref('');
        
        // Szerkesztő űrlap
        const editForm = Vue.ref({
            name: '',
            title: '',
            motto: '',
            language: 'en',
            traits: [],
            likes: '',
            dislikes: '',
            moral_compass: [],
            relationships: {}
        });
        
        // ====================================================================
        // COMPUTED PROPERTIES
        // ====================================================================
        
        // Szűrt személyiségek
        const filteredPersonalities = Vue.computed(() => {
            let filtered = personalities.value;
            
            // Keresés
            if (searchQuery.value) {
                const query = searchQuery.value.toLowerCase();
                filtered = filtered.filter(p => 
                    p.name?.toLowerCase().includes(query) ||
                    p.title?.toLowerCase().includes(query) ||
                    p.motto?.toLowerCase().includes(query)
                );
            }
            
            // Aktív szűrés
            if (filterActive.value === 'active') {
                filtered = filtered.filter(p => p.is_active);
            } else if (filterActive.value === 'inactive') {
                filtered = filtered.filter(p => !p.is_active);
            }
            
            return filtered;
        });
        
        // Rendezett személyiségek
        const filteredAndSortedPersonalities = Vue.computed(() => {
            const sorted = [...filteredPersonalities.value];
            
            switch (sortBy.value) {
                case 'name':
                    sorted.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
                    break;
                case 'date':
                    sorted.sort((a, b) => (b.created_at || 0) - (a.created_at || 0));
                    break;
                case 'usage':
                    sorted.sort((a, b) => (b.usage_count || 0) - (a.usage_count || 0));
                    break;
            }
            
            // Aktív személyiségek előre
            sorted.sort((a, b) => {
                if (a.is_active && !b.is_active) return -1;
                if (!a.is_active && b.is_active) return 1;
                return 0;
            });
            
            return sorted;
        });
        
        // Űrlap validáció
        const isFormValid = Vue.computed(() => {
            return editForm.value.name?.trim();
        });
        
        // ====================================================================
        // SEGÉDFÜGGVÉNYEK
        // ====================================================================
        
        const gettext = (key, params = {}) => {
            return window.gettext ? window.gettext(key, params) : key;
        };
        
        const formatDate = (dateStr) => {
            if (!dateStr) return '';
            const date = new Date(dateStr);
            return date.toLocaleDateString();
        };
        
        const getTraits = (personality) => {
            if (personality.traits) return personality.traits;
            
            // Szövegből kinyerés
            if (personality.content) {
                const match = personality.content.match(/traits:\s*(.+?)(?:\n|$)/i);
                if (match) {
                    return match[1].split(',').map(t => t.trim());
                }
            }
            
            return [];
        };
        
        const parseContent = (content) => {
            const result = {
                name: '',
                title: '',
                motto: '',
                traits: [],
                likes: '',
                dislikes: '',
                moral_compass: [],
                relationships: {}
            };
            
            if (!content) return result;
            
            const lines = content.split('\n');
            let currentSection = '';
            
            lines.forEach(line => {
                line = line.trim();
                if (!line) return;
                
                if (line.includes(':')) {
                    const [key, ...valueParts] = line.split(':');
                    const value = valueParts.join(':').trim();
                    
                    if (key.toLowerCase() === 'name') result.name = value;
                    else if (key.toLowerCase() === 'title') result.title = value;
                    else if (key.toLowerCase() === 'motto') result.motto = value;
                    else if (key.toLowerCase() === 'traits') {
                        result.traits = value.split(',').map(t => t.trim());
                    }
                    else if (key.toLowerCase() === 'likes') result.likes = value;
                    else if (key.toLowerCase() === 'dislikes') result.dislikes = value;
                    else if (key.toLowerCase() === 'rules') {
                        result.moral_compass.push(value);
                    }
                    else if (key.match(/^[a-z]+:$/i)) {
                        const relKey = key.slice(0, -1).toLowerCase();
                        result.relationships[relKey] = value;
                    }
                }
            });
            
            return result;
        };
        
        const formatContent = (personality) => {
            if (personality.content) return personality.content;
            
            const lines = [
                `name: ${personality.name || 'Unknown'}`,
                `title: ${personality.title || ''}`,
                `motto: ${personality.motto || ''}`,
                '',
                `traits: ${personality.traits?.join(', ') || ''}`,
                '',
                `likes: ${personality.likes || ''}`,
                `dislikes: ${personality.dislikes || ''}`,
                '',
                'moral_compass:'
            ];
            
            if (personality.moral_compass) {
                personality.moral_compass.forEach(rule => {
                    lines.push(`  - ${rule}`);
                });
            }
            
            lines.push('');
            lines.push('relationships:');
            
            if (personality.relationships) {
                Object.entries(personality.relationships).forEach(([key, value]) => {
                    lines.push(`  ${key}: ${value}`);
                });
            }
            
            return lines.join('\n');
        };
        
        // ====================================================================
        // METÓDUSOK
        // ====================================================================
        
        const refreshPersonalities = async () => {
            if (window.api) {
                await window.api.getPersonalities();
            }
        };
        
        const selectPersonality = (personality) => {
            selectedPersonality.value = personality;
            showDetails.value = true;
        };
        
        const createNew = () => {
            editingPersonality.value = false;
            editForm.value = {
                name: '',
                title: '',
                motto: '',
                language: 'en',
                traits: [],
                likes: '',
                dislikes: '',
                moral_compass: [],
                relationships: {}
            };
            showEditor.value = true;
        };
        
        const editPersonality = (personality) => {
            editingPersonality.value = true;
            
            // Meglévő adatok betöltése
            if (personality.content) {
                const parsed = parseContent(personality.content);
                editForm.value = {
                    ...parsed,
                    id: personality.id,
                    language: personality.language || 'en'
                };
            } else {
                editForm.value = {
                    id: personality.id,
                    name: personality.name || '',
                    title: personality.title || '',
                    motto: personality.motto || '',
                    language: personality.language || 'en',
                    traits: personality.traits || [],
                    likes: personality.likes || '',
                    dislikes: personality.dislikes || '',
                    moral_compass: personality.moral_compass || [],
                    relationships: personality.relationships || {}
                };
            }
            
            showEditor.value = true;
        };
        
        const duplicatePersonality = (personality) => {
            const duplicate = {
                ...personality,
                id: null,
                name: personality.name + ' (' + gettext('personalities.copy') + ')',
                is_active: false
            };
            editPersonality(duplicate);
            editingPersonality.value = false;
        };
        
        const exportPersonality = (personality) => {
            const data = {
                ...personality,
                exported: new Date().toISOString()
            };
            
            const blob = new Blob([formatContent(data)], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `personality_${personality.name}_${new Date().toISOString().slice(0,10)}.inf`;
            a.click();
        };
        
        const activatePersonality = async (id) => {
            if (!isAdmin.value) return;
            
            loading.value = true;
            
            try {
                await window.api.activatePersonality(id);
                await refreshPersonalities();
                showDetails.value = false;
                
                window.socketManager?.addSystemMessage?.(
                    gettext('personalities.activated'),
                    'success'
                );
            } catch (error) {
                alert(gettext('personalities.activate_error') + ': ' + error.message);
            } finally {
                loading.value = false;
            }
        };
        
        const savePersonality = async () => {
            if (!isAdmin.value || !isFormValid.value) return;
            
            saving.value = true;
            
            try {
                const content = formatContent(editForm.value);
                
                const personalityData = {
                    name: editForm.value.name,
                    content: content,
                    language: editForm.value.language,
                    activate: false
                };
                
                if (editingPersonality.value) {
                    personalityData.id = editForm.value.id;
                }
                
                await window.api.createPersonality(personalityData);
                await refreshPersonalities();
                closeEditor();
                
                window.socketManager?.addSystemMessage?.(
                    editingPersonality.value ? 
                        gettext('personalities.updated') : 
                        gettext('personalities.created'),
                    'success'
                );
                
            } catch (error) {
                alert(gettext('personalities.save_error') + ': ' + error.message);
            } finally {
                saving.value = false;
            }
        };
        
        const closeEditor = () => {
            showEditor.value = false;
            editingPersonality.value = false;
        };
        
        // Trait kezelés
        const addTrait = () => {
            if (!editForm.value.traits) {
                editForm.value.traits = [];
            }
            editForm.value.traits.push('');
        };
        
        const removeTrait = (index) => {
            editForm.value.traits.splice(index, 1);
        };
        
        // Rule kezelés
        const addRule = () => {
            if (!editForm.value.moral_compass) {
                editForm.value.moral_compass = [];
            }
            editForm.value.moral_compass.push('');
        };
        
        const removeRule = (index) => {
            editForm.value.moral_compass.splice(index, 1);
        };
        
        // Relationship kezelés
        const addRelationship = () => {
            if (!newRelationshipKey.value) return;
            
            if (!editForm.value.relationships) {
                editForm.value.relationships = {};
            }
            
            editForm.value.relationships[newRelationshipKey.value] = '';
            newRelationshipKey.value = '';
        };
        
        const removeRelationship = (key) => {
            Vue.delete(editForm.value.relationships, key);
        };
        
        // ====================================================================
        // ÉLETCIKLUS
        // ====================================================================
        
        Vue.onMounted(refreshPersonalities);
        
        return {
            // Állapotok
            personalities,
            isAdmin,
            loading,
            saving,
            searchQuery,
            filterActive,
            sortBy,
            selectedPersonality,
            showDetails,
            showEditor,
            editingPersonality,
            editForm,
            newRelationshipKey,
            
            // Computed
            filteredPersonalities,
            filteredAndSortedPersonalities,
            isFormValid,
            
            // Metódusok
            gettext,
            formatDate,
            getTraits,
            formatContent,
            selectPersonality,
            createNew,
            editPersonality,
            duplicatePersonality,
            exportPersonality,
            activatePersonality,
            savePersonality,
            closeEditor,
            addTrait,
            removeTrait,
            addRule,
            removeRule,
            addRelationship,
            removeRelationship
        };
    }
};

window.PersonalityManager = PersonalityManager;
console.log('✅ PersonalityManager betöltve globálisan');