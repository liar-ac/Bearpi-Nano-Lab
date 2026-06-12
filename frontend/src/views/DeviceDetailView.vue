<script setup lang="ts">
import { ArrowLeft, Fan, Gauge, History, Lightbulb, Power, RefreshCcw, Settings, ShieldCheck, Zap } from 'lucide-vue-next';
import { ElMessage, ElMessageBox } from 'element-plus';
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import StatusBadge from '@/components/StatusBadge.vue';
import { fetchCommands, fetchDevice, sendCommand } from '@/api/lab';
import { useAuthStore } from '@/stores/auth';
import type { CommandPayload, CommandResult, CommandType, Device } from '@/types/domain';
import { formatDateTime, formatValue, relativeTime } from '@/utils/format';

const route = useRoute();
const auth = useAuthStore();
const deviceId = computed(() => Number(route.params.deviceId));
const device = ref<Device | null>(null);
const commandLogs = ref<CommandResult[]>([]);
const loading = ref(false);
const error = ref('');

type OverrideKey = 'motor_override' | 'light_override';
type OverrideMode = 'auto' | 'on' | 'off';

const commandLabel: Record<CommandType, string> = {
  reboot: '重启',
  upgrade: '固件升级',
  set_param: '参数设置'
};

const overrideModeLabels: Record<OverrideMode, string> = {
  auto: '自动',
  on: '强制开',
  off: '强制关'
};

const actuatorState = ref<Record<OverrideKey, OverrideMode>>({
  motor_override: 'auto',
  light_override: 'auto'
});

const actuatorControls = [
  {
    key: 'motor_override' as const,
    label: '通风电机',
    description: '温度 > 32℃ 或湿度 > 75% 时自动开启',
    icon: Fan
  },
  {
    key: 'light_override' as const,
    label: '补光灯',
    description: '光照 < 20lx 时自动开启',
    icon: Lightbulb
  }
];

const overrideModes: OverrideMode[] = ['auto', 'on', 'off'];
const actuatorSensorCodes = new Set(['motor', 'fan', 'ventilation', 'lamp', 'led', 'fill_light']);

const sensorRows = computed(() =>
  device.value?.sensors.filter((sensor) => !actuatorSensorCodes.has(sensor.code)) ?? []
);
const actuatorTelemetry = computed(() =>
  device.value?.sensors.filter((sensor) => actuatorSensorCodes.has(sensor.code)) ?? []
);
const thresholdBreaches = computed(() =>
  sensorRows.value.filter((sensor) => {
    const value = sensor.latest?.value;
    if (typeof value !== 'number') return false;
    return (typeof sensor.max === 'number' && value > sensor.max) || (typeof sensor.min === 'number' && value < sensor.min);
  })
);
const deviceHealthCards = computed(() => {
  const current = device.value;
  if (!current) return [];
  return [
    {
      label: '采样频率',
      value: `${current.sampleRate}s`,
      detail: '设备上报周期',
      icon: Gauge,
      tone: 'cyan'
    },
    {
      label: '阈值越界',
      value: `${thresholdBreaches.value.length}`,
      detail: thresholdBreaches.value.length ? thresholdBreaches.value.map((sensor) => sensor.name).join(' / ') : '全部正常',
      icon: ShieldCheck,
      tone: thresholdBreaches.value.length ? 'amber' : 'green'
    },
    {
      label: '入库状态',
      value: current.lastSeen ? '已入库' : '待上报',
      detail: current.lastSeen ? `最近${relativeTime(current.lastSeen)}` : '等待HTTP上报',
      icon: Zap,
      tone: current.lastSeen ? 'green' : 'amber'
    }
  ];
});

const controlStrategies = computed(() => [
  {
    name: '温湿度通风策略',
    condition: '温度 > 32℃ 或湿度 > 75%',
    target: '通风电机',
    action: '自动开启通风；恢复正常后关闭',
    mode: actuatorState.value.motor_override
  },
  {
    name: '低光照补光策略',
    condition: '光照 < 20lx',
    target: '补光灯',
    action: '自动开启补光；光照恢复后关闭',
    mode: actuatorState.value.light_override
  }
]);

async function load() {
  loadAbort?.abort();
  const controller = new AbortController();
  loadAbort = controller;
  loading.value = true;
  error.value = '';
  try {
    device.value = await fetchDevice(deviceId.value);
    if (controller.signal.aborted) return;
    commandLogs.value = await fetchCommands(deviceId.value);
    if (controller.signal.aborted) return;
    syncActuatorState(commandLogs.value);
  } catch (cause) {
    if (controller.signal.aborted) return;
    error.value = cause instanceof Error ? cause.message : '设备详情加载失败';
  } finally {
    if (!controller.signal.aborted) loading.value = false;
  }
}

