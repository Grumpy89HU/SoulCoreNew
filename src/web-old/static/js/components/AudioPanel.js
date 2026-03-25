// ==============================================
// SOULCORE 3.0 - Hang (ASR/TTS) panel
// ==============================================

window.AudioPanel = {
    name: 'AudioPanel',
    
    template: `
        <div class="audio-panel">
            <div class="audio-header">
                <h3>{{ t('audio.title') }}</h3>
                <p>{{ t('audio.description') }}</p>
            </div>
            
            <!-- Fülek -->
            <div class="audio-tabs">
                <button class="tab-btn" :class="{ active: activeTab === 'asr' }" @click="activeTab = 'asr'">
                    🎤 {{ t('audio.asr') }}
                </button>
                <button class="tab-btn" :class="{ active: activeTab === 'tts' }" @click="activeTab = 'tts'">
                    🔊 {{ t('audio.tts') }}
                </button>
            </div>
            
            <!-- ASR (Speech-to-Text) -->
            <div v-show="activeTab === 'asr'" class="asr-section">
                <div class="settings-section">
                    <h4>{{ t('audio.asr_settings') }}</h4>
                    <div class="setting-item">
                        <label>{{ t('audio.asr_engine') }}</label>
                        <select v-model="asrSettings.engine" @change="saveAsrSettings">
                            <option value="whisper">Whisper (local)</option>
                            <option value="whisper-cpp">Whisper.cpp</option>
                            <option value="openai">OpenAI Whisper</option>
                            <option value="deepgram">Deepgram</option>
                            <option value="azure">Azure Speech</option>
                        </select>
                    </div>
                    
                    <div class="setting-item" v-if="asrSettings.engine === 'whisper'">
                        <label>{{ t('audio.model_size') }}</label>
                        <select v-model="asrSettings.whisper_model" @change="saveAsrSettings">
                            <option value="tiny">Tiny</option>
                            <option value="base">Base</option>
                            <option value="small">Small</option>
                            <option value="medium">Medium</option>
                            <option value="large">Large</option>
                        </select>
                    </div>
                    
                    <div class="setting-item" v-if="asrSettings.engine === 'openai'">
                        <label>{{ t('audio.api_key') }}</label>
                        <input type="password" v-model="asrSettings.openai_key" @change="saveAsrSettings">
                    </div>
                    
                    <div class="setting-item">
                        <label>{{ t('audio.language') }}</label>
                        <select v-model="asrSettings.language" @change="saveAsrSettings">
                            <option value="auto">Auto-detect</option>
                            <option value="hu">Magyar</option>
                            <option value="en">English</option>
                            <option value="de">Deutsch</option>
                            <option value="fr">Français</option>
                        </select>
                    </div>
                </div>
                
                <!-- Felvétel és fájl feltöltés -->
                <div class="recording-section">
                    <button class="record-btn" :class="{ recording: isRecording }" @click="toggleRecording">
                        {{ isRecording ? '⏹️ ' + t('audio.stop') : '🎤 ' + t('audio.start_recording') }}
                    </button>
                    <div class="recording-timer" v-if="isRecording">{{ recordingTime }}s</div>
                    <div class="upload-area" @click="triggerAudioFile">
                        <span>📁 {{ t('audio.upload_file') }}</span>
                        <input type="file" ref="audioFileInput" accept="audio/*" style="display:none" @change="handleAudioFile">
                    </div>
                </div>
                
                <!-- Felismerési eredmény -->
                <div class="transcription-result" v-if="transcription">
                    <div class="result-header">{{ t('audio.transcription') }}</div>
                    <div class="result-text">{{ transcription }}</div>
                    <button class="btn-secondary" @click="insertTranscription">
                        💬 {{ t('audio.insert_to_chat') }}
                    </button>
                </div>
            </div>
            
            <!-- TTS (Text-to-Speech) -->
            <div v-show="activeTab === 'tts'" class="tts-section">
                <div class="settings-section">
                    <h4>{{ t('audio.tts_settings') }}</h4>
                    <div class="setting-item">
                        <label>{{ t('audio.tts_engine') }}</label>
                        <select v-model="ttsSettings.engine" @change="saveTtsSettings">
                            <option value="coqui">Coqui TTS (local)</option>
                            <option value="piper">Piper TTS</option>
                            <option value="openai">OpenAI TTS</option>
                            <option value="elevenlabs">ElevenLabs</option>
                            <option value="azure">Azure Speech</option>
                        </select>
                    </div>
                    
                    <div class="setting-item" v-if="ttsSettings.engine === 'coqui'">
                        <label>{{ t('audio.model') }}</label>
                        <select v-model="ttsSettings.coqui_model" @change="saveTtsSettings">
                            <option value="tts_models/hu/cess_cat">Hungarian (CESS_CAT)</option>
                            <option value="tts_models/en/ljspeech/tacotron2-DDC">English (Tacotron2)</option>
                            <option value="tts_models/de/thorsten/tacotron2-DDC">German (Thorsten)</option>
                        </select>
                    </div>
                    
                    <div class="setting-item" v-if="ttsSettings.engine === 'openai'">
                        <label>{{ t('audio.api_key') }}</label>
                        <input type="password" v-model="ttsSettings.openai_key" @change="saveTtsSettings">
                        <label>{{ t('audio.voice') }}</label>
                        <select v-model="ttsSettings.openai_voice" @change="saveTtsSettings">
                            <option value="alloy">Alloy</option>
                            <option value="echo">Echo</option>
                            <option value="fable">Fable</option>
                            <option value="onyx">Onyx</option>
                            <option value="nova">Nova</option>
                            <option value="shimmer">Shimmer</option>
                        </select>
                    </div>
                    
                    <div class="setting-item">
                        <label>{{ t('audio.voice_name') }}</label>
                        <select v-model="ttsSettings.voice" @change="saveTtsSettings">
                            <option value="default">Default</option>
                            <option value="male">Male</option>
                            <option value="female">Female</option>
                        </select>
                    </div>
                    
                    <div class="setting-item">
                        <label>{{ t('audio.speed') }}</label>
                        <input type="range" v-model="ttsSettings.speed" min="0.5" max="2.0" step="0.1" @change="saveTtsSettings">
                        <span>{{ ttsSettings.speed }}x</span>
                    </div>
                </div>
                
                <!-- Szöveg bevitel -->
                <div class="tts-input">
                    <textarea v-model="ttsText" :placeholder="t('audio.tts_placeholder')" rows="4"></textarea>
                    <button class="btn-primary" @click="speakText" :disabled="speaking">
                        <span v-if="!speaking">🔊 {{ t('audio.speak') }}</span>
                        <span v-else class="spinner-small"></span>
                    </button>
                </div>
                
                <!-- Hang export -->
                <div class="audio-player" v-if="audioUrl">
                    <audio controls :src="audioUrl"></audio>
                    <button class="btn-secondary" @click="downloadAudio">📥 {{ t('audio.download') }}</button>
                </div>
            </div>
        </div>
    `,
    
    setup() {
        const activeTab = Vue.ref('asr');
        
        // ASR beállítások
        const asrSettings = Vue.ref({
            engine: 'whisper',
            whisper_model: 'base',
            openai_key: '',
            language: 'auto'
        });
        
        // TTS beállítások
        const ttsSettings = Vue.ref({
            engine: 'coqui',
            coqui_model: 'tts_models/hu/cess_cat',
            openai_key: '',
            openai_voice: 'nova',
            voice: 'default',
            speed: 1.0
        });
        
        // ASR állapotok
        const isRecording = Vue.ref(false);
        const recordingTime = Vue.ref(0);
        const transcription = Vue.ref('');
        const mediaRecorder = Vue.ref(null);
        const audioChunks = Vue.ref([]);
        let recordingInterval = null;
        
        // TTS állapotok
        const ttsText = Vue.ref('');
        const speaking = Vue.ref(false);
        const audioUrl = Vue.ref('');
        
        // Refs
        const audioFileInput = Vue.ref(null);
        
        const t = (key, params = {}) => window.gettext(key, params);
        
        const loadAsrSettings = async () => {
            try {
                const saved = await window.api.getSettings('asr');
                if (saved) asrSettings.value = { ...asrSettings.value, ...saved };
            } catch (error) {
                console.error('Error loading ASR settings:', error);
            }
        };
        
        const loadTtsSettings = async () => {
            try {
                const saved = await window.api.getSettings('tts');
                if (saved) ttsSettings.value = { ...ttsSettings.value, ...saved };
            } catch (error) {
                console.error('Error loading TTS settings:', error);
            }
        };
        
        const saveAsrSettings = async () => {
            try {
                await window.api.updateSettings('asr', asrSettings.value);
                window.store.addNotification('success', t('audio.settings_saved'));
            } catch (error) {
                console.error('Error saving ASR settings:', error);
            }
        };
        
        const saveTtsSettings = async () => {
            try {
                await window.api.updateSettings('tts', ttsSettings.value);
                window.store.addNotification('success', t('audio.settings_saved'));
            } catch (error) {
                console.error('Error saving TTS settings:', error);
            }
        };
        
        // ASR - Felvétel
        const toggleRecording = async () => {
            if (isRecording.value) {
                stopRecording();
            } else {
                await startRecording();
            }
        };
        
        const startRecording = async () => {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder.value = new MediaRecorder(stream);
                audioChunks.value = [];
                
                mediaRecorder.value.ondataavailable = (event) => {
                    audioChunks.value.push(event.data);
                };
                
                mediaRecorder.value.onstop = async () => {
                    const audioBlob = new Blob(audioChunks.value, { type: 'audio/webm' });
                    await transcribeAudio(audioBlob);
                    stream.getTracks().forEach(track => track.stop());
                };
                
                mediaRecorder.value.start();
                isRecording.value = true;
                recordingTime.value = 0;
                
                recordingInterval = setInterval(() => {
                    recordingTime.value++;
                }, 1000);
            } catch (error) {
                console.error('Error starting recording:', error);
                window.store.addNotification('error', t('audio.mic_error'));
            }
        };
        
        const stopRecording = () => {
            if (mediaRecorder.value && isRecording.value) {
                mediaRecorder.value.stop();
                isRecording.value = false;
                if (recordingInterval) {
                    clearInterval(recordingInterval);
                    recordingInterval = null;
                }
            }
        };
        
        const transcribeAudio = async (audioBlob) => {
            try {
                const result = await window.api.transcribeAudio(audioBlob, asrSettings.value);
                transcription.value = result.text;
                window.store.addNotification('success', t('audio.transcription_complete'));
            } catch (error) {
                console.error('Error transcribing audio:', error);
                window.store.addNotification('error', t('audio.transcription_error'));
            }
        };
        
        const triggerAudioFile = () => {
            audioFileInput.value?.click();
        };
        
        const handleAudioFile = async (event) => {
            const file = event.target.files[0];
            if (!file) return;
            
            try {
                const result = await window.api.transcribeAudio(file, asrSettings.value);
                transcription.value = result.text;
                window.store.addNotification('success', t('audio.transcription_complete'));
            } catch (error) {
                console.error('Error transcribing file:', error);
                window.store.addNotification('error', t('audio.transcription_error'));
            }
            event.target.value = '';
        };
        
        const insertTranscription = () => {
            if (!transcription.value) return;
            const chatBox = document.querySelector('.chat-input');
            if (chatBox) {
                chatBox.value = (chatBox.value ? chatBox.value + '\n\n' : '') + transcription.value;
                chatBox.dispatchEvent(new Event('input'));
                chatBox.focus();
                transcription.value = '';
            }
        };
        
        // TTS
        const speakText = async () => {
            if (!ttsText.value.trim()) {
                window.store.addNotification('warning', t('audio.tts_text_required'));
                return;
            }
            
            speaking.value = true;
            
            try {
                const audioBlob = await window.api.synthesizeSpeech(ttsText.value, ttsSettings.value);
                const url = URL.createObjectURL(audioBlob);
                if (audioUrl.value) URL.revokeObjectURL(audioUrl.value);
                audioUrl.value = url;
                
                const audio = new Audio(url);
                audio.onended = () => {
                    speaking.value = false;
                };
                audio.play();
                
                window.store.addNotification('success', t('audio.speech_playing'));
            } catch (error) {
                console.error('Error synthesizing speech:', error);
                window.store.addNotification('error', t('audio.speech_error'));
                speaking.value = false;
            }
        };
        
        const downloadAudio = () => {
            if (!audioUrl.value) return;
            const a = document.createElement('a');
            a.href = audioUrl.value;
            a.download = `speech_${Date.now()}.mp3`;
            a.click();
        };
        
        Vue.onMounted(() => {
            loadAsrSettings();
            loadTtsSettings();
        });
        
        Vue.onUnmounted(() => {
            if (recordingInterval) clearInterval(recordingInterval);
            if (audioUrl.value) URL.revokeObjectURL(audioUrl.value);
        });
        
        return {
            activeTab,
            asrSettings,
            ttsSettings,
            isRecording,
            recordingTime,
            transcription,
            ttsText,
            speaking,
            audioUrl,
            audioFileInput,
            t,
            saveAsrSettings,
            saveTtsSettings,
            toggleRecording,
            triggerAudioFile,
            handleAudioFile,
            insertTranscription,
            speakText,
            downloadAudio
        };
    }
};

console.log('✅ AudioPanel komponens betöltve');