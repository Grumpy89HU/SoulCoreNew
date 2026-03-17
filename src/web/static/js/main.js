// Fő Vue alkalmazás
const { createApp } = Vue;

console.log('Vue verzió:', Vue.version);
console.log('Store létezik:', !!window.store);
console.log('SocketManager létezik:', !!window.socketManager);
console.log('Komponensek:', {
    ConversationList: !!window.ConversationList,
    ChatBox: !!window.ChatBox,
    TelemetryPanel: !!window.TelemetryPanel,
    AdminPanel: !!window.AdminPanel
});

// Gyökér komponens definiálása a szükséges adatokkal
const App = {
    setup() {
        // Reaktív állapotok a gyökér komponensben
        const heartbeatRunning = Vue.ref(true);
        const currentTime = Vue.ref(new Date().toLocaleTimeString());
        const showLoginModal = Vue.ref(false);
        const showConfirmModal = Vue.ref(false);
        const loginPassword = Vue.ref('');
        const loginError = Vue.ref('');
        const confirmTitle = Vue.ref('');
        const confirmMessage = Vue.ref('');
        const language = Vue.ref(window.i18n?.language || 'en');
        let confirmCallback = null;
        
        // Computed property-k a store-ból
        const heartbeat = Vue.computed(() => window.store?.state.heartbeat || {});
        const kingState = Vue.computed(() => window.store?.state.kingState || {});
        const connected = Vue.computed(() => window.store?.state.connected || false);
        
        // Segédfüggvények
        const formatUptime = (seconds) => {
            return window.store?.formatUptime ? window.store.formatUptime(seconds) : (seconds + 's');
        };
        
        const createNewConversation = () => {
            const title = prompt('Beszélgetés címe:', `Beszélgetés ${new Date().toLocaleString()}`);
            if (title && window.socketManager) {
                window.socketManager.createConversation(title);
            }
        };
        
        const adminLogin = () => {
            if (window.socketManager && loginPassword.value) {
                window.socketManager.adminLogin(loginPassword.value);
                showLoginModal.value = false;
                loginPassword.value = '';
            }
        };
        
        const confirmAction = () => {
            if (confirmCallback) {
                confirmCallback();
                confirmCallback = null;
            }
            showConfirmModal.value = false;
        };
        
        // i18n függvények
        const gettext = (key, params = {}) => {
            if (window.gettext) {
                return window.gettext(key, params);
            }
            return key;
        };
        
        const changeLanguage = (lang) => {
            language.value = lang;
            if (window.changeLanguage) {
                window.changeLanguage(lang);
            } else if (window.i18n) {
                window.i18n.load(lang);
            }
        };
        
        // Idő frissítése
        setInterval(() => {
            currentTime.value = new Date().toLocaleTimeString();
        }, 1000);
        
        return {
            // Állapotok
            heartbeatRunning,
            currentTime,
            showLoginModal,
            showConfirmModal,
            loginPassword,
            loginError,
            confirmTitle,
            confirmMessage,
            language,
            
            // Computed
            heartbeat,
            kingState,
            connected,
            
            // Metódusok
            formatUptime,
            createNewConversation,
            adminLogin,
            confirmAction,
            gettext,
            changeLanguage
        };
    }
};

// Komponensek regisztrálása
const app = createApp(App);

// Globális komponensek regisztrálása
if (window.ConversationList) {
    app.component('conversation-list', window.ConversationList);
    console.log('✅ conversation-list regisztrálva');
}

if (window.ChatBox) {
    app.component('chat-box', window.ChatBox);
    console.log('✅ chat-box regisztrálva');
}

if (window.TelemetryPanel) {
    app.component('telemetry-panel', window.TelemetryPanel);
    console.log('✅ telemetry-panel regisztrálva');
}

if (window.AdminPanel) {
    app.component('admin-panel', window.AdminPanel);
    console.log('✅ admin-panel regisztrálva');
}

// Mount
app.mount('#app');

console.log('✅ Vue app indult');