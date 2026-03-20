// Validátor függvények

/**
 * Ellenőrzi, hogy a megadott érték érvényes e-mail cím-e
 * @param {string} email - Az e-mail cím
 * @returns {boolean} true, ha érvényes
 */
function isEmail(email) {
    if (typeof email !== 'string') return false;
    
    // RFC 5322 compliant regex (egyszerűsített)
    const emailRegex = /^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$/;
    return emailRegex.test(email) && email.length <= 254;
}

/**
 * Ellenőrzi, hogy a megadott érték érvényes telefonszám-e
 * @param {string} phone - A telefonszám
 * @param {string} country - Országkód (alapértelmezett: 'HU')
 * @returns {boolean} true, ha érvényes
 */
function isPhone(phone, country = 'HU') {
    if (typeof phone !== 'string') return false;
    
    // Csak a számjegyeket tartjuk meg
    const digits = phone.replace(/\D/g, '');
    
    // Országspecifikus ellenőrzések
    switch (country.toUpperCase()) {
        case 'HU':
            // Magyar telefonszám: 9-12 számjegy (vagy +36 előhívóval)
            return digits.length >= 9 && digits.length <= 12;
        case 'US':
            // USA: 10 számjegy (vagy +1 előhívóval)
            return digits.length === 10 || (digits.length === 11 && digits[0] === '1');
        case 'UK':
            // UK: 10-11 számjegy (vagy +44 előhívóval)
            return digits.length >= 10 && digits.length <= 12;
        default:
            // Általános: minimum 8 számjegy
            return digits.length >= 8 && digits.length <= 15;
    }
}

/**
 * Ellenőrzi, hogy a megadott érték nem üres string-e
 * @param {string} str - A vizsgálandó string
 * @param {boolean} trim - Trim-elés előtte?
 * @returns {boolean} true, ha nem üres
 */
function notEmpty(str, trim = true) {
    if (str === undefined || str === null) return false;
    if (typeof str !== 'string') return false;
    
    if (trim) {
        return str.trim().length > 0;
    }
    return str.length > 0;
}

/**
 * Ellenőrzi, hogy a megadott érték érvényes URL-e
 * @param {string} url - Az URL
 * @param {Array} protocols - Engedélyezett protokollok (pl. ['http', 'https'])
 * @returns {boolean} true, ha érvényes
 */
function isUrl(url, protocols = ['http', 'https']) {
    if (typeof url !== 'string') return false;
    
    try {
        const parsed = new URL(url);
        return protocols.includes(parsed.protocol.replace(':', ''));
    } catch {
        return false;
    }
}

/**
 * Ellenőrzi, hogy a megadott érték érvényes IP cím-e (IPv4 vagy IPv6)
 * @param {string} ip - Az IP cím
 * @returns {boolean} true, ha érvényes
 */
