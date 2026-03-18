// i18n JavaScript kliens oldalon
const i18n = {
    language: 'en',
    translations: {},
    fallbackLanguage: 'en',
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
        
        // Ha már betöltöttük és nem force, akkor csak nyelvet váltunk
        if (this.loadedLanguages.has(lang) && !force) {
            this.language = lang;
            this._notifyListeners();
            localStorage.setItem('language', lang);
            document.documentElement.lang = lang;
            return Promise.resolve();
        }
        
        try {
            const response = await fetch(`/static/lang/${lang}.json`);
            
            if (!response.ok) {
                throw new Error(`HTTP error ${response.status}`);
            }
            
            const translations = await response.json();
            this.translations = this._mergeDeep(this.translations, translations);
            this.loadedLanguages.add(lang);
            this.language = lang;
            
            localStorage.setItem('language', lang);
            document.documentElement.lang = lang;
            this._notifyListeners();
            
            console.log(`🌐 Nyelv betöltve: ${lang}`);
            return translations;
            
        } catch (e) {
            console.error(`Failed to load translations for ${lang}:`, e);
            
            // Fallback angolra
            if (lang !== this.fallbackLanguage) {
                console.log(`⚠️ Fallback to ${this.fallbackLanguage}`);
                return this.load(this.fallbackLanguage);
            }
            
            throw e;
        }
    },
    
    /**
     * Több nyelv előzetes betöltése
     * @param {Array} languages - Nyelvek listája
     */
    async preload(languages) {
        const promises = languages.map(lang => 
            this.load(lang, false).catch(() => {})
        );
        await Promise.all(promises);
    },
    
    /**
     * Fordítás lekérése
     * @param {string} key - Pontozott kulcs (pl. 'ui.welcome')
     * @param {Object} params - Paraméterek a szövegben
     * @param {string} lang - Nyelv (alapértelmezett: current)
     * @returns {string} A lefordított szöveg
     */
    get(key, params = {}, lang = null) {
        const keys = key.split('.');
        let value = this.translations;
        
        // Ha másik nyelvet kérünk, de még nincs betöltve
        if (lang && lang !== this.language && !this.loadedLanguages.has(lang)) {
            this.load(lang).catch(() => {});
        }
        
        for (const k of keys) {
            if (value && value[k] !== undefined) {
                value = value[k];
            } else {
                // Ha nincs meg a fordítás, visszaadjuk a kulcsot
                return key;
            }
        }
        
        if (typeof value === 'string') {
            return value.replace(/\{(\w+)\}/g, (match, p1) => params[p1] !== undefined ? params[p1] : match);
        }
        
        // Ha a value nem string, akkor JSON.stringify
        if (value !== undefined) {
            return JSON.stringify(value);
        }
        
        return key;
    },
    
    /**
     * Több fordítás lekérése egyszerre
     * @param {Array} keys - Kulcsok listája
     * @param {Object} params - Paraméterek
     * @returns {Object} Fordítások objektumban
     */
    getAll(keys, params = {}) {
        const result = {};
        keys.forEach(key => {
            result[key] = this.get(key, params);
        });
        return result;
    },
    
    /**
     * Nyelv beállítása
     * @param {string} lang - Nyelvkód
     * @param {boolean} reload - Újratöltés, ha már betöltöttük
     */
    setLanguage(lang, reload = false) {
        if (lang === this.language && !reload) return;
        this.load(lang, reload);
    },
    
    /**
     * Támogatott nyelvek listájának lekérése
     * @returns {Array} Támogatott nyelvek
     */
    getSupportedLanguages() {
        return ['en', 'hu', 'de', 'fr', 'es']; // Bővíthető
    },
    
    /**
     * Nyelv nevének lekérése
     * @param {string} lang - Nyelvkód
     * @returns {string} Nyelv neve
     */
    getLanguageName(lang) {
        const names = {
            'en': 'English',
            'hu': 'Magyar',
            'de': 'Deutsch',
            'fr': 'Français',
            'es': 'Español'
        };
        return names[lang] || lang;
    },
    
    /**
     * Feliratkozás nyelvváltozásra
     * @param {Function} callback - Callback függvény
     * @returns {Function} Leiratkozó függvény
     */
    onChange(callback) {
        this.listeners.push(callback);
        return () => {
            this.listeners = this.listeners.filter(cb => cb !== callback);
        };
    },
    
    /**
     * Értesítés a nyelvváltozásról
     * @private
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
     * Objektumok mély összefésülése
     * @private
     */
    _mergeDeep(target, source) {
        const result = { ...target };
        
        for (const key in source) {
            if (source[key] instanceof Object && key in result) {
                result[key] = this._mergeDeep(result[key], source[key]);
            } else {
                result[key] = source[key];
            }
        }
        
        return result;
    },
    
    /**
     * Aktuális nyelv lekérése
     * @returns {string} Nyelvkód
     */
    getCurrentLanguage() {
        return this.language;
    },
    
    /**
     * Ellenőrzi, hogy egy nyelv támogatott-e
     * @param {string} lang - Nyelvkód
     * @returns {boolean} true, ha támogatott
     */
    isSupported(lang) {
        return this.getSupportedLanguages().includes(lang);
    },
    
    /**
     * Nyelv detektálása böngésző beállításokból
     * @returns {string} Detektált nyelv
     */
    detectBrowserLanguage() {
        const browserLang = navigator.language || navigator.userLanguage;
        if (!browserLang) return this.fallbackLanguage;
        
        const shortLang = browserLang.split('-')[0];
        return this.isSupported(shortLang) ? shortLang : this.fallbackLanguage;
    },
    
    /**
     * Szöveg hosszának lekérése karakterekben (többnyelvű támogatás)
     * @param {string} text - A szöveg
     * @returns {number} Karakterek száma
     */
    getLength(text) {
        if (!text) return 0;
        
        // Különböző nyelvek eltérő karaktereket használhatnak
        // Ez egy egyszerű megvalósítás
        return text.length;
    },
    
    /**
     * Szöveg csonkolása, ha túl hosszú
     * @param {string} text - A szöveg
     * @param {number} maxLength - Maximum hossz
     * @param {string} suffix - Utótag
     * @returns {string} Csonkolt szöveg
     */
    truncate(text, maxLength = 100, suffix = '…') {
        if (!text) return '';
        if (this.getLength(text) <= maxLength) return text;
        return text.substring(0, maxLength) + suffix;
    }
};

// Globális segédfüggvények
window.gettext = (key, params) => i18n.get(key, params);
window.ngettext = (singular, plural, count, params = {}) => {
    params.count = count;
    const key = count === 1 ? singular : plural;
    return i18n.get(key, params);
};

// Nyelv detektálás és betöltés
const savedLang = localStorage.getItem('language');
const browserLang = i18n.detectBrowserLanguage();
const initialLang = savedLang || browserLang;

i18n.load(initialLang).then(() => {
    console.log(`✅ i18n inicializálva: ${initialLang}`);
});

// Nyelvváltozás esemény figyelése
window.addEventListener('languagechange', () => {
    const newLang = i18n.detectBrowserLanguage();
    if (i18n.isSupported(newLang) && newLang !== i18n.language) {
        i18n.setLanguage(newLang);
    }
});

console.log('✅ i18n betöltve');