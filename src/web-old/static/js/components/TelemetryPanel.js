// ==============================================
// SOULCORE 3.0 - Telemetria panel komponens
// TELJES VERZIÓ - MINDEN FUNKCIÓVAL
// ==============================================

window.TelemetryPanel = {
    name: 'TelemetryPanel',
    
    template: `
        <div class="telemetry-panel">
            <!-- Rendszer információk -->
            <div class="metric-group">
                <div class="metric-group-title">{{ t('telemetry.system') }}</div>
                <div class="metric">
                    <label>🔧 {{ t('telemetry.status') }}</label>
                    <span class="metric-value">{{ status }}</span>
                </div>
                <div class="metric">
                    <label>💓 {{ t('telemetry.uptime') }}</label>
                    <span class="metric-value">{{ formatUptime(heartbeat?.uptime_seconds || 0) }}</span>
                </div>
                <div class="metric">
                    <label>🆔 {{ t('telemetry.system_id') }}</label>
                    <span class="metric-value"><code>{{ systemId || '—' }}</code></span>
                </div>
            </div>
            
            <!-- Király állapota -->
            <div class="metric-group">
                <div class="metric-group-title">{{ t('telemetry.king') }}</div>
                <div class="metric">
                    <label>👑 {{ t('telemetry.king_status') }}</label>
                    <span class="metric-value">
                        <span class="status-badge" :class="kingState?.status">{{ formatStatus(kingState?.status) }}</span>
                    </span>
                </div>
                <div class="metric">
                    <label>😊 {{ t('telemetry.king_mood') }}</label>
                    <span class="metric-value">{{ formatMood(kingState?.mood) }}</span>
                </div>
                <div class="metric" v-if="kingState?.model_loaded">
                    <label>🤖 {{ t('telemetry.model_loaded') }}</label>
                    <span class="metric-value">{{ t('telemetry.yes') }}</span>
                </div>
                <div class="metric" v-if="kingState?.response_count">
                    <label>📊 {{ t('telemetry.responses') }}</label>
                    <span class="metric-value">{{ formatNumber(kingState.response_count) }}</span>
                </div>
                <div class="metric" v-if="kingState?.avg_response_time">
                    <label>⚡ {{ t('telemetry.avg_response_time') }}</label>
                    <span class="metric-value">{{ kingState.avg_response_time }}ms</span>
                </div>
            </div>
            
            <!-- GPU állapot -->
            <div class="metric-group" v-if="gpuStatus && gpuStatus.length">
                <div class="metric-group-title">{{ t('telemetry.gpu') }}</div>
                <div v-for="(gpu, idx) in gpuStatus" :key="idx" class="gpu-card">
                    <div class="gpu-header">
                        <span class="gpu-name">GPU {{ idx }}</span>
                        <span class="gpu-status" :class="gpu.status">{{ gpu.status }}</span>
                    </div>
                    <div class="metric">
                        <label>{{ t('telemetry.temperature') }}</label>
                        <span :class="getTempClass(gpu.temperature)">
                            {{ gpu.temperature || 0 }}°C
                        </span>
                    </div>
                    <div class="metric">
                        <label>{{ t('telemetry.vram') }}</label>
                        <span>{{ formatBytes(gpu.vram_used) }} / {{ formatBytes(gpu.vram_total) }}</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" :class="getVramClass(gpu.vram_percent)" :style="{ width: (gpu.vram_percent || 0) + '%' }"></div>
                    </div>
                    <div class="metric">
                        <label>{{ t('telemetry.utilization') }}</label>
                        <span>{{ gpu.utilization || 0 }}%</span>
                    </div>
                    <div class="metric" v-if="gpu.power">
                        <label>{{ t('telemetry.power') }}</label>
                        <span>{{ gpu.power }}W</span>
                    </div>
                </div>
                
                <!-- Sentinel állapot -->
                <div v-if="sentinelState && sentinelState.throttle_active" class="metric">
                    <label>⚠️ {{ t('telemetry.throttle') }}</label>
                    <span class="metric-value warning">{{ t('telemetry.active') }}</span>
                </div>
                <div v-if="sentinelState && sentinelState.throttle_factor !== undefined && sentinelState.throttle_factor !== 1.0" class="metric">
                    <label>{{ t('telemetry.throttle_factor') }}</label>
                    <span class="metric-value">{{ ((sentinelState.throttle_factor || 1) * 100).toFixed(0) }}%</span>
                </div>
                <div v-if="sentinelState && sentinelState.recovery_mode" class="metric">
                    <label>🔄 {{ t('telemetry.recovery') }}</label>
                    <span class="metric-value warning">{{ t('telemetry.active') }}</span>
                </div>
            </div>
            
            <!-- Modulok állapota -->
            <div class="metric-group">
                <div class="metric-group-title">{{ t('telemetry.modules') }}</div>
                <div v-for="(status, name) in modules" :key="name" class="metric">
                    <label>{{ formatModuleName(name) }}</label>
                    <span class="status-badge" :class="status">{{ formatStatus(status) }}</span>
                </div>
            </div>
            
            <!-- Memória (Scratchpad) -->
            <div class="metric-group" v-if="memoryStats">
                <div class="metric-group-title">{{ t('telemetry.memory') }}</div>
                <div class="metric">
                    <label>📝 {{ t('telemetry.scratchpad') }}</label>
                    <span class="metric-value">{{ memoryStats.percent || 0 }}% {{ t('telemetry.used') }}</span>
                </div>
                <div class="progress-bar" v-if="memoryStats.percent">
                    <div class="progress-fill" :style="{ width: (memoryStats.percent || 0) + '%' }"></div>
                </div>
                <div class="metric" v-if="memoryStats.entry_count">
                    <label>📋 {{ t('telemetry.cache') }}</label>
                    <span class="metric-value">{{ memoryStats.entry_count }} {{ t('telemetry.entries') }}</span>
                </div>
            </div>
            
            <!-- Heartbeat adatok -->
            <div class="metric-group">
                <div class="metric-group-title">{{ t('telemetry.heartbeat') }}</div>
                <div class="metric">
                    <label>💓 {{ t('telemetry.beats') }}</label>
                    <span class="metric-value">{{ formatNumber(heartbeat?.beats || 0) }}</span>
                </div>
                <div class="metric">
                    <label>🔮 {{ t('telemetry.proactive') }}</label>
                    <span class="metric-value">{{ formatNumber(heartbeat?.proactive_count || 0) }}</span>
                </div>
                <div class="metric">
                    <label>⏰ {{ t('telemetry.reminders') }}</label>
                    <span class="metric-value">{{ formatNumber(heartbeat?.reminder_count || 0) }}</span>
                </div>
            </div>
            
            <!-- Token használat -->
            <div class="metric-group" v-if="metrics && metrics.total_tokens">
                <div class="metric-group-title">{{ t('telemetry.token_usage') }}</div>
                <div class="metric">
                    <label>🔤 {{ t('telemetry.total_tokens') }}</label>
                    <span class="metric-value">{{ formatNumber(metrics.total_tokens) }}</span>
                </div>
                <div class="metric" v-if="metrics.total_messages">
                    <label>💬 {{ t('telemetry.total_messages') }}</label>
                    <span class="metric-value">{{ formatNumber(metrics.total_messages) }}</span>
                </div>
            </div>
            
            <!-- Idő -->
            <div class="metric-group">
                <div class="metric-group-title">{{ t('telemetry.time') }}</div>
                <div class="metric">
                    <label>🕐 {{ t('telemetry.current_time') }}</label>
                    <span class="metric-value">{{ currentTime }}</span>
                </div>
                <div class="metric" v-if="lastInteraction">
                    <label>💬 {{ t('telemetry.last_interaction') }}</label>
                    <span class="metric-value">{{ lastInteraction }} {{ t('telemetry.ago') }}</span>
                </div>
                <div class="metric">
                    <label>🌞 {{ t('telemetry.time_of_day') }}</label>
                    <span class="metric-value">{{ timeOfDay }}</span>
                </div>
            </div>
        </div>
    `,
    
    setup() {
        const systemId = Vue.computed(() => window.store.systemId);
        const status = Vue.computed(() => 'running');
        const kingState = Vue.computed(() => window.store.kingState);
        const heartbeat = Vue.computed(() => window.store.heartbeat);
        const gpuStatus = Vue.computed(() => window.store.gpuStatus || []);
        const sentinelState = Vue.computed(() => window.store.sentinelState);
        const modules = Vue.computed(() => window.store.modules || {});
        const metrics = Vue.computed(() => window.store.metrics);
        const memoryStats = Vue.computed(() => window.store.memoryStats);
        
        const currentTime = Vue.ref(new Date().toLocaleTimeString());
        const lastInteraction = Vue.ref(null);
        const timeOfDay = Vue.ref('');
        
        const t = (key, params = {}) => window.gettext(key, params);
        const formatUptime = (s) => window.formatUptime(s);
        const formatBytes = (b) => window.formatBytes(b);
        const formatNumber = (n) => window.formatNumber(n);
        const formatStatus = (s) => window.formatStatus(s);
        const formatMood = (m) => window.formatMood(m);
        const formatModuleName = (n) => window.formatModuleName(n);
        const getTempClass = (temp) => window.getTempClass(temp);
        const getVramClass = (p) => window.getVramClass(p);
        
        // Idő és napszak frissítése
        const updateTime = () => {
            const now = new Date();
            currentTime.value = now.toLocaleTimeString();
            const hour = now.getHours();
            if (hour < 6) timeOfDay.value = t('telemetry.time_night');
            else if (hour < 12) timeOfDay.value = t('telemetry.time_morning');
            else if (hour < 18) timeOfDay.value = t('telemetry.time_afternoon');
            else timeOfDay.value = t('telemetry.time_evening');
        };
        
        setInterval(updateTime, 1000);
        updateTime();
        
        // Utolsó interakció frissítése
        const updateLastInteraction = () => {
            const msgs = window.store.messages;
            if (msgs && msgs.length > 0) {
                const lastMsg = msgs[msgs.length - 1];
                if (lastMsg && lastMsg.timestamp) {
                    lastInteraction.value = window.formatRelativeTime(lastMsg.timestamp);
                }
            }
        };
        
        Vue.watch(() => window.store.messages, updateLastInteraction, { deep: true });
        
        // Automatikus frissítés
        let refreshInterval = null;
        
        const refreshData = async () => {
            try {
                await Promise.all([
                    window.api.getStatus(),
                    window.api.getKingState(),
                    window.api.getSentinelStatus()
                ]);
            } catch (error) {
                console.error('Hiba a telemetria frissítésekor:', error);
            }
        };
        
        Vue.onMounted(() => {
            refreshData();
            refreshInterval = setInterval(refreshData, 5000);
            updateLastInteraction();
        });
        
        Vue.onUnmounted(() => {
            if (refreshInterval) clearInterval(refreshInterval);
        });
        
        return {
            systemId,
            status,
            kingState,
            heartbeat,
            gpuStatus,
            sentinelState,
            modules,
            metrics,
            memoryStats,
            currentTime,
            lastInteraction,
            timeOfDay,
            t,
            formatUptime,
            formatBytes,
            formatNumber,
            formatStatus,
            formatMood,
            formatModuleName,
            getTempClass,
            getVramClass
        };
    }
};

console.log('✅ TelemetryPanel komponens betöltve (teljes verzió)');