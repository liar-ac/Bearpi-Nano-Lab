<script setup lang="ts">
import { BatteryCharging, Cpu, Eye, Gauge, PlugZap, RefreshCcw, Search, Sparkles, Zap } from 'lucide-vue-next';
import { ElMessage } from 'element-plus';
import { computed, onMounted, ref, watch } from 'vue';
import EmptyState from '@/components/EmptyState.vue';
import TrendChart from '@/components/LineChart.vue';
import StatusBadge from '@/components/StatusBadge.vue';
import { fetchDevices, fetchHistory, sendAiChat } from '@/api/lab';
import type { Device, HistoryInterval, Point, Sensor } from '@/types/domain';
import { formatDateTime, formatValue, relativeTime } from '@/utils/format';

type PowerRange = '5m' | '1h' | '1d';

const devices = ref<Device[]>([]);
const loading = ref(false);
const error = ref('');
const keyword = ref('');
const selectedDevice = ref<Device | null>(null);
const detailOpen = ref(false);
const selectedTrendDeviceId = ref<number | null>(null);
const trendRange = ref<PowerRange>('1h');
const trendLoading = ref(false);
const trendError = ref('');
const trendPoints = ref<Point[]>([]);

const boardPowerCodes = new Set(['voltage', 'current', 'power']);
const modulePowerCodes = new Set(['power_mcu', 'power_wifi', 'power_sensor', 'power_motor', 'power_light']);
const sourceCodes = new Set(['voltage_sampled', 'current_sampled', 'power_sampled']);
const allPowerCodes = new Set([...boardPowerCodes, ...modulePowerCodes, ...sourceCodes]);

const trendRanges: Array<{
  label: string;
  value: PowerRange;
  durationMs: number;
  interval: HistoryInterval;
}> = [
  { label: '5分钟', value: '5m', durationMs: 5 * 60_000, interval: '1m' },
  { label: '1小时', value: '1h', durationMs: 60 * 60_000, interval: '5m' },
  { label: '1天', value: '1d', durationMs: 24 * 60 * 60_000, interval: '1h' }
];

function sensorByCode(device: Device, code: string) {
  return device.sensors.find((sensor) => sensor.code === code);
}

function sensorValue(device: Device, code: string) {
  return sensorByCode(device, code)?.latest?.value;
}

function powerValue(device: Device) {
  return sensorValue(device, 'power') ?? 0;
}

function powerTone(device: Device) {
  const value = powerValue(device);
  const sensor = sensorByCode(device, 'power');
  if (typeof sensor?.max === 'number' && value > sensor.max) return 'danger';
  if (value > 1200) return 'warning';
  return 'normal';
}

function sortByPower(a: Device, b: Device) {
  return powerValue(a) - powerValue(b);
}

function isSampled(device: Device, code: string) {
  return (sensorValue(device, code) ?? 0) >= 0.5;
}

function powerSourceLabel(device: Device) {
  const voltage = isSampled(device, 'voltage_sampled');
  const current = isSampled(device, 'current_sampled');
  if (voltage && current) return 'ADC实测';
  if (voltage) return '电压ADC';
  if (current) return '电流ADC';
  return '估算';
}

function powerSourceTone(device: Device) {
  const voltage = isSampled(device, 'voltage_sampled');
  const current = isSampled(device, 'current_sampled');
  if (voltage && current) return 'success';
  if (voltage || current) return 'warning';
  return 'info';
}

const filteredDevices = computed(() => {
  const query = keyword.value.trim().toLowerCase();
  const rows = devices.value.slice().sort((a, b) => a.slotNo - b.slotNo);
  if (!query) return rows;
  return rows.filter((device) =>
    [device.sn, device.location, device.member, String(device.slotNo)]
      .filter(Boolean)
      .some((value) => value.toLowerCase().includes(query))
  );
});

const onlineDevices = computed(() =>
  devices.value.filter((device) => device.status === 'online' || device.status === 'warning')
);

const totalPower = computed(() =>
  onlineDevices.value.reduce((sum, device) => sum + powerValue(device), 0)
);

const averagePower = computed(() =>
  onlineDevices.value.length ? totalPower.value / onlineDevices.value.length : 0
);

const peakDevice = computed(() =>
  filteredDevices.value.reduce<Device | null>((peak, device) => {
    if (!peak) return device;
    return powerValue(device) > powerValue(peak) ? device : peak;
  }, null)
);

