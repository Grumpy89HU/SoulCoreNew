// ==============================================
// SOULCORE 3.0 - Teljesítmény metrikák komponens
// ==============================================

window.MetricsPanel = {
    name: 'MetricsPanel',
    
    template: `
        <div class="metrics-panel">
            <!-- Fejléc időtáv választóval -->
            <div class="metrics-header">
                <div class="header-title">
                    <h3>{{ t('metrics.title') }}</h3>
                </div>
                <div class="header-actions">
                    <select v-model="timeRange" class="range-select" @change="loadMetrics">
                        <option value="hour">{{ t('metrics.last_hour') }}</option>
                        <option value="day">{{ t('metrics.last_day') }}</option>
                        <option value="week">{{ t('metrics.last_week') }}</option>
                        <option value="month">{{ t('metrics.last_month') }}</option>
                    </select>
                    <button class="refresh-btn" @click="loadMetrics" :disabled="loading">
                        <span :class="{ 'spin': loading }">🔄</span>
                    </button>
                </div>
            </div>
            
            <!-- Betöltés jelző -->
            <div v-if="loading" class="loading-spinner">
                <div class="spinner"></div>
                <span>{{ t('metrics.loading') }}</span>
            </div>
            
            <div v-else class="metrics-content">
                <!-- Összesítő kártyák -->
                <div class="summary-cards">
                    <div class="summary-card">
                        <div class="card-icon">💬</div>
                        <div class="card-content">
                            <span class="card-value">{{ formatNumber(summary.total_messages) }}</span>
                            <span class="card-label">{{ t('metrics.total_messages') }}</span>
                        </div>
                    </div>
                    <div class="summary-card">
                        <div class="card-icon">🔤</div>
                        <div class="card-content">
                            <span class="card-value">{{ formatNumber(summary.total_tokens) }}</span>
                            <span class="card-label">{{ t('metrics.total_tokens') }}</span>
                        </div>
                    </div>
                    <div class="summary-card">
                        <div class="card-icon">⚡</div>
                        <div class="card-content">
                            <span class="card-value">{{ formatNumber(summary.avg_response_time) }}ms</span>
                            <span class="card-label">{{ t('metrics.avg_response') }}</span>
                        </div>
                    </div>
                    <div class="summary-card">
                        <div class="card-icon">👥</div>
                        <div class="card-content">
                            <span class="card-value">{{ formatNumber(summary.active_users) }}</span>
                            <span class="card-label">{{ t('metrics.active_users') }}</span>
                        </div>
                    </div>
                </div>
                
                <!-- Grafikonok -->
                <div class="charts-grid">
                    <div class="chart-card">
                        <div class="chart-header">
                            <h4>{{ t('metrics.token_usage') }}</h4>
                            <div class="chart-legend">
                                <span class="legend-item">
                                    <span class="legend-color" style="background: #7aa2f7;"></span>
                                    {{ t('metrics.tokens') }}
                                </span>
                            </div>
                        </div>
                        <div class="chart-container">
                            <canvas ref="tokenChart"></canvas>
                        </div>
                    </div>
                    
                    <div class="chart-card">
                        <div class="chart-header">
                            <h4>{{ t('metrics.response_times') }}</h4>
                            <div class="chart-legend">
                                <span class="legend-item">
                                    <span class="legend-color" style="background: #9ece6a;"></span>
                                    {{ t('metrics.avg_time') }}
                                </span>
                            </div>
                        </div>
                        <div class="chart-container">
                            <canvas ref="responseChart"></canvas>
                        </div>
                    </div>
                    
                    <div class="chart-card">
                        <div class="chart-header">
                            <h4>{{ t('metrics.active_conversations') }}</h4>
                        </div>
                        <div class="chart-container">
                            <canvas ref="conversationChart"></canvas>
                        </div>
                    </div>
                    
                    <div class="chart-card" v-if="hasGPU">
                        <div class="chart-header">
                            <h4>{{ t('metrics.gpu_usage') }}</h4>
                            <div class="chart-legend">
                                <span class="legend-item" v-for="(gpu, idx) in gpuCount" :key="idx">
                                    <span class="legend-color" :style="{ background: colors[idx % colors.length] }"></span>
                                    GPU {{ idx }}
                                </span>
                            </div>
                        </div>
                        <div class="chart-container">
                            <canvas ref="gpuChart"></canvas>
                        </div>
                    </div>
                </div>
                
                <!-- Részletes táblázatok -->
                <div class="details-section">
                    <div class="details-card">
                        <h4>{{ t('metrics.top_users') }}</h4>
                        <table class="metrics-table">
                            <thead>
                                <tr>
                                    <th>{{ t('metrics.user') }}</th>
                                    <th>{{ t('metrics.messages') }}</th>
                                    <th>{{ t('metrics.tokens') }}</th>
                                    <th>{{ t('metrics.avg_time') }}</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr v-for="user in topUsers" :key="user.id">
                                    <td>{{ user.name }}</td>
                                    <td>{{ formatNumber(user.messages) }}</td>
                                    <td>{{ formatNumber(user.tokens) }}</td>
                                    <td>{{ user.avg_time }}ms</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                    
                    <div class="details-card">
                        <h4>{{ t('metrics.top_intents') }}</h4>
                        <table class="metrics-table">
                            <thead>
                                <tr>
                                    <th>{{ t('metrics.intent') }}</th>
                                    <th>{{ t('metrics.count') }}</th>
                                    <th>{{ t('metrics.percentage') }}</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr v-for="intent in topIntents" :key="intent.name">
                                    <td>{{ intent.name }}</td>
                                    <td>{{ formatNumber(intent.count) }}</td>
                                    <td>{{ intent.percentage }}%</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                    
                    <div class="details-card">
                        <h4>{{ t('metrics.system_resources') }}</h4>
                        <div class="resource-list">
                            <div class="resource-item">
                                <span class="resource-label">CPU:</span>
                                <div class="resource-bar">
                                    <div class="bar-fill" :style="{ width: resources.cpu + '%' }"></div>
                                </div>
                                <span class="resource-value">{{ resources.cpu }}%</span>
                            </div>
                            <div class="resource-item">
                                <span class="resource-label">RAM:</span>
                                <div class="resource-bar">
                                    <div class="bar-fill" :style="{ width: resources.ram + '%' }"></div>
                                </div>
                                <span class="resource-value">{{ resources.ram }}%</span>
                            </div>
                            <div v-for="(gpu, idx) in resources.gpus" :key="idx" class="resource-item">
                                <span class="resource-label">GPU{{ idx }}:</span>
                                <div class="resource-bar">
                                    <div class="bar-fill" :style="{ width: gpu + '%' }"></div>
                                </div>
                                <span class="resource-value">{{ gpu }}%</span>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Export gombok -->
                <div class="metrics-footer">
                    <button class="btn-secondary" @click="exportMetrics('json')">
                        📥 JSON
                    </button>
                    <button class="btn-secondary" @click="exportMetrics('csv')">
                        📊 CSV
                    </button>
                    <button class="btn-secondary" @click="exportMetrics('png')" v-if="hasCharts">
                        🖼️ PNG
                    </button>
                </div>
            </div>
        </div>
    `,
    
    setup() {
        // ====================================================================
        // REAKTÍV ÁLLAPOTOK
        // ====================================================================
        
        const loading = Vue.ref(false);
        const timeRange = Vue.ref('day');
        const hasGPU = Vue.ref(false);
        const gpuCount = Vue.ref(0);
        const hasCharts = Vue.ref(false);
        const colors = ['#7aa2f7', '#9ece6a', '#f7768e', '#bb9af7', '#e5c890'];
        
        // Összesített adatok
        const summary = Vue.ref({
            total_messages: 0,
            total_tokens: 0,
            avg_response_time: 0,
            active_users: 0
        });
        
        // Idősoros adatok
        const timeSeriesData = Vue.ref({
            timestamps: [],
            tokens: [],
            responses: [],
            conversations: [],
            gpu: []
        });
        
        // Részletes adatok
        const topUsers = Vue.ref([]);
        const topIntents = Vue.ref([]);
        const resources = Vue.ref({
            cpu: 0,
            ram: 0,
            gpus: []
        });
        
        // Chart referenciák
        const tokenChart = Vue.ref(null);
        const responseChart = Vue.ref(null);
        const conversationChart = Vue.ref(null);
        const gpuChart = Vue.ref(null);
        
        let charts = {};
        
        // ====================================================================
        // SEGÉDFÜGGVÉNYEK
        // ====================================================================
        
        const t = (key, params = {}) => window.gettext(key, params);
        const formatNumber = (num) => window.formatNumber(num);
        
        const chartOptions = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: '#1a1e24',
                    titleColor: '#e0e0e0',
                    bodyColor: '#e0e0e0'
                }
            },
            scales: {
                x: { grid: { color: '#2a2f38' }, ticks: { color: '#888' } },
                y: { grid: { color: '#2a2f38' }, ticks: { color: '#888' } }
            }
        };
        
        const initCharts = () => {
            if (typeof Chart === 'undefined') return;
            
            const labels = timeSeriesData.value.timestamps.map(ts => formatTime(ts));
            
            if (tokenChart.value) {
                charts.token = new Chart(tokenChart.value, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: t('metrics.tokens'),
                            data: timeSeriesData.value.tokens,
                            borderColor: '#7aa2f7',
                            backgroundColor: 'rgba(122, 162, 247, 0.1)',
                            tension: 0.4,
                            fill: true
                        }]
                    },
                    options: chartOptions
                });
            }
            
            if (responseChart.value) {
                charts.response = new Chart(responseChart.value, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: t('metrics.avg_time'),
                            data: timeSeriesData.value.responses,
                            borderColor: '#9ece6a',
                            backgroundColor: 'rgba(158, 206, 106, 0.1)',
                            tension: 0.4,
                            fill: true
                        }]
                    },
                    options: chartOptions
                });
            }
            
            if (conversationChart.value) {
                charts.conversation = new Chart(conversationChart.value, {
                    type: 'bar',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: t('metrics.conversations'),
                            data: timeSeriesData.value.conversations,
                            backgroundColor: '#e5c890',
                            borderRadius: 4
                        }]
                    },
                    options: {
                        ...chartOptions,
                        scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } }
                    }
                });
            }
            
            if (gpuChart.value && hasGPU.value && timeSeriesData.value.gpu.length) {
                const datasets = [];
                for (let i = 0; i < gpuCount.value; i++) {
                    datasets.push({
                        label: `GPU ${i}`,
                        data: timeSeriesData.value.gpu.map(d => d[i] || 0),
                        borderColor: colors[i % colors.length],
                        backgroundColor: 'transparent',
                        tension: 0.4
                    });
                }
                charts.gpu = new Chart(gpuChart.value, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: datasets
                    },
                    options: {
                        ...chartOptions,
                        scales: { y: { beginAtZero: true, max: 100, ticks: { callback: v => v + '%' } } }
                    }
                });
            }
            
            hasCharts.value = true;
        };
        
        const updateCharts = () => {
            if (!hasCharts.value || typeof Chart === 'undefined') return;
            
            const labels = timeSeriesData.value.timestamps.map(ts => formatTime(ts));
            
            if (charts.token) {
                charts.token.data.labels = labels;
                charts.token.data.datasets[0].data = timeSeriesData.value.tokens;
                charts.token.update();
            }
            if (charts.response) {
                charts.response.data.labels = labels;
                charts.response.data.datasets[0].data = timeSeriesData.value.responses;
                charts.response.update();
            }
            if (charts.conversation) {
                charts.conversation.data.labels = labels;
                charts.conversation.data.datasets[0].data = timeSeriesData.value.conversations;
                charts.conversation.update();
            }
            if (charts.gpu && hasGPU.value) {
                charts.gpu.data.labels = labels;
                for (let i = 0; i < gpuCount.value; i++) {
                    if (charts.gpu.data.datasets[i]) {
                        charts.gpu.data.datasets[i].data = timeSeriesData.value.gpu.map(d => d[i] || 0);
                    }
                }
                charts.gpu.update();
            }
        };
        
        const formatTime = (ts) => {
            if (timeRange.value === 'hour') return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            return new Date(ts).toLocaleDateString([], { month: 'short', day: 'numeric' });
        };
        
        const loadMetrics = async () => {
            loading.value = true;
            try {
                const data = await window.api.getMetrics(timeRange.value);
                processMetricsData(data);
                await loadGPUInfo();
                await loadResources();
                
                Vue.nextTick(() => {
                    if (!hasCharts.value && typeof Chart !== 'undefined') initCharts();
                    else updateCharts();
                });
            } catch (error) {
                console.error('Error loading metrics:', error);
                generateDemoData();
                window.store.addNotification('error', t('metrics.load_error'));
            } finally {
                loading.value = false;
            }
        };
        
        const loadGPUInfo = async () => {
            const gpus = window.store.gpuStatus;
            hasGPU.value = gpus.length > 0;
            gpuCount.value = gpus.length;
        };
        
        const loadResources = async () => {
            resources.value = {
                cpu: Math.floor(Math.random() * 60) + 20,
                ram: Math.floor(Math.random() * 50) + 30,
                gpus: Array(gpuCount.value).fill().map(() => Math.floor(Math.random() * 70) + 10)
            };
        };
        
        const processMetricsData = (data) => {
            if (!data) { generateDemoData(); return; }
            
            summary.value = {
                total_messages: data.total_messages || 0,
                total_tokens: data.total_tokens || 0,
                avg_response_time: data.avg_response_time || 0,
                active_users: data.active_users || 0
            };
            
            timeSeriesData.value = {
                timestamps: data.timestamps || generateTimestamps(24),
                tokens: data.tokens || generateRandomData(24, 100, 1000),
                responses: data.responses || generateRandomData(24, 50, 500),
                conversations: data.conversations || generateRandomData(24, 1, 10, true),
                gpu: data.gpu || generateGPUData(24, gpuCount.value)
            };
            
            topUsers.value = data.top_users || generateTopUsers(5);
            topIntents.value = data.top_intents || generateTopIntents(5);
        };
        
        const generateTimestamps = (count) => {
            const now = Date.now();
            const interval = timeRange.value === 'hour' ? 60000 : 3600000;
            return Array.from({ length: count + 1 }, (_, i) => now - i * interval).reverse();
        };
        
        const generateRandomData = (count, min, max, integer = false) => {
            return Array.from({ length: count + 1 }, () => {
                let val = Math.random() * (max - min) + min;
                return integer ? Math.floor(val) : val;
            });
        };
        
        const generateGPUData = (count, gpuCount) => {
            return Array.from({ length: count + 1 }, () => 
                Array.from({ length: gpuCount }, () => Math.floor(Math.random() * 70) + 10)
            );
        };
        
        const generateTopUsers = (count) => {
            const names = ['Alice', 'Bob', 'Charlie', 'Diana', 'Eve'];
            return Array.from({ length: count }, (_, i) => ({
                id: i + 1,
                name: names[i] || `User${i + 1}`,
                messages: Math.floor(Math.random() * 500) + 100,
                tokens: Math.floor(Math.random() * 10000) + 1000,
                avg_time: Math.floor(Math.random() * 2000) + 500
            }));
        };
        
        const generateTopIntents = (count) => {
            const names = ['greeting', 'question', 'command', 'farewell', 'knowledge'];
            const total = Math.floor(Math.random() * 1000) + 500;
            return Array.from({ length: count }, (_, i) => {
                const cnt = Math.floor(Math.random() * 300) + 50;
                return {
                    name: names[i] || `intent_${i + 1}`,
                    count: cnt,
                    percentage: Math.round((cnt / total) * 100)
                };
            });
        };
        
        const generateDemoData = () => {
            const points = timeRange.value === 'hour' ? 60 : 24;
            timeSeriesData.value = {
                timestamps: generateTimestamps(points),
                tokens: generateRandomData(points, 500, 2000),
                responses: generateRandomData(points, 100, 800),
                conversations: generateRandomData(points, 5, 20, true),
                gpu: generateGPUData(points, gpuCount.value)
            };
            summary.value = {
                total_messages: timeSeriesData.value.tokens.reduce((a, b) => a + b, 0) / 10,
                total_tokens: timeSeriesData.value.tokens.reduce((a, b) => a + b, 0),
                avg_response_time: timeSeriesData.value.responses.reduce((a, b) => a + b, 0) / points,
                active_users: 3
            };
            topUsers.value = generateTopUsers(5);
            topIntents.value = generateTopIntents(5);
        };
        
        const exportMetrics = (format) => {
            const data = {
                exported: new Date().toISOString(),
                timeRange: timeRange.value,
                summary: summary.value,
                timeSeries: timeSeriesData.value,
                topUsers: topUsers.value,
                topIntents: topIntents.value,
                resources: resources.value
            };
            
            if (format === 'json') {
                const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `metrics_${timeRange.value}_${new Date().toISOString().slice(0, 10)}.json`;
                a.click();
                URL.revokeObjectURL(url);
            } else if (format === 'csv') {
                let csv = 'Timestamp,Tokens,ResponseTime,Conversations\n';
                timeSeriesData.value.timestamps.forEach((ts, i) => {
                    csv += `${new Date(ts).toISOString()},${timeSeriesData.value.tokens[i] || 0},${timeSeriesData.value.responses[i] || 0},${timeSeriesData.value.conversations[i] || 0}\n`;
                });
                const blob = new Blob([csv], { type: 'text/csv' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `metrics_${timeRange.value}_${new Date().toISOString().slice(0, 10)}.csv`;
                a.click();
                URL.revokeObjectURL(url);
            } else if (format === 'png') {
                alert(t('metrics.png_export_not_implemented'));
            }
        };
        
        Vue.onMounted(() => {
            loadMetrics();
            if (window.store) {
                Vue.watch(() => window.store.gpuStatus, (newGpus) => {
                    hasGPU.value = newGpus.length > 0;
                    gpuCount.value = newGpus.length;
                });
            }
        });
        
        Vue.onUnmounted(() => {
            Object.values(charts).forEach(chart => chart?.destroy());
        });
        
        return {
            loading, timeRange, hasGPU, gpuCount, hasCharts, colors,
            summary, timeSeriesData, topUsers, topIntents, resources,
            tokenChart, responseChart, conversationChart, gpuChart,
            t, formatNumber, loadMetrics, exportMetrics
        };
    }
};

console.log('✅ MetricsPanel komponens betöltve');