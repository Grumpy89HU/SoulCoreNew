// Fő Vue alkalmazás
const { createApp } = Vue;

console.log('🚀 SoulCore Frontend indítása...');
console.log('📊 Vue verzió:', Vue.version);
console.log('📦 Store létezik:', !!window.store);
console.log('🔌 SocketManager létezik:', !!window.socketManager);
console.log('🧩 Komponensek:', {
    ConversationList: !!window.ConversationList,
    ChatBox: !!window.ChatBox,
    TelemetryPanel: !!window.TelemetryPanel,
    AdminPanel: !!window.AdminPanel,
    ModuleControl: !!window.ModuleControl,
    ModelSelector: !!window.ModelSelector,
    PromptEditor: !!window.PromptEditor,
    SettingsPanel: !!window.SettingsPanel
});

// Globális segédfüggvények a template-ekhez
window.gettext = (key, params) => {
    if (window.i18n) {
        return window.i18n.get(key, params);
    }
    return key;
};

window.changeLanguage = (lang) => {
    if (window.i18n) {
        window.i18n.load(lang);
        if (window.store) {
            window.store.setUserLanguage(lang);
        }
    }
};

// Gyökér komponens definiálása a szükséges adatokkal
const App = {
    setup() {
        // ====================================================================
        // REAKTÍV ÁLLAPOTOK
        // ====================================================================
        
        // Alap állapotok
        const heartbeatRunning = Vue.ref(true);
        const currentTime = Vue.ref(new Date().toLocaleTimeString());
        const pageTitle = Vue.ref('SoulCore');
        const isLoading = Vue.ref(false);
        
        // Modálok
        const showLoginModal = Vue.ref(false);
        const showConfirmModal = Vue.ref(false);
        const showSettingsModal = Vue.ref(false);
        const showAboutModal = Vue.ref(false);
        
        // Login
        const loginPassword = Vue.ref('');
        const loginError = Vue.ref('');
        
        // Confirm modal
        const confirmTitle = Vue.ref('');
        const confirmMessage = Vue.ref('');
        let confirmCallback = null;
        
        // Settings
        const activeSettingsTab = Vue.ref('general');
        
        // Nyelv
        const language = Vue.ref(window.i18n?.language || window.store?.userLanguage || 'en');
        
        // Notifications (helyi, mert a store-ban is van)
        const notifications = Vue.ref([]);
        
        // ====================================================================
        // COMPUTED PROPERTIES (store-ból)
        // ====================================================================
        
        const connected = Vue.computed(() => window.store?.connected || false);
        const isAdmin = Vue.computed(() => window.store?.isAdmin || false);
        const userName = Vue.computed(() => window.store?.userName || 'User');
        const userLanguage = Vue.computed(() => window.store?.userLanguage || 'en');
        
        const heartbeat = Vue.computed(() => window.store?.heartbeat || {});
        const kingState = Vue.computed(() => window.store?.kingState || {});
        const queenState = Vue.computed(() => window.store?.queenState || {});
        const jesterState = Vue.computed(() => window.store?.jesterState || {});
        const valetState = Vue.computed(() => window.store?.valetState || {});
        const gpuStatus = Vue.computed(() => window.store?.gpuStatus || []);
        const sentinelState = Vue.computed(() => window.store?.sentinelState || {});
        const moduleStatuses = Vue.computed(() => window.store?.moduleStatuses || {});
        
        const conversations = Vue.computed(() => window.store?.conversations || []);
        const messages = Vue.computed(() => window.store?.messages || []);
        const currentConversationId = Vue.computed(() => window.store?.currentConversationId);
        
        const models = Vue.computed(() => window.store?.models || []);
        const prompts = Vue.computed(() => window.store?.prompts || []);
        const personalities = Vue.computed(() => window.store?.personalities || []);
        const settings = Vue.computed(() => window.store?.settings || {});
        
        const metrics = Vue.computed(() => window.store?.metrics || {});
        
        // ====================================================================
        // SEGÉDFÜGGVÉNYEK
        // ====================================================================
        
        const formatUptime = (seconds) => {
            return window.store?.formatUptime ? window.store.formatUptime(seconds) : (seconds + 's');
        };
        
        const formatDate = (dateStr) => {
            return window.store?.formatDate ? window.store.formatDate(dateStr) : dateStr;
        };
        
        const formatTime = (timestamp) => {
            return window.store?.formatTime ? window.store.formatTime(timestamp) : timestamp;
        };
        
        const formatBytes = (bytes) => {
            return window.store?.formatBytes ? window.store.formatBytes(bytes) : bytes;
        };
        
        const formatNumber = (num) => {
            return window.store?.formatNumber ? window.store.formatNumber(num) : num;
        };
        
        // ====================================================================
        // METÓDUSOK - BESZÉLGETÉSEK
        // ====================================================================
        
        const createNewConversation = () => {
            const defaultTitle = window.gettext('ui.new_conversation') + ' ' + new Date().toLocaleString();
            const title = prompt(window.gettext('ui.conversation_title'), defaultTitle);
            if (title && window.socketManager) {
                window.socketManager.createConversation(title);
            }
        };
        
        const loadConversation = (id) => {
            if (window.socketManager) {
                window.socketManager.loadConversation(id);
            }
        };
        
        const deleteConversation = (id) => {
            if (window.socketManager) {
                window.socketManager.deleteConversation(id);
            }
        };
        
        // ====================================================================
        // METÓDUSOK - ADMIN
        // ====================================================================
        
        const adminLogin = () => {
            if (window.socketManager && loginPassword.value) {
                window.socketManager.adminLogin(loginPassword.value);
                showLoginModal.value = false;
                loginPassword.value = '';
            }
        };
        
        const adminLogout = () => {
            if (window.socketManager) {
                window.socketManager.adminLogout();
            }
        };
        
        const controlModule = (module, action) => {
            if (window.socketManager) {
                window.socketManager.controlModule(module, action);
            }
        };
        
        const activateModel = (id) => {
            if (window.socketManager) {
                window.socketManager.activateModel(id);
            }
        };
        
        // ====================================================================
        // METÓDUSOK - MODÁLOK
        // ====================================================================
        
        const showConfirm = (title, message, callback) => {
            confirmTitle.value = title;
            confirmMessage.value = message;
            confirmCallback = callback;
            showConfirmModal.value = true;
        };
        
        const confirmAction = () => {
            if (confirmCallback) {
                confirmCallback();
                confirmCallback = null;
            }
            showConfirmModal.value = false;
        };
        
        const showNotification = (message, type = 'info', timeout = 5000) => {
            const id = Date.now() + Math.random();
            notifications.value.push({ id, message, type });
            
            if (timeout > 0) {
                setTimeout(() => {
                    const index = notifications.value.findIndex(n => n.id === id);
                    if (index !== -1) {
                        notifications.value.splice(index, 1);
                    }
                }, timeout);
            }
        };
        
        const removeNotification = (id) => {
            const index = notifications.value.findIndex(n => n.id === id);
            if (index !== -1) {
                notifications.value.splice(index, 1);
            }
        };
        
        // ====================================================================
        // METÓDUSOK - NYELV
        // ====================================================================
        
        const changeLanguage = (lang) => {
            language.value = lang;
            window.changeLanguage(lang);
            showNotification(window.gettext('ui.language_changed'), 'success', 3000);
        };
        
        // ====================================================================
        // METÓDUSOK - EGYÉB
        // ====================================================================
        
        const refreshData = () => {
            if (window.socketManager) {
                window.socketManager.getStatus();
                window.socketManager.getConversations();
                window.socketManager.getPrompts();
                window.socketManager.getSettings();
                window.socketManager.getModels();
                window.socketManager.getPersonalities();
            }
        };
        
        const copyToClipboard = (text) => {
            navigator.clipboard.writeText(text).then(() => {
                showNotification(window.gettext('ui.copied'), 'success', 2000);
            }).catch(() => {
                showNotification(window.gettext('ui.copy_failed'), 'error', 3000);
            });
        };
        
        // ====================================================================
        // WATCHEREK
        // ====================================================================
        
        // Store-beli értesítések figyelése
        Vue.watch(() => window.store?.error, (newError) => {
            if (newError) {
                showNotification(newError, 'error', 5000);
            }
        });
        
        // Nyelv változás figyelése
        Vue.watch(language, (newLang) => {
            document.documentElement.lang = newLang;
        });
        
        // ====================================================================
        // ÉLETCIKLUS HOOKOK
        // ====================================================================
        
        // Idő frissítése
        setInterval(() => {
            currentTime.value = new Date().toLocaleTimeString(userLanguage.value);
        }, 1000);
        
        // Rendszeres státusz lekérés
        setInterval(() => {
            if (connected.value && window.socketManager) {
                window.socketManager.getStatus();
            }
        }, 5000);
        
        // Kezdeti nyelv beállítása
        Vue.onMounted(() => {
            document.documentElement.lang = language.value;
            
            // Store figyelése socket eseményekre
            if (window.socketManager) {
                window.socketManager.on('notification', (data) => {
                    showNotification(data.message, data.type || 'info');
                });
            }
        });
        
        // ====================================================================
        // RETURN
        // ====================================================================
        
        return {
            // Állapotok
            heartbeatRunning,
            currentTime,
            pageTitle,
            isLoading,
            
            // Modálok
            showLoginModal,
            showConfirmModal,
            showSettingsModal,
            showAboutModal,
            
            // Login
            loginPassword,
            loginError,
            
            // Confirm
            confirmTitle,
            confirmMessage,
            
            // Settings
            activeSettingsTab,
            
            // Nyelv
            language,
            
            // Notifications
            notifications,
            
            // Computed
            connected,
            isAdmin,
            userName,
            userLanguage,
            
            heartbeat,
            kingState,
            queenState,
            jesterState,
            valetState,
            gpuStatus,
            sentinelState,
            moduleStatuses,
            
            conversations,
            messages,
            currentConversationId,
            
            models,
            prompts,
            personalities,
            settings,
            
            metrics,
            
            // Segédfüggvények
            formatUptime,
            formatDate,
            formatTime,
            formatBytes,
            formatNumber,
            gettext: window.gettext,
            
            // Beszélgetés metódusok
            createNewConversation,
            loadConversation,
            deleteConversation,
            
            // Admin metódusok
            adminLogin,
            adminLogout,
            controlModule,
            activateModel,
            
            // Modál metódusok
            showConfirm,
            confirmAction,
            
            // Notification metódusok
            showNotification,
            removeNotification,
            
            // Nyelv metódusok
            changeLanguage,
            
            // Egyéb metódusok
            refreshData,
            copyToClipboard
        };
    }
};

