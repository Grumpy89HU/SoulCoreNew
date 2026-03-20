// ==============================================
// SOULCORE 3.0 - Prompt szerkesztő komponens
// ==============================================

window.PromptEditor = {
    name: 'PromptEditor',
    
    template: `
        <div class="prompt-editor">
            <div class="prompt-list">
                <div 
                    v-for="prompt in prompts" 
                    :key="prompt.id"
                    class="prompt-item"
                    :class="{ active: selectedPrompt?.id === prompt.id }"
                    @click="selectPrompt(prompt)"
                >
                    <div class="prompt-name">{{ prompt.name }}</div>
                    <div class="prompt-preview">{{ truncate(prompt.content, 50) }}</div>
                    <div class="prompt-meta">
                        <span class="prompt-category">{{ prompt.category }}</span>
                        <span v-if="prompt.is_default" class="badge badge-info">{{ t('prompts.default') }}</span>
                    </div>
                </div>
            </div>
            
            <div v-if="selectedPrompt" class="prompt-editor-panel">
                <div class="editor-header">
                    <input 
                        type="text" 
                        v-model="editForm.name" 
                        class="form-input"
                        :placeholder="t('prompts.name')"
                    >
                    <select v-model="editForm.category" class="form-input">
                        <option value="general">{{ t('prompts.category_general') }}</option>
                        <option value="king">{{ t('prompts.category_king') }}</option>
                        <option value="queen">{{ t('prompts.category_queen') }}</option>
                    </select>
                </div>
                
                <textarea 
                    v-model="editForm.content" 
                    class="prompt-content"
                    rows="10"
                    :placeholder="t('prompts.content_placeholder')"
                ></textarea>
                
                <div class="editor-footer">
                    <label class="checkbox-label">
                        <input type="checkbox" v-model="editForm.is_default">
                        {{ t('prompts.set_default') }}
                    </label>
                    
                    <div class="editor-actions">
                        <button class="btn btn-secondary" @click="cancelEdit">
                            {{ t('ui.cancel') }}
                        </button>
                        <button class="btn btn-primary" @click="savePrompt" :disabled="saving">
                            <span v-if="!saving">{{ t('ui.save') }}</span>
                            <span v-else class="spinner-small"></span>
                        </button>
                    </div>
                </div>
            </div>
            
            <div v-else class="empty-state">
                <div class="empty-icon">📝</div>
                <div class="empty-text">{{ t('prompts.select_or_create') }}</div>
                <button class="btn btn-primary" @click="createNew">
                    + {{ t('prompts.new') }}
                </button>
            </div>
        </div>
    `,
    
    setup() {
        const prompts = Vue.computed(() => window.store.prompts);
        const selectedPrompt = Vue.ref(null);
        const editForm = Vue.ref({
            id: null,
            name: '',
            content: '',
            category: 'general',
            is_default: false
        });
        const saving = Vue.ref(false);
        
        const t = (key, params = {}) => {
            return window.gettext ? window.gettext(key, params) : key;
        };
        
        const truncate = (text, length) => {
            if (window.formatters) {
                return window.formatters.truncate(text, length);
            }
            return text;
        };
        
        const loadPrompts = async () => {
            try {
                await window.api.getPrompts();
            } catch (error) {
                console.error('Hiba a promptok betöltésekor:', error);
            }
        };
        
        const selectPrompt = (prompt) => {
            selectedPrompt.value = prompt;
            editForm.value = { ...prompt };
        };
        
        const createNew = () => {
            selectedPrompt.value = {
                id: null,
                name: '',
                content: '',
                category: 'general',
                is_default: false
            };
            editForm.value = { ...selectedPrompt.value };
        };
        
        const cancelEdit = () => {
            if (selectedPrompt.value?.id) {
                selectPrompt(selectedPrompt.value);
            } else {
                selectedPrompt.value = null;
                editForm.value = {
                    id: null,
                    name: '',
                    content: '',
                    category: 'general',
                    is_default: false
                };
            }
        };
        
        const savePrompt = async () => {
            if (!editForm.value.name.trim()) {
                window.store.addNotification('warning', t('prompts.error_name_required'));
                return;
            }
            
            if (!editForm.value.content.trim()) {
                window.store.addNotification('warning', t('prompts.error_content_required'));
                return;
            }
            
            saving.value = true;
            try {
                await window.api.savePrompt(editForm.value);
                window.store.addNotification('success', t('prompts.saved'));
                await loadPrompts();
                
                if (editForm.value.id) {
                    const updated = window.store.prompts.find(p => p.id === editForm.value.id);
                    if (updated) selectPrompt(updated);
                } else {
                    selectedPrompt.value = null;
                    editForm.value = {
                        id: null,
                        name: '',
                        content: '',
                        category: 'general',
                        is_default: false
                    };
                }
            } catch (error) {
                console.error('Hiba a prompt mentésekor:', error);
                window.store.addNotification('error', t('prompts.save_error'));
            } finally {
                saving.value = false;
            }
        };
        
        Vue.onMounted(() => {
            loadPrompts();
        });
        
        return {
            prompts,
            selectedPrompt,
            editForm,
            saving,
            t,
            truncate,
            selectPrompt,
            createNew,
            cancelEdit,
            savePrompt
        };
    }
};

console.log('✅ PromptEditor komponens betöltve');