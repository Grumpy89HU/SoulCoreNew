// Modulvezérlő komponens
const ModuleControl = {
    template: `
        <div class="module-control">
            <ul class="module-list">
                <li v-for="(status, name) in moduleStatuses" :key="name" class="module-item">
                    <span class="module-name">
                        <span class="status-dot" :class="statusClass(status)"></span>
                        {{ name }}
                    </span>
                    
                    <span class="module-status" :class="statusClass(status)">
                        {{ status }}
                    </span>
                    
                    <div class="module-control-buttons" v-if="isAdmin">
                        <button class="control-btn" @click="controlModule(name, 'restart')" 
                                v-if="status != 'stopped'" title="Újraindítás">↻</button>
                        <button class="control-btn" @click="controlModule(name, 'start')" 
                                v-if="status == 'stopped'" title="Indítás">▶</button>
                        <button class="control-btn stop" @click="controlModule(name, 'stop')" 
                                v-if="status != 'stopped'" title="Leállítás">⏹</button>
                    </div>
                </li>
            </ul>
        </div>
    `,
    
    setup() {
        const moduleStatuses = Vue.computed(() => store.state.moduleStatuses);
        const isAdmin = Vue.computed(() => store.state.isAdmin);
        
        const statusClass = (status) => {
            return {
                'status-running': status == 'running' || status == 'ready' || status == 'watching',
                'status-warning': status == 'idle' || status == 'processing',
                'status-error': status == 'error' || status == 'stopped'
            };
        };
        
        const controlModule = (module, action) => {
            if (socketManager && socketManager.controlModule) {
                socketManager.controlModule(module, action);
            }
        };
        
        return {
            moduleStatuses,
            isAdmin,
            statusClass,
            controlModule
        };
    }
};

// Globális változóként elérhetővé tesszük
window.ModuleControl = ModuleControl;