// ==============================================
// SoulCore 3.0 - Internationalization
// ==============================================

window.i18n = {
    language: 'hu',  // Alapértelmezett magyar
    translations: {},
    fallbackLanguage: 'hu',
    loadedLanguages: new Set(),
    listeners: [],
    
    /**
     * Nyelv betöltése
     * @param {string} lang - Nyelvkód (pl. 'en', 'hu')
     * @param {boolean} force - Újratöltés, ha már betöltöttük
     * @returns {Promise} A betöltés promise-ja
     */
    async load(lang, force = false) {
        if (!lang) lang = this.language;
        
        console.log(`🌐 i18n: Nyelv betöltése - ${lang}`);
        
        // Ha már betöltöttük és nem force, akkor csak nyelvet váltunk
        if (this.loadedLanguages.has(lang) && !force) {
            this.language = lang;
            this._notifyListeners();
            localStorage.setItem('language', lang);
            document.documentElement.lang = lang;
            console.log(`✅ i18n: Nyelv váltás - ${lang}`);
            return Promise.resolve();
        }
        
        try {
            // FONTOS: /static/lang/ mappa használata!
            const response = await fetch(`/static/lang/${lang}.json`);
            
            if (!response.ok) {
                throw new Error(`HTTP error ${response.status} - ${response.statusText}`);
            }
            
            const translations = await response.json();
            
            // Tárolás nyelv szerint
            this.translations[lang] = translations;
            this.loadedLanguages.add(lang);
            this.language = lang;
            
            localStorage.setItem('language', lang);
            document.documentElement.lang = lang;
            this._notifyListeners();
            
            console.log(`✅ i18n: Nyelv betöltve - ${lang} (${Object.keys(translations).length} kulcs)`);
            
            // UI frissítése - ha van Vue app, triggerelünk egy újrarenderelést
            this.updateUI();
            
            return translations;
            
        } catch (e) {
            console.error(`❌ i18n: Hiba a nyelv betöltésekor - ${lang}:`, e);
            
            // Fallback magyarra
            if (lang !== this.fallbackLanguage) {
                console.log(`⚠️ i18n: Fallback to ${this.fallbackLanguage}`);
                return this.load(this.fallbackLanguage, force);
            }
            
            // Utolsó fallback - üres fordítás
            this.translations[lang] = {};
            this.language = lang;
            
            return {};
        }
    },
    
    /**
     * Fordítás lekérése
     * @param {string} key - Pontozott kulcs (pl. 'ui.welcome')
     * @param {Object} params - Paraméterek a szövegben
     * @returns {string} A lefordított szöveg
     */
    get(key, params = {}) {
        const targetLang = this.language;
        const keys = key.split('.');
        
        // Ha nincs meg a nyelv, visszaadjuk a kulcsot
        if (!this.translations[targetLang]) {
            if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
                console.warn(`⚠️ i18n: Hiányzó nyelv - "${targetLang}"`);
            }
            return key;
        }
        
        let value = this.translations[targetLang];
        
        for (const k of keys) {
            if (value && value[k] !== undefined) {
                value = value[k];
            } else {
                // Ha nincs meg a fordítás, visszaadjuk a kulcsot
                if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
                    console.warn(`⚠️ i18n: Hiányzó fordítás - "${key}" (${targetLang})`);
                }
                return key;
            }
        }
        
        if (typeof value === 'string') {
            // Paraméterek helyettesítése
            let result = value;
            if (params && Object.keys(params).length > 0) {
                Object.keys(params).forEach(param => {
                    result = result.replace(new RegExp(`{${param}}`, 'g'), params[param]);
                });
            }
            return result;
        }
        
        return key;
    },
    
    /**
     * Nyelv beállítása
     * @param {string} lang - Nyelvkód
     */
    setLanguage(lang) {
        if (lang === this.language) return;
        this.load(lang);
    },
    
    /**
     * Támogatott nyelvek listája
     */
    getSupportedLanguages() {
        return ['hu', 'en'];
    },
    
    /**
     * Nyelv nevének lekérése
     */
    getLanguageName(lang) {
        const names = {
            'hu': 'Magyar',
            'en': 'English'
        };
        return names[lang] || lang;
    },
    
    /**
     * Feliratkozás nyelvváltozásra
     */
    onChange(callback) {
        this.listeners.push(callback);
        return () => {
            this.listeners = this.listeners.filter(cb => cb !== callback);
        };
    },
    
    /**
     * Értesítés a nyelvváltozásról
     */
    _notifyListeners() {
        this.listeners.forEach(callback => {
            try {
                callback(this.language);
            } catch (e) {
                console.error('Error in i18n listener:', e);
            }
        });
    },
    
    /**
     * Nyelv detektálása böngészőből
     */
    detectBrowserLanguage() {
        const browserLang = navigator.language || navigator.userLanguage;
        if (!browserLang) return this.fallbackLanguage;
        
        const shortLang = browserLang.split('-')[0];
        return this.getSupportedLanguages().includes(shortLang) ? shortLang : this.fallbackLanguage;
    },
    
    /**
     * UI frissítése
     */
    updateUI() {
        // Force update minden Vue komponensben
        // A komponensek a gettext/t függvényen keresztül automatikusan frissülnek
        // De triggerelünk egy egyedi eseményt
        window.dispatchEvent(new CustomEvent('languagechanged', { 
            detail: { language: this.language } 
        }));
    }
};

// Globális segédfüggvények
window.gettext = (key, params = {}) => {
    return window.i18n ? window.i18n.get(key, params) : key;
};

window.t = window.gettext;  // Rövid alias

// Nyelv detektálás és betöltés
(async function initI18n() {
    const savedLang = localStorage.getItem('language');
    const browserLang = window.i18n.detectBrowserLanguage();
    const initialLang = savedLang || browserLang || 'hu';
    
    await window.i18n.load(initialLang);
    console.log(`✅ i18n inicializálva: ${initialLang}`);
})();

console.log('✅ i18n modul betöltve');