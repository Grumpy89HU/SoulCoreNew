// SoulCore API konfiguráció
// EZT A KING BÁRMIKOR ÁTÍRHATJA!

export const API_CONFIG = {
  baseUrl: import.meta.env.VITE_API_URL || 'http://localhost:6000',
  wsUrl: import.meta.env.VITE_WS_URL || 'ws://localhost:6001'
};

export function getApiUrl(path) {
  return `${API_CONFIG.baseUrl}${path}`;
}

export function getWsUrl() {
  return API_CONFIG.wsUrl;
}