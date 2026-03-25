// ==============================================
// SOULCORE 3.0 - Embedding motor és Reranker
// ==============================================

window.EmbeddingPanel = {
    name: 'EmbeddingPanel',
    
    template: `
        <div class="embedding-panel">
            <div class="embedding-header">
                <h3>{{ t('embedding.title') }}</h3>
                <p>{{ t('embedding.description') }}</p>
            </div>
            
            <!-- Embedding motor -->
            <div class="settings-section">
                <h4>{{ t('embedding.embedding_engine') }}</h4>
                <div class="setting-item">
                    <label>{{ t('embedding.engine') }}</label>
                    <select v-model="settings.embedding_engine" @change="saveSettings">
                        <option value="sentence-transformers">Sentence Transformers</option>
                        <option value="openai">OpenAI Embeddings</option>
                        <option value="cohere">Cohere Embeddings</option>
                        <option value="voyage">Voyage AI</option>
                        <option value="local">Local (Ollama)</option>
                    </select>
                </div>
                
                <div class="setting-item" v-if="settings.embedding_engine === 'sentence-transformers'">
                    <label>{{ t('embedding.model') }}</label>
                    <select v-model="settings.embedding_model" @change="saveSettings">
                        <option value="all-MiniLM-L6-v2">all-MiniLM-L6-v2 (384 dim)</option>
                        <option value="all-mpnet-base-v2">all-mpnet-base-v2 (768 dim)</option>
                        <option value="multi-qa-mpnet-base-dot-v1">multi-qa-mpnet-base-dot-v1 (768 dim)</option>
                        <option value="gte-large">gte-large (1024 dim)</option>
                    </select>
                </div>
                
                <div class="setting-item" v-if="settings.embedding_engine === 'openai'">
                    <label>{{ t('embedding.api_key') }}</label>
                    <input type="password" v-model="settings.openai_key" @change="saveSettings" 
                           :placeholder="t('embedding.api_key_placeholder')">
                </div>
                
                <div class="setting-item" v-if="settings.embedding_engine === 'local'">
                    <label>{{ t('embedding.endpoint') }}</label>
                    <input type="text" v-model="settings.local_endpoint" @change="saveSettings" 
                           placeholder="http://localhost:11434/api/embeddings">
                    <label>{{ t('embedding.model') }}</label>
                    <input type="text" v-model="settings.local_model" @change="saveSettings" 
                           placeholder="nomic-embed-text">
                </div>
                
                <div class="setting-item">
                    <label>{{ t('embedding.batch_size') }}</label>
                    <input type="number" v-model="settings.batch_size" @change="saveSettings" min="1" max="100">
                </div>
            </div>
            
            <!-- Reranker -->
            <div class="settings-section">
                <h4>{{ t('embedding.reranker') }}</h4>
                <div class="setting-item">
                    <label>{{ t('embedding.enable_reranker') }}</label>
                    <input type="checkbox" v-model="settings.enable_reranker" @change="saveSettings">
                </div>
                
                <div class="setting-item" v-if="settings.enable_reranker">
                    <label>{{ t('embedding.reranker_engine') }}</label>
                    <select v-model="settings.reranker_engine" @change="saveSettings">
                        <option value="cross-encoder">Cross-Encoder (local)</option>
                        <option value="cohere">Cohere Rerank</option>
                        <option value="voyage">Voyage Rerank</option>
                    </select>
                </div>
                
                <div class="setting-item" v-if="settings.enable_reranker && settings.reranker_engine === 'cross-encoder'">
                    <label>{{ t('embedding.reranker_model') }}</label>
                    <select v-model="settings.reranker_model" @change="saveSettings">
                        <option value="cross-encoder/ms-marco-MiniLM-L-6-v2">ms-marco-MiniLM-L-6-v2</option>
                        <option value="cross-encoder/ms-marco-MiniLM-L-12-v2">ms-marco-MiniLM-L-12-v2</option>
                        <option value="BAAI/bge-reranker-base">BAAI/bge-reranker-base</option>
                        <option value="BAAI/bge-reranker-large">BAAI/bge-reranker-large</option>
                    </select>
                </div>
                
                <div class="setting-item" v-if="settings.enable_reranker && settings.reranker_engine === 'cohere'">
                    <label>{{ t('embedding.api_key') }}</label>
                    <input type="password" v-model="settings.cohere_key" @change="saveSettings">
                </div>
                
                <div class="setting-item">
                    <label>{{ t('embedding.top_k') }}</label>
                    <input type="number" v-model="settings.top_k" @change="saveSettings" min="1" max="50">
                </div>
            </div>
            
            <!-- Vektor adatbázis -->
            <div class="settings-section">
                <h4>{{ t('embedding.vector_db') }}</h4>
                <div class="setting-item">
                    <label>{{ t('embedding.vector_db_type') }}</label>
                    <select v-model="settings.vector_db" @change="saveSettings">
                        <option value="qdrant">Qdrant</option>
                        <option value="chroma">ChromaDB</option>
                        <option value="pgvector">PGVector</option>
                        <option value="milvus">Milvus</option>
                        <option value="elasticsearch">Elasticsearch</option>
                    </select>
                </div>
                
                <div class="setting-item" v-if="settings.vector_db === 'qdrant'">
                    <label>{{ t('embedding.qdrant_url') }}</label>
                    <input type="text" v-model="settings.qdrant_url" @change="saveSettings" 
                           placeholder="http://localhost:6333">
                </div>
                
                <div class="setting-item" v-if="settings.vector_db === 'chroma'">
                    <label>{{ t('embedding.chroma_path') }}</label>
                    <input type="text" v-model="settings.chroma_path" @change="saveSettings" 
                           placeholder="./chroma_data">
                </div>
                
                <div class="setting-item">
                    <label>{{ t('embedding.collection_name') }}</label>
                    <input type="text" v-model="settings.collection_name" @change="saveSettings" 
                           placeholder="soulcore_knowledge">
                </div>
            </div>
            
            <!-- Teszt szakasz -->
            <div class="test-section">
                <h4>{{ t('embedding.test') }}</h4>
                <div class="test-input">
                    <textarea v-model="testText" :placeholder="t('embedding.test_placeholder')" rows="3"></textarea>
                    <button class="btn-primary" @click="testEmbedding" :disabled="testing">
                        <span v-if="!testing">🧪 {{ t('embedding.test') }}</span>
                        <span v-else class="spinner-small"></span>
                    </button>
                </div>
                <div class="test-result" v-if="testResult">
                    <div class="result-header">{{ t('embedding.result') }}</div>
                    <div class="result-content">
                        <div><strong>{{ t('embedding.vector_dimension') }}:</strong> {{ testResult.dimension }}</div>
                        <div><strong>{{ t('embedding.first_values') }}:</strong> [{{ testResult.preview.join(', ') }}]</div>
                    </div>
                </div>
            </div>
        </div>
    `,
    
    setup() {
        const settings = Vue.ref({
            embedding_engine: 'sentence-transformers',
            embedding_model: 'all-MiniLM-L6-v2',
            openai_key: '',
            local_endpoint: 'http://localhost:11434/api/embeddings',
            local_model: 'nomic-embed-text',
            batch_size: 32,
            enable_reranker: false,
            reranker_engine: 'cross-encoder',
            reranker_model: 'cross-encoder/ms-marco-MiniLM-L-6-v2',
            cohere_key: '',
            top_k: 10,
            vector_db: 'qdrant',
            qdrant_url: 'http://localhost:6333',
            chroma_path: './chroma_data',
            collection_name: 'soulcore_knowledge'
        });
        
        const testText = Vue.ref('');
        const testResult = Vue.ref(null);
        const testing = Vue.ref(false);
        
        const t = (key, params = {}) => window.gettext(key, params);
        
        const loadSettings = async () => {
            try {
                const saved = await window.api.getSettings('embedding');
                if (saved) {
                    settings.value = { ...settings.value, ...saved };
                }
            } catch (error) {
                console.error('Error loading embedding settings:', error);
            }
        };
        
        const saveSettings = async () => {
            try {
                await window.api.updateSettings('embedding', settings.value);
                window.store.addNotification('success', t('embedding.settings_saved'));
            } catch (error) {
                console.error('Error saving embedding settings:', error);
                window.store.addNotification('error', t('embedding.save_error'));
            }
        };
        
        const testEmbedding = async () => {
            if (!testText.value.trim()) {
                window.store.addNotification('warning', t('embedding.test_required'));
                return;
            }
            
            testing.value = true;
            testResult.value = null;
            
            try {
                const result = await window.api.testEmbedding(testText.value, settings.value);
                testResult.value = {
                    dimension: result.dimension,
                    preview: result.vector.slice(0, 5).map(v => v.toFixed(4))
                };
                window.store.addNotification('success', t('embedding.test_success'));
            } catch (error) {
                console.error('Error testing embedding:', error);
                window.store.addNotification('error', t('embedding.test_error'));
            } finally {
                testing.value = false;
            }
        };
        
        Vue.onMounted(() => {
            loadSettings();
        });
        
        return {
            settings,
            testText,
            testResult,
            testing,
            t,
            saveSettings,
            testEmbedding
        };
    }
};

console.log('✅ EmbeddingPanel komponens betöltve');