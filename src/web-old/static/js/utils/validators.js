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
        return /\d/.test(password);
    },
    
    /**
     * Üres string ellenőrzése
     */
    isNotEmpty(value) {
        return value !== undefined && value !== null && String(value).trim() !== '';
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
    },
    
    /**
     * Hex szín validálása
     */
    isHexColor(color) {
        if (!color) return false;
        const re = /^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$/;
        return re.test(color);
    },
    
    /**
     * UUID validálása
     */
    isUUID(uuid) {
        if (!uuid) return false;
        const re = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
        return re.test(uuid);
    },
    
    /**
     * IP cím validálása (IPv4)
     */
    isIPv4(ip) {
        if (!ip) return false;
        const re = /^(\d{1,3}\.){3}\d{1,3}$/;
        if (!re.test(ip)) return false;
        const parts = ip.split('.');
        return parts.every(p => {
            const num = parseInt(p, 10);
            return num >= 0 && num <= 255;
        });
    },
    
    /**
     * Port szám validálása
     */
    isPort(port) {
        if (!port) return false;
        const num = parseInt(port, 10);
        return !isNaN(num) && num >= 1 && num <= 65535;
    },
    
    /**
     * Két jelszó egyezésének ellenőrzése
     */
    passwordsMatch(password, confirm) {
        return password === confirm;
    },
    
    /**
     * Távolság ellenőrzése (min/max)
     */
    isBetween(value, min, max) {
        const num = Number(value);
        return !isNaN(num) && num >= min && num <= max;
    },
    
    /**
     * Min hossz ellenőrzése
     */
    minLength(value, length) {
        return String(value).length >= length;
    },
    
    /**
     * Max hossz ellenőrzése
     */
    maxLength(value, length) {
        return String(value).length <= length;
    },
    
    /**
     * Regex ellenőrzés
     */
    matchesRegex(value, regex) {
        if (!value) return false;
        return regex.test(value);
    }
};

console.log('✅ Validators modul betöltve');