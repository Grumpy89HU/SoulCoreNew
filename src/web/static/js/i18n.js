// ==============================================
// SOULCORE 3.0 - Többnyelvű támogatás (i18n)
// ==============================================

window.i18n = {
    language: 'hu',
    translations: {},
    fallbackLanguage: 'hu',
    loadedLanguages: new Set(),
    listeners: [],
    debug: false,  // Debug mód kapcsoló
    
    /**
     * Nyelv betöltése
     */
    async load(lang) {
        if (!lang) lang = this.language;
        
        // Ha már betöltöttük, csak nyelvet váltunk
        if (this.loadedLanguages.has(lang)) {
            this.language = lang;
            this._notifyListeners();
            localStorage.setItem('language', lang);
            document.documentElement.lang = lang;
            return true;
        }
        
        try {
            const response = await fetch(`/static/lang/${lang}.json`);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
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
            
            // Fallback magyarra
            if (lang !== this.fallbackLanguage) {
                return this.load(this.fallbackLanguage);
            }
            
            return false;
        }
    },
    
    /**
     * Fordítás lekérése
     */
    get(key, params = {}) {
        const keys = key.split('.');
        let value = this.translations[this.language];
        
        for (const k of keys) {
            if (value && value[k] !== undefined) {
                value = value[k];
            } else {
                // Ha nincs fordítás, visszaadjuk a kulcsot
                if (this.debug) {
                    console.warn(`⚠️ i18n: Hiányzó fordítás - ${key}`);
                }
                return key;
            }
        }
        
        if (typeof value === 'string') {
            // Paraméterek helyettesítése
            let result = value;
            Object.keys(params).forEach(param => {
                result = result.replace(new RegExp(`{${param}}`, 'g'), params[param]);
            });
            return result;
        }
        
        return key;
    },
    
    /**
     * Nyelv beállítása
     */
    setLanguage(lang) {
        if (lang === this.language) return;
        this.load(lang);
    },
    
    /**
     * Támogatott nyelvek listája
     */
    getSupportedLanguages() {
        return [
            { code: 'hu', name: 'Magyar' },
            { code: 'en', name: 'English' }
        ];
    },
    
    /**
     * Értesítés a nyelvváltozásról
     */
    onChange(callback) {
        this.listeners.push(callback);
        return () => {
            this.listeners = this.listeners.filter(cb => cb !== callback);
        };
    },
    
    _notifyListeners() {
        this.listeners.forEach(callback => {
            try {
                callback(this.language);
            } catch (e) {
                console.error('Hiba az i18n listenerben:', e);
            }
        });
    },
    
    /**
     * Böngésző nyelvének detektálása
     */
    detectBrowserLanguage() {
        const browserLang = navigator.language?.split('-')[0] || 'hu';
        const supported = this.getSupportedLanguages().map(l => l.code);
        return supported.includes(browserLang) ? browserLang : this.fallbackLanguage;
    }
};

// Globális segédfüggvények
window.gettext = (key, params = {}) => {
    return window.i18n ? window.i18n.get(key, params) : key;
};

window.t = window.gettext;

// Nyelv inicializálása
(async () => {
    const savedLang = localStorage.getItem('language');
    const browserLang = window.i18n.detectBrowserLanguage();
    const initialLang = savedLang || browserLang;
    
    await window.i18n.load(initialLang);
    console.log(`✅ i18n inicializálva: ${initialLang}`);
})();

console.log('✅ i18n modul betöltve');