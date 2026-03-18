// Formázó függvények

/**
 * Időtartam formázása másodpercek alapján
 * @param {number} seconds - Másodpercek száma
 * @param {boolean} compact - Rövid formátum (pl. "2h 30m" vs "2 óra 30 perc")
 * @returns {string} Formázott időtartam
 */
function formatUptime(seconds, compact = true) {
    if (!seconds && seconds !== 0) return compact ? '0s' : '0 másodperc';
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (compact) {
        const parts = [];
        if (hours > 0) parts.push(`${hours}h`);
        if (minutes > 0) parts.push(`${minutes}m`);
        if (secs > 0 || parts.length === 0) parts.push(`${secs}s`);
        return parts.join(' ');
    } else {
        const parts = [];
        if (hours > 0) parts.push(`${hours} óra`);
        if (minutes > 0) parts.push(`${minutes} perc`);
        if (secs > 0 || parts.length === 0) parts.push(`${secs} másodperc`);
        return parts.join(' ');
    }
}

/**
 * Relatív idő formázása (pl. "5 perce", "2 órája")
 * @param {string|number} timestamp - Időbélyeg vagy dátum string
 * @param {string} language - Nyelv ('en' vagy 'hu')
 * @returns {string} Relatív idő
 */
function formatRelativeTime(timestamp, language = 'en') {
    if (!timestamp) return '';
    
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now - date;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);
    const diffWeek = Math.floor(diffDay / 7);
    const diffMonth = Math.floor(diffDay / 30);
    const diffYear = Math.floor(diffDay / 365);
    
    if (language === 'hu') {
        if (diffSec < 10) return 'most';
        if (diffSec < 60) return `${diffSec} másodperce`;
        if (diffMin < 60) return `${diffMin} perce`;
        if (diffHour < 24) return `${diffHour} órája`;
        if (diffDay < 7) return `${diffDay} napja`;
        if (diffWeek < 5) return `${diffWeek} hete`;
        if (diffMonth < 12) return `${diffMonth} hónapja`;
        return `${diffYear} éve`;
    } else {
        if (diffSec < 10) return 'just now';
        if (diffSec < 60) return `${diffSec} seconds ago`;
        if (diffMin < 60) return `${diffMin} minutes ago`;
        if (diffHour < 24) return `${diffHour} hours ago`;
        if (diffDay < 7) return `${diffDay} days ago`;
        if (diffWeek < 5) return `${diffWeek} weeks ago`;
        if (diffMonth < 12) return `${diffMonth} months ago`;
        return `${diffYear} years ago`;
    }
}

/**
 * Dátum formázása
 * @param {string|number} dateStr - Dátum string vagy timestamp
 * @param {string} format - Formátum ('short', 'long', 'iso', 'relative')
 * @param {string} language - Nyelv ('en' vagy 'hu')
 * @returns {string} Formázott dátum
 */