function isIpAddress(ip) {
    if (typeof ip !== 'string') return false;
    
    // IPv4
    const ipv4Regex = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;
    if (ipv4Regex.test(ip)) return true;
    
    // IPv6 (egyszerűsített)
    const ipv6Regex = /^(([0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|:((:[0-9a-fA-F]{1,4}){1,7}|:)|fe80:(:[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|::(ffff(:0{1,4}){0,1}:){0,1}((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])|([0-9a-fA-F]{1,4}:){1,4}:((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9]))$/;
    return ipv6Regex.test(ip);
}

/**
 * Ellenőrzi, hogy a megadott érték érvényes domain név-e
 * @param {string} domain - A domain név
 * @returns {boolean} true, ha érvényes
 */
function isDomain(domain) {
    if (typeof domain !== 'string') return false;
    
    const domainRegex = /^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$/;
    return domainRegex.test(domain) && domain.length <= 255;
}

/**
 * Ellenőrzi, hogy a megadott érték szám-e (integer vagy float)
 * @param {*} value - A vizsgálandó érték
 * @param {Object} options - Opciók (min, max, integer)
 * @returns {boolean} true, ha érvényes szám
 */
function isNumber(value, options = {}) {
    const { min, max, integer = false } = options;
    
    if (value === null || value === undefined) return false;
    
    const num = Number(value);
    if (isNaN(num)) return false;
    
    if (integer && !Number.isInteger(num)) return false;
    
    if (min !== undefined && num < min) return false;
    if (max !== undefined && num > max) return false;
    
    return true;
}

/**
 * Ellenőrzi, hogy a megadott érték érvényes UUID-e (v4)
 * @param {string} uuid - Az UUID
 * @returns {boolean} true, ha érvényes
 */
function isUuid(uuid) {
    if (typeof uuid !== 'string') return false;
    
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
    return uuidRegex.test(uuid);
}

/**
 * Ellenőrzi, hogy a megadott érték érvényes hexadecimális színkód-e
 * @param {string} color - A színkód (pl. #FF00FF)
 * @returns {boolean} true, ha érvényes
 */
function isHexColor(color) {
    if (typeof color !== 'string') return false;
    
    const hexRegex = /^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$/;
    return hexRegex.test(color);
}

/**
 * Ellenőrzi, hogy a megadott érték érvényes JSON-e
 * @param {string} str - A vizsgálandó string
 * @returns {boolean} true, ha érvényes JSON
 */
function isJson(str) {
    if (typeof str !== 'string') return false;
    
    try {
        JSON.parse(str);
        return true;
    } catch {
        return false;
    }
}

/**
 * Ellenőrzi, hogy a megadott érték erős jelszó-e
 * @param {string} password - A jelszó
 * @param {Object} options - Opciók (minLength, requireUppercase, requireLowercase, requireNumbers, requireSpecial)
 * @returns {boolean} true, ha erős jelszó
 */
function isStrongPassword(password, options = {}) {
    if (typeof password !== 'string') return false;
    
    const {
        minLength = 8,
        requireUppercase = true,
        requireLowercase = true,
        requireNumbers = true,
        requireSpecial = true
    } = options;
    
    if (password.length < minLength) return false;
    
    if (requireUppercase && !/[A-Z]/.test(password)) return false;
    if (requireLowercase && !/[a-z]/.test(password)) return false;
    if (requireNumbers && !/[0-9]/.test(password)) return false;
    if (requireSpecial && !/[!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?]/.test(password)) return false;
    
    return true;
}

/**
 * Ellenőrzi, hogy a megadott érték biztonságos fájlnév-e
 * @param {string} filename - A fájlnév
 * @returns {boolean} true, ha biztonságos
 */
function isSafeFilename(filename) {
    if (typeof filename !== 'string') return false;
    
    // Csak alfanumerikus karakterek, pont, aláhúzás, kötőjel
    const safeRegex = /^[a-zA-Z0-9._-]+$/;
    return safeRegex.test(filename) && !filename.startsWith('.') && !filename.includes('..');
}

/**
 * Ellenőrzi, hogy a megadott érték érvényes port szám-e
 * @param {*} port - A port szám
 * @returns {boolean} true, ha érvényes port
 */
function isPort(port) {
    if (typeof port === 'string') port = parseInt(port, 10);
    if (typeof port !== 'number' || isNaN(port)) return false;
    
    return port >= 1 && port <= 65535;
}

/**
 * Ellenőrzi, hogy a megadott érték érvényes RGB szín-e
 * @param {number} r - Red (0-255)
 * @param {number} g - Green (0-255)
 * @param {number} b - Blue (0-255)
 * @returns {boolean} true, ha érvényes
 */
function isRgbColor(r, g, b) {
    return isNumber(r, { min: 0, max: 255, integer: true }) &&
           isNumber(g, { min: 0, max: 255, integer: true }) &&
           isNumber(b, { min: 0, max: 255, integer: true });
}

/**
 * Ellenőrzi, hogy a megadott érték érvényes HSL szín-e
 * @param {number} h - Hue (0-360)
 * @param {number} s - Saturation (0-100)
 * @param {number} l - Lightness (0-100)
 * @returns {boolean} true, ha érvényes
 */
function isHslColor(h, s, l) {
    return isNumber(h, { min: 0, max: 360, integer: true }) &&
           isNumber(s, { min: 0, max: 100, integer: true }) &&
           isNumber(l, { min: 0, max: 100, integer: true });
}

/**
 * Ellenőrzi, hogy a megadott érték érvényes dátum-e
 * @param {*} date - A dátum
 * @returns {boolean} true, ha érvényes dátum
 */
function isValidDate(date) {
    if (date === null || date === undefined) return false;
    
    const d = new Date(date);
    return d instanceof Date && !isNaN(d);
}

/**
 * Ellenőrzi, hogy a megadott érték érvényes időbélyeg-e
 * @param {*} timestamp - Az időbélyeg
 * @returns {boolean} true, ha érvényes
 */
function isValidTimestamp(timestamp) {
    if (typeof timestamp === 'string') timestamp = parseInt(timestamp, 10);
    if (typeof timestamp !== 'number' || isNaN(timestamp)) return false;
    
    const date = new Date(timestamp);
    return date instanceof Date && !isNaN(date) && date.getTime() === timestamp;
}

/**
 * Ellenőrzi, hogy a megadott érték érvényes base64 string-e
 * @param {string} str - A base64 string
 * @returns {boolean} true, ha érvényes
 */
function isBase64(str) {
    if (typeof str !== 'string') return false;
    
    const base64Regex = /^([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{3}=|[A-Za-z0-9+/]{2}==)?$/;
    return base64Regex.test(str);
}

/**
 * Ellenőrzi, hogy a megadott érték érvényes ASCII string-e
 * @param {string} str - A string
 * @returns {boolean} true, ha csak ASCII karaktereket tartalmaz
 */
function isAscii(str) {
    if (typeof str !== 'string') return false;
    return /^[\x00-\x7F]*$/.test(str);
}

/**
 * Ellenőrzi, hogy a megadott érték érvényes UTF-8 string-e
 * @param {string} str - A string
 * @returns {boolean} true, ha érvényes UTF-8
 */
function isUtf8(str) {
    if (typeof str !== 'string') return false;
    
    try {
        encodeURIComponent(str);
        return true;
    } catch {
        return false;
    }
}

// Globális elérhetővé tétel
window.validators = {
    isEmail,
    isPhone,
    notEmpty,
    isUrl,
    isIpAddress,
    isDomain,
    isNumber,
    isUuid,
    isHexColor,
    isJson,
    isStrongPassword,
    isSafeFilename,
    isPort,
    isRgbColor,
    isHslColor,
    isValidDate,
    isValidTimestamp,
    isBase64,
    isAscii,
    isUtf8
};

console.log('✅ Validators betöltve');