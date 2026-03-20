// ==============================================
// SoulCore 3.0 - Main Application Entry Point
// ==============================================

// GLOBÁLIS SEGÉDFÜGGVÉNYEK - Ezeknek KELL előbb lenniük!
window.getNotificationIcon = function(type) {
    const icons = {
        'success': '✅',
        'error': '❌',
        'warning': '⚠️',
        'info': 'ℹ️'
    };
    return icons[type] || '📢';
};

window.getNotificationClass = function(type) {
    const classes = {
        'success': 'notification-success',
        'error': 'notification-error',
        'warning': 'notification-warning',
        'info': 'notification-info'
    };
    return classes[type] || 'notification-info';
};

// HIÁNYZÓ FÜGGVÉNY - státusz osztályokhoz
window.getStatusClass = function(status) {
    const classes = {
        'active': 'status-active',
        'ready': 'status-ready',
        'loading': 'status-loading',
        'error': 'status-error',
        'paused': 'status-paused',
        'frozen': 'status-frozen'
    };
    return classes[status] || 'status-unknown';
};

window.formatDate = function(timestamp) {
    if (!timestamp) return '';
    try {
        const date = new Date(timestamp);
        return date.toLocaleString(window.i18n?.language || 'hu-HU', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    } catch (e) {
        return timestamp || '';
    }
};

window.formatTime = function(timestamp) {
    if (!timestamp) return '';
    try {
        const date = new Date(timestamp);
        return date.toLocaleTimeString(window.i18n?.language || 'hu-HU', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    } catch (e) {
        return timestamp || '';
    }
};

window.formatBytes = function(bytes) {
    if (bytes === undefined || bytes === null) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let size = bytes;
    let unitIndex = 0;
    while (size >= 1024 && unitIndex < units.length - 1) {
        size /= 1024;
        unitIndex++;
    }
    return `${size.toFixed(1)} ${units[unitIndex]}`;
};

window.formatNumber = function(num, decimals = 1) {
    if (num === undefined || num === null) return '0';
    return Number(num).toFixed(decimals);
};

window.formatUptime = function(seconds) {
    if (!seconds) return '0s';
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    
    const parts = [];
    if (hours > 0) parts.push(`${hours}h`);
    if (minutes > 0) parts.push(`${minutes}m`);
    if (secs > 0 || parts.length === 0) parts.push(`${secs}s`);
    
    return parts.join(' ');
};

// Ideiglenes gettext amíg betölt a valódi
window.gettext = function(key, params = {}) {
    // Ha már betöltött a i18n, használjuk azt
    if (window.i18n && window.i18n.get) {
        return window.i18n.get(key, params);
    }
    
    // Különben visszaadjuk a kulcsot
    let text = key;
    
    // Paraméterek helyettesítése (ha vannak)
    if (params) {
        Object.keys(params).forEach(param => {
            text = text.replace(new RegExp(`{${param}}`, 'g'), params[param]);
        });
    }
    
    return text;
};

// t függvény - kompatibilitás a komponensekkel
window.t = function(key, params = {}) {
    return window.gettext(key, params);
};

// Nyelvváltó függvény
window.changeLanguage = function(lang) {
    if (window.i18n) {
        window.i18n.load(lang);
        document.documentElement.lang = lang;
        if (window.store) {
            window.store.setUserLanguage(lang);
        }
        // Értesítés a felhasználónak
        if (window.showNotification) {
            window.showNotification(window.gettext('ui.language_changed'), 'success', 3000);
        }
    }
};

// ==============================================
// FŐ VUE ALKALMAZÁS
// ==============================================

console.log('🚀 SoulCore Frontend indítása...');
console.log('📊 Vue verzió:', Vue.version);

// Gyökér komponens definiálása
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
        const language = Vue.ref(document.documentElement.lang || 'hu');
        
        // Notifications
        const notifications = Vue.ref([]);
        
        // User menu
        const showUserMenu = Vue.ref(false);
        
        // ====================================================================
        // COMPUTED PROPERTIES
        // ====================================================================
        
        const connected = Vue.computed(() => window.store?.connected || false);
        const isAdmin = Vue.computed(() => window.store?.isAdmin || false);
        const userName = Vue.computed(() => window.store?.userName || 'User');
        const userLanguage = Vue.computed(() => window.store?.userLanguage || 'hu');
        
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
        
        // Mobil nézet
        const isMobile = Vue.computed(() => window.innerWidth <= 768);
        
        // Rendszer ID (ha van)
        const systemId = Vue.computed(() => window.store?.systemId || '');
        
        // ====================================================================
        // METÓDUSOK
        // ====================================================================
        
        // Beszélgetés metódusok
        const createNewConversation = () => {
            const defaultTitle = window.gettext('ui.new_conversation') + ' ' + new Date().toLocaleString();
            const title = prompt(window.gettext('ui.conversation_title'), defaultTitle);
            if (title && window.socketManager) {
                window.socketManager.createConversation(title);
                window.showNotification(window.gettext('ui.conversation_created'), 'success');
            }
        };
        
        const loadConversation = (id) => {
            if (window.socketManager) {
                window.socketManager.loadConversation(id);
            }
        };
        
        const deleteConversation = (id) => {
            window.showConfirm(
                window.gettext('ui.delete_conversation'),
                window.gettext('ui.delete_conversation_confirm'),
                () => {
                    if (window.socketManager) {
                        window.socketManager.deleteConversation(id);
                        window.showNotification(window.gettext('ui.conversation_deleted'), 'success');
                    }
                }
            );
        };
        
        // Admin metódusok
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
                window.showNotification(window.gettext('ui.logged_out'), 'info');
            }
        };
        
        const controlModule = (module, action) => {
            if (window.socketManager) {
                window.socketManager.controlModule(module, action);
                window.showNotification(
                    window.gettext('ui.module_action', { module, action }),
                    'info'
                );
            }
        };
        
        const activateModel = (id) => {
            if (window.socketManager) {
                window.socketManager.activateModel(id);
                window.showNotification(window.gettext('ui.model_activated'), 'success');
            }
        };
        
        // Modál metódusok
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
        
        // Notification metódusok
        const showNotification = (message, type = 'info', timeout = 5000) => {
            const id = Date.now() + Math.random();
            notifications.value.push({ id, message, type });
            
            if (timeout > 0) {
                setTimeout(() => {
                    notifications.value = notifications.value.filter(n => n.id !== id);
                }, timeout);
            }
            
            return id;
        };
        
        const removeNotification = (id) => {
            notifications.value = notifications.value.filter(n => n.id !== id);
        };
        
        // Nyelv metódusok
        const changeLanguage = (lang) => {
            language.value = lang;
            window.changeLanguage(lang);
        };
        
        // User menu
        const hideUserMenu = () => {
            showUserMenu.value = false;
        };
        
        // Panel toggle
        const toggleMobileMenu = () => {
            console.log('Mobile menu toggle');
            // Implementáció
        };
        
        const toggleLeftPanel = () => {
            console.log('Left panel toggle');
            // Implementáció
        };
        
        const toggleRightPanel = () => {
            console.log('Right panel toggle');
            // Implementáció
        };
        
        // Adatfrissítés
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
        
        Vue.watch(() => window.store?.error, (newError) => {
            if (newError) {
                showNotification(newError, 'error', 5000);
            }
        });
        
        Vue.watch(language, (newLang) => {
            document.documentElement.lang = newLang;
        });
        
        // ====================================================================
        // ÉLETCIKLUS HOOKOK
        // ====================================================================
        
        Vue.onMounted(() => {
            // Idő frissítése
            const timeInterval = setInterval(() => {
                currentTime.value = new Date().toLocaleTimeString(language.value);
            }, 1000);
            
            // Státusz frissítése
            const statusInterval = setInterval(() => {
                if (connected.value && window.socketManager) {
                    window.socketManager.getStatus();
                }
            }, 5000);
            
            // Store figyelése socket eseményekre
            if (window.socketManager) {
                window.socketManager.on('notification', (data) => {
                    showNotification(data.message, data.type || 'info');
                });
            }
            
            // Cleanup
            Vue.onUnmounted(() => {
                clearInterval(timeInterval);
                clearInterval(statusInterval);
            });
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
            showUserMenu,
            
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
            isMobile,
            systemId,
            
            // GLOBÁLIS SEGÉDFÜGGVÉNYEK
            getNotificationIcon: window.getNotificationIcon,
            getNotificationClass: window.getNotificationClass,
            getStatusClass: window.getStatusClass, // HIÁNYZOTT!
            formatDate: window.formatDate,
            formatTime: window.formatTime,
            formatBytes: window.formatBytes,
            formatNumber: window.formatNumber,
            formatUptime: window.formatUptime,
            gettext: window.gettext,
            t: window.t,
            
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
            
            // User menu
            hideUserMenu,
            
            // Panel toggle
            toggleMobileMenu,
            toggleLeftPanel,
            toggleRightPanel,
            
            // Egyéb metódusok
            refreshData,
            copyToClipboard
        };
    }
};