const summaryCards = computed(() => [
  {
    label: '在线板卡',
    value: `${onlineDevices.value.length}/${devices.value.length}`,
    detail: '参与实时功耗统计',
    icon: Cpu,
    tone: 'cyan'
  },
  {
    label: '总功耗',
    value: formatValue(totalPower.value, 'mW'),
    detail: '在线板卡瞬时合计',
    icon: Zap,
    tone: 'amber'
  },
  {
    label: '平均功耗',
    value: formatValue(averagePower.value, 'mW'),
    detail: '单板平均瞬时功耗',
    icon: Gauge,
    tone: 'green'
  },
  {
    label: '最高功耗',
    value: peakDevice.value ? formatValue(powerValue(peakDevice.value), 'mW') : '--',
    detail: peakDevice.value ? `${peakDevice.value.sn} / 槽位${peakDevice.value.slotNo}` : '暂无数据',
    icon: BatteryCharging,
    tone: 'red'
  }
]);

const selectedPowerSensors = computed(() =>
  selectedDevice.value?.sensors.filter((sensor) => boardPowerCodes.has(sensor.code)) ?? []
);

const selectedModulePowerSensors = computed(() =>
  selectedDevice.value?.sensors.filter((sensor) => modulePowerCodes.has(sensor.code)) ?? []
);

const selectedSourceSensors = computed(() =>
  selectedDevice.value?.sensors.filter((sensor) => sourceCodes.has(sensor.code)) ?? []
);

const selectedOtherSensors = computed(() =>
  selectedDevice.value?.sensors.filter((sensor) => !allPowerCodes.has(sensor.code)) ?? []
);

const trendDevices = computed(() =>
  devices.value.filter((device) => sensorByCode(device, 'power'))
);

const selectedTrendDevice = computed(() =>
  trendDevices.value.find((device) => device.id === selectedTrendDeviceId.value) ?? trendDevices.value[0] ?? null
);

const selectedTrendPowerSensor = computed(() =>
  selectedTrendDevice.value ? sensorByCode(selectedTrendDevice.value, 'power') : undefined
);

const selectedTrendRange = computed(() =>
  trendRanges.find((item) => item.value === trendRange.value) ?? trendRanges[1]
);

const trendStats = computed(() => {
  const points = trendPoints.value.slice().sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime());
  const durationHours = selectedTrendRange.value.durationMs / 3_600_000;
  const latestPower = selectedTrendDevice.value ? powerValue(selectedTrendDevice.value) : 0;
  const values = points.map((point) => point.value).filter((value) => Number.isFinite(value));
  const peak = values.length ? Math.max(...values) : latestPower;
  const minVal = values.length ? Math.min(...values) : latestPower;
  const average = values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : latestPower;
  const energy = computeEnergyWh(points, selectedTrendRange.value.durationMs, latestPower);
  return {
    energy,
    average,
    peak,
    min: minVal,
    count: points.length
  };
});

const trendCards = computed(() => [
  {
    label: '累计电量',
    value: formatValue(trendStats.value.energy, 'Wh'),
    detail: `${selectedTrendRange.value.label}内估算积分`,
    icon: BatteryCharging,
    tone: 'amber'
  },
  {
    label: '平均功耗',
    value: formatValue(trendStats.value.average, 'mW'),
    detail: '基于历史采样点',
    icon: Gauge,
    tone: 'green'
  },
  {
    label: '峰值功耗',
    value: formatValue(trendStats.value.peak, 'mW'),
    detail: selectedTrendDevice.value?.sn ?? '暂无板卡',
    icon: Zap,
    tone: 'red'
  },
  {
    label: '曲线点数',
    value: trendStats.value.count,
    detail: selectedTrendPowerSensor.value ? `传感器#${selectedTrendPowerSensor.value.id}` : '等待功耗传感器',
    icon: Cpu,
    tone: 'cyan'
  }
]);

async function load() {
  loading.value = true;
  error.value = '';
  try {
    devices.value = (await fetchDevices()).results;
    ensureTrendDevice();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '功耗数据加载失败';
  } finally {
    loading.value = false;
  }
}

function openDetail(device: Device) {
  selectedDevice.value = device;
  detailOpen.value = true;
}

function valueCell(device: Device, code: string) {
  const sensor = sensorByCode(device, code);
  return formatValue(sensor?.latest?.value, sensor?.unit ?? '');
}

function sensorLatest(sensor: Sensor) {
  if (!sensor.latest) return '从未上报';
  return `${formatValue(sensor.latest.value, sensor.unit)} / ${relativeTime(sensor.latest.ts)}`;
}

function sourceLatest(sensor: Sensor) {
  if (!sensor.latest) return '从未上报';
  const label = sensor.latest.value >= 0.5 ? 'ADC采样' : '估算';
  return `${label} / ${relativeTime(sensor.latest.ts)}`;
}

