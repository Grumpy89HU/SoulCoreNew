<script>
  import { t, setLanguage, currentLanguage } from '../../lib/i18n.js';
  import { config, updateConfig } from '../../lib/store.js';
  
  let tempLanguage = 'hu';
  
  $: tempLanguage = $currentLanguage;
  
  function handleLanguageChange() {
    setLanguage(tempLanguage);
  }
  
  async function handleSave() {
    // TODO: Konfiguráció mentése
    await updateConfig($config);
  }
</script>

<div class="settings-page">
  <h1>{$t('admin.settings')}</h1>
  
  <div class="settings-group">
    <h2>{$t('settings.language')}</h2>
    <select bind:value={tempLanguage} on:change={handleLanguageChange}>
      <option value="en">English</option>
      <option value="hu">Magyar</option>
    </select>
  </div>
  
  <div class="settings-group">
    <h2>{$t('settings.theme')}</h2>
    <select>
      <option value="dark">Dark</option>
      <option value="light">Light</option>
      <option value="system">System</option>
    </select>
  </div>
  
  <button class="save-btn" on:click={handleSave}>{$t('general.save')}</button>
</div>

<style>
  .settings-page {
    padding: 1.5rem;
    max-width: 600px;
    margin: 0 auto;
  }
  
  h1 {
    margin-bottom: 1.5rem;
    color: var(--primary);
  }
  
  .settings-group {
    margin-bottom: 1.5rem;
  }
  
  .settings-group h2 {
    margin-bottom: 0.5rem;
    font-size: 1rem;
  }
  
  select {
    padding: 0.5rem;
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 0.5rem;
    color: var(--text-primary);
    width: 200px;
  }
  
  .save-btn {
    padding: 0.75rem 1.5rem;
    background: var(--primary);
    border: none;
    border-radius: 0.5rem;
    color: #000;
    font-weight: 600;
    cursor: pointer;
  }
</style>