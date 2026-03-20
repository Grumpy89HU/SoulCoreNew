// ==============================================
// SOULCORE 3.0 - Prompt szerkesztő komponens
// ==============================================

window.PromptEditor = {
    name: 'PromptEditor',
    
    template: `
        <div class="prompt-editor">
            <!-- Fejléc -->
            <div class="prompt-header">
                <div class="header-title">
                    <h3>{{ t('prompts.title') }}</h3>
                    <span class="prompt-count" v-if="prompts.length">({{ prompts.length }})</span>
                </div>
                <div class="header-actions">
                    <input 
                        type="text" 
                        v-model="searchQuery" 
                        :placeholder="t('prompts.search')"
                        class="search-input"
                    >
                    <select v-model="selectedCategory" class="category-select">
                        <option value="all">{{ t('prompts.all_categories') }}</option>
                        <option value="king">{{ t('prompts.category_king') }}</option>
                        <option value="queen">{{ t('prompts.category_queen') }}</option>
                        <option value="general">{{ t('prompts.category_general') }}</option>
                        <option value="expert">{{ t('prompts.category_expert') }}</option>
                        <option value="custom">{{ t('prompts.category_custom') }}</option>
                    </select>
                    <button class="refresh-btn" @click="refreshPrompts" :disabled="refreshing">
                        <span :class="{ 'spin': refreshing }">🔄</span>
                    </button>
                    <button class="btn-primary" @click="createNew" v-if="isAdmin">
                        + {{ t('prompts.new') }}
                    </button>
                </div>
            </div>
            
            <div class="prompt-main" :class="{ 'split-view': selectedPrompt }">
                <!-- Prompt lista -->
                <div class="prompt-list-container">
                    <div class="prompt-list-header">
                        <span>{{ t('prompts.list') }}</span>
                    </div>
                    <div class="prompt-list">
                        <div v-for="prompt in filteredPrompts" :key="prompt.id" 
                             class="prompt-item" 
                             :class="{ 
                                 active: selectedPrompt?.id === prompt.id,
                                 'default': prompt.is_default
                             }"
                             @click="selectPrompt(prompt)">
                            <div class="prompt-item-header">
                                <div class="prompt-title">
                                    <span class="prompt-name">{{ prompt.name }}</span>
                                    <span class="prompt-badge" v-if="prompt.is_default">
                                        ⭐ {{ t('prompts.default') }}
                                    </span>
                                    <span class="prompt-badge" v-if="prompt.version > 1">
                                        v{{ prompt.version }}
                                    </span>
                                </div>
                                <div class="prompt-meta">
                                    <span class="prompt-category">{{ getCategoryName(prompt.category) }}</span>
                                    <span class="prompt-date" :title="formatDate(prompt.updated_at)">
                                        🕒 {{ formatRelativeTime(prompt.updated_at) }}
                                    </span>
                                </div>
                            </div>
                            <div class="prompt-preview">{{ truncate(prompt.content, 80) }}</div>
                            <div class="prompt-stats" v-if="prompt.usage_count">
                                <span>📊 {{ prompt.usage_count }} {{ t('prompts.uses') }}</span>
                            </div>
                        </div>
                        <div v-if="filteredPrompts.length === 0" class="empty-list">
                            <div class="empty-icon">📝</div>
                            <div class="empty-text">{{ t('prompts.no_prompts') }}</div>
                            <button class="btn-primary" @click="createNew" v-if="isAdmin">
                                + {{ t('prompts.create_first') }}
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
                            <button class="icon-btn" @click="duplicatePrompt" :title="t('prompts.duplicate')">
                                📋
                            </button>
                            <button class="icon-btn" @click="showHistory" :title="t('prompts.history')">
                                📜
                            </button>
                            <button class="icon-btn" @click="testPrompt" :title="t('prompts.test')">
                                🧪
                            </button>
                            <button class="control-btn" @click="savePrompt" :disabled="saving">
                                <span v-if="!saving">💾 {{ t('ui.save') }}</span>
                                <span v-else class="spinner-small"></span>
                            </button>
                            <button class="control-btn stop" @click="deletePrompt" 
                                    v-if="!selectedPrompt.is_default" :disabled="saving">
                                🗑️ {{ t('ui.delete') }}
                            </button>
                        </div>
                    </div>
                    
                    <!-- Alapadatok -->
                    <div class="edit-basic">
                        <div class="form-row">
                            <div class="form-group">
                                <label>{{ t('prompts.name') }} *</label>
                                <input type="text" v-model="editForm.name" class="form-input" 
                                       :disabled="!isAdmin || loading">
                            </div>
                            <div class="form-group">
                                <label>{{ t('prompts.category') }}</label>
                                <select v-model="editForm.category" class="form-input" :disabled="!isAdmin">
                                    <option value="king">{{ t('prompts.category_king') }}</option>
                                    <option value="queen">{{ t('prompts.category_queen') }}</option>
                                    <option value="general">{{ t('prompts.category_general') }}</option>
                                    <option value="expert">{{ t('prompts.category_expert') }}</option>
                                    <option value="custom">{{ t('prompts.category_custom') }}</option>
                                </select>
                            </div>
                        </div>
                        <div class="form-group">
                            <label>{{ t('prompts.description') }}</label>
                            <input type="text" v-model="editForm.description" class="form-input" 
                                   :disabled="!isAdmin" :placeholder="t('prompts.description_placeholder')">
                        </div>
                    </div>
                    
                    <!-- Változók panel -->
                    <div class="variables-panel">
                        <div class="panel-header">
                            <span>{{ t('prompts.variables') }}</span>
                            <button class="small-btn" @click="showVariablesHelp = !showVariablesHelp">❓</button>
                        </div>
                        <div class="variables-list">
                            <div v-for="(desc, varName) in variableList" 
                                 :key="varName" 
                                 class="variable-chip"
                                 @click="insertVariable(varName)"
                                 :title="desc">
                                <code>{{ '{' + varName + '}' }}</code>
                            </div>
                        </div>
                        <div v-if="showVariablesHelp" class="variables-help">
                            {{ t('prompts.variables_help') }}
                        </div>
                    </div>
                    
                    <!-- Prompt tartalom -->
                    <div class="edit-content">
                        <div class="content-header">
                            <label>{{ t('prompts.content') }} *</label>
                            <div class="content-stats">
                                <span>📏 {{ contentLength }} {{ t('prompts.chars') }}</span>
                                <span>🔤 {{ estimatedTokens }} {{ t('prompts.tokens') }}</span>
                            </div>
                        </div>
                        <textarea 
                            v-model="editForm.content" 
                            class="prompt-textarea" 
                            :class="{ 'has-error': contentError }"
                            rows="12" 
                            :disabled="!isAdmin"
                            @input="validateContent"
                            :placeholder="t('prompts.content_placeholder')"
                        ></textarea>
                        <div v-if="contentError" class="content-error">
                            ⚠️ {{ contentError }}
                        </div>
                        
                        <!-- Gyors sablonok -->
                        <div class="quick-templates" v-if="isAdmin">
                            <span class="label">{{ t('prompts.templates') }}:</span>
                            <button class="template-btn" @click="insertTemplate('basic')">
                                💬 {{ t('prompts.template_basic') }}
                            </button>
                            <button class="template-btn" @click="insertTemplate('instruction')">
                                📋 {{ t('prompts.template_instruction') }}
                            </button>
                            <button class="template-btn" @click="insertTemplate('fewshot')">
                                🔢 {{ t('prompts.template_fewshot') }}
                            </button>
                            <button class="template-btn" @click="insertTemplate('system')">
                                ⚙️ {{ t('prompts.template_system') }}
                            </button>
                        </div>
                    </div>
                    
                    <!-- Opciók -->
                    <div class="edit-options">
                        <label class="checkbox-label">
                            <input type="checkbox" v-model="editForm.is_default" :disabled="!isAdmin">
                            {{ t('prompts.set_default') }}
                        </label>
                        <div class="token-estimate" v-if="editForm.content">
                            <span class="label">{{ t('prompts.estimated_cost') }}:</span>
                            <span class="value">≈ {{ (estimatedTokens * 0.002).toFixed(4) }} ({{ estimatedTokens }} tk)</span>
                        </div>
                    </div>
                    
                    <!-- Előnézet -->
                    <div class="preview-section">
                        <div class="preview-header">
                            <span>{{ t('prompts.preview') }}</span>
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
                                :placeholder="t('prompts.test_input')"
                                class="preview-input"
                                @input="updatePreview"
                            >
                            <button class="small-btn" @click="testWithInput">🧪</button>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Verziótörténet modal -->
            <div class="modal" v-if="showHistoryModal">
                <div class="modal-content">
                    <div class="modal-header">
                        <h3>{{ t('prompts.history') }} - {{ selectedPrompt?.name }}</h3>
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
                                <div class="version-comment">{{ version.comment || t('prompts.no_comment') }}</div>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn-secondary" @click="showHistoryModal = false">
                            {{ t('ui.close') }}
                        </button>
                    </div>
                </div>
            </div>
            
            <!-- Teszt modal -->
            <div class="modal" v-if="showTestModal">
                <div class="modal-content large">
                    <div class="modal-header">
                        <h3>{{ t('prompts.test') }} - {{ selectedPrompt?.name }}</h3>
                        <button class="close-btn" @click="showTestModal = false">✕</button>
                    </div>
                    <div class="modal-body">
                        <div class="form-group">
                            <label>{{ t('prompts.test_input') }}</label>
                            <textarea v-model="testInput" rows="3" class="form-input" 
                                      :placeholder="t('prompts.test_input_placeholder')"></textarea>
                        </div>
                        <div class="form-group">
                            <label>{{ t('prompts.test_output') }}</label>
                            <div class="test-output">{{ testOutput || t('prompts.test_click') }}</div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn-secondary" @click="showTestModal = false">
                            {{ t('ui.close') }}
                        </button>
                        <button class="btn-primary" @click="runTest" :disabled="testing">
                            <span v-if="!testing">🧪 {{ t('prompts.run_test') }}</span>
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
        
        const prompts = Vue.computed(() => window.store.prompts || []);
        const isAdmin = Vue.computed(() => window.store.user?.role === 'admin');
        
        // UI állapotok
        const loading = Vue.ref(false);
        const saving = Vue.ref(false);
        const refreshing = Vue.ref(false);
        const previewLoading = Vue.ref(false);
        const testing = Vue.ref(false);
        
        // Keresés és szűrés
        const searchQuery = Vue.ref('');
        const selectedCategory = Vue.ref('all');
        
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
        
        // Hibák
        const contentError = Vue.ref('');
        
        // Változók
        const showVariablesHelp = Vue.ref(false);
        const variableList = {
            'text': 'Felhasználó aktuális üzenete',
            'user': 'Felhasználó neve',
            'date': 'Aktuális dátum',
            'time': 'Aktuális idő',
            'context': 'Beszélgetés kontextus',
            'history': 'Üzenet előzmények',
            'personality': 'Aktív személyiség',
            'model': 'Aktív modell neve'
        };
        
        // Verziótörténet
        const showHistoryModal = Vue.ref(false);
        const promptVersions = Vue.ref([]);
        const currentVersion = Vue.ref(null);
        
        // Teszt
        const showTestModal = Vue.ref(false);
        const testInput = Vue.ref('');
        const testOutput = Vue.ref('');
        
        // ====================================================================
        // SEGÉDFÜGGVÉNYEK
        // ====================================================================
        
        const t = (key, params = {}) => {
            return window.gettext ? window.gettext(key, params) : key;
        };
        
        const truncate = (text, length) => window.truncate(text, length);
        const formatDate = (ts) => window.formatDate(ts);
        const formatRelativeTime = (ts) => window.formatRelativeTime(ts);
        
        // ====================================================================
        // COMPUTED PROPERTIES
        // ====================================================================
        
        const filteredPrompts = Vue.computed(() => {
            let filtered = prompts.value;
            
            if (selectedCategory.value !== 'all') {
                filtered = filtered.filter(p => p.category === selectedCategory.value);
            }
            
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
        
        const formattedPreview = Vue.computed(() => {
            if (!editForm.value.content) return '';
            
            let preview = editForm.value.content;
            preview = preview.replace(/\{text\}/g, previewText.value || '...');
            preview = preview.replace(/\{user\}/g, window.store.user?.username || 'User');
            preview = preview.replace(/\{date\}/g, new Date().toLocaleDateString());
            preview = preview.replace(/\{time\}/g, new Date().toLocaleTimeString());
            preview = preview.replace(/\{context\}/g, '[Beszélgetés kontextus]');
            preview = preview.replace(/\{history\}/g, '[Üzenet előzmények]');
            preview = preview.replace(/\{personality\}/g, '[Aktív személyiség]');
            preview = preview.replace(/\{model\}/g, window.store.currentModel?.name || 'Ismeretlen');
            preview = preview.replace(/\n/g, '<br>');
            
            return preview;
        });
        
        const contentLength = Vue.computed(() => editForm.value.content?.length || 0);
        const estimatedTokens = Vue.computed(() => Math.ceil((editForm.value.content?.length || 0) / 4));
        
        // ====================================================================
        // METÓDUSOK
        // ====================================================================
        
        const getCategoryName = (category) => {
            const names = {
                'king': t('prompts.category_king'),
                'queen': t('prompts.category_queen'),
                'general': t('prompts.category_general'),
                'expert': t('prompts.category_expert'),
                'custom': t('prompts.category_custom')
            };
            return names[category] || category;
        };
        
        const selectPrompt = (prompt) => {
            selectedPrompt.value = prompt;
            editForm.value = { ...prompt };
            previewText.value = '';
            contentError.value = '';
        };
        
        const createNew = () => {
            const newPrompt = {
                id: null,
                name: t('prompts.new_prompt'),
                content: t('prompts.default_content'),
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
                id: null,
                name: selectedPrompt.value.name + ' (' + t('prompts.copy') + ')',
                is_default: false,
                version: 1
            };
            selectPrompt(duplicate);
        };
        
        const validateContent = () => {
            const content = editForm.value.content;
            if (!content || content.trim().length === 0) {
                contentError.value = t('prompts.error_empty');
                return false;
            }
            
            const matches = content.match(/\{[^}]+\}/g) || [];
            for (const match of matches) {
                const varName = match.slice(1, -1);
                if (!variableList[varName] && !['text', 'user', 'date', 'time', 'context', 'history', 'personality', 'model'].includes(varName)) {
                    contentError.value = t('prompts.error_variable', { var: varName });
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
            
            Vue.nextTick(() => {
                textarea.selectionStart = textarea.selectionEnd = start + varName.length + 2;
                textarea.focus();
            });
        };
        
        const insertTemplate = (type) => {
            const templates = {
                basic: t('prompts.template_basic_content'),
                instruction: t('prompts.template_instruction_content'),
                fewshot: t('prompts.template_fewshot_content'),
                system: t('prompts.template_system_content')
            };
            
            if (templates[type]) {
                editForm.value.content = (editForm.value.content || '') + '\n\n' + templates[type];
            }
        };
        
        const updatePreview = () => {};
        const refreshPreview = () => {
            previewLoading.value = true;
            setTimeout(() => { previewLoading.value = false; }, 100);
        };
        
        const savePrompt = async () => {
            if (!isAdmin.value) return;
            if (!validateContent()) return;
            
            saving.value = true;
            try {
                await window.api.savePrompt(editForm.value);
                window.store.addNotification('success', t('prompts.saved'));
                await refreshPrompts();
                
                if (editForm.value.id) {
                    const updated = window.store.prompts.find(p => p.id === editForm.value.id);
                    if (updated) selectPrompt(updated);
                } else {
                    selectedPrompt.value = null;
                }
            } catch (error) {
                console.error('Error saving prompt:', error);
                window.store.addNotification('error', t('prompts.save_error'));
            } finally {
                saving.value = false;
            }
        };
        
        const deletePrompt = async () => {
            if (!isAdmin.value || selectedPrompt.value?.is_default) return;
            if (!confirm(t('prompts.confirm_delete', { name: selectedPrompt.value.name }))) return;
            
            saving.value = true;
            try {
                await window.api.deletePrompt(selectedPrompt.value.id);
                window.store.addNotification('success', t('prompts.deleted'));
                selectedPrompt.value = null;
                await refreshPrompts();
            } catch (error) {
                console.error('Error deleting prompt:', error);
                window.store.addNotification('error', t('prompts.delete_error'));
            } finally {
                saving.value = false;
            }
        };
        
        const refreshPrompts = async () => {
            refreshing.value = true;
            try {
                await window.api.getPrompts();
            } finally {
                refreshing.value = false;
            }
        };
        
        const showHistory = async () => {
            if (!selectedPrompt.value) return;
            showHistoryModal.value = true;
            promptVersions.value = [
                { id: 1, version: 3, created_at: Date.now() - 86400000, comment: t('prompts.version_improved') },
                { id: 2, version: 2, created_at: Date.now() - 172800000, comment: t('prompts.version_initial') }
            ];
        };
        
        const loadVersion = (version) => { currentVersion.value = version.id; };
        const testPrompt = () => {
            if (!selectedPrompt.value) return;
            testInput.value = '';
            testOutput.value = '';
            showTestModal.value = true;
        };
        
        const runTest = async () => {
            if (!testInput.value.trim()) {
                window.store.addNotification('warning', t('prompts.test_input_required'));
                return;
            }
            
            testing.value = true;
            try {
                let output = editForm.value.content;
                output = output.replace(/\{text\}/g, testInput.value);
                output = output.replace(/\{user\}/g, window.store.user?.username || 'User');
                output = output.replace(/\{date\}/g, new Date().toLocaleDateString());
                output = output.replace(/\{time\}/g, new Date().toLocaleTimeString());
                testOutput.value = output;
                window.store.addNotification('success', t('prompts.test_complete'));
            } catch (error) {
                testOutput.value = t('prompts.test_error');
            } finally {
                testing.value = false;
            }
        };
        
        const testWithInput = () => {
            if (!editForm.value.content) return;
            testInput.value = previewText.value;
            runTest();
        };
        
        Vue.onMounted(() => { refreshPrompts(); });
        
        return {
            prompts, isAdmin, loading, saving, refreshing, previewLoading, testing,
            searchQuery, selectedCategory, selectedPrompt, editForm, previewText,
            contentError, showVariablesHelp, variableList, showHistoryModal,
            promptVersions, currentVersion, showTestModal, testInput, testOutput,
            filteredPrompts, formattedPreview, contentLength, estimatedTokens,
            t, truncate, formatDate, formatRelativeTime, getCategoryName, validateContent,
            selectPrompt, createNew, duplicatePrompt, insertVariable, insertTemplate,
            updatePreview, refreshPreview, savePrompt, deletePrompt, refreshPrompts,
            showHistory, loadVersion, testPrompt, runTest, testWithInput
        };
    }
};

console.log('✅ PromptEditor komponens betöltve');