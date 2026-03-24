// ==============================================
// SOULCORE 3.0 - REST API kliens
// ==============================================

window.api = {
    baseUrl: '',
    
    async fetch(endpoint, options = {}) {
        const headers = { 'Content-Type': 'application/json', ...options.headers };
        
        try {
            const response = await fetch(this.baseUrl + endpoint, {
                credentials: 'include',
                headers,
                ...options
            });
            
            if (response.status === 401) {
                window.store.clearAuth();
                if (!window.location.pathname.includes('/login')) {
                    window.location.href = '/login';
                }
                throw new Error('Unauthorized');
            }
            
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
            return data;
        } catch (e) {
            console.error('❌ API hiba:', e);
            throw e;
        }
    },
    
    // ========================================================================
    // AUTH
    // ========================================================================
    
    async login(username, password) {
        try {
            const data = await this.fetch('/api/auth/login', {
                method: 'POST',
                body: JSON.stringify({ username, password })
            });
            
            if (data && data.id && window.store) {
                window.store.setAuth(data);
            }
            
            return data;
        } catch (error) {
            console.error('Login API hiba:', error);
            throw error;
        }
    },
    
    async logout() {
        await this.fetch('/api/auth/logout', { method: 'POST' });
        window.store.clearAuth();
        window.location.href = '/login';
    },
    
    async register(username, email, password) {
        return await this.fetch('/api/auth/register', {
            method: 'POST',
            body: JSON.stringify({ username, email, password })
        });
    },
    
    async getCurrentUser() {
        try {
            const data = await this.fetch('/api/auth/me');
            if (data && data.authenticated && data.id) {
                if (window.store) {
                    window.store.setAuth(data);
                }
                return data;
            }
            return { authenticated: false };
        } catch (error) {
            console.error('Error getting current user:', error);
            return { authenticated: false };
        }
    },
    
    // ========================================================================
    // RENDSZER
    // ========================================================================
    
    async getStatus() {
        const data = await this.fetch('/api/status');
        window.store.setSystemId(data.system_id);
        window.store.setHeartbeat({ uptime_seconds: data.uptime });
        window.store.setModules(data.modules || {});
        return data;
    },
    
    async getKingState() {
        const data = await this.fetch('/api/king/state');
        window.store.setKingState(data);
        return data;
    },
    
    async getSentinelStatus() {
		try {
			const response = await this.fetch('/api/sentinel/status');
			return response;
		} catch (error) {
			// Sentinel nem elérhető - visszaadunk egy alapértelmezett állapotot
			console.warn('⚠️ Sentinel modul nem elérhető, dummy adatokkal dolgozom');
			return {
				available: false,
				status: 'unavailable',
				temperature: 0,
				vram_usage: 0,
				message: 'Sentinel modul nincs betöltve'
			};
		}
	},
    
    async getBlackboxStats() {
        const data = await this.fetch('/api/blackbox/stats');
        window.store.setBlackboxStats(data);
        return data;
    },
    
    async getBlackboxTrace(traceId) {
        return await this.fetch(`/api/blackbox/trace/${traceId}`);
    },
    
    async searchBlackbox(query, limit = 50) {
        return await this.fetch(`/api/blackbox/search?q=${encodeURIComponent(query)}&limit=${limit}`);
    },
    
    // ========================================================================
    // BESZÉLGETÉSEK
    // ========================================================================
    
    async getConversations() {
        try {
            const data = await this.fetch('/api/conversations');
            if (data && data.conversations) {
                window.store.setConversations(data.conversations);
                // Ha van beszélgetés, az elsőt állítsuk be aktuálisnak
                if (data.conversations.length > 0 && !window.store.currentConversationId) {
                    window.store.setCurrentConversationId(data.conversations[0].id);
                    await this.getMessages(data.conversations[0].id);
                }
            }
            return data;
        } catch (error) {
            console.error('Error loading conversations:', error);
            // Demo beszélgetések
            window.store.setConversations([
                { id: 1, title: 'Első beszélgetés', updated_at: Date.now(), message_count: 0 }
            ]);
            window.store.setCurrentConversationId(1);
            window.store.setMessages(1, []);
            return { conversations: [] };
        }
    },
    
    async createConversation(title) {
        const data = await this.fetch('/api/conversations', {
            method: 'POST',
            body: JSON.stringify({ title })
        });
        await this.getConversations();
        return data;
    },
    
    async getConversation(id) {
        return await this.fetch(`/api/conversations/${id}`);
    },
    
    async getMessages(conversationId) {
        const data = await this.fetch(`/api/conversations/${conversationId}/messages`);
        window.store.setMessages(conversationId, data.messages || []);
        return data;
    },
    
    async sendMessage(conversationId, content) {
        return await this.fetch(`/api/conversations/${conversationId}/messages`, {
            method: 'POST',
            body: JSON.stringify({ role: 'user', content })
        });
    },
    
    async deleteConversation(id) {
        await this.fetch(`/api/conversations/${id}`, { method: 'DELETE' });
        window.store.removeConversation(id);
    },
    
    async exportConversation(id, format = 'json') {
        return await this.fetch(`/api/conversations/${id}/export?format=${format}`);
    },
    
    // ========================================================================
    // MODELLEK
    // ========================================================================
    
    async getModels() {
        const data = await this.fetch('/api/models');
        window.store.setModels(data.models || []);
        return data;
    },
    
    async activateModel(id) {
        const data = await this.fetch(`/api/models/${id}/activate`, { method: 'POST' });
        window.store.activateModel(id);
        return data;
    },
    
    // ========================================================================
    // PROMPTOK
    // ========================================================================
    
    async getPrompts() {
        const data = await this.fetch('/api/prompts');
        window.store.setPrompts(data.prompts || []);
        return data;
    },
    
    async savePrompt(prompt) {
        const data = await this.fetch('/api/prompts', {
            method: 'POST',
            body: JSON.stringify(prompt)
        });
        await this.getPrompts();
        return data;
    },
    
    async deletePrompt(id) {
        await this.fetch(`/api/prompts/${id}`, { method: 'DELETE' });
        await this.getPrompts();
    },
    
    // ========================================================================
    // SZEMÉLYISÉGEK
    // ========================================================================
    
    async getPersonalities() {
        const data = await this.fetch('/api/personalities');
        window.store.setPersonalities(data.personalities || []);
        return data;
    },
    
    async savePersonality(personality) {
        const data = await this.fetch('/api/personalities', {
            method: 'POST',
            body: JSON.stringify(personality)
        });
        await this.getPersonalities();
        return data;
    },
    
    async activatePersonality(id) {
        const data = await this.fetch(`/api/personalities/${id}/activate`, { method: 'POST' });
        window.store.activatePersonality(id);
        return data;
    },
    
    async deletePersonality(id) {
        await this.fetch(`/api/personalities/${id}`, { method: 'DELETE' });
        await this.getPersonalities();
    },
    
    // ========================================================================
    // MODUL VEZÉRLÉS
    // ========================================================================
    
    async controlModule(module, action) {
        const data = await this.fetch(`/api/modules/${module}/${action}`, { method: 'POST' });
        setTimeout(() => this.getStatus(), 500);
        return data;
    },
    
    // ========================================================================
    // BEÁLLÍTÁSOK
    // ========================================================================
    
    async getSettings() {
        const data = await this.fetch('/api/settings');
        window.store.setSettings(data);
        return data;
    },
    
    async updateSetting(key, value, type = null, category = 'general') {
        return await this.fetch(`/api/settings/${key}`, {
            method: 'POST',
            body: JSON.stringify({ value, type, category })
        });
    },
    
    // ========================================================================
    // AUDIT LOG
    // ========================================================================
    
    async getAuditLog(limit = 100) {
        const data = await this.fetch(`/api/audit?limit=${Math.min(limit, 500)}`);
        window.store.setAuditLog(data.audit_log || []);
        return data;
    },
    
    // ========================================================================
    // METRIKÁK
    // ========================================================================
    
    async getMetrics(period = 'day', limit = 100) {
        const data = await this.fetch(`/api/metrics?period=${period}&limit=${Math.min(limit, 500)}`);
        window.store.setMetrics(data.metrics || {});
        return data;
    },
    
    // ========================================================================
    // VISION (EYE-CORE)
    // ========================================================================
    
    async processImage(imageData, source = 'upload') {
        return await this.fetch('/api/vision/process', {
            method: 'POST',
            body: JSON.stringify({ image: imageData, source })
        });
    },
    
    // ========================================================================
    // SANDBOX
    // ========================================================================
    
    async executeCode(code, context = {}) {
        return await this.fetch('/api/sandbox/execute', {
            method: 'POST',
            body: JSON.stringify({ code, context })
        });
    },
    
    // ========================================================================
    // GATEWAY
    // ========================================================================
    
    async getGateways() {
        const data = await this.fetch('/api/gateway/status');
        window.store.setGateways(data.gateways || []);
        return data;
    },
    
    async sendGatewayMessage(gatewayId, message) {
        return await this.fetch(`/api/gateway/message`, {
            method: 'POST',
            body: JSON.stringify({ gateway_id: gatewayId, message })
        });
    },
    
    // ========================================================================
    // EGÉSZSÉGÜGYI ELLENŐRZÉS
    // ========================================================================
    
    async healthCheck() {
        return await this.fetch('/health');
    },
    
    // ========================================================================
    // BATCH MŰVELETEK
    // ========================================================================
    
    async loadInitialData() {
        if (!window.store.authenticated) return;
        
        try {
            await Promise.all([
                this.getStatus(),
                this.getKingState(),
                this.getSentinelStatus(),
                this.getConversations(),
                this.getModels(),
                this.getPrompts(),
                this.getPersonalities(),
                this.getSettings()
            ]);
        } catch (e) {
            console.error('Hiba az inicializálás során:', e);
        }
    }
};

console.log('✅ API modul betöltve');