import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export default defineConfig({
  plugins: [svelte()],
  server: {
    port: 8000,
    proxy: {
      '/api': {
        target: 'http://localhost:6000',
        changeOrigin: true
      },
      '/ws': {
        target: 'ws://localhost:6001',
        ws: true
      }
    }
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true
  }
});