function isOverrideMode(value: unknown): value is OverrideMode {
  return value === 'auto' || value === 'on' || value === 'off';
}

function syncActuatorState(logs: CommandResult[]) {
  const next = { ...actuatorState.value };
  const seen = new Set<OverrideKey>();
  if (!Array.isArray(logs)) return;
  for (const command of logs) {
    if (command.command !== 'set_param' || !command.params) continue;
    for (const key of Object.keys(next) as OverrideKey[]) {
      if (seen.has(key)) continue;
      const value = command.params[key];
      if (isOverrideMode(value)) {
        next[key] = value;
        seen.add(key);
      }
    }
  }
  actuatorState.value = next;
}

function commandDisplay(command: CommandResult) {
  if (command.command !== 'set_param' || !command.params) {
    return commandLabel[command.command];
  }

  const parts = [];
  if (isOverrideMode(command.params.motor_override)) {
    parts.push(`电机${overrideModeLabels[command.params.motor_override]}`);
  }
  if (isOverrideMode(command.params.light_override)) {
    parts.push(`补光灯${overrideModeLabels[command.params.light_override]}`);
  }
  if (command.params.sample_rate) {
    parts.push(`采样率 ${command.params.sample_rate}s`);
  }
  return parts.length ? parts.join(' / ') : commandLabel[command.command];
}

function sensorThreshold(row: Device['sensors'][number]) {
  const parts = [];
  if (typeof row.min === 'number') parts.push(`下限 ${formatValue(row.min, row.unit)}`);
  if (typeof row.max === 'number') parts.push(`上限 ${formatValue(row.max, row.unit)}`);
  return parts.length ? parts.join(' / ') : '未设置';
}

function sensorState(row: Device['sensors'][number]) {
  const value = row.latest?.value;
  if (typeof value !== 'number') return 'unknown';
  if (typeof row.max === 'number' && value > row.max) return 'high';
  if (typeof row.min === 'number' && value < row.min) return 'low';
  return 'normal';
}

async function runCommand(payload: CommandPayload, displayName = commandLabel[payload.type]) {
  if (!auth.canCommand) {
    ElMessage.warning('当前角色没有指令下发权限');
    return null;
  }

  if (!device.value) return null;
  try {
    await ElMessageBox.confirm(
      `确认向 ${device.value.sn} 下发「${displayName}」指令？`,
      '设备指令确认',
      {
        type: 'warning',
        confirmButtonText: '确认下发',
        cancelButtonText: '取消'
      }
    );
    const result = await sendCommand(deviceId.value, payload);
    commandLogs.value = [result, ...(Array.isArray(commandLogs.value) ? commandLogs.value : [])].slice(0, 20);
    ElMessage.success(result.message);
    return result;
  } catch (cause) {
    if (cause !== 'cancel') {
      ElMessage.error(cause instanceof Error ? cause.message : '指令下发失败');
    }
    return null;
  }
}

async function setActuatorOverride(key: OverrideKey, mode: OverrideMode) {
  const control = actuatorControls.find((item) => item.key === key);
  const result = await runCommand(
    { type: 'set_param', params: { [key]: mode } },
    `${control?.label ?? '执行器'}${overrideModeLabels[mode]}`
  );
  if (result) {
    actuatorState.value = { ...actuatorState.value, [key]: mode };
  }
}

let refreshTimer: number | null = null;
let loadAbort: AbortController | null = null;

onMounted(() => {
  void load();
  refreshTimer = window.setInterval(() => {
    void load();
  }, 10000);
});

onBeforeUnmount(() => {
  if (refreshTimer !== null) {
    window.clearInterval(refreshTimer);
    refreshTimer = null;
  }
  loadAbort?.abort();
});

watch(deviceId, () => {
  void load();
});
</script>

