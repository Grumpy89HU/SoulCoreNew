// Prompt szerkesztő komponens
window.PromptEditor = {
    template: `
        <div class="prompt-editor">
            <!-- Fejléc keresővel és szűrőkkel -->
            <div class="prompt-header">
                <div class="header-title">
                    <h3>{{ gettext('prompts.title') }}</h3>
                    <span class="prompt-count" v-if="filteredPrompts.length">({{ filteredPrompts.length }})</span>
                </div>
                
                <div class="header-actions">
                    <input 
                        type="text" 
                        v-model="searchQuery" 
                        :placeholder="gettext('prompts.search')"
                        class="search-input"
                    >
                    
                    <select v-model="selectedCategory" class="category-select">
                        <option value="all">{{ gettext('prompts.all_categories') }}</option>
                        <option value="king">{{ gettext('prompts.category_king') }}</option>
                        <option value="queen">{{ gettext('prompts.category_queen') }}</option>
                        <option value="general">{{ gettext('prompts.category_general') }}</option>
                        <option value="expert">{{ gettext('prompts.category_expert') }}</option>
                        <option value="custom">{{ gettext('prompts.category_custom') }}</option>
                    </select>
                    
                    <button class="btn-primary" @click="createNew" v-if="isAdmin" :disabled="loading">
                        <span v-if="!loading">+ {{ gettext('prompts.new') }}</span>
                        <span v-else class="spinner-small"></span>
                    </button>
                </div>
            </div>
            
            <div class="prompt-main" :class="{ 'split-view': selectedPrompt }">
                <!-- Prompt lista -->
                <div class="prompt-list-container">
                    <div class="prompt-list-header">
                        <span>{{ gettext('prompts.list') }}</span>
                        <button class="refresh-btn" @click="refreshPrompts" :disabled="refreshing">
                            <span :class="{ 'spin': refreshing }">🔄</span>
                        </button>
                    </div>
                    
                    <div class="prompt-list">
                        <div v-for="prompt in filteredAndSortedPrompts" :key="prompt.id" 
                             class="prompt-item" 
                             :class="{ 
                                 active: selectedPrompt?.id == prompt.id,
                                 'default': prompt.is_default
                             }"
                             @click="selectPrompt(prompt)">
                            
                            <div class="prompt-item-header">
                                <div class="prompt-title">
                                    <span class="prompt-name">{{ prompt.name }}</span>
                                    <span class="prompt-badge" v-if="prompt.is_default">
                                        ⭐ {{ gettext('prompts.default') }}
                                    </span>
                                    <span class="prompt-badge" v-if="prompt.version > 1">
                                        v{{ prompt.version }}
                                    </span>
                                </div>
                                <div class="prompt-meta">
                                    <span class="prompt-category">{{ getPromptCategoryName(prompt.category) }}</span>
                                    <span class="prompt-date" :title="formatDate(prompt.updated_at)">
                                        🕒 {{ formatRelativeTime(prompt.updated_at) }}
                                    </span>
                                </div>
                            </div>
                            
                            <div class="prompt-preview">{{ truncate(prompt.content, 100) }}</div>
                            
                            <div class="prompt-stats" v-if="prompt.usage_count">
                                <span class="stat">📊 {{ prompt.usage_count }} {{ gettext('prompts.uses') }}</span>
                            </div>
                        </div>
                        
                        <div v-if="filteredPrompts.length === 0" class="empty-list">
                            <div class="empty-icon">📝</div>
                            <div class="empty-text">{{ gettext('prompts.no_prompts') }}</div>
                            <button class="btn-primary" @click="createNew" v-if="isAdmin">
                                + {{ gettext('prompts.create_first') }}
                            </button>
                        </div>
                    </div>
                </div>
                
                <!-- Szerkesztő panel -->
                <div class="prompt-edit-panel" v-if="selectedPrompt">
                    <div class="edit-header">
                        <div class="edit-title">
                            <h3>{{ selectedPrompt.is_default ? '⭐' : '' }} {{ selectedPrompt.name }}</h3>
                            <span class="edit-id" v-if="selectedPrompt.id">#{{ selectedPrompt.id }}</span>
                        </div>
                        
                        <div class="edit-actions" v-if="isAdmin">
                            <button class="icon-btn" @click="duplicatePrompt" :title="gettext('prompts.duplicate')">
                                📋
                            </button>
                            <button class="icon-btn" @click="showHistory" :title="gettext('prompts.history')">
                                📜
                            </button>
                            <button class="icon-btn" @click="testPrompt" :title="gettext('prompts.test')">
                                🧪
                            </button>
                            <button class="control-btn" @click="savePrompt" :disabled="saving">
                                <span v-if="!saving">💾 {{ gettext('ui.save') }}</span>
                                <span v-else class="spinner-small"></span>
                            </button>
                            <button class="control-btn stop" @click="deletePrompt" 
                                    v-if="!selectedPrompt.is_default" :disabled="saving">
                                🗑️ {{ gettext('ui.delete') }}
                            </button>
                        </div>
                    </div>
                    
                    <!-- Alapadatok -->
                    <div class="edit-basic">
                        <div class="form-row">
                            <div class="form-group">
                                <label>{{ gettext('prompts.name') }} *</label>
                                <input type="text" v-model="editForm.name" class="form-input" 
                                       :disabled="!isAdmin || loading">
                            </div>
                            
                            <div class="form-group">
                                <label>{{ gettext('prompts.category') }}</label>
                                <select v-model="editForm.category" class="form-input" :disabled="!isAdmin">
                                    <option value="king">{{ gettext('prompts.category_king') }}</option>
                                    <option value="queen">{{ gettext('prompts.category_queen') }}</option>
                                    <option value="general">{{ gettext('prompts.category_general') }}</option>
                                    <option value="expert">{{ gettext('prompts.category_expert') }}</option>
                                    <option value="custom">{{ gettext('prompts.category_custom') }}</option>
                                </select>
                            </div>
                        </div>
                        
                        <div class="form-group">
                            <label>{{ gettext('prompts.description') }}</label>
                            <input type="text" v-model="editForm.description" class="form-input" 
                                   :disabled="!isAdmin" :placeholder="gettext('prompts.description_placeholder')">
                        </div>
                    </div>
                    
                    <!-- Változók panel -->
                    <div class="variables-panel">
                        <div class="panel-header">
                            <span>{{ gettext('prompts.variables') }}</span>
                            <button class="small-btn" @click="showVariablesHelp = !showVariablesHelp">❓</button>
                        </div>
                        
                        <div class="variables-list">
                            <div v-for="(desc, varName) in availableVariables" 
                                 :key="varName" 
                                 class="variable-chip"
                                 @click="insertVariable(varName)"
                                 :title="desc">
                                <code>{{ '{' + varName + '}' }}</code>
                            </div>
                        </div>
                        
                        <div v-if="showVariablesHelp" class="variables-help">
                            {{ gettext('prompts.variables_help') }}
                        </div>
                    </div>
                    
                    <!-- Prompt szerkesztő -->
                    <div class="edit-content">
                        <div class="content-header">
                            <label>{{ gettext('prompts.content') }} *</label>
                            <div class="content-stats">
                                <span class="stat">📏 {{ contentLength }} {{ gettext('prompts.chars') }}</span>
                                <span class="stat">🔤 {{ estimatedTokens }} {{ gettext('prompts.tokens') }}</span>
                            </div>
                        </div>
                        
                        <textarea 
                            v-model="editForm.content" 
                            class="prompt-textarea" 
                            :class="{ 'has-error': contentError }"
                            rows="12" 
                            :disabled="!isAdmin"
                            @input="validateContent"
                            :placeholder="gettext('prompts.content_placeholder')"
                        ></textarea>
                        
                        <div v-if="contentError" class="content-error">
                            ⚠️ {{ contentError }}
                        </div>
                        
                        <!-- Gyors sablonok -->
                        <div class="quick-templates" v-if="isAdmin">
                            <span class="label">{{ gettext('prompts.templates') }}:</span>
                            <button class="template-btn" @click="insertTemplate('basic')">
                                💬 {{ gettext('prompts.template_basic') }}
                            </button>
                            <button class="template-btn" @click="insertTemplate('instruction')">
                                📋 {{ gettext('prompts.template_instruction') }}
                            </button>
                            <button class="template-btn" @click="insertTemplate('fewshot')">
                                🔢 {{ gettext('prompts.template_fewshot') }}
                            </button>
                        </div>
                    </div>
                    
                    <!-- Opciók -->
                    <div class="edit-options">
                        <label class="checkbox-label">
                            <input type="checkbox" v-model="editForm.is_default" :disabled="!isAdmin">
                            {{ gettext('prompts.is_default') }}
                        </label>
                        
                        <div class="token-estimate" v-if="editForm.content">
                            <span class="label">{{ gettext('prompts.estimated_cost') }}:</span>
                            <span class="value">≈ {{ estimatedTokens * 0.002 | currency }} ({{ estimatedTokens }} tk)</span>
                        </div>
                    </div>
                    
                    <!-- Előnézet -->
                    <div class="preview-section">
                        <div class="preview-header">
                            <span>{{ gettext('prompts.preview') }}</span>
                            <button class="small-btn" @click="refreshPreview">🔄</button>
                        </div>
                        
                        <div class="preview-box" :class="{ 'preview-loading': previewLoading }">
                            <div v-if="!previewLoading" class="preview-content" v-html="formattedPreview"></div>
                            <div v-else class="preview-loading-indicator">⏳</div>
                        </div>
                        
                        <div class="preview-controls">
                            <input 
                                type="text" 
                                v-model="previewText" 
                                :placeholder="gettext('prompts.test_input')"
                                class="preview-input"
                                @input="updatePreview"
                            >
                            <button class="small-btn" @click="testWithInput">🧪</button>
                        </div>
                    </div>
                    
                    <!-- Verziótörténet (modal) -->
                    <div class="modal" v-if="showHistoryModal">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h3>{{ gettext('prompts.history') }} - {{ selectedPrompt.name }}</h3>
                                <button class="close-btn" @click="showHistoryModal = false">✕</button>
                            </div>
                            
                            <div class="modal-body">
                                <div class="version-list">
                                    <div v-for="version in promptVersions" :key="version.id" 
                                         class="version-item" 
                                         :class="{ 'active': version.id === currentVersion }"
                                         @click="loadVersion(version)">
                                        <div class="version-header">
                                            <span class="version-number">v{{ version.version }}</span>
                                            <span class="version-date">{{ formatDate(version.created_at) }}</span>
                                        </div>
                                        <div class="version-comment">{{ version.comment || gettext('prompts.no_comment') }}</div>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="modal-footer">
                                <button class="btn-secondary" @click="showHistoryModal = false">
                                    {{ gettext('ui.close') }}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `,
    
    setup() {
        // ====================================================================
        // REAKTÍV ÁLLAPOTOK
        // ====================================================================
        
        const prompts = Vue.computed(() => window.store?.prompts || []);
        const isAdmin = Vue.computed(() => window.store?.isAdmin || false);
        
        // UI állapotok
        const loading = Vue.ref(false);
        const saving = Vue.ref(false);
        const refreshing = Vue.ref(false);
        const previewLoading = Vue.ref(false);
        
        // Keresés és szűrés
        const searchQuery = Vue.ref('');
        const selectedCategory = Vue.ref('all');
        const sortBy = Vue.ref('updated');
        
        // Kiválasztott prompt
        const selectedPrompt = Vue.ref(null);
        const editForm = Vue.ref({
            id: null,
            name: '',
            content: '',
            description: '',
            category: 'general',
            is_default: false,
            version: 1
        });
        
        // Előnézet
        const previewText = Vue.ref('');
        const previewContent = Vue.ref('');
        
        // Hibák
        const contentError = Vue.ref('');
        
        // Változók
        const showVariablesHelp = Vue.ref(false);
        const availableVariables = {
            'text': gettext('prompts.var_text'),
            'user': gettext('prompts.var_user'),
            'date': gettext('prompts.var_date'),
            'time': gettext('prompts.var_time'),
            'context': gettext('prompts.var_context'),
            'history': gettext('prompts.var_history')
        };
        
        // Verziótörténet
        const showHistoryModal = Vue.ref(false);
        const promptVersions = Vue.ref([]);
        const currentVersion = Vue.ref(null);
        
        // ====================================================================
        // COMPUTED PROPERTIES
        // ====================================================================
        
        // Szűrt promptok
        const filteredPrompts = Vue.computed(() => {
            let filtered = prompts.value;
            
            // Kategória szűrés
            if (selectedCategory.value !== 'all') {
                filtered = filtered.filter(p => p.category === selectedCategory.value);
            }
            
            // Keresés
            if (searchQuery.value) {
                const query = searchQuery.value.toLowerCase();
                filtered = filtered.filter(p => 
                    p.name?.toLowerCase().includes(query) ||
                    p.content?.toLowerCase().includes(query) ||
                    p.description?.toLowerCase().includes(query)
                );
            }
            
            return filtered;
        });
        
        // Rendezett promptok
        const filteredAndSortedPrompts = Vue.computed(() => {
            const sorted = [...filteredPrompts.value];
            
            sorted.sort((a, b) => {
                if (a.is_default && !b.is_default) return -1;
                if (!a.is_default && b.is_default) return 1;
                
                const dateA = new Date(a.updated_at || 0);
                const dateB = new Date(b.updated_at || 0);
                return dateB - dateA;
            });
            
            return sorted;
        });
        
        // Előnézet tartalom
        const formattedPreview = Vue.computed(() => {
            if (!editForm.value.content) return '';
            
            let preview = editForm.value.content;
            
            // Változók helyettesítése
            preview = preview.replace(/\{text\}/g, previewText.value || '...');
            preview = preview.replace(/\{user\}/g, window.store?.userName || 'User');
            preview = preview.replace(/\{date\}/g, new Date().toLocaleDateString());
            preview = preview.replace(/\{time\}/g, new Date().toLocaleTimeString());
            
            // Sortörések és formázás
            preview = preview.replace(/\n/g, '<br>');
            
            return preview;
        });
        
        // Tartalom hossza
        const contentLength = Vue.computed(() => editForm.value.content?.length || 0);
        
        // Token becslés (kb 4 karakter = 1 token)
        const estimatedTokens = Vue.computed(() => 
            Math.ceil((editForm.value.content?.length || 0) / 4)
        );
        
        // ====================================================================
        // METÓDUSOK
        // ====================================================================
        
        const gettext = (key, params = {}) => {
            return window.gettext ? window.gettext(key, params) : key;
        };
        
        const getPromptCategoryName = (category) => {
            const categories = {
                'king': gettext('prompts.category_king'),
                'queen': gettext('prompts.category_queen'),
                'general': gettext('prompts.category_general'),
                'expert': gettext('prompts.category_expert'),
                'custom': gettext('prompts.category_custom')
            };
            return categories[category] || category;
        };
        
        const truncate = (text, length) => {
            if (!text) return '';
            return text.length > length ? text.substring(0, length) + '…' : text;
        };
        
        const formatDate = (dateStr) => {
            if (!dateStr) return '';
            const date = new Date(dateStr);
            return date.toLocaleDateString();
        };
        
        const formatRelativeTime = (dateStr) => {
            if (!dateStr) return '';
            
            const date = new Date(dateStr);
            const now = new Date();
            const diffMs = now - date;
            const diffMins = Math.floor(diffMs / 60000);
            
            if (diffMins < 1) return gettext('time.just_now');
            if (diffMins < 60) return `${diffMins} ${gettext('time.min_ago')}`;
            if (diffMins < 1440) return `${Math.floor(diffMins / 60)} ${gettext('time.hours_ago')}`;
            
            return formatDate(dateStr);
        };
        
        const selectPrompt = (prompt) => {
            selectedPrompt.value = prompt;
            editForm.value = { ...prompt };
            previewText.value = '';
            contentError.value = '';
        };
        
        const createNew = () => {
            const newPrompt = {
                id: 'new_' + Date.now(),
                name: gettext('prompts.new_prompt'),
                content: gettext('prompts.default_content'),
                description: '',
                category: 'general',
                is_default: false,
                version: 1
            };
            selectPrompt(newPrompt);
        };
        
        const duplicatePrompt = () => {
            if (!selectedPrompt.value) return;
            
            const duplicate = {
                ...selectedPrompt.value,
                id: 'new_' + Date.now(),
                name: selectedPrompt.value.name + ' (' + gettext('prompts.copy') + ')',
                is_default: false,
                version: 1
            };
            selectPrompt(duplicate);
        };
        
        const validateContent = () => {
            const content = editForm.value.content;
            
            if (!content || content.trim().length === 0) {
                contentError.value = gettext('prompts.error_empty');
                return false;
            }
            
            // Ellenőrizzük a változók formátumát
            const matches = content.match(/\{[^}]+\}/g) || [];
            for (const match of matches) {
                const varName = match.slice(1, -1);
                if (!availableVariables[varName] && varName !== 'text') {
                    contentError.value = gettext('prompts.error_variable', { var: varName });
                    return false;
                }
            }
            
            contentError.value = '';
            return true;
        };
        
        const insertVariable = (varName) => {
            const textarea = document.querySelector('.prompt-textarea');
            if (!textarea) return;
            
            const start = textarea.selectionStart;
            const end = textarea.selectionEnd;
            const text = editForm.value.content;
            
            editForm.value.content = 
                text.substring(0, start) + 
                '{' + varName + '}' + 
                text.substring(end);
            
            // Visszaállítjuk a kurzor pozíciót
            Vue.nextTick(() => {
                textarea.selectionStart = textarea.selectionEnd = start + varName.length + 2;
                textarea.focus();
            });
        };
        
        const insertTemplate = (type) => {
            const templates = {
                basic: gettext('prompts.template_basic_content'),
                instruction: gettext('prompts.template_instruction_content'),
                fewshot: gettext('prompts.template_fewshot_content')
            };
            
            if (templates[type]) {
                editForm.value.content = (editForm.value.content || '') + '\n\n' + templates[type];
            }
        };
        
        const updatePreview = () => {
            // Automatikusan frissül a computed miatt
        };
        
        const refreshPreview = () => {
            previewLoading.value = true;
            setTimeout(() => {
                previewLoading.value = false;
            }, 100);
        };
        
        const testWithInput = () => {
            if (!editForm.value.content) return;
            
            // Itt lehetne elküldeni a promptot tesztelésre
            alert(gettext('prompts.test_not_implemented'));
        };
        
        const savePrompt = async () => {
            if (!isAdmin.value) return;
            if (!validateContent()) return;
            
            saving.value = true;
            
            try {
                if (window.api) {
                    const result = await window.api.savePrompt(editForm.value);
                    
                    if (result.success) {
                        // Verzió növelés
                        editForm.value.version = (editForm.value.version || 0) + 1;
                        
                        await refreshPrompts();
                        
                        window.socketManager?.addSystemMessage?.(
                            gettext('prompts.saved'),
                            'success'
                        );
                    }
                }
            } catch (error) {
                alert(gettext('prompts.save_error', { error: error.message }));
            } finally {
                saving.value = false;
            }
        };
        
        const deletePrompt = async () => {
            if (!isAdmin.value || selectedPrompt.value?.is_default) return;
            
            const message = gettext('prompts.confirm_delete', { name: selectedPrompt.value.name });
            if (!confirm(message)) return;
            
            saving.value = true;
            
            try {
                if (window.api) {
                    await window.api.deletePrompt(selectedPrompt.value.id);
                    selectedPrompt.value = null;
                    await refreshPrompts();
                    
                    window.socketManager?.addSystemMessage?.(
                        gettext('prompts.deleted'),
                        'success'
                    );
                }
            } catch (error) {
                alert(gettext('prompts.delete_error', { error: error.message }));
            } finally {
                saving.value = false;
            }
        };
        
        const refreshPrompts = async () => {
            refreshing.value = true;
            
            try {
                if (window.api) {
                    await window.api.getPrompts();
                }
            } finally {
                refreshing.value = false;
            }
        };
        
        const showHistory = async () => {
            if (!selectedPrompt.value) return;
            
            showHistoryModal.value = true;
            
            // Demo verziók
            promptVersions.value = [
                {
                    id: 1,
                    version: 3,
                    created_at: Date.now() - 86400000,
                    comment: gettext('prompts.version_improved')
                },
                {
                    id: 2,
                    version: 2,
                    created_at: Date.now() - 172800000,
                    comment: gettext('prompts.version_initial')
                }
            ];
        };
        
        const loadVersion = (version) => {
            currentVersion.value = version.id;
            // Itt lehetne betölteni a verzió tartalmát
        };
        
        const testPrompt = () => {
            // Itt lehetne tesztelni a promptot
            alert(gettext('prompts.test_not_implemented'));
        };
        
        return {
            // Állapotok
            prompts,
            isAdmin,
            loading,
            saving,
            refreshing,
            previewLoading,
            searchQuery,
            selectedCategory,
            sortBy,
            selectedPrompt,
            editForm,
            previewText,
            contentError,
            showVariablesHelp,
            availableVariables,
            showHistoryModal,
            promptVersions,
            currentVersion,
            
            // Computed
            filteredPrompts,
            filteredAndSortedPrompts,
            formattedPreview,
            contentLength,
            estimatedTokens,
            
            // Metódusok
            gettext,
            getPromptCategoryName,
            truncate,
            formatDate,
            formatRelativeTime,
            selectPrompt,
            createNew,
            duplicatePrompt,
            validateContent,
            insertVariable,
            insertTemplate,
            updatePreview,
            refreshPreview,
            testWithInput,
            savePrompt,
            deletePrompt,
            refreshPrompts,
            showHistory,
            loadVersion,
            testPrompt
        };
    }
};

window.PromptEditor = PromptEditor;
console.log('✅ PromptEditor betöltve globálisan');