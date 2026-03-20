// ==============================================
// SOULCORE 3.0 - Telemetria panel komponens
// ==============================================

window.TelemetryPanel = {
    name: 'TelemetryPanel',
    
    template: `
        <div class="telemetry-container">
            <!-- Rendszer információk -->
            <div class="metric-group">
                <div class="metric-group-title">{{ t('telemetry.system') }}</div>
                
                <div class="metric">
                    <div class="metric-label">{{ t('telemetry.uptime') }}</div>
                    <div class="metric-value">{{ formatUptime(uptime) }}</div>
                </div>
                
                <div class="metric">
                    <div class="metric-label">{{ t('telemetry.status') }}</div>
                    <div class="metric-value">
                        <span class="status-dot" :class="status"></span>
                        {{ formatStatus(status) }}
                    </div>
                </div>
                
                <div class="metric">
                    <div class="metric-label">{{ t('telemetry.system_id') }}</div>
                    <div class="metric-value"><code>{{ systemId }}</code></div>
                </div>
            </div>
            
            <!-- Király állapota -->
            <div class="metric-group">
                <div class="metric-group-title">{{ t('telemetry.king') }}</div>
                
                <div class="metric">
                    <div class="metric-label">{{ t('telemetry.king_status') }}</div>
                    <div class="metric-value">
                        <span class="status-dot" :class="kingState.status"></span>
                        {{ formatStatus(kingState.status) }}
                    </div>
                </div>
                
                <div class="metric">
                    <div class="metric-label">{{ t('telemetry.king_mood') }}</div>
                    <div class="metric-value">{{ formatMood(kingState.mood) }}</div>
                </div>
                
                <div class="metric" v-if="kingState.model_loaded">
                    <div class="metric-label">{{ t('telemetry.model_loaded') }}</div>
                    <div class="metric-value">{{ t('telemetry.yes') }}</div>
                </div>
            </div>
            
            <!-- GPU állapot -->
            <div class="metric-group" v-if="gpus.length > 0">
                <div class="metric-group-title">{{ t('telemetry.gpu') }}</div>
                
                <div v-for="(gpu, idx) in gpus" :key="idx" class="gpu-card">
                    <div class="gpu-header">
                        <span class="gpu-name">GPU {{ idx }}</span>
                        <span class="gpu-status" :class="'status-' + gpu.status">
                            {{ gpu.status }}
                        </span>
                    </div>
                    
                    <div class="metric">
                        <div class="metric-label">{{ t('telemetry.temperature') }}</div>
                        <div class="metric-value" :class="getTempClass(gpu.temperature)">
                            {{ gpu.temperature || 0 }}°C
                        </div>
                    </div>
                    
                    <div class="metric">
                        <div class="metric-label">{{ t('telemetry.vram') }}</div>
                        <div class="metric-value">
                            {{ formatBytes(gpu.vram_used) }} / {{ formatBytes(gpu.vram_total) }}
                        </div>
                        <div class="progress-bar">
                            <div class="progress-fill" :style="{ width: gpu.vram_percent + '%' }"
                                 :class="getVramClass(gpu.vram_percent)"></div>
                        </div>
                    </div>
                    
                    <div class="metric">
                        <div class="metric-label">{{ t('telemetry.utilization') }}</div>
                        <div class="metric-value">{{ gpu.utilization || 0 }}%</div>
                        <div class="progress-bar">
                            <div class="progress-fill" :style="{ width: (gpu.utilization || 0) + '%' }"></div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Modulok -->
            <div class="metric-group">
                <div class="metric-group-title">{{ t('telemetry.modules') }}</div>
                
                <div v-for="(status, name) in modules" :key="name" class="metric">
                    <div class="metric-label">{{ formatModuleName(name) }}</div>
                    <div class="metric-value">
                        <span class="status-dot" :class="status"></span>
                        {{ formatStatus(status) }}
                    </div>
                </div>
            </div>
        </div>
    `,
    
    setup() {
        const systemId = Vue.computed(() => window.store.systemId);
        const uptime = Vue.computed(() => window.store.uptime);
        const status = Vue.computed(() => window.store.status);
        const kingState = Vue.computed(() => window.store.kingState);
        const gpus = Vue.computed(() => window.store.sentinelState?.gpus || []);
        const modules = Vue.computed(() => window.store.modules);
        
        const t = (key, params = {}) => {
            return window.gettext ? window.gettext(key, params) : key;
        };
        
        const formatUptime = (seconds) => {
            if (window.formatters) {
                return window.formatters.formatUptime(seconds);
            }
            return seconds + 's';
        };
        
        const formatBytes = (bytes) => {
            if (window.formatters) {
                return window.formatters.formatBytes(bytes);
            }
            return bytes;
        };
        
        const formatStatus = (status) => {
            const translations = {
                'running': t('telemetry.status_running'),
                'ready': t('telemetry.status_ready'),
                'processing': t('telemetry.status_processing'),
                'idle': t('telemetry.status_idle'),
                'error': t('telemetry.status_error'),
                'stopped': t('telemetry.status_stopped')
            };
            return translations[status] || status;
        };
        
        const formatMood = (mood) => {
            const translations = {
                'lively': t('telemetry.mood_lively'),
                'calm': t('telemetry.mood_calm'),
                'thoughtful': t('telemetry.mood_thoughtful'),
                'tired': t('telemetry.mood_tired'),
                'neutral': t('telemetry.mood_neutral')
            };
            return translations[mood] || mood;
        };
        
        const formatModuleName = (name) => {
            return name
                .split('_')
                .map(word => word.charAt(0).toUpperCase() + word.slice(1))
                .join(' ');
        };
        
        const getTempClass = (temp) => {
            if (temp < 60) return 'temp-normal';
            if (temp < 80) return 'temp-warm';
            return 'temp-hot';
        };
        
        const getVramClass = (percent) => {
            if (percent < 70) return '';
            if (percent < 85) return 'warning';
            return 'critical';
        };
        
        // Rendszeres frissítés
        let interval = null;
        
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
            interval = setInterval(refreshData, 5000);
        });
        
        Vue.onUnmounted(() => {
            if (interval) {
                clearInterval(interval);
            }
        });
        
        return {
            systemId,
            uptime,
            status,
            kingState,
            gpus,
            modules,
            t,
            formatUptime,
            formatBytes,
            formatStatus,
            formatMood,
            formatModuleName,
            getTempClass,
            getVramClass
        };
    }
};

console.log('✅ TelemetryPanel komponens betöltve');