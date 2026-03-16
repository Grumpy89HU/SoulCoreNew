// Chat komponens
window.ChatBox = {
    template: `
        <div class="center-panel">
            <div class="chat-messages" ref="chatContainer">
                <div v-for="msg in messages" :key="msg.id" 
                     class="message" 
                     :class="msg.sender">
                    <div class="sender" v-if="msg.sender !== 'user'">{{ msg.senderName }}</div>
                    <div style="white-space: pre-wrap;">{{ msg.text }}</div>
                </div>
            </div>
            
            <div class="chat-input-area">
                <div class="input-container">
                    <select v-if="prompts.length" v-model="selectedPrompt" class="prompt-select">
                        <option v-for="p in prompts" :key="p.id" :value="p.id">
                            {{ p.name }}
                        </option>
                    </select>
                    
                    <input type="text" 
                           class="chat-input" 
                           v-model="inputMessage" 
                           @keyup.enter="sendMessage"
                           placeholder="Üzenet Kópénak..."
                           :disabled="!connected">
                    
                    <label class="upload-btn" for="image-upload">
                        <span>📷</span>
                    </label>
                    <input type="file" id="image-upload" accept="image/*" style="display: none;" @change="uploadImage">
                </div>
                
                <div class="model-info" v-if="currentModel">
                    Modell: {{ currentModel }}
                </div>
            </div>
        </div>
    `,
    
    setup() {
        const inputMessage = Vue.ref('');
        const selectedPrompt = Vue.ref(null);
        
        // Használd a store gettereit! (window.store.messages, nem window.store.state.messages)
        const messages = Vue.computed(() => window.store?.messages || []);
        const connected = Vue.computed(() => window.store?.connected || false);
        const prompts = Vue.computed(() => window.store?.prompts || []);
        const currentModel = Vue.computed(() => {
            const models = window.store?.models || [];
            const activeModel = models.find(m => m.is_active);
            return activeModel ? activeModel.name : 'Ismeretlen';
        });
        
        const sendMessage = () => {
            if (!inputMessage.value.trim() || !window.socketManager) return;
            
            window.socketManager.sendMessage(
                inputMessage.value, 
                window.store?.currentConversationId
            );
            
            inputMessage.value = '';
        };
        
        const uploadImage = (event) => {
            const file = event.target.files[0];
            if (!file || !window.socketManager) return;
            
            const reader = new FileReader();
            reader.onload = (e) => {
                window.socketManager.uploadImage(e.target.result, file.name);
            };
            reader.readAsDataURL(file);
        };
        
        return {
            inputMessage,
            selectedPrompt,
            messages,
            connected,
            prompts,
            currentModel,
            sendMessage,
            uploadImage
        };
    }
};

console.log('✅ ChatBox betöltve globálisan');