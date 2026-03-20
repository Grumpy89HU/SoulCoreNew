// ==============================================
// SOULCORE 3.0 - Kép feltöltés és feldolgozás
// ==============================================

window.VisionUpload = {
    name: 'VisionUpload',
    
    template: `
        <div class="vision-panel">
            <div class="vision-header">
                <h3>{{ t('vision.title') }}</h3>
                <p>{{ t('vision.description') }}</p>
            </div>
            
            <!-- Feltöltési terület -->
            <div class="upload-area" 
                 :class="{ 'drag-over': dragOver }"
                 @dragover.prevent="dragOver = true"
                 @dragleave.prevent="dragOver = false"
                 @drop.prevent="handleDrop"
                 @click="triggerFileInput">
                <div class="upload-icon">📷</div>
                <div class="upload-text">{{ t('vision.drag_drop') }}</div>
                <div class="upload-hint">{{ t('vision.or_click') }}</div>
                <input type="file" ref="fileInput" accept="image/*" multiple style="display: none" @change="handleFiles">
            </div>
            
            <!-- Feltöltött képek listája -->
            <div v-if="images.length" class="image-list">
                <div v-for="(img, idx) in images" :key="idx" class="image-item">
                    <img :src="img.preview" class="image-preview" @click="processImage(img)">
                    <div class="image-info">
                        <div class="image-name">{{ img.name }}</div>
                        <div class="image-size">{{ formatBytes(img.size) }}</div>
                        <div class="image-status" :class="img.status">
                            {{ getStatusText(img.status) }}
                        </div>
                    </div>
                    <button class="remove-btn" @click.stop="removeImage(idx)">✕</button>
                </div>
            </div>
            
            <!-- Feldolgozási eredmények -->
            <div v-if="results.length" class="results-section">
                <div class="results-header">
                    <h4>{{ t('vision.results') }}</h4>
                    <button class="clear-btn" @click="clearResults">✕</button>
                </div>
                <div v-for="(res, idx) in results" :key="idx" class="result-item">
                    <div class="result-image">
                        <img :src="res.preview" class="result-thumb">
                    </div>
                    <div class="result-content">
                        <div class="result-description" v-if="res.description">
                            <strong>{{ t('vision.description') }}:</strong>
                            <p>{{ res.description }}</p>
                        </div>
                        <div class="result-ocr" v-if="res.ocr_text">
                            <strong>{{ t('vision.ocr') }}:</strong>
                            <p>{{ res.ocr_text }}</p>
                        </div>
                        <div class="result-entities" v-if="res.entities?.length">
                            <strong>{{ t('vision.entities') }}:</strong>
                            <div class="entity-tags">
                                <span v-for="ent in res.entities" :key="ent" class="entity-tag">{{ ent }}</span>
                            </div>
                        </div>
                        <div class="result-actions">
                            <button class="btn-sm btn-secondary" @click="copyResult(res)">
                                📋 {{ t('vision.copy') }}
                            </button>
                            <button class="btn-sm btn-secondary" @click="insertToChat(res)">
                                💬 {{ t('vision.insert_to_chat') }}
                            </button>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Beállítások -->
            <div class="vision-settings">
                <details>
                    <summary>{{ t('vision.settings') }}</summary>
                    <div class="setting-item">
                        <label>{{ t('vision.engine') }}</label>
                        <select v-model="settings.engine">
                            <option value="moondream">Moondream</option>
                            <option value="llava">LLaVA</option>
                            <option value="cogvlm">CogVLM</option>
                        </select>
                    </div>
                    <div class="setting-item">
                        <label>{{ t('vision.enable_ocr') }}</label>
                        <input type="checkbox" v-model="settings.enable_ocr">
                    </div>
                    <div class="setting-item">
                        <label>{{ t('vision.enable_object_detection') }}</label>
                        <input type="checkbox" v-model="settings.enable_object_detection">
                    </div>
                </details>
            </div>
        </div>
    `,
    
    setup() {
        const images = Vue.ref([]);
        const results = Vue.ref([]);
        const dragOver = Vue.ref(false);
        const fileInput = Vue.ref(null);
        
        const settings = Vue.ref({
            engine: 'moondream',
            enable_ocr: true,
            enable_object_detection: true
        });
        
        const t = (key, params = {}) => window.gettext(key, params);
        const formatBytes = (b) => window.formatBytes(b);
        
        const getStatusText = (status) => {
            const texts = {
                pending: t('vision.pending'),
                processing: t('vision.processing'),
                completed: t('vision.completed'),
                error: t('vision.error')
            };
            return texts[status] || status;
        };
        
        const triggerFileInput = () => {
            fileInput.value?.click();
        };
        
        const handleDrop = (e) => {
            dragOver.value = false;
            const files = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith('image/'));
            addImages(files);
        };
        
        const handleFiles = (e) => {
            const files = Array.from(e.target.files).filter(f => f.type.startsWith('image/'));
            addImages(files);
            e.target.value = '';
        };
        
        const addImages = (files) => {
            files.forEach(file => {
                const reader = new FileReader();
                reader.onload = (ev) => {
                    images.value.push({
                        id: Date.now() + Math.random(),
                        file: file,
                        name: file.name,
                        size: file.size,
                        preview: ev.target.result,
                        status: 'pending',
                        data: null
                    });
                };
                reader.readAsDataURL(file);
            });
        };
        
        const processImage = async (img) => {
            img.status = 'processing';
            
            try {
                const result = await window.api.processImage(img.data || img.preview, {
                    engine: settings.value.engine,
                    ocr: settings.value.enable_ocr,
                    object_detection: settings.value.enable_object_detection
                });
                
                img.status = 'completed';
                results.value.unshift({
                    id: img.id,
                    preview: img.preview,
                    name: img.name,
                    description: result.description,
                    ocr_text: result.ocr_text,
                    entities: result.entities || []
                });
            } catch (error) {
                console.error('Error processing image:', error);
                img.status = 'error';
                window.store.addNotification('error', t('vision.process_error'));
            }
        };
        
        const removeImage = (idx) => {
            images.value.splice(idx, 1);
        };
        
        const clearResults = () => {
            results.value = [];
        };
        
        const copyResult = (result) => {
            let text = '';
            if (result.description) text += result.description + '\n';
            if (result.ocr_text) text += result.ocr_text;
            navigator.clipboard.writeText(text);
            window.store.addNotification('success', t('vision.copied'));
        };
        
        const insertToChat = (result) => {
            let text = `🖼️ **Kép feldolgozás eredménye:**\n\n`;
            if (result.description) text += `${result.description}\n\n`;
            if (result.ocr_text) text += `**OCR szöveg:**\n${result.ocr_text}`;
            
            // Beszúrás a chat inputba
            const chatBox = document.querySelector('.chat-input');
            if (chatBox) {
                chatBox.value = (chatBox.value ? chatBox.value + '\n\n' : '') + text;
                chatBox.dispatchEvent(new Event('input'));
                chatBox.focus();
            }
        };
        
        return {
            images,
            results,
            dragOver,
            fileInput,
            settings,
            t,
            formatBytes,
            getStatusText,
            triggerFileInput,
            handleDrop,
            handleFiles,
            processImage,
            removeImage,
            clearResults,
            copyResult,
            insertToChat
        };
    }
};

console.log('✅ VisionUpload komponens betöltve');