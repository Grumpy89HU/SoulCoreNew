// ==============================================
// SOULCORE 3.0 - Chat komponens
// ==============================================

window.ChatBox = {
    name: 'ChatBox',
    
    template: `
        <div class="chat-container" style="display: flex; flex-direction: column; height: 100%;">
            <!-- Chat fejléc -->
            <div class="chat-header" style="padding: 16px; border-bottom: 1px solid var(--border);">
                <div class="chat-header-info">
                    <h3>{{ currentConversation?.title || t('chat.untitled') }}</h3>
                    <span v-if="currentModel" class="badge">
                        🤖 {{ currentModel.name }}
                    </span>
                </div>
            </div>
            
            <!-- Üzenetek -->
            <div class="chat-messages" ref="messagesContainer" style="flex: 1; overflow-y: auto; padding: 20px;">
                <div v-if="loadingMessages" class="loading-spinner">
                    <div class="spinner-small"></div>
                </div>
                
                <div v-else-if="messages.length === 0" class="empty-state">
                    <div class="empty-icon">💬</div>
                    <div class="empty-title">{{ t('chat.no_messages') }}</div>
                    <div class="empty-text">{{ t('chat.start_conversation') }}</div>
                </div>
                
                <div v-else>
                    <div 
                        v-for="msg in messages" 
                        :key="msg.id"
                        class="message"
                        :class="msg.role"
                    >
                        <div class="message-sender">
                            {{ msg.role === 'user' ? (user?.username || t('chat.you')) : t('chat.assistant') }}
                            <span class="message-time">{{ formatTime(msg.timestamp) }}</span>
                        </div>
                        <div class="message-content" v-html="formatMessage(msg.content)"></div>
                    </div>
                    
                    <div v-if="isTyping" class="typing-indicator">
                        <span></span>
                        <span></span>
                        <span></span>
                        <span>{{ t('chat.typing') }}</span>
                    </div>
                </div>
            </div>
            
            <!-- Input terület -->
            <div class="chat-input-area" style="padding: 16px; border-top: 1px solid var(--border);">
                <div class="input-container" style="display: flex; gap: 12px;">
                    <textarea 
                        v-model="inputMessage"
                        @keydown.enter.exact.prevent="sendMessage"
                        @keydown.enter.shift.exact="insertNewline"
                        @input="handleTyping"
                        :placeholder="t('chat.type_message')"
                        :disabled="!connected || !currentConversationId"
                        class="chat-input"
                        rows="1"
                        ref="inputField"
                        style="flex: 1; resize: none; padding: 12px;"
                    ></textarea>
                    
                    <button 
                        class="btn btn-primary" 
                        @click="sendMessage"
                        :disabled="!canSend"
                        style="height: 44px; width: 44px; border-radius: 50%;"
                    >
                        📤
                    </button>
                </div>
            </div>
        </div>
    `,
    
    setup() {
        const user = Vue.computed(() => window.store.user);
        const connected = Vue.computed(() => window.store.connected);
        const currentConversationId = Vue.computed(() => window.store.currentConversationId);
        const currentConversation = Vue.computed(() => window.store.currentConversation);
        const currentModel = Vue.computed(() => window.store.currentModel);
        const messages = Vue.computed(() => window.store.messages);
        
        const inputMessage = Vue.ref('');
        const isTyping = Vue.ref(false);
        const loadingMessages = Vue.ref(false);
        const typingTimeout = Vue.ref(null);
        
        const messagesContainer = Vue.ref(null);
        const inputField = Vue.ref(null);
        
        const t = (key, params = {}) => {
            return window.gettext ? window.gettext(key, params) : key;
        };
        
        const canSend = Vue.computed(() => {
            return connected.value && 
                   currentConversationId.value && 
                   inputMessage.value.trim() &&
                   !isTyping.value;
        });
        
        const formatTime = (timestamp) => {
            if (window.formatters) {
                return window.formatters.formatTime(timestamp);
            }
            return new Date(timestamp).toLocaleTimeString();
        };
        
        const formatMessage = (content) => {
            if (!content) return '';
            
            // HTML escape
            let formatted = content
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;');
            
            // Linkek
            formatted = formatted.replace(
                /(https?:\/\/[^\s]+)/g,
                '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>'
            );
            
            // Kód blokkok
            formatted = formatted.replace(
                /```([\s\S]*?)```/g,
                '<pre><code>$1</code></pre>'
            );
            
            // Inline kód
            formatted = formatted.replace(
                /`([^`]+)`/g,
                '<code>$1</code>'
            );
            
            // Sortörések
            formatted = formatted.replace(/\n/g, '<br>');
            
            return formatted;
        };
        
        const scrollToBottom = () => {
            Vue.nextTick(() => {
                if (messagesContainer.value) {
                    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
                }
            });
        };
        
        const sendMessage = async () => {
            if (!canSend.value) return;
            
            const text = inputMessage.value.trim();
            inputMessage.value = '';
            
            // Helyi üzenet hozzáadása
            const tempMessage = {
                id: `temp_${Date.now()}`,
                role: 'user',
                content: text,
                timestamp: Date.now(),
                temp: true
            };
            window.store.addMessage(currentConversationId.value, tempMessage);
            scrollToBottom();
            
            try {
                await window.socketManager.sendMessage(text, currentConversationId.value);
            } catch (error) {
                console.error('Hiba az üzenet küldésekor:', error);
                window.store.addNotification('error', t('chat.send_error'));
            }
            
            // Auto-resize textarea
            if (inputField.value) {
                inputField.value.style.height = 'auto';
            }
        };
        
        const insertNewline = () => {
            const start = inputField.value.selectionStart;
            const end = inputField.value.selectionEnd;
            inputMessage.value = inputMessage.value.substring(0, start) + '\n' + inputMessage.value.substring(end);
            
            Vue.nextTick(() => {
                inputField.value.selectionStart = inputField.value.selectionEnd = start + 1;
            });
        };
        
        const handleTyping = () => {
            if (typingTimeout.value) {
                clearTimeout(typingTimeout.value);
            }
            
            if (!isTyping.value && currentConversationId.value) {
                isTyping.value = true;
                window.socketManager.startTyping(currentConversationId.value);
            }
            
            typingTimeout.value = setTimeout(() => {
                if (isTyping.value) {
                    isTyping.value = false;
                    window.socketManager.stopTyping(currentConversationId.value);
                }
            }, 2000);
            
            // Auto-resize textarea
            if (inputField.value) {
                inputField.value.style.height = 'auto';
                inputField.value.style.height = inputField.value.scrollHeight + 'px';
            }
        };
        
        const loadMessages = async () => {
            if (!currentConversationId.value) return;
            
            loadingMessages.value = true;
            try {
                await window.api.getMessages(currentConversationId.value);
                scrollToBottom();
            } catch (error) {
                console.error('Hiba az üzenetek betöltésekor:', error);
            } finally {
                loadingMessages.value = false;
            }
        };
        
        // Figyeljük a beszélgetés váltást
        Vue.watch(currentConversationId, (newId, oldId) => {
            if (newId && newId !== oldId) {
                loadMessages();
            }
        });
        
        // Figyeljük az új üzeneteket
        Vue.watch(messages, () => {
            scrollToBottom();
        }, { deep: true });
        
        Vue.onMounted(() => {
            if (currentConversationId.value) {
                loadMessages();
            }
        });
        
        return {
            user,
            connected,
            currentConversationId,
            currentConversation,
            currentModel,
            messages,
            inputMessage,
            isTyping,
            loadingMessages,
            messagesContainer,
            inputField,
            canSend,
            t,
            formatTime,
            formatMessage,
            sendMessage,
            insertNewline,
            handleTyping
        };
    }
};

console.log('✅ ChatBox komponens betöltve');