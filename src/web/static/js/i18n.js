// ==============================================
// SOULCORE 3.0 - Többnyelvű támogatás (i18n)
// ==============================================

window.i18n = {
    language: 'hu',
    translations: {},
    fallbackLanguage: 'hu',
    loadedLanguages: new Set(),
    listeners: [],
    debug: false,
    
    async load(lang) {
        if (!lang) lang = this.language;
        
        if (this.loadedLanguages.has(lang)) {
            this.language = lang;
            this._notifyListeners();
            localStorage.setItem('language', lang);
            document.documentElement.lang = lang;
            return true;
        }
        
        try {
            const response = await fetch(`/static/lang/${lang}.json`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const translations = await response.json();
            this.translations[lang] = translations;
            this.loadedLanguages.add(lang);
            this.language = lang;
            localStorage.setItem('language', lang);
            document.documentElement.lang = lang;
            this._notifyListeners();
            console.log(`✅ i18n: ${lang} nyelv betöltve`);
            return true;
        } catch (error) {
            console.error(`❌ i18n: Hiba a ${lang} nyelv betöltésekor:`, error);
            if (lang !== this.fallbackLanguage) {
                return this.load(this.fallbackLanguage);
            }
            return false;
        }
    },
    
    get(key, params = {}) {
        const keys = key.split('.');
        let value = this.translations[this.language];
        
        for (const k of keys) {
            if (value && value[k] !== undefined) {
                value = value[k];
            } else {
                if (this.debug) console.warn(`⚠️ i18n: Hiányzó fordítás - ${key}`);
                return key;
            }
        }
        
        if (typeof value === 'string') {
            let result = value;
            Object.keys(params).forEach(param => {
                result = result.replace(new RegExp(`{${param}}`, 'g'), params[param]);
            });
            return result;
        }
        
        return key;
    },
    
    setLanguage(lang) {
        if (lang === this.language) return;
        this.load(lang);
    },
    
    getSupportedLanguages() {
        return [
            { code: 'hu', name: 'Magyar' },
            { code: 'en', name: 'English' }
        ];
    },
    
    getLanguageName(code) {
        const names = { hu: 'Magyar', en: 'English' };
        return names[code] || code;
    },
    
    detectBrowserLanguage() {
        const browserLang = navigator.language?.split('-')[0] || 'hu';
        return this.getSupportedLanguages().some(l => l.code === browserLang) ? browserLang : this.fallbackLanguage;
    },
    
    onChange(cb) {
        this.listeners.push(cb);
        return () => { this.listeners = this.listeners.filter(l => l !== cb); };
    },
    
    _notifyListeners() {
        this.listeners.forEach(cb => { try { cb(this.language); } catch(e) {} });
    }
};

// GLOBÁLIS FÜGGVÉNYEK - EZ KELL A MAIN.JS-HEZ!
window.gettext = (key, params) => window.i18n.get(key, params);
window.t = window.gettext;

// Inicializálás
const savedLang = localStorage.getItem('language');
const initialLang = savedLang || window.i18n.detectBrowserLanguage();
window.i18n.load(initialLang);

console.log('✅ i18n modul betöltve');