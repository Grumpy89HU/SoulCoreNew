<script>
  import TelemetryPanel from '../../components/TelemetryPanel.svelte';
  import { t } from '../../lib/i18n.js';
</script>

<div class="admin-page">
  <h1>{$t('admin.dashboard')}</h1>
  
  <section>
    <h2>{$t('admin.metrics')}</h2>
    <TelemetryPanel />
  </section>
  
  <section>
    <h2>{$t('admin.modules')}</h2>
    <div class="modules-grid">
      <div class="module-card">
        <h3>King</h3>
        <span class="status status-running">running</span>
      </div>
      <div class="module-card">
        <h3>Queen</h3>
        <span class="status status-stopped">stopped</span>
      </div>
      <div class="module-card">
        <h3>Valet</h3>
        <span class="status status-running">running</span>
      </div>
      <div class="module-card">
        <h3>Jester</h3>
        <span class="status status-running">running</span>
      </div>
    </div>
  </section>
</div>

<style>
  .admin-page {
    padding: 1.5rem;
    max-width: 1200px;
    margin: 0 auto;
  }
  
  h1 {
    margin-bottom: 1.5rem;
    color: var(--primary);
  }
  
  section {
    margin-bottom: 2rem;
  }
  
  section h2 {
    margin-bottom: 1rem;
    font-size: 1.25rem;
  }
  
  .modules-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 1rem;
  }
  
  .module-card {
    background: var(--bg-secondary);
    padding: 1rem;
    border-radius: 0.5rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  
  .module-card h3 {
    font-size: 1rem;
  }
  
  .status {
    font-size: 0.75rem;
    padding: 0.25rem 0.5rem;
    border-radius: 0.25rem;
  }
  
  .status-running {
    background: var(--success);
    color: #000;
  }
  
  .status-stopped {
    background: var(--danger);
    color: #fff;
  }
</style>