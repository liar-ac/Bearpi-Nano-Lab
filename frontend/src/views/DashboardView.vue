<script setup lang="ts">
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Cpu,
  Database,
  Fan,
  Lightbulb,
  RadioTower,
  Send,
  Server,
  ShieldCheck,
  Siren,
  Wifi
} from 'lucide-vue-next';
import { computed, onBeforeUnmount, onMounted } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import AiQuery from '@/components/AiQuery.vue';
import BoardGrid from '@/components/BoardGrid.vue';
import EmptyState from '@/components/EmptyState.vue';
import LabCapacityGrid from '@/components/LabCapacityGrid.vue';
import MetricCard from '@/components/MetricCard.vue';
import { sendBulkCommand } from '@/api/lab';
import { realtimeState, realtimeStatusLabel, subscribeRealtime } from '@/api/realtime';
import { useAuthStore } from '@/stores/auth';
import { useDeviceStore } from '@/stores/devices';
import type { Device, DeviceStatus } from '@/types/domain';
import { formatValue, relativeTime, statusLabel } from '@/utils/format';

const store = useDeviceStore();
const auth = useAuthStore();
let unsubscribe: (() => void) | null = null;
let refreshTimer: number | null = null;

const filters: Array<{ label: string; value: DeviceStatus | 'all' }> = [
  { label: '全部', value: 'all' },
  { label: '在线', value: 'online' },
  { label: '异常', value: 'warning' },
  { label: '维护中', value: 'maintenance' },
  { label: '离线', value: 'offline' }
];

const onlineRate = computed(() => {
  if (!store.devices.length) return '0%';
  return `${Math.round((store.statusCounts.online / store.devices.length) * 100)}%`;
});

const realtimeTone = computed(() => {
  if (realtimeState.status === 'online' || realtimeState.status === 'mock') return 'good';
  if (realtimeState.status === 'connecting' || realtimeState.status === 'reconnecting') return 'warn';
  return 'bad';
});

const priorityDevices = computed(() =>
  store.devices
    .map((device) => ({
      device,
      score: riskScore(device),
      reasons: riskReasons(device)
    }))
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 6)
);

const incidentCount = computed(() => priorityDevices.value.length);
const controllableDevices = computed(() =>
  store.devices.filter((device) => device.status === 'online' || device.status === 'warning')
);

onMounted(async () => {
  await store.loadDevices({ status: 'all' });
  unsubscribe = subscribeRealtime(store.applyRealtime);
  refreshTimer = window.setInterval(() => {
    void store.loadDevices({ status: 'all' });
  }, 10_000);
});

onBeforeUnmount(() => {
  unsubscribe?.();
  if (refreshTimer !== null) {
    window.clearInterval(refreshTimer);
  }
});

function riskScore(device: Device) {
  let score = 0;
  if (device.status === 'offline') score += 100;
  if (device.status === 'warning') score += 80;
  if (device.status === 'maintenance') score += 35;
  if (isStale(device)) score += 20;
  score += thresholdBreaches(device).length * 18;
  return score;
}

function riskReasons(device: Device) {
  const reasons: string[] = [];
  if (device.status !== 'online') reasons.push(statusLabel[device.status]);
  if (device.abnormalReason) reasons.push(device.abnormalReason);
  if (isStale(device)) reasons.push(`上报延迟：${relativeTime(device.lastSeen)}`);
  reasons.push(...thresholdBreaches(device));
  return Array.from(new Set(reasons)).slice(0, 3);
}

function thresholdBreaches(device: Device) {
  return device.sensors
    .filter((sensor) => typeof sensor.latest?.value === 'number')
    .flatMap((sensor) => {
      const value = sensor.latest?.value;
      if (typeof value !== 'number') return [];
      if (typeof sensor.max === 'number' && value > sensor.max) {
        return [`${sensor.name}高于阈值 ${formatValue(value, sensor.unit)}`];
      }
      if (typeof sensor.min === 'number' && value < sensor.min) {
        return [`${sensor.name}低于阈值 ${formatValue(value, sensor.unit)}`];
      }
      return [];
    });
}

function isStale(device: Device) {
  if (!device.lastSeen || device.status === 'offline') return false;
  const diff = Date.now() - new Date(device.lastSeen).getTime();
  return Number.isFinite(diff) && diff > 2 * 60_000;
}

async function runBulkControl(actuator: 'motor' | 'light', mode: 'auto' | 'on' | 'off') {
  if (!auth.canCommand) {
    ElMessage.warning('当前角色没有批量控制权限');
    return;
  }
  const actuatorLabel = actuator === 'motor' ? '电机' : '补光灯';
  const modeLabel = { auto: '自动模式', on: '同时打开', off: '同时关闭' }[mode];
  try {
    await ElMessageBox.confirm(
      `确认向 ${controllableDevices.value.length} 台在线/异常板卡下发「${actuatorLabel}${modeLabel}」？`,
      '批量控制确认',
      {
        type: 'warning',
        confirmButtonText: '确认下发',
        cancelButtonText: '取消'
      }
    );
    const result = await sendBulkCommand({ target: 'online', actuator, mode });
    const executeTime = result.executeAt ? new Date(result.executeAt).toLocaleTimeString() : '';
    ElMessage.success(`已创建${result.count}条同步控制指令${executeTime ? `，预计${executeTime}同时执行` : ''}`);
  } catch (cause) {
    if (cause !== 'cancel') {
      ElMessage.error(cause instanceof Error ? cause.message : '批量控制失败');
    }
  }
}
</script>

