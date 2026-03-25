<script>
  import { conversations, currentConversation, setCurrentConversation, loadConversations, newConversation } from '../lib/store.js';
  import { t } from '../lib/i18n.js';
  
  let isCreating = false;
  let newTitle = '';
  
  async function handleNewConversation() {
    if (isCreating) return;
    
    isCreating = true;
    const title = newTitle.trim() || `Conversation ${new Date().toLocaleString()}`;
    const conv = await newConversation(title);
    
    if (conv) {
      setCurrentConversation(conv);
    }
    
    newTitle = '';
    isCreating = false;
  }
  
  function selectConversation(conv) {
    setCurrentConversation(conv);
  }
</script>

<div class="conversation-list">
  <div class="list-header">
    <h3>{$t('chat.conversations')}</h3>
    <button class="new-btn" on:click={handleNewConversation} disabled={isCreating}>
      +
    </button>
  </div>
  
  {#if isCreating}
    <div class="new-conversation">
      <input
        type="text"
        bind:value={newTitle}
        placeholder={$t('chat.conversation_title')}
        on:keydown={(e) => e.key === 'Enter' && handleNewConversation()}
        autofocus
      />
    </div>
  {/if}
  
  <div class="conversations">
    {#each $conversations as conv (conv.id)}
      <div
        class="conversation-item"
        class:active={$currentConversation?.id === conv.id}
        on:click={() => selectConversation(conv)}
      >
        <span class="icon">💬</span>
        <span class="title">{conv.title || 'Untitled'}</span>
        <span class="date">{new Date(conv.created_at).toLocaleDateString()}</span>
      </div>
    {/each}
    
    {#if $conversations.length === 0}
      <div class="empty">
        <p>{$t('chat.no_conversations')}</p>
      </div>
    {/if}
  </div>
</div>

<style>
  .conversation-list {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  
  .list-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem;
    border-bottom: 1px solid var(--border);
  }
  
  .list-header h3 {
    margin: 0;
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--text-secondary);
  }
  
  .new-btn {
    background: none;
    border: none;
    font-size: 1.25rem;
    cursor: pointer;
    color: var(--primary);
    width: 1.75rem;
    height: 1.75rem;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 0.5rem;
    transition: background 0.2s;
  }
  
  .new-btn:hover:not(:disabled) {
    background: var(--bg-tertiary);
  }
  
  .new-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  
  .new-conversation {
    padding: 0.75rem 1rem;
    border-bottom: 1px solid var(--border);
  }
  
  .new-conversation input {
    width: 100%;
    padding: 0.5rem;
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-radius: 0.5rem;
    color: var(--text-primary);
  }
  
  .conversations {
    flex: 1;
    overflow-y: auto;
  }
  
  .conversation-item {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem 1rem;
    cursor: pointer;
    transition: background 0.2s;
    border-bottom: 1px solid var(--border);
  }
  
  .conversation-item:hover {
    background: var(--bg-tertiary);
  }
  
  .conversation-item.active {
    background: var(--bg-tertiary);
    border-left: 3px solid var(--primary);
  }
  
  .icon {
    font-size: 1rem;
  }
  
  .title {
    flex: 1;
    font-size: 0.875rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  
  .date {
    font-size: 0.75rem;
    color: var(--text-secondary);
  }
  
  .empty {
    padding: 2rem;
    text-align: center;
    color: var(--text-secondary);
    font-size: 0.875rem;
  }
</style>