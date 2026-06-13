import { reactive } from 'vue';
import { USE_MOCK, WS_BASE } from '@/api/config';
import { refreshAccessToken } from '@/api/http';
import { nextRealtimeMessage } from '@/api/mock';
import type { RealtimeAlarmEvent, RealtimeMessage } from '@/types/domain';

let authRefreshAttempts = 0;
const MAX_AUTH_REFRESH_ATTEMPTS = 3;

export type RealtimeStatus =
  | 'idle'
  | 'mock'
  | 'connecting'
  | 'online'
  | 'reconnecting'
  | 'offline'
  | 'auth_failed'
  | 'error';

export const realtimeStatusLabel: Record<RealtimeStatus, string> = {
  idle: '未连接',
  mock: 'Mock 实时',
  connecting: '连接中',
  online: '实时在线',
  reconnecting: '重连中',
  offline: '实时离线',
  auth_failed: '鉴权失败',
  error: '连接异常'
};

export const realtimeState = reactive({
  status: 'idle' as RealtimeStatus,
  attempts: 0,
  lastMessageAt: null as string | null,
  error: ''
});

const listeners = new Set<(message: RealtimeMessage) => void>();
const alarmListeners = new Set<(event: RealtimeAlarmEvent) => void>();
let socket: WebSocket | null = null;
let reconnectTimer: number | null = null;
let mockTimer: number | null = null;
let closingIntentionally = false;
let reconnecting = false;
let connectGeneration = 0;

export function subscribeRealtime(onMessage: (message: RealtimeMessage) => void) {
  listeners.add(onMessage);
  ensureRealtimeConnection();

  return () => {
    listeners.delete(onMessage);
    if (!hasSubscribers()) {
      stopRealtimeConnection();
    }
  };
}

export function subscribeAlarmEvents(onEvent: (event: RealtimeAlarmEvent) => void) {
  alarmListeners.add(onEvent);
  ensureRealtimeConnection();

  return () => {
    alarmListeners.delete(onEvent);
    if (!hasSubscribers()) {
      stopRealtimeConnection();
    }
  };
}

function hasSubscribers() {
  return listeners.size > 0 || alarmListeners.size > 0;
}

function ensureRealtimeConnection() {
  if (USE_MOCK) {
    startMockRealtime();
    return;
  }

  if (socket && (socket.readyState === WebSocket.CONNECTING || socket.readyState === WebSocket.OPEN)) {
    return;
  }

  connectWebSocket();
}

function startMockRealtime() {
  realtimeState.status = 'mock';
  realtimeState.error = '';
  if (mockTimer !== null) return;

  mockTimer = window.setInterval(() => {
    const message = nextRealtimeMessage();
    realtimeState.lastMessageAt = message.ts;
    emitMessage(message);
  }, 1200);
}

function connectWebSocket() {
  if (reconnecting) return;
  const token = localStorage.getItem('access_token');
  if (!token) {
    realtimeState.status = 'auth_failed';
    realtimeState.error = '缺少访问令牌，无法建立实时连接';
    return;
  }

  const gen = ++connectGeneration;
  clearReconnectTimer();
  closingIntentionally = false;
  realtimeState.status = realtimeState.attempts > 0 ? 'reconnecting' : 'connecting';
  realtimeState.error = '';

  const url = `${WS_BASE}?token=${encodeURIComponent(token)}`;
  const currentSocket = new WebSocket(url);
  socket = currentSocket;

  currentSocket.onopen = () => {
    if (gen !== connectGeneration || socket !== currentSocket) return;
    realtimeState.status = 'online';
    realtimeState.attempts = 0;
    authRefreshAttempts = 0;
    realtimeState.error = '';
  };

  currentSocket.onmessage = (event) => {
    if (gen !== connectGeneration || socket !== currentSocket) return;
    const parsed = parseEnvelope(event.data);
    if (!parsed) return;
    realtimeState.lastMessageAt = parsed.ts;
    if (parsed.kind === 'sensor') {
      emitMessage(parsed.payload);
    } else if (parsed.kind === 'alarm') {
      emitAlarm(parsed.payload);
    }
  };

  currentSocket.onerror = () => {
    if (gen !== connectGeneration || socket !== currentSocket) return;
    realtimeState.status = 'error';
    realtimeState.error = 'WebSocket 连接异常';
  };

  currentSocket.onclose = (event) => {
    if (gen !== connectGeneration || socket !== currentSocket) return;
    socket = null;
    if (closingIntentionally || !hasSubscribers()) {
      realtimeState.status = 'idle';
      return;
    }

    if (event.code === 4401 || event.code === 1008) {
      if (authRefreshAttempts < MAX_AUTH_REFRESH_ATTEMPTS) {
        authRefreshAttempts++;
        realtimeState.status = 'reconnecting';
        realtimeState.error = `Token过期，尝试刷新后重连(${authRefreshAttempts}/${MAX_AUTH_REFRESH_ATTEMPTS})...`;
        reconnecting = true;
        refreshAccessToken().then((newToken) => {
          reconnecting = false;
          if (connectGeneration !== gen) return;
          if (!hasSubscribers()) {
            realtimeState.status = 'idle';
            realtimeState.error = '';
          } else if (newToken) {
            realtimeState.attempts = 0;
            connectWebSocket();
          } else {
            realtimeState.status = 'auth_failed';
            realtimeState.error = '实时连接鉴权失败，请重新登录';
          }
        });
        return;
      }
      realtimeState.status = 'auth_failed';
      realtimeState.error = '实时连接鉴权失败，请重新登录';
      return;
    }

    scheduleReconnect(event.reason || `连接关闭：${event.code}`);
  };
}

