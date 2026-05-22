export type UserRole = 'admin' | 'experimenter' | 'viewer';
export type DeviceStatus = 'online' | 'offline' | 'warning' | 'maintenance';
export type AlarmLevel = 'info' | 'warning' | 'critical';
export type AlarmStatus = 'new' | 'acknowledged' | 'closed';
export type CommandType = 'reboot' | 'upgrade' | 'set_param';
export type HistoryInterval = '1m' | '5m' | '1h' | '1d';

export interface User {
  id: number;
  name: string;
  role: UserRole;
  team: string;
}

export interface AccountUser {
  id: number;
  username: string;
  name: string;
  role: UserRole;
  isActive: boolean;
  createdAt: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  user: User;
}

export interface SensorLatest {
  ts: string;
  value: number;
}

export interface Sensor {
  id: number;
  deviceId: number;
  code: string;
  name: string;
  unit: string;
  description: string;
  min?: number;
  max?: number;
  latest?: SensorLatest;
}

export interface Device {
  id: number;
  slotNo: number;
  sn: string;
  labId: string;
  model: string;
  firmwareVersion: string;
  location: string;
  owner: string;
  member: string;
  status: DeviceStatus;
  lastSeen: string | null;
  registerTime: string;
  ipAddress?: string;
  sampleRate: number;
  abnormalReason?: string;
  sensors: Sensor[];
}

export interface LabSlot {
  slotNo: number;
  row: number;
  column: number;
  status: DeviceStatus | 'empty';
  device?: Device;
}

export interface DeviceListResponse {
  count: number;
  results: Device[];
}

export interface Point {
  ts: string;
  value: number;
}

export interface PointsResponse {
  metric: string;
  sensor_id: number;
  device_id: number;
  interval: HistoryInterval;
  points: Point[];
}

export interface Alarm {
  id: number;
  deviceId: number;
  sensorId?: number;
  deviceName: string;
  ts: string;
  level: AlarmLevel;
  status: AlarmStatus;
  message: string;
}

export interface RealtimeMessage {
  deviceId: number;
  sensorId: number;
  code: string;
  name: string;
  unit: string;
  value: number;
  ts: string;
  status?: DeviceStatus;
}

export interface RealtimeAlarmEvent {
  id: number;
  deviceId: number;
  sensorId?: number;
  deviceName: string;
  level: AlarmLevel;
  status: AlarmStatus;
  message: string;
  ts: string;
}

export interface CommandPayload {
  type: CommandType;
  params?: Record<string, string | number | boolean>;
}

export interface CommandResult {
  id: number | string;
  deviceId: number;
  command: CommandType;
  params?: Record<string, string | number | boolean>;
  status: 'queued' | 'sent' | 'acked' | 'failed';
  message: string;
  createdAt: string;
  ackAt?: string | null;
}

export interface BulkCommandResponse {
  count: number;
  batchId?: string;
  executeAt?: string;
  serverTime?: string;
  commands: CommandResult[];
  task?: BulkTask;
}

export type BulkTaskStatus = 'queued' | 'running' | 'completed' | 'partial' | 'failed';
export type BulkTaskActuator = 'motor' | 'light' | 'unknown';
export type BulkTaskMode = 'auto' | 'on' | 'off' | 'unknown';

export interface BulkTaskCommand {
  id: number | string;
  deviceId: number;
  slotNo: number;
  sn: string;
  status: CommandResult['status'];
  message: string;
  createdAt: string;
  ackAt?: string | null;
}

export interface BulkTaskLog {
  ts: string;
  level: 'info' | 'success' | 'warning' | 'error';
  message: string;
  deviceId?: number;
  slotNo?: number;
  sn?: string;
  commandId?: number | string;
  status?: CommandResult['status'];
}

export interface BulkTask {
  batchId: string;
  title: string;
  actuator: BulkTaskActuator;
  mode: BulkTaskMode;
  status: BulkTaskStatus;
  total: number;
  queued: number;
  sent: number;
  acked: number;
  failed: number;
  pending: number;
  progress: number;
  executeAt?: string;
  syncDelayMs?: number;
  retryOf?: string;
  createdAt: string;
  latestAt: string;
  commands: BulkTaskCommand[];
  failedDevices: BulkTaskCommand[];
  logs: BulkTaskLog[];
}

export interface BulkTaskListResponse {
  count: number;
  results: BulkTask[];
}

export interface AuditLog {
  id: number;
  actorName: string;
  action: string;
  target: string;
  detail: string;
  metadata: Record<string, unknown>;
  ipAddress: string | null;
  createdAt: string;
}

export interface RuleConfig {
  id: number;
  deviceId: number;
  deviceName: string;
  slotNo: number;
  code: string;
  name: string;
  unit: string;
  description: string;
  min: number | null;
  max: number | null;
  sampleRate: number;
}
