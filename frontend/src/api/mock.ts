import type {
  AccountUser,
  AuditLog,
  Alarm,
  BulkCommandResponse,
  BulkTask,
  BulkTaskActuator,
  BulkTaskListResponse,
  BulkTaskMode,
  CommandPayload,
  CommandResult,
  CommandType,
  Device,
  DeviceListResponse,
  HistoryInterval,
  LoginResponse,
  PointsResponse,
  RuleConfig,
  RealtimeMessage,
  Sensor,
  UserRole
} from '@/types/domain';

const now = Date.now();

const sensorTemplates = [
  { code: 'temp', name: '温度', unit: '℃', description: '板载温度传感器', min: 18, max: 32 },
  { code: 'hum', name: '湿度', unit: '%', description: '环境湿度', min: 30, max: 75 },
  { code: 'light', name: '光照', unit: 'lx', description: '光照强度，低于阈值时开启补光灯', min: 20, max: 1200 },
  { code: 'motor', name: '电机驱动', unit: '', description: 'IA1 通风电机状态，0=关闭，1=开启', min: 0, max: 1 },
  { code: 'voltage', name: '工作电压', unit: 'V', description: '开发板工作电压', min: 4.75, max: 5.25 },
  { code: 'current', name: '工作电流', unit: 'mA', description: '开发板工作电流，优先使用ADC采样值', min: 0, max: 500 },
  { code: 'power', name: '功耗', unit: 'mW', description: '开发板瞬时功耗，优先由实测电压/电流计算', min: 0, max: 2500 },
  { code: 'voltage_sampled', name: '电压采样来源', unit: '', description: '0=估算，1=ADC采样', min: 0, max: 1 },
  { code: 'current_sampled', name: '电流采样来源', unit: '', description: '0=估算，1=ADC采样', min: 0, max: 1 },
  { code: 'power_sampled', name: '功耗采样来源', unit: '', description: '0=估算，1=由ADC电流采样参与计算', min: 0, max: 1 },
  { code: 'power_mcu', name: '主控功耗', unit: 'mW', description: '主控芯片功耗，整板实测时按估算比例分摊', min: 0, max: 800 },
  { code: 'power_wifi', name: 'WiFi功耗', unit: 'mW', description: 'WiFi通信模块功耗，整板实测时按估算比例分摊', min: 0, max: 1000 },
  { code: 'power_sensor', name: '传感器功耗', unit: 'mW', description: 'E53_IA1传感器板功耗，整板实测时按估算比例分摊', min: 0, max: 500 },
  { code: 'power_motor', name: '电机功耗', unit: 'mW', description: '通风电机功耗，整板实测时按估算比例分摊', min: 0, max: 1500 },
  { code: 'power_light', name: '补光灯功耗', unit: 'mW', description: '补光灯功耗，整板实测时按估算比例分摊', min: 0, max: 500 }
];

const members = ['成员 A', '成员 B', '成员 C', '成员 D'];

function iso(minutesAgo: number) {
  return new Date(now - minutesAgo * 60_000).toISOString();
}

function latestValue(code: string, index: number) {
  const modulePower = {
    mcu: 250,
    wifi: 120,
    sensor: 35,
    motor: index % 2 === 0 ? 0 : 600,
    light: index % 3 === 0 ? 150 : 0
  };
  const totalPower = modulePower.mcu + modulePower.wifi + modulePower.sensor + modulePower.motor + modulePower.light;
  const sampled = index % 2 === 0 ? 1 : 0;
  const voltage = sampled ? 5.04 + index * 0.01 : 5;
  const base = {
    temp: 24.6 + index * 0.7,
    hum: 48 + index * 4,
    light: 420 + index * 86,
    motor: 0,
    voltage,
    current: totalPower / voltage,
    power: totalPower,
    voltage_sampled: sampled,
    current_sampled: sampled,
    power_sampled: sampled,
    power_mcu: modulePower.mcu,
    power_wifi: modulePower.wifi,
    power_sensor: modulePower.sensor,
    power_motor: modulePower.motor,
    power_light: modulePower.light
  }[code];
  return Number((base ?? 0).toFixed(2));
}

function createSensors(deviceId: number): Sensor[] {
  return sensorTemplates.map((sensor, index) => ({
    id: deviceId * 100 + index + 1,
    deviceId,
    ...sensor,
    latest: {
      ts: iso(deviceId * 2 + index),
      value: latestValue(sensor.code, deviceId - 1)
    }
  }));
}

