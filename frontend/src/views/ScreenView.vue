<script setup lang="ts">
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  Cpu,
  Database,
  RadioTower,
  ShieldCheck,
  Siren,
  Wifi
} from 'lucide-vue-next';
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { RouterLink } from 'vue-router';
import { fetchAlarms } from '@/api/lab';
import { realtimeState, realtimeStatusLabel, subscribeRealtime } from '@/api/realtime';
import { useDeviceStore } from '@/stores/devices';
import type { Alarm, Device } from '@/types/domain';
import { alarmLevelLabel, formatValue, relativeTime, statusLabel } from '@/utils/format';

const store = useDeviceStore();
const alarms = ref<Alarm[]>([]);
const now = ref(new Date());
const error = ref('');
const loading = ref(false);

let unsubscribe: (() => void) | null = null;
let clockTimer: number | null = null;
let refreshTimer: number | null = null;

const onlineRate = computed(() => {
  if (!store.devices.length) return 0;
  return Math.round((store.statusCounts.online / store.devices.length) * 100);
});

const realtimeTone = computed(() => {
  if (realtimeState.status === 'online' || realtimeState.status === 'mock') return 'good';
  if (realtimeState.status === 'connecting' || realtimeState.status === 'reconnecting') return 'warn';
  return 'bad';
});

const activeAlarms = computed(() => alarms.value.filter((alarm) => alarm.status === 'new'));
const criticalAlarms = computed(() => activeAlarms.value.filter((alarm) => alarm.level === 'critical'));
const recentAlarms = computed(() => alarms.value.slice(0, 6));

const riskDevices = computed(() =>
  store.devices
    .map((device) => ({
      device,
      score: riskScore(device),
      reasons: riskReasons(device)
    }))
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 8)
);

const slotPreview = computed(() => store.labSlots.filter((slot) => slot.device).slice(0, 72));

onMounted(() => {
  unsubscribe = subscribeRealtime(store.applyRealtime);
  clockTimer = window.setInterval(() => {
    now.value = new Date();
  }, 1000);
  refreshTimer = window.setInterval(() => {
    void load();
  }, 10000);
  void load();
});

onBeforeUnmount(() => {
  unsubscribe?.();
  if (clockTimer !== null) window.clearInterval(clockTimer);
  if (refreshTimer !== null) window.clearInterval(refreshTimer);
});

async function load() {
  loading.value = true;
  error.value = '';
  const [devicesResult, alarmsResult] = await Promise.allSettled([
    store.loadDevices({ status: 'all', includeInactive: true }),
    fetchAlarms({ limit: 100 })
  ]);

  if (devicesResult.status === 'rejected') {
    error.value = devicesResult.reason instanceof Error ? devicesResult.reason.message : '设备数据加载失败';
  } else if (store.error) {
    error.value = store.error;
  }

  if (alarmsResult.status === 'fulfilled') {
    alarms.value = alarmsResult.value;
  } else {
    error.value = alarmsResult.reason instanceof Error ? alarmsResult.reason.message : error.value || '告警数据加载失败';
  }
  loading.value = false;
}

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
  if (isStale(device)) reasons.push(`上报延迟 ${relativeTime(device.lastSeen)}`);
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
        return [`${sensor.name} ${formatValue(value, sensor.unit)}`];
      }
      if (typeof sensor.min === 'number' && value < sensor.min) {
        return [`${sensor.name} ${formatValue(value, sensor.unit)}`];
      }
      return [];
    });
}

function isStale(device: Device) {
  if (!device.lastSeen || device.status === 'offline') return false;
  const diff = Date.now() - new Date(device.lastSeen).getTime();
  return Number.isFinite(diff) && diff > 2 * 60_000;
}

function timeText() {
  return now.value.toLocaleTimeString('zh-CN', { hour12: false });
}

function dateText() {
  return now.value.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    weekday: 'short'
  });
}
</script>

