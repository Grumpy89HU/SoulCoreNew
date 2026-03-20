// ==============================================
// SOULCORE 3.0 - Validátor függvények
// ==============================================

window.validators = {
    /**
     * Email cím validálása
     */
    isEmail(email) {
        if (!email) return false;
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    },
    
    /**
     * Felhasználónév validálása (3-20 karakter, csak betűk, számok, _)
     */
    isUsername(username) {
        if (!username) return false;
        const re = /^[a-zA-Z0-9_]{3,20}$/;
        return re.test(username);
    },
    
    /**
     * Jelszó validálása (min. 8 karakter, legalább egy szám)
     */
    isPassword(password) {
        if (!password) return false;
        if (password.length < 8) return false;
        // Legalább egy szám
        return /\d/.test(password);
    },
    
    /**
     * Üres string ellenőrzése
     */
    isNotEmpty(value) {
        return value !== undefined && value !== null && value.trim() !== '';
    },
    
    /**
     * Szám ellenőrzése
     */
    isNumber(value) {
        return !isNaN(parseFloat(value)) && isFinite(value);
    },
    
    /**
     * Egész szám ellenőrzése
     */
    isInteger(value) {
        return Number.isInteger(Number(value));
    },
    
    /**
     * Pozitív szám ellenőrzése
     */
    isPositive(value) {
        return this.isNumber(value) && Number(value) > 0;
    },
    
    /**
     * URL validálása
     */
    isUrl(url) {
        if (!url) return false;
        try {
            new URL(url);
            return true;
        } catch {
            return false;
        }
    },
    
    /**
     * JSON string ellenőrzése
     */
    isJson(str) {
        if (!str) return false;
        try {
            JSON.parse(str);
            return true;
        } catch {
            return false;
        }
    }
};

console.log('✅ Validators modul betöltve');