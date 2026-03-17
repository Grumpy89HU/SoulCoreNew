// i18n JavaScript kliens oldalon
const i18n = {
    language: 'en',
    translations: {},
    
    async load(lang) {
        this.language = lang;
        try {
            const response = await fetch(`/static/lang/${lang}.json`);
            this.translations = await response.json();
        } catch (e) {
            console.error('Failed to load translations:', e);
        }
    },
    
    get(key, params = {}) {
        const keys = key.split('.');
        let value = this.translations;
        
        for (const k of keys) {
            if (value && value[k]) {
                value = value[k];
            } else {
                return key;
            }
        }
        
        if (typeof value === 'string') {
            return value.replace(/\{(\w+)\}/g, (match, p1) => params[p1] || match);
        }
        
        return value || key;
    }
};

// Globális segédfüggvény template-ekhez
window.gettext = (key, params) => i18n.get(key, params);

// Nyelv betöltése indításkor
const savedLang = localStorage.getItem('language') || 'en';
i18n.load(savedLang);