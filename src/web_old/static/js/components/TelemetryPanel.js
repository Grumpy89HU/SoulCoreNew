// Telemetria panel
window.TelemetryPanel = {
    template: `
        <div class="telemetry-container">
            <div class="panel-header">
                <span>🔍 {{ gettext('telemetry.title') }}</span>
                <button class="refresh-btn" @click="refreshData" :disabled="refreshing">
                    <span :class="{ 'spin': refreshing }">🔄</span>
                </button>
            </div>
            
            <div class="panel-content">
                <!-- ==================================================================== -->
                <!-- RENDSZER INFORMÁCIÓK -->
                <!-- ==================================================================== -->
                
                <div class="metric-group">
                    <div class="metric-group-title">{{ gettext('telemetry.system') }}</div>
                    
                    <div class="metric">
                        <div class="metric-label">{{ gettext('telemetry.uptime') }}</div>
                        <div class="metric-value">{{ formatUptime(systemStats.uptime) }}</div>
                    </div>
                    
                    <div class="metric">
                        <div class="metric-label">{{ gettext('telemetry.idle') }}</div>
                        <div class="metric-value">{{ formatUptime(systemStats.idle) }}</div>
                    </div>
                    
                    <div class="metric">
                        <div class="metric-label">{{ gettext('telemetry.heartbeat') }}</div>
                        <div class="metric-value">{{ heartbeat.beats || 0 }} <span class="metric-unit">{{ gettext('telemetry.beats') }}</span></div>
                    </div>
                    
                    <div class="metric">
                        <div class="metric-label">{{ gettext('telemetry.proactive') }}</div>
                        <div class="metric-value">{{ heartbeat.proactive_count || 0 }}</div>
                    </div>
                    
                    <div class="metric">
                        <div class="metric-label">{{ gettext('telemetry.reminders') }}</div>
                        <div class="metric-value">{{ heartbeat.reminder_count || 0 }}</div>
                    </div>
                </div>
                
                <!-- ==================================================================== -->
                <!-- GPU INFORMÁCIÓK -->
                <!-- ==================================================================== -->
                
                <div class="metric-group">
                    <div class="metric-group-title">{{ gettext('telemetry.gpu') }}</div>
                    
                    <div v-if="gpuStatus.length === 0" class="metric">
                        <div class="metric-label">{{ gettext('telemetry.no_gpu') }}</div>
                    </div>
                    
                    <div v-for="(gpu, index) in gpuStatus" :key="index" class="gpu-card">
                        <div class="gpu-header">
                            <span class="gpu-name">GPU {{ index }}</span>
                            <span class="gpu-status" :class="'status-' + gpu.status">{{ gpu.status }}</span>
                        </div>
                        
                        <!-- Hőmérséklet -->
                        <div class="metric">
                            <div class="metric-label">{{ gettext('telemetry.temperature') }}</div>
                            <div class="metric-value" :class="'temp-' + gpu.tempLevel">
                                {{ gpu.temperature }}°C
                                <span class="metric-unit">{{ gettext('telemetry.celsius') }}</span>
                            </div>
                            <div class="temp-bar">
                                <div class="temp-fill" :style="{ width: (gpu.temperature / 100 * 100) + '%' }"></div>
                            </div>
                        </div>
                        
                        <!-- VRAM használat -->
                        <div class="metric">
                            <div class="metric-label">{{ gettext('telemetry.vram') }}</div>
                            <div class="metric-value">
                                {{ formatBytes(gpu.vram_used * 1024 * 1024) }} / {{ formatBytes(gpu.vram_total * 1024 * 1024) }}
                            </div>
                            <div class="progress-bar">
                                <div class="progress-fill" :style="{ width: gpu.vram_percent + '%' }"
                                     :class="{ 'warning': gpu.vram_percent > 85, 'critical': gpu.vram_percent > 95 }">
                                </div>
                            </div>
                        </div>
                        
                        <!-- GPU kihasználtság -->
                        <div class="metric">
                            <div class="metric-label">{{ gettext('telemetry.utilization') }}</div>
                            <div class="metric-value">{{ gpu.utilization }}%</div>
                            <div class="progress-bar">
                                <div class="progress-fill" :style="{ width: gpu.utilization + '%' }"></div>
                            </div>
                        </div>
                        
                        <!-- Teljesítmény -->
                        <div class="metric">
                            <div class="metric-label">{{ gettext('telemetry.power') }}</div>
                            <div class="metric-value">{{ gpu.power }} W</div>
                        </div>
                    </div>
                </div>
                
                <!-- ==================================================================== -->
                <!-- KING STATISZTIKÁK -->
                <!-- ==================================================================== -->
                
                <div class="metric-group">
                    <div class="metric-group-title">{{ gettext('telemetry.king') }}</div>
                    
                    <div class="metric">
                        <div class="metric-label">{{ gettext('telemetry.king_status') }}</div>
                        <div class="metric-value" :class="kingStatusClass">
                            {{ gettext('telemetry.status_' + (kingState.status || 'unknown')) }}
                        </div>
                    </div>
                    
                    <div class="metric">
                        <div class="metric-label">{{ gettext('telemetry.king_mood') }}</div>
                        <div class="metric-value" :class="'mood-' + kingState.mood">
                            {{ gettext('telemetry.mood_' + (kingState.mood || 'neutral')) }}
                        </div>
                    </div>
                    
                    <div class="metric">
                        <div class="metric-label">{{ gettext('telemetry.responses') }}</div>
                        <div class="metric-value">{{ kingState.response_count || 0 }}</div>
                    </div>
                    
                    <div class="metric">
                        <div class="metric-label">{{ gettext('telemetry.avg_response_time') }}</div>
                        <div class="metric-value">{{ formatTime(kingState.average_response_time) }}</div>
                    </div>
                    
                    <div class="metric">
                        <div class="metric-label">{{ gettext('telemetry.model_loaded') }}</div>
                        <div class="metric-value">
                            <span class="status-indicator" :class="{ active: kingState.model_loaded }"></span>
                            {{ kingState.model_loaded ? gettext('telemetry.yes') : gettext('telemetry.no') }}
                        </div>
                    </div>
                </div>
                
                <!-- ==================================================================== -->
                <!-- EGYÉB AGENSEK -->
                <!-- ==================================================================== -->
                
                <div class="metric-group">
                    <div class="metric-group-title">{{ gettext('telemetry.agents') }}</div>
                    
                    <div class="metric">
                        <div class="metric-label">{{ gettext('telemetry.jester') }}</div>
                        <div class="metric-value">
                            <span class="status-indicator" :class="{ active: jesterState.status == 'watching' }"></span>
                            {{ jesterState.status || 'unknown' }}
                        </div>
                        <div class="metric-note" v-if="jesterState.warnings">
                            ⚠️ {{ jesterState.warnings }}
                        </div>
                    </div>
                    
                    <div class="metric">
                        <div class="metric-label">{{ gettext('telemetry.valet') }}</div>
                        <div class="metric-value">
                            <span class="status-indicator" :class="{ active: valetState.status == 'ready' }"></span>
                            {{ valetState.status || 'unknown' }}
                        </div>
                        <div class="metric-note" v-if="valetState.memories_stored">
                            💾 {{ valetState.memories_stored }} {{ gettext('telemetry.memories') }}
                        </div>
                    </div>
                    
                    <div class="metric">
                        <div class="metric-label">{{ gettext('telemetry.queen') }}</div>
                        <div class="metric-value">
                            <span class="status-indicator" :class="{ active: queenState.status == 'ready' }"></span>
                            {{ queenState.status || 'unknown' }}
                        </div>
                        <div class="metric-note" v-if="queenState.contradictions_found">
                            🔍 {{ queenState.contradictions_found }} {{ gettext('telemetry.contradictions') }}
                        </div>
                    </div>
                </div>
                
                <!-- ==================================================================== -->
                <!-- SENTINEL (THROTTLE) -->
                <!-- ==================================================================== -->
                
                <div class="metric-group" v-if="sentinelState">
                    <div class="metric-group-title">{{ gettext('telemetry.sentinel') }}</div>
                    
                    <div class="metric">
                        <div class="metric-label">{{ gettext('telemetry.throttle') }}</div>
                        <div class="metric-value" :class="{ 'throttle-active': sentinelState.throttle_active }">
                            {{ sentinelState.throttle_active ? gettext('telemetry.active') : gettext('telemetry.inactive') }}
                        </div>
                    </div>
                    
                    <div class="metric">
                        <div class="metric-label">{{ gettext('telemetry.throttle_factor') }}</div>
                        <div class="metric-value">{{ (sentinelState.throttle_factor * 100).toFixed(0) }}%</div>
                    </div>
                    
                    <div class="metric">
                        <div class="metric-label">{{ gettext('telemetry.recovery') }}</div>
                        <div class="metric-value" :class="{ 'recovery-active': sentinelState.recovery_mode }">
                            {{ sentinelState.recovery_mode ? gettext('telemetry.active') : gettext('telemetry.inactive') }}
                        </div>
                    </div>
                </div>
                
                <!-- ==================================================================== -->
                <!-- MEMÓRIA HASZNÁLAT -->
                <!-- ==================================================================== -->
                
                <div class="metric-group">
                    <div class="metric-group-title">{{ gettext('telemetry.memory') }}</div>
                    
                    <div class="metric">
                        <div class="metric-label">{{ gettext('telemetry.scratchpad') }}</div>
                        <div class="progress-bar">
                            <div class="progress-fill" :style="{ width: memoryPercent + '%' }"></div>
                        </div>
                        <div class="metric-note">{{ memoryPercent.toFixed(1) }}% {{ gettext('telemetry.used') }}</div>
                    </div>
                    
                    <div class="metric">
                        <div class="metric-label">{{ gettext('telemetry.cache') }}</div>
                        <div class="metric-value">{{ cacheSize }} {{ gettext('telemetry.entries') }}</div>
                    </div>
                    
                    <div class="metric">
                        <div class="metric-label">{{ gettext('telemetry.token_usage') }}</div>
                        <div class="metric-value">{{ formatNumber(totalTokens) }}</div>
                    </div>
                </div>
                
                <!-- ==================================================================== -->
                <!-- IDŐINFORMÁCIÓK -->
                <!-- ==================================================================== -->
                
                <div class="metric-group">
                    <div class="metric-group-title">{{ gettext('telemetry.time') }}</div>
                    
                    <div class="metric">
                        <div class="metric-label">{{ gettext('telemetry.current_time') }}</div>
                        <div class="metric-value">{{ currentTime }}</div>
                    </div>
                    
                    <div class="metric">
                        <div class="metric-label">{{ gettext('telemetry.time_of_day') }}</div>
                        <div class="metric-value">{{ gettext('telemetry.time_' + (timeOfDay || 'day')) }}</div>
                    </div>
                    
                    <div class="metric">
                        <div class="metric-label">{{ gettext('telemetry.last_interaction') }}</div>
                        <div class="metric-value">{{ formatUptime(idleSeconds) }} {{ gettext('telemetry.ago') }}</div>
                    </div>
                </div>
            </div>
        </div>
    `,
    
    setup() {
        // ====================================================================
        // REAKTÍV ÁLLAPOTOK
        // ====================================================================
        
        const heartbeat = Vue.computed(() => window.store?.heartbeat || {});
        const kingState = Vue.computed(() => window.store?.kingState || {});
        const queenState = Vue.computed(() => window.store?.queenState || {});
        const jesterState = Vue.computed(() => window.store?.jesterState || {});
        const valetState = Vue.computed(() => window.store?.valetState || {});
        const gpuStatus = Vue.computed(() => window.store?.gpuStatus || []);
        const sentinelState = Vue.computed(() => window.store?.sentinelState || {});
        const metrics = Vue.computed(() => window.store?.metrics || {});
        
        // Számított értékek
        const memoryPercent = Vue.ref(0);
        const cacheSize = Vue.ref(0);
        const totalTokens = Vue.ref(0);
        const refreshing = Vue.ref(false);
        const currentTime = Vue.ref(new Date().toLocaleTimeString());
        const timeOfDay = Vue.ref('day');
        const idleSeconds = Vue.ref(0);
        
        // ====================================================================
        // COMPUTED PROPERTIES
        // ====================================================================
        
        const systemStats = Vue.computed(() => ({
            uptime: heartbeat.value.uptime_seconds || 0,
            idle: heartbeat.value.idle_seconds || 0,
            beats: heartbeat.value.beats || 0,
            proactive: heartbeat.value.proactive_count || 0,
            reminders: heartbeat.value.reminder_count || 0
        }));
        
        const kingStatusClass = Vue.computed(() => ({
            'status-ready': kingState.value.status === 'ready',
            'status-processing': kingState.value.status === 'processing',
            'status-error': kingState.value.status === 'error',
            'status-idle': kingState.value.status === 'idle'
        }));
        
        // ====================================================================
        // METÓDUSOK
        // ====================================================================
        
        const formatUptime = (seconds) => {
            if (!seconds) return '0s';
            
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            const secs = Math.floor(seconds % 60);
            
            if (hours > 0) {
                return `${hours}h ${minutes}m`;
            } else if (minutes > 0) {
                return `${minutes}m ${secs}s`;
            } else {
                return `${secs}s`;
            }
        };
        
        const formatBytes = (bytes) => {
            if (bytes === 0) return '0 B';
            
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        };
        
        const formatNumber = (num) => {
            if (num === undefined || num === null) return '0';
            return num.toLocaleString();
        };
        
        const formatTime = (seconds) => {
            if (!seconds) return '0ms';
            
            if (seconds < 1) {
                return (seconds * 1000).toFixed(0) + 'ms';
            } else {
                return seconds.toFixed(2) + 's';
            }
        };
        
        const gettext = (key, params = {}) => {
            return window.gettext ? window.gettext(key, params) : key;
        };
        
        const refreshData = async () => {
            refreshing.value = true;
            
            try {
                if (window.socketManager) {
                    window.socketManager.getStatus();
                }
                
                if (window.api) {
                    const [kingMetrics, sentinelStatus] = await Promise.all([
                        window.api.getKingMetrics?.().catch(() => null),
                        window.api.getSentinelStatus?.().catch(() => null)
                    ]);
                    
                    if (kingMetrics) {
                        totalTokens.value = kingMetrics.total_tokens || 0;
                    }
                }
                
                // Kis késleltetés a vizuális visszajelzésért
                await new Promise(resolve => setTimeout(resolve, 500));
                
            } finally {
                refreshing.value = false;
            }
        };
        
        // ====================================================================
        // WATCHEREK
        // ====================================================================
        
        // GPU státusz figyelése
        Vue.watch(gpuStatus, (newGpus) => {
            // Összes VRAM számítás
            const totalVram = newGpus.reduce((sum, gpu) => sum + (gpu.vram_total || 0), 0);
            const usedVram = newGpus.reduce((sum, gpu) => sum + (gpu.vram_used || 0), 0);
            memoryPercent.value = totalVram > 0 ? (usedVram / totalVram) * 100 : 0;
        }, { immediate: true });
        
        // Cache méret figyelése
        Vue.watch(() => window.store?.state, (newState) => {
            if (newState) {
                cacheSize.value = newState.messages?.length || 0;
            }
        }, { deep: true, immediate: true });
        
        // Idő frissítése
        setInterval(() => {
            currentTime.value = new Date().toLocaleTimeString();
            
            const hour = new Date().getHours();
            if (hour < 6) timeOfDay.value = 'night';
            else if (hour < 12) timeOfDay.value = 'morning';
            else if (hour < 18) timeOfDay.value = 'afternoon';
            else timeOfDay.value = 'evening';
            
            if (heartbeat.value.last_interaction) {
                idleSeconds.value = Math.floor((Date.now() / 1000) - heartbeat.value.last_interaction);
            }
        }, 1000);
        
        // ====================================================================
        // ÉLETCIKLUS
        // ====================================================================
        
        Vue.onMounted(() => {
            refreshData();
        });
        
        return {
            // Állapotok
            heartbeat,
            kingState,
            queenState,
            jesterState,
            valetState,
            gpuStatus,
            sentinelState,
            metrics,
            
            memoryPercent,
            cacheSize,
            totalTokens,
            refreshing,
            currentTime,
            timeOfDay,
            idleSeconds,
            
            systemStats,
            kingStatusClass,
            
            // Metódusok
            formatUptime,
            formatBytes,
            formatNumber,
            formatTime,
            gettext,
            refreshData
        };
    }
};

window.TelemetryPanel = TelemetryPanel;
console.log('✅ Telemetria panel betöltve globálisan');