let devices: Device[] = [
  {
    id: 1,
    slotNo: 1,
    sn: 'BEARPI-NANO-A001',
    labId: 'lab-embedded-01',
    model: 'BearPi-HM Nano',
    firmwareVersion: 'v1.3.2',
    location: '实验台1/后端HTTP接入组',
    owner: '嵌入式+前端+后端+APP联合组',
    member: members[0],
    status: 'online',
    lastSeen: iso(1),
    registerTime: iso(6800),
    ipAddress: '192.168.31.41',
    sampleRate: 1,
    sensors: createSensors(1)
  },
  {
    id: 2,
    slotNo: 2,
    sn: 'BEARPI-NANO-A002',
    labId: 'lab-embedded-01',
    model: 'BearPi-HM Nano',
    firmwareVersion: 'v1.3.2',
    location: '实验台2/后端HTTP接入组',
    owner: '嵌入式+前端+后端+APP联合组',
    member: members[1],
    status: 'warning',
    abnormalReason: '光照传感器近 10 分钟波动过大',
    lastSeen: iso(3),
    registerTime: iso(6200),
    ipAddress: '192.168.31.45',
    sampleRate: 1,
    sensors: createSensors(2)
  },
  {
    id: 3,
    slotNo: 3,
    sn: 'BEARPI-NANO-A003',
    labId: 'lab-embedded-01',
    model: 'BearPi-HM Nano',
    firmwareVersion: 'v1.3.2',
    location: '实验台3/后端HTTP接入组',
    owner: '嵌入式+前端+后端+APP联合组',
    member: members[2],
    status: 'maintenance',
    lastSeen: iso(12),
    registerTime: iso(6000),
    ipAddress: '192.168.31.46',
    sampleRate: 1,
    sensors: createSensors(3)
  },
  {
    id: 4,
    slotNo: 4,
    sn: 'BEARPI-NANO-A004',
    labId: 'lab-embedded-01',
    model: 'BearPi-HM Nano',
    firmwareVersion: 'v1.3.2',
    location: '实验台4/后端HTTP接入组',
    owner: '嵌入式+前端+后端+APP联合组',
    member: members[3],
    status: 'offline',
    abnormalReason: '超过 30 分钟未上报',
    lastSeen: iso(42),
    registerTime: iso(5400),
    ipAddress: '192.168.31.47',
    sampleRate: 1,
    sensors: createSensors(4)
  }
];

let alarms: Alarm[] = [
  {
    id: 1,
    deviceId: 2,
    sensorId: 203,
    deviceName: 'BEARPI-NANO-A002',
    ts: iso(4),
    level: 'warning',
    status: 'new',
    message: '光照传感器波动超过预警阈值'
  },
  {
    id: 2,
    deviceId: 4,
    deviceName: 'BEARPI-NANO-A004',
    ts: iso(42),
    level: 'critical',
    status: 'new',
    message: '设备离线，最近一次上报超过 30 分钟'
  },
  {
    id: 3,
    deviceId: 3,
    deviceName: 'BEARPI-NANO-A003',
    ts: iso(16),
    level: 'info',
    status: 'acknowledged',
    message: '固件版本低于推荐版本 v1.3.2'
  }
];

let commands: CommandResult[] = [];
let auditId = 4;
let auditLogs: AuditLog[] = [
  {
    id: 1,
    actorName: 'admin',
    action: 'login',
    target: '实验室管理员',
    detail: '用户登录控制台',
    metadata: { role: 'admin' },
    ipAddress: '127.0.0.1',
    createdAt: iso(3)
  },
  {
    id: 2,
    actorName: 'device',
    action: 'command_ack',
    target: 'BEARPI-NANO-A001',
    detail: '设备回执指令：acked',
    metadata: { commandId: 1001 },
    ipAddress: '192.168.31.41',
    createdAt: iso(18)
  },
  {
    id: 3,
    actorName: 'admin',
    action: 'rule_update',
    target: 'BEARPI-NANO-A002/light',
    detail: '更新传感器阈值规则',
    metadata: { before: { min: 10, max: 1200 }, after: { min: 20, max: 1200 } },
    ipAddress: '127.0.0.1',
    createdAt: iso(34)
  }
];
let accountUserId = 4;
let accountUsers: AccountUser[] = [
  {
    id: 1,
    username: 'admin',
    name: '实验室管理员',
    role: 'admin',
    isActive: true,
    createdAt: iso(7200)
  },
  {
    id: 2,
    username: 'exp',
    name: '实验员',
    role: 'experimenter',
    isActive: true,
    createdAt: iso(6800)
  },
  {
    id: 3,
    username: 'viewer',
    name: '只读观察员',
    role: 'viewer',
    isActive: true,
    createdAt: iso(6400)
  },
  {
    id: 4,
    username: 'lab',
    name: '实验员',
    role: 'experimenter',
    isActive: true,
    createdAt: iso(6200)
  }
];

