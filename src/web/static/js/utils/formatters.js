// ==============================================
// SOULCORE 3.0 - Formázó függvények
// ==============================================

window.formatters = {
    /**
     * Üzemidő formázása (pl. 3661 -> 1h 1m)
     */
    formatUptime(seconds) {
        if (!seconds && seconds !== 0) return '0s';
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
    formatDate(timestamp, locale = null) {
        if (!timestamp) return '';
        try {
            const date = new Date(timestamp);
            return date.toLocaleDateString(locale || window.i18n?.language || 'hu-HU');
        } catch (e) {
            return timestamp;
        }
    },
    
    /**
     * Időpont formázása
     */
    formatTime(timestamp, locale = null) {
        if (!timestamp) return '';
        try {
            const date = new Date(timestamp);
            return date.toLocaleTimeString(locale || window.i18n?.language || 'hu-HU', {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
        } catch (e) {
            return timestamp;
        }
    },
    
    /**
     * Dátum és idő formázása
     */
    formatDateTime(timestamp, locale = null) {
        if (!timestamp) return '';
        try {
            const date = new Date(timestamp);
            return date.toLocaleString(locale || window.i18n?.language || 'hu-HU');
        } catch (e) {
            return timestamp;
        }
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
        if (bytes === undefined || bytes === null) return '0 B';
        if (bytes === 0) return '0 B';
        
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(decimals)) + ' ' + sizes[i];
    },
    
    /**
     * Százalék formázása
     */
    formatPercent(value, decimals = 1) {
        if (value === undefined || value === null) return '0%';
        return value.toFixed(decimals) + '%';
    },
    
    /**
     * Szám formázása ezres elválasztókkal
     */
    formatNumber(num, decimals = 0) {
        if (num === undefined || num === null) return '0';
        return num.toLocaleString(window.i18n?.language || 'hu-HU', {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals
        });
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
     * Modul név formázása (pl. "orchestrator" -> "Orchestrator")
     * BIZTONSÁGOS VERZIÓ!
     */
    formatModuleName(name) {
        if (!name) return '';
        // Ha nem string, próbáljuk stringgé alakítani
        if (typeof name !== 'string') {
            name = String(name);
        }
        return name.split('_').map(word => 
            word.charAt(0).toUpperCase() + word.slice(1)
        ).join(' ');
    },
    
    /**
     * Státusz szöveg formázása
     */
    formatStatus(status) {
        const translations = {
            'running': 'Fut',
            'ready': 'Kész',
            'processing': 'Feldolgozás',
            'idle': 'Tétlen',
            'error': 'Hiba',
            'stopped': 'Leállítva',
            'watching': 'Figyel',
            'active': 'Aktív',
            'inactive': 'Inaktív'
        };
        return translations[status] || status;
    },
    
    /**
     * Hangulat formázása
     */
    formatMood(mood) {
        const translations = {
            'lively': 'Élénk',
            'calm': 'Nyugodt',
            'thoughtful': 'Gondolkodó',
            'tired': 'Fáradt',
            'neutral': 'Semleges',
            'happy': 'Boldog',
            'sad': 'Szomorú',
            'angry': 'Mérges'
        };
        return translations[mood] || mood;
    },
    
    /**
     * Hőmérséklet osztály meghatározása
     */
    getTempClass(temp) {
        if (temp < 60) return 'temp-normal';
        if (temp < 80) return 'temp-warm';
        return 'temp-hot';
    },
    
    /**
     * VRAM osztály meghatározása
     */
    getVramClass(percent) {
        if (percent < 70) return '';
        if (percent < 85) return 'warning';
        return 'critical';
    },
    
    /**
     * Markdown formázás (egyszerűsített)
     */
    formatMarkdown(text) {
        if (!text) return '';
        
        let html = text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
        
        // Linkek
        html = html.replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>');
        
        // Kód blokkok
        html = html.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
        
        // Inline kód
        html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
        
        // Félkövér
        html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
        
        // Dőlt
        html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
        
        // Idézetek
        html = html.replace(/^&gt; (.*)$/gm, '<blockquote>$1</blockquote>');
        
        // Sortörések
        html = html.replace(/\n/g, '<br>');
        
        return html;
    }
};

// Globális alias-ok
window.formatUptime = window.formatters.formatUptime;
window.formatDate = window.formatters.formatDate;
window.formatTime = window.formatters.formatTime;
window.formatDateTime = window.formatters.formatDateTime;
window.formatRelativeTime = window.formatters.formatRelativeTime;
window.formatBytes = window.formatters.formatBytes;
window.formatNumber = window.formatters.formatNumber;
window.truncate = window.formatters.truncate;
window.capitalize = window.formatters.capitalize;
window.formatModuleName = window.formatters.formatModuleName;
window.formatStatus = window.formatters.formatStatus;
window.formatMood = window.formatters.formatMood;
window.getTempClass = window.formatters.getTempClass;
window.getVramClass = window.formatters.getVramClass;
window.formatMarkdown = window.formatters.formatMarkdown;

console.log('✅ Formatters modul betöltve');