function buildAnalysisContext() {
  const device = selectedTrendDevice.value;
  const sensor = selectedTrendPowerSensor.value;
  return {
    device: device ? { sn: device.sn, slotNo: device.slotNo, status: device.status } : {},
    sensor: sensor ? { name: sensor.name, code: sensor.code, unit: sensor.unit, min: sensor.min, max: sensor.max } : {},
    stats: {
      count: trendStats.value.count,
      min: trendStats.value.min,
      peak: trendStats.value.peak,
      average: trendStats.value.average,
      energy: trendStats.value.energy,
    },
    points: trendPoints.value.slice(-30).map((p) => ({ ts: p.ts, value: p.value })),
  };
}

const aiVisible = ref(false);
const aiLoading = ref(false);
const aiReply = ref('');
const aiError = ref('');

async function runAiAnalysis() {
  if (!selectedTrendDevice.value) return;
  aiVisible.value = true;
  aiLoading.value = true;
  aiReply.value = '';
  aiError.value = '';
  try {
    const result = await sendAiChat('data_analysis', buildAnalysisContext());
    aiReply.value = result.reply;
  } catch (cause) {
    aiError.value = cause instanceof Error ? cause.message : 'AI分析请求失败';
    ElMessage.error(aiError.value);
  } finally {
    aiLoading.value = false;
  }
}

function closeAiDialog() {
  if (aiLoading.value) return;
  aiVisible.value = false;
}

function ensureTrendDevice() {
  if (!trendDevices.value.length) {
    selectedTrendDeviceId.value = null;
    return;
  }
  const exists = trendDevices.value.some((device) => device.id === selectedTrendDeviceId.value);
  if (!exists) {
    selectedTrendDeviceId.value = trendDevices.value[0].id;
  }
}

async function loadPowerTrend() {
  const sensor = selectedTrendPowerSensor.value;
  if (!sensor) {
    trendPoints.value = [];
    trendError.value = '';
    return;
  }
  trendLoading.value = true;
  trendError.value = '';
  const end = new Date();
  const range = selectedTrendRange.value;
  const start = new Date(end.getTime() - range.durationMs);
  try {
    const response = await fetchHistory(sensor.id, {
      start: start.toISOString(),
      end: end.toISOString(),
      interval: range.interval
    });
    trendPoints.value = response.points;
  } catch (cause) {
    trendError.value = cause instanceof Error ? cause.message : '功耗趋势加载失败';
    trendPoints.value = [];
  } finally {
    trendLoading.value = false;
  }
}

function computeEnergyWh(points: Point[], durationMs: number, fallbackPower: number) {
  if (points.length < 2) {
    return (fallbackPower / 1000) * (durationMs / 3_600_000);
  }

  const sorted = points.slice().sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime());
  let energyWh = 0;
  for (let index = 1; index < sorted.length; index++) {
    const prev = sorted[index - 1];
    const current = sorted[index];
    const deltaHours = Math.max(0, new Date(current.ts).getTime() - new Date(prev.ts).getTime()) / 3_600_000;
    const averageMw = (prev.value + current.value) / 2;
    energyWh += (averageMw / 1000) * deltaHours;
  }
  return energyWh;
}

watch([selectedTrendDeviceId, trendRange], () => {
  void loadPowerTrend();
});

onMounted(load);
</script>

