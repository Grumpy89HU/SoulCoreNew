// ==============================================
// Chat komponens
// ==============================================

window.ChatBox = {
    name: 'ChatBox',
    
    template: `
        <div class="chat-container">
            <!-- Chat fejléc -->
            <div class="chat-header" v-if="currentConversation">
                <div class="chat-header-info">
                    <h3>{{ currentConversation.title }}</h3>
                    <span class="chat-model-badge" v-if="currentModel">🤖 {{ currentModel }}</span>
                </div>
                <div class="chat-header-actions">
                    <button class="icon-btn" @click="showInfo" :title="t('chat.info')">ℹ️</button>
                    <button class="icon-btn" @click="clearChat" :title="t('chat.clear')" v-if="isAdmin">🗑️</button>
                </div>
            </div>
            
            <!-- Chat üzenetek -->
            <div class="chat-messages" ref="chatContainer" @scroll="handleScroll">
                <!-- Betöltés jelző (scroll felfelé) -->
                <div v-if="loadingMore" class="loading-more">
                    <div class="spinner-small"></div>
                </div>
                
                <!-- Üzenetek -->
                <div v-for="(msg, index) in messages" :key="msg.id" 
                     class="message" 
                     :class="[msg.sender]"
                     :data-id="msg.id">
                    
                    <!-- Feladó neve -->
                    <div class="sender" v-if="msg.sender !== 'user'">
                        {{ msg.senderName || t('chat.system') }}
                        <span class="message-time">{{ formatTime(msg.time) }}</span>
                    </div>
                    <div class="sender user-sender" v-else>
                        <span class="message-time">{{ formatTime(msg.time) }}</span>
                    </div>
                    
                    <!-- Üzenet tartalom (markdown támogatással) -->
                    <div class="message-content" v-html="formatMessage(msg.text)"></div>
                    
                    <!-- Válasz gomb (quote) -->
                    <button class="quote-btn" @click="quoteMessage(msg)" v-if="msg.sender !== 'system'" :title="t('chat.quote')">
                        ↩️
                    </button>
                    
                    <!-- Token információ (ha van) -->
                    <div class="message-footer" v-if="msg.tokens">
                        <span class="token-count">🔤 {{ msg.tokens }} {{ t('chat.tokens') }}</span>
                    </div>
                </div>
                
                <!-- Gépelés jelzés -->
                <div v-if="isTyping" class="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
            
            <!-- Chat input terület -->
            <div class="chat-input-area">
                <!-- Prompt választó (ha van) -->
                <div class="prompt-bar" v-if="prompts.length">
                    <select v-model="selectedPrompt" class="prompt-select" @change="loadPrompt">
                        <option value="">{{ t('chat.select_prompt') }}</option>
                        <option v-for="p in prompts" :key="p.id" :value="p.id">
                            {{ p.name }}
                        </option>
                    </select>
                </div>
                
                <!-- Input sor -->
                <div class="input-container">
                    <!-- Quote preview -->
                    <div v-if="quotedMessage" class="quote-preview">
                        <div class="quote-content">
                            <span class="quote-author">{{ quotedMessage.senderName || t('chat.system') }}:</span>
                            {{ truncate(quotedMessage.text, 50) }}
                        </div>
                        <button class="quote-close" @click="quotedMessage = null">✕</button>
                    </div>
                    
                    <!-- Input mező -->
                    <textarea 
                        v-model="inputMessage" 
                        @keydown.enter.exact.prevent="sendMessage"
                        @keydown.enter.shift.exact="insertNewline"
                        @input="handleTyping"
                        :placeholder="t('chat.type_message')"
                        :disabled="!connected"
                        class="chat-input"
                        rows="1"
                        ref="inputField"
                    ></textarea>
                    
                    <!-- Eszköztár -->
                    <div class="input-toolbar">
                        <button class="tool-btn" @click="uploadImage" :title="t('chat.upload_image')">
                            📷
                        </button>
                        <button class="tool-btn" @click="openEmojiPicker" :title="t('chat.emoji')">
                            😊
                        </button>
                        <button class="tool-btn" @click="clearInput" :title="t('chat.clear_input')" v-if="inputMessage">
                            🗑️
                        </button>
                    </div>
                    
                    <!-- Küldés gomb -->
                    <button class="send-btn" @click="sendMessage" :disabled="!canSend">
                        <span v-if="!isSending">📤</span>
                        <span v-else class="spinner-small"></span>
                    </button>
                </div>
                
                <!-- Rejtett fájl input -->
                <input type="file" ref="fileInput" accept="image/*" style="display: none;" @change="handleFileSelect">
                
                <!-- Modell információ -->
                <div class="model-info" v-if="currentModel">
                    <span>🤖 {{ currentModel }}</span>
                    <span v-if="tokenCount" class="token-info"> | 🔤 {{ tokenCount }} {{ t('chat.tokens') }}</span>
                </div>
            </div>
        </div>
    `,
    
    setup() {
        // ====================================================================
        // BIZTONSÁGOS GETTEXT
        // ====================================================================
        
        const t = (key, params = {}) => {
            if (window.gettext) {
                return window.gettext(key, params);
            }
            return key;
        };
        
        // ====================================================================
        // REAKTÍV ÁLLAPOTOK
        // ====================================================================
        
        const inputMessage = Vue.ref('');
        const selectedPrompt = Vue.ref(null);
        const quotedMessage = Vue.ref(null);
        const isTyping = Vue.ref(false);
        const isSending = Vue.ref(false);
        const loadingMore = Vue.ref(false);
        const tokenCount = Vue.ref(0);
        const page = Vue.ref(1);
        const hasMore = Vue.ref(false);
        
        // Refs
        const chatContainer = Vue.ref(null);
        const inputField = Vue.ref(null);
        const fileInput = Vue.ref(null);
        
        // ====================================================================
        // COMPUTED PROPERTIES (store-ból)
        // ====================================================================
        
        const messages = Vue.computed(() => window.store?.state?.messages || []);
        const connected = Vue.computed(() => window.store?.state?.connected || false);
        const isAdmin = Vue.computed(() => window.store?.state?.isAdmin || false);
        const prompts = Vue.computed(() => window.store?.state?.prompts || []);
        const userName = Vue.computed(() => window.store?.state?.user?.name || 'User');
        const currentConversationId = Vue.computed(() => window.store?.state?.currentConversationId);
        
        const currentConversation = Vue.computed(() => {
            const convs = window.store?.state?.conversations || [];
            return convs.find(c => c.id === currentConversationId.value);
        });
        
        const currentModel = Vue.computed(() => {
            const models = window.store?.state?.models || [];
            const activeModel = models.find(m => m.is_active);
            return activeModel ? activeModel.name : t('chat.unknown_model');
        });
        
        const canSend = Vue.computed(() => {
            return connected.value && 
                   inputMessage.value.trim() && 
                   !isSending.value &&
                   currentConversationId.value;
        });
        
        // ====================================================================
        // METÓDUSOK
        // ====================================================================
        
        // Üzenet küldés
        const sendMessage = async () => {
            if (!canSend.value) return;
            
            const text = inputMessage.value.trim();
            
            // Quote hozzáadása
            let finalText = text;
            if (quotedMessage.value) {
                const quote = `> ${quotedMessage.value.senderName || t('chat.system')}: ${quotedMessage.value.text}\n\n`;
                finalText = quote + text;
                quotedMessage.value = null;
            }
            
            isSending.value = true;
            
            try {
                await window.socketManager?.sendMessage(
                    finalText, 
                    currentConversationId.value,
                    { promptId: selectedPrompt.value }
                );
                
                inputMessage.value = '';
                tokenCount.value += text.split(/\s+/).length;
                
                // Auto-resize textarea
                if (inputField.value) {
                    inputField.value.style.height = 'auto';
                }
                
            } finally {
                isSending.value = false;
            }
        };
        
        // Új sor beszúrása (Shift+Enter)
        const insertNewline = () => {
            const start = inputField.value.selectionStart;
            const end = inputField.value.selectionEnd;
            inputMessage.value = inputMessage.value.substring(0, start) + '\n' + inputMessage.value.substring(end);
            
            // Kurzor pozíció beállítása
            Vue.nextTick(() => {
                inputField.value.selectionStart = inputField.value.selectionEnd = start + 1;
                inputField.value.style.height = 'auto';
                inputField.value.style.height = inputField.value.scrollHeight + 'px';
            });
        };
        
        // Gépelés jelzés
        const handleTyping = () => {
            if (!isTyping.value) {
                isTyping.value = true;
                window.socketManager?.emit('typing_start', { 
                    conversationId: currentConversationId.value 
                });
                
                setTimeout(() => {
                    isTyping.value = false;
                    window.socketManager?.emit('typing_stop', { 
                        conversationId: currentConversationId.value 
                    });
                }, 2000);
            }
            
            // Auto-resize
            if (inputField.value) {
                inputField.value.style.height = 'auto';
                inputField.value.style.height = inputField.value.scrollHeight + 'px';
            }
        };
        
        // Kép feltöltés
        const uploadImage = () => {
            fileInput.value?.click();
        };
        
        const handleFileSelect = (event) => {
            const file = event.target.files[0];
            if (!file || !window.socketManager) return;
            
            // Kép előnézet hozzáadása
            const previewUrl = URL.createObjectURL(file);
            const tempId = `temp_${Date.now()}`;
            
            window.store?.addMessage({
                id: tempId,
                text: `📷 ${file.name}`,
                sender: 'user',
                senderName: userName.value,
                time: new Date().toISOString(),
                image: previewUrl,
                temp: true
            });
            
            const reader = new FileReader();
            reader.onload = (e) => {
                window.socketManager.uploadImage(e.target.result, file.name);
                // Temp üzenet eltávolítása, majd a szerver válasza hozzáadja a véglegeset
                setTimeout(() => {
                    window.store?.setMessages(
                        window.store.state.messages.filter(m => m.id !== tempId)
                    );
                }, 1000);
            };
            reader.readAsDataURL(file);
            
            // File input reset
            event.target.value = '';
        };
        
        // Idézés
        const quoteMessage = (msg) => {
            quotedMessage.value = msg;
            inputField.value?.focus();
        };
        
        // Üzenet formázás (markdown + linkek)
        const formatMessage = (text) => {
            if (!text) return '';
            
            // HTML escape
            let formatted = text
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#039;');
            
            // Linkek
            formatted = formatted.replace(
                /(https?:\/\/[^\s]+)/g, 
                '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>'
            );
            
            // Képek (ha van kép URL)
            if (formatted.match(/\.(jpg|jpeg|png|gif|webp)(\?.*)?$/i)) {
                formatted = formatted.replace(
                    /(https?:\/\/[^\s]+\.(jpg|jpeg|png|gif|webp)(\?.*)?)/gi,
                    '<img src="$1" alt="Image" class="image-preview" loading="lazy">'
                );
            }
            
            // Kód blokkok
            formatted = formatted.replace(
                /```(.*?)```/gs,
                '<pre><code>$1</code></pre>'
            );
            
            // Inline kód
            formatted = formatted.replace(
                /`([^`]+)`/g,
                '<code>$1</code>'
            );
            
            // Sortörések
            formatted = formatted.replace(/\n/g, '<br>');
            
            // Idézetek
            formatted = formatted.replace(
                /^&gt; (.*)$/gm,
                '<blockquote>$1</blockquote>'
            );
            
            return formatted;
        };
        
        // Szöveg rövidítés
        const truncate = (text, length) => {
            if (!text) return '';
            return text.length > length ? text.substring(0, length) + '…' : text;
        };
        
        // Idő formázás
        const formatTime = (timeStr) => {
            if (!timeStr) return '';
            try {
                const date = new Date(timeStr);
                return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            } catch (e) {
                return timeStr;
            }
        };
        
        // Prompt betöltés
        const loadPrompt = () => {
            if (!selectedPrompt.value) return;
            
            const prompt = prompts.value.find(p => p.id === selectedPrompt.value);
            if (prompt && prompt.content) {
                inputMessage.value = prompt.content;
            }
        };
        
        // Görgetés kezelés (több üzenet betöltéséhez)
        const handleScroll = () => {
            if (!chatContainer.value) return;
            
            const { scrollTop } = chatContainer.value;
            if (scrollTop < 100 && !loadingMore.value && hasMore.value) {
                loadMoreMessages();
            }
        };
        
        // Több üzenet betöltése
        const loadMoreMessages = async () => {
            if (!currentConversationId.value) return;
            
            loadingMore.value = true;
            try {
                const olderMessages = await window.api?.getMessages(
                    currentConversationId.value,
                    { limit: 20, before: messages.value[0]?.timestamp }
                );
                
                if (olderMessages?.length) {
                    // Meglévő üzenetek elé beszúrás
                    const allMessages = [...olderMessages, ...messages.value];
                    window.store?.setMessages(allMessages);
                    hasMore.value = olderMessages.length === 20;
                } else {
                    hasMore.value = false;
                }
            } finally {
                loadingMore.value = false;
            }
        };
        
        // Görgetés aljára
        const scrollToBottom = () => {
            Vue.nextTick(() => {
                if (chatContainer.value) {
                    chatContainer.value.scrollTop = chatContainer.value.scrollHeight;
                }
            });
        };
        
        // Chat infó
        const showInfo = () => {
            console.log('Show info');
        };
        
        // Chat törlés (admin)
        const clearChat = () => {
            if (!isAdmin.value || !currentConversationId.value) return;
            
            const confirmMsg = t('chat.confirm_clear');
            if (confirm(confirmMsg) && window.socketManager) {
                window.socketManager.deleteConversation(currentConversationId.value);
            }
        };
        
        // Emoji picker
        const openEmojiPicker = () => {
            console.log('Emoji picker');
        };
        
        // Input törlés
        const clearInput = () => {
            inputMessage.value = '';
            if (inputField.value) {
                inputField.value.style.height = 'auto';
            }
        };
        
        // ====================================================================
        // WATCHEREK
        // ====================================================================
        
        // Új üzenet érkezésekor görgetés aljára
        Vue.watch(messages, (newMessages, oldMessages) => {
            if (newMessages.length > oldMessages.length) {
                const lastNew = newMessages[newMessages.length - 1];
                const lastOld = oldMessages[oldMessages.length - 1];
                
                // Ha új üzenet jött (nem betöltés), görgetünk
                if (lastNew?.id !== lastOld?.id) {
                    scrollToBottom();
                }
            }
        }, { deep: true });
        
        // Beszélgetés váltáskor görgetés
        Vue.watch(currentConversationId, () => {
            Vue.nextTick(scrollToBottom);
            page.value = 1;
            hasMore.value = false;
        });
        
        // ====================================================================
        // ÉLETCIKLUS
        // ====================================================================
        
        Vue.onMounted(() => {
            scrollToBottom();
            
            // Socket események figyelése
            if (window.socketManager) {
                window.socketManager.on('typing_start', (data) => {
                    if (data.conversationId === currentConversationId.value) {
                        isTyping.value = true;
                    }
                });
                
                window.socketManager.on('typing_stop', (data) => {
                    if (data.conversationId === currentConversationId.value) {
                        isTyping.value = false;
                    }
                });
            }
        });
        
        Vue.onUnmounted(() => {
            // Cleanup - socket események eltávolítása
            if (window.socketManager) {
                window.socketManager.off('typing_start');
                window.socketManager.off('typing_stop');
            }
        });
        
        // ====================================================================
        // RETURN
        // ====================================================================
        
        return {
            // Állapotok
            inputMessage,
            selectedPrompt,
            quotedMessage,
            isTyping,
            isSending,
            loadingMore,
            tokenCount,
            
            // Computed
            messages,
            connected,
            isAdmin,
            prompts,
            currentConversation,
            currentModel,
            currentConversationId,
            canSend,
            
            // Refs
            chatContainer,
            inputField,
            fileInput,
            
            // Fordítás (EZ KELL!)
            t,
            
            // Metódusok
            sendMessage,
            insertNewline,
            handleTyping,
            uploadImage,
            handleFileSelect,
            quoteMessage,
            formatMessage,
            truncate,
            formatTime,
            loadPrompt,
            handleScroll,
            showInfo,
            clearChat,
            openEmojiPicker,
            clearInput
        };
    }
};

window.ChatBox = ChatBox;
console.log('✅ ChatBox betöltve globálisan');