// ==============================================
// SOULCORE 3.0 - Formázó függvények
// ==============================================

window.formatters = {
    /**
     * Idő formázása (pl. 3661 -> 1h 1m)
     */
    formatUptime(seconds) {
        if (!seconds) return '0s';
        
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        
        const parts = [];
        if (hours > 0) parts.push(`${hours}h`);
        if (minutes > 0) parts.push(`${minutes}m`);
        if (secs > 0 || parts.length === 0) parts.push(`${secs}s`);
        
        return parts.join(' ');
    },
    
    /**
     * Dátum formázása
     */
    formatDate(timestamp) {
        if (!timestamp) return '';
        const date = new Date(timestamp);
        return date.toLocaleDateString(window.i18n?.language || 'hu-HU');
    },
    
    /**
     * Időpont formázása
     */
    formatTime(timestamp) {
        if (!timestamp) return '';
        const date = new Date(timestamp);
        return date.toLocaleTimeString(window.i18n?.language || 'hu-HU', {
            hour: '2-digit',
            minute: '2-digit'
        });
    },
    
    /**
     * Dátum és idő formázása
     */
    formatDateTime(timestamp) {
        if (!timestamp) return '';
        const date = new Date(timestamp);
        return date.toLocaleString(window.i18n?.language || 'hu-HU');
    },
    
    /**
     * Relatív idő formázása (pl. "5 perce")
     */
    formatRelativeTime(timestamp) {
        if (!timestamp) return '';
        
        const now = Date.now();
        const diff = now - (typeof timestamp === 'string' ? new Date(timestamp).getTime() : timestamp);
        
        const seconds = Math.floor(diff / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);
        
        if (days > 7) return this.formatDate(timestamp);
        if (days > 0) return `${days} napja`;
        if (hours > 0) return `${hours} órája`;
        if (minutes > 0) return `${minutes} perce`;
        if (seconds > 30) return `${seconds} másodperce`;
        return 'most';
    },
    
    /**
     * Bájtok formázása (pl. 1024 -> 1 KB)
     */
    formatBytes(bytes, decimals = 1) {
        if (bytes === 0 || bytes === undefined || bytes === null) return '0 B';
        
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(decimals)) + ' ' + sizes[i];
    },
    
    /**
     * Szám formázása ezres elválasztókkal
     */
    formatNumber(num) {
        if (num === undefined || num === null) return '0';
        return num.toLocaleString(window.i18n?.language || 'hu-HU');
    },
    
    /**
     * Százalék formázása
     */
    formatPercent(num, decimals = 1) {
        if (num === undefined || num === null) return '0%';
        return num.toFixed(decimals) + '%';
    },
    
    /**
     * Szöveg rövidítése
     */
    truncate(text, length = 100, suffix = '...') {
        if (!text) return '';
        if (text.length <= length) return text;
        return text.substring(0, length) + suffix;
    },
    
    /**
     * Első betű nagybetűsítése
     */
    capitalize(text) {
        if (!text) return '';
        return text.charAt(0).toUpperCase() + text.slice(1);
    },
    
    /**
     * Státusz szövegének formázása
     */
    formatStatus(status) {
        const translations = {
            'running': 'Fut',
            'ready': 'Kész',
            'processing': 'Feldolgozás',
            'idle': 'Tétlen',
            'error': 'Hiba',
            'stopped': 'Leállítva',
            'watching': 'Figyel'
        };
        return translations[status] || status;
    }
};

// Globális alias-ok a gyakran használt függvényekhez
window.formatUptime = window.formatters.formatUptime;
window.formatDate = window.formatters.formatDate;
window.formatTime = window.formatters.formatTime;
window.formatDateTime = window.formatters.formatDateTime;
window.formatBytes = window.formatters.formatBytes;
window.formatNumber = window.formatters.formatNumber;
window.truncate = window.formatters.truncate;

console.log('✅ Formatters modul betöltve');