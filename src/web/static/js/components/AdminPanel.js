// Admin panel (jobb oldali fülek)
window.AdminPanel = {
    template: `
        <div class="admin-panel-container">
            <div class="tabs">
                <div class="tab" :class="{ active: activeTab == 'modules' }" @click="activeTab = 'modules'">Modulok</div>
                <div class="tab" :class="{ active: activeTab == 'models' }" @click="activeTab = 'models'">Modellek</div>
                <div class="tab" :class="{ active: activeTab == 'prompts' }" @click="activeTab = 'prompts'">Promptok</div>
                <div class="tab" :class="{ active: activeTab == 'settings' }" @click="activeTab = 'settings'">Beállítások</div>
                <div class="tab" :class="{ active: activeTab == 'traces' }" @click="activeTab = 'traces'">Trace-ek</div>
            </div>
            
            <div class="tab-content">
                <!-- Modulok -->
                <div v-show="activeTab == 'modules'">
                    <module-control></module-control>
                </div>
                
                <!-- Modellek -->
                <div v-show="activeTab == 'models'">
                    <model-selector></model-selector>
                </div>
                
                <!-- Promptok -->
                <div v-show="activeTab == 'prompts'">
                    <prompt-editor></prompt-editor>
                </div>
                
                <!-- Beállítások -->
                <div v-show="activeTab == 'settings'">
                    <settings-panel></settings-panel>
                </div>
                
                <!-- Trace-ek -->
                <div v-show="activeTab == 'traces'">
                    <div v-for="trace in recentTraces" :key="trace.id" class="trace-item">
                        <span class="trace-time">{{ formatTime(trace.time) }}</span>
                        <span>{{ trace.text }}</span>
                    </div>
                </div>
            </div>
            
            <div class="admin-footer" v-if="!isAdmin">
                <button class="admin-login-btn" @click="showLogin">Admin belépés</button>
            </div>
        </div>
    `,
    
    setup() {
        const activeTab = Vue.ref('modules');
        const recentTraces = Vue.ref([]);
        const isAdmin = Vue.computed(() => window.store.state.isAdmin);
        
        // Trace-ek figyelése
        const addTrace = (text) => {
            recentTraces.value.unshift({
                id: Date.now(),
                time: Date.now(),
                text: text
            });
            if (recentTraces.value.length > 10) recentTraces.value.pop();
        };
        
        const showLogin = () => {
            const password = prompt('Admin jelszó:');
            if (password && window.socketManager) {
                window.socketManager.adminLogin(password);
            }
        };
        
        const formatTime = (timestamp) => {
            if (window.store && window.store.formatTime) {
                return window.store.formatTime(timestamp);
            }
            const date = new Date(timestamp);
            return date.toLocaleTimeString();
        };
        
        // Socket események trace-ekhez
        if (window.socketManager && window.socketManager.socket) {
            window.socketManager.socket.on('trace_event', (data) => {
                addTrace(data.text);
            });
        }
        
        return {
            activeTab,
            recentTraces,
            isAdmin,
            showLogin,
            formatTime
        };
    },
    
    components: {
        ModuleControl: window.ModuleControl,
        ModelSelector: window.ModelSelector,
        PromptEditor: window.PromptEditor,
        SettingsPanel: window.SettingsPanel
    }
};

window.AdminPanel = AdminPanel;
console.log('✅ AdminPanel betöltve globálisan');