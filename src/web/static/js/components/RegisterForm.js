// ==============================================
// SOULCORE 3.0 - Regisztrációs komponens
// ==============================================

window.RegisterForm = {
    name: 'RegisterForm',
    
    template: `
        <div class="auth-box">
            <div class="auth-header">
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
                    >
                    <div v-if="errors.username" class="form-error">{{ errors.username }}</div>
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
                    >
                    <div v-if="errors.password" class="form-error">{{ errors.password }}</div>
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
                    >
                    <div v-if="errors.confirmPassword" class="form-error">{{ errors.confirmPassword }}</div>
                </div>
                
                <button 
                    type="submit" 
                    class="btn btn-primary" 
                    style="width: 100%;"
                    :disabled="loading"
                >
                    <span v-if="!loading">{{ t('auth.register_button') }}</span>
                    <span v-else class="spinner-small"></span>
                </button>
                
                <div v-if="authError" class="auth-error">
                    {{ authError }}
                </div>
            </form>
            
            <div class="auth-footer">
                <p>
                    {{ t('auth.have_account') }}
                    <a href="/login">{{ t('auth.login_link') }}</a>
                </p>
            </div>
        </div>
    `,
    
    setup() {
        const form = Vue.ref({
            username: '',
            email: '',
            password: '',
            confirmPassword: ''
        });
        
        const errors = Vue.ref({});
        const authError = Vue.ref('');
        const loading = Vue.ref(false);
        
        const t = (key, params = {}) => {
            return window.gettext ? window.gettext(key, params) : key;
        };
        
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
        
        const clearError = (field) => {
            if (errors.value[field]) {
                errors.value[field] = '';
            }
            authError.value = '';
        };
        
        const handleSubmit = async () => {
            if (!validate()) return;
            
            loading.value = true;
            authError.value = '';
            
            try {
                await window.api.register(
                    form.value.username,
                    form.value.email,
                    form.value.password
                );
                
                // Sikeres regisztráció után automatikus bejelentkezés
                await window.api.login(form.value.username, form.value.password);
                window.location.href = '/';
                
            } catch (error) {
                authError.value = error.message || t('auth.error_registration_failed');
            } finally {
                loading.value = false;
            }
        };
        
        return {
            form,
            errors,
            authError,
            loading,
            t,
            clearError,
            handleSubmit
        };
    }
};

console.log('✅ RegisterForm komponens betöltve');