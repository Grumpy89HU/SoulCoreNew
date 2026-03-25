<script>
  import { onMount, onDestroy } from 'svelte';
  import { telemetry } from '../lib/store.js';
  import { t } from '../lib/i18n.js';
  
  let interval;
  
  onMount(() => {
    interval = setInterval(() => {
      // Telemetria frissítés (WebSocket már hozza)
    }, 2000);
  });
  
  onDestroy(() => {
    if (interval) clearInterval(interval);
  });
  
  function formatBytes(bytes) {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }
</script>

<div class="telemetry-panel">
  <div class="metrics-grid">
    <div class="metric-card">
      <span class="label">GPU Temperature</span>
      <span class="value" class:warning={$telemetry.gpu?.[0]?.temperature > 80}>
        {$telemetry.gpu?.[0]?.temperature || 0}°C
      </span>
    </div>
    <div class="metric-card">
      <span class="label">VRAM Usage</span>
      <span class="value">
        {formatBytes($telemetry.gpu?.[0]?.vram_used || 0)} / 
        {formatBytes($telemetry.gpu?.[0]?.vram_total || 0)}
      </span>
    </div>
    <div class="metric-card">
      <span class="label">Response Time</span>
      <span class="value">{$telemetry.king?.average_response_time || 0}ms</span>
    </div>
    <div class="metric-card">
      <span class="label">King Mood</span>
      <span class="value mood-{$telemetry.king?.last_mood}">
        {$telemetry.king?.last_mood || 'neutral'}
      </span>
    </div>
    <div class="metric-card">
      <span class="label">Uptime</span>
      <span class="value">{$telemetry.uptime_formatted || '0s'}</span>
    </div>
    <div class="metric-card">
      <span class="label">Messages</span>
      <span class="value">{$telemetry.king?.response_count || 0}</span>
    </div>
  </div>
  
  {#if $telemetry.gpu}
    <div class="gpu-chart">
      {#each $telemetry.gpu as gpu}
        <div class="gpu-bar" style="width: {gpu.utilization}%">
          GPU {gpu.index}: {gpu.utilization}%
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .telemetry-panel {
    padding: 1rem;
    background: var(--bg-secondary);
    border-radius: 0.75rem;
  }
  
  .metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 1rem;
    margin-bottom: 1rem;
  }
  
  .metric-card {
    background: var(--bg-tertiary);
    padding: 0.75rem;
    border-radius: 0.5rem;
  }
  
  .metric-card .label {
    display: block;
    font-size: 0.75rem;
    color: var(--text-secondary);
    margin-bottom: 0.25rem;
  }
  
  .metric-card .value {
    display: block;
    font-size: 1.25rem;
    font-weight: bold;
  }
  
  .value.warning {
    color: var(--danger);
  }
  
  .gpu-chart {
    margin-top: 1rem;
  }
  
  .gpu-bar {
    background: var(--primary);
    color: white;
    padding: 0.25rem 0.5rem;
    margin: 0.25rem 0;
    border-radius: 0.25rem;
    transition: width 0.3s ease;
    font-size: 0.75rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
</style>