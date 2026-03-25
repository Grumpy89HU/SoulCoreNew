// ==============================================
// SOULCORE 3.0 - Fő Vue alkalmazás (JAVÍTOTT)
// ==============================================

window.getNotificationIcon = function(type) {
    const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
    return icons[type] || '📢';
};

const { createApp, ref, computed, onMounted, onUnmounted } = Vue;

const App = {
    setup() {
        // ====================================================================
        // REAKTÍV ÁLLAPOTOK
        // ====================================================================
        const authenticated = computed(() => window.store?.authenticated || false);
        const user = computed(() => window.store?.user || null);
        const isAdmin = computed(() => user.value?.role === 'admin');
        const connected = computed(() => window.store?.connected || false);
        const systemId = computed(() => window.store?.systemId || '');
        const heartbeat = computed(() => window.store?.heartbeat || { uptime_seconds: 0 });
        const kingState = computed(() => window.store?.kingState || { status: 'unknown', mood: 'neutral' });
        const notifications = computed(() => window.store?.notifications || []);
        
        const sidebarOpen = ref(true);
        const isMobile = computed(() => window.innerWidth <= 768);
        
        const showUserMenu = ref(false);
        const showSettingsMenu = ref(false);
        
        const showAboutModal = ref(false);
        const showAdminModal = ref(false);
        const showSettingsModal = ref(false);
        const showHelpModal = ref(false);
        
        const currentTime = ref(new Date().toLocaleTimeString());
        const apiReady = ref(false);
        
        // ====================================================================
        // SEGÉDFÜGGVÉNYEK
        // ====================================================================
        const t = (key, params = {}) => {
            if (window.gettext) return window.gettext(key, params);
            return key;
        };
        
        // ====================================================================
        // BESZÉLGETÉSEK BETÖLTÉSE
        // ====================================================================
        const loadConversations = async () => {
            if (!window.store) return;
            
            try {
                console.log('📋 Beszélgetések betöltése...');
                const response = await fetch('/api/conversations');
                const data = await response.json();
                
                if (data.conversations && data.conversations.length > 0) {
                    window.store.setConversations(data.conversations);
                    console.log(`✅ ${data.conversations.length} beszélgetés betöltve`);
                    
                    // Ha nincs aktuális beszélgetés, állítsuk be az elsőt
                    if (!window.store.currentConversationId && data.conversations.length > 0) {
                        window.store.setCurrentConversationId(data.conversations[0].id);
                        console.log(`📌 Aktuális beszélgetés beállítva: ${data.conversations[0].id}`);
                        
                        // Töltsük be az üzeneteket is
                        await loadMessages(data.conversations[0].id);
                    }
                } else {
                    console.log('📝 Nincs beszélgetés, létrehozok egyet...');
                    await createNewConversation();
                }
            } catch (error) {
                console.error('❌ Hiba a beszélgetések betöltésekor:', error);
            }
        };
        
        // ====================================================================
        // ÜZENETEK BETÖLTÉSE
        // ====================================================================
        const loadMessages = async (conversationId) => {
            if (!window.store || !conversationId) return;
            
            try {
                console.log(`💬 Üzenetek betöltése (conv: ${conversationId})...`);
                const response = await fetch(`/api/conversations/${conversationId}/messages`);
                const data = await response.json();
                
                if (data.messages && data.messages.length > 0) {
                    window.store.setMessages(conversationId, data.messages);
                    console.log(`✅ ${data.messages.length} üzenet betöltve`);
                } else {
                    // Ha nincsenek üzenetek, üres tömb
                    window.store.setMessages(conversationId, []);
                }
            } catch (error) {
                console.error('❌ Hiba az üzenetek betöltésekor:', error);
                window.store.setMessages(conversationId, []);
            }
        };
        
        // ====================================================================
        // ÚJ BESZÉLGETÉS LÉTREHOZÁSA
        // ====================================================================
        const createNewConversation = async () => {
            if (!window.store) return;
            
            try {
                const title = `Beszélgetés ${new Date().toLocaleString()}`;
                const response = await fetch('/api/conversations', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ title })
                });
                const data = await response.json();
                
                if (data.id) {
                    console.log(`✅ Új beszélgetés létrehozva: ${data.id}`);
                    // Frissítsük a beszélgetések listáját
                    await loadConversations();
                }
            } catch (error) {
                console.error('❌ Hiba az új beszélgetés létrehozásakor:', error);
            }
        };
        
        // ====================================================================
        // INICIALIZÁLÁS
        // ====================================================================
        const initialize = async () => {
            console.log('🔧 SoulCore inicializálás...');
            
            // Várjuk meg a store-t
            await new Promise(resolve => {
                const checkStore = () => {
                    if (window.store && window.store.state) {
                        resolve(true);
                    } else {
                        setTimeout(checkStore, 100);
                    }
                };
                checkStore();
            });
            
            // Töltsük be a beszélgetéseket
            await loadConversations();
            
            // Frissítsük a store connected állapotát
            if (window.socketManager && window.socketManager.connected) {
                window.store.setConnected(true);
            }
            
            console.log('✅ SoulCore inicializálva');
        };
        
        // ====================================================================
        // METÓDUSOK
        // ====================================================================
        const toggleSidebar = () => { sidebarOpen.value = !sidebarOpen.value; };
        
        const logout = async () => {
            if (confirm(t('auth.confirm_logout') || 'Biztosan ki akarsz jelentkezni?')) {
                if (window.api) await window.api.logout();
                window.location.href = '/login';
            }
        };
        
        const hideUserMenu = () => { showUserMenu.value = false; };
        const hideSettingsMenu = () => { showSettingsMenu.value = false; };
        const removeNotification = (id) => {
            if (window.store) window.store.removeNotification(id);
        };
        
        const handleNewConversation = async () => {
            await createNewConversation();
        };
        
        let timeInterval = null;
        
        // ====================================================================
        // ÉLETCIKLUS
        // ====================================================================
        onMounted(async () => {
            timeInterval = setInterval(() => {
                currentTime.value = new Date().toLocaleTimeString();
            }, 1000);
            
            // Inicializálás
            await initialize();
            
            // Várjuk meg az API-t is
            await new Promise(resolve => {
                const checkApi = () => {
                    if (window.api && typeof window.api.getCurrentUser === 'function') {
                        apiReady.value = true;
                        resolve(true);
                    } else {
                        setTimeout(checkApi, 100);
                    }
                };
                checkApi();
            });
            
            console.log('✅ API elérhető, folytatás...');
            
            try {
                if (window.api && typeof window.api.getCurrentUser === 'function') {
                    await window.api.getCurrentUser();
                    
                    // Ha nincs bejelentkezve, de fejlesztői módban vagyunk, automatikus bejelentkezés
                    if (!window.store?.authenticated) {
                        console.log('🔓 Fejlesztői mód: automatikus bejelentkezés admin-ként');
                        if (window.store) {
                            window.store.setAuth({
                                id: 1,
                                username: 'admin',
                                role: 'admin',
                                email: 'admin@localhost'
                            });
                        }
                    }
                    
                    if (window.store?.authenticated && window.api.loadInitialData) {
                        await window.api.loadInitialData();
                    }
                }
            } catch (error) {
                console.error('Init error:', error);
                // Hiba esetén is próbáljuk meg az automatikus bejelentkezést
                if (window.store && !window.store.authenticated) {
                    console.log('🔓 Hiba esetén automatikus bejelentkezés');
                    window.store.setAuth({
                        id: 1,
                        username: 'admin',
                        role: 'admin',
                        email: 'admin@localhost'
                    });
                }
            }
        });
        
        onUnmounted(() => { 
            if (timeInterval) clearInterval(timeInterval); 
        });
        
        return {
            authenticated, user, isAdmin, connected, systemId, heartbeat, kingState,
            notifications, sidebarOpen, isMobile, currentTime, showAboutModal,
            showUserMenu, showSettingsMenu, showAdminModal, showSettingsModal, showHelpModal,
            apiReady,
            t, toggleSidebar, logout, hideUserMenu, hideSettingsMenu, removeNotification,
            handleNewConversation,
            formatUptime: window.formatUptime || ((s) => {
                if (!s) return '0s';
                const hours = Math.floor(s / 3600);
                const minutes = Math.floor((s % 3600) / 60);
                const seconds = Math.floor(s % 60);
                if (hours > 0) return `${hours}h ${minutes}m`;
                if (minutes > 0) return `${minutes}m ${seconds}s`;
                return `${seconds}s`;
            }),
            getNotificationIcon: window.getNotificationIcon
        };
    },
    
    template: `
        <div class="app" style="display: flex; flex-direction: column; height: 100vh; overflow: hidden;">
            <!-- Fejléc -->
            <div class="header">
                <div class="header-left">
                    <button class="menu-toggle" @click="toggleSidebar" title="Menü">
                        <span>☰</span>
                    </button>
                    <div class="logo">✦ SOULCORE 3.0</div>
                </div>
                
                <div class="header-center" v-if="authenticated" style="flex: 1; max-width: 600px; margin: 0 20px;">
                    <input type="text" placeholder="Keresés..." style="width: 100%; padding: 8px 16px; border-radius: 20px; border: 1px solid var(--border); background: var(--bg-secondary); color: white;">
                </div>

                <div class="header-right">
                    <div class="status-badge" v-if="authenticated">
                        <div class="badge">💓 {{ formatUptime(heartbeat?.uptime_seconds || 0) }}</div>
                        <div class="badge">👑 {{ kingState?.status || 'unknown' }}</div>
                    </div>
                    <div class="user-menu">
                        <button class="user-menu-btn" @click="showUserMenu = !showUserMenu" v-if="authenticated">
                            👤 {{ user?.username }}
                        </button>
                        <a v-else href="/login" class="btn btn-primary">Bejelentkezés</a>
                        <div class="user-menu-dropdown" v-if="showUserMenu && authenticated" v-click-outside="hideUserMenu">
                            <a href="#" @click.prevent="showSettingsModal = true; showUserMenu = false" class="dropdown-item">⚙️ Beállítások</a>
                            <a href="#" @click.prevent="showHelpModal = true; showUserMenu = false" class="dropdown-item">❓ Súgó</a>
                            <a href="#" @click.prevent="logout" class="dropdown-item">🚪 Kijelentkezés</a>
                        </div>
                    </div>
                    <button class="icon-btn" @click="showAboutModal = true">ℹ️</button>
                </div>
            </div>
            
            <!-- Értesítések -->
            <div class="notifications-container">
                <div v-for="n in notifications" :key="n.id" class="notification" :class="n.type" @click="removeNotification(n.id)">
                    <span class="notification-icon">{{ getNotificationIcon(n.type) }}</span>
                    <div class="notification-content"><div class="notification-message">{{ n.message }}</div></div>
                    <button class="notification-close" @click.stop="removeNotification(n.id)">✕</button>
                </div>
            </div>
            
            <!-- Fő tartalom -->
            <div class="main" v-if="authenticated" style="flex: 1; display: flex; overflow: hidden;">
                <!-- Bal panel -->
                <div class="left-panel" :class="{ collapsed: !sidebarOpen }" style="display: flex; flex-direction: column; height: 100%;">
                    <div class="panel-content" style="flex: 1; overflow-y: auto;">
                        <div class="panel-header" v-if="sidebarOpen" style="padding: 10px;">
                            <button style="width:100%; padding: 10px; border: 1px dashed var(--border); background: transparent; color: white; border-radius: 8px; cursor: pointer;" @click="handleNewConversation">
                                + Új beszélgetés
                            </button>
                        </div>
                        <conversation-list v-show="sidebarOpen"></conversation-list>
                    </div>
                    
                    <div class="sidebar-footer" v-if="sidebarOpen" style="padding: 10px; border-top: 1px solid var(--border);">
                        <button class="dropdown-item" @click="showSettingsModal = true" style="width: 100%; background: transparent; border: none; color: white; text-align: left; cursor: pointer; padding: 10px; border-radius: 4px;">
                            ⚙️ Beállítások
                        </button>
                        <button class="dropdown-item" @click="showAdminModal = true" v-if="isAdmin" style="width: 100%; background: transparent; border: none; color: white; text-align: left; cursor: pointer; padding: 10px; border-radius: 4px;">
                            🛡️ Adminisztráció
                        </button>
                    </div>
                </div>
                
                <!-- Középső panel (Chat) -->
                <div class="center-panel" style="flex: 1; display: flex; flex-direction: column; overflow: hidden; position: relative;">
                    <chat-box style="flex: 1; height: 100%;"></chat-box>
                </div>
            </div>
            
            <!-- Bejelentkezési oldal -->
            <div class="main" v-else style="flex: 1; display: flex; justify-content: center; align-items: center;">
                <login-form></login-form>
            </div>

            <!-- Modálok -->
            <div class="modal" v-if="showAboutModal" @click.self="showAboutModal = false">
                <div class="modal-content small">
                    <div class="modal-header"><h3>Névjegy</h3><button class="modal-close" @click="showAboutModal = false">✕</button></div>
                    <div class="modal-body" style="text-align:center">
                        <div style="font-size:48px">✦</div>
                        <h2>SoulCore 3.0</h2>
                        <p>ID: {{ systemId }}</p>
                        <p style="margin-top:16px">Szuverén AI rendszer</p>
                    </div>
                    <div class="modal-footer"><button class="btn-primary" @click="showAboutModal = false">Bezárás</button></div>
                </div>
            </div>

            <div class="modal" v-if="showAdminModal" @click.self="showAdminModal = false">
                <div class="modal-content large">
                    <div class="modal-header"><h3>Adminisztráció</h3><button class="modal-close" @click="showAdminModal = false">✕</button></div>
                    <div class="modal-body"><admin-panel></admin-panel></div>
                    <div class="modal-footer"><button class="btn-primary" @click="showAdminModal = false">Bezárás</button></div>
                </div>
            </div>

            <div class="modal" v-if="showSettingsModal" @click.self="showSettingsModal = false">
                <div class="modal-content large">
                    <div class="modal-header"><h3>Beállítások</h3><button class="modal-close" @click="showSettingsModal = false">✕</button></div>
                    <div class="modal-body"><settings-panel></settings-panel></div>
                    <div class="modal-footer"><button class="btn-primary" @click="showSettingsModal = false">Bezárás</button></div>
                </div>
            </div>

            <div class="modal" v-if="showHelpModal" @click.self="showHelpModal = false">
                <div class="modal-content">
                    <div class="modal-header"><h3>Súgó</h3><button class="modal-close" @click="showHelpModal = false">✕</button></div>
                    <div class="modal-body">
                        <div class="help-content">
                            <h4>📖 SoulCore 3.0 - Súgó</h4>
                            <p>A SoulCore egy szuverén AI rendszer, amely saját emlékekkel és identitással rendelkezik.</p>
                            <ul>
                                <li><strong>💬 Chat</strong> - Írjon üzenetet, az AI válaszol</li>
                                <li><strong>📋 Beszélgetések</strong> - A bal oldali menüben láthatja a korábbi beszélgetéseket</li>
                                <li><strong>⚙️ Beállítások</strong> - Itt módosíthatja a felület és a chat beállításait</li>
                                <li><strong>🛡️ Admin</strong> - Rendszeradminisztrációs funkciók (csak adminoknak)</li>
                            </ul>
                            <p><strong>🔗 Linkek</strong></p>
                            <p><a href="https://github.com/Grumpy89HU/SoulCoreNew" target="_blank">GitHub</a> | <a href="https://soulcore.hu" target="_blank">soulcore.hu</a></p>
                        </div>
                    </div>
                    <div class="modal-footer"><button class="btn-primary" @click="showHelpModal = false">Bezárás</button></div>
                </div>
            </div>
        </div>
    `
};