function scheduleReconnect(reason: string) {
  if (!hasSubscribers()) return;

  realtimeState.attempts += 1;
  realtimeState.status = 'reconnecting';
  realtimeState.error = reason;
  const delay = Math.min(1200 * 2 ** Math.min(realtimeState.attempts - 1, 4), 12000);

  clearReconnectTimer();
  reconnectTimer = window.setTimeout(() => {
    connectWebSocket();
  }, delay);
}

function stopRealtimeConnection() {
  connectGeneration++;
  clearReconnectTimer();
  reconnecting = false;
  if (mockTimer !== null) {
    window.clearInterval(mockTimer);
    mockTimer = null;
  }
  if (socket) {
    closingIntentionally = true;
    socket.close();
    socket = null;
  }
  realtimeState.status = 'idle';
  realtimeState.attempts = 0;
  realtimeState.error = '';
}

function clearReconnectTimer() {
  if (reconnectTimer !== null) {
    window.clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
}

type ParsedEnvelope =
  | { kind: 'sensor'; payload: RealtimeMessage; ts: string }
  | { kind: 'alarm'; payload: RealtimeAlarmEvent; ts: string };

function parseEnvelope(raw: string): ParsedEnvelope | null {
  try {
    const parsed = JSON.parse(raw) as
      | RealtimeMessage
      | { type?: string; payload?: RealtimeMessage | RealtimeAlarmEvent };
    if ('type' in parsed && parsed.type && parsed.payload) {
      if (parsed.type === 'alarm.event') {
        const payload = parsed.payload as RealtimeAlarmEvent;
        return { kind: 'alarm', payload, ts: payload.ts };
      }
      const payload = parsed.payload as RealtimeMessage;
      return { kind: 'sensor', payload, ts: payload.ts };
    }
    if ('deviceId' in parsed && 'sensorId' in parsed && 'value' in parsed) {
      return { kind: 'sensor', payload: parsed as RealtimeMessage, ts: (parsed as RealtimeMessage).ts };
    }
    return null;
  } catch {
    return null;
  }
}

export function reconnectRealtime() {
  if (USE_MOCK) {
    ensureRealtimeConnection();
    return;
  }
  if (!hasSubscribers()) return;
  connectGeneration++;
  clearReconnectTimer();
  if (socket) {
    closingIntentionally = true;
    try {
      socket.close();
    } catch {
      // ignore
    }
    socket = null;
  }
  reconnecting = false;
  authRefreshAttempts = 0;
  realtimeState.attempts = 0;
  realtimeState.status = 'idle';
  realtimeState.error = '';
  ensureRealtimeConnection();
}

function emitMessage(message: RealtimeMessage) {
  for (const listener of listeners) {
    listener(message);
  }
}

function emitAlarm(event: RealtimeAlarmEvent) {
  for (const listener of alarmListeners) {
    listener(event);
  }
}