<template>
  <main class="screen-page">
    <header class="screen-header">
      <div class="screen-title">
        <RouterLink class="back-link" to="/dashboard" aria-label="返回控制台">
          <ArrowLeft :size="18" />
        </RouterLink>
        <div>
          <p>BearPi Nano Lab / Real-Time Command Screen</p>
          <h1>小熊派 Nano 实验室实时大屏</h1>
        </div>
      </div>
      <div class="screen-clock">
        <strong>{{ timeText() }}</strong>
        <span>{{ dateText() }}</span>
      </div>
    </header>

    <p v-if="loading" class="screen-loading">正在刷新大屏数据...</p>

    <section class="screen-kpis">
      <article class="screen-kpi">
        <span class="kpi-icon good"><Wifi :size="24" /></span>
        <div>
          <p>在线率</p>
          <strong>{{ onlineRate }}%</strong>
          <small>{{ store.statusCounts.online }} / {{ store.devices.length }} 台在线</small>
        </div>
      </article>
      <article class="screen-kpi">
        <span class="kpi-icon warn"><Siren :size="24" /></span>
        <div>
          <p>待处理告警</p>
          <strong>{{ activeAlarms.length }}</strong>
          <small>严重 {{ criticalAlarms.length }} 条</small>
        </div>
      </article>
      <article class="screen-kpi">
        <span class="kpi-icon cyan"><RadioTower :size="24" /></span>
        <div>
          <p>实时通道</p>
          <strong>{{ realtimeStatusLabel[realtimeState.status] }}</strong>
          <small>{{ realtimeState.lastMessageAt ? relativeTime(realtimeState.lastMessageAt) : realtimeState.error || '等待数据' }}</small>
        </div>
      </article>
      <article class="screen-kpi">
        <span class="kpi-icon blue"><Database :size="24" /></span>
        <div>
          <p>本地入库</p>
          <strong>{{ store.devices.length }}</strong>
          <small>MySQL保存设备与历史数据</small>
        </div>
      </article>
    </section>

    <section class="screen-grid">
      <article class="screen-panel lab-panel">
        <div class="panel-heading">
          <div>
            <p>Active Slots</p>
            <h2>实验室接入槽位</h2>
          </div>
          <span>{{ slotPreview.length }} active</span>
        </div>
        <div v-if="slotPreview.length" class="slot-map">
          <span
            v-for="slot in slotPreview"
            :key="slot.slotNo"
            :class="['screen-slot', slot.status]"
            :title="slot.device?.sn"
          >
            {{ slot.slotNo }}
          </span>
        </div>
        <div v-else class="screen-empty">暂无活跃接入板卡</div>
      </article>

      <article class="screen-panel risk-panel">
        <div class="panel-heading">
          <div>
            <p>Priority Queue</p>
            <h2>异常优先队列</h2>
          </div>
          <span>{{ riskDevices.length }} risk</span>
        </div>
        <div v-if="riskDevices.length" class="risk-list">
          <RouterLink
            v-for="item in riskDevices"
            :key="item.device.id"
            class="risk-row"
            :to="`/devices/${item.device.id}`"
          >
            <strong>{{ item.score }}</strong>
            <div>
              <span>{{ item.device.sn }}</span>
              <small>{{ item.reasons.join(' / ') }}</small>
            </div>
            <em>{{ relativeTime(item.device.lastSeen) }}</em>
          </RouterLink>
        </div>
        <div v-else class="screen-empty">当前没有高优先级风险</div>
      </article>

      <article class="screen-panel alarms-panel">
        <div class="panel-heading">
          <div>
            <p>Alarm Stream</p>
            <h2>最近告警</h2>
          </div>
          <span>{{ recentAlarms.length }} shown</span>
        </div>
        <div v-if="recentAlarms.length" class="alarm-stream">
          <div v-for="alarm in recentAlarms" :key="alarm.id" class="screen-alarm" :class="`alarm-${alarm.level}`">
            <span>{{ alarmLevelLabel[alarm.level] }}</span>
            <div>
              <strong>{{ alarm.deviceName }}</strong>
              <small>{{ alarm.message }}</small>
            </div>
            <em>{{ relativeTime(alarm.ts) }}</em>
          </div>
        </div>
        <div v-else class="screen-empty">暂无告警</div>
      </article>

      <article class="screen-panel health-panel">
        <div class="panel-heading">
          <div>
            <p>Runtime Health</p>
            <h2>链路健康度</h2>
          </div>
          <span :class="`tone-${realtimeTone}`">{{ realtimeStatusLabel[realtimeState.status] }}</span>
        </div>
        <div class="health-flow">
          <span class="good"><Cpu :size="18" />设备接入 {{ store.devices.length }}</span>
          <span class="good"><ShieldCheck :size="18" />JWT 已启用</span>
          <span :class="realtimeTone"><Activity :size="18" />Channels {{ realtimeStatusLabel[realtimeState.status] }}</span>
          <span class="good"><RadioTower :size="18" />HTTPJSON</span>
        </div>
        <p v-if="error" class="screen-error">
          <AlertTriangle :size="18" />
          {{ error }}
        </p>
        <p v-else class="screen-note">
          大屏每 10 秒刷新 REST 统计，WebSocket 消息会实时更新设备状态和点位数据。
        </p>
      </article>
    </section>
  </main>
