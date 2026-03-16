// REST API hívások - GLOBÁLISAN
window.api = {
    async fetch(url, options = {}) {
        try {
            const response = await fetch(url, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error ${response.status}`);
            }
            
            const data = await response.json();
            return data;
        } catch (error) {
            console.error('API fetch error:', error);
            throw error;
        }
    },
    
    // Beszélgetések
    async getConversations() {
        return await this.fetch('/api/conversations');
    },
    
    async createConversation(title, model = null) {
        return await this.fetch('/api/conversations', {
            method: 'POST',
            body: JSON.stringify({ title, model })
        });
    },
    
    async deleteConversation(id) {
        return await this.fetch(`/api/conversations/${id}`, {
            method: 'DELETE'
        });
    },
    
    async getMessages(id, limit = 100) {
        const data = await this.fetch(`/api/conversations/${id}/messages?limit=${limit}`);
        return data.messages || [];
    },
    
    // Promptok
    async getPrompts() {
        const data = await this.fetch('/api/prompts');
        return data.prompts || [];
    },
    
    async savePrompt(prompt) {
        return await this.fetch('/api/prompts', {
            method: 'POST',
            body: JSON.stringify(prompt)
        });
    },
    
    async deletePrompt(id) {
        return await this.fetch(`/api/prompts/${id}`, {
            method: 'DELETE'
        });
    },
    
    // Beállítások
    async getSettings() {
        return await this.fetch('/api/settings');
    },
    
    async updateSetting(key, value, type = null, category = 'general') {
        return await this.fetch(`/api/settings/${key}`, {
            method: 'POST',
            body: JSON.stringify({ value, type, category })
        });
    },
    
    // Modellek
    async getModels() {
        const data = await this.fetch('/api/models');
        return data.models || [];
    },
    
    async addModel(model) {
        return await this.fetch('/api/models', {
            method: 'POST',
            body: JSON.stringify(model)
        });
    },
    
    async activateModel(id) {
        return await this.fetch(`/api/models/${id}/activate`, {
            method: 'POST'
        });
    },
    
    async deleteModel(id) {
        return await this.fetch(`/api/models/${id}`, {
            method: 'DELETE'
        });
    },
    
    // Státusz
    async getStatus() {
        return await this.fetch('/api/status');
    },
    
    async getKingState() {
        return await this.fetch('/api/king/state');
    },
    
    async getSentinelStatus() {
        return await this.fetch('/api/sentinel/status');
    },
    
    // Admin
    async login(password) {
        return await this.fetch('/login', {
            method: 'POST',
            body: JSON.stringify({ password })
        });
    },
    
    async logout() {
        return await this.fetch('/logout', {
            method: 'POST'
        });
    },
    
    async controlModule(module, action) {
        return await this.fetch(`/api/modules/${module}/${action}`, {
            method: 'POST'
        });
    },
    
    // Vision
    async processImage(imageData) {
        return await this.fetch('/api/vision/process', {
            method: 'POST',
            body: JSON.stringify({ image: imageData })
        });
    },
    
    // Sandbox
    async executeCode(code, context = {}) {
        return await this.fetch('/api/tools/execute', {
            method: 'POST',
            body: JSON.stringify({ code, context })
        });
    }
};

console.log('✅ API betöltve globálisan');