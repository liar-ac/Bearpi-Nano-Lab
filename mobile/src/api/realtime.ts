import { reactive } from 'vue';
import { USE_MOCK, WS_BASE } from '@/api/config';
import { refreshAccessToken } from '@/api/http';
import { nextRealtimeMessage } from '@/api/mock';
import type { RealtimeAlarmEvent, RealtimeMessage } from '@/types/domain';

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
let socket: UniApp.SocketTask | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let mockTimer: ReturnType<typeof setInterval> | null = null;
let closingIntentionally = false;
let socketOpening = false;
let socketOpen = false;
let reconnecting = false;

export function subscribeRealtime(onMessage: (message: RealtimeMessage) => void) {
  listeners.add(onMessage);
  ensureRealtimeConnection();

  return () => {
    listeners.delete(onMessage);
    if (listeners.size === 0 && alarmListeners.size === 0) {
      stopRealtimeConnection();
    }
  };
}

export function subscribeAlarmEvents(onEvent: (event: RealtimeAlarmEvent) => void) {
  alarmListeners.add(onEvent);
  ensureRealtimeConnection();

  return () => {
    alarmListeners.delete(onEvent);
    if (listeners.size === 0 && alarmListeners.size === 0) {
      stopRealtimeConnection();
    }
  };
}

function ensureRealtimeConnection() {
  if (USE_MOCK) {
    startMockRealtime();
    return;
  }

  if (socket && (socketOpening || socketOpen)) return;
  connectWebSocket();
}

function startMockRealtime() {
  realtimeState.status = 'mock';
  realtimeState.error = '';
  if (mockTimer !== null) return;

  mockTimer = setInterval(() => {
    const message = nextRealtimeMessage();
    realtimeState.lastMessageAt = message.ts;
    emitMessage(message);
  }, 1200);
}

function connectWebSocket() {
  if (reconnecting) return;
  const token = uni.getStorageSync('access_token');
  if (!token) {
    realtimeState.status = 'auth_failed';
    realtimeState.error = '缺少访问令牌，无法建立实时连接';
    return;
  }

  clearReconnectTimer();
  closingIntentionally = false;
  socketOpening = true;
  socketOpen = false;
  realtimeState.status = realtimeState.attempts > 0 ? 'reconnecting' : 'connecting';
  realtimeState.error = '';

  const url = `${WS_BASE}?token=${encodeURIComponent(String(token))}`;
  const task = uni.connectSocket({ url }) as unknown as UniApp.SocketTask;
  socket = task;

  task.onOpen(() => {
    socketOpening = false;
    socketOpen = true;
    realtimeState.status = 'online';
    realtimeState.attempts = 0;
    realtimeState.error = '';
  });

  task.onMessage((event) => {
    const parsed = parseEnvelope(event.data);
    if (!parsed) return;
    realtimeState.lastMessageAt = parsed.ts;
    if (parsed.kind === 'sensor') {
      emitMessage(parsed.payload);
    } else if (parsed.kind === 'alarm') {
      emitAlarm(parsed.payload);
    }
  });

  task.onError(() => {
    socketOpening = false;
    realtimeState.status = 'error';
    realtimeState.error = 'WebSocket 连接异常';
  });

  task.onClose((event) => {
    socket = null;
    socketOpening = false;
    socketOpen = false;

    if (closingIntentionally || (listeners.size === 0 && alarmListeners.size === 0)) {
      realtimeState.status = 'idle';
      return;
    }

    if (event.code === 4401 || event.code === 1008) {
      if (realtimeState.attempts === 0) {
        realtimeState.status = 'reconnecting';
        realtimeState.error = 'Token过期，尝试刷新后重连...';
        reconnecting = true;
        refreshAccessToken().then((newToken) => {
          reconnecting = false;
          const hasSubscribers = listeners.size > 0 || alarmListeners.size > 0;
          if (!hasSubscribers) {
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
  });
}

function scheduleReconnect(reason: string) {
  if (listeners.size === 0 && alarmListeners.size === 0) return;

  realtimeState.attempts += 1;
  realtimeState.status = 'reconnecting';
  realtimeState.error = reason;
  const delay = Math.min(1200 * 2 ** Math.min(realtimeState.attempts - 1, 4), 12000);

  clearReconnectTimer();
  reconnectTimer = setTimeout(() => {
    connectWebSocket();
  }, delay);
}

function stopRealtimeConnection() {
  clearReconnectTimer();
  if (mockTimer !== null) {
    clearInterval(mockTimer);
    mockTimer = null;
  }
  if (socket) {
    closingIntentionally = true;
    socket.close({});
    socket = null;
  }
  socketOpening = false;
  socketOpen = false;
  reconnecting = false;
  realtimeState.status = 'idle';
  realtimeState.attempts = 0;
  realtimeState.error = '';
}

function clearReconnectTimer() {
  if (reconnectTimer !== null) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
}

type ParsedEnvelope =
  | { kind: 'sensor'; payload: RealtimeMessage; ts: string }
  | { kind: 'alarm'; payload: RealtimeAlarmEvent; ts: string };

function parseEnvelope(raw: string | ArrayBuffer): ParsedEnvelope | null {
  if (typeof raw !== 'string') return null;
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
  // 登录成功 / token 刷新后主动重连
  if (USE_MOCK) {
    ensureRealtimeConnection();
    return;
  }
  if (listeners.size === 0 && alarmListeners.size === 0) return;
  clearReconnectTimer();
  reconnecting = false;
  if (socket) {
    closingIntentionally = true;
    try {
      socket.close({});
    } catch {
      // ignore
    }
    socket = null;
    socketOpening = false;
    socketOpen = false;
  }
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
