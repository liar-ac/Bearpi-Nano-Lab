import { USE_MOCK } from '@/api/config';
import { request } from '@/api/http';
import {
  mockAckAlarm,
  mockFetchAlarms,
  mockFetchCommands,
  mockFetchBulkTasks,
  mockFetchDevice,
  mockFetchDevices,
  mockFetchHistory,
  mockFetchAccountUsers,
  mockFetchAuditLogs,
  mockFetchRules,
  mockLogin,
  mockRegister,
  mockSimulateRealtime,
  mockSendBulkCommand,
  mockRetryBulkTask,
  mockSendCommand,
  mockUpdateAccountUserRole,
  mockUpdateRule
} from '@/api/mock';
import type {
  AccountUser,
  AuditLog,
  Alarm,
  BulkCommandResponse,
  BulkTaskListResponse,
  CommandPayload,
  CommandResult,
  Device,
  DeviceListResponse,
  HistoryInterval,
  LoginResponse,
  PointsResponse,
  RealtimeMessage,
  RuleConfig,
  UserRole
} from '@/types/domain';

type PagedResponse<T> = T[] | { results?: T[]; data?: T[]; items?: T[] };

function normalizeListResponse<T>(response: PagedResponse<T>): T[] {
  if (Array.isArray(response)) return response;
  if (Array.isArray(response.results)) return response.results;
  if (Array.isArray(response.data)) return response.data;
  if (Array.isArray(response.items)) return response.items;
  return [];
}

export function login(username: string, password: string) {
  if (USE_MOCK) return mockLogin(username, password);
  return request<LoginResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password })
  });
}