</template>

<style scoped>
.screen-page {
  min-height: 100vh;
  padding: clamp(18px, 2vw, 30px);
  background:
    linear-gradient(rgba(255, 255, 255, 0.02) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.015) 1px, transparent 1px),
    radial-gradient(circle at 16% 18%, rgba(56, 189, 248, 0.18), transparent 34vw),
    radial-gradient(circle at 78% 8%, rgba(45, 212, 125, 0.13), transparent 30vw),
    #071018;
  background-size: 56px 56px, 56px 56px, auto, auto, auto;
  color: var(--text);
}

.screen-header,
.screen-title,
.screen-clock,
.screen-kpis,
.panel-heading,
.risk-row,
.screen-alarm,
.health-flow span,
.screen-error {
  display: flex;
  align-items: center;
}

.screen-header {
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 18px;
}

.screen-title {
  gap: 14px;
  min-width: 0;
}

.back-link {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border: 1px solid rgba(56, 189, 248, 0.32);
  border-radius: 6px;
  color: var(--cyan);
  background: rgba(56, 189, 248, 0.1);
}

.screen-title p,
.panel-heading p,
.screen-kpi p,
.screen-note,
.screen-error,
.screen-loading {
  margin: 0;
}

.screen-title p,
.panel-heading p,
.screen-kpi p {
  color: var(--text-subtle);
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}

.screen-title h1 {
  margin: 4px 0 0;
  font-size: clamp(26px, 3vw, 44px);
  line-height: 1.08;
}

.screen-clock {
  flex-direction: column;
  align-items: flex-end;
  min-width: 180px;
}

.screen-clock strong {
  font-family: "Fira Code", Consolas, monospace;
  font-size: clamp(28px, 3vw, 46px);
  line-height: 1;
  color: var(--green);
  text-shadow: 0 0 18px rgba(45, 212, 125, 0.22);
}

.screen-clock span {
  margin-top: 6px;
  color: var(--text-muted);
}

.screen-kpis {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}

.screen-loading {
  margin-bottom: 12px;
  color: var(--text-muted);
  font-size: 13px;
}

.screen-kpi,
.screen-panel {
  border: 1px solid rgba(188, 238, 255, 0.15);
  border-radius: 6px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.055), rgba(255, 255, 255, 0.012)),
    rgba(17, 26, 34, 0.88);
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.28), 0 1px 0 rgba(255, 255, 255, 0.04) inset;
}

.screen-kpi {
  gap: 14px;
  min-height: 118px;
  padding: 18px;
}

.kpi-icon {
  display: grid;
  place-items: center;
  width: 48px;
  height: 48px;
  flex: 0 0 auto;
  border-radius: 6px;
}

.kpi-icon.good { color: var(--green); background: rgba(45, 212, 125, 0.12); }
.kpi-icon.warn { color: var(--amber); background: rgba(246, 184, 75, 0.12); }
.kpi-icon.cyan { color: var(--cyan); background: rgba(56, 189, 248, 0.12); }
.kpi-icon.blue { color: var(--blue); background: rgba(96, 165, 250, 0.12); }

.screen-kpi strong {
  display: block;
  margin: 6px 0 5px;
  font-size: clamp(26px, 2.8vw, 42px);
  line-height: 1;
}

.screen-kpi small,
.risk-row small,
.screen-alarm small,
.risk-row em,
.screen-alarm em,
.screen-note {
  color: var(--text-muted);
}

.screen-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(340px, 0.78fr);
  grid-template-areas:
    "lab risk"
    "alarms health";
  gap: 12px;
}

.screen-panel {
  min-height: 280px;
  padding: 18px;
  overflow: hidden;
}

