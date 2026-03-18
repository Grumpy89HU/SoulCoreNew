// Audit log megjelenítő komponens
window.AuditLog = {
    template: `
        <div class="audit-log">
            <!-- Fejléc szűrőkkel -->
            <div class="audit-header">
                <div class="header-title">
                    <h3>{{ gettext('audit.title') }}</h3>
                    <span class="log-count" v-if="filteredLogs.length">({{ filteredLogs.length }})</span>
                </div>
                
                <div class="header-actions">
                    <button class="refresh-btn" @click="refreshLogs" :disabled="loading">
                        <span :class="{ 'spin': loading }">🔄</span>
                    </button>
                    <button class="export-btn" @click="exportLogs" :disabled="!filteredLogs.length">
                        📥 {{ gettext('audit.export') }}
                    </button>
                </div>
            </div>
            
            <!-- Szűrők -->
            <div class="filter-bar">
                <div class="filter-group">
                    <label>{{ gettext('audit.user') }}:</label>
                    <input 
                        type="text" 
                        v-model="filters.user" 
                        :placeholder="gettext('audit.user_placeholder')"
                        class="filter-input"
                    >
                </div>
                
                <div class="filter-group">
                    <label>{{ gettext('audit.action') }}:</label>
                    <select v-model="filters.action" class="filter-select">
                        <option value="">{{ gettext('audit.all_actions') }}</option>
                        <option v-for="action in availableActions" :key="action" :value="action">
                            {{ formatAction(action) }}
                        </option>
                    </select>
                </div>
                
                <div class="filter-group">
                    <label>{{ gettext('audit.resource') }}:</label>
                    <input 
                        type="text" 
                        v-model="filters.resource" 
                        :placeholder="gettext('audit.resource_placeholder')"
                        class="filter-input"
                    >
                </div>
                
                <div class="filter-group">
                    <label>{{ gettext('audit.date_from') }}:</label>
                    <input 
                        type="date" 
                        v-model="filters.dateFrom" 
                        class="filter-input"
                    >
                </div>
                
                <div class="filter-group">
                    <label>{{ gettext('audit.date_to') }}:</label>
                    <input 
                        type="date" 
                        v-model="filters.dateTo" 
                        class="filter-input"
                    >
                </div>
                
                <button class="clear-filters-btn" @click="clearFilters" v-if="hasFilters">
                    🧹 {{ gettext('audit.clear_filters') }}
                </button>
            </div>
            
            <!-- Idővonal nézet / Tábla nézet váltó -->
            <div class="view-toggle">
                <button class="toggle-btn" :class="{ active: viewMode == 'table' }" @click="viewMode = 'table'">
                    📊 {{ gettext('audit.table_view') }}
                </button>
                <button class="toggle-btn" :class="{ active: viewMode == 'timeline' }" @click="viewMode = 'timeline'">
                    📅 {{ gettext('audit.timeline_view') }}
                </button>
            </div>
            
            <!-- Betöltés jelző -->
            <div v-if="loading" class="loading-spinner">
                <div class="spinner"></div>
                <span>{{ gettext('audit.loading') }}</span>
            </div>
            
            <!-- Tábla nézet -->
            <div v-else-if="viewMode == 'table'" class="table-view">
                <table class="audit-table">
                    <thead>
                        <tr>
                            <th @click="sortBy('timestamp')">
                                🕒 {{ gettext('audit.time') }}
                                <span v-if="sortColumn == 'timestamp'">{{ sortDirection == 'asc' ? '↑' : '↓' }}</span>
                            </th>
                            <th @click="sortBy('user')">
                                👤 {{ gettext('audit.user') }}
                                <span v-if="sortColumn == 'user'">{{ sortDirection == 'asc' ? '↑' : '↓' }}</span>
                            </th>
                            <th @click="sortBy('action')">
                                ⚡ {{ gettext('audit.action') }}
                                <span v-if="sortColumn == 'action'">{{ sortDirection == 'asc' ? '↑' : '↓' }}</span>
                            </th>
                            <th @click="sortBy('resource')">
                                📁 {{ gettext('audit.resource') }}
                                <span v-if="sortColumn == 'resource'">{{ sortDirection == 'asc' ? '↑' : '↓' }}</span>
                            </th>
                            <th>{{ gettext('audit.details') }}</th>
                            <th @click="sortBy('ip')">
                                🌐 IP
                                <span v-if="sortColumn == 'ip'">{{ sortDirection == 'asc' ? '↑' : '↓' }}</span>
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="log in sortedAndFilteredLogs" :key="log.id" 
                            class="log-row" 
                            :class="'log-' + log.action_type"
                            @click="showDetails(log)">
                            <td class="log-time">{{ formatTime(log.timestamp) }}</td>
                            <td class="log-user">{{ log.username || log.user_id || 'system' }}</td>
                            <td class="log-action">
                                <span class="action-badge" :class="'action-' + log.action">
                                    {{ formatAction(log.action) }}
                                </span>
                            </td>
                            <td class="log-resource">{{ log.resource || '-' }}</td>
                            <td class="log-details">{{ truncate(log.details, 50) }}</td>
                            <td class="log-ip">{{ log.ip_address || '-' }}</td>
                        </tr>
                        
                        <tr v-if="sortedAndFilteredLogs.length === 0">
                            <td colspan="6" class="empty-table">
                                {{ gettext('audit.no_logs') }}
                            </td>
                        </tr>
                    </tbody>
                </table>
                
                <!-- Lapozás -->
                <div class="pagination" v-if="totalPages > 1">
                    <button class="page-btn" @click="prevPage" :disabled="currentPage == 1">
                        ←
                    </button>
                    <span class="page-info">{{ currentPage }} / {{ totalPages }}</span>
                    <button class="page-btn" @click="nextPage" :disabled="currentPage == totalPages">
                        →
                    </button>
                </div>
            </div>
            
            <!-- Idővonal nézet -->
            <div v-else-if="viewMode == 'timeline'" class="timeline-view">
                <div v-for="(group, date) in groupedByDate" :key="date" class="timeline-group">
                    <div class="timeline-date">{{ formatDate(date) }}</div>
                    
                    <div v-for="log in group" :key="log.id" class="timeline-item">
                        <div class="timeline-time">{{ formatTime(log.timestamp, 'HH:MM') }}</div>
                        <div class="timeline-content" @click="showDetails(log)">
                            <span class="timeline-badge" :class="'badge-' + log.action_type"></span>
                            <span class="timeline-user">{{ log.username || log.user_id || 'system' }}</span>
                            <span class="timeline-action">{{ formatAction(log.action) }}</span>
                            <span class="timeline-resource" v-if="log.resource">→ {{ log.resource }}</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Részletek modal -->
            <div class="modal" v-if="showDetailsModal">
                <div class="modal-content">
                    <div class="modal-header">
                        <h3>{{ gettext('audit.details') }}</h3>
                        <button class="close-btn" @click="showDetailsModal = false">✕</button>
                    </div>
                    
                    <div class="modal-body">
                        <div class="detail-grid">
                            <div class="detail-row">
                                <span class="detail-label">{{ gettext('audit.time') }}:</span>
                                <span class="detail-value">{{ formatTime(selectedLog.timestamp, 'full') }}</span>
                            </div>
                            
                            <div class="detail-row">
                                <span class="detail-label">{{ gettext('audit.user') }}:</span>
                                <span class="detail-value">{{ selectedLog.username || selectedLog.user_id || 'system' }}</span>
                            </div>
                            
                            <div class="detail-row">
                                <span class="detail-label">{{ gettext('audit.action') }}:</span>
                                <span class="detail-value">
                                    <span class="action-badge" :class="'action-' + selectedLog.action">
                                        {{ formatAction(selectedLog.action) }}
                                    </span>
                                </span>
                            </div>
                            
                            <div class="detail-row">
                                <span class="detail-label">{{ gettext('audit.resource') }}:</span>
                                <span class="detail-value">{{ selectedLog.resource || '-' }}</span>
                            </div>
                            
                            <div class="detail-row">
                                <span class="detail-label">IP {{ gettext('audit.address') }}:</span>
                                <span class="detail-value">{{ selectedLog.ip_address || '-' }}</span>
                            </div>
                            
                            <div class="detail-row" v-if="selectedLog.details">
                                <span class="detail-label">{{ gettext('audit.details') }}:</span>
                                <pre class="detail-pre">{{ formatDetails(selectedLog.details) }}</pre>
                            </div>
                            
                            <div class="detail-row" v-if="selectedLog.metadata">
                                <span class="detail-label">{{ gettext('audit.metadata') }}:</span>
                                <pre class="detail-pre">{{ formatMetadata(selectedLog.metadata) }}</pre>
                            </div>
                        </div>
                    </div>
                    
                    <div class="modal-footer">
                        <button class="btn-secondary" @click="showDetailsModal = false">
                            {{ gettext('ui.close') }}
                        </button>
                    </div>
                </div>
            </div>
            
            <!-- Statisztikák -->
            <div class="audit-stats" v-if="stats">
                <div class="stat-card">
                    <span class="stat-value">{{ stats.total_events }}</span>
                    <span class="stat-label">{{ gettext('audit.total_events') }}</span>
                </div>
                <div class="stat-card">
                    <span class="stat-value">{{ stats.unique_users }}</span>
                    <span class="stat-label">{{ gettext('audit.unique_users') }}</span>
                </div>
                <div class="stat-card">
                    <span class="stat-value">{{ stats.most_active_user }}</span>
                    <span class="stat-label">{{ gettext('audit.most_active') }}</span>
                </div>
            </div>
        </div>
    `,
    
    setup() {
        // ====================================================================
        // REAKTÍV ÁLLAPOTOK
        // ====================================================================
        
        const logs = Vue.ref([]);
        const loading = Vue.ref(false);
        const viewMode = Vue.ref('table');
        const showDetailsModal = Vue.ref(false);
        const selectedLog = Vue.ref(null);
        
        // Szűrők
        const filters = Vue.ref({
            user: '',
            action: '',
            resource: '',
            dateFrom: '',
            dateTo: ''
        });
        
        // Rendezés
        const sortColumn = Vue.ref('timestamp');
        const sortDirection = Vue.ref('desc');
        
        // Lapozás
        const currentPage = Vue.ref(1);
        const pageSize = Vue.ref(50);
        const totalPages = Vue.ref(1);
        
        // Statisztikák
        const stats = Vue.ref(null);
        
        // ====================================================================
        // COMPUTED PROPERTIES
        // ====================================================================
        
        // Elérhető akciók (szűréshez)
        const availableActions = Vue.computed(() => {
            const actions = new Set();
            logs.value.forEach(log => {
                if (log.action) actions.add(log.action);
            });
            return Array.from(actions).sort();
        });
        
        // Szűrt naplók
        const filteredLogs = Vue.computed(() => {
            return logs.value.filter(log => {
                // Felhasználó szűrés
                if (filters.value.user) {
                    const userMatch = (log.username || log.user_id || '').toLowerCase()
                        .includes(filters.value.user.toLowerCase());
                    if (!userMatch) return false;
                }
                
                // Akció szűrés
                if (filters.value.action && log.action !== filters.value.action) {
                    return false;
                }
                
                // Erőforrás szűrés
                if (filters.value.resource) {
                    const resourceMatch = (log.resource || '').toLowerCase()
                        .includes(filters.value.resource.toLowerCase());
                    if (!resourceMatch) return false;
                }
                
                // Dátum szűrés
                if (filters.value.dateFrom) {
                    const logDate = new Date(log.timestamp).toISOString().split('T')[0];
                    if (logDate < filters.value.dateFrom) return false;
                }
                
                if (filters.value.dateTo) {
                    const logDate = new Date(log.timestamp).toISOString().split('T')[0];
                    if (logDate > filters.value.dateTo) return false;
                }
                
                return true;
            });
        });
        
        // Rendezett és szűrt naplók
        const sortedAndFilteredLogs = Vue.computed(() => {
            const sorted = [...filteredLogs.value];
            
            sorted.sort((a, b) => {
                let aVal = a[sortColumn.value];
                let bVal = b[sortColumn.value];
                
                if (sortColumn.value === 'timestamp') {
                    aVal = new Date(aVal).getTime();
                    bVal = new Date(bVal).getTime();
                }
                
                if (sortDirection.value === 'asc') {
                    return aVal > bVal ? 1 : -1;
                } else {
                    return aVal < bVal ? 1 : -1;
                }
            });
            
            // Lapozás
            const start = (currentPage.value - 1) * pageSize.value;
            const end = start + pageSize.value;
            totalPages.value = Math.ceil(sorted.length / pageSize.value);
            
            return sorted.slice(start, end);
        });
        
        // Dátum szerint csoportosított naplók (idővonal nézethez)
        const groupedByDate = Vue.computed(() => {
            const groups = {};
            
            filteredLogs.value.forEach(log => {
                const date = new Date(log.timestamp).toISOString().split('T')[0];
                if (!groups[date]) groups[date] = [];
                groups[date].push(log);
            });
            
            // Dátum szerint rendezés (újabb előre)
            return Object.keys(groups)
                .sort((a, b) => b.localeCompare(a))
                .reduce((acc, date) => {
                    acc[date] = groups[date];
                    return acc;
                }, {});
        });
        
        // Vannak aktív szűrők?
        const hasFilters = Vue.computed(() => {
            return Object.values(filters.value).some(v => v);
        });
        
        // ====================================================================
        // SEGÉDFÜGGVÉNYEK
        // ====================================================================
        
        const gettext = (key, params = {}) => {
            return window.gettext ? window.gettext(key, params) : key;
        };
        
        const formatTime = (timestamp, format = 'full') => {
            if (!timestamp) return '';
            
            const date = new Date(timestamp);
            
            if (format === 'HH:MM') {
                return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            }
            
            return date.toLocaleString();
        };
        
        const formatDate = (dateStr) => {
            if (!dateStr) return '';
            const date = new Date(dateStr);
            return date.toLocaleDateString(undefined, { 
                weekday: 'long', 
                year: 'numeric', 
                month: 'long', 
                day: 'numeric' 
            });
        };
        
        const formatAction = (action) => {
            if (!action) return '-';
            
            const actionMap = {
                'login': '🔐 ' + gettext('audit.action_login'),
                'logout': '🚪 ' + gettext('audit.action_logout'),
                'create': '➕ ' + gettext('audit.action_create'),
                'update': '✏️ ' + gettext('audit.action_update'),
                'delete': '🗑️ ' + gettext('audit.action_delete'),
                'start': '▶️ ' + gettext('audit.action_start'),
                'stop': '⏹️ ' + gettext('audit.action_stop'),
                'restart': '🔄 ' + gettext('audit.action_restart'),
                'activate': '⚡ ' + gettext('audit.action_activate'),
                'deactivate': '💤 ' + gettext('audit.action_deactivate'),
                'export': '📤 ' + gettext('audit.action_export'),
                'import': '📥 ' + gettext('audit.action_import'),
                'error': '❌ ' + gettext('audit.action_error')
            };
            
            return actionMap[action] || action;
        };
        
        const truncate = (text, length) => {
            if (!text) return '';
            if (typeof text === 'object') text = JSON.stringify(text);
            return text.length > length ? text.substring(0, length) + '…' : text;
        };
        
        const formatDetails = (details) => {
            if (!details) return '-';
            
            try {
                if (typeof details === 'string') {
                    const parsed = JSON.parse(details);
                    return JSON.stringify(parsed, null, 2);
                }
                return JSON.stringify(details, null, 2);
            } catch {
                return String(details);
            }
        };
        
        const formatMetadata = (metadata) => {
            return formatDetails(metadata);
        };
        
        // ====================================================================
        // METÓDUSOK
        // ====================================================================
        
        const loadLogs = async () => {
            loading.value = true;
            
            try {
                if (window.api) {
                    const data = await window.api.getAuditLog(1000);
                    logs.value = data.audit_log || [];
                    
                    // Statisztikák számolása
                    calculateStats();
                } else {
                    // Demo adatok
                    logs.value = generateDemoLogs();
                }
            } catch (error) {
                console.error('Error loading audit logs:', error);
            } finally {
                loading.value = false;
            }
        };
        
        const refreshLogs = () => {
            currentPage.value = 1;
            loadLogs();
        };
        
        const calculateStats = () => {
            const users = new Set();
            const actionCounts = {};
            
            logs.value.forEach(log => {
                const user = log.username || log.user_id || 'system';
                users.add(user);
                
                actionCounts[log.action] = (actionCounts[log.action] || 0) + 1;
            });
            
            // Legaktívabb felhasználó
            let mostActive = '';
            let maxCount = 0;
            
            const userCounts = {};
            logs.value.forEach(log => {
                const user = log.username || log.user_id || 'system';
                userCounts[user] = (userCounts[user] || 0) + 1;
                
                if (userCounts[user] > maxCount) {
                    maxCount = userCounts[user];
                    mostActive = user;
                }
            });
            
            stats.value = {
                total_events: logs.value.length,
                unique_users: users.size,
                most_active_user: mostActive
            };
        };
        
        const sortBy = (column) => {
            if (sortColumn.value === column) {
                sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc';
            } else {
                sortColumn.value = column;
                sortDirection.value = 'desc';
            }
        };
        
        const clearFilters = () => {
            filters.value = {
                user: '',
                action: '',
                resource: '',
                dateFrom: '',
                dateTo: ''
            };
        };
        
        const prevPage = () => {
            if (currentPage.value > 1) currentPage.value--;
        };
        
        const nextPage = () => {
            if (currentPage.value < totalPages.value) currentPage.value++;
        };
        
        const showDetails = (log) => {
            selectedLog.value = log;
            showDetailsModal.value = true;
        };
        
        const exportLogs = () => {
            const data = {
                exported: new Date().toISOString(),
                filters: filters.value,
                logs: filteredLogs.value
            };
            
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `audit_log_${new Date().toISOString().slice(0,10)}.json`;
            a.click();
        };
        
        // Demo naplók generálása
        const generateDemoLogs = () => {
            const actions = ['login', 'logout', 'create', 'update', 'delete', 'start', 'stop', 'error'];
            const users = ['admin', 'user1', 'system'];
            const resources = ['conversation', 'model', 'prompt', 'setting', 'module'];
            
            const logs = [];
            const now = Date.now();
            
            for (let i = 0; i < 200; i++) {
                const action = actions[Math.floor(Math.random() * actions.length)];
                const user = users[Math.floor(Math.random() * users.length)];
                const resource = resources[Math.floor(Math.random() * resources.length)];
                
                logs.push({
                    id: i + 1,
                    timestamp: now - i * 3600000,
                    user_id: user === 'system' ? null : (user === 'admin' ? 1 : 2),
                    username: user,
                    action: action,
                    resource: resource,
                    details: { id: Math.floor(Math.random() * 1000) },
                    ip_address: `192.168.1.${Math.floor(Math.random() * 255)}`,
                    action_type: action === 'error' ? 'error' : 'info'
                });
            }
            
            return logs;
        };
        
        // ====================================================================
        // ÉLETCIKLUS
        // ====================================================================
        
        Vue.onMounted(loadLogs);
        
        return {
            // Állapotok
            logs,
            loading,
            viewMode,
            showDetailsModal,
            selectedLog,
            filters,
            sortColumn,
            sortDirection,
            currentPage,
            pageSize,
            totalPages,
            stats,
            
            // Computed
            availableActions,
            filteredLogs,
            sortedAndFilteredLogs,
            groupedByDate,
            hasFilters,
            
            // Metódusok
            gettext,
            formatTime,
            formatDate,
            formatAction,
            truncate,
            formatDetails,
            formatMetadata,
            loadLogs,
            refreshLogs,
            sortBy,
            clearFilters,
            prevPage,
            nextPage,
            showDetails,
            exportLogs
        };
    }
};

window.AuditLog = AuditLog;
console.log('✅ AuditLog betöltve globálisan');