<template>
  <div class="stack gap-lg">
    <section class="ops-overview priority-overview">
      <div>
        <p class="eyebrow">Incident First Console</p>
        <h2>异常优先值班台</h2>
        <p>只有最近真实上报过的板卡才会出现在这里；没有板子接入时，总览保持空状态。</p>
      </div>
      <div class="ops-status-grid">
        <span><ShieldCheck :size="16" /> JWT 已启用</span>
        <span><Database :size="16" /> SQLite</span>
        <span :class="`runtime-${realtimeTone}`"><Activity :size="16" /> {{ realtimeStatusLabel[realtimeState.status] }}</span>
        <span><RadioTower :size="16" /> HTTP网关就绪</span>
      </div>
      <div style="margin-top:10px;">
        <AiQuery />
      </div>
    </section>

    <section class="dashboard-summary">
      <MetricCard
        label="待处理设备"
        :value="incidentCount"
        :detail="incidentCount ? '按风险优先级排序' : '当前无高优先级风险'"
        tone="red"
        :icon="Siren"
      />
      <MetricCard label="在线率" :value="onlineRate" detail="基于当前接入设备" tone="green" :icon="Wifi" />
      <MetricCard
        label="实时链路"
        :value="realtimeStatusLabel[realtimeState.status]"
        :detail="realtimeState.lastMessageAt ? `最近消息 ${relativeTime(realtimeState.lastMessageAt)}` : '等待实时数据'"
        tone="cyan"
        :icon="Activity"
      />
      <MetricCard label="接入检测" value="实时" detail="超过活跃窗口自动隐藏" tone="violet" :icon="Cpu" />
    </section>

    <section class="bulk-control-panel">
      <div>
        <p class="eyebrow">Multi Board Control</p>
        <h2>多板同步控制</h2>
        <p>向当前在线/异常板卡批量下发执行器指令，设备端继续通过原有拉取指令和 ACK 流程执行。</p>
      </div>
      <div class="bulk-control-grid">
        <section class="bulk-actuator">
          <div class="bulk-actuator-title">
            <Fan :size="19" />
            <strong>通风电机</strong>
            <small>{{ controllableDevices.length }} 台可控</small>
          </div>
          <el-button-group>
            <el-button type="success" :disabled="!controllableDevices.length || !auth.canCommand" @click="runBulkControl('motor', 'on')">
              <Send :size="15" />
              全部打开
            </el-button>
            <el-button :disabled="!controllableDevices.length || !auth.canCommand" @click="runBulkControl('motor', 'auto')">自动</el-button>
            <el-button type="danger" plain :disabled="!controllableDevices.length || !auth.canCommand" @click="runBulkControl('motor', 'off')">
              全部关闭
            </el-button>
          </el-button-group>
        </section>
        <section class="bulk-actuator">
          <div class="bulk-actuator-title">
            <Lightbulb :size="19" />
            <strong>补光灯</strong>
            <small>{{ controllableDevices.length }} 台可控</small>
          </div>
          <el-button-group>
            <el-button type="success" :disabled="!controllableDevices.length || !auth.canCommand" @click="runBulkControl('light', 'on')">
              <Send :size="15" />
              全部照亮
            </el-button>
            <el-button :disabled="!controllableDevices.length || !auth.canCommand" @click="runBulkControl('light', 'auto')">自动</el-button>
            <el-button type="danger" plain :disabled="!controllableDevices.length || !auth.canCommand" @click="runBulkControl('light', 'off')">
              全部关闭
            </el-button>
          </el-button-group>
        </section>
      </div>
    </section>

    <section class="ops-priority-layout">
      <el-card class="incident-card" shadow="never">
        <template #header>
          <div class="section-heading">
            <div>
              <p class="eyebrow">Priority Queue</p>
              <h2>当前最需要处理</h2>
            </div>
            <el-tag :type="incidentCount ? 'danger' : 'success'" effect="dark">
              {{ incidentCount ? `${incidentCount} 项风险` : '全部稳定' }}
            </el-tag>
          </div>
        </template>

        <div v-if="priorityDevices.length" class="incident-list">
          <RouterLink
            v-for="item in priorityDevices"
            :key="item.device.id"
            class="incident-row"
            :to="`/devices/${item.device.id}`"
          >
            <span class="incident-rank">{{ item.score }}</span>
            <div>
              <strong>{{ item.device.sn }}</strong>
              <small>{{ item.reasons.join(' / ') }}</small>
            </div>
            <span>{{ relativeTime(item.device.lastSeen) }}</span>
          </RouterLink>
        </div>
        <EmptyState
          v-else
          title="当前没有接入板卡"
          detail="小熊派连接热点并上报 telemetry 后，会自动注册并显示在这里。"
        />
      </el-card>

      <el-card class="ops-health-card" shadow="never">
        <template #header>
          <div class="section-heading">
            <div>
              <p class="eyebrow">Runtime Health</p>
              <h2>运行链路健康度</h2>
            </div>
          </div>
        </template>
        <div class="health-steps">
          <span class="good"><Cpu :size="16" /> 设备接入 {{ store.devices.length }}</span>
          <span class="good"><Server :size="16" /> Django API</span>
          <span :class="realtimeTone"><Activity :size="16" /> {{ realtimeStatusLabel[realtimeState.status] }}</span>
          <span class="good"><RadioTower :size="16" /> 本地HTTP网关</span>
        </div>
        <p class="health-note">
          {{ realtimeState.error || '实时通道正常时，设备上报会直接刷新状态卡、实时曲线和告警入口。' }}
        </p>
      </el-card>
    </section>

    <el-card class="flow-card" shadow="never">
      <div class="ops-band compact">
        <div>
          <p class="eyebrow">Runtime Flow</p>
          <h2>BearPi Nano -> HTTPJSON -> Django REST/Channels -> Vue</h2>
        </div>
        <div class="flow-items">
          <span><Cpu :size="16" /> 设备</span>
          <span><RadioTower :size="16" /> HTTPJSON</span>
          <span><Server :size="16" /> Django</span>
          <span><Activity :size="16" /> Vue 实时视图</span>
        </div>
      </div>
    </el-card>

    <section class="toolbar">
      <div>
        <h2>项目组重点板卡</h2>
        <p>这里只展示活跃接入的板卡；断开或停止上报后会自动从列表移除。</p>
      </div>
      <el-radio-group v-model="store.selectedStatus" size="large">
        <el-radio-button v-for="filter in filters" :key="filter.value" :label="filter.value">
          {{ filter.label }}
        </el-radio-button>
      </el-radio-group>
    </section>

    <el-alert v-if="store.error" :title="store.error" type="error" show-icon :closable="false" />

    <div v-if="store.loading && store.devices.length === 0" class="board-grid skeleton-grid" aria-hidden="true">
      <div v-for="n in 4" :key="n" class="skeleton-card" />
    </div>
    <EmptyState
      v-else-if="!store.loading && store.filteredDevices.length === 0"
      title="当前没有接入板卡"
      detail="烧录后的开发板开始上报数据后，会自动出现在总览中。"
    />
    <BoardGrid v-else :devices="store.filteredDevices" />

    <el-card class="lab-grid-card" shadow="never">
      <template #header>
        <div class="section-heading">
          <div>
            <p class="eyebrow">Active Slots</p>
            <h2>活跃接入槽位</h2>
          </div>
          <el-tag type="info" effect="dark">仅显示实时接入状态</el-tag>
        </div>
      </template>
      <LabCapacityGrid v-if="store.devices.length" :slots="store.labSlots" :filter="store.selectedStatus" />
      <EmptyState v-else title="暂无活跃槽位" detail="没有板卡上报时，不展示任何默认设备。" />
    </el-card>
  </div>
