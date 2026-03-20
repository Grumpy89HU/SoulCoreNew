// ==============================================
// SOULCORE 3.0 - REST API kliens
// ==============================================

window.api = {
    // Alap URL
    baseUrl: '',
    
    // ========================================================================
    // ALAP FETCH METÓDUS
    // ========================================================================
    
    async fetch(endpoint, options = {}) {
        const url = this.baseUrl + endpoint;
        
        const headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            ...options.headers
        };
        
        // Token hozzáadása, ha van
        const token = localStorage.getItem('token');
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        
        const config = {
            credentials: 'include',
            headers,
            ...options
        };
        
        try {
            const response = await fetch(url, config);
            
            // Ha 401-es hiba, töröljük a session-t
            if (response.status === 401) {
                if (window.store) {
                    window.store.clearAuth();
                    window.store.addNotification('error', 'A munkamenet lejárt. Kérjük, jelentkezzen be újra.');
                }
                
                // Átirányítás a login oldalra, ha nem ott vagyunk
                if (!window.location.pathname.includes('/login')) {
                    window.location.href = '/login';
                }
                
                throw new Error('Unauthorized');
            }
            
            // Ha 403-as hiba
            if (response.status === 403) {
                throw new Error('Access denied');
            }
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || `HTTP error ${response.status}`);
            }
            
            return data;
            
        } catch (error) {
            console.error('❌ API hívás hiba:', error);
            throw error;
        }
    },
    
    // ========================================================================
    // AUTH API
    // ========================================================================
    
    async login(username, password) {
        const data = await this.fetch('/api/auth/login', {
            method: 'POST',
            body: JSON.stringify({ username, password })
        });
        
        if (window.store) {
            window.store.setAuth(data);
        }
        return data;
    },
    
    async logout() {
        await this.fetch('/api/auth/logout', { method: 'POST' });
        if (window.store) {
            window.store.clearAuth();
        }
        window.location.href = '/login';
    },
    
    async register(username, email, password) {
        const data = await this.fetch('/api/auth/register', {
            method: 'POST',
            body: JSON.stringify({ username, email, password })
        });
        
        return data;
    },
    
    async getCurrentUser() {
        try {
            const data = await this.fetch('/api/auth/me');
            if (data.authenticated && window.store) {
                window.store.setAuth(data);
            }
            return data;
        } catch (error) {
            return { authenticated: false };
        }
    },
    
    // ========================================================================
    // RENDSZER API
    // ========================================================================
    
    async getStatus() {
        const data = await this.fetch('/api/status');
        if (window.store) {
            window.store.setSystemId(data.system_id);
            window.store.setUptime(data.uptime);
            window.store.setStatus(data.status);
        }
        return data;
    },
    
    async getKingState() {
        const data = await this.fetch('/api/king/state');
        if (window.store) {
            window.store.setKingState(data);
        }
        return data;
    },
    
    async getSentinelStatus() {
        const data = await this.fetch('/api/sentinel/status');
        if (window.store) {
            window.store.setSentinelState(data);
        }
        return data;
    },
    
    // ========================================================================
    // BESZÉLGETÉSEK API
    // ========================================================================
    
    async getConversations(limit = 50, offset = 0) {
        const data = await this.fetch(`/api/conversations?limit=${limit}&offset=${offset}`);
        if (window.store) {
            window.store.setConversations(data.conversations);
        }
        return data;
    },
    
    async createConversation(title, model = null, systemPrompt = null) {
        const data = await this.fetch('/api/conversations', {
            method: 'POST',
            body: JSON.stringify({ title, model, system_prompt: systemPrompt })
        });
        
        // Új beszélgetés lekérése
        await this.getConversations();
        
        return data;
    },
    
    async getConversation(id) {
        const data = await this.fetch(`/api/conversations/${id}`);
        return data;
    },
    
    async getMessages(conversationId, limit = 100, before = null) {
        let url = `/api/conversations/${conversationId}/messages?limit=${limit}`;
        if (before) {
            url += `&before=${before}`;
        }
        
        const data = await this.fetch(url);
        if (window.store) {
            window.store.setMessages(conversationId, data.messages);
        }
        return data;
    },
    
    async sendMessage(conversationId, content) {
        const data = await this.fetch(`/api/conversations/${conversationId}/messages`, {
            method: 'POST',
            body: JSON.stringify({ role: 'user', content })
        });
        
        return data;
    },
    
    async deleteConversation(id) {
        await this.fetch(`/api/conversations/${id}`, { method: 'DELETE' });
        if (window.store) {
            window.store.removeConversation(id);
        }
    },
    
    // ========================================================================
    // MODELLEK API
    // ========================================================================
    
    async getModels(activeOnly = false) {
        const data = await this.fetch(`/api/models?active_only=${activeOnly}`);
        if (window.store) {
            window.store.setModels(data.models);
        }
        return data;
    },
    
    async activateModel(id) {
        const data = await this.fetch(`/api/models/${id}/activate`, { method: 'POST' });
        if (window.store) {
            window.store.activateModel(id);
        }
        return data;
    },
    
    // ========================================================================
    // PROMPTOK API
    // ========================================================================
    
    async getPrompts(category = null) {
        const url = category ? `/api/prompts?category=${category}` : '/api/prompts';
        const data = await this.fetch(url);
        if (window.store) {
            window.store.setPrompts(data.prompts);
        }
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
    // MODUL VEZÉRLÉS (ADMIN)
    // ========================================================================
    
    async controlModule(module, action) {
        const data = await this.fetch(`/api/modules/${module}/${action}`, {
            method: 'POST'
        });
        
        // Státusz frissítése
        setTimeout(() => this.getStatus(), 500);
        
        return data;
    }
};

console.log('✅ API modul betöltve');