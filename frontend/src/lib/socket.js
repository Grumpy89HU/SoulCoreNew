import { writable } from 'svelte/store';
import { getWsUrl } from './config.js';
import { addMessage, setLoading, updateTelemetry } from './store.js';

let socket = null;
let reconnectAttempts = 0;
const maxReconnectAttempts = 10;
const reconnectDelay = 3000;

export const socketStatus = writable('disconnected');

export function initSocket() {
  if (socket && socket.readyState === WebSocket.OPEN) {
    return;
  }
  
  const wsUrl = getWsUrl();
  socket = new WebSocket(wsUrl);
  
  socket.onopen = () => {
    console.log('🔌 WebSocket kapcsolódva');
    socketStatus.set('connected');
    reconnectAttempts = 0;
    
    // Feliratkozás telemetriára
    socket.send(JSON.stringify({
      type: 'subscribe',
      topic: 'telemetry'
    }));
  };
  
  socket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      handleMessage(data);
    } catch (e) {
      console.error('WebSocket üzenet hiba:', e);
    }
  };
  
  socket.onclose = () => {
    console.log('🔌 WebSocket lecsatlakozva');
    socketStatus.set('disconnected');
    
    // Újrakapcsolódás
    if (reconnectAttempts < maxReconnectAttempts) {
      reconnectAttempts++;
      setTimeout(initSocket, reconnectDelay);
    }
  };
  
  socket.onerror = (error) => {
    console.error('WebSocket hiba:', error);
    socketStatus.set('error');
  };
}

export function disconnectSocket() {
  if (socket) {
    socket.close();
    socket = null;
  }
}

function handleMessage(data) {
  switch (data.type) {
    case 'chat:response':
      addMessage({
        role: 'assistant',
        content: data.text,
        conversation_id: data.conversation_id,
        timestamp: data.timestamp
      });
      setLoading(false);
      break;
      
    case 'telemetry:update':
      updateTelemetry(data.data);
      break;
      
    case 'notification':
      console.log('📢 Értesítés:', data.notification);
      // TODO: Toast értesítés
      break;
      
    case 'connected':
      console.log('✅ Kapcsolódva:', data.client_id);
      break;
  }
}

export function sendChatMessage(text, conversationId) {
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    console.error('WebSocket nem elérhető');
    return false;
  }
  
  socket.send(JSON.stringify({
    type: 'chat:message',
    text: text,
    conversation_id: conversationId
  }));
  
  return true;
}

export function subscribeToTopic(topic) {
  if (!socket || socket.readyState !== WebSocket.OPEN) return;
  
  socket.send(JSON.stringify({
    type: 'subscribe',
    topic: topic
  }));
}

export function unsubscribeFromTopic(topic) {
  if (!socket || socket.readyState !== WebSocket.OPEN) return;
  
  socket.send(JSON.stringify({
    type: 'unsubscribe',
    topic: topic
  }));
}