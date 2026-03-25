import { writable, derived } from 'svelte/store';

// Üzenetek store
export const messages = writable([]);
export const isLoading = writable(false);
export const currentConversation = writable(null);
export const conversations = writable([]);
export const telemetry = writable({});
export const kingState = writable({});
export const models = writable([]);
export const config = writable({});

// Derive-olt store-ok
export const currentMessages = derived(
  [messages, currentConversation],
  ([$messages, $currentConversation]) => {
    if (!$currentConversation) return [];
    return $messages.filter(m => m.conversation_id === $currentConversation.id);
  }
);

// Műveletek
export function addMessage(message) {
  messages.update(m => [...m, {
    id: Date.now(),
    timestamp: Date.now(),
    ...message
  }]);
}

export function setLoading(loading) {
  isLoading.set(loading);
}

export function clearMessages() {
  messages.set([]);
}

export function setCurrentConversation(conv) {
  currentConversation.set(conv);
}

export function setConversations(list) {
  conversations.set(list);
}

export function addConversation(conv) {
  conversations.update(c => [conv, ...c]);
}

export function removeConversation(id) {
  conversations.update(c => c.filter(conv => conv.id !== id));
}

export function updateTelemetry(data) {
  telemetry.update(t => ({ ...t, ...data }));
}

export function updateKingState(state) {
  kingState.set(state);
}

export function setModels(modelList) {
  models.set(modelList);
}

export function updateConfig(newConfig) {
  config.set(newConfig);
}

// API integráció
import { getConversations as apiGetConversations, createConversation as apiCreateConversation } from './api.js';

export async function loadConversations() {
  try {
    const data = await apiGetConversations();
    setConversations(data.conversations || []);
  } catch (e) {
    console.error('Beszélgetések betöltési hiba:', e);
  }
}

export async function newConversation(title) {
  try {
    const data = await apiCreateConversation(title);
    if (data.id) {
      const newConv = { id: data.id, title, created_at: Date.now() };
      addConversation(newConv);
      return newConv;
    }
  } catch (e) {
    console.error('Beszélgetés létrehozási hiba:', e);
  }
  return null;
}