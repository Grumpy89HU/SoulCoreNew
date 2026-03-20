// Beszélgetés lista komponens - GLOBÁLISAN
window.ConversationList = {
    template: `
        <div class="conversation-list-container">
            <!-- Fejléc keresőmezővel -->
            <div class="panel-header">
                <div class="header-title">
                    <span>📋 {{ gettext('ui.conversations') }}</span>
                    <span class="conv-count" v-if="filteredConversations.length">({{ filteredConversations.length }})</span>
                </div>
                <button class="new-conv-btn" @click="createNew" :disabled="!connected || loading">
                    <span>+</span> {{ gettext('ui.new_conversation') }}
                </button>
            </div>
            
            <!-- Keresőmező -->
            <div class="search-box" v-if="conversations.length > 0">
                <input 
                    type="text" 
                    v-model="searchQuery" 
                    :placeholder="gettext('ui.search_conversations')"
                    class="search-input"
                >
                <span class="search-icon">🔍</span>
            </div>
            
            <!-- Rendezés és szűrés -->
            <div class="filter-bar" v-if="conversations.length > 0">
                <select v-model="sortBy" class="sort-select">
                    <option value="updated_desc">{{ gettext('ui.sort_recent') }}</option>
                    <option value="updated_asc">{{ gettext('ui.sort_oldest') }}</option>
                    <option value="title_asc">{{ gettext('ui.sort_title_asc') }}</option>
                    <option value="title_desc">{{ gettext('ui.sort_title_desc') }}</option>
                </select>
            </div>
            
            <!-- Betöltés jelző -->
            <div v-if="loading" class="loading-spinner">
                <div class="spinner"></div>
            </div>
            
            <!-- Beszélgetés lista -->
            <div class="conversation-list" v-else>
                <div v-for="conv in filteredAndSortedConversations" :key="conv.id" 
                     class="conversation-item" 
                     :class="{ 
                         active: currentId == conv.id,
                         'has-unread': conv.unread
                     }"
                     @click="loadConversation(conv.id)">
                    
                    <div class="conv-content">
                        <div class="conv-title">
                            <span v-if="conv.unread" class="unread-dot">●</span>
                            {{ conv.title }}
                        </div>
                        <div class="conv-preview" v-if="conv.preview">
                            {{ conv.preview }}
                        </div>
                        <div class="conv-meta">
                            <span class="conv-date">{{ formatDate(conv.updated_at) }}</span>
                            <span class="conv-model" v-if="conv.model">🤖 {{ conv.model }}</span>
                        </div>
                    </div>
                    
                    <div class="conv-actions" v-if="isAdmin">
                        <button class="icon-btn" @click.stop="renameConv(conv.id, conv.title)" title="Átnevezés">
                            ✏️
                        </button>
                        <button class="icon-btn delete-btn" @click.stop="deleteConv(conv.id)" title="Törlés">
                            🗑️
                        </button>
                    </div>
                </div>
                
                <div v-if="filteredConversations.length === 0 && conversations.length > 0" class="empty-search">
                    🔍 {{ gettext('ui.no_search_results') }}
                </div>
                
                <div v-if="conversations.length === 0 && !loading" class="empty-list">
                    <div class="empty-icon">💬</div>
                    <div class="empty-text">{{ gettext('ui.no_conversations') }}</div>
                    <button class="new-conv-btn" @click="createNew" :disabled="!connected">
                        {{ gettext('ui.create_first') }}
                    </button>
                </div>
            </div>
            
            <!-- Betöltés több (infinite scroll) -->
            <div v-if="hasMore" class="load-more">
                <button @click="loadMore" :disabled="loadingMore" class="load-more-btn">
                    <span v-if="!loadingMore">{{ gettext('ui.load_more') }}</span>
                    <span v-else>{{ gettext('ui.loading') }}</span>
                </button>
            </div>
        </div>
    `,
    
    setup() {
        // ====================================================================
        // REAKTÍV ÁLLAPOTOK
        // ====================================================================
        
        const conversations = Vue.computed(() => window.store?.conversations || []);
        const currentId = Vue.computed(() => window.store?.currentConversationId);
        const connected = Vue.computed(() => window.store?.connected || false);
        const isAdmin = Vue.computed(() => window.store?.isAdmin || false);
        
        // Keresés és szűrés
        const searchQuery = Vue.ref('');
        const sortBy = Vue.ref('updated_desc');
        
        // Lapozás
        const page = Vue.ref(1);
        const limit = Vue.ref(20);
        const hasMore = Vue.ref(false);
        const loading = Vue.ref(false);
        const loadingMore = Vue.ref(false);
        
        // ====================================================================
        // COMPUTED PROPERTIES
        // ====================================================================
        
        // Szűrt beszélgetések
        const filteredConversations = Vue.computed(() => {
            if (!searchQuery.value) return conversations.value;
            
            const query = searchQuery.value.toLowerCase();
            return conversations.value.filter(conv => 
                conv.title?.toLowerCase().includes(query) ||
                conv.preview?.toLowerCase().includes(query) ||
                conv.model?.toLowerCase().includes(query)
            );
        });
        
        // Rendezett és szűrt beszélgetések
        const filteredAndSortedConversations = Vue.computed(() => {
            let sorted = [...filteredConversations.value];
            
            switch (sortBy.value) {
                case 'updated_desc':
                    sorted.sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at));
                    break;
                case 'updated_asc':
                    sorted.sort((a, b) => new Date(a.updated_at) - new Date(b.updated_at));
                    break;
                case 'title_asc':
                    sorted.sort((a, b) => (a.title || '').localeCompare(b.title || ''));
                    break;
                case 'title_desc':
                    sorted.sort((a, b) => (b.title || '').localeCompare(a.title || ''));
                    break;
            }
            
            return sorted.slice(0, page.value * limit.value);
        });
        
        // ====================================================================
        // METÓDUSOK
        // ====================================================================
        
        const createNew = () => {
            if (!connected.value) {
                window.socketManager?.addSystemMessage?.(
                    window.gettext?.('errors.offline') || 'You are offline',
                    'error'
                );
                return;
            }
            
            const defaultTitle = window.gettext?.('ui.new_conversation') || 'New conversation';
            const title = prompt(
                window.gettext?.('ui.conversation_title') || 'Conversation title:',
                `${defaultTitle} ${new Date().toLocaleString()}`
            );
            
            if (title && window.socketManager) {
                window.socketManager.createConversation(title);
            }
        };
        
        const loadConversation = (id) => {
            if (window.socketManager) {
                window.socketManager.loadConversation(id);
                // Ha van unread jelzés, eltüntetjük
                const conv = conversations.value.find(c => c.id === id);
                if (conv && conv.unread) {
                    conv.unread = false;
                }
            }
        };
        
        const deleteConv = (id) => {
            const conv = conversations.value.find(c => c.id === id);
            const message = window.gettext?.('conversation.confirm_delete') || 
                `Are you sure you want to delete "${conv?.title || 'this conversation'}"?`;
            
            if (window.socketManager && confirm(message)) {
                window.socketManager.deleteConversation(id);
            }
        };
        
        const renameConv = (id, currentTitle) => {
            const newTitle = prompt(
                window.gettext?.('ui.rename_conversation') || 'Rename conversation:',
                currentTitle
            );
            
            if (newTitle && newTitle !== currentTitle && window.api) {
                window.api.updateConversation(id, { title: newTitle })
                    .then(() => {
                        window.socketManager?.addSystemMessage?.(
                            window.gettext?.('ui.rename_success') || 'Conversation renamed',
                            'success'
                        );
                    })
                    .catch(error => {
                        window.socketManager?.addSystemMessage?.(
                            error.message || 'Failed to rename',
                            'error'
                        );
                    });
            }
        };
        
        const loadMore = async () => {
            if (loadingMore.value || !hasMore.value) return;
            
            loadingMore.value = true;
            try {
                page.value++;
                // Itt lehetne új adatokat lekérni a szervertől
                // Most csak a meglévő listából mutatunk többet
            } finally {
                loadingMore.value = false;
            }
        };
        
        const formatDate = (dateStr) => {
            if (!dateStr) return '';
            
            const date = new Date(dateStr);
            const now = new Date();
            const diffMs = now - date;
            const diffMins = Math.floor(diffMs / 60000);
            const diffHours = Math.floor(diffMs / 3600000);
            const diffDays = Math.floor(diffMs / 86400000);
            
            if (diffMins < 1) return window.gettext?.('time.just_now') || 'just now';
            if (diffMins < 60) return `${diffMins} ${window.gettext?.('time.minutes_ago') || 'min ago'}`;
            if (diffHours < 24) return `${diffHours} ${window.gettext?.('time.hours_ago') || 'hours ago'}`;
            if (diffDays < 7) return `${diffDays} ${window.gettext?.('time.days_ago') || 'days ago'}`;
            
            return date.toLocaleDateString(window.store?.userLanguage || 'en');
        };
        
        const gettext = (key, params = {}) => {
            return window.gettext ? window.gettext(key, params) : key;
        };
        
        // ====================================================================
        // WATCHEREK
        // ====================================================================
        
        Vue.watch(conversations, (newConvs) => {
            // Ha új beszélgetések jönnek, ellenőrizzük a lapozást
            hasMore.value = newConvs.length > page.value * limit.value;
        }, { immediate: true });
        
        Vue.watch(searchQuery, () => {
            page.value = 1; // Kereséskor visszaállítjuk a lapozást
        });
        
        // ====================================================================
        // ÉLETCIKLUS
        // ====================================================================
        
        Vue.onMounted(() => {
            // Kezdeti lapozás beállítása
            hasMore.value = conversations.value.length > page.value * limit.value;
        });
        
        return {
            // Állapotok
            conversations,
            currentId,
            connected,
            isAdmin,
            searchQuery,
            sortBy,
            filteredConversations,
            filteredAndSortedConversations,
            loading,
            loadingMore,
            hasMore,
            
            // Metódusok
            createNew,
            loadConversation,
            deleteConv,
            renameConv,
            loadMore,
            formatDate,
            gettext
        };
    }
};

window.ConversationList = ConversationList;
console.log('✅ ConversationList betöltve globálisan');