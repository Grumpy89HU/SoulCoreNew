// REST API hívások - GLOBÁLISAN
window.api = {
    // ========================================================================
    // ALAP METÓDUSOK
    // ========================================================================
    
    async fetch(url, options = {}) {
        const startTime = Date.now();
        
        // Alapértelmezett headers
        const headers = {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            ...options.headers
        };
        
        // Session token (ha van)
        const token = localStorage.getItem('session_token');
        if (token) {
            headers['X-Session-Token'] = token;
        }
        
        const config = {
            headers,
            credentials: 'include', // Cookie-k küldése
            ...options
        };
        
        // Kimenet naplózása (csak debug módban)
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            console.log(`📡 API ${config.method || 'GET'} ${url}`);
        }
        
        try {
            const response = await fetch(url, config);
            
            // Válasz idő mérése
            const duration = Date.now() - startTime;
            
            // Sikertelen válasz kezelése
            if (!response.ok) {
                let errorData;
                try {
                    errorData = await response.json();
                } catch {
                    errorData = { message: response.statusText };
                }
                
                const error = new Error(errorData.message || `HTTP error ${response.status}`);
                error.status = response.status;
                error.data = errorData;
                throw error;
            }
            
            // JSON válasz feldolgozása
            const data = await response.json();
            
            // Naplózás (debug)
            if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
                console.log(`📡 API ${config.method || 'GET'} ${url} - ${duration}ms`);
            }
            
            return data;
            
        } catch (error) {
            console.error('❌ API fetch error:', error);
            
            // Hibaüzenet normalizálása
            const errorMessage = error.message || 'Unknown error';
            const status = error.status || 500;
            
            // Értesítés a store-nak (ha van)
            if (window.store) {
                window.store.setError(errorMessage);
            }
            
            // Újra dobjuk a hibát a hívó kezeléséhez
            throw {
                message: errorMessage,
                status,
                data: error.data,
                original: error
            };
        }
    },
    
    // ========================================================================
    // SEGÉDFÜGGVÉNYEK
    // ========================================================================
    
    _buildQueryString(params) {
        if (!params) return '';
        const query = Object.entries(params)
            .filter(([_, value]) => value !== undefined && value !== null)
            .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
            .join('&');
        return query ? `?${query}` : '';
    },
    
    _handleResponse(data, errorMessage) {
        if (data.error) {
            throw new Error(data.error);
        }
        return data;
    },
    
    // ========================================================================
    // RENDSZER STÁTUSZ
    // ========================================================================
    
    async getStatus() {
        const data = await this.fetch('/api/status');
        return this._handleResponse(data);
    },
    
    async getKingState() {
        const data = await this.fetch('/api/king/state');
        return this._handleResponse(data);
    },
    
    async getKingMetrics() {
        const data = await this.fetch('/api/king/metrics');
        return this._handleResponse(data);
    },
    
    async getJesterDiagnosis() {
        const data = await this.fetch('/api/jester/diagnosis');
        return this._handleResponse(data);
    },
    
    async getSentinelStatus() {
        const data = await this.fetch('/api/sentinel/status');
        return this._handleResponse(data);
    },
    
    async getBlackboxStats() {
        const data = await this.fetch('/api/blackbox/stats');
        return this._handleResponse(data);
    },
    
    async getBlackboxTrace(traceId) {
        const data = await this.fetch(`/api/blackbox/trace/${traceId}`);
        return this._handleResponse(data);
    },
    
    async searchBlackbox(query, limit = 50) {
        const qs = this._buildQueryString({ q: query, limit });
        const data = await this.fetch(`/api/blackbox/search${qs}`);
        return this._handleResponse(data);
    },
    
    // ========================================================================
    // BESZÉLGETÉSEK
    // ========================================================================
    
    async getConversations(params = {}) {
        const qs = this._buildQueryString(params);
        const data = await this.fetch(`/api/conversations${qs}`);
        return this._handleResponse(data);
    },
    
    async createConversation(data = {}) {
        const response = await this.fetch('/api/conversations', {
            method: 'POST',
            body: JSON.stringify(data)
        });
        return this._handleResponse(response);
    },
    
    async getConversation(id) {
        const data = await this.fetch(`/api/conversations/${id}`);
        return this._handleResponse(data);
    },
    
    async updateConversation(id, data) {
        const response = await this.fetch(`/api/conversations/${id}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
        return this._handleResponse(response);
    },
    
    async deleteConversation(id) {
        const response = await this.fetch(`/api/conversations/${id}`, {
            method: 'DELETE'
        });
        return this._handleResponse(response);
    },
    
    async getMessages(id, params = {}) {
        const qs = this._buildQueryString(params);
        const data = await this.fetch(`/api/conversations/${id}/messages${qs}`);
        return this._handleResponse(data);
    },
    
    async addMessage(id, message) {
        const response = await this.fetch(`/api/conversations/${id}/messages`, {
            method: 'POST',
            body: JSON.stringify(message)
        });
        return this._handleResponse(response);
    },
    
    async exportConversation(id, format = 'json') {
        const qs = this._buildQueryString({ format });
        const response = await this.fetch(`/api/conversations/${id}/export${qs}`);
        return response; // Lehet szöveg vagy JSON
    },
    
    // ========================================================================
    // PROMPT SABLONOK
    // ========================================================================
    
    async getPrompts(category = null) {
        const qs = category ? `?category=${encodeURIComponent(category)}` : '';
        const data = await this.fetch(`/api/prompts${qs}`);
        return this._handleResponse(data);
    },
    
    async savePrompt(prompt) {
        const response = await this.fetch('/api/prompts', {
            method: 'POST',
            body: JSON.stringify(prompt)
        });
        return this._handleResponse(response);
    },
    
    async getPrompt(id) {
        const data = await this.fetch(`/api/prompts/${id}`);
        return this._handleResponse(data);
    },
    
    async deletePrompt(id) {
        const response = await this.fetch(`/api/prompts/${id}`, {
            method: 'DELETE'
        });
        return this._handleResponse(response);
    },
    
    // ========================================================================
    // SZEMÉLYISÉGEK
    // ========================================================================
    
    async getPersonalities() {
        const data = await this.fetch('/api/personalities');
        return this._handleResponse(data);
    },
    
    async createPersonality(data) {
        const response = await this.fetch('/api/personalities', {
            method: 'POST',
            body: JSON.stringify(data)
        });
        return this._handleResponse(response);
    },
    
    async activatePersonality(id) {
        const response = await this.fetch(`/api/personalities/${id}/activate`, {
            method: 'POST'
        });
        return this._handleResponse(response);
    },
    
    // ========================================================================
    // BEÁLLÍTÁSOK
    // ========================================================================
    
    async getSettings(category = null) {
        const qs = category ? `?category=${encodeURIComponent(category)}` : '';
        const data = await this.fetch(`/api/settings${qs}`);
        return this._handleResponse(data);
    },
    
    async getSetting(key) {
        const data = await this.fetch(`/api/settings/${key}`);
        return this._handleResponse(data);
    },
    
    async updateSetting(key, value, type = null, category = 'general') {
        const response = await this.fetch(`/api/settings/${key}`, {
            method: 'POST',
            body: JSON.stringify({ value, type, category })
        });
        return this._handleResponse(response);
    },
    
    // ========================================================================
    // MODELLEK
    // ========================================================================
    
    async getModels(activeOnly = true) {
        const qs = this._buildQueryString({ active_only: activeOnly });
        const data = await this.fetch(`/api/models${qs}`);
        return this._handleResponse(data);
    },
    
    async addModel(model) {
        const response = await this.fetch('/api/models', {
            method: 'POST',
            body: JSON.stringify(model)
        });
        return this._handleResponse(response);
    },
    
    async activateModel(id) {
        const response = await this.fetch(`/api/models/${id}/activate`, {
            method: 'POST'
        });
        return this._handleResponse(response);
    },
    
    async deleteModel(id) {
        const response = await this.fetch(`/api/models/${id}`, {
            method: 'DELETE'
        });
        return this._handleResponse(response);
    },
    
    // ========================================================================
    // MODUL VEZÉRLÉS
    // ========================================================================
    
    async controlModule(module, action) {
        const response = await this.fetch(`/api/modules/${module}/${action}`, {
            method: 'POST'
        });
        return this._handleResponse(response);
    },
    
    // ========================================================================
    // VISION (EYE-CORE)
    // ========================================================================
    
    async processImage(imageData, source = 'upload') {
        const response = await this.fetch('/api/vision/process', {
            method: 'POST',
            body: JSON.stringify({ image: imageData, source })
        });
        return this._handleResponse(response);
    },
    
    // ========================================================================
    // SANDBOX
    // ========================================================================
    
    async executeCode(code, context = {}) {
        const response = await this.fetch('/api/tools/execute', {
            method: 'POST',
            body: JSON.stringify({ code, context })
        });
        return this._handleResponse(response);
    },
    
    // ========================================================================
    // ADMIN
    // ========================================================================
    
    async login(password) {
        const response = await this.fetch('/login', {
            method: 'POST',
            body: JSON.stringify({ password })
        });
        return this._handleResponse(response);
    },
    
    async logout() {
        const response = await this.fetch('/logout', {
            method: 'POST'
        });
        return this._handleResponse(response);
    },
    
    async getSession() {
        const data = await this.fetch('/api/session');
        return this._handleResponse(data);
    },
    
    async setLanguage(lang) {
        const response = await this.fetch('/api/language', {
            method: 'POST',
            body: JSON.stringify({ language: lang })
        });
        return this._handleResponse(response);
    },
    
    // ========================================================================
    // AUDIT LOG
    // ========================================================================
    
    async getAuditLog(limit = 100) {
        const qs = this._buildQueryString({ limit });
        const data = await this.fetch(`/api/audit${qs}`);
        return this._handleResponse(data);
    },
    
    // ========================================================================
    // METRIKÁK
    // ========================================================================
    
    async getMetrics(period = 'hour') {
        const qs = this._buildQueryString({ period });
        const data = await this.fetch(`/api/metrics${qs}`);
        return this._handleResponse(data);
    },
    
    // ========================================================================
    // EGÉSZSÉGÜGYI ELLENŐRZÉS
    // ========================================================================
    
    async healthCheck() {
        const data = await this.fetch('/health');
        return this._handleResponse(data);
    },
    
    // ========================================================================
    // BATCH MŰVELETEK
    // ========================================================================
    
    async getInitialData() {
        try {
            const [status, king, sentinel, conversations, prompts, settings, models, personalities] = await Promise.allSettled([
                this.getStatus(),
                this.getKingState(),
                this.getSentinelStatus(),
                this.getConversations({ limit: 50 }),
                this.getPrompts(),
                this.getSettings(),
                this.getModels(),
                this.getPersonalities()
            ]);
            
            return {
                status: status.status === 'fulfilled' ? status.value : null,
                king: king.status === 'fulfilled' ? king.value : null,
                sentinel: sentinel.status === 'fulfilled' ? sentinel.value : null,
                conversations: conversations.status === 'fulfilled' ? conversations.value : null,
                prompts: prompts.status === 'fulfilled' ? prompts.value : null,
                settings: settings.status === 'fulfilled' ? settings.value : null,
                models: models.status === 'fulfilled' ? models.value : null,
                personalities: personalities.status === 'fulfilled' ? personalities.value : null
            };
        } catch (error) {
            console.error('Batch data fetch error:', error);
            return {};
        }
    }
};

console.log('✅ API betöltve globálisan');