<template>
  <div class="stack gap-lg">
    <section class="ops-overview priority-overview">
      <div>
        <p class="eyebrow">PowerMonitor</p>
        <h2>开发板功耗监控</h2>
        <p>按槽位查看每块板的电压、电流、功耗和最近上报时间，适配最多120块板同时接入。</p>
      </div>
      <div class="ops-status-grid">
        <span><PlugZap :size="16" />功耗遥测</span>
        <span><Cpu :size="16" />{{ devices.length }}块板</span>
        <span><Zap :size="16" />{{ formatValue(totalPower, 'mW') }}</span>
      </div>
    </section>

    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />

    <section class="metric-grid">
      <article v-for="card in summaryCards" :key="card.label" class="metric-card" :class="`tone-${card.tone}`">
        <component :is="card.icon" :size="22" />
        <div>
          <span>{{ card.label }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.detail }}</small>
        </div>
      </article>
    </section>

    <section class="panel-section power-trend-panel" v-loading="trendLoading">
      <div class="section-heading">
        <div>
          <p class="eyebrow">PowerTrend</p>
          <h3>功耗趋势与能耗统计</h3>
        </div>
        <div class="toolbar-row">
          <el-select v-model="selectedTrendDeviceId" filterable placeholder="选择板卡" class="trend-device-select">
            <el-option
              v-for="device in trendDevices"
              :key="device.id"
              :label="`槽位${device.slotNo}/${device.sn}`"
              :value="device.id"
            />
          </el-select>
          <el-radio-group v-model="trendRange">
            <el-radio-button v-for="range in trendRanges" :key="range.value" :label="range.value">
              {{ range.label }}
            </el-radio-button>
          </el-radio-group>
          <el-button :disabled="!selectedTrendPowerSensor" @click="loadPowerTrend">
            <RefreshCcw :size="16" />
            刷新曲线
          </el-button>
          <el-button :disabled="!selectedTrendDevice" @click="runAiAnalysis">
            <Sparkles :size="16" />
            AI分析
          </el-button>
        </div>
      </div>

      <el-alert v-if="trendError" :title="trendError" type="error" show-icon :closable="false" />

      <template v-if="selectedTrendDevice">
        <div class="trend-context">
          <span>{{ selectedTrendDevice.sn }}</span>
          <span>槽位{{ selectedTrendDevice.slotNo }}</span>
          <span>当前{{ valueCell(selectedTrendDevice, 'power') }}</span>
          <span>来源{{ powerSourceLabel(selectedTrendDevice) }}</span>
        </div>

        <section class="metric-grid trend-card-grid">
          <article v-for="card in trendCards" :key="card.label" class="metric-card" :class="`tone-${card.tone}`">
            <component :is="card.icon" :size="22" />
            <div>
              <span>{{ card.label }}</span>
              <strong>{{ card.value }}</strong>
              <small>{{ card.detail }}</small>
            </div>
          </article>
        </section>

        <TrendChart
          :points="trendPoints"
          title="功耗趋势"
          unit="mW"
          color="#f6b84b"
          :thresholds="selectedTrendPowerSensor?.max ? [{ name: '上限', value: selectedTrendPowerSensor.max, color: '#ff6874' }] : []"
        />
      </template>
      <EmptyState v-else title="暂无功耗趋势" detail="等待开发板上报power传感器后显示曲线。" />
    </section>

    <section class="panel-section">
      <div class="section-heading">
        <div>
          <p class="eyebrow">BoardPowerTable</p>
          <h3>单板功耗明细</h3>
        </div>
        <div class="toolbar-row">
          <el-input v-model="keyword" clearable placeholder="搜索槽位、SN、成员" class="power-search">
            <template #prefix><Search :size="16" /></template>
          </el-input>
          <el-button :loading="loading" @click="load">
            <RefreshCcw :size="16" />
            刷新
          </el-button>
        </div>
      </div>

      <EmptyState v-if="!loading && !filteredDevices.length" title="暂无功耗数据" detail="等待开发板上报voltage/current/power后显示。" />

      <el-table v-else v-loading="loading" :data="filteredDevices" class="power-table" row-key="id">
        <el-table-column prop="slotNo" label="槽位" width="82" sortable />
        <el-table-column label="板卡" min-width="210">
          <template #default="{ row }">
            <div class="board-identity">
              <strong>{{ row.sn }}</strong>
              <small>{{ row.member }} / {{ row.location }}</small>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <StatusBadge :status="row.status" />
          </template>
        </el-table-column>
        <el-table-column label="电压" width="110">
          <template #default="{ row }">{{ valueCell(row, 'voltage') }}</template>
        </el-table-column>
        <el-table-column label="电流" width="110">
          <template #default="{ row }">{{ valueCell(row, 'current') }}</template>
        </el-table-column>
        <el-table-column label="功耗" width="130" sortable :sort-method="sortByPower">
          <template #default="{ row }">
            <span class="power-value" :class="`is-${powerTone(row)}`">{{ valueCell(row, 'power') }}</span>
          </template>
        </el-table-column>
        <el-table-column label="来源" width="112">
          <template #default="{ row }">
            <el-tag :type="powerSourceTone(row)" effect="plain">{{ powerSourceLabel(row) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最近上报" width="145">
          <template #default="{ row }">{{ relativeTime(row.lastSeen) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" @click="openDetail(row)">
              <Eye :size="16" />
              详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-drawer v-model="detailOpen" size="460px" title="板卡功耗详情">
      <template v-if="selectedDevice">
        <div class="power-detail-head">
          <div>
            <h3>{{ selectedDevice.sn }}</h3>
            <p>槽位{{ selectedDevice.slotNo }} / {{ selectedDevice.model }} / {{ selectedDevice.firmwareVersion }}</p>
          </div>
          <StatusBadge :status="selectedDevice.status" />
        </div>

        <div class="detail-meta-grid">
          <span>成员：{{ selectedDevice.member }}</span>
          <span>位置：{{ selectedDevice.location }}</span>
          <span>IP：{{ selectedDevice.ipAddress ?? '未登记' }}</span>
          <span>最近上报：{{ relativeTime(selectedDevice.lastSeen) }}</span>
          <span>注册时间：{{ formatDateTime(selectedDevice.registerTime) }}</span>
          <span>数据链路：HTTP上报到后端</span>
        </div>

        <h4>功耗指标</h4>
        <div class="sensor-list">
          <div v-for="sensor in selectedPowerSensors" :key="sensor.id" class="sensor-row">
            <span>{{ sensor.name }}</span>
            <strong>{{ sensorLatest(sensor) }}</strong>
            <small>{{ sensor.description }}</small>
          </div>
        </div>

        <h4>模块功耗</h4>
        <div class="sensor-list">
          <div v-for="sensor in selectedModulePowerSensors" :key="sensor.id" class="sensor-row">
            <span>{{ sensor.name }}</span>
            <strong>{{ sensorLatest(sensor) }}</strong>
            <small>{{ sensor.description }}</small>
          </div>
        </div>

        <h4>采样来源</h4>
        <div class="sensor-list compact">
          <div v-for="sensor in selectedSourceSensors" :key="sensor.id" class="sensor-row">
            <span>{{ sensor.name }}</span>
            <strong>{{ sourceLatest(sensor) }}</strong>
            <small>{{ sensor.description }}</small>
          </div>
        </div>

        <h4>全部遥测</h4>
        <div class="sensor-list compact">
          <div v-for="sensor in selectedOtherSensors" :key="sensor.id" class="sensor-row">
            <span>{{ sensor.name }}</span>
            <strong>{{ sensorLatest(sensor) }}</strong>
          </div>
        </div>
      </template>
    </el-drawer>

    <el-dialog
      v-model="aiVisible"
      title="AI数据分析"
      width="min(640px, 90vw)"
      append-to-body
      :close-on-click-modal="!aiLoading"
      @close="closeAiDialog"
    >
      <div v-if="aiLoading" class="ai-loading">
        <el-icon class="is-loading" :size="28"><Sparkles /></el-icon>
        <p>AI正在分析功耗数据,请稍候...</p>
      </div>
      <div v-else-if="aiError" class="ai-error">
        <p>{{ aiError }}</p>
      </div>
      <div v-else-if="aiReply" class="ai-reply">
        <pre>{{ aiReply }}</pre>
      </div>
      <template #footer>
        <el-button @click="closeAiDialog">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.power-search {
  width: min(280px, 100%);
}

.trend-device-select {
  width: min(300px, 100%);
}

.power-trend-panel {
  display: grid;
  gap: 14px;
}

.trend-context {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  color: var(--text-muted);
}

.trend-context span {
  display: inline-flex;
  min-height: 30px;
  align-items: center;
  padding: 0 10px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.026);
}

.trend-card-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.board-identity {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.board-identity small,
.power-detail-head p,
.sensor-row small {
  color: var(--text-muted);
}

.power-value {
  font-weight: 800;
}

.power-value.is-normal {
  color: var(--green);
}

.power-value.is-warning {
  color: var(--amber);
}

.power-value.is-danger {
  color: var(--red);
}

.power-detail-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.power-detail-head h3 {
  margin: 0 0 6px;
}

.power-detail-head p {
  margin: 0;
}

.detail-meta-grid {
  display: grid;
  gap: 8px;
  margin-bottom: 20px;
  color: var(--text-muted);
}

h4 {
  margin: 18px 0 10px;
}

.sensor-list {
  display: grid;
  gap: 10px;
}

.sensor-row {
  display: grid;
  gap: 4px;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--panel-soft);
}

.sensor-list.compact .sensor-row {
  padding: 10px 12px;
}

@media (max-width: 980px) {
  .trend-card-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .trend-card-grid {
    grid-template-columns: 1fr;
  }
}

.ai-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 40px 0;
  color: var(--text-muted);
}

.ai-loading p { margin: 0; }

.ai-error {
  padding: 20px;
  color: var(--red);
  background: rgba(255, 104, 116, 0.08);
  border-radius: var(--radius);
}

.ai-error p { margin: 0; }

.ai-reply pre {
  margin: 0;
  padding: 20px;
  white-space: pre-wrap;
  word-wrap: break-word;
  line-height: 1.7;
  color: var(--text);
  background: var(--panel-soft);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-family: inherit;
  font-size: 14px;
}
</style>
