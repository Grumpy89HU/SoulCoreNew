// ==============================================
// SOULCORE 3.0 - Audit log komponens
// ==============================================

window.AuditLog = {
    name: 'AuditLog',
    
    template: `
        <div class="audit-log">
            <!-- Fejléc szűrőkkel -->
            <div class="audit-header">
                <div class="header-title">
                    <h3>{{ t('audit.title') }}</h3>
                    <span class="log-count" v-if="logs.length">({{ logs.length }})</span>
                </div>
                <div class="header-actions">
                    <button class="refresh-btn" @click="refreshLogs" :disabled="refreshing">
                        <span :class="{ 'spin': refreshing }">🔄</span>
                    </button>
                    <button class="btn-secondary" @click="exportLogs">
                        📥 {{ t('audit.export') }}
                    </button>
                </div>
            </div>
            
            <!-- Szűrők -->
            <div class="filter-bar">
                <input 
                    type="text" 
                    v-model="searchQuery" 
                    :placeholder="t('audit.search')"
                    class="search-input"
                >
                <select v-model="filterUser" class="filter-select">
                    <option value="all">{{ t('audit.all_users') }}</option>
                    <option v-for="user in users" :key="user" :value="user">{{ user }}</option>
                </select>
                <select v-model="filterAction" class="filter-select">
                    <option value="all">{{ t('audit.all_actions') }}</option>
                    <option v-for="action in actions" :key="action" :value="action">{{ action }}</option>
                </select>
                <div class="date-range">
                    <input type="date" v-model="dateFrom" :placeholder="t('audit.from')">
                    <input type="date" v-model="dateTo" :placeholder="t('audit.to')">
                </div>
                <button class="clear-filters-btn" @click="clearFilters" v-if="hasFilters">
                    ✕ {{ t('audit.clear_filters') }}
                </button>
            </div>
            
            <!-- Nézet választó -->
            <div class="view-toggle">
                <button class="toggle-btn" :class="{ active: viewMode === 'table' }" @click="viewMode = 'table'">
                    📋 {{ t('audit.table_view') }}
                </button>
                <button class="toggle-btn" :class="{ active: viewMode === 'timeline' }" @click="viewMode = 'timeline'">
                    ⏱️ {{ t('audit.timeline_view') }}
                </button>
            </div>
            
            <!-- Táblázatos nézet -->
            <div v-show="viewMode === 'table'" class="table-view">
                <div v-if="loading" class="loading-spinner">
                    <div class="spinner-small"></div>
                </div>
                <div v-else-if="filteredLogs.length === 0" class="empty-list">
                    <div class="empty-icon">📋</div>
                    <div class="empty-text">{{ t('audit.no_logs') }}</div>
                </div>
                <div v-else class="table-container">
                    <table class="audit-table">
                        <thead>
                            <tr>
                                <th @click="sortBy('timestamp')">
                                    {{ t('audit.time') }}
                                    <span v-if="sortField === 'timestamp'">{{ sortOrder === 'asc' ? '↑' : '↓' }}</span>
                                </th>
                                <th @click="sortBy('user')">
                                    {{ t('audit.user') }}
                                    <span v-if="sortField === 'user'">{{ sortOrder === 'asc' ? '↑' : '↓' }}</span>
                                </th>
                                <th @click="sortBy('action')">
                                    {{ t('audit.action') }}
                                    <span v-if="sortField === 'action'">{{ sortOrder === 'asc' ? '↑' : '↓' }}</span>
                                </th>
                                <th>{{ t('audit.resource') }}</th>
                                <th>{{ t('audit.details') }}</th>
                                <th>{{ t('audit.ip') }}</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="log in paginatedLogs" :key="log.id" 
                                class="log-row" 
                                :class="'log-' + log.level"
                                @click="showDetails(log)">
                                <td class="log-time">{{ formatDateTime(log.timestamp) }}</td>
                                <td class="log-user">{{ log.user || t('audit.system') }}</td>
                                <td><span class="action-badge" :class="'action-' + log.action">{{ log.action }}</span></td>
                                <td class="log-resource">{{ log.resource || '—' }}</td>
                                <td class="log-details">{{ truncate(log.details || '—', 50) }}</td>
                                <td class="log-ip">{{ log.ip || '—' }}</td>
                            </tr>
                        </tbody>
                    </table>
                    
                    <!-- Lapozás -->
                    <div class="pagination" v-if="filteredLogs.length > pageSize">
                        <button class="page-btn" @click="currentPage--" :disabled="currentPage === 1">◀</button>
                        <span class="page-info">{{ currentPage }} / {{ totalPages }}</span>
                        <button class="page-btn" @click="currentPage++" :disabled="currentPage === totalPages">▶</button>
                    </div>
                </div>
            </div>
            
            <!-- Idővonal nézet -->
            <div v-show="viewMode === 'timeline'" class="timeline-view">
                <div v-if="loading" class="loading-spinner">
                    <div class="spinner-small"></div>
                </div>
                <div v-else-if="filteredLogs.length === 0" class="empty-list">
                    <div class="empty-icon">⏱️</div>
                    <div class="empty-text">{{ t('audit.no_logs') }}</div>
                </div>
                <div v-else>
                    <div v-for="group in groupedLogs" :key="group.date" class="timeline-group">
                        <div class="timeline-date">{{ group.date }}</div>
                        <div v-for="log in group.logs" :key="log.id" 
                             class="timeline-item" 
                             @click="showDetails(log)">
                            <span class="timeline-time">{{ formatTime(log.timestamp) }}</span>
                            <div class="timeline-content">
                                <span class="timeline-badge" :class="'badge-' + (log.level || 'info')"></span>
                                <span class="timeline-user">{{ log.user || t('audit.system') }}</span>
                                <span class="timeline-action">{{ log.action }}</span>
                                <span class="timeline-resource" v-if="log.resource">{{ log.resource }}</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Részletek modal -->
            <div class="modal" v-if="showDetailsModal" @click.self="showDetailsModal = false">
                <div class="modal-content">
                    <div class="modal-header">
                        <h3>{{ t('audit.details') }}</h3>
                        <button class="close-btn" @click="showDetailsModal = false">✕</button>
                    </div>
                    <div class="modal-body">
                        <div class="detail-grid">
                            <div class="detail-row">
                                <span class="detail-label">{{ t('audit.time') }}:</span>
                                <span class="detail-value">{{ formatDateTime(selectedLog?.timestamp) }}</span>
                            </div>
                            <div class="detail-row">
                                <span class="detail-label">{{ t('audit.user') }}:</span>
                                <span class="detail-value">{{ selectedLog?.user || t('audit.system') }}</span>
                            </div>
                            <div class="detail-row">
                                <span class="detail-label">{{ t('audit.action') }}:</span>
                                <span class="detail-value">{{ selectedLog?.action }}</span>
                            </div>
                            <div class="detail-row">
                                <span class="detail-label">{{ t('audit.resource') }}:</span>
                                <span class="detail-value">{{ selectedLog?.resource || '—' }}</span>
                            </div>
                            <div class="detail-row">
                                <span class="detail-label">{{ t('audit.ip') }}:</span>
                                <span class="detail-value">{{ selectedLog?.ip || '—' }}</span>
                            </div>
                            <div class="detail-row">
                                <span class="detail-label">{{ t('audit.details') }}:</span>
                                <pre class="detail-pre">{{ formatDetails(selectedLog?.details) }}</pre>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn-primary" @click="showDetailsModal = false">
                            {{ t('ui.close') }}
                        </button>
                    </div>
                </div>
            </div>
            
            <!-- Statisztikák -->
            <div class="audit-stats" v-if="filteredLogs.length">
                <div class="stat-card">
                    <span class="stat-value">{{ filteredLogs.length }}</span>
                    <span class="stat-label">{{ t('audit.total_events') }}</span>
                </div>
                <div class="stat-card">
                    <span class="stat-value">{{ uniqueUsers }}</span>
                    <span class="stat-label">{{ t('audit.unique_users') }}</span>
                </div>
                <div class="stat-card">
                    <span class="stat-value">{{ mostCommonAction }}</span>
                    <span class="stat-label">{{ t('audit.most_common_action') }}</span>
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
        const refreshing = Vue.ref(false);
        
        // Szűrők
        const searchQuery = Vue.ref('');
        const filterUser = Vue.ref('all');
        const filterAction = Vue.ref('all');
        const dateFrom = Vue.ref('');
        const dateTo = Vue.ref('');
        
        // Nézet
        const viewMode = Vue.ref('table');
        
        // Rendezés
        const sortField = Vue.ref('timestamp');
        const sortOrder = Vue.ref('desc');
        
        // Lapozás
        const currentPage = Vue.ref(1);
        const pageSize = Vue.ref(50);
        
        // Modal
        const showDetailsModal = Vue.ref(false);
        const selectedLog = Vue.ref(null);
        
        // ====================================================================
        // COMPUTED PROPERTIES
        // ====================================================================
        
        const users = Vue.computed(() => {
            const userSet = new Set();
            logs.value.forEach(log => {
                if (log.user) userSet.add(log.user);
            });
            return Array.from(userSet).sort();
        });
        
        const actions = Vue.computed(() => {
            const actionSet = new Set();
            logs.value.forEach(log => {
                if (log.action) actionSet.add(log.action);
            });
            return Array.from(actionSet).sort();
        });
        
        const hasFilters = Vue.computed(() => {
            return searchQuery.value || filterUser.value !== 'all' || 
                   filterAction.value !== 'all' || dateFrom.value || dateTo.value;
        });
        
        const filteredLogs = Vue.computed(() => {
            let filtered = [...logs.value];
            
            // Keresés
            if (searchQuery.value) {
                const query = searchQuery.value.toLowerCase();
                filtered = filtered.filter(log => 
                    log.user?.toLowerCase().includes(query) ||
                    log.action?.toLowerCase().includes(query) ||
                    log.resource?.toLowerCase().includes(query) ||
                    log.details?.toLowerCase().includes(query)
                );
            }
            
            // Felhasználó szűrés
            if (filterUser.value !== 'all') {
                filtered = filtered.filter(log => log.user === filterUser.value);
            }
            
            // Művelet szűrés
            if (filterAction.value !== 'all') {
                filtered = filtered.filter(log => log.action === filterAction.value);
            }
            
            // Dátum szűrés
            if (dateFrom.value) {
                const from = new Date(dateFrom.value).setHours(0, 0, 0, 0);
                filtered = filtered.filter(log => log.timestamp >= from);
            }
            if (dateTo.value) {
                const to = new Date(dateTo.value).setHours(23, 59, 59, 999);
                filtered = filtered.filter(log => log.timestamp <= to);
            }
            
            // Rendezés
            filtered.sort((a, b) => {
                let aVal = a[sortField.value];
                let bVal = b[sortField.value];
                
                if (sortField.value === 'timestamp') {
                    aVal = aVal || 0;
                    bVal = bVal || 0;
                } else {
                    aVal = String(aVal || '').toLowerCase();
                    bVal = String(bVal || '').toLowerCase();
                }
                
                if (aVal < bVal) return sortOrder.value === 'asc' ? -1 : 1;
                if (aVal > bVal) return sortOrder.value === 'asc' ? 1 : -1;
                return 0;
            });
            
            return filtered;
        });
        
        const totalPages = Vue.computed(() => {
            return Math.ceil(filteredLogs.value.length / pageSize.value);
        });
        
        const paginatedLogs = Vue.computed(() => {
            const start = (currentPage.value - 1) * pageSize.value;
            const end = start + pageSize.value;
            return filteredLogs.value.slice(start, end);
        });
        
        const groupedLogs = Vue.computed(() => {
            const groups = {};
            
            filteredLogs.value.forEach(log => {
                const date = formatDate(log.timestamp);
                if (!groups[date]) {
                    groups[date] = { date, logs: [] };
                }
                groups[date].logs.push(log);
            });
            
            return Object.values(groups).sort((a, b) => b.date.localeCompare(a.date));
        });
        
        const uniqueUsers = Vue.computed(() => {
            const userSet = new Set();
            filteredLogs.value.forEach(log => {
                if (log.user) userSet.add(log.user);
            });
            return userSet.size;
        });
        
        const mostCommonAction = Vue.computed(() => {
            const counts = {};
            filteredLogs.value.forEach(log => {
                if (log.action) {
                    counts[log.action] = (counts[log.action] || 0) + 1;
                }
            });
            
            let maxAction = '';
            let maxCount = 0;
            for (const [action, count] of Object.entries(counts)) {
                if (count > maxCount) {
                    maxCount = count;
                    maxAction = action;
                }
            }
            return maxAction;
        });
        
        // ====================================================================
        // SEGÉDFÜGGVÉNYEK
        // ====================================================================
        
        const t = (key, params = {}) => window.gettext(key, params);
        const formatDateTime = (ts) => window.formatDateTime(ts);
        const formatTime = (ts) => window.formatTime(ts);
        const formatDate = (ts) => window.formatDate(ts);
        const truncate = (text, len) => window.truncate(text, len);
        
        const formatDetails = (details) => {
            if (!details) return '—';
            if (typeof details === 'object') {
                return JSON.stringify(details, null, 2);
            }
            return details;
        };
        
        const sortBy = (field) => {
            if (sortField.value === field) {
                sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc';
            } else {
                sortField.value = field;
                sortOrder.value = 'desc';
            }
        };
        
        const clearFilters = () => {
            searchQuery.value = '';
            filterUser.value = 'all';
            filterAction.value = 'all';
            dateFrom.value = '';
            dateTo.value = '';
            currentPage.value = 1;
        };
        
        const showDetails = (log) => {
            selectedLog.value = log;
            showDetailsModal.value = true;
        };
        
        /**
         * Naplók betöltése
         */
        const loadLogs = async () => {
            loading.value = true;
            try {
                const data = await window.api.getAuditLog(1000);
                logs.value = data.audit_log || [];
            } catch (error) {
                console.error('Error loading audit logs:', error);
                window.store.addNotification('error', t('audit.load_error'));
                logs.value = generateDemoLogs();
            } finally {
                loading.value = false;
            }
        };
        
        /**
         * Naplók frissítése
         */
        const refreshLogs = async () => {
            refreshing.value = true;
            await loadLogs();
            refreshing.value = false;
        };
        
        /**
         * Naplók exportálása
         */
        const exportLogs = () => {
            const data = {
                exported: new Date().toISOString(),
                filters: {
                    search: searchQuery.value,
                    user: filterUser.value,
                    action: filterAction.value,
                    date_from: dateFrom.value,
                    date_to: dateTo.value
                },
                logs: filteredLogs.value
            };
            
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `audit_log_${new Date().toISOString().slice(0, 19)}.json`;
            a.click();
            URL.revokeObjectURL(url);
            
            window.store.addNotification('success', t('audit.exported'));
        };
        
        /**
         * Demo naplók generálása
         */
        const generateDemoLogs = () => {
            const actions = ['login', 'logout', 'create_conversation', 'delete_conversation', 
                           'update_settings', 'activate_model', 'control_module', 'save_prompt'];
            const users = ['admin', 'user1', 'user2', 'system'];
            
            return Array.from({ length: 100 }, (_, i) => ({
                id: i,
                timestamp: Date.now() - i * 3600000,
                user: users[Math.floor(Math.random() * users.length)],
                action: actions[Math.floor(Math.random() * actions.length)],
                resource: `resource_${Math.floor(Math.random() * 10)}`,
                details: { key: 'value', id: i },
                ip: `192.168.1.${Math.floor(Math.random() * 255)}`,
                level: ['info', 'warning', 'error'][Math.floor(Math.random() * 3)]
            }));
        };
        
        // ====================================================================
        // ÉLETCIKLUS
        // ====================================================================
        
        Vue.onMounted(() => {
            loadLogs();
        });
        
        // ====================================================================
        // RETURN
        // ====================================================================
        
        return {
            // Állapotok
            logs,
            loading,
            refreshing,
            searchQuery,
            filterUser,
            filterAction,
            dateFrom,
            dateTo,
            viewMode,
            sortField,
            sortOrder,
            currentPage,
            pageSize,
            showDetailsModal,
            selectedLog,
            
            // Computed
            users,
            actions,
            hasFilters,
            filteredLogs,
            totalPages,
            paginatedLogs,
            groupedLogs,
            uniqueUsers,
            mostCommonAction,
            
            // Segédfüggvények
            t,
            formatDateTime,
            formatTime,
            formatDate,
            truncate,
            formatDetails,
            sortBy,
            clearFilters,
            showDetails,
            refreshLogs,
            exportLogs
        };
    }
};

console.log('✅ AuditLog komponens betöltve');