function delay<T>(value: T, ms = 250): Promise<T> {
  return new Promise((resolve) => window.setTimeout(() => resolve(value), ms));
}

function resolveRole(username: string): UserRole {
  if (username === 'viewer') return 'viewer';
  if (username === 'exp' || username === 'lab') return 'experimenter';
  return 'admin';
}

export function mockLogin(username: string, password: string): Promise<LoginResponse> {
  if (!username || !password) {
    return Promise.reject(new Error('请输入账号和密码'));
  }

  const account = accountUsers.find((item) => item.username === username);
  const role = account?.role ?? resolveRole(username);
  return delay({
    access_token: 'mock.jwt.access',
    refresh_token: 'mock.jwt.refresh',
    user: {
      id: account?.id ?? (role === 'admin' ? 1 : role === 'experimenter' ? 2 : 3),
      name: account?.name ?? (role === 'admin' ? '实验室管理员' : role === 'experimenter' ? '实验员' : '只读观察员'),
      role,
      team: '小熊派 Nano 项目组'
    }
  });
}

export function mockRegister(payload: { username: string; password: string; name?: string }): Promise<LoginResponse> {
  const username = payload.username.trim();
  if (!username || payload.password.length < 6) {
    return Promise.reject(new Error('账号不能为空，密码至少 6 位'));
  }
  if (accountUsers.some((item) => item.username === username)) {
    return Promise.reject(new Error('该账号已存在'));
  }

  accountUserId += 1;
  const user: AccountUser = {
    id: accountUserId,
    username,
    name: payload.name?.trim() || username,
    role: 'viewer',
    isActive: true,
    createdAt: new Date().toISOString()
  };
  accountUsers = [...accountUsers, user];
  return delay({
    access_token: 'mock.jwt.access',
    refresh_token: 'mock.jwt.refresh',
    user: {
      id: user.id,
      name: user.name,
      role: user.role,
      team: '小熊派 Nano 项目组'
    }
  });
}

