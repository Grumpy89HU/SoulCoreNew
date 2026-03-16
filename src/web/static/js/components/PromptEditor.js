// Prompt szerkesztő komponens
const PromptEditor = {
    template: `
        <div class="prompt-editor">
            <div class="prompt-toolbar">
                <select v-model="selectedCategory" class="category-select">
                    <option value="all">Minden kategória</option>
                    <option value="king">Király</option>
                    <option value="queen">Királynő</option>
                    <option value="general">Általános</option>
                    <option value="expert">Szakértő</option>
                </select>
                
                <button class="btn-primary" @click="createNew" v-if="isAdmin">
                    + Új prompt
                </button>
            </div>
            
            <div class="prompt-list">
                <div v-for="prompt in filteredPrompts" :key="prompt.id" 
                     class="prompt-item" :class="{ active: selectedPrompt?.id == prompt.id }"
                     @click="selectPrompt(prompt)">
                    
                    <div class="prompt-item-header">
                        <span class="prompt-name">{{ prompt.name }}</span>
                        <span class="prompt-badge" v-if="prompt.is_default">Alapértelmezett</span>
                    </div>
                    
                    <div class="prompt-category">{{ prompt.category }}</div>
                    <div class="prompt-preview">{{ prompt.content.substring(0, 100) }}...</div>
                </div>
            </div>
            
            <!-- Szerkesztő panel -->
            <div class="prompt-edit-panel" v-if="selectedPrompt">
                <div class="edit-header">
                    <h3>Prompt szerkesztése</h3>
                    <div class="edit-actions" v-if="isAdmin">
                        <button class="control-btn" @click="savePrompt" :disabled="saving">
                            💾 Mentés
                        </button>
                        <button class="control-btn stop" @click="deletePrompt" 
                                v-if="!selectedPrompt.is_default" :disabled="saving">
                            🗑️ Törlés
                        </button>
                    </div>
                </div>
                
                <div class="form-group">
                    <label>Név</label>
                    <input type="text" v-model="editForm.name" class="form-input" 
                           :disabled="!isAdmin">
                </div>
                
                <div class="form-group">
                    <label>Kategória</label>
                    <select v-model="editForm.category" class="form-input" :disabled="!isAdmin">
                        <option value="king">Király</option>
                        <option value="queen">Királynő</option>
                        <option value="general">Általános</option>
                        <option value="expert">Szakértő</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label>Leírás</label>
                    <input type="text" v-model="editForm.description" class="form-input" 
                           :disabled="!isAdmin">
                </div>
                
                <div class="form-group">
                    <label>Prompt tartalom</label>
                    <div class="variable-hint">
                        Változók: <code>{text}</code> - felhasználói üzenet
                    </div>
                    <textarea v-model="editForm.content" class="prompt-textarea" 
                              rows="15" :disabled="!isAdmin"></textarea>
                </div>
                
                <div class="form-group" v-if="isAdmin">
                    <label>
                        <input type="checkbox" v-model="editForm.is_default">
                        Alapértelmezett prompt
                    </label>
                </div>
                
                <!-- Előnézet -->
                <div class="prompt-preview-section">
                    <h4>Előnézet</h4>
                    <div class="preview-box">
                        {{ previewContent }}
                    </div>
                </div>
            </div>
        </div>
    `,
    
    setup() {
        const prompts = Vue.computed(() => store.prompts);
        const isAdmin = Vue.computed(() => store.isAdmin);
        const selectedCategory = Vue.ref('all');
        const selectedPrompt = Vue.ref(null);
        const saving = Vue.ref(false);
        
        const editForm = Vue.ref({
            id: null,
            name: '',
            content: '',
            description: '',
            category: 'general',
            is_default: false
        });
        
        const filteredPrompts = Vue.computed(() => {
            if (selectedCategory.value === 'all') return prompts.value;
            return prompts.value.filter(p => p.category === selectedCategory.value);
        });
        
        const previewContent = Vue.computed(() => {
            if (!editForm.value.content) return '';
            return editForm.value.content.replace('{text}', 'Ez egy teszt üzenet...');
        });
        
        const selectPrompt = (prompt) => {
            selectedPrompt.value = prompt;
            editForm.value = { ...prompt };
        };
        
        const createNew = () => {
            selectedPrompt.value = {
                id: 'new',
                name: 'Új prompt',
                content: 'Felhasználó: {text}\n\nVálasz:',
                description: '',
                category: 'general',
                is_default: false
            };
            editForm.value = { ...selectedPrompt.value };
        };
        
        const savePrompt = async () => {
            if (!isAdmin.value) return;
            
            saving.value = true;
            try {
                const result = await api.savePrompt(editForm.value);
                if (result.success) {
                    alert('Prompt mentve!');
                    api.getPrompts();
                }
            } catch (error) {
                alert('Hiba a mentés során: ' + error.message);
            } finally {
                saving.value = false;
            }
        };
        
        const deletePrompt = async () => {
            if (!isAdmin.value || selectedPrompt.value.is_default) return;
            
            if (confirm('Biztosan törlöd ezt a promptot?')) {
                saving.value = true;
                try {
                    await api.deletePrompt(selectedPrompt.value.id);
                    selectedPrompt.value = null;
                    api.getPrompts();
                } catch (error) {
                    alert('Hiba a törlés során: ' + error.message);
                } finally {
                    saving.value = false;
                }
            }
        };
        
        return {
            prompts,
            isAdmin,
            selectedCategory,
            selectedPrompt,
            editForm,
            saving,
            filteredPrompts,
            previewContent,
            selectPrompt,
            createNew,
            savePrompt,
            deletePrompt
        };
    }
};
window.PromptEditor = PromptEditor;