// Felhasználói menü komponens
window.UserMenu = {
    template: `
        <div class="user-menu" v-click-outside="closeMenu">
            <button class="user-menu-btn" @click="toggleMenu">
                <span class="user-avatar">👤</span>
                <span class="user-name">{{ userName }}</span>
                <span class="user-arrow">▼</span>
            </button>
            
            <div class="user-menu-dropdown" v-if="isOpen">
                <div class="dropdown-header">
                    <div class="user-info">
                        <span class="user-fullname">{{ userName }}</span>
                        <span class="user-role">{{ userRole }}</span>
                    </div>
                </div>
                
                <div class="dropdown-divider"></div>
                
                <a href="/admin" class="dropdown-item" v-if="isAdmin">
                    <span class="item-icon">⚙️</span>
                    <span class="item-text">{{ gettext('admin.title') }}</span>
                </a>
                
                <a href="#" class="dropdown-item" @click.prevent="showSettings">
                    <span class="item-icon">⚙️</span>
                    <span class="item-text">{{ gettext('ui.settings') }}</span>
                </a>
                
                <a href="#" class="dropdown-item" @click.prevent="showAbout">
                    <span class="item-icon">ℹ️</span>
                    <span class="item-text">{{ gettext('ui.about') }}</span>
                </a>
                
                <div class="dropdown-divider"></div>
                
                <a href="#" class="dropdown-item logout" @click.prevent="logout">
                    <span class="item-icon">🚪</span>
                    <span class="item-text">{{ gettext('ui.logout') }}</span>
                </a>
            </div>
        </div>
    `,
    
    setup() {
        // ====================================================================
        // REAKTÍV ÁLLAPOTOK
        // ====================================================================
        
        const isOpen = Vue.ref(false);
        
        // ====================================================================
        // COMPUTED PROPERTIES
        // ====================================================================
        
        const userName = Vue.computed(() => window.store?.userName || 'User');
        const userRole = Vue.computed(() => {
            const role = window.store?.userRole || 'user';
            return role === 'admin' ? gettext('admin.administrator') : gettext('admin.user');
        });
        const isAdmin = Vue.computed(() => window.store?.isAdmin || false);
        
        // ====================================================================
        // SEGÉDFÜGGVÉNYEK
        // ====================================================================
        
        const gettext = (key, params = {}) => {
            if (typeof window.gettext === 'function') {
                return window.gettext(key, params);
            }
            return key;
        };
        
        // ====================================================================
        // METÓDUSOK
        // ====================================================================
        
        const toggleMenu = () => {
            isOpen.value = !isOpen.value;
        };
        
        const closeMenu = () => {
            isOpen.value = false;
        };
        
        const showSettings = () => {
            // Itt lehetne megnyitni a beállítások modált
            console.log('Settings clicked');
            closeMenu();
        };
        
        const showAbout = () => {
            // Itt lehetne megnyitni a névjegy modált
            console.log('About clicked');
            closeMenu();
        };
        
        const logout = async () => {
            if (window.socketManager) {
                window.socketManager.adminLogout();
            }
            closeMenu();
        };
        
        return {
            // Állapotok
            isOpen,
            
            // Computed
            userName,
            userRole,
            isAdmin,
            
            // Metódusok
            toggleMenu,
            closeMenu,
            showSettings,
            showAbout,
            logout,
            gettext
        };
    }
};

console.log('✅ UserMenu betöltve globálisan');