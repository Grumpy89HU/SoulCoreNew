// ==============================================
// SOULCORE 3.0 - Beszélgetés lista komponens
// ==============================================

window.ConversationList = {
    name: 'ConversationList',
    
    template: `
        <div class="conversation-list-container">
            <button 
                class="btn btn-primary" 
                style="width: 100%; margin-bottom: 16px;"
                @click="createNew"
                :disabled="!connected"
            >
                + {{ t('conversations.new') }}
            </button>
            
            <div class="search-box" style="margin-bottom: 16px;">
                <input 
                    type="text" 
                    v-model="searchQuery"
                    class="form-input"
                    :placeholder="t('conversations.search')"
                >
            </div>
            
            <div v-if="loading" class="loading-spinner">
                <div class="spinner-small"></div>
            </div>
            
            <div v-else-if="filteredConversations.length === 0" class="empty-state">
                <div class="empty-icon">💬</div>
                <div class="empty-title">{{ t('conversations.no_conversations') }}</div>
                <div class="empty-text">{{ t('conversations.create_first') }}</div>
                <button class="btn btn-primary" @click="createNew">
                    {{ t('conversations.new') }}
                </button>
            </div>
            
            <div v-else class="conversation-list">
                <div 
                    v-for="conv in filteredConversations" 
                    :key="conv.id"
                    class="conversation-item"
                    :class="{ active: currentConversationId === conv.id }"
                    @click="selectConversation(conv.id)"
                >
                    <div class="conv-content">
                        <div class="conv-title">
                            {{ conv.title || t('conversations.untitled') }}
                        </div>
                        <div class="conv-preview" v-if="conv.last_message">
                            {{ truncate(conv.last_message, 50) }}
                        </div>
                        <div class="conv-meta">
                            <span class="conv-date">
                                {{ formatRelativeTime(conv.updated_at) }}
                            </span>
                            <span v-if="conv.message_count" class="conv-count">
                                {{ conv.message_count }} üzenet
                            </span>
                        </div>
                    </div>
                    <div class="conv-actions" @click.stop>
                        <button 
                            class="btn-icon" 
                            @click="deleteConversation(conv.id)"
                            :title="t('ui.delete')"
                        >
                            🗑️
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `,
    
    setup() {
        const conversations = Vue.computed(() => window.store.conversations);
        const currentConversationId = Vue.computed(() => window.store.currentConversationId);
        const connected = Vue.computed(() => window.store.connected);
        
        const loading = Vue.ref(true);
        const searchQuery = Vue.ref('');
        
        const t = (key, params = {}) => {
            return window.gettext ? window.gettext(key, params) : key;
        };
        
        const filteredConversations = Vue.computed(() => {
            if (!searchQuery.value) return conversations.value;
            
            const query = searchQuery.value.toLowerCase();
            return conversations.value.filter(conv => 
                conv.title?.toLowerCase().includes(query) ||
                conv.last_message?.toLowerCase().includes(query)
            );
        });
        
        const formatRelativeTime = (timestamp) => {
            if (window.formatters) {
                return window.formatters.formatRelativeTime(timestamp);
            }
            return timestamp;
        };
        
        const truncate = (text, length) => {
            if (window.formatters) {
                return window.formatters.truncate(text, length);
            }
            return text;
        };
        
        const loadConversations = async () => {
            loading.value = true;
            try {
                await window.api.getConversations();
            } catch (error) {
                console.error('Hiba a beszélgetések betöltésekor:', error);
            } finally {
                loading.value = false;
            }
        };
        
        const createNew = async () => {
            const title = prompt(t('conversations.new_title'));
            if (title) {
                try {
                    await window.api.createConversation(title);
                } catch (error) {
                    console.error('Hiba a beszélgetés létrehozásakor:', error);
                    window.store.addNotification('error', t('conversations.create_error'));
                }
            }
        };
        
        const selectConversation = async (id) => {
            if (currentConversationId.value === id) return;
            
            window.store.setCurrentConversationId(id);
            await window.api.getMessages(id);
        };
        
        const deleteConversation = async (id) => {
            if (!confirm(t('conversations.confirm_delete'))) return;
            
            try {
                await window.api.deleteConversation(id);
                window.store.addNotification('success', t('conversations.deleted'));
            } catch (error) {
                console.error('Hiba a beszélgetés törlésekor:', error);
                window.store.addNotification('error', t('conversations.delete_error'));
            }
        };
        
        Vue.onMounted(() => {
            loadConversations();
        });
        
        return {
            conversations,
            currentConversationId,
            connected,
            loading,
            searchQuery,
            filteredConversations,
            t,
            formatRelativeTime,
            truncate,
            createNew,
            selectConversation,
            deleteConversation
        };
    }
};

console.log('✅ ConversationList komponens betöltve');