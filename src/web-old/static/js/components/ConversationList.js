// ==============================================
// SOULCORE 3.0 - Beszélgetés lista komponens
// ==============================================

window.ConversationList = {
    name: 'ConversationList',
    
    template: `
        <div class="conversation-list">
            <button class="btn btn-primary btn-block" @click="createNew" style="margin-bottom: 12px;">
                + {{ t('conversations.new') }}
            </button>
            
            <div v-if="loading" class="loading-spinner">
                <div class="spinner-small"></div>
            </div>
            
            <div v-else-if="conversations.length === 0" class="empty-state">
                <div class="empty-icon">💬</div>
                <div class="empty-text">{{ t('conversations.no_conversations') }}</div>
                <button class="btn btn-primary" @click="createNew">
                    {{ t('conversations.create_first') }}
                </button>
            </div>
            
            <div v-else class="conv-list">
                <div 
                    v-for="conv in conversations" 
                    :key="conv.id" 
                    class="conv-item" 
                    :class="{ active: currentId === conv.id }"
                    @click="select(conv.id)"
                >
                    <div class="conv-title">{{ conv.title || t('conversations.untitled') }}</div>
                    <div class="conv-preview" v-if="conv.last_message">
                        {{ truncate(conv.last_message, 50) }}
                    </div>
                    <div class="conv-meta">
                        <span>{{ formatRelativeTime(conv.updated_at) }}</span>
                        <button class="delete-btn" @click.stop="deleteConv(conv.id)">🗑️</button>
                    </div>
                </div>
            </div>
        </div>
    `,
    
    setup() {
        const conversations = Vue.computed(() => window.store.conversations);
        const currentId = Vue.computed(() => window.store.currentConversationId);
        const loading = Vue.ref(false);
        
        const t = (key, params = {}) => window.gettext(key, params);
        const formatRelativeTime = (ts) => window.formatRelativeTime(ts);
        const truncate = (text, len) => window.truncate(text, len);
        
        const load = async () => {
            loading.value = true;
            try {
                await window.api.getConversations();
            } catch (error) {
                console.error('Hiba a beszélgetések betöltésekor:', error);
                window.store.addNotification('error', t('conversations.load_error'));
            } finally {
                loading.value = false;
            }
        };
        
        const createNew = async () => {
            const title = prompt(t('conversations.new_title'));
            if (title) {
                try {
                    await window.api.createConversation(title);
                    window.store.addNotification('success', t('conversations.created'));
                } catch (error) {
                    console.error('Hiba a beszélgetés létrehozásakor:', error);
                    window.store.addNotification('error', t('conversations.create_error'));
                }
            }
        };
        
        const select = async (id) => {
            if (currentId.value === id) return;
            
            window.store.setCurrentConversationId(id);
            try {
                await window.api.getMessages(id);
            } catch (error) {
                console.error('Hiba az üzenetek betöltésekor:', error);
                window.store.addNotification('error', t('conversations.load_messages_error'));
            }
        };
        
        // ConversationList.js-ben a deleteConv metódus
		const deleteConv = async (convId) => {
			if (!confirm('Biztosan törli ezt a beszélgetést?')) return;
			
			try {
				if (window.api && window.api.deleteConversation) {
					await window.api.deleteConversation(convId);
				}
				
				// Store frissítés
				if (window.store && window.store.removeConversation) {
					window.store.removeConversation(convId);
				}
				
				// Értesítés
				if (window.store && window.store.addNotification) {
					window.store.addNotification('success', 'Beszélgetés törölve');
				} else {
					console.log('✅ Beszélgetés törölve');
				}
			} catch (error) {
				console.error('Hiba a beszélgetés törlésekor:', error);
				if (window.store && window.store.addNotification) {
					window.store.addNotification('error', 'Hiba a törlés során');
				}
			}
		};
        
        Vue.onMounted(load);
        
        return {
            conversations,
            currentId,
            loading,
            t,
            formatRelativeTime,
            truncate,
            createNew,
            select,
            deleteConv
        };
    }
};

console.log('✅ ConversationList komponens betöltve');