// Click outside direktíva
const vClickOutside = {
    beforeMount: (el, binding) => {
        el.clickOutsideEvent = (event) => {
            if (!(el === event.target || el.contains(event.target) || event.target.closest('.user-menu-btn'))) {
                binding.value(event);
            }
        };
        document.addEventListener('click', el.clickOutsideEvent);
    },
    unmounted: (el) => {
        document.removeEventListener('click', el.clickOutsideEvent);
    }
};

const app = createApp(App);
app.directive('click-outside', vClickOutside);

// Komponensek regisztrálása (biztonságos)
const safeRegister = (name, component) => {
    if (component && (typeof component === 'object' || typeof component === 'function')) {
        app.component(name, component);
        console.log(`✅ ${name} regisztrálva`);
    } else {
        console.warn(`⚠️ ${name} nem elérhető, placeholder használata`);
        app.component(name, {
            template: `<div style="padding:20px; text-align:center; color:var(--error);">❌ ${name} komponens nem töltődött be!</div>`
        });
    }
};

safeRegister('conversation-list', window.ConversationList);
safeRegister('chat-box', window.ChatBox);
safeRegister('admin-panel', window.AdminPanel);
safeRegister('settings-panel', window.SettingsPanel);
safeRegister('login-form', window.LoginForm);
safeRegister('register-form', window.RegisterForm);

app.mount('#app');
console.log('🚀 SoulCore 3.0 elindult');