import { getApiUrl } from './config.js';

export async function getStatus() {
  const response = await fetch(getApiUrl('/api/status'));
  return response.json();
}

export async function sendMessage(text, conversationId) {
  const response = await fetch(getApiUrl('/api/chat'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, conversation_id: conversationId })
  });
  return response.json();
}

export async function getConversations() {
  const response = await fetch(getApiUrl('/api/conversations'));
  return response.json();
}

export async function createConversation(title) {
  const response = await fetch(getApiUrl('/api/conversations'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title })
  });
  return response.json();
}

export async function deleteConversation(conversationId) {
  const response = await fetch(getApiUrl(`/api/conversations/${conversationId}`), {
    method: 'DELETE'
  });
  return response.json();
}

export async function getMessages(conversationId, limit = 100) {
  const response = await fetch(getApiUrl(`/api/conversations/${conversationId}/messages?limit=${limit}`));
  return response.json();
}

export async function getModels() {
  const response = await fetch(getApiUrl('/api/models'));
  return response.json();
}

export async function loadModel(modelId) {
  const response = await fetch(getApiUrl('/api/models/load'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model_id: modelId })
  });
  return response.json();
}

export async function unloadModel(modelId) {
  const response = await fetch(getApiUrl('/api/models/unload'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model_id: modelId })
  });
  return response.json();
}

export async function getKingState() {
  const response = await fetch(getApiUrl('/api/king/state'));
  return response.json();
}

export async function setKingParameters(params) {
  const response = await fetch(getApiUrl('/api/king/parameters'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
  });
  return response.json();
}

export async function startModule(moduleName) {
  const response = await fetch(getApiUrl('/api/modules/start'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ module: moduleName })
  });
  return response.json();
}

export async function stopModule(moduleName) {
  const response = await fetch(getApiUrl('/api/modules/stop'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ module: moduleName })
  });
  return response.json();
}

export async function rememberMemory(key, value, type = 'fact') {
  const response = await fetch(getApiUrl('/api/memory/remember'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ key, value, type })
  });
  return response.json();
}

export async function recallMemory(key) {
  const response = await fetch(getApiUrl('/api/memory/recall'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ key })
  });
  return response.json();
}

export async function cleanMemory() {
  const response = await fetch(getApiUrl('/api/memory/clean'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
  });
  return response.json();
}

export async function getConfig() {
  const response = await fetch(getApiUrl('/api/config'));
  return response.json();
}

export async function updateConfig(config) {
  const response = await fetch(getApiUrl('/api/config'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config)
  });
  return response.json();
}