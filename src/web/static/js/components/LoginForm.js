// ==============================================
// SOULCORE 3.0 - Bejelentkezési komponens
// ==============================================

window.LoginForm = {
    name: 'LoginForm',
    
    template: `
        <div class="auth-box">
            <div class="auth-header">
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
                    >
                    <div v-if="errors.password" class="form-error">{{ errors.password }}</div>
                </div>
                
                <button 
                    type="submit" 
                    class="btn btn-primary" 
                    style="width: 100%;"
                    :disabled="loading"
                >
                    <span v-if="!loading">{{ t('auth.login_button') }}</span>
                    <span v-else class="spinner-small"></span>
                </button>
                
                <div v-if="authError" class="auth-error">
                    {{ authError }}
                </div>
            </form>
            
            <div class="auth-footer">
                <p>
                    {{ t('auth.no_account') }}
                    <a href="/register">{{ t('auth.register_link') }}</a>
                </p>
            </div>
        </div>
    `,
    
    setup() {
        const form = Vue.ref({
            username: '',
            password: ''
        });
        
        const errors = Vue.ref({});
        const authError = Vue.ref('');
        const loading = Vue.ref(false);
        
        const t = (key, params = {}) => {
            return window.gettext ? window.gettext(key, params) : key;
        };
        
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
                console.log('🔐 Bejelentkezés kísérlet:', form.value.username);
                await window.api.login(form.value.username, form.value.password);
                console.log('✅ Bejelentkezés sikeres');
                window.location.href = '/';
            } catch (error) {
                console.error('❌ Bejelentkezési hiba:', error);
                authError.value = error.message || t('auth.error_invalid_credentials');
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

console.log('✅ LoginForm komponens betöltve');