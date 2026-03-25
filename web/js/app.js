// SoulCore Web UI - Egyszerűsített verzió (csak chat)

const API_URL = 'http://10.6.14.35:5001';
const WS_URL = 'ws://10.6.14.35:5002';

let socket = null;
let messages = [];
let isLoading = false;
let conversationId = 1;  // Fix conversation ID

// DOM elemek
const statusEl = document.getElementById('status');
const messagesEl = document.getElementById('messages');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const newChatBtn = document.getElementById('newChatBtn');

// WebSocket kapcsolat
function connectWebSocket() {
    socket = new WebSocket(WS_URL);
    
    socket.onopen = () => {
        console.log('WebSocket connected');
        statusEl.textContent = 'Connected';
        statusEl.className = 'status connected';
    };
    
    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
    };
    
    socket.onclose = () => {
        console.log('WebSocket disconnected');
        statusEl.textContent = 'Disconnected';
        statusEl.className = 'status disconnected';
        setTimeout(connectWebSocket, 3000);
    };
    
    socket.onerror = (error) => {
        console.error('WebSocket error:', error);
    };
}

function handleWebSocketMessage(data) {
    switch (data.type) {
        case 'chat:response':
            messages.push({
                id: Date.now(),
                role: 'assistant',
                content: data.text,
                timestamp: data.timestamp || Date.now()
            });
            isLoading = false;
            renderMessages();
            break;
    }
}

// Üzenet küldése
async function sendMessage(text) {
    // Add user message
    messages.push({
        id: Date.now(),
        role: 'user',
        content: text,
        timestamp: Date.now()
    });
    renderMessages();
    
    isLoading = true;
    renderMessages();
    
    // Try WebSocket first
    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({
            type: 'chat:message',
            text: text,
            conversation_id: conversationId
        }));
    } else {
        // Fallback to HTTP
        try {
            const response = await fetch(`${API_URL}/api/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text, conversation_id: conversationId })
            });
            const data = await response.json();
            messages.push({
                id: Date.now(),
                role: 'assistant',
                content: data.response,
                timestamp: Date.now()
            });
            isLoading = false;
            renderMessages();
        } catch (e) {
            console.error('Failed to send message:', e);
            messages.push({
                id: Date.now(),
                role: 'assistant',
                content: 'Error: Could not send message. Check if SoulCore API is running.',
                timestamp: Date.now()
            });
            isLoading = false;
            renderMessages();
        }
    }
}

// UI renderelés
function renderMessages() {
    if (!messagesEl) return;
    
    messagesEl.innerHTML = messages.map(msg => `
        <div class="message ${msg.role}">
            <div class="avatar">${msg.role === 'user' ? '🧑' : '👑'}</div>
            <div class="content">
                <div class="text">${escapeHtml(msg.content)}</div>
                <div class="timestamp">${new Date(msg.timestamp).toLocaleTimeString()}</div>
            </div>
        </div>
    `).join('');
    
    if (isLoading) {
        messagesEl.innerHTML += `
            <div class="message assistant loading">
                <div class="avatar">👑</div>
                <div class="content">
                    <div class="typing-indicator">
                        <span></span><span></span><span></span>
                    </div>
                </div>
            </div>
        `;
    }
    
    // Scroll to bottom
    messagesEl.scrollTop = messagesEl.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Eseménykezelők
function handleSend() {
    const text = messageInput.value.trim();
    if (!text) return;
    if (isLoading) return;
    
    messageInput.value = '';
    sendMessage(text);
}

function handleKeydown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
    }
}

function newConversation() {
    conversationId = Date.now();
    messages = [];
    renderMessages();
    alert(`New conversation created (ID: ${conversationId})`);
}

// Inicializálás
function init() {
    connectWebSocket();
    
    // Üdvözlő üzenet
    messages.push({
        id: Date.now(),
        role: 'assistant',
        content: 'Hello! I am Kópé, your sovereign AI assistant. How can I help you today?',
        timestamp: Date.now()
    });
    renderMessages();
    
    sendBtn.addEventListener('click', handleSend);
    messageInput.addEventListener('keydown', handleKeydown);
    if (newChatBtn) {
        newChatBtn.addEventListener('click', newConversation);
    }
}

// Indítás
init();
