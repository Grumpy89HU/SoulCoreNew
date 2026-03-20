// ==============================================
// SOULCORE 3.0 - Trace panel komponens
// ==============================================

window.TracePanel = {
    name: 'TracePanel',
    
    template: `
        <div class="trace-panel">
            <!-- Fejléc -->
            <div class="trace-header">
                <div class="header-title">
                    <h3>{{ t('traces.title') }}</h3>
                    <span class="trace-count" v-if="traces.length">({{ traces.length }})</span>
                </div>
                <div class="header-actions">
                    <input 
                        type="text" 
                        v-model="searchQuery" 
                        :placeholder="t('traces.search')"
                        class="search-input"
                    >
                    <select v-model="filterLevel" class="filter-select">
                        <option value="all">{{ t('traces.all_levels') }}</option>
                        <option value="error">{{ t('traces.error') }}</option>
                        <option value="warning">{{ t('traces.warning') }}</option>
                        <option value="info">{{ t('traces.info') }}</option>
                        <option value="debug">{{ t('traces.debug') }}</option>
                    </select>
                    <select v-model="filterModule" class="filter-select">
                        <option value="all">{{ t('traces.all_modules') }}</option>
                        <option v-for="mod in modules" :key="mod" :value="mod">{{ formatModuleName(mod) }}</option>
                    </select>
                    <button class="refresh-btn" @click="refreshTraces" :disabled="refreshing">
                        <span :class="{ 'spin': refreshing }">🔄</span>
                    </button>
                </div>
            </div>
            
            <!-- Trace lista -->
            <div class="trace-list">
                <div v-if="loading" class="loading-spinner">
                    <div class="spinner-small"></div>
                </div>
                <div v-else-if="filteredTraces.length === 0" class="empty-list">
                    <div class="empty-icon">🔍</div>
                    <div class="empty-text">{{ t('traces.no_traces') }}</div>
                </div>
                <div v-else>
                    <div v-for="trace in filteredTraces" :key="trace.id" 
                         class="trace-item" 
                         :class="'trace-' + trace.level"
                         @click="showTraceDetails(trace)">
                        <div class="trace-header-row">
                            <span class="trace-time">{{ formatDateTime(trace.timestamp) }}</span>
                            <span class="trace-id" :title="trace.trace_id">{{ trace.trace_id?.slice(0, 8) }}...</span>
                            <span class="trace-level" :class="trace.level">{{ trace.level?.toUpperCase() }}</span>
                            <span class="trace-module">{{ formatModuleName(trace.module) }}</span>
                        </div>
                        <div class="trace-message">{{ truncate(trace.message, 100) }}</div>
                        <div class="trace-meta" v-if="trace.duration">
                            <span>⏱️ {{ trace.duration }}ms</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Trace részletek modal -->
            <div class="modal" v-if="showDetailsModal" @click.self="showDetailsModal = false">
                <div class="modal-content large">
                    <div class="modal-header">
                        <h3>{{ t('traces.details') }} - {{ selectedTrace?.trace_id?.slice(0, 8) }}...</h3>
                        <button class="close-btn" @click="showDetailsModal = false">✕</button>
                    </div>
                    <div class="modal-body">
                        <div class="trace-detail-grid">
                            <div class="detail-row">
                                <span class="detail-label">{{ t('traces.trace_id') }}:</span>
                                <span class="detail-value"><code>{{ selectedTrace?.trace_id }}</code></span>
                            </div>
                            <div class="detail-row">
                                <span class="detail-label">{{ t('traces.time') }}:</span>
                                <span class="detail-value">{{ formatDateTime(selectedTrace?.timestamp) }}</span>
                            </div>
                            <div class="detail-row">
                                <span class="detail-label">{{ t('traces.module') }}:</span>
                                <span class="detail-value">{{ formatModuleName(selectedTrace?.module) }}</span>
                            </div>
                            <div class="detail-row">
                                <span class="detail-label">{{ t('traces.level') }}:</span>
                                <span class="detail-value" :class="selectedTrace?.level">{{ selectedTrace?.level?.toUpperCase() }}</span>
                            </div>
                            <div class="detail-row">
                                <span class="detail-label">{{ t('traces.message') }}:</span>
                                <span class="detail-value">{{ selectedTrace?.message }}</span>
                            </div>
                            <div class="detail-row" v-if="selectedTrace?.duration">
                                <span class="detail-label">{{ t('traces.duration') }}:</span>
                                <span class="detail-value">{{ selectedTrace?.duration }}ms</span>
                            </div>
                            <div class="detail-row" v-if="selectedTrace?.context">
                                <span class="detail-label">{{ t('traces.context') }}:</span>
                                <pre class="detail-pre">{{ formatContext(selectedTrace?.context) }}</pre>
                            </div>
                            <div class="detail-row" v-if="selectedTrace?.stack">
                                <span class="detail-label">{{ t('traces.stack') }}:</span>
                                <pre class="detail-pre">{{ selectedTrace?.stack }}</pre>
                            </div>
                        </div>
                        
                        <div class="trace-actions" v-if="selectedTrace?.trace_id">
                            <button class="btn-secondary" @click="replayTrace(selectedTrace.trace_id)">
                                ▶️ {{ t('traces.replay') }}
                            </button>
                            <button class="btn-secondary" @click="exportTrace(selectedTrace)">
                                📥 {{ t('traces.export') }}
                            </button>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn-primary" @click="showDetailsModal = false">
                            {{ t('ui.close') }}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `,
    
    setup() {
        // ====================================================================
        // REAKTÍV ÁLLAPOTOK
        // ====================================================================
        
        const traces = Vue.ref([]);
        const loading = Vue.ref(false);
        const refreshing = Vue.ref(false);
        
        // Szűrők
        const searchQuery = Vue.ref('');
        const filterLevel = Vue.ref('all');
        const filterModule = Vue.ref('all');
        
        // Modal
        const showDetailsModal = Vue.ref(false);
        const selectedTrace = Vue.ref(null);
        
        // ====================================================================
        // COMPUTED PROPERTIES
        // ====================================================================
        
        const modules = Vue.computed(() => {
            const modSet = new Set();
            traces.value.forEach(trace => {
                if (trace.module) modSet.add(trace.module);
            });
            return Array.from(modSet).sort();
        });
        
        const filteredTraces = Vue.computed(() => {
            let filtered = [...traces.value];
            
            if (searchQuery.value) {
                const query = searchQuery.value.toLowerCase();
                filtered = filtered.filter(t => 
                    t.message?.toLowerCase().includes(query) ||
                    t.trace_id?.toLowerCase().includes(query) ||
                    t.module?.toLowerCase().includes(query)
                );
            }
            
            if (filterLevel.value !== 'all') {
                filtered = filtered.filter(t => t.level === filterLevel.value);
            }
            
            if (filterModule.value !== 'all') {
                filtered = filtered.filter(t => t.module === filterModule.value);
            }
            
            return filtered;
        });
        
        // ====================================================================
        // SEGÉDFÜGGVÉNYEK
        // ====================================================================
        
        const t = (key, params = {}) => window.gettext(key, params);
        const formatDateTime = (ts) => window.formatDateTime(ts);
        const truncate = (text, len) => window.truncate(text, len);
        const formatModuleName = (name) => window.formatModuleName(name);
        
        const formatContext = (context) => {
            if (!context) return '—';
            if (typeof context === 'object') {
                return JSON.stringify(context, null, 2);
            }
            return context;
        };
        
        const loadTraces = async () => {
            loading.value = true;
            try {
                const data = await window.api.searchBlackbox('', 500);
                traces.value = data.results || generateDemoTraces();
            } catch (error) {
                console.error('Error loading traces:', error);
                traces.value = generateDemoTraces();
            } finally {
                loading.value = false;
            }
        };
        
        const refreshTraces = async () => {
            refreshing.value = true;
            await loadTraces();
            refreshing.value = false;
        };
        
        const showTraceDetails = (trace) => {
            selectedTrace.value = trace;
            showDetailsModal.value = true;
        };
        
        const replayTrace = async (traceId) => {
            try {
                const trace = await window.api.getBlackboxTrace(traceId);
                window.store.addNotification('info', t('traces.replay_started'));
                // Itt lehetne a visszajátszás logikája
            } catch (error) {
                console.error('Error replaying trace:', error);
                window.store.addNotification('error', t('traces.replay_error'));
            }
        };
        
        const exportTrace = (trace) => {
            const data = {
                exported: new Date().toISOString(),
                trace: trace
            };
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `trace_${trace.trace_id}_${new Date().toISOString().slice(0, 19)}.json`;
            a.click();
            URL.revokeObjectURL(url);
            window.store.addNotification('success', t('traces.exported'));
        };
        
        const generateDemoTraces = () => {
            const levels = ['info', 'debug', 'warning', 'error'];
            const modules = ['orchestrator', 'king', 'queen', 'scribe', 'valet', 'jester', 'sentinel'];
            const messages = [
                'Processing request',
                'Model loaded successfully',
                'Memory allocation: 256MB',
                'Cache hit rate: 85%',
                'Warning: High latency detected',
                'Error: Timeout while waiting for response',
                'Debug: KVK packet parsed',
                'Info: Conversation saved to database'
            ];
            
            return Array.from({ length: 100 }, (_, i) => ({
                id: i,
                trace_id: `trace_${Math.random().toString(36).substr(2, 16)}`,
                timestamp: Date.now() - i * 60000,
                module: modules[Math.floor(Math.random() * modules.length)],
                level: levels[Math.floor(Math.random() * levels.length)],
                message: messages[Math.floor(Math.random() * messages.length)],
                duration: Math.floor(Math.random() * 500),
                context: { request_id: i, user: 'admin' }
            }));
        };
        
        Vue.onMounted(() => {
            loadTraces();
        });
        
        return {
            traces,
            loading,
            refreshing,
            searchQuery,
            filterLevel,
            filterModule,
            showDetailsModal,
            selectedTrace,
            modules,
            filteredTraces,
            t,
            formatDateTime,
            truncate,
            formatModuleName,
            formatContext,
            refreshTraces,
            showTraceDetails,
            replayTrace,
            exportTrace
        };
    }
};

console.log('✅ TracePanel komponens betöltve');