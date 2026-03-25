<script>
  import { onMount } from 'svelte';
  import { initSocket, disconnectSocket } from './lib/socket.js';
  import { messages, isLoading, currentConversation, loadConversations } from './lib/store.js';
  import ChatBox from './components/ChatBox.svelte';
  import ConversationList from './components/ConversationList.svelte';
  import TelemetryPanel from './components/TelemetryPanel.svelte';
  import { t, setLanguage } from './lib/i18n.js';
  
  let sidebarOpen = true;
  let activeTab = 'chat';
  
  onMount(async () => {
    // WebSocket kapcsolat indítása
    initSocket();
    
    // Beszélgetések betöltése
    await loadConversations();
    
    // Alapértelmezett beszélgetés
    if ($messages.length === 0) {
      currentConversation.set(null);
    }
  });
  
  function toggleSidebar() {
    sidebarOpen = !sidebarOpen;
  }
  
  function handleTabChange(tab) {
    activeTab = tab;
  }
</script>

<div class="app">
  <div class="sidebar" class:closed={!sidebarOpen}>
    <div class="sidebar-header">
      <h1>🏰 SoulCore</h1>
      <button class="close-sidebar" on:click={toggleSidebar}>✕</button>
    </div>
    
    <div class="sidebar-tabs">
      <button class="tab" class:active={activeTab === 'chat'} on:click={() => handleTabChange('chat')}>
        💬 {t('nav.chat')}
      </button>
      <button class="tab" class:active={activeTab === 'admin'} on:click={() => handleTabChange('admin')}>
        ⚙️ {t('nav.admin')}
      </button>
    </div>
    
    {#if activeTab === 'chat'}
      <ConversationList />
    {:else if activeTab === 'admin'}
      <div class="admin-placeholder">
        <p>Admin panel (komponens betöltése...)</p>
      </div>
    {/if}
  </div>
  
  <div class="main" class:sidebar-closed={!sidebarOpen}>
    <button class="open-sidebar" on:click={toggleSidebar} class:visible={!sidebarOpen}>
      ☰
    </button>
    
    {#if activeTab === 'chat'}
      <ChatBox />
    {:else if activeTab === 'admin'}
      <div class="admin-panel">
        <h2>{t('admin.dashboard')}</h2>
        <TelemetryPanel />
      </div>
    {/if}
  </div>
</div>

<style>
  .app {
    display: flex;
    height: 100vh;
    overflow: hidden;
  }
  
  .sidebar {
    width: 280px;
    background: var(--bg-secondary);
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    transition: transform 0.3s ease;
    flex-shrink: 0;
  }
  
  .sidebar.closed {
    transform: translateX(-100%);
  }
  
  .sidebar-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem;
    border-bottom: 1px solid var(--border);
  }
  
  .sidebar-header h1 {
    font-size: 1.25rem;
    margin: 0;
    color: var(--primary);
  }
  
  .close-sidebar {
    background: none;
    border: none;
    font-size: 1.25rem;
    cursor: pointer;
    color: var(--text-secondary);
  }
  
  .sidebar-tabs {
    display: flex;
    border-bottom: 1px solid var(--border);
  }
  
  .tab {
    flex: 1;
    padding: 0.75rem;
    background: none;
    border: none;
    cursor: pointer;
    color: var(--text-secondary);
    font-size: 0.875rem;
  }
  
  .tab.active {
    color: var(--primary);
    border-bottom: 2px solid var(--primary);
  }
  
  .main {
    flex: 1;
    display: flex;
    flex-direction: column;
    position: relative;
  }
  
  .open-sidebar {
    position: absolute;
    top: 1rem;
    left: 1rem;
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 0.5rem;
    padding: 0.5rem;
    cursor: pointer;
    display: none;
    z-index: 10;
  }
  
  .open-sidebar.visible {
    display: block;
  }
  
  .admin-panel {
    padding: 1.5rem;
    overflow-y: auto;
    flex: 1;
  }
  
  .admin-panel h2 {
    margin-bottom: 1.5rem;
    color: var(--primary);
  }
  
  @media (max-width: 768px) {
    .sidebar {
      position: fixed;
      top: 0;
      left: 0;
      height: 100vh;
      z-index: 100;
      background: var(--bg-primary);
    }
  }
</style>