export function register(payload: { username: string; password: string; name?: string }) {
  if (USE_MOCK) return mockRegister(payload);
  return request<LoginResponse>('/auth/register', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export function fetchAccountUsers() {
  if (USE_MOCK) return mockFetchAccountUsers();
  return request<PagedResponse<AccountUser>>('/auth/users').then(normalizeListResponse);
}

export function updateAccountUserRole(userId: number, role: UserRole) {
  if (USE_MOCK) return mockUpdateAccountUserRole(userId, role);
  return request<AccountUser>(`/auth/users/${userId}/role`, {
    method: 'POST',
    body: JSON.stringify({ role })
  });
}

export function fetchDevices(params: { status?: string; includeInactive?: boolean } = {}) {
  if (USE_MOCK) return mockFetchDevices(params.status);
  const query = new URLSearchParams();
  if (params.status) query.set('status', params.status);
  if (params.includeInactive) query.set('include_inactive', 'true');
  const suffix = query.toString() ? `?${query}` : '';
  return request<DeviceListResponse>(`/devices${suffix}`);
}

export function fetchDevice(deviceId: number) {
  if (USE_MOCK) return mockFetchDevice(deviceId);
  return request<Device>(`/devices/${deviceId}`);
}

export function fetchHistory(
  sensorId: number,
  params: { start: string; end: string; interval: HistoryInterval }
) {
  if (USE_MOCK) return mockFetchHistory(sensorId, params);
  const query = new URLSearchParams({
    start: params.start,
    end: params.end,
    interval: params.interval
  });
  return request<PointsResponse>(`/sensors/${sensorId}/history?${query}`);
}

export function sendCommand(deviceId: number, payload: CommandPayload) {
  if (USE_MOCK) return mockSendCommand(deviceId, payload);
  return request<CommandResult>(`/devices/${deviceId}/commands`, {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export function sendBulkCommand(payload: {
  target: 'all' | 'online' | 'selected';
  actuator: 'motor' | 'light';
  mode: 'auto' | 'on' | 'off';
  device_ids?: number[];
  sync_delay_ms?: number;
}) {
  if (USE_MOCK) return mockSendBulkCommand(payload);
  return request<BulkCommandResponse>('/devices/bulk-commands', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export function fetchBulkTasks(params: { limit?: number } = {}) {
  if (USE_MOCK) return mockFetchBulkTasks(params);
  const query = new URLSearchParams();
  if (params.limit != null) query.set('limit', String(params.limit));
  const suffix = query.toString() ? `?${query}` : '';
  return request<BulkTaskListResponse>(`/devices/bulk-tasks${suffix}`);
}

export function retryBulkTask(batchId: string) {
  if (USE_MOCK) return mockRetryBulkTask(batchId);
  return request<BulkCommandResponse>(`/devices/bulk-tasks/${encodeURIComponent(batchId)}/retry`, {
    method: 'POST',
    body: JSON.stringify({})
  });
}

export function fetchCommands(deviceId: number) {
  if (USE_MOCK) return mockFetchCommands(deviceId);
  return request<CommandResult[] | { count: number; results: CommandResult[] }>(`/devices/${deviceId}/commands`).then(
    (r) => (Array.isArray(r) ? r : r.results ?? [])
  );
}

export function fetchAlarms(params: { status?: string; level?: string; limit?: number; offset?: number } = {}) {
  if (USE_MOCK) return mockFetchAlarms(params);
  const query = new URLSearchParams();
  if (params.status) query.set('status', params.status);
  if (params.level) query.set('level', params.level);
  if (params.limit != null) query.set('limit', String(params.limit));
  if (params.offset != null) query.set('offset', String(params.offset));
  const suffix = query.toString() ? `?${query}` : '';
  return request<PagedResponse<Alarm>>(`/alarms${suffix}`).then(normalizeListResponse);
}

export function ackAlarm(alarmId: number) {
  if (USE_MOCK) return mockAckAlarm(alarmId);
  return request<Alarm>(`/alarms/${alarmId}/ack`, {
    method: 'POST'
  });
}

export function simulateRealtime(sensorId: number) {
  if (USE_MOCK) return mockSimulateRealtime(sensorId);
  return request<RealtimeMessage>('/simulate/realtime', {
    method: 'POST',
    body: JSON.stringify({ sensor_id: sensorId })
  });
}

export function fetchAuditLogs(params: { action?: string; limit?: number; offset?: number } = {}) {
  if (USE_MOCK) return mockFetchAuditLogs(params);
  const query = new URLSearchParams();
  if (params.action) query.set('action', params.action);
  if (params.limit != null) query.set('limit', String(params.limit));
  if (params.offset != null) query.set('offset', String(params.offset));
  const suffix = query.toString() ? `?${query}` : '';
  return request<PagedResponse<AuditLog>>(`/audit-logs${suffix}`).then(normalizeListResponse);
}

export function fetchRules() {
  if (USE_MOCK) return mockFetchRules();
  return request<PagedResponse<RuleConfig>>('/rules').then(normalizeListResponse);
}

export function updateRule(sensorId: number, payload: { min?: number | null; max?: number | null }) {
  if (USE_MOCK) return mockUpdateRule(sensorId, payload);
  return request<RuleConfig>(`/rules/${sensorId}`, {
    method: 'PUT',
    body: JSON.stringify(payload)
  });
}

export function sendAiChat(feature: string, context: Record<string, unknown>, signal?: AbortSignal | null) {
  return request<{ reply: string; feature: string; data_source?: string }>('/ai/chat', {
    method: 'POST',
    body: JSON.stringify({ feature, context })
  }, signal);
}

export function sendAiQuery(question: string, history?: Array<{ role: string; content: string }>, signal?: AbortSignal | null) {
  return request<{ reply: string; question: string; data_source?: string; diagnostic?: Record<string, unknown> }>('/ai/query', {
    method: 'POST',
    body: JSON.stringify({ question, history })
  }, signal);
}

export interface AiCommandResult {
  detected: boolean;
  device_sn?: string;
  device_id?: number;
  slot_no?: number;
  device_status?: string;
  actuator?: string;
  mode?: string;
  confidence?: number;
  explanation?: string;
}

export function parseAiCommand(text: string) {
  return request<AiCommandResult>('/ai/command', {
    method: 'POST',
    body: JSON.stringify({ text })
  });
}
