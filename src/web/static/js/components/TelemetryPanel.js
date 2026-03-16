// Telemetria panel
window.TelemetryPanel = {
    template: `
        <div class="telemetry-container">
            <div class="panel-header">
                <span>🔍 TELEMETRIA</span>
            </div>
            
            <div class="panel-content">
                <div class="metric">
                    <div class="metric-label">ÜZEMIDŐ</div>
                    <div class="metric-value">{{ formatUptime(heartbeat.uptime_seconds) }}</div>
                </div>
                
                <div class="metric">
                    <div class="metric-label">INAKTIVITÁS</div>
                    <div class="metric-value">{{ formatUptime(heartbeat.idle_seconds) }}</div>
                </div>
                
                <div class="metric">
                    <div class="metric-label">SZÍVDOBBANÁS</div>
                    <div class="metric-value">{{ heartbeat.beats || 0 }} <span class="metric-unit">dobbanás</span></div>
                </div>
                
                <div class="metric">
                    <div class="metric-label">PROAKTÍV GONDOLATOK</div>
                    <div class="metric-value">{{ heartbeat.proactive_count || 0 }}</div>
                </div>
                
                <div class="metric">
                    <div class="metric-label">GPU HŐMÉRSÉKLET</div>
                    <div v-for="(gpu, index) in gpuStatus" :key="index" 
                         class="metric-value" 
                         :class="'temp-' + gpu.tempLevel">
                        GPU{{ index }}: {{ gpu.temperature }}°C 
                        <span class="metric-unit">({{ gpu.vram_percent }}% VRAM)</span>
                    </div>
                </div>
                
                <div class="metric">
                    <div class="metric-label">MEMÓRIA HASZNÁLAT</div>
                    <div class="progress-bar">
                        <div class="progress-fill" :style="{ width: memoryPercent + '%' }"></div>
                    </div>
                </div>
                
                <div class="metric">
                    <div class="metric-label">KING ÁLLAPOT</div>
                    <div class="metric-value" :class="kingStatusClass">
                        {{ kingState.status || '???' }}
                    </div>
                </div>
            </div>
        </div>
    `,
    
    setup() {
        const heartbeat = Vue.computed(() => window.store.heartbeat);
        const kingState = Vue.computed(() => window.store.kingState);
        const gpuStatus = Vue.computed(() => window.store.gpuStatus);
        const memoryPercent = Vue.ref(0);
        
        const kingStatusClass = Vue.computed(() => ({
            'temp-normal': kingState.value.status == 'ready',
            'temp-warm': kingState.value.status == 'processing',
            'temp-hot': kingState.value.status == 'error'
        }));
        
        const formatUptime = (seconds) => {
            return window.store.formatUptime(seconds);
        };
        
        // Memória szimuláció (később valós adat)
        Vue.watch(() => window.store.messages.length, (newVal) => {
            memoryPercent.value = Math.min(100, (newVal / 200) * 100);
        });
        
        return {
            heartbeat,
            kingState,
            gpuStatus,
            memoryPercent,
            kingStatusClass,
            formatUptime
        };
    }
};
window.TelemetryPanel = TelemetryPanel;
console.log('✅ Telemetria panel betöltve globálisan');