<script>
  import { onMount, afterUpdate } from 'svelte';
  import { messages, isLoading, currentConversation, currentMessages } from '../lib/store.js';
  import { sendChatMessage } from '../lib/socket.js';
  import { t } from '../lib/i18n.js';
  
  let inputText = '';
  let messagesContainer;
  
  afterUpdate(() => {
    scrollToBottom();
  });
  
  function scrollToBottom() {
    if (messagesContainer) {
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
  }
  
  async function handleSend() {
    if (!inputText.trim()) return;
    if (!$currentConversation) return;
    
    const text = inputText.trim();
    const convId = $currentConversation.id;
    
    // Felhasználói üzenet hozzáadása
    messages.update(m => [...m, {
      id: Date.now(),
      role: 'user',
      content: text,
      conversation_id: convId,
      timestamp: Date.now()
    }]);
    
    inputText = '';
    isLoading.set(true);
    
    // Üzenet küldése WebSocket-en
    sendChatMessage(text, convId);
  }
  
  function handleKeydown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }
  
  function formatTime(timestamp) {
    return new Date(timestamp).toLocaleTimeString();
  }
</script>

<div class="chat-container">
  <div class="messages" bind:this={messagesContainer}>
    {#each $currentMessages as msg (msg.id)}
      <div class="message {msg.role}">
        <div class="avatar">
          {#if msg.role === 'user'}
            🧑
          {:else}
            👑
          {/if}
        </div>
        <div class="content">
          <div class="text">{msg.content}</div>
          <div class="timestamp">{formatTime(msg.timestamp)}</div>
        </div>
      </div>
    {/each}
    
    {#if $isLoading}
      <div class="message assistant loading">
        <div class="avatar">👑</div>
        <div class="content">
          <div class="typing-indicator">
            <span></span><span></span><span></span>
          </div>
        </div>
      </div>
    {/if}
  </div>
  
  <div class="input-area">
    <textarea
      bind:value={inputText}
      on:keydown={handleKeydown}
      placeholder={$t('chat.placeholder')}
      disabled={$isLoading || !$currentConversation}
      rows="3"
    ></textarea>
    <button
      on:click={handleSend}
      disabled={$isLoading || !$currentConversation || !inputText.trim()}
    >
      {$t('chat.send')}
    </button>
  </div>
</div>

<style>
  .chat-container {
    display: flex;
    flex-direction: column;
    height: 100%;
    background: var(--bg-primary);
  }
  
  .messages {
    flex: 1;
    overflow-y: auto;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }
  
  .message {
    display: flex;
    gap: 0.75rem;
    max-width: 80%;
  }
  
  .message.user {
    align-self: flex-end;
    flex-direction: row-reverse;
  }
  
  .message.user .content {
    background: var(--primary);
    color: white;
    border-radius: 1rem 0.5rem 1rem 1rem;
  }
  
  .message.assistant .content {
    background: var(--bg-secondary);
    border-radius: 0.5rem 1rem 1rem 1rem;
  }
  
  .avatar {
    width: 2rem;
    height: 2rem;
    background: var(--bg-tertiary);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.25rem;
    flex-shrink: 0;
  }
  
  .content {
    padding: 0.75rem 1rem;
    max-width: 100%;
  }
  
  .text {
    white-space: pre-wrap;
    word-break: break-word;
  }
  
  .timestamp {
    font-size: 0.625rem;
    color: var(--text-secondary);
    margin-top: 0.25rem;
  }
  
  .typing-indicator {
    display: flex;
    gap: 0.25rem;
    padding: 0.25rem;
  }
  
  .typing-indicator span {
    width: 0.5rem;
    height: 0.5rem;
    background: var(--text-secondary);
    border-radius: 50%;
    animation: bounce 1.4s infinite ease-in-out;
  }
  
  .typing-indicator span:nth-child(1) { animation-delay: 0s; }
  .typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
  .typing-indicator span:nth-child(3) { animation-delay: 0.4s; }
  
  @keyframes bounce {
    0%, 60%, 100% { transform: translateY(0); }
    30% { transform: translateY(-0.5rem); }
  }
  
  .input-area {
    padding: 1rem;
    border-top: 1px solid var(--border);
    display: flex;
    gap: 0.75rem;
    align-items: flex-end;
  }
  
  textarea {
    flex: 1;
    padding: 0.75rem;
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 0.75rem;
    color: var(--text-primary);
    font-family: inherit;
    resize: none;
    font-size: 0.875rem;
  }
  
  textarea:focus {
    outline: none;
    border-color: var(--primary);
  }
  
  button {
    padding: 0.75rem 1.5rem;
    background: var(--primary);
    border: none;
    border-radius: 0.75rem;
    color: white;
    font-weight: 600;
    cursor: pointer;
    transition: opacity 0.2s;
  }
  
  button:hover:not(:disabled) {
    opacity: 0.9;
  }
  
  button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  
  @media (max-width: 768px) {
    .message {
      max-width: 90%;
    }
  }
</style>