// ========================================================================
// GLOBÁLIS SEGÉDFÜGGVÉNYEK VUE-N KERESZTÜL
// ========================================================================

window.showNotification = null; // Ezt majd a Vue beállítja

// ========================================================================
// KOMPONENSEK REGISZTRÁLÁSA
// ========================================================================

const app = Vue.createApp(App);

// Segédkomponensek (ha hiányoznak, dummy-t rakunk)
const registerComponent = (name, component) => {
    if (component) {
        app.component(name, component);
        console.log(`✅ ${name} regisztrálva`);
    } else {
        console.warn(`⚠️ ${name} nem elérhető, dummy komponens használata`);
        app.component(name, {
            template: `<div class="component-placeholder">${name} (betöltés...)</div>`
        });
    }
};

// Fő komponensek
registerComponent('ConversationList', window.ConversationList);
registerComponent('ChatBox', window.ChatBox);
registerComponent('TelemetryPanel', window.TelemetryPanel);
registerComponent('AdminPanel', window.AdminPanel);

// Admin alkomponensek
registerComponent('ModuleControl', window.ModuleControl);
registerComponent('ModelSelector', window.ModelSelector);
registerComponent('PromptEditor', window.PromptEditor);
registerComponent('SettingsPanel', window.SettingsPanel);
registerComponent('PersonalityManager', window.PersonalityManager);
registerComponent('AuditLog', window.AuditLog);
registerComponent('SystemMetrics', window.SystemMetrics);

