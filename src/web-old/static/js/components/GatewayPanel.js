// ==============================================
// SOULCORE 3.0 - Külső LLM Gateway
// ==============================================

window.GatewayPanel = {
    name: 'GatewayPanel',
    
    template: `
        <div class="gateway-panel">
            <div class="gateway-header">
                <h3>{{ t('gateway.title') }}</h3>
                <p>{{ t('gateway.description') }}</p>
                <button class="btn-primary" @click="showAddModal = true">
                    + {{ t('gateway.add_connection') }}
                </button>
            </div>
            
            <!-- Kapcsolatok listája -->
            <div class="gateway-list">
                <div v-if="loading" class="loading-spinner">
                    <div class="spinner-small"></div>
                </div>
                <div v-else-if="gateways.length === 0" class="empty-list">
                    <div class="empty-icon">🌐</div>
                    <div class="empty-text">{{ t('gateway.no_connections') }}</div>
                </div>
                <div v-else>
                    <div v-for="gw in gateways" :key="gw.id" class="gateway-card" :class="gw.status">
                        <div class="gateway-header-row">
                            <div class="gateway-info">
                                <span class="gateway-name">{{ gw.name }}</span>
                                <span class="gateway-type">{{ gw.type }}</span>
                            </div>
                            <div class="gateway-status">
                                <span class="status-dot" :class="gw.status"></span>
                                {{ formatStatus(gw.status) }}
                            </div>
                        </div>
                        
                        <div class="gateway-details">
                            <div class="detail-row">
                                <span class="detail-label">{{ t('gateway.endpoint') }}:</span>
                                <span class="detail-value">{{ gw.endpoint }}</span>
                            </div>
                            <div class="detail-row">
                                <span class="detail-label">{{ t('gateway.trust_score') }}:</span>
                                <span class="detail-value trust-score">{{ gw.trust_score || 0 }}/1000</span>
                            </div>
                            <div class="detail-row" v-if="gw.last_communication">
                                <span class="detail-label">{{ t('gateway.last_communication') }}:</span>
                                <span class="detail-value">{{ formatRelativeTime(gw.last_communication) }}</span>
                            </div>
                        </div>
                        
                        <div class="gateway-actions">
                            <button class="btn-sm btn-secondary" @click="testConnection(gw.id)">
                                🔌 {{ t('gateway.test') }}
                            </button>
                            <button class="btn-sm btn-secondary" @click="openChatModal(gw)">
                                💬 {{ t('gateway.chat') }}
                            </button>
                            <button class="btn-sm btn-secondary" @click="editGateway(gw)">
                                ✏️
                            </button>
                            <button class="btn-sm btn-danger" @click="deleteGateway(gw.id)">
                                🗑️
                            </button>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Hozzáadás/Szerkesztés modal -->
            <div class="modal" v-if="showAddModal" @click.self="showAddModal = false">
                <div class="modal-content">
                    <div class="modal-header">
                        <h3>{{ editingGateway ? t('gateway.edit') : t('gateway.add') }}</h3>
                        <button class="close-btn" @click="showAddModal = false">✕</button>
                    </div>
                    <div class="modal-body">
                        <div class="form-group">
                            <label>{{ t('gateway.name') }}</label>
                            <input type="text" v-model="form.name" class="form-input">
                        </div>
                        <div class="form-group">
                            <label>{{ t('gateway.type') }}</label>
                            <select v-model="form.type" class="form-input">
                                <option value="ollama">Ollama</option>
                                <option value="openai">OpenAI API</option>
                                <option value="anthropic">Anthropic Claude</option>
                                <option value="gemini">Google Gemini</option>
                                <option value="custom">Custom</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>{{ t('gateway.endpoint') }}</label>
                            <input type="text" v-model="form.endpoint" class="form-input" 
                                   placeholder="http://localhost:11434">
                        </div>
                        <div class="form-group">
                            <label>{{ t('gateway.api_key') }}</label>
                            <input type="password" v-model="form.api_key" class="form-input" 
                                   :placeholder="t('gateway.api_key_placeholder')">
                        </div>
                        <div class="form-group">
                            <label>{{ t('gateway.model') }}</label>
                            <input type="text" v-model="form.model" class="form-input" 
                                   placeholder="llama2">
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn-secondary" @click="showAddModal = false">
                            {{ t('ui.cancel') }}
                        </button>
                        <button class="btn-primary" @click="saveGateway" :disabled="saving">
                            <span v-if="!saving">💾 {{ t('ui.save') }}</span>
                            <span v-else class="spinner-small"></span>
                        </button>
                    </div>
                </div>
            </div>
            
            <!-- Chat modal -->
            <div class="modal" v-if="showChatModal" @click.self="showChatModal = false">
                <div class="modal-content large">
                    <div class="modal-header">
                        <h3>{{ t('gateway.chat_with') }} {{ selectedGateway?.name }}</h3>
                        <button class="close-btn" @click="showChatModal = false">✕</button>
                    </div>
                    <div class="modal-body">
                        <div class="chat-messages" ref="chatMessages">
                            <div v-for="msg in chatMessages" :key="msg.id" class="message" :class="msg.role">
                                <div class="sender">{{ msg.role === 'user' ? t('chat.you') : selectedGateway?.name }}</div>
                                <div class="content">{{ msg.content }}</div>
                                <div class="time">{{ formatTime(msg.timestamp) }}</div>
                            </div>
                        </div>
                        <div class="chat-input">
                            <textarea v-model="chatInput" @keydown.enter.exact.prevent="sendGatewayMessage" 
                                      :placeholder="t('gateway.type_message')" rows="2"></textarea>
                            <button class="send-btn" @click="sendGatewayMessage" :disabled="sending">
                                📤
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `,
    
    setup() {
        const gateways = Vue.ref([]);
        const loading = Vue.ref(false);
        const saving = Vue.ref(false);
        const sending = Vue.ref(false);
        
        const showAddModal = Vue.ref(false);
        const showChatModal = Vue.ref(false);
        const editingGateway = Vue.ref(null);
        const selectedGateway = Vue.ref(null);
        
        const form = Vue.ref({
            name: '',
            type: 'ollama',
            endpoint: '',
            api_key: '',
            model: ''
        });
        
        const chatMessages = Vue.ref([]);
        const chatInput = Vue.ref('');
        const chatMessagesRef = Vue.ref(null);
        
        const t = (key, params = {}) => window.gettext(key, params);
        const formatStatus = (status) => {
            const statuses = {
                online: t('gateway.online'),
                offline: t('gateway.offline'),
                error: t('gateway.error')
            };
            return statuses[status] || status;
        };
        const formatRelativeTime = (ts) => window.formatRelativeTime(ts);
        const formatTime = (ts) => window.formatTime(ts);
        
        const loadGateways = async () => {
            loading.value = true;
            try {
                const data = await window.api.getGateways();
                gateways.value = data.gateways || generateDemoGateways();
            } catch (error) {
                console.error('Error loading gateways:', error);
                gateways.value = generateDemoGateways();
            } finally {
                loading.value = false;
            }
        };
        
        const testConnection = async (id) => {
            try {
                await window.api.testGateway(id);
                window.store.addNotification('success', t('gateway.test_success'));
                await loadGateways();
            } catch (error) {
                window.store.addNotification('error', t('gateway.test_failed'));
            }
        };
        
        const saveGateway = async () => {
            if (!form.value.name || !form.value.endpoint) {
                window.store.addNotification('warning', t('gateway.fields_required'));
                return;
            }
            
            saving.value = true;
            try {
                if (editingGateway.value) {
                    await window.api.updateGateway(editingGateway.value.id, form.value);
                } else {
                    await window.api.addGateway(form.value);
                }
                window.store.addNotification('success', t('gateway.saved'));
                showAddModal.value = false;
                await loadGateways();
                resetForm();
            } catch (error) {
                window.store.addNotification('error', t('gateway.save_error'));
            } finally {
                saving.value = false;
            }
        };
        
        const editGateway = (gw) => {
            editingGateway.value = gw;
            form.value = {
                name: gw.name,
                type: gw.type,
                endpoint: gw.endpoint,
                api_key: '',
                model: gw.model || ''
            };
            showAddModal.value = true;
        };
        
        const deleteGateway = async (id) => {
            if (!confirm(t('gateway.confirm_delete'))) return;
            try {
                await window.api.deleteGateway(id);
                window.store.addNotification('success', t('gateway.deleted'));
                await loadGateways();
            } catch (error) {
                window.store.addNotification('error', t('gateway.delete_error'));
            }
        };
        
        const openChatModal = (gw) => {
            selectedGateway.value = gw;
            chatMessages.value = [];
            chatInput.value = '';
            showChatModal.value = true;
        };
        
        const sendGatewayMessage = async () => {
            if (!chatInput.value.trim()) return;
            
            const userMsg = {
                id: Date.now(),
                role: 'user',
                content: chatInput.value,
                timestamp: Date.now()
            };
            chatMessages.value.push(userMsg);
            scrollChatToBottom();
            
            const msgText = chatInput.value;
            chatInput.value = '';
            sending.value = true;
            
            try {
                const response = await window.api.sendGatewayMessage(selectedGateway.value.id, msgText);
                const assistantMsg = {
                    id: Date.now() + 1,
                    role: 'assistant',
                    content: response.text || t('gateway.no_response'),
                    timestamp: Date.now()
                };
                chatMessages.value.push(assistantMsg);
                scrollChatToBottom();
            } catch (error) {
                window.store.addNotification('error', t('gateway.send_error'));
            } finally {
                sending.value = false;
            }
        };
        
        const scrollChatToBottom = () => {
            Vue.nextTick(() => {
                if (chatMessagesRef.value) {
                    chatMessagesRef.value.scrollTop = chatMessagesRef.value.scrollHeight;
                }
            });
        };
        
        const resetForm = () => {
            editingGateway.value = null;
            form.value = {
                name: '',
                type: 'ollama',
                endpoint: '',
                api_key: '',
                model: ''
            };
        };
        
        const generateDemoGateways = () => {
            return [
                { id: 1, name: 'Local Ollama', type: 'ollama', endpoint: 'http://localhost:11434', status: 'online', trust_score: 950, last_communication: Date.now() - 60000, model: 'llama2' },
                { id: 2, name: 'OpenAI', type: 'openai', endpoint: 'https://api.openai.com/v1', status: 'offline', trust_score: 800, last_communication: Date.now() - 3600000, model: 'gpt-3.5-turbo' }
            ];
        };
        
        Vue.onMounted(() => {
            loadGateways();
        });
        
        return {
            gateways,
            loading,
            saving,
            sending,
            showAddModal,
            showChatModal,
            editingGateway,
            selectedGateway,
            form,
            chatMessages,
            chatInput,
            chatMessagesRef,
            t,
            formatStatus,
            formatRelativeTime,
            formatTime,
            loadGateways,
            testConnection,
            saveGateway,
            editGateway,
            deleteGateway,
            openChatModal,
            sendGatewayMessage,
            resetForm
        };
    }
};

console.log('✅ GatewayPanel komponens betöltve');