// ========================================================================
// KOMPONENSEK REGISZTRÁLÁSA
// ========================================================================

const app = createApp(App);

// Segédkomponensek (ha hiányoznak, dummy-t rakunk)
const registerComponent = (name, component) => {
    if (component) {
        app.component(name, component);
        console.log(`✅ ${name} regisztrálva`);
    } else {
        console.warn(`⚠️ ${name} nem elérhető, dummy komponens használata`);
        app.component(name, {
            template: `<div class="component-placeholder">${name} (loading...)</div>`
        });
    }
};

// Fő komponensek
registerComponent('conversation-list', window.ConversationList);
registerComponent('chat-box', window.ChatBox);
registerComponent('telemetry-panel', window.TelemetryPanel);
registerComponent('admin-panel', window.AdminPanel);

// Admin alkomponensek
registerComponent('module-control', window.ModuleControl);
registerComponent('model-selector', window.ModelSelector);
registerComponent('prompt-editor', window.PromptEditor);
registerComponent('settings-panel', window.SettingsPanel);

// ========================================================================
// EGYÉB KONFIGURÁCIÓ
// ========================================================================

// Globális error handler
app.config.errorHandler = (err, instance, info) => {
    console.error('Vue error:', err);
    console.error('Info:', info);
    if (window.store) {
        window.store.setError(err.message || 'Unknown Vue error');
    }
};

// Mount
app.mount('#app');

console.log('✅ Vue app sikeresen elindult');
console.log('🌐 Nyelv:', window.i18n?.language || 'en');
console.log('🔗 Kapcsolat:', window.socketManager?.isConnected() ? 'aktív' : 'inaktív');