export function mockFetchAccountUsers(): Promise<AccountUser[]> {
  return delay([...accountUsers].sort((a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime()));
}

export function mockUpdateAccountUserRole(userId: number, role: UserRole): Promise<AccountUser> {
  const user = accountUsers.find((item) => item.id === userId);
  if (!user) return Promise.reject(new Error('用户不存在'));
  accountUsers = accountUsers.map((item) => (item.id === userId ? { ...item, role } : item));
  return delay({ ...user, role });
}

function appendAudit(action: string, target: string, detail: string, metadata: Record<string, unknown> = {}) {
  auditId += 1;
  auditLogs = [
    {
      id: auditId,
      actorName: 'admin',
      action,
      target,
      detail,
      metadata,
      ipAddress: '127.0.0.1',
      createdAt: new Date().toISOString()
    },
    ...auditLogs
  ].slice(0, 200);
}

function commandBatchId(command: CommandResult) {
  return typeof command.params?.batch_id === 'string' ? command.params.batch_id : '';
}

function parseControlMode(value: unknown): Exclude<BulkTaskMode, 'unknown'> | null {
  return value === 'auto' || value === 'on' || value === 'off' ? value : null;
}

function inferTaskActuatorAndMode(command: CommandResult): { actuator: BulkTaskActuator; mode: BulkTaskMode } {
  const params = command.params ?? {};
  const motorMode = parseControlMode(params.motor_override);
  if (motorMode) {
    return { actuator: 'motor', mode: motorMode };
  }
  const lightMode = parseControlMode(params.light_override);
  if (lightMode) {
    return { actuator: 'light', mode: lightMode };
  }
  return { actuator: 'unknown', mode: 'unknown' };
}

function buildBulkTask(batchId: string, batchCommands: CommandResult[]): BulkTask {
  const rows = batchCommands
    .map((command) => {
      const device = devices.find((item) => item.id === command.deviceId);
      return {
        id: command.id,
        deviceId: command.deviceId,
        slotNo: device?.slotNo ?? command.deviceId,
        sn: device?.sn ?? `DEVICE-${command.deviceId}`,
        status: command.status,
        message: command.message,
        createdAt: command.createdAt,
        ackAt: command.ackAt
      };
    })
    .sort((a, b) => a.slotNo - b.slotNo);
  const first = batchCommands.slice().sort((a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime())[0];
  const latest = batchCommands
    .slice()
    .sort((a, b) => new Date(b.ackAt ?? b.createdAt).getTime() - new Date(a.ackAt ?? a.createdAt).getTime())[0];
  const { actuator, mode } = inferTaskActuatorAndMode(first);
  const total = rows.length;
  const queued = rows.filter((row) => row.status === 'queued').length;
  const sent = rows.filter((row) => row.status === 'sent').length;
  const acked = rows.filter((row) => row.status === 'acked').length;
  const failed = rows.filter((row) => row.status === 'failed').length;
  const finished = acked + failed;
  const status =
    failed > 0
      ? finished === total
        ? 'failed'
        : 'partial'
      : acked === total
        ? 'completed'
        : sent > 0
          ? 'running'
          : 'queued';
  const title = `${actuator === 'motor' ? '电机' : actuator === 'light' ? '补光灯' : '执行器'}${{ auto: '自动模式', on: '打开', off: '关闭', unknown: '' }[mode]}`;
  const logs = rows
    .flatMap((row) => [
      {
        ts: row.createdAt,
        level: 'info' as const,
        message: `槽位${row.slotNo}${row.sn}指令已入队`,
        deviceId: row.deviceId,
        slotNo: row.slotNo,
        sn: row.sn,
        commandId: row.id,
        status: 'queued' as const
      },
      ...(row.status === 'sent' || row.status === 'acked' || row.status === 'failed'
        ? [
            {
              ts: row.createdAt,
              level: 'info' as const,
              message: `槽位${row.slotNo}${row.sn}已被设备拉取`,
              deviceId: row.deviceId,
              slotNo: row.slotNo,
              sn: row.sn,
              commandId: row.id,
              status: 'sent' as const
            }
          ]
        : []),
      ...(row.ackAt
        ? [
            {
              ts: row.ackAt,
              level: row.status === 'failed' ? 'error' as const : 'success' as const,
              message: `槽位${row.slotNo}${row.sn}${row.status === 'failed' ? '执行失败' : '执行成功'}：${row.message}`,
              deviceId: row.deviceId,
              slotNo: row.slotNo,
              sn: row.sn,
              commandId: row.id,
              status: row.status
            }
          ]
        : [])
    ])
    .sort((a, b) => new Date(b.ts).getTime() - new Date(a.ts).getTime());

  return {
    batchId,
    title,
    actuator,
    mode,
    status,
    total,
    queued,
    sent,
    acked,
    failed,
    pending: total - finished,
    progress: total ? Number(((finished / total) * 100).toFixed(1)) : 0,
    executeAt: typeof first.params?.execute_at === 'string' ? first.params.execute_at : undefined,
    syncDelayMs: typeof first.params?.sync_delay_ms === 'number' ? first.params.sync_delay_ms : undefined,
    retryOf: typeof first.params?.retry_of === 'string' ? first.params.retry_of : undefined,
    createdAt: first.createdAt,
    latestAt: latest.ackAt ?? latest.createdAt,
    commands: rows,
    failedDevices: rows.filter((row) => row.status === 'failed'),
    logs
  };
}

function collectBulkTasks(): BulkTask[] {
  const groups = new Map<string, CommandResult[]>();
  for (const command of commands) {
    const batchId = commandBatchId(command);
    if (!batchId) continue;
    groups.set(batchId, [...(groups.get(batchId) ?? []), command]);
  }
  return Array.from(groups.entries())
    .map(([batchId, batchCommands]) => buildBulkTask(batchId, batchCommands))
    .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
}

export function mockFetchDevices(status?: string): Promise<DeviceListResponse> {
  const results = status ? devices.filter((device) => device.status === status) : devices;
  return delay({ count: results.length, results });
}

export function mockFetchDevice(deviceId: number): Promise<Device> {
  const device = devices.find((item) => item.id === deviceId);
  if (!device) return Promise.reject(new Error('设备不存在'));
  return delay(device);
}

export function mockFetchHistory(
  sensorId: number,
  params: { start: string; end: string; interval: HistoryInterval }
): Promise<PointsResponse> {
  const device = devices.find((item) => item.sensors.some((sensor) => sensor.id === sensorId));
  const sensor = device?.sensors.find((item) => item.id === sensorId);
  if (!device || !sensor) return Promise.reject(new Error('传感器不存在'));

  const start = new Date(params.start).getTime();
  const end = new Date(params.end).getTime();
  const step =
    params.interval === '1m'
      ? 60_000
      : params.interval === '5m'
        ? 5 * 60_000
        : params.interval === '1h'
          ? 60 * 60_000
          : 24 * 60 * 60_000;
  const points = Array.from({ length: Math.min(96, Math.max(8, Math.floor((end - start) / step))) }, (_, index) => {
    const t = start + index * step;
    const wave = Math.sin(index / 3) * ((sensor.max ?? 10) - (sensor.min ?? 0)) * 0.08;
    const drift = (index % 7) * 0.12;
    return {
      ts: new Date(t).toISOString(),
      value: Number(((sensor.latest?.value ?? 1) + wave + drift).toFixed(2))
    };
  });

  return delay({
    metric: sensor.name,
    sensor_id: sensor.id,
    device_id: device.id,
    interval: params.interval,
    points
  });
}

export function mockSendCommand(deviceId: number, payload: CommandPayload): Promise<CommandResult> {
  const device = devices.find((item) => item.id === deviceId);
  if (!device) return Promise.reject(new Error('设备不存在'));

  const commandName: Record<CommandType, string> = {
    reboot: '重启',
    upgrade: '固件升级',
    set_param: '参数设置'
  };
  const result: CommandResult = {
    id: `cmd-${Date.now()}`,
    deviceId,
    command: payload.type,
    params: payload.params,
    status: 'queued',
    message:
      payload.type === 'set_param' && (payload.params?.motor_override || payload.params?.light_override)
        ? '远程执行器控制指令已进入队列，等待设备 ACK'
        : `${commandName[payload.type]}指令已进入队列，等待设备 ACK`,
    createdAt: new Date().toISOString(),
    ackAt: null
  };
  commands = [result, ...commands].slice(0, 20);
  appendAudit('command_create', device.sn, '下发设备指令', { deviceId, type: payload.type, params: payload.params ?? {} });
  return delay(result);
}

export function mockSendBulkCommand(payload: {
  target: 'all' | 'online' | 'selected';
  actuator: 'motor' | 'light';
  mode: 'auto' | 'on' | 'off';
  device_ids?: number[];
  sync_delay_ms?: number;
}): Promise<BulkCommandResponse> {
  const targetDevices =
    payload.target === 'selected'
      ? devices.filter((device) => payload.device_ids?.includes(device.id))
      : payload.target === 'online'
        ? devices.filter((device) => device.status === 'online' || device.status === 'warning')
        : devices;
  if (!targetDevices.length) return Promise.reject(new Error('没有可下发的设备'));

  const paramKey = payload.actuator === 'motor' ? 'motor_override' : 'light_override';
  const actuatorLabel = payload.actuator === 'motor' ? '电机' : '补光灯';
  const modeLabel = { auto: '自动', on: '强制开', off: '强制关' }[payload.mode];
  const syncDelayMs = payload.sync_delay_ms ?? 3000;
  const executeAt = new Date(Date.now() + syncDelayMs).toISOString();
  const batchId = `mock-bulk-${Date.now()}`;
  const created: CommandResult[] = targetDevices.map((device, index) => {
    const status: CommandResult['status'] =
      device.status === 'offline' || index % 6 === 4
        ? 'failed'
        : index % 4 === 2
          ? 'sent'
          : index % 5 === 3
            ? 'queued'
            : 'acked';
    const createdAt = new Date(Date.now() - index * 1200).toISOString();
    return {
      id: `cmd-${Date.now()}-${device.id}`,
      deviceId: device.id,
      command: 'set_param' as const,
      params: {
        [paramKey]: payload.mode,
        batch_id: batchId,
        execute_at: executeAt,
        sync_delay_ms: syncDelayMs,
        sync: true
      },
      status,
      message:
        status === 'acked'
          ? '设备已确认执行'
          : status === 'failed'
            ? '设备执行失败，等待人工重试'
            : `批量${actuatorLabel}${modeLabel}同步指令已进入队列，预计${executeAt}同时执行`,
      createdAt,
      ackAt: status === 'acked' || status === 'failed' ? new Date(Date.now() + 2800 + index * 220).toISOString() : null
    };
  });
  commands = [...created, ...commands].slice(0, 60);
  appendAudit('command_create', `${created.length} 台设备`, `批量下发${actuatorLabel}${modeLabel}`, {
    target: payload.target,
    actuator: payload.actuator,
    mode: payload.mode,
    batchId,
    executeAt,
    syncDelayMs,
    deviceIds: targetDevices.map((device) => device.id)
  });
  return delay({
    count: created.length,
    batchId,
    executeAt,
    serverTime: new Date().toISOString(),
    commands: created,
    task: buildBulkTask(batchId, created)
  });
}

export function mockFetchBulkTasks(params: { limit?: number } = {}): Promise<BulkTaskListResponse> {
  const results = collectBulkTasks().slice(0, params.limit);
  return delay({ count: results.length, results });
}

export function mockRetryBulkTask(batchId: string): Promise<BulkCommandResponse> {
  const task = collectBulkTasks().find((item) => item.batchId === batchId);
  if (!task) return Promise.reject(new Error('批量任务不存在'));
  if (!task.failedDevices.length) return Promise.reject(new Error('没有失败板卡可重试'));
  const firstCommand = commands.find((command) => commandBatchId(command) === batchId);
  if (!firstCommand) return Promise.reject(new Error('无法识别原任务参数'));
  const { actuator, mode } = inferTaskActuatorAndMode(firstCommand);
  if (actuator === 'unknown' || mode === 'unknown') return Promise.reject(new Error('无法识别原任务参数'));
  const retryActuator: Exclude<BulkTaskActuator, 'unknown'> = actuator;
  const retryMode: Exclude<BulkTaskMode, 'unknown'> = mode;
  return mockSendBulkCommand({
    target: 'selected',
    actuator: retryActuator,
    mode: retryMode,
    device_ids: task.failedDevices.map((device) => device.deviceId)
  }).then((response) => {
    const retryCommands = response.commands.map((command) => ({
      ...command,
      params: { ...command.params, retry_of: batchId }
    }));
    commands = commands.map((command) => {
      const retryCommand = retryCommands.find((item) => item.id === command.id);
      return retryCommand ?? command;
    });
    const retryBatchId = response.batchId ?? commandBatchId(retryCommands[0]);
    return {
      ...response,
      commands: retryCommands,
      task: buildBulkTask(retryBatchId, retryCommands)
    };
  });
}

export function mockFetchCommands(deviceId: number): Promise<CommandResult[]> {
  return delay(commands.filter((command) => command.deviceId === deviceId));
}

export function mockFetchAlarms(params: { status?: string; level?: string } = {}): Promise<Alarm[]> {
  let results = alarms;
  if (params.status) {
    results = results.filter((alarm) => alarm.status === params.status);
  } else {
    results = results.filter((alarm) => alarm.status !== 'closed');
  }
  if (params.level) {
    results = results.filter((alarm) => alarm.level === params.level);
  }
  return delay(results);
}

export function mockAckAlarm(alarmId: number): Promise<Alarm> {
  alarms = alarms.map((alarm) => (alarm.id === alarmId ? { ...alarm, status: 'acknowledged' } : alarm));
  const alarm = alarms.find((item) => item.id === alarmId);
  if (!alarm) return Promise.reject(new Error('告警不存在'));
  return delay(alarm);
}

export function mockSimulateRealtime(sensorId: number): Promise<RealtimeMessage> {
  const device = devices.find((item) => item.sensors.some((sensor) => sensor.id === sensorId));
  const sensor = device?.sensors.find((item) => item.id === sensorId);
  if (!device || !sensor) return Promise.reject(new Error('传感器不存在'));

  const latest = sensor.latest?.value ?? 1;
  const next = Number((latest + (Math.random() - 0.45) * 1.8).toFixed(2));
  const ts = new Date().toISOString();
  const status = device.status === 'maintenance' ? 'maintenance' : 'online';

  devices = devices.map((item) =>
    item.id === device.id
      ? {
          ...item,
          status,
          lastSeen: ts,
          sensors: item.sensors.map((candidate) =>
            candidate.id === sensor.id ? { ...candidate, latest: { ts, value: next } } : candidate
          )
        }
      : item
  );

  return delay({
    deviceId: device.id,
    sensorId: sensor.id,
    code: sensor.code,
    name: sensor.name,
    unit: sensor.unit,
    value: next,
    ts,
    status
  });
}

export function mockFetchAuditLogs(params: { action?: string } = {}): Promise<AuditLog[]> {
  const results = params.action ? auditLogs.filter((log) => log.action === params.action) : auditLogs;
  return delay(results);
}

export function mockFetchRules(): Promise<RuleConfig[]> {
  return delay(
    devices.flatMap((device) =>
      device.sensors
        .filter((sensor) => !['motor', 'fan', 'ventilation', 'lamp', 'led'].includes(sensor.code))
        .map((sensor) => ({
          id: sensor.id,
          deviceId: device.id,
          deviceName: device.sn,
          slotNo: device.slotNo,
          code: sensor.code,
          name: sensor.name,
          unit: sensor.unit,
          description: sensor.description,
          min: sensor.min ?? null,
          max: sensor.max ?? null,
          sampleRate: device.sampleRate
        }))
    )
  );
}

export function mockUpdateRule(sensorId: number, payload: { min?: number | null; max?: number | null }): Promise<RuleConfig> {
  const device = devices.find((item) => item.sensors.some((sensor) => sensor.id === sensorId));
  const sensor = device?.sensors.find((item) => item.id === sensorId);
  if (!device || !sensor) return Promise.reject(new Error('规则不存在'));
  if (payload.min != null && payload.max != null && payload.min >= payload.max) {
    return Promise.reject(new Error('上限必须大于下限'));
  }
  const before = { min: sensor.min ?? null, max: sensor.max ?? null };
  devices = devices.map((item) =>
    item.id === device.id
      ? {
          ...item,
          sensors: item.sensors.map((candidate) =>
            candidate.id === sensorId
              ? {
                  ...candidate,
                  min: payload.min === undefined ? candidate.min : payload.min ?? undefined,
                  max: payload.max === undefined ? candidate.max : payload.max ?? undefined
                }
              : candidate
          )
        }
      : item
  );
  const nextDevice = devices.find((item) => item.id === device.id)!;
  const nextSensor = nextDevice.sensors.find((item) => item.id === sensorId)!;
  appendAudit('rule_update', `${nextDevice.sn}/${nextSensor.code}`, '更新传感器阈值规则', {
    before,
    after: { min: nextSensor.min ?? null, max: nextSensor.max ?? null }
  });
  return delay({
    id: nextSensor.id,
    deviceId: nextDevice.id,
    deviceName: nextDevice.sn,
    slotNo: nextDevice.slotNo,
    code: nextSensor.code,
    name: nextSensor.name,
    unit: nextSensor.unit,
    description: nextSensor.description,
    min: nextSensor.min ?? null,
    max: nextSensor.max ?? null,
    sampleRate: nextDevice.sampleRate
  });
}

export function nextRealtimeMessage(): RealtimeMessage {
  const onlineDevices = devices.filter((device) => device.status !== 'offline');
  const device = onlineDevices[Math.floor(Math.random() * onlineDevices.length)];
  const sensor = device.sensors[Math.floor(Math.random() * device.sensors.length)];
  const latest = sensor.latest?.value ?? 1;
  const next = Number((latest + (Math.random() - 0.45) * 1.8).toFixed(2));
  const ts = new Date().toISOString();

  devices = devices.map((item) =>
    item.id === device.id
      ? {
          ...item,
          status: item.status === 'maintenance' ? 'maintenance' : 'online',
          lastSeen: ts,
          sensors: item.sensors.map((candidate) =>
            candidate.id === sensor.id ? { ...candidate, latest: { ts, value: next } } : candidate
          )
        }
      : item
  );

  return {
    deviceId: device.id,
    sensorId: sensor.id,
    code: sensor.code,
    name: sensor.name,
    unit: sensor.unit,
    value: next,
    ts,
    status: device.status === 'maintenance' ? 'maintenance' : 'online'
  };
}
