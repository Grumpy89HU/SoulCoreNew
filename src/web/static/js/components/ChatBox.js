// ==============================================
// SOULCORE 3.0 - Chat ablak komponens
// Kódblokk támogatással, másolás/letöltés funkcióval
// ==============================================

window.ChatBox = {
    name: 'ChatBox',
    
    template: `
        <div class="chat-container">
            <!-- Chat fejléc -->
            <div class="chat-header">
                <h3>{{ currentConversation ? currentConversation.title : t('chat.untitled') }}</h3>
                <div class="chat-header-actions">
                    <span v-if="currentModel" class="chat-model-badge">
                        🤖 {{ currentModel.name || currentModel }}
                    </span>
                    <button class="icon-btn" @click="showInfo" :title="t('chat.info')">ℹ️</button>
                    <button 
                        v-if="isAdmin && currentConversation" 
                        class="icon-btn" 
                        @click="clearChat" 
                        :title="t('chat.clear')"
                    >🗑️</button>
                </div>
            </div>
            
            <!-- Üzenetek területe -->
            <div class="chat-messages" ref="messagesContainer" @scroll="handleScroll">
                <!-- Betöltés jelző (több üzenet betöltésekor) -->
                <div v-if="loadingMore" class="loading-more">
                    <div class="spinner-small"></div>
                </div>
                
                <!-- Üzenetek -->
                <div v-for="msg in messages" :key="msg.id" 
                     class="message" 
                     :class="[msg.role, msg.proactive ? 'proactive' : '']"
                     :data-id="msg.id">
                    
                    <!-- Feladó neve -->
                    <div class="sender">
                        <span v-if="msg.role === 'user'">{{ t('chat.you') }}</span>
                        <span v-else-if="msg.role === 'assistant'">{{ t('chat.assistant') }}</span>
                        <span v-else-if="msg.role === 'jester'">{{ t('chat.jester') }}</span>
                        <span v-else>{{ t('chat.system') }}</span>
                        <span v-if="msg.proactive" class="proactive-badge" :title="t('chat.proactive_hint')">🔔</span>
                        <span class="message-time">{{ formatTime(msg.timestamp) }}</span>
                    </div>
                    
                    <!-- Üzenet tartalom (markdown támogatással) -->
                    <div class="content" v-html="formatMessage(msg.content)"></div>
                    
                    <!-- Idéző gomb (csak nem rendszer üzeneteknél) -->
                    <button 
                        v-if="msg.role !== 'system'" 
                        class="quote-btn" 
                        @click="quoteMessage(msg)"
                        :title="t('chat.quote')"
                    >↩️</button>
                    
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
                    <select v-model="selectedPromptId" class="prompt-select" @change="loadPrompt">
                        <option value="">{{ t('chat.select_prompt') }}</option>
                        <option v-for="p in prompts" :key="p.id" :value="p.id">
                            {{ p.name }}
                        </option>
                    </select>
                </div>
                
                <!-- Input sor -->
                <div class="input-container">
                    <!-- Quote előnézet -->
                    <div v-if="quotedMessage" class="quote-preview">
                        <div class="quote-content">
                            <span class="quote-author">
                                {{ quotedMessage.role === 'user' ? t('chat.you') : t('chat.assistant') }}:
                            </span>
                            {{ truncate(quotedMessage.content, 50) }}
                        </div>
                        <button class="quote-close" @click="clearQuote">✕</button>
                    </div>
                    
                    <!-- Textarea beviteli mező -->
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
                    ></textarea>
                    
                    <!-- Eszköztár -->
                    <div class="input-toolbar">
                        <button class="tool-btn" @click="uploadImage" :title="t('chat.upload_image')">📷</button>
                        <button class="tool-btn" @click="openEmojiPicker" :title="t('chat.emoji')">😊</button>
                        <button class="tool-btn" @click="clearInput" :title="t('chat.clear_input')" v-if="inputMessage">🗑️</button>
                    </div>
                    
                    <!-- Küldés gomb -->
                    <button class="send-btn" @click="sendMessage" :disabled="!canSend">
                        <span v-if="!isSending">📤</span>
                        <span v-else class="spinner-small"></span>
                    </button>
                </div>
                
                <!-- Rejtett fájl input (kép feltöltéshez) -->
                <input type="file" ref="fileInput" accept="image/*" style="display: none;" @change="handleFileSelect">
                
                <!-- Modell információ -->
                <div class="model-info" v-if="currentModel">
                    <span>🤖 {{ currentModel.name || currentModel }}</span>
                    <span v-if="tokenCount" class="token-info"> | 🔤 {{ tokenCount }} {{ t('chat.tokens') }}</span>
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
        
        // Refs
        const messagesContainer = Vue.ref(null);
        const inputField = Vue.ref(null);
        const fileInput = Vue.ref(null);
        
        // Gépelés timeout
        let typingTimeout = null;
        
        // ====================================================================
        // COMPUTED PROPERTIES (BIZTONSÁGOS)
        // ====================================================================
        
        const currentConversation = Vue.computed(() => {
            const convId = window.store?.currentConversationId;
            if (!convId) return null;
            return window.store?.conversations?.find(c => c.id === convId);
        });
        
        const currentConversationId = Vue.computed(() => window.store?.currentConversationId);
        
        const messages = Vue.computed(() => {
            const convId = window.store?.currentConversationId;
            if (!convId) return [];
            return window.store?.messages?.[convId] || [];
        });
        
        const connected = Vue.computed(() => window.store?.connected || false);
        const isAdmin = Vue.computed(() => window.store?.user?.role === 'admin');
        const prompts = Vue.computed(() => window.store?.prompts || []);
        
        const currentModel = Vue.computed(() => {
            const models = window.store?.models || [];
            return models.find(m => m.is_active) || null;
        });
        
        const canSend = Vue.computed(() => {
            return connected.value && 
                   currentConversationId.value && 
                   inputMessage.value.trim() && 
                   !isSending.value;
        });
        
        // ====================================================================
        // KÓDBLOKK SEGÉDFÜGGVÉNYEK
        // ====================================================================
        
        const t = (key, params = {}) => window.gettext ? window.gettext(key, params) : key;
        
        const formatTime = (timestamp) => {
            if (!timestamp) return '';
            try { return new Date(timestamp).toLocaleTimeString(); }
            catch(e) { return ''; }
        };
        
        const truncate = (text, length) => {
            if (!text) return '';
            return text.length > length ? text.substring(0, length) + '...' : text;
        };
        
        /**
         * Kód másolása a vágólapra
         */
        const copyCodeToClipboard = async (code, language) => {
            try {
                await navigator.clipboard.writeText(code);
                window.store?.addNotification('success', `${language || 'Kód'} másolva a vágólapra`);
            } catch (err) {
                console.error('Másolás hiba:', err);
                window.store?.addNotification('error', 'Másolás sikertelen');
            }
        };
        
        /**
         * Kód letöltése fájlként
         */
        const downloadCode = (code, language) => {
            const ext = getFileExtension(language);
            const filename = `code_${Date.now()}.${ext}`;
            const blob = new Blob([code], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            window.store?.addNotification('success', `Kód mentve: ${filename}`);
        };
        
        /**
         * Fájlkiterjesztés meghatározása nyelv alapján
         */
        const getFileExtension = (language) => {
            const exts = {
                'python': 'py',
                'javascript': 'js',
                'typescript': 'ts',
                'html': 'html',
                'css': 'css',
                'json': 'json',
                'yaml': 'yaml',
                'yml': 'yml',
                'markdown': 'md',
                'bash': 'sh',
                'shell': 'sh',
                'sql': 'sql',
                'java': 'java',
                'c': 'c',
                'cpp': 'cpp',
                'csharp': 'cs',
                'go': 'go',
                'rust': 'rs',
                'php': 'php',
                'ruby': 'rb',
                'lua': 'lua',
                'xml': 'xml'
            };
            return exts[language?.toLowerCase()] || 'txt';
        };
        
        /**
         * HTML attribútum escape (biztonság)
         */
        const escapeHtmlAttribute = (str) => {
            return str
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        };
        
        /**
         * Kód blokk HTML generálása másolás/letöltés gombokkal
         */
        const generateCodeBlock = (code, language) => {
            const langLabel = language || 'code';
            const escapedCode = code
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;');
            
            return `
                <div class="code-block-container">
                    <div class="code-block-header">
                        <span class="code-language">${langLabel}</span>
                        <div class="code-actions">
                            <button class="code-copy-btn" data-code="${escapeHtmlAttribute(code)}" data-lang="${langLabel}">
                                📋 Másolás
                            </button>
                            <button class="code-download-btn" data-code="${escapeHtmlAttribute(code)}" data-lang="${langLabel}">
                                💾 Letöltés
                            </button>
                        </div>
                    </div>
                    <pre><code class="language-${langLabel}">${escapedCode}</code></pre>
                </div>
            `;
        };
        
        /**
         * Kódblokk események beállítása (DOM-ba helyezés után)
         */
        const attachCodeBlockEvents = (element) => {
            if (!element) return;
            
            const copyButtons = element.querySelectorAll('.code-copy-btn');
            copyButtons.forEach(btn => {
                btn.removeEventListener('click', handleCopyClick);
                btn.addEventListener('click', handleCopyClick);
            });
            
            const downloadButtons = element.querySelectorAll('.code-download-btn');
            downloadButtons.forEach(btn => {
                btn.removeEventListener('click', handleDownloadClick);
                btn.addEventListener('click', handleDownloadClick);
            });
        };
        
        /**
         * Másolás gomb eseménykezelő
         */
        const handleCopyClick = async (e) => {
            e.stopPropagation();
            const btn = e.currentTarget;
            const code = btn.getAttribute('data-code');
            const lang = btn.getAttribute('data-lang');
            if (code) {
                await copyCodeToClipboard(code, lang);
                const originalText = btn.innerHTML;
                btn.innerHTML = '✅ Másolva!';
                setTimeout(() => { btn.innerHTML = originalText; }, 1500);
            }
        };
        
        /**
         * Letöltés gomb eseménykezelő
         */
        const handleDownloadClick = (e) => {
            e.stopPropagation();
            const btn = e.currentTarget;
            const code = btn.getAttribute('data-code');
            const lang = btn.getAttribute('data-lang');
            if (code) {
                downloadCode(code, lang);
            }
        };
        
        /**
         * Kódblokk események frissítése (minden üzenet változás után)
         */
        const refreshCodeBlockEvents = () => {
            Vue.nextTick(() => {
                if (messagesContainer.value) {
                    attachCodeBlockEvents(messagesContainer.value);
                }
            });
        };
        
        // ====================================================================
        // ÜZENET FORMÁZÁS (markdown, linkek, kódblokkok)
        // ====================================================================
        
        const formatMessage = (content) => {
            if (!content) return '';
            
            let html = content;
            
            // Kódblokkok feldolgozása (```language\ncode\n```)
            html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (match, language, code) => {
                return generateCodeBlock(code.trim(), language);
            });
            
            // HTML escape a maradék tartalomra
            html = html
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#039;');
            
            // Linkek
            html = html.replace(
                /(https?:\/\/[^\s]+)/g,
                '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>'
            );
            
            // Inline kód (nem kódblokkban)
            html = html.replace(
                /`([^`]+)`/g,
                '<code>$1</code>'
            );
            
            // Félkövér
            html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
            
            // Dőlt
            html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
            
            // Idézetek
            html = html.replace(/^&gt; (.*)$/gm, '<blockquote>$1</blockquote>');
            
            // Sortörések
            html = html.replace(/\n/g, '<br>');
            
            return html;
        };
        
        /**
         * Görgetés az üzenetek aljára
         */
        const scrollToBottom = () => {
            Vue.nextTick(() => {
                if (messagesContainer.value) {
                    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
                    attachCodeBlockEvents(messagesContainer.value);
                }
            });
        };
        
        // ====================================================================
        // ÜZENET KÜLDÉS
        // ====================================================================
        
        const sendMessage = async () => {
            if (!canSend.value) return;
            
            const text = inputMessage.value.trim();
            
            let finalText = text;
            if (quotedMessage.value) {
                const quoteAuthor = quotedMessage.value.role === 'user' ? t('chat.you') : t('chat.assistant');
                finalText = `> ${quoteAuthor}: ${quotedMessage.value.content}\n\n${text}`;
                quotedMessage.value = null;
            }
            
            isSending.value = true;
            const convId = currentConversationId.value;
            
            // Helyi üzenet hozzáadása
            const tempId = `temp_${Date.now()}`;
            if (window.store && convId) {
                if (!window.store.state.messages[convId]) window.store.state.messages[convId] = [];
                window.store.state.messages[convId].push({
                    id: tempId,
                    role: 'user',
                    content: text,
                    timestamp: Date.now(),
                    temp: true
                });
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
                window.store?.addNotification('error', t('chat.send_error'));
                if (window.store && convId && window.store.state.messages[convId]) {
                    const msgs = window.store.state.messages[convId];
                    if (msgs && msgs[msgs.length - 1]?.id === tempId) msgs.pop();
                }
            } finally {
                isSending.value = false;
            }
        };
        
        /**
         * Új sor beszúrása (Shift+Enter)
         */
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
        
        /**
         * Gépelés jelzés küldése
         */
        const handleTyping = () => {
            if (typingTimeout) clearTimeout(typingTimeout);
            if (!isTyping.value && currentConversationId.value) {
                isTyping.value = true;
                window.socketManager?.startTyping(currentConversationId.value);
            }
            typingTimeout = setTimeout(() => {
                if (isTyping.value) {
                    isTyping.value = false;
                    window.socketManager?.stopTyping(currentConversationId.value);
                }
            }, 2000);
            if (inputField.value) {
                inputField.value.style.height = 'auto';
                inputField.value.style.height = inputField.value.scrollHeight + 'px';
            }
        };
        
        const quoteMessage = (msg) => {
            quotedMessage.value = msg;
            inputField.value?.focus();
        };
        
        const clearQuote = () => { quotedMessage.value = null; };
        const clearInput = () => {
            inputMessage.value = '';
            if (inputField.value) inputField.value.style.height = 'auto';
        };
        
        const uploadImage = () => { fileInput.value?.click(); };
        
        const handleFileSelect = async (event) => {
            const file = event.target.files[0];
            if (!file) return;
            
            const convId = currentConversationId.value;
            const tempId = `temp_img_${Date.now()}`;
            const previewUrl = URL.createObjectURL(file);
            
            if (window.store && convId) {
                if (!window.store.state.messages[convId]) window.store.state.messages[convId] = [];
                window.store.state.messages[convId].push({
                    id: tempId,
                    role: 'user',
                    content: `📷 ${file.name}`,
                    timestamp: Date.now(),
                    image: previewUrl,
                    temp: true
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
                            if (msgs && msgs[msgs.length - 1]?.id === tempId) msgs.pop();
                            if (result.success) {
                                window.store.state.messages[convId].push({
                                    id: Date.now(),
                                    role: 'assistant',
                                    content: `🖼️ **Kép feldolgozás eredménye:**\n\n${result.description || result.ocr_text || 'Kép feldolgozva'}`,
                                    timestamp: Date.now()
                                });
                            } else {
                                window.store?.addNotification('error', result.error || 'Kép feldolgozása sikertelen');
                            }
                            scrollToBottom();
                        }
                    }
                };
                reader.readAsDataURL(file);
            } catch (error) {
                console.error('Hiba a kép feltöltésekor:', error);
                window.store?.addNotification('error', t('chat.upload_error'));
                if (window.store && convId && window.store.state.messages[convId]) {
                    const msgs = window.store.state.messages[convId];
                    if (msgs && msgs[msgs.length - 1]?.id === tempId) msgs.pop();
                }
            }
            event.target.value = '';
        };
        
        const openEmojiPicker = () => {
            const emojis = ['😊', '😂', '❤️', '👍', '🎉', '🔥', '💡', '🤔', '👋', '🙏', '🐍', '🚀', '✨', '💻', '🔧'];
            const emoji = prompt('Válassz egy emojit:\n\n' + emojis.join(' '));
            if (emoji && emojis.includes(emoji)) {
                inputMessage.value += emoji;
                inputField.value?.focus();
            }
        };
        
        const loadPrompt = () => {
            if (!selectedPromptId.value) return;
            const prompt = prompts.value.find(p => p.id === selectedPromptId.value);
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
            if (!confirm(t('chat.confirm_clear'))) return;
            try {
                if (window.api) await window.api.deleteConversation(currentConversationId.value);
                window.store?.addNotification('success', t('chat.cleared'));
            } catch (error) {
                console.error('Hiba a chat törlésekor:', error);
                window.store?.addNotification('error', t('chat.clear_error'));
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
        
        Vue.watch(messages, (newMessages, oldMessages) => {
            if (newMessages.length !== oldMessages.length) {
                scrollToBottom();
                refreshCodeBlockEvents();
            }
        }, { deep: true });
        
        Vue.watch(currentConversationId, () => {
            Vue.nextTick(() => {
                scrollToBottom();
                refreshCodeBlockEvents();
            });
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
            refreshCodeBlockEvents();
            if (window.socketManager) {
                window.socketManager.on('proactive_message', () => {
                    if (window.store?.currentConversationId) {
                        window.store?.addNotification('info', t('chat.proactive_received'), 'Kópé');
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

console.log('✅ ChatBox komponens betöltve (teljes verzió)');