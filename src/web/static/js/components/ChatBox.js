// ==============================================
// SOULCORE 3.0 - Chat ablak komponens
// JAVÍTOTT VERZIÓ - store elérés javítva
// ==============================================

window.ChatBox = {
    name: 'ChatBox',
    
    template: `
        <div class="chat-container">
            <!-- Chat fejléc -->
            <div class="chat-header">
                <h3 align="center">{{ currentConversation ? currentConversation.title : (t ? t('chat.untitled') : 'Új beszélgetés') }}</h3>
                <div class="chat-header-actions">
                    <span v-if="currentModel" class="chat-model-badge">
                        🤖 {{ currentModel.name || currentModel }}
                    </span>
                    <button 
                        v-if="isAdmin && currentConversation" 
                        class="icon-btn" 
                        @click="clearChat" 
                        :title="(t ? t('chat.clear') : 'Törlés')"
                    >🗑️</button>
                </div>
            </div>
            
            <!-- Üzenetek területe -->
            <div class="chat-messages" ref="messagesContainer" @scroll="handleScroll">
                <div v-if="loadingMore" class="loading-more">
                    <div class="spinner-small"></div>
                </div>
                
                <div v-for="msg in messages" :key="msg.id" 
                     class="message" 
                     :class="[msg.role, msg.proactive ? 'proactive' : '']"
                     :data-id="msg.id">
                    
                    <div class="sender">
                        <span v-if="msg.role === 'user'">{{ t ? t('chat.you') : 'Te' }}</span>
                        <span v-else-if="msg.role === 'assistant'">{{ t ? t('chat.assistant') : 'Kópé' }}</span>
                        <span v-else-if="msg.role === 'jester'">{{ t ? t('chat.jester') : 'Bohóc' }}</span>
                        <span v-else>{{ t ? t('chat.system') : 'Rendszer' }}</span>
                        <span v-if="msg.proactive" class="proactive-badge" :title="(t ? t('chat.proactive_hint') : 'Proaktív')">🔔</span>
                        <span class="message-time">{{ formatTime(msg.timestamp) }}</span>
                    </div>
                    
                    <div class="content" v-html="formatMessage(msg.content)"></div>
                    
                    <button 
                        v-if="msg.role !== 'system'" 
                        class="quote-btn" 
                        @click="quoteMessage(msg)"
                        :title="(t ? t('chat.quote') : 'Idézés')"
                    >↩️</button>
                    
                    <div class="message-footer" v-if="msg.tokens">
                        <span class="token-count">🔤 {{ msg.tokens }} {{ t ? t('chat.tokens') : 'token' }}</span>
                    </div>
                </div>
                
                <div v-if="isTyping" class="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
            
            <!-- Chat input terület -->
            <div class="chat-input-area">
                <div class="prompt-bar" v-if="prompts && prompts.length">
                    <select v-model="selectedPromptId" class="prompt-select" @change="loadPrompt">
                        <option value="">{{ t ? t('chat.select_prompt') : 'Válassz promptot...' }}</option>
                        <option v-for="p in prompts" :key="p.id" :value="p.id">
                            {{ p.name }}
                        </option>
                    </select>
                </div>
                
                <div class="input-container">
                    <div v-if="quotedMessage" class="quote-preview">
                        <div class="quote-content">
                            <span class="quote-author">
                                {{ quotedMessage.role === 'user' ? (t ? t('chat.you') : 'Te') : (t ? t('chat.assistant') : 'Kópé') }}:
                            </span>
                            {{ truncate(quotedMessage.content, 50) }}
                        </div>
                        <button class="quote-close" @click="clearQuote">✕</button>
                    </div>
                    
                    <textarea 
                        v-model="inputMessage" 
                        @keydown.enter.exact.prevent="sendMessage"
                        @keydown.enter.shift.exact="insertNewline"
                        @input="handleTyping"
                        :placeholder="(t ? t('chat.type_message') : 'Írja be üzenetét...')"
                        :disabled="!connected || !currentConversationId"
                        class="chat-input"
                        rows="1"
                        ref="inputField"
                    ></textarea>
                    
                    <div class="input-toolbar">
                        <button class="tool-btn" @click="uploadImage" :title="(t ? t('chat.upload_image') : 'Kép feltöltés')">📷</button>
                        <button class="tool-btn" @click="openEmojiPicker" :title="(t ? t('chat.emoji') : 'Hangulatjel')">😊</button>
                        <button class="tool-btn" @click="clearInput" :title="(t ? t('chat.clear_input') : 'Törlés')" v-if="inputMessage">🗑️</button>
                    </div>
                    
                    <button class="send-btn" @click="sendMessage" :disabled="!canSend">
                        <span v-if="!isSending">📤</span>
                        <span v-else class="spinner-small"></span>
                    </button>
                </div>
                
                <input type="file" ref="fileInput" accept="image/*" style="display: none;" @change="handleFileSelect">
                
                <div class="model-info" v-if="currentModel">
                    <span>🤖 {{ currentModel.name || currentModel }}</span>
                    <span v-if="tokenCount" class="token-info"> | 🔤 {{ tokenCount }} {{ t ? t('chat.tokens') : 'token' }}</span>
                </div>
            </div>
        </div>
    `,
    
    setup() {
        // ====================================================================
        // REAKTÍV ÁLLAPOTOK
        // ====================================================================
        
        const inputMessage = Vue.ref('');
        const selectedPromptId = Vue.ref(null);
        const quotedMessage = Vue.ref(null);
        const isTyping = Vue.ref(false);
        const isSending = Vue.ref(false);
        const loadingMore = Vue.ref(false);
        const tokenCount = Vue.ref(0);
        const page = Vue.ref(1);
        const hasMore = Vue.ref(false);
        
        const messagesContainer = Vue.ref(null);
        const inputField = Vue.ref(null);
        const fileInput = Vue.ref(null);
        
        let typingTimeout = null;
        
        // ====================================================================
        // COMPUTED PROPERTIES (BIZTONSÁGOS STORE ELÉRÉS)
        // ====================================================================
        
        const currentConversation = Vue.computed(() => {
            if (!window.store) return null;
            const convId = window.store.currentConversationId;
            if (!convId) return null;
            const convs = window.store.conversations;
            return convs ? convs.find(c => c.id === convId) : null;
        });
        
        const currentConversationId = Vue.computed(() => {
            return window.store ? window.store.currentConversationId : null;
        });
        
        const messages = Vue.computed(() => {
            if (!window.store) return [];
            const convId = window.store.currentConversationId;
            if (!convId) return [];
            const msgs = window.store.messages;
            return msgs && msgs[convId] ? msgs[convId] : [];
        });
        
        const connected = Vue.computed(() => {
            return window.store ? window.store.connected : false;
        });
        
        const isAdmin = Vue.computed(() => {
            return window.store && window.store.user ? window.store.user.role === 'admin' : false;
        });
        
        const prompts = Vue.computed(() => {
            return window.store ? window.store.prompts : [];
        });
        
        const currentModel = Vue.computed(() => {
            if (!window.store) return null;
            const models = window.store.models;
            return models ? models.find(m => m.is_active) : null;
        });
        
        const canSend = Vue.computed(() => {
            return connected.value && 
                   currentConversationId.value && 
                   inputMessage.value.trim() && 
                   !isSending.value;
        });
        
        // ====================================================================
        // SEGÉDFÜGGVÉNYEK
        // ====================================================================
        
        const t = (key, params = {}) => {
            return window.gettext ? window.gettext(key, params) : key;
        };
        
        const formatTime = (timestamp) => {
            if (!timestamp) return '';
            try { return new Date(timestamp).toLocaleTimeString(); }
            catch(e) { return ''; }
        };
        
        const truncate = (text, length) => {
            if (!text) return '';
            return text.length > length ? text.substring(0, length) + '...' : text;
        };
        
        const scrollToBottom = () => {
            Vue.nextTick(() => {
                if (messagesContainer.value) {
                    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
                }
            });
        };
        
        // ====================================================================
        // KÓDBLOKK FUNKCIÓK
        // ====================================================================
        
        const copyCodeToClipboard = async (code, language) => {
            try {
                await navigator.clipboard.writeText(code);
                if (window.store) window.store.addNotification('success', `${language || 'Kód'} másolva a vágólapra`);
            } catch (err) {
                console.error('Másolás hiba:', err);
                if (window.store) window.store.addNotification('error', 'Másolás sikertelen');
            }
        };
        
        const downloadCode = (code, language) => {
            const exts = {
                'python': 'py', 'javascript': 'js', 'html': 'html', 'css': 'css',
                'json': 'json', 'bash': 'sh', 'sql': 'sql', 'java': 'java'
            };
            const ext = exts[language?.toLowerCase()] || 'txt';
            const filename = `code_${Date.now()}.${ext}`;
            const blob = new Blob([code], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            a.click();
            URL.revokeObjectURL(url);
            if (window.store) window.store.addNotification('success', `Kód mentve: ${filename}`);
        };
        
        const escapeHtml = (str) => {
            return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
        };
        
        const generateCodeBlock = (code, language) => {
            const langLabel = language || 'code';
            const escapedCode = escapeHtml(code);
            return `
                <div class="code-block-container">
                    <div class="code-block-header">
                        <span class="code-language">${langLabel}</span>
                        <div class="code-actions">
                            <button class="code-copy-btn" data-code="${escapeHtml(code)}" data-lang="${langLabel}">📋 Másolás</button>
                            <button class="code-download-btn" data-code="${escapeHtml(code)}" data-lang="${langLabel}">💾 Letöltés</button>
                        </div>
                    </div>
                    <pre><code>${escapedCode}</code></pre>
                </div>
            `;
        };
        
        const attachCodeBlockEvents = (element) => {
            if (!element) return;
            element.querySelectorAll('.code-copy-btn').forEach(btn => {
                btn.onclick = async (e) => {
                    e.stopPropagation();
                    const code = btn.getAttribute('data-code');
                    const lang = btn.getAttribute('data-lang');
                    if (code) {
                        await copyCodeToClipboard(code, lang);
                        const original = btn.innerHTML;
                        btn.innerHTML = '✅ Másolva!';
                        setTimeout(() => { btn.innerHTML = original; }, 1500);
                    }
                };
            });
            element.querySelectorAll('.code-download-btn').forEach(btn => {
                btn.onclick = (e) => {
                    e.stopPropagation();
                    const code = btn.getAttribute('data-code');
                    const lang = btn.getAttribute('data-lang');
                    if (code) downloadCode(code, lang);
                };
            });
        };
        
        const formatMessage = (content) => {
            if (!content) return '';
            
            let html = content;
            html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (match, language, code) => {
                return generateCodeBlock(code.trim(), language);
            });
            html = html.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
            html = html.replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>');
            html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
            html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
            html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
            html = html.replace(/^&gt; (.*)$/gm, '<blockquote>$1</blockquote>');
            html = html.replace(/\n/g, '<br>');
            
            return html;
        };
        
        // ====================================================================
        // ÜZENET KÜLDÉS
        // ====================================================================
        
        const sendMessage = async () => {
            if (!canSend.value) return;
            
            const text = inputMessage.value.trim();
            
            let finalText = text;
            if (quotedMessage.value) {
                const quoteAuthor = quotedMessage.value.role === 'user' ? (t ? t('chat.you') : 'Te') : (t ? t('chat.assistant') : 'Kópé');
                finalText = `> ${quoteAuthor}: ${quotedMessage.value.content}\n\n${text}`;
                quotedMessage.value = null;
            }
            
            isSending.value = true;
            const convId = currentConversationId.value;
            
            // JAVÍTVA: helyi üzenet hozzáadása a store-hoz
            const tempMsg = {
                id: Date.now(),
                role: 'user',
                content: text,
                timestamp: Date.now(),
                temp: true
            };
            
            if (window.store && convId) {
                // Közvetlenül a store state-jébe írunk
                if (!window.store.state.messages[convId]) {
                    window.store.state.messages[convId] = [];
                }
                window.store.state.messages[convId].push(tempMsg);
            }
            
            scrollToBottom();
            tokenCount.value += Math.ceil(text.length / 4);
            inputMessage.value = '';
            if (inputField.value) inputField.value.style.height = 'auto';
            
            try {
                if (window.api) await window.api.sendMessage(convId, finalText);
                if (window.socketManager) window.socketManager.sendMessage(finalText, convId);
            } catch (error) {
                console.error('Hiba az üzenet küldésekor:', error);
                if (window.store) window.store.addNotification('error', 'Hiba az üzenet küldésekor');
                
                // Hiba esetén töröljük a helyi üzenetet
                if (window.store && convId && window.store.state.messages[convId]) {
                    const msgs = window.store.state.messages[convId];
                    if (msgs[msgs.length - 1]?.id === tempMsg.id) {
                        msgs.pop();
                    }
                }
            } finally {
                isSending.value = false;
            }
        };
        
        const insertNewline = () => {
            if (!inputField.value) return;
            const start = inputField.value.selectionStart;
            const end = inputField.value.selectionEnd;
            inputMessage.value = inputMessage.value.substring(0, start) + '\n' + inputMessage.value.substring(end);
            Vue.nextTick(() => {
                inputField.value.selectionStart = inputField.value.selectionEnd = start + 1;
                inputField.value.style.height = 'auto';
                inputField.value.style.height = inputField.value.scrollHeight + 'px';
            });
        };
        
        const handleTyping = () => {
            if (typingTimeout) clearTimeout(typingTimeout);
            if (!isTyping.value && currentConversationId.value) {
                isTyping.value = true;
                if (window.socketManager) window.socketManager.startTyping(currentConversationId.value);
            }
            typingTimeout = setTimeout(() => {
                if (isTyping.value) {
                    isTyping.value = false;
                    if (window.socketManager) window.socketManager.stopTyping(currentConversationId.value);
                }
            }, 2000);
            if (inputField.value) {
                inputField.value.style.height = 'auto';
                inputField.value.style.height = inputField.value.scrollHeight + 'px';
            }
        };
        
        const quoteMessage = (msg) => {
            quotedMessage.value = msg;
            if (inputField.value) inputField.value.focus();
        };
        
        const clearQuote = () => { quotedMessage.value = null; };
        const clearInput = () => {
            inputMessage.value = '';
            if (inputField.value) inputField.value.style.height = 'auto';
        };
        
        const uploadImage = () => { if (fileInput.value) fileInput.value.click(); };
        
        const handleFileSelect = async (event) => {
            const file = event.target.files[0];
            if (!file) return;
            
            const convId = currentConversationId.value;
            const tempId = `temp_img_${Date.now()}`;
            const previewUrl = URL.createObjectURL(file);
            
            if (window.store && convId) {
                if (!window.store.state.messages[convId]) window.store.state.messages[convId] = [];
                window.store.state.messages[convId].push({
                    id: tempId, role: 'user', content: `📷 ${file.name}`, timestamp: Date.now(), image: previewUrl, temp: true
                });
            }
            scrollToBottom();
            
            try {
                const reader = new FileReader();
                reader.onload = async (e) => {
                    if (window.api) {
                        const result = await window.api.processImage(e.target.result);
                        if (window.store && convId && window.store.state.messages[convId]) {
                            const msgs = window.store.state.messages[convId];
                            if (msgs[msgs.length - 1]?.id === tempId) msgs.pop();
                            if (result && result.success) {
                                window.store.state.messages[convId].push({
                                    id: Date.now(), role: 'assistant',
                                    content: `🖼️ **Kép feldolgozás eredménye:**\n\n${result.description || result.ocr_text || 'Kép feldolgozva'}`,
                                    timestamp: Date.now()
                                });
                            } else {
                                if (window.store) window.store.addNotification('error', result?.error || 'Kép feldolgozása sikertelen');
                            }
                            scrollToBottom();
                        }
                    }
                };
                reader.readAsDataURL(file);
            } catch (error) {
                console.error('Hiba a kép feltöltésekor:', error);
                if (window.store) window.store.addNotification('error', 'Hiba a kép feltöltésekor');
                if (window.store && convId && window.store.state.messages[convId]) {
                    const msgs = window.store.state.messages[convId];
                    if (msgs[msgs.length - 1]?.id === tempId) msgs.pop();
                }
            }
            event.target.value = '';
        };
        
        const openEmojiPicker = () => {
            const emojis = ['😊', '😂', '❤️', '👍', '🎉', '🔥', '💡', '🤔', '👋', '🙏'];
            const emoji = prompt('Válassz egy emojit:\n\n' + emojis.join(' '));
            if (emoji && emojis.includes(emoji)) {
                inputMessage.value += emoji;
                if (inputField.value) inputField.value.focus();
            }
        };
        
        const loadPrompt = () => {
            if (!selectedPromptId.value) return;
            const prompt = prompts.value ? prompts.value.find(p => p.id === selectedPromptId.value) : null;
            if (prompt && prompt.content) {
                inputMessage.value = prompt.content;
                if (inputField.value) {
                    inputField.value.style.height = 'auto';
                    inputField.value.style.height = inputField.value.scrollHeight + 'px';
                }
            }
        };
        
        const showInfo = () => {
            if (!currentConversation.value) return;
            alert(`📋 Beszélgetés adatai\n─────────────────\nCím: ${currentConversation.value.title}\nÜzenetek száma: ${messages.value.length}`);
        };
        
        const clearChat = async () => {
            if (!isAdmin.value || !currentConversationId.value) return;
            if (!confirm('Biztosan törli ezt a beszélgetést?')) return;
            try {
                if (window.api) await window.api.deleteConversation(currentConversationId.value);
                if (window.store) window.store.addNotification('success', 'Beszélgetés törölve');
            } catch (error) {
                console.error('Hiba a chat törlésekor:', error);
                if (window.store) window.store.addNotification('error', 'Hiba a törlés során');
            }
        };
        
        const handleScroll = () => {
            if (!messagesContainer.value) return;
            const { scrollTop } = messagesContainer.value;
            if (scrollTop < 100 && !loadingMore.value && hasMore.value) {
                loadMoreMessages();
            }
        };
        
        const loadMoreMessages = async () => {
            if (!currentConversationId.value) return;
            loadingMore.value = true;
            try {
                const olderMessages = await window.api?.getMessages(
                    currentConversationId.value,
                    { limit: 20, before: messages.value[0]?.timestamp }
                );
                if (olderMessages?.messages?.length) {
                    const currentMsgs = window.store?.state?.messages[currentConversationId.value] || [];
                    if (window.store && window.store.state.messages) {
                        window.store.state.messages[currentConversationId.value] = [...olderMessages.messages, ...currentMsgs];
                    }
                    hasMore.value = olderMessages.messages.length === 20;
                } else {
                    hasMore.value = false;
                }
            } catch (error) {
                console.error('Hiba a régebbi üzenetek betöltésekor:', error);
            } finally {
                loadingMore.value = false;
            }
        };
        
        // ====================================================================
        // WATCHEREK
        // ====================================================================
        
        Vue.watch(messages, () => {
            scrollToBottom();
            Vue.nextTick(() => {
                if (messagesContainer.value) attachCodeBlockEvents(messagesContainer.value);
            });
        }, { deep: true });
        
        Vue.watch(currentConversationId, () => {
            Vue.nextTick(scrollToBottom);
            page.value = 1;
            hasMore.value = false;
        });
        
        Vue.watch(() => window.socketManager?.typingActive, (active) => {
            isTyping.value = active;
        });
        
        // ====================================================================
        // ÉLETCIKLUS
        // ====================================================================
        
        Vue.onMounted(() => {
            scrollToBottom();
            if (messagesContainer.value) attachCodeBlockEvents(messagesContainer.value);
            if (window.socketManager) {
                window.socketManager.on('proactive_message', () => {
                    if (window.store && window.store.currentConversationId) {
                        if (window.store) window.store.addNotification('info', 'Proaktív üzenet érkezett', 'Kópé');
                    }
                });
            }
        });
        
        Vue.onUnmounted(() => {
            if (typingTimeout) clearTimeout(typingTimeout);
            if (window.socketManager) {
                window.socketManager.off('proactive_message');
            }
        });
        
        // ====================================================================
        // RETURN
        // ====================================================================
        
        return {
            inputMessage,
            selectedPromptId,
            quotedMessage,
            isTyping,
            isSending,
            loadingMore,
            tokenCount,
            currentConversation,
            currentConversationId,
            messages,
            connected,
            isAdmin,
            prompts,
            currentModel,
            canSend,
            messagesContainer,
            inputField,
            fileInput,
            t,
            formatTime,
            truncate,
            formatMessage,
            sendMessage,
            insertNewline,
            handleTyping,
            quoteMessage,
            clearQuote,
            clearInput,
            uploadImage,
            handleFileSelect,
            openEmojiPicker,
            loadPrompt,
            showInfo,
            clearChat,
            handleScroll
        };
    }
};

console.log('✅ ChatBox komponens betöltve (javított verzió)');