// ========================================================================
// ERROR HANDLER
// ========================================================================

app.config.errorHandler = (err, instance, info) => {
    console.error('❌ Vue error:', err);
    console.error('📋 Info:', info);
    
    // Hibaüzenet megjelenítése
    if (window.showNotification) {
        window.showNotification(
            `Rendszer hiba: ${err.message}`,
            'error',
            5000
        );
    }
    
    if (window.store) {
        window.store.setError(err.message || 'Unknown Vue error');
    }
};

// ========================================================================
// VUE MOUNTOLÁSA
// ========================================================================

// Globális showNotification beállítása mountolás után
app.mount('#app');

// A showNotification elérhetővé tétele
window.showNotification = (message, type, timeout) => {
    // Megpróbáljuk elérni a Vue példányt
    const vm = document.querySelector('#app')?.__vue_app__?.config?.globalProperties;
    if (vm && vm.showNotification) {
        return vm.showNotification(message, type, timeout);
    } else {
        // Fallback console-ra
        console.log(`[${type}] ${message}`);
        return Date.now();
    }
};

console.log('✅ Vue app sikeresen elindult');
console.log('🌐 Nyelv:', document.documentElement.lang || 'hu');
console.log('🔗 Kapcsolat:', window.socketManager?.isConnected?.() ? 'aktív' : 'inaktív');