.lab-panel { grid-area: lab; }
.risk-panel { grid-area: risk; }
.alarms-panel { grid-area: alarms; }
.health-panel { grid-area: health; }

.panel-heading {
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.panel-heading h2 {
  margin: 4px 0 0;
  font-size: 20px;
}

.panel-heading > span {
  min-height: 30px;
  padding: 0 10px;
  border: 1px solid rgba(56, 189, 248, 0.25);
  border-radius: 999px;
  color: var(--cyan);
  background: rgba(56, 189, 248, 0.08);
  line-height: 30px;
  white-space: nowrap;
}

.slot-map {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 8px;
}

.screen-slot {
  display: grid;
  place-items: center;
  aspect-ratio: 1;
  min-height: 36px;
  border: 1px solid var(--border);
  border-radius: 5px;
  color: var(--text-muted);
  background: rgba(255, 255, 255, 0.03);
  font-family: "Fira Code", Consolas, monospace;
  font-size: 12px;
  font-weight: 800;
}

.screen-slot.online {
  color: var(--green);
  border-color: rgba(45, 212, 125, 0.58);
  background: rgba(45, 212, 125, 0.1);
  box-shadow: 0 0 16px rgba(45, 212, 125, 0.08);
}

.screen-slot.warning {
  color: var(--amber);
  border-color: rgba(246, 184, 75, 0.65);
  background: rgba(246, 184, 75, 0.1);
}

.screen-slot.offline {
  color: var(--text-subtle);
  border-color: rgba(112, 129, 141, 0.42);
}

.screen-slot.maintenance {
  color: var(--cyan);
  border-color: rgba(56, 189, 248, 0.56);
  background: rgba(56, 189, 248, 0.09);
}

.risk-list,
.alarm-stream,
.health-flow {
  display: grid;
  gap: 10px;
}

.risk-row {
  grid-template-columns: 48px minmax(0, 1fr) auto;
  gap: 12px;
  min-height: 62px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.03);
}

.risk-row > strong {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: 6px;
  color: #160b04;
  background: var(--amber);
  font-family: "Fira Code", Consolas, monospace;
}

.risk-row span,
.screen-alarm strong {
  display: block;
  color: var(--text);
  font-weight: 800;
}

.risk-row small,
.screen-alarm small {
  display: block;
  margin-top: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.risk-row em,
.screen-alarm em {
  font-style: normal;
  font-size: 12px;
  white-space: nowrap;
}

.screen-alarm {
  grid-template-columns: 70px minmax(0, 1fr) auto;
  gap: 12px;
  min-height: 58px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.03);
}

.screen-alarm > span {
  text-align: center;
  font-size: 12px;
  font-weight: 900;
}

.alarm-info > span { color: var(--cyan); }
.alarm-warning > span { color: var(--amber); }
.alarm-critical > span { color: var(--red); }

.health-flow span {
  gap: 9px;
  min-height: 46px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.03);
  font-weight: 800;
}

.good,
.tone-good {
  color: var(--green);
}

.warn,
.tone-warn {
  color: var(--amber);
}

.bad,
.tone-bad {
  color: var(--red);
}

.screen-note,
.screen-error {
  margin-top: 14px;
  line-height: 1.65;
}

.screen-error {
  gap: 8px;
  color: var(--red);
}

.screen-empty {
  display: grid;
  place-items: center;
  min-height: 180px;
  border: 1px dashed var(--border-strong);
  border-radius: 6px;
  color: var(--text-muted);
}

@media (max-width: 1080px) {
  .screen-kpis,
  .screen-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .screen-grid {
    grid-template-areas:
      "lab lab"
      "risk alarms"
      "health health";
  }
}

@media (max-width: 720px) {
  .screen-header,
  .screen-title {
    align-items: flex-start;
  }

  .screen-header {
    flex-direction: column;
  }

  .screen-clock {
    align-items: flex-start;
  }

  .screen-kpis,
  .screen-grid {
    grid-template-columns: 1fr;
  }

  .screen-grid {
    grid-template-areas:
      "lab"
      "risk"
      "alarms"
      "health";
  }

  .slot-map {
    grid-template-columns: repeat(6, minmax(0, 1fr));
  }

  .risk-row,
  .screen-alarm {
    grid-template-columns: 44px minmax(0, 1fr);
  }

  .risk-row em,
  .screen-alarm em {
    grid-column: 2;
  }
}
</style>