<template>
  <div class="stack gap-lg">
    <RouterLink class="text-link" to="/dashboard">
      <ArrowLeft :size="16" />
      返回总览
    </RouterLink>

    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />

    <template v-if="device">
      <section class="detail-hero">
        <div>
          <div class="hero-title-row">
            <h2>{{ device.sn }}</h2>
            <StatusBadge :status="device.status" />
          </div>
          <p>槽位 {{ device.slotNo }} / {{ device.model }} / {{ device.firmwareVersion }} / {{ device.location }}</p>
          <div class="detail-meta-strip">
            <span>负责人：{{ device.member }}</span>
            <span>采样率：{{ device.sampleRate }} 秒</span>
            <span>最近上报：{{ relativeTime(device.lastSeen) }}</span>
            <span>IP：{{ device.ipAddress ?? '未登记' }}</span>
          </div>
        </div>
        <div class="command-row">
          <el-button type="danger" plain :disabled="!auth.canCommand" @click="runCommand({ type: 'reboot' })">
            <Power :size="17" />
            重启
          </el-button>
          <el-button type="warning" plain :disabled="!auth.canCommand" @click="runCommand({ type: 'upgrade' })">
            <RefreshCcw :size="17" />
            升级固件
          </el-button>
          <el-button
            type="primary"
            plain
            :disabled="!auth.canCommand"
            @click="runCommand({ type: 'set_param', params: { sample_rate: 1 } }, '设置采样率')"
          >
            <Settings :size="17" />
            设置采样率
          </el-button>
        </div>
      </section>

      <el-alert
        v-if="!auth.canCommand"
        title="当前为只读权限：可以查看设备、实时数据和历史数据，不能下发重启/升级/参数设置指令。"
        type="info"
        show-icon
        :closable="false"
      />

      <section class="device-health-grid">
        <article v-for="card in deviceHealthCards" :key="card.label" class="device-health-card" :class="`tone-${card.tone}`">
          <span class="metric-icon">
            <component :is="card.icon" :size="19" />
          </span>
          <div>
            <small>{{ card.label }}</small>
            <strong>{{ card.value }}</strong>
            <p>{{ card.detail }}</p>
          </div>
        </article>
      </section>

      <section class="device-context-grid">
        <el-card class="context-card" shadow="never">
          <template #header>
            <div class="section-heading">
              <div>
                <p class="eyebrow">Device Context</p>
                <h2>设备上下文</h2>
              </div>
            </div>
          </template>
          <div class="context-grid">
            <span><small>实验室</small><strong>{{ device.labId }}</strong></span>
            <span><small>注册时间</small><strong>{{ formatDateTime(device.registerTime) }}</strong></span>
            <span><small>异常原因</small><strong>{{ device.abnormalReason ?? '无异常' }}</strong></span>
          </div>
        </el-card>
      </section>

      <el-card shadow="never">
        <template #header>
          <div class="section-heading">
            <div>
              <p class="eyebrow">Sensors</p>
              <h2>传感器</h2>
            </div>
            <span class="role-hint">IA1 环境数据进入阈值策略和历史曲线</span>
          </div>
        </template>

        <el-table :data="sensorRows" stripe empty-text="暂无环境传感器">
          <el-table-column label="传感器" min-width="180">
            <template #default="{ row }">
              <strong>{{ row.name }}</strong>
              <small>{{ row.description }}</small>
            </template>
          </el-table-column>
          <el-table-column prop="code" label="Code" width="110" />
          <el-table-column label="最新值" width="140">
            <template #default="{ row }">{{ formatValue(row.latest?.value, row.unit) }}</template>
          </el-table-column>
          <el-table-column label="阈值" min-width="180">
            <template #default="{ row }">{{ sensorThreshold(row) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <el-tag
                :type="sensorState(row) === 'normal' ? 'success' : sensorState(row) === 'unknown' ? 'info' : 'danger'"
                effect="dark"
              >
                {{ sensorState(row) === 'normal' ? '正常' : sensorState(row) === 'unknown' ? '未知' : '越界' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="更新时间" min-width="180">
            <template #default="{ row }">{{ formatDateTime(row.latest?.ts) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="190" fixed="right">
            <template #default="{ row }">
              <div class="table-actions">
                <RouterLink class="icon-text-link" :to="`/devices/${device.id}/sensors/${row.id}/realtime`">
                  <Zap :size="16" />
                  实时
                </RouterLink>
                <RouterLink class="icon-text-link" :to="`/devices/${device.id}/sensors/${row.id}/history`">
                  <History :size="16" />
                  历史
                </RouterLink>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="section-heading">
            <div>
              <p class="eyebrow">Actuators</p>
              <h2>执行器</h2>
            </div>
            <span class="role-hint">自动模式按阈值运行；强制模式会覆盖当前环境判断</span>
          </div>
        </template>

        <div class="actuator-grid">
          <section v-for="control in actuatorControls" :key="control.key" class="actuator-panel">
            <div class="actuator-copy">
              <span class="metric-icon tone-green actuator-icon">
                <component :is="control.icon" :size="20" />
              </span>
              <div>
                <strong>{{ control.label }}</strong>
                <small>{{ control.description }}</small>
              </div>
            </div>
            <el-button-group>
              <el-button
                v-for="mode in overrideModes"
                :key="mode"
                size="small"
                :type="
                  actuatorState[control.key] === mode
                    ? mode === 'on'
                      ? 'success'
                      : mode === 'off'
                        ? 'danger'
                        : 'primary'
                    : ''
                "
                :plain="actuatorState[control.key] !== mode"
                :disabled="!auth.canCommand"
                @click="setActuatorOverride(control.key, mode)"
              >
                {{ overrideModeLabels[mode] }}
              </el-button>
            </el-button-group>
          </section>
        </div>

        <div v-if="actuatorTelemetry.length" class="actuator-telemetry">
          <p class="eyebrow">Actuator Telemetry</p>
          <div class="context-grid">
            <span v-for="sensor in actuatorTelemetry" :key="sensor.id">
              <small>{{ sensor.name }}</small>
              <strong>{{ formatValue(sensor.latest?.value, sensor.unit) }}</strong>
            </span>
          </div>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="section-heading">
            <div>
              <p class="eyebrow">Control Strategy</p>
              <h2>控制策略</h2>
            </div>
            <span class="role-hint">自动策略由后端/设备侧阈值判断；人工强制会通过指令覆盖</span>
          </div>
        </template>

        <div class="strategy-grid">
          <section v-for="strategy in controlStrategies" :key="strategy.name" class="strategy-card">
            <div>
              <strong>{{ strategy.name }}</strong>
              <small>{{ strategy.condition }}</small>
            </div>
            <div>
              <span>目标：{{ strategy.target }}</span>
              <span>动作：{{ strategy.action }}</span>
            </div>
            <el-tag :type="strategy.mode === 'auto' ? 'primary' : strategy.mode === 'on' ? 'success' : 'danger'" effect="dark">
              当前 {{ overrideModeLabels[strategy.mode] }}
            </el-tag>
          </section>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="section-heading">
            <div>
              <p class="eyebrow">Command Tracking</p>
              <h2>指令记录</h2>
            </div>
            <span class="role-hint">后端对接后展示 queued / sent / acked / failed 全链路状态</span>
          </div>
        </template>
        <el-table :data="commandLogs" empty-text="暂无指令记录">
          <el-table-column label="指令" min-width="190">
            <template #default="{ row }">{{ commandDisplay(row) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="row.status === 'failed' ? 'danger' : row.status === 'queued' ? 'warning' : 'success'">
                {{ row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="message" label="消息" min-width="260" />
          <el-table-column label="创建时间" min-width="180">
            <template #default="{ row }">{{ formatDateTime(row.createdAt) }}</template>
          </el-table-column>
          <el-table-column label="ACK 时间" min-width="180">
            <template #default="{ row }">{{ formatDateTime(row.ackAt) }}</template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>

    <el-skeleton v-else-if="loading" :rows="8" animated />
  </div>
</template>

<style scoped>
.device-health-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.device-health-card {
  display: flex;
  gap: 12px;
  min-height: 104px;
  padding: 14px;
  border: 1px solid rgba(188, 238, 255, 0.13);
  border-radius: var(--radius);
  background:
    linear-gradient(135deg, rgba(56, 189, 248, 0.055), transparent 52%),
    var(--panel);
  box-shadow: var(--shadow-soft);
}

.device-health-card .metric-icon {
  color: var(--cyan);
  background: rgba(56, 189, 248, 0.12);
}

.device-health-card.tone-green .metric-icon {
  color: var(--green);
  background: rgba(45, 212, 125, 0.12);
}

.device-health-card.tone-amber .metric-icon {
  color: var(--amber);
  background: rgba(246, 184, 75, 0.12);
}

.device-health-card.tone-red .metric-icon {
  color: var(--red);
  background: rgba(255, 104, 116, 0.12);
}

.device-health-card small,
.device-health-card strong,
.device-health-card p {
  display: block;
  margin: 0;
}

.device-health-card small {
  color: var(--text-muted);
}

.device-health-card strong {
  margin-top: 6px;
  font-size: 26px;
  line-height: 1;
}

.device-health-card p {
  margin-top: 8px;
  color: var(--text-subtle);
  line-height: 1.45;
}

@media (max-width: 760px) {
  .device-health-grid {
    grid-template-columns: 1fr;
  }
}
</style>
