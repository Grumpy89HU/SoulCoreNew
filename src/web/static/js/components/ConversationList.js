// Beszélgetés lista komponens - GLOBÁLISAN
window.ConversationList = {
    template: `
        <div class="conversation-list-container">
            <div class="panel-header">
                <span>📋 BESZÉLGETÉSEK</span>
                <button class="new-conv-btn" @click="createNew" :disabled="!connected">+ Új</button>
            </div>
            
            <div class="conversation-list">
                <div v-for="conv in conversations" :key="conv.id" 
                     class="conversation-item" 
                     :class="{ active: currentId == conv.id }"
                     @click="loadConversation(conv.id)">
                    
                    <div class="conv-title">{{ conv.title }}</div>
                    <div class="conv-meta">
                        <span>{{ formatDate(conv.updated_at) }}</span>
                        <span v-if="isAdmin" class="delete-btn" @click.stop="deleteConv(conv.id)">🗑️</span>
                    </div>
                </div>
                
                <div v-if="conversations.length === 0" class="empty-list">
                    Nincs még beszélgetés
                </div>
            </div>
        </div>
    `,
    
    setup() {
        // Window.store használata
        const conversations = Vue.computed(() => window.store?.conversations || []);
        const currentId = Vue.computed(() => window.store?.currentConversationId);
        const connected = Vue.computed(() => window.store?.connected || false);
        const isAdmin = Vue.computed(() => window.store?.isAdmin || false);
        
        const createNew = () => {
            const title = prompt('Beszélgetés címe:', `Beszélgetés ${new Date().toLocaleString()}`);
            if (title && window.socketManager) {
                window.socketManager.createConversation(title);
            }
        };
        
        const loadConversation = (id) => {
            if (window.socketManager) {
                window.socketManager.loadConversation(id);
            }
        };
        
        const deleteConv = (id) => {
            if (window.socketManager) {
                window.socketManager.deleteConversation(id);
            }
        };
        
        const formatDate = (dateStr) => {
            return window.store?.formatDate ? window.store.formatDate(dateStr) : dateStr;
        };
        
        return {
            conversations,
            currentId,
            connected,
            isAdmin,
            createNew,
            loadConversation,
            deleteConv,
            formatDate
        };
    }
};
window.ConversationList = ConversationList;
console.log('✅ ConversationList betöltve globálisan');