</template>

<style scoped>
.skeleton-grid {
  margin-top: 4px;
}

.skeleton-card {
  min-height: 304px;
  border: 1px solid rgba(188, 238, 255, 0.1);
  border-radius: 6px;
  background:
    linear-gradient(110deg, rgba(255, 255, 255, 0.03) 0%, rgba(255, 255, 255, 0.06) 50%, rgba(255, 255, 255, 0.03) 100%),
    rgba(17, 26, 34, 0.6);
  background-size: 480px 100%;
  animation: shimmer 1.6s linear infinite;
}

.bulk-control-panel {
  display: grid;
  grid-template-columns: minmax(0, 0.75fr) minmax(520px, 1.25fr);
  align-items: center;
  gap: 18px;
  padding: 16px;
  border: 1px solid rgba(188, 238, 255, 0.14);
  border-radius: var(--radius);
  background:
    linear-gradient(90deg, rgba(45, 212, 125, 0.08), rgba(56, 189, 248, 0.055) 50%, transparent),
    var(--panel);
  box-shadow: var(--shadow-soft);
}

.bulk-control-panel h2,
.bulk-control-panel p {
  margin: 0;
}

.bulk-control-panel p:not(.eyebrow) {
  margin-top: 7px;
  color: var(--text-muted);
}

.bulk-control-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.bulk-actuator {
  display: grid;
  gap: 12px;
  min-height: 112px;
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: rgba(255, 255, 255, 0.03);
}

.bulk-actuator-title {
  display: flex;
  align-items: center;
  gap: 9px;
}

.bulk-actuator-title svg {
  color: var(--green);
}

.bulk-actuator-title small {
  margin-left: auto;
  color: var(--text-muted);
}

@media (max-width: 960px) {
  .bulk-control-panel,
  .bulk-control-grid {
    grid-template-columns: 1fr;
  }
}

@media (prefers-reduced-motion: reduce) {
  .skeleton-card {
    animation: none;
  }
}
</style>
