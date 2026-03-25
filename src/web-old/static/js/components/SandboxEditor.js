// ==============================================
// SOULCORE 3.0 - Sandbox kódfuttató
// ==============================================

window.SandboxEditor = {
    name: 'SandboxEditor',
    
    template: `
        <div class="sandbox-panel">
            <div class="sandbox-header">
                <h3>{{ t('sandbox.title') }}</h3>
                <p>{{ t('sandbox.description') }}</p>
            </div>
            
            <!-- Kód szerkesztő -->
            <div class="editor-container">
                <div class="editor-toolbar">
                    <select v-model="language" class="language-select">
                        <option value="python">Python</option>
                        <option value="javascript">JavaScript</option>
                        <option value="bash">Bash</option>
                    </select>
                    <button class="btn-primary" @click="runCode" :disabled="running">
                        <span v-if="!running">▶️ {{ t('sandbox.run') }}</span>
                        <span v-else class="spinner-small"></span>
                    </button>
                    <button class="btn-secondary" @click="clearCode">
                        🗑️ {{ t('sandbox.clear') }}
                    </button>
                    <button class="btn-secondary" @click="loadExample">
                        📋 {{ t('sandbox.load_example') }}
                    </button>
                </div>
                
                <textarea 
                    v-model="code" 
                    class="code-editor"
                    :placeholder="t('sandbox.code_placeholder')"
                    rows="12"
                ></textarea>
            </div>
            
            <!-- Kimenet -->
            <div class="output-container">
                <div class="output-header">
                    <h4>{{ t('sandbox.output') }}</h4>
                    <button class="clear-output-btn" @click="clearOutput">✕</button>
                </div>
                <div class="output-content" :class="{ 'has-error': outputError }">
                    <pre>{{ output || t('sandbox.no_output') }}</pre>
                </div>
                <div class="output-stats" v-if="executionTime">
                    <span>⏱️ {{ t('sandbox.execution_time') }}: {{ executionTime }}ms</span>
                    <span v-if="memoryUsed">💾 {{ t('sandbox.memory_used') }}: {{ memoryUsed }} MB</span>
                </div>
            </div>
            
            <!-- Beállítások -->
            <div class="sandbox-settings">
                <details>
                    <summary>{{ t('sandbox.settings') }}</summary>
                    <div class="setting-item">
                        <label>{{ t('sandbox.timeout') }}</label>
                        <input type="number" v-model="settings.timeout" min="1" max="60">
                        <span>{{ t('sandbox.seconds') }}</span>
                    </div>
                    <div class="setting-item">
                        <label>{{ t('sandbox.memory_limit') }}</label>
                        <input type="number" v-model="settings.memory_limit" min="64" max="2048">
                        <span>MB</span>
                    </div>
                    <div class="setting-item">
                        <label>{{ t('sandbox.network_access') }}</label>
                        <input type="checkbox" v-model="settings.network_access">
                    </div>
                </details>
            </div>
        </div>
    `,
    
    setup() {
        const code = Vue.ref('');
        const language = Vue.ref('python');
        const output = Vue.ref('');
        const outputError = Vue.ref(false);
        const running = Vue.ref(false);
        const executionTime = Vue.ref(null);
        const memoryUsed = Vue.ref(null);
        
        const settings = Vue.ref({
            timeout: 30,
            memory_limit: 512,
            network_access: false
        });
        
        const t = (key, params = {}) => window.gettext(key, params);
        
        const examples = {
            python: `# Egyszerű Python példa
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

print("Fibonacci(10) =", fibonacci(10))

# List comprehension
squares = [x**2 for x in range(10)]
print("Négyzetek:", squares)

# Szótár
data = {"name": "SoulCore", "version": "3.0"}
print("Adatok:", data)`,
            
            javascript: `// Egyszerű JavaScript példa
function fibonacci(n) {
    if (n <= 1) return n;
    return fibonacci(n-1) + fibonacci(n-2);
}

console.log("Fibonacci(10) =", fibonacci(10));

// Tömb műveletek
const squares = Array.from({length: 10}, (_, i) => i ** 2);
console.log("Négyzetek:", squares);

// Objektum
const data = { name: "SoulCore", version: "3.0" };
console.log("Adatok:", data);`,
            
            bash: `#!/bin/bash
# Egyszerű Bash példa

echo "Rendszer információk:"
echo "---------------------"
echo "Jelenlegi könyvtár: $(pwd)"
echo "Felhasználó: $(whoami)"
echo "Dátum: $(date)"

echo ""
echo "Fájlok listája:"
ls -la | head -5`
        };
        
        const loadExample = () => {
            code.value = examples[language.value] || examples.python;
        };
        
        const runCode = async () => {
            if (!code.value.trim()) {
                window.store.addNotification('warning', t('sandbox.no_code'));
                return;
            }
            
            running.value = true;
            output.value = '';
            outputError.value = false;
            executionTime.value = null;
            memoryUsed.value = null;
            
            const startTime = performance.now();
            
            try {
                const result = await window.api.executeCode(code.value, {
                    language: language.value,
                    timeout: settings.value.timeout,
                    memory_limit: settings.value.memory_limit,
                    network_access: settings.value.network_access
                });
                
                output.value = result.output || result.result || t('sandbox.no_output');
                if (result.error) {
                    outputError.value = true;
                    output.value = result.error;
                }
                executionTime.value = Math.round(performance.now() - startTime);
                memoryUsed.value = result.memory_used;
                
                window.store.addNotification('success', t('sandbox.execution_success'));
            } catch (error) {
                console.error('Error executing code:', error);
                output.value = error.message || t('sandbox.execution_error');
                outputError.value = true;
            } finally {
                running.value = false;
            }
        };
        
        const clearCode = () => {
            code.value = '';
        };
        
        const clearOutput = () => {
            output.value = '';
            outputError.value = false;
            executionTime.value = null;
            memoryUsed.value = null;
        };
        
        Vue.onMounted(() => {
            loadExample();
        });
        
        return {
            code,
            language,
            output,
            outputError,
            running,
            executionTime,
            memoryUsed,
            settings,
            t,
            loadExample,
            runCode,
            clearCode,
            clearOutput
        };
    }
};

console.log('✅ SandboxEditor komponens betöltve');