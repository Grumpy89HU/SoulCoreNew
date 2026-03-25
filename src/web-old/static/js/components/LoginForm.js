// ==============================================
// SOULCORE 3.0 - Bejelentkezési komponens
// ==============================================

window.LoginForm = {
    name: 'LoginForm',
    
    template: `
        <div class="auth-container">
            <div class="auth-box">
                <div class="auth-header">
                    <div class="auth-logo">✦</div>
                    <h2>{{ t('auth.login_title') }}</h2>
                    <p>{{ t('auth.login_subtitle') }}</p>
                </div>
                
                <form @submit.prevent="handleSubmit">
                    <div class="form-group">
                        <label>{{ t('auth.username') }}</label>
                        <input 
                            type="text" 
                            v-model="form.username"
                            class="form-input"
                            :class="{ error: errors.username }"
                            :placeholder="t('auth.username_placeholder')"
                            @input="clearError('username')"
                            autocomplete="username"
                        >
                        <div v-if="errors.username" class="form-error">{{ errors.username }}</div>
                    </div>
                    
                    <div class="form-group">
                        <label>{{ t('auth.password') }}</label>
                        <input 
                            type="password" 
                            v-model="form.password"
                            class="form-input"
                            :class="{ error: errors.password }"
                            :placeholder="t('auth.password_placeholder')"
                            @input="clearError('password')"
                            autocomplete="current-password"
                        >
                        <div v-if="errors.password" class="form-error">{{ errors.password }}</div>
                    </div>
                    
                    <div class="form-options">
                        <label class="checkbox-label">
                            <input type="checkbox" v-model="rememberMe">
                            <span>{{ t('auth.remember_me') }}</span>
                        </label>
                        <a href="/forgot-password" class="forgot-link">{{ t('auth.forgot_password') }}</a>
                    </div>
                    
                    <button 
                        type="submit" 
                        class="btn btn-primary btn-block" 
                        :disabled="loading || !apiReady"
                    >
                        <span v-if="!loading">{{ t('auth.login_button') }}</span>
                        <span v-else class="spinner-small"></span>
                    </button>
                    
                    <div v-if="!apiReady" class="auth-warning">
                        ⚠️ Kapcsolódás a szerverhez...
                    </div>
                    
                    <div v-if="authError" class="auth-error">
                        {{ authError }}
                    </div>
                </form>
                
                <div class="auth-footer">
                    <p>{{ t('auth.no_account') }} <a href="/register">{{ t('auth.register_link') }}</a></p>
                </div>
                
                <div class="auth-demo" v-if="showDemo && apiReady">
                    <button class="demo-btn" @click="demoLogin">
                        🧪 {{ t('auth.demo_login') }}
                    </button>
                </div>
            </div>
        </div>
    `,
    
    setup() {
        // ====================================================================
        // REAKTÍV ÁLLAPOTOK
        // ====================================================================
        
        const form = Vue.ref({
            username: '',
            password: ''
        });
        
        const errors = Vue.ref({});
        const authError = Vue.ref('');
        const loading = Vue.ref(false);
        const rememberMe = Vue.ref(false);
        const showDemo = Vue.ref(true);
        const apiReady = Vue.ref(false);
        
        // ====================================================================
        // SEGÉDFÜGGVÉNYEK
        // ====================================================================
        
        const t = (key, params = {}) => {
            return window.gettext ? window.gettext(key, params) : key;
        };
        
        /**
         * Űrlap validálás
         */
        const validate = () => {
            const newErrors = {};
            
            if (!form.value.username) {
                newErrors.username = t('auth.error_username_required');
            }
            
            if (!form.value.password) {
                newErrors.password = t('auth.error_password_required');
            }
            
            errors.value = newErrors;
            return Object.keys(newErrors).length === 0;
        };
        
        /**
         * Hiba törlése egy mezőről
         */
        const clearError = (field) => {
            if (errors.value[field]) {
                errors.value[field] = '';
            }
            authError.value = '';
        };
        
        /**
         * Bejelentkezés küldése
         */
        const handleSubmit = async () => {
            if (!validate()) return;
            
            // Várjuk meg, amíg az API betöltődik
            if (!window.api) {
                authError.value = 'A rendszer inicializálása folyamatban van, kérjük várjon...';
                return;
            }
            
            if (typeof window.api.login !== 'function') {
                authError.value = 'A bejelentkezés szolgáltatás nem elérhető';
                return;
            }
            
            loading.value = true;
            authError.value = '';
            
            try {
                const response = await window.api.login(form.value.username, form.value.password);
                
                if (rememberMe.value) {
                    localStorage.setItem('remember_me', 'true');
                    localStorage.setItem('username', form.value.username);
                } else {
                    localStorage.removeItem('remember_me');
                }
                
                if (window.store && window.store.addNotification) {
                    window.store.addNotification('success', t('auth.login_success'));
                }
                
                // Átirányítás a főoldalra
                window.location.href = '/';
                
            } catch (error) {
                console.error('Login error:', error);
                authError.value = error.message || t('auth.error_invalid_credentials');
            } finally {
                loading.value = false;
            }
        };
        
        /**
         * Demo bejelentkezés (fejlesztéshez)
         */
        const demoLogin = async () => {
            form.value.username = 'admin';
            form.value.password = 'admin123';
            await handleSubmit();
        };
        
        /**
         * Mentett felhasználónév betöltése
         */
        const loadSavedUsername = () => {
            if (localStorage.getItem('remember_me') === 'true') {
                const savedUsername = localStorage.getItem('username');
                if (savedUsername) {
                    form.value.username = savedUsername;
                    rememberMe.value = true;
                }
            }
        };
        
        /**
         * API elérhetőségének ellenőrzése
         */
        const checkApiReady = () => {
            if (window.api && typeof window.api.login === 'function') {
                apiReady.value = true;
                console.log('✅ API elérhető a LoginForm számára');
            } else {
                console.log('⏳ API betöltése folyamatban...');
                setTimeout(checkApiReady, 100);
            }
        };
        
        // ====================================================================
        // ÉLETCIKLUS
        // ====================================================================
        
        Vue.onMounted(() => {
            loadSavedUsername();
            checkApiReady();
            
            // Ha már be van jelentkezve, átirányítás
            if (window.store && window.store.authenticated) {
                window.location.href = '/';
            }
        });
        
        // ====================================================================
        // RETURN
        // ====================================================================
        
        return {
            form,
            errors,
            authError,
            loading,
            rememberMe,
            showDemo,
            apiReady,
            t,
            clearError,
            handleSubmit,
            demoLogin
        };
    }
};

console.log('✅ LoginForm komponens betöltve');