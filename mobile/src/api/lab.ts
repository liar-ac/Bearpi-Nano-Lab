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

function buildQuery(params: Record<string, string | number | boolean | undefined | null>) {
  const entries: string[] = [];
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue;
    entries.push(`${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`);
  }
  return entries.length ? `?${entries.join('&')}` : '';
}

export function login(username: string, password: string) {
  if (USE_MOCK) return mockLogin(username, password);
  return request<LoginResponse>('/auth/login', {
    method: 'POST',
    data: { username, password }
  });
}

export function register(payload: { username: string; password: string; name?: string }) {
  if (USE_MOCK) return mockRegister(payload);
  return request<LoginResponse>('/auth/register', {
    method: 'POST',
    data: payload
  });
}

export function fetchDevices(params: { status?: string; includeInactive?: boolean } = {}) {
  if (USE_MOCK) return mockFetchDevices(params.status);
  const query = buildQuery({
    status: params.status,
    include_inactive: params.includeInactive ? 'true' : undefined
  });
  return request<DeviceListResponse>(`/devices${query}`);
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
  const query = buildQuery({
    start: params.start,
    end: params.end,
    interval: params.interval
  });
  return request<PointsResponse>(`/sensors/${sensorId}/history${query}`);
}

export function sendCommand(deviceId: number, payload: CommandPayload) {
  if (USE_MOCK) return mockSendCommand(deviceId, payload);
  return request<CommandResult>(`/devices/${deviceId}/commands`, {
    method: 'POST',
    data: payload
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
    data: payload
  });
}

export function fetchBulkTasks(params: { limit?: number } = {}) {
  if (USE_MOCK) return mockFetchBulkTasks(params);
  const query = buildQuery({ limit: params.limit });
  return request<BulkTaskListResponse>(`/devices/bulk-tasks${query}`);
}

export function retryBulkTask(batchId: string) {
  if (USE_MOCK) return mockRetryBulkTask(batchId);
  return request<BulkCommandResponse>(`/devices/bulk-tasks/${encodeURIComponent(batchId)}/retry`, {
    method: 'POST',
    data: {}
  });
}

export function fetchCommands(deviceId: number) {
  if (USE_MOCK) return mockFetchCommands(deviceId);
  return request<CommandResult[]>(`/devices/${deviceId}/commands`);
}

export function fetchAlarms(params: { status?: string; level?: string; limit?: number; offset?: number } = {}) {
  if (USE_MOCK) return mockFetchAlarms(params);
  const query = buildQuery({
    status: params.status,
    level: params.level,
    limit: params.limit,
    offset: params.offset
  });
  return request<PagedResponse<Alarm>>(`/alarms${query}`).then(normalizeListResponse);
}

export function ackAlarm(alarmId: number) {
  if (USE_MOCK) return mockAckAlarm(alarmId);
  return request<Alarm>(`/alarms/${alarmId}/ack`, { method: 'POST' });
}

export function simulateRealtime(sensorId: number) {
  if (USE_MOCK) return mockSimulateRealtime(sensorId);
  return request<RealtimeMessage>('/simulate/realtime', {
    method: 'POST',
    data: { sensor_id: sensorId }
  });
}

export function fetchAccountUsers() {
  if (USE_MOCK) return mockFetchAccountUsers();
  return request<AccountUser[]>('/auth/users');
}

export function updateAccountUserRole(userId: number, role: UserRole) {
  if (USE_MOCK) return mockUpdateAccountUserRole(userId, role);
  return request<AccountUser>(`/auth/users/${userId}/role`, {
    method: 'POST',
    data: { role }
  });
}

export function fetchRules() {
  if (USE_MOCK) return mockFetchRules();
  return request<RuleConfig[]>('/rules');
}

export function updateRule(sensorId: number, payload: { min?: number | null; max?: number | null }) {
  if (USE_MOCK) return mockUpdateRule(sensorId, payload);
  return request<RuleConfig>(`/rules/${sensorId}`, {
    method: 'PUT',
    data: payload
  });
}

export function fetchAuditLogs(params: { action?: string; limit?: number; offset?: number } = {}) {
  if (USE_MOCK) return mockFetchAuditLogs(params);
  const query = buildQuery({
    action: params.action,
    limit: params.limit,
    offset: params.offset
  });
  return request<PagedResponse<AuditLog>>(`/audit-logs${query}`).then(normalizeListResponse);
}
