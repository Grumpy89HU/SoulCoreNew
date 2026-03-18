// Rendszer metrikák megjelenítő komponens
window.SystemMetrics = {
    template: `
        <div class="system-metrics">
            <!-- Fejléc időtáv választóval -->
            <div class="metrics-header">
                <div class="header-title">
                    <h3>{{ gettext('metrics.title') }}</h3>
                </div>
                
                <div class="header-actions">
                    <select v-model="timeRange" class="range-select" @change="loadMetrics">
                        <option value="hour">{{ gettext('metrics.last_hour') }}</option>
                        <option value="day">{{ gettext('metrics.last_day') }}</option>
                        <option value="week">{{ gettext('metrics.last_week') }}</option>
                        <option value="month">{{ gettext('metrics.last_month') }}</option>
                    </select>
                    
                    <button class="refresh-btn" @click="loadMetrics" :disabled="loading">
                        <span :class="{ 'spin': loading }">🔄</span>
                    </button>
                </div>
            </div>
            
            <!-- Betöltés jelző -->
            <div v-if="loading" class="loading-spinner">
                <div class="spinner"></div>
                <span>{{ gettext('metrics.loading') }}</span>
            </div>
            
            <div v-else class="metrics-content">
                <!-- Összesítő kártyák -->
                <div class="summary-cards">
                    <div class="summary-card">
                        <div class="card-icon">💬</div>
                        <div class="card-content">
                            <span class="card-value">{{ formatNumber(summary.total_messages) }}</span>
                            <span class="card-label">{{ gettext('metrics.total_messages') }}</span>
                        </div>
                    </div>
                    
                    <div class="summary-card">
                        <div class="card-icon">🔤</div>
                        <div class="card-content">
                            <span class="card-value">{{ formatNumber(summary.total_tokens) }}</span>
                            <span class="card-label">{{ gettext('metrics.total_tokens') }}</span>
                        </div>
                    </div>
                    
                    <div class="summary-card">
                        <div class="card-icon">⚡</div>
                        <div class="card-content">
                            <span class="card-value">{{ formatNumber(summary.avg_response_time) }}ms</span>
                            <span class="card-label">{{ gettext('metrics.avg_response') }}</span>
                        </div>
                    </div>
                    
                    <div class="summary-card">
                        <div class="card-icon">👥</div>
                        <div class="card-content">
                            <span class="card-value">{{ formatNumber(summary.active_users) }}</span>
                            <span class="card-label">{{ gettext('metrics.active_users') }}</span>
                        </div>
                    </div>
                </div>
                
                <!-- Grafikonok -->
                <div class="charts-grid">
                    <!-- Token használat idővonal -->
                    <div class="chart-card">
                        <div class="chart-header">
                            <h4>{{ gettext('metrics.token_usage') }}</h4>
                            <div class="chart-legend">
                                <span class="legend-item">
                                    <span class="legend-color" style="background: #7aa2f7;"></span>
                                    {{ gettext('metrics.tokens') }}
                                </span>
                            </div>
                        </div>
                        <div class="chart-container">
                            <canvas ref="tokenChart"></canvas>
                        </div>
                    </div>
                    
                    <!-- Válaszidők -->
                    <div class="chart-card">
                        <div class="chart-header">
                            <h4>{{ gettext('metrics.response_times') }}</h4>
                            <div class="chart-legend">
                                <span class="legend-item">
                                    <span class="legend-color" style="background: #9ece6a;"></span>
                                    {{ gettext('metrics.avg_time') }}
                                </span>
                            </div>
                        </div>
                        <div class="chart-container">
                            <canvas ref="responseChart"></canvas>
                        </div>
                    </div>
                    
                    <!-- Aktív beszélgetések -->
                    <div class="chart-card">
                        <div class="chart-header">
                            <h4>{{ gettext('metrics.active_conversations') }}</h4>
                        </div>
                        <div class="chart-container">
                            <canvas ref="conversationChart"></canvas>
                        </div>
                    </div>
                    
                    <!-- GPU használat (ha van) -->
                    <div class="chart-card" v-if="hasGPU">
                        <div class="chart-header">
                            <h4>{{ gettext('metrics.gpu_usage') }}</h4>
                            <div class="chart-legend">
                                <span class="legend-item">
                                    <span class="legend-color" style="background: #f7768e;"></span>
                                    {{ gettext('metrics.gpu_0') }}
                                </span>
                                <span class="legend-item" v-if="gpuCount > 1">
                                    <span class="legend-color" style="background: #bb9af7;"></span>
                                    {{ gettext('metrics.gpu_1') }}
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
                    <!-- Legaktívabb felhasználók -->
                    <div class="details-card">
                        <h4>{{ gettext('metrics.top_users') }}</h4>
                        <table class="metrics-table">
                            <thead>
                                <tr>
                                    <th>{{ gettext('metrics.user') }}</th>
                                    <th>{{ gettext('metrics.messages') }}</th>
                                    <th>{{ gettext('metrics.tokens') }}</th>
                                    <th>{{ gettext('metrics.avg_time') }}</th>
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
                    
                    <!-- Leggyakoribb intentek -->
                    <div class="details-card">
                        <h4>{{ gettext('metrics.top_intents') }}</h4>
                        <table class="metrics-table">
                            <thead>
                                <tr>
                                    <th>{{ gettext('metrics.intent') }}</th>
                                    <th>{{ gettext('metrics.count') }}</th>
                                    <th>{{ gettext('metrics.percentage') }}</th>
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
                    
                    <!-- Rendszer erőforrások -->
                    <div class="details-card">
                        <h4>{{ gettext('metrics.system_resources') }}</h4>
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
                            
                            <div class="resource-item" v-for="(gpu, index) in resources.gpus" :key="index">
                                <span class="resource-label">GPU{{ index }}:</span>
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
        
        // Chart objektumok
        let charts = {};
        
        // ====================================================================
        // SEGÉDFÜGGVÉNYEK
        // ====================================================================
        
        const gettext = (key, params = {}) => {
            return window.gettext ? window.gettext(key, params) : key;
        };
        
        const formatNumber = (num) => {
            if (num === undefined || num === null) return '0';
            return num.toLocaleString();
        };
        
        const formatTime = (timestamp) => {
            const date = new Date(timestamp);
            
            if (timeRange.value === 'hour') {
                return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            } else if (timeRange.value === 'day') {
                return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            } else {
                return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
            }
        };
        
        // ====================================================================
        // CHART KEZELÉS
        // ====================================================================
        
        const initCharts = () => {
            // Token használat chart
            if (tokenChart.value) {
                charts.token = new Chart(tokenChart.value, {
                    type: 'line',
                    data: {
                        labels: timeSeriesData.value.timestamps.map(ts => formatTime(ts)),
                        datasets: [{
                            label: gettext('metrics.tokens'),
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
            
            // Válaszidő chart
            if (responseChart.value) {
                charts.response = new Chart(responseChart.value, {
                    type: 'line',
                    data: {
                        labels: timeSeriesData.value.timestamps.map(ts => formatTime(ts)),
                        datasets: [{
                            label: gettext('metrics.avg_time'),
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
            
            // Beszélgetés chart
            if (conversationChart.value) {
                charts.conversation = new Chart(conversationChart.value, {
                    type: 'bar',
                    data: {
                        labels: timeSeriesData.value.timestamps.map(ts => formatTime(ts)),
                        datasets: [{
                            label: gettext('metrics.conversations'),
                            data: timeSeriesData.value.conversations,
                            backgroundColor: '#e5c890',
                            borderRadius: 4
                        }]
                    },
                    options: {
                        ...chartOptions,
                        scales: {
                            y: {
                                beginAtZero: true,
                                ticks: {
                                    stepSize: 1
                                }
                            }
                        }
                    }
                });
            }
            
            // GPU chart
            if (gpuChart.value && hasGPU.value) {
                const datasets = [];
                
                if (gpuCount.value >= 1) {
                    datasets.push({
                        label: gettext('metrics.gpu_0'),
                        data: timeSeriesData.value.gpu.map(d => d[0] || 0),
                        borderColor: '#f7768e',
                        backgroundColor: 'rgba(247, 118, 142, 0.1)',
                        tension: 0.4
                    });
                }
                
                if (gpuCount.value >= 2) {
                    datasets.push({
                        label: gettext('metrics.gpu_1'),
                        data: timeSeriesData.value.gpu.map(d => d[1] || 0),
                        borderColor: '#bb9af7',
                        backgroundColor: 'rgba(187, 154, 247, 0.1)',
                        tension: 0.4
                    });
                }
                
                charts.gpu = new Chart(gpuChart.value, {
                    type: 'line',
                    data: {
                        labels: timeSeriesData.value.timestamps.map(ts => formatTime(ts)),
                        datasets: datasets
                    },
                    options: {
                        ...chartOptions,
                        scales: {
                            y: {
                                beginAtZero: true,
                                max: 100,
                                ticks: {
                                    callback: value => value + '%'
                                }
                            }
                        }
                    }
                });
            }
            
            hasCharts.value = true;
        };
        
        const chartOptions = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: '#1a1e24',
                    titleColor: '#e0e0e0',
                    bodyColor: '#e0e0e0',
                    borderColor: '#2a2f38',
                    borderWidth: 1
                }
            },
            scales: {
                x: {
                    grid: {
                        color: '#2a2f38'
                    },
                    ticks: {
                        color: '#888'
                    }
                },
                y: {
                    grid: {
                        color: '#2a2f38'
                    },
                    ticks: {
                        color: '#888'
                    }
                }
            }
        };
        
        const updateCharts = () => {
            if (charts.token) {
                charts.token.data.labels = timeSeriesData.value.timestamps.map(ts => formatTime(ts));
                charts.token.data.datasets[0].data = timeSeriesData.value.tokens;
                charts.token.update();
            }
            
            if (charts.response) {
                charts.response.data.labels = timeSeriesData.value.timestamps.map(ts => formatTime(ts));
                charts.response.data.datasets[0].data = timeSeriesData.value.responses;
                charts.response.update();
            }
            
            if (charts.conversation) {
                charts.conversation.data.labels = timeSeriesData.value.timestamps.map(ts => formatTime(ts));
                charts.conversation.data.datasets[0].data = timeSeriesData.value.conversations;
                charts.conversation.update();
            }
            
            if (charts.gpu && hasGPU.value) {
                charts.gpu.data.labels = timeSeriesData.value.timestamps.map(ts => formatTime(ts));
                
                if (gpuCount.value >= 1) {
                    charts.gpu.data.datasets[0].data = timeSeriesData.value.gpu.map(d => d[0] || 0);
                }
                
                if (gpuCount.value >= 2 && charts.gpu.data.datasets[1]) {
                    charts.gpu.data.datasets[1].data = timeSeriesData.value.gpu.map(d => d[1] || 0);
                }
                
                charts.gpu.update();
            }
        };
        
        // ====================================================================
        // ADATOK BETÖLTÉSE
        // ====================================================================
        
        const loadMetrics = async () => {
            loading.value = true;
            
            try {
                if (window.api) {
                    const data = await window.api.getMetrics(timeRange.value);
                    processMetricsData(data);
                } else {
                    // Demo adatok
                    generateDemoData();
                }
                
                // GPU információk betöltése
                await loadGPUInfo();
                
                // Rendszer erőforrások
                await loadResources();
                
                // Chartok frissítése
                Vue.nextTick(() => {
                    if (!hasCharts.value) {
                        initCharts();
                    } else {
                        updateCharts();
                    }
                });
                
            } catch (error) {
                console.error('Error loading metrics:', error);
            } finally {
                loading.value = false;
            }
        };
        
        const loadGPUInfo = async () => {
            if (window.store?.gpuStatus) {
                const gpus = window.store.gpuStatus;
                hasGPU.value = gpus.length > 0;
                gpuCount.value = gpus.length;
            }
        };
        
        const loadResources = async () => {
            // Itt lehetne valós rendszer erőforrásokat lekérni
            // Most demo adatok
            resources.value = {
                cpu: Math.floor(Math.random() * 60) + 20,
                ram: Math.floor(Math.random() * 50) + 30,
                gpus: [Math.floor(Math.random() * 70) + 10]
            };
            
            if (gpuCount.value > 1) {
                resources.value.gpus.push(Math.floor(Math.random() * 60) + 20);
            }
        };
        
        const processMetricsData = (data) => {
            if (!data) return;
            
            // Összesített adatok
            summary.value = {
                total_messages: data.total_messages || 0,
                total_tokens: data.total_tokens || 0,
                avg_response_time: data.avg_response_time || 0,
                active_users: data.active_users || 0
            };
            
            // Idősoros adatok
            timeSeriesData.value = {
                timestamps: data.timestamps || generateTimestamps(24),
                tokens: data.tokens || generateRandomData(24, 100, 1000),
                responses: data.responses || generateRandomData(24, 50, 500),
                conversations: data.conversations || generateRandomData(24, 1, 10, true),
                gpu: data.gpu || generateGPUData(24, gpuCount.value)
            };
            
            // Részletes adatok
            topUsers.value = data.top_users || generateTopUsers(5);
            topIntents.value = data.top_intents || generateTopIntents(5);
        };
        
        // ====================================================================
        // DEMO ADATOK GENERÁLÁSA
        // ====================================================================
        
        const generateTimestamps = (count) => {
            const timestamps = [];
            const now = Date.now();
            const interval = timeRange.value === 'hour' ? 60000 : 3600000;
            
            for (let i = count; i >= 0; i--) {
                timestamps.push(now - i * interval);
            }
            
            return timestamps;
        };
        
        const generateRandomData = (count, min, max, integer = false) => {
            const data = [];
            for (let i = 0; i <= count; i++) {
                let value = Math.random() * (max - min) + min;
                if (integer) value = Math.floor(value);
                data.push(value);
            }
            return data;
        };
        
        const generateGPUData = (count, gpuCount) => {
            const data = [];
            for (let i = 0; i <= count; i++) {
                const gpuData = [];
                for (let g = 0; g < gpuCount; g++) {
                    gpuData.push(Math.floor(Math.random() * 70) + 10);
                }
                data.push(gpuData);
            }
            return data;
        };
        
        const generateTopUsers = (count) => {
            const users = [];
            const names = ['Alice', 'Bob', 'Charlie', 'Diana', 'Eve'];
            
            for (let i = 0; i < count; i++) {
                users.push({
                    id: i + 1,
                    name: names[i] || `User${i + 1}`,
                    messages: Math.floor(Math.random() * 500) + 100,
                    tokens: Math.floor(Math.random() * 10000) + 1000,
                    avg_time: Math.floor(Math.random() * 2000) + 500
                });
            }
            
            return users;
        };
        
        const generateTopIntents = (count) => {
            const intents = [];
            const names = ['greeting', 'question', 'command', 'farewell', 'knowledge'];
            const total = Math.floor(Math.random() * 1000) + 500;
            
            for (let i = 0; i < count; i++) {
                const count = Math.floor(Math.random() * 300) + 50;
                intents.push({
                    name: names[i] || `intent_${i + 1}`,
                    count: count,
                    percentage: Math.round((count / total) * 100)
                });
            }
            
            return intents;
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
        
        // ====================================================================
        // EXPORTÁLÁS
        // ====================================================================
        
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
                a.download = `metrics_${timeRange.value}_${new Date().toISOString().slice(0,10)}.json`;
                a.click();
                
            } else if (format === 'csv') {
                let csv = 'Timestamp,Tokens,ResponseTime,Conversations\n';
                
                timeSeriesData.value.timestamps.forEach((ts, i) => {
                    csv += `${new Date(ts).toISOString()},`;
                    csv += `${timeSeriesData.value.tokens[i] || 0},`;
                    csv += `${timeSeriesData.value.responses[i] || 0},`;
                    csv += `${timeSeriesData.value.conversations[i] || 0}\n`;
                });
                
                const blob = new Blob([csv], { type: 'text/csv' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `metrics_${timeRange.value}_${new Date().toISOString().slice(0,10)}.csv`;
                a.click();
                
            } else if (format === 'png') {
                // Itt lehetne screenshotot készíteni a chartokról
                alert(gettext('metrics.png_export_not_implemented'));
            }
        };
        
        // ====================================================================
        // ÉLETCIKLUS
        // ====================================================================
        
        Vue.onMounted(() => {
            loadMetrics();
            
            // GPU státusz figyelése
            if (window.store) {
                Vue.watch(() => window.store.gpuStatus, (newGpus) => {
                    hasGPU.value = newGpus.length > 0;
                    gpuCount.value = newGpus.length;
                });
            }
        });
        
        Vue.onUnmounted(() => {
            // Chartok megsemmisítése
            Object.values(charts).forEach(chart => {
                if (chart) chart.destroy();
            });
        });
        
        return {
            // Állapotok
            loading,
            timeRange,
            hasGPU,
            gpuCount,
            hasCharts,
            summary,
            timeSeriesData,
            topUsers,
            topIntents,
            resources,
            
            // Chart refek
            tokenChart,
            responseChart,
            conversationChart,
            gpuChart,
            
            // Metódusok
            gettext,
            formatNumber,
            loadMetrics,
            exportMetrics
        };
    }
};

window.SystemMetrics = SystemMetrics;
console.log('✅ SystemMetrics betöltve globálisan');