// ==============================================
// SOULCORE 3.0 - Regisztrációs komponens
// ==============================================

window.RegisterForm = {
    name: 'RegisterForm',
    
    template: `
        <div class="auth-container">
            <div class="auth-box">
                <div class="auth-header">
                    <div class="auth-logo">✦</div>
                    <h2>{{ t('auth.register_title') }}</h2>
                    <p>{{ t('auth.register_subtitle') }}</p>
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
                        <div class="form-hint">{{ t('auth.username_hint') }}</div>
                    </div>
                    
                    <div class="form-group">
                        <label>{{ t('auth.email') }}</label>
                        <input 
                            type="email" 
                            v-model="form.email"
                            class="form-input"
                            :class="{ error: errors.email }"
                            :placeholder="t('auth.email_placeholder')"
                            @input="clearError('email')"
                            autocomplete="email"
                        >
                        <div v-if="errors.email" class="form-error">{{ errors.email }}</div>
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
                            autocomplete="new-password"
                        >
                        <div v-if="errors.password" class="form-error">{{ errors.password }}</div>
                        <div class="form-hint">{{ t('auth.password_hint') }}</div>
                    </div>
                    
                    <div class="form-group">
                        <label>{{ t('auth.confirm_password') }}</label>
                        <input 
                            type="password" 
                            v-model="form.confirmPassword"
                            class="form-input"
                            :class="{ error: errors.confirmPassword }"
                            :placeholder="t('auth.confirm_password_placeholder')"
                            @input="clearError('confirmPassword')"
                            autocomplete="off"
                        >
                        <div v-if="errors.confirmPassword" class="form-error">{{ errors.confirmPassword }}</div>
                    </div>
                    
                    <div class="form-options">
                        <label class="checkbox-label">
                            <input type="checkbox" v-model="agreeTerms">
                            <span>{{ t('auth.agree_terms') }} <a href="/terms" target="_blank">{{ t('auth.terms') }}</a></span>
                        </label>
                    </div>
                    
                    <button 
                        type="submit" 
                        class="btn btn-primary btn-block" 
                        :disabled="loading || !agreeTerms"
                    >
                        <span v-if="!loading">{{ t('auth.register_button') }}</span>
                        <span v-else class="spinner-small"></span>
                    </button>
                    
                    <div v-if="authError" class="auth-error">
                        {{ authError }}
                    </div>
                </form>
                
                <div class="auth-footer">
                    <p>{{ t('auth.have_account') }} <a href="/login">{{ t('auth.login_link') }}</a></p>
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
            email: '',
            password: '',
            confirmPassword: ''
        });
        
        const errors = Vue.ref({});
        const authError = Vue.ref('');
        const loading = Vue.ref(false);
        const agreeTerms = Vue.ref(false);
        
        // ====================================================================
        // SEGÉDFÜGGVÉNYEK
        // ====================================================================
        
        const t = (key, params = {}) => window.gettext(key, params);
        
        /**
         * Űrlap validálás
         */
        const validate = () => {
            const newErrors = {};
            
            // Felhasználónév ellenőrzése
            if (!form.value.username) {
                newErrors.username = t('auth.error_username_required');
            } else if (!window.validators.isUsername(form.value.username)) {
                newErrors.username = t('auth.error_username_invalid');
            }
            
            // Email ellenőrzése
            if (!form.value.email) {
                newErrors.email = t('auth.error_email_required');
            } else if (!window.validators.isEmail(form.value.email)) {
                newErrors.email = t('auth.error_email_invalid');
            }
            
            // Jelszó ellenőrzése
            if (!form.value.password) {
                newErrors.password = t('auth.error_password_required');
            } else if (!window.validators.isPassword(form.value.password)) {
                newErrors.password = t('auth.error_password_weak');
            }
            
            // Jelszó megerősítés
            if (form.value.password !== form.value.confirmPassword) {
                newErrors.confirmPassword = t('auth.error_password_mismatch');
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
         * Regisztráció küldése
         */
        const handleSubmit = async () => {
            if (!validate()) return;
            if (!agreeTerms.value) {
                authError.value = t('auth.error_terms_required');
                return;
            }
            
            loading.value = true;
            authError.value = '';
            
            try {
                await window.api.register(
                    form.value.username,
                    form.value.email,
                    form.value.password
                );
                
                window.store.addNotification('success', t('auth.register_success'));
                
                // Automatikus bejelentkezés regisztráció után
                await window.api.login(form.value.username, form.value.password);
                
                // Átirányítás a főoldalra
                window.location.href = '/';
                
            } catch (error) {
                console.error('Registration error:', error);
                authError.value = error.message || t('auth.error_registration_failed');
            } finally {
                loading.value = false;
            }
        };
        
        // ====================================================================
        // ÉLETCIKLUS
        // ====================================================================
        
        Vue.onMounted(() => {
            // Ha már be van jelentkezve, átirányítás
            if (window.store.authenticated) {
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
            agreeTerms,
            t,
            clearError,
            handleSubmit
        };
    }
};

console.log('✅ RegisterForm komponens betöltve');