function formatDate(dateStr, format = 'short', language = 'en') {
    if (!dateStr) return '';
    
    const date = new Date(dateStr);
    
    if (format === 'relative') {
        return formatRelativeTime(dateStr, language);
    }
    
    if (format === 'iso') {
        return date.toISOString().split('T')[0];
    }
    
    if (format === 'long') {
        return date.toLocaleDateString(language, {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            weekday: 'long'
        });
    }
    
    // short alapértelmezett
    return date.toLocaleDateString(language, {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

/**
 * Idő formázása
 * @param {string|number} timestamp - Időbélyeg vagy dátum string
 * @param {string} format - Formátum ('short', 'long', 'full')
 * @param {string} language - Nyelv ('en' vagy 'hu')
 * @returns {string} Formázott idő
 */
function formatTime(timestamp, format = 'short', language = 'en') {
    if (!timestamp) return '';
    
    const date = new Date(timestamp);
    
    if (format === 'full') {
        return date.toLocaleString(language, {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    }
    
    if (format === 'long') {
        return date.toLocaleTimeString(language, {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    }
    
    // short alapértelmezett
    return date.toLocaleTimeString(language, {
        hour: '2-digit',
        minute: '2-digit'
    });
}

/**
 * Dátum és idő együttes formázása
 * @param {string|number} timestamp - Időbélyeg vagy dátum string
 * @param {string} language - Nyelv ('en' vagy 'hu')
 * @returns {string} Formázott dátum és idő
 */
function formatDateTime(timestamp, language = 'en') {
    if (!timestamp) return '';
    
    const date = new Date(timestamp);
    return date.toLocaleString(language, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

/**
 * Bájtok formázása emberi olvasható formátumba
 * @param {number} bytes - Bájtok száma
 * @param {boolean} si - SI egységek használata (true: KB/MB/GB, false: KiB/MiB/GiB)
 * @returns {string} Formázott méret
 */
function formatBytes(bytes, si = true) {
    if (bytes === 0 || bytes === undefined || bytes === null) return '0 B';
    
    const k = si ? 1000 : 1024;
    const units = si 
        ? ['B', 'KB', 'MB', 'GB', 'TB', 'PB'] 
        : ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB'];
    
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + units[i];
}

/**
 * Százalék formázása
 * @param {number} value - Érték (0-100 vagy 0-1)
 * @param {number} decimals - Tizedesjegyek száma
 * @returns {string} Formázott százalék
 */
function formatPercent(value, decimals = 1) {
    if (value === undefined || value === null) return '0%';
    
    // Ha 0-1 közötti érték, átváltjuk százalékra
    let percent = value;
    if (value >= 0 && value <= 1) {
        percent = value * 100;
    }
    
    return percent.toFixed(decimals) + '%';
}

/**
 * Szám formázása ezres elválasztókkal
 * @param {number} num - A formázandó szám
 * @param {number} decimals - Tizedesjegyek száma
 * @returns {string} Formázott szám
 */
function formatNumber(num, decimals = 0) {
    if (num === undefined || num === null) return '0';
    
    if (typeof num === 'string') {
        num = parseFloat(num);
    }
    
    return num.toLocaleString(undefined, {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    });
}

/**
 * Pénzösszeg formázása
 * @param {number} amount - Összeg
 * @param {string} currency - Pénznem (HUF, USD, EUR)
 * @param {string} language - Nyelv
 * @returns {string} Formázott pénzösszeg
 */
function formatCurrency(amount, currency = 'HUF', language = 'hu') {
    if (amount === undefined || amount === null) return '0 ' + currency;
    
    return amount.toLocaleString(language, {
        style: 'currency',
        currency: currency,
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    });
}

/**
 * JSON objektum formázása emberi olvashatóvá
 * @param {Object} obj - A formázandó objektum
 * @param {number} maxLength - Maximum hossz
 * @returns {string} Formázott JSON string
 */
function formatJSON(obj, maxLength = 200) {
    if (!obj) return '';
    
    try {
        let str;
        if (typeof obj === 'string') {
            str = obj;
        } else {
            str = JSON.stringify(obj, null, 2);
        }
        
        if (str.length > maxLength) {
            return str.substring(0, maxLength) + '…';
        }
        return str;
    } catch (e) {
        return String(obj);
    }
}

/**
 * Szöveg rövidítése
 * @param {string} text - A szöveg
 * @param {number} length - Maximum hossz
 * @param {string} suffix - Utótag (alapértelmezett: '...')
 * @returns {string} Rövidített szöveg
 */
function truncate(text, length = 100, suffix = '…') {
    if (!text) return '';
    if (text.length <= length) return text;
    return text.substring(0, length) + suffix;
}

/**
 * Lista formázása olvashatóvá
 * @param {Array} items - Lista elemek
 * @param {string} language - Nyelv
 * @returns {string} Formázott lista
 */
function formatList(items, language = 'en') {
    if (!items || items.length === 0) return '';
    if (items.length === 1) return items[0];
    if (items.length === 2) return items.join(language === 'hu' ? ' és ' : ' and ');
    
    const last = items.pop();
    const list = items.join(', ');
    return language === 'hu' 
        ? `${list} és ${last}`
        : `${list} and ${last}`;
}

/**
 * Telefonszám formázása
 * @param {string} phone - Telefonszám
 * @returns {string} Formázott telefonszám
 */
function formatPhone(phone) {
    if (!phone) return '';
    
    // Csak számok megtartása
    const cleaned = phone.replace(/\D/g, '');
    
    // Magyar telefonszám formátum
    if (cleaned.startsWith('36') && cleaned.length === 11) {
        return `+36 ${cleaned.slice(2, 4)} ${cleaned.slice(4, 7)} ${cleaned.slice(7)}`;
    }
    
    return phone;
}

/**
 * JSON pretty print
 * @param {Object} obj - Az objektum
 * @returns {string} Szépen formázott JSON
 */
function prettyJSON(obj) {
    try {
        return JSON.stringify(obj, null, 2);
    } catch (e) {
        return String(obj);
    }
}

// Globális elérhetővé tétel
window.formatters = {
    formatUptime,
    formatRelativeTime,
    formatDate,
    formatTime,
    formatDateTime,
    formatBytes,
    formatPercent,
    formatNumber,
    formatCurrency,
    formatJSON,
    truncate,
    formatList,
    formatPhone,
    prettyJSON
};

console.log('✅ Formatters betöltve');