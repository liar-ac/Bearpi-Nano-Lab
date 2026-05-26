<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { onHide, onPullDownRefresh, onShow, onUnload } from '@dcloudio/uni-app';
import AiChat from '@/components/AiChat.vue';
import { fetchDevices, fetchHistory } from '@/api/lab';
import { realtimeState, realtimeStatusLabel, subscribeRealtime } from '@/api/realtime';
import type { Device, HistoryInterval, Point, RealtimeMessage, Sensor } from '@/types/domain';
import { formatDateTime, formatValue, relativeTime } from '@/utils/format';

type PowerRange = '5m' | '1h' | '1d';

const devices = ref<Device[]>([]);
const loading = ref(false);
const error = ref('');
const keyword = ref('');
const selectedDeviceId = ref<number | null>(null);
const detailVisible = ref(false);
const selectedTrendDeviceId = ref<number | null>(null);
const trendRange = ref<PowerRange>('1h');
const trendLoading = ref(false);
const trendError = ref('');
const trendPoints = ref<Point[]>([]);
let unsubscribe: (() => void) | null = null;
let refreshTimer: ReturnType<typeof setInterval> | null = null;

const boardPowerCodes = new Set(['voltage', 'current', 'power']);
const modulePowerCodes = new Set(['power_mcu', 'power_wifi', 'power_sensor', 'power_motor', 'power_light']);
const sourceCodes = new Set(['voltage_sampled', 'current_sampled', 'power_sampled']);
const allPowerCodes = new Set([...boardPowerCodes, ...modulePowerCodes, ...sourceCodes]);

const trendRanges: Array<{ label: string; value: PowerRange; durationMs: number; interval: HistoryInterval }> = [
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

function powerSourceType(device: Device) {
  const voltage = isSampled(device, 'voltage_sampled');
  const current = isSampled(device, 'current_sampled');
  if (voltage && current) return 'success';
  if (voltage || current) return 'warning';
  return 'primary';
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

const totalPower = computed(() => onlineDevices.value.reduce((sum, device) => sum + powerValue(device), 0));
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
    detail: '参与实时功耗统计'
  },
  {
    label: '总功耗',
    value: formatValue(totalPower.value, 'mW'),
    detail: '在线板卡瞬时合计'
  },
  {
    label: '平均功耗',
    value: formatValue(averagePower.value, 'mW'),
    detail: '单板平均瞬时'
  },
  {
    label: '最高功耗',
    value: peakDevice.value ? formatValue(powerValue(peakDevice.value), 'mW') : '--',
    detail: peakDevice.value ? `${peakDevice.value.sn} / 槽位${peakDevice.value.slotNo}` : '暂无数据'
  }
]);

const selectedDevice = computed(() =>
  selectedDeviceId.value !== null
    ? devices.value.find((device) => device.id === selectedDeviceId.value) ?? null
    : null
);

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

const trendDevices = computed(() => devices.value.filter((device) => sensorByCode(device, 'power')));

const selectedTrendDevice = computed(
  () => trendDevices.value.find((device) => device.id === selectedTrendDeviceId.value) ?? trendDevices.value[0] ?? null
);

const selectedTrendPowerSensor = computed(() =>
  selectedTrendDevice.value ? sensorByCode(selectedTrendDevice.value, 'power') : undefined
);

const selectedTrendRange = computed(() =>
  trendRanges.find((item) => item.value === trendRange.value) ?? trendRanges[1]
);

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

const trendStats = computed(() => {
  const points = trendPoints.value.slice().sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime());
  const durationHours = selectedTrendRange.value.durationMs / 3_600_000;
  const latestPower = selectedTrendDevice.value ? powerValue(selectedTrendDevice.value) : 0;
  const values = points.map((point) => point.value).filter((value) => Number.isFinite(value));
  const peak = values.length ? Math.max(...values) : latestPower;
  const minPower = values.length ? Math.min(...values) : latestPower;
  const average = values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : latestPower;
  const energy = computeEnergyWh(points, selectedTrendRange.value.durationMs, latestPower);
  return {
    energy,
    average,
    peak,
    min: minPower,
    count: points.length,
    durationHours
  };
});

const trendCards = computed(() => [
  {
    label: '累计电量',
    value: formatValue(trendStats.value.energy, 'Wh'),
    detail: `${selectedTrendRange.value.label}估算积分`
  },
  {
    label: '平均功耗',
    value: formatValue(trendStats.value.average, 'mW'),
    detail: '基于历史采样点'
  },
  {
    label: '峰值功耗',
    value: formatValue(trendStats.value.peak, 'mW'),
    detail: selectedTrendDevice.value?.sn ?? '暂无板卡'
  },
  {
    label: '曲线点数',
    value: String(trendStats.value.count),
    detail: selectedTrendPowerSensor.value ? `传感器#${selectedTrendPowerSensor.value.id}` : '等待功耗传感器'
  }
]);

async function load() {
  loading.value = true;
  error.value = '';
  try {
    const response = await fetchDevices();
    devices.value = response.results;
    ensureTrendDevice();
    void loadPowerTrend();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '功耗数据加载失败';
  } finally {
    loading.value = false;
  }
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

function applyRealtime(message: RealtimeMessage) {
  devices.value = devices.value.map((device) => {
    if (device.id !== message.deviceId) return device;
    const newStatus = message.status ?? device.status;
    return {
      ...device,
      status: newStatus,
      lastSeen: message.ts,
      abnormalReason: newStatus === 'online' ? '' : device.abnormalReason,
      sensors: device.sensors.map((sensor) =>
        sensor.id === message.sensorId ? { ...sensor, latest: { ts: message.ts, value: message.value } } : sensor
      )
    };
  });
}

onShow(async () => {
  await load();
  if (!unsubscribe) unsubscribe = subscribeRealtime(applyRealtime);
  if (!refreshTimer) {
    refreshTimer = setInterval(() => {
      void load();
    }, 10000);
  }
});

onHide(() => {
  teardown();
});

onUnload(() => {
  teardown();
});

onBeforeUnmount(() => {
  teardown();
});

onPullDownRefresh(async () => {
  await load();
  uni.stopPullDownRefresh();
});

function teardown() {
  if (unsubscribe) {
    unsubscribe();
    unsubscribe = null;
  }
  if (refreshTimer) {
    clearInterval(refreshTimer);
    refreshTimer = null;
  }
}

function openDetail(device: Device) {
  selectedDeviceId.value = device.id;
  detailVisible.value = true;
}

function closeDetail() {
  detailVisible.value = false;
}

function selectTrendDevice(deviceId: number) {
  selectedTrendDeviceId.value = deviceId;
}

function selectTrendRange(value: PowerRange) {
  trendRange.value = value;
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

function statusTagType(status: Device['status']) {
  return status === 'online' ? 'success' : status === 'warning' ? 'danger' : status === 'maintenance' ? 'warning' : 'primary';
}

function statusText(status: Device['status']) {
  return status === 'online' ? '在线' : status === 'warning' ? '异常' : status === 'maintenance' ? '维护' : '离线';
}

function deviceLabel(device: Device) {
  return `槽位${device.slotNo} / ${device.sn}`;
}

watch([selectedTrendDeviceId, trendRange], () => {
  void loadPowerTrend();
});
</script>

<template>
  <view class="page">
    <view class="hero">
      <view>
        <text class="eyebrow">PowerMonitor</text>
        <text class="title">开发板功耗监控</text>
        <text class="subtitle">按槽位查看电压、电流、功耗与采样来源，最多支持120块板。</text>
      </view>
      <view class="hero-meta">
        <text>{{ realtimeStatusLabel[realtimeState.status] }}</text>
        <text>{{ devices.length }}块板</text>
        <text>{{ formatValue(totalPower, 'mW') }}</text>
      </view>
    </view>

    <view v-if="error" class="notice error">{{ error }}</view>

    <view class="metric-grid">
      <view v-for="card in summaryCards" :key="card.label" class="metric-card">
        <text>{{ card.label }}</text>
        <text>{{ card.value }}</text>
        <text>{{ card.detail }}</text>
      </view>
    </view>

    <view class="panel">
      <view class="panel-head">
        <view>
          <text class="eyebrow">PowerTrend</text>
          <text class="title small">功耗趋势与能耗</text>
        </view>
        <view class="trend-toolbar-actions">
          <wd-button size="small" plain :disabled="!selectedTrendPowerSensor || trendLoading" @click="loadPowerTrend">
            刷新曲线
          </wd-button>
          <AiChat
            v-if="selectedTrendDevice"
            feature="data_analysis"
            :context="buildAnalysisContext()"
            trigger-text="AI分析"
            title="AI数据分析"
          />
        </view>
      </view>

      <scroll-view class="filter-scroll" scroll-x>
        <view class="filter-row">
          <text class="filter-label">板卡</text>
          <wd-button
            v-for="device in trendDevices"
            :key="device.id"
            size="small"
            :type="selectedTrendDeviceId === device.id ? 'primary' : 'info'"
            :plain="selectedTrendDeviceId !== device.id"
            @click="selectTrendDevice(device.id)"
          >
            {{ deviceLabel(device) }}
          </wd-button>
          <text v-if="!trendDevices.length" class="empty-hint">暂无功耗传感器</text>
        </view>
      </scroll-view>

      <scroll-view class="filter-scroll" scroll-x>
        <view class="filter-row">
          <text class="filter-label">范围</text>
          <wd-button
            v-for="range in trendRanges"
            :key="range.value"
            size="small"
            :type="trendRange === range.value ? 'primary' : 'info'"
            :plain="trendRange !== range.value"
            @click="selectTrendRange(range.value)"
          >
            {{ range.label }}
          </wd-button>
        </view>
      </scroll-view>

      <view v-if="trendError" class="notice error">{{ trendError }}</view>

      <template v-if="selectedTrendDevice">
        <view class="trend-context">
          <text>{{ selectedTrendDevice.sn }}</text>
          <text>槽位{{ selectedTrendDevice.slotNo }}</text>
          <text>当前{{ valueCell(selectedTrendDevice, 'power') }}</text>
          <text>来源{{ powerSourceLabel(selectedTrendDevice) }}</text>
        </view>

        <view class="trend-grid">
          <view v-for="card in trendCards" :key="card.label" class="metric-card compact">
            <text>{{ card.label }}</text>
            <text>{{ card.value }}</text>
            <text>{{ card.detail }}</text>
          </view>
        </view>

        <view class="trend-range">
          <text>区间最低 {{ formatValue(trendStats.min, 'mW') }}</text>
          <text>区间最高 {{ formatValue(trendStats.peak, 'mW') }}</text>
        </view>
      </template>
      <view v-else class="empty-state">暂无功耗趋势，等待开发板上报power传感器。</view>
    </view>

    <view class="panel">
      <view class="panel-head">
        <view>
          <text class="eyebrow">BoardPowerTable</text>
          <text class="title small">单板功耗明细</text>
        </view>
        <wd-button size="small" plain :loading="loading" @click="load">刷新</wd-button>
      </view>

      <view class="search-row">
        <wd-input v-model="keyword" placeholder="搜索槽位、SN、成员" clearable />
      </view>

      <view v-if="!loading && !filteredDevices.length" class="empty-state">
        暂无功耗数据，等待开发板上报voltage/current/power。
      </view>

      <view v-else class="board-list">
        <view v-for="device in filteredDevices" :key="device.id" class="board-row" @click="openDetail(device)">
          <view class="board-head">
            <view>
              <text class="board-title">槽位{{ device.slotNo }} · {{ device.sn }}</text>
              <text class="board-meta">{{ device.member }} / {{ device.location }}</text>
            </view>
            <wd-tag :type="statusTagType(device.status)">{{ statusText(device.status) }}</wd-tag>
          </view>
          <view class="board-metric">
            <view class="metric-pair">
              <text>电压</text>
              <text>{{ valueCell(device, 'voltage') }}</text>
            </view>
            <view class="metric-pair">
              <text>电流</text>
              <text>{{ valueCell(device, 'current') }}</text>
            </view>
            <view class="metric-pair">
              <text>功耗</text>
              <text :class="`tone-${powerTone(device)}`">{{ valueCell(device, 'power') }}</text>
            </view>
          </view>
          <view class="board-footer">
            <wd-tag :type="powerSourceType(device)">{{ powerSourceLabel(device) }}</wd-tag>
            <text class="board-meta">{{ relativeTime(device.lastSeen) }}</text>
          </view>
        </view>
      </view>
    </view>

    <wd-popup v-model="detailVisible" position="bottom" closable @close="closeDetail">
      <view v-if="selectedDevice" class="detail-popup">
        <view class="detail-head">
          <view>
            <text class="title small">{{ selectedDevice.sn }}</text>
            <text class="board-meta">
              槽位{{ selectedDevice.slotNo }} / {{ selectedDevice.model }} / {{ selectedDevice.firmwareVersion }}
            </text>
          </view>
          <wd-tag :type="statusTagType(selectedDevice.status)">{{ statusText(selectedDevice.status) }}</wd-tag>
        </view>

        <view class="detail-meta">
          <text>成员：{{ selectedDevice.member }}</text>
          <text>位置：{{ selectedDevice.location }}</text>
          <text>IP：{{ selectedDevice.ipAddress ?? '未登记' }}</text>
          <text>最近上报：{{ relativeTime(selectedDevice.lastSeen) }}</text>
          <text>注册时间：{{ formatDateTime(selectedDevice.registerTime) }}</text>
          <text>数据链路：HTTP上报到后端</text>
        </view>

        <text class="section-title">功耗指标</text>
        <view class="sensor-list">
          <view v-for="sensor in selectedPowerSensors" :key="sensor.id" class="sensor-row">
            <text>{{ sensor.name }}</text>
            <text>{{ sensorLatest(sensor) }}</text>
            <text>{{ sensor.description }}</text>
          </view>
        </view>

        <text class="section-title">模块功耗</text>
        <view class="sensor-list">
          <view v-for="sensor in selectedModulePowerSensors" :key="sensor.id" class="sensor-row">
            <text>{{ sensor.name }}</text>
            <text>{{ sensorLatest(sensor) }}</text>
            <text>{{ sensor.description }}</text>
          </view>
        </view>

        <text class="section-title">采样来源</text>
        <view class="sensor-list compact">
          <view v-for="sensor in selectedSourceSensors" :key="sensor.id" class="sensor-row">
            <text>{{ sensor.name }}</text>
            <text>{{ sourceLatest(sensor) }}</text>
            <text>{{ sensor.description }}</text>
          </view>
        </view>

        <text class="section-title">全部遥测</text>
        <view class="sensor-list compact">
          <view v-for="sensor in selectedOtherSensors" :key="sensor.id" class="sensor-row">
            <text>{{ sensor.name }}</text>
            <text>{{ sensorLatest(sensor) }}</text>
          </view>
        </view>

        <wd-button block plain @click="closeDetail">关闭</wd-button>
      </view>
    </wd-popup>
  </view>
</template>

<style lang="scss" scoped>
.page {
  min-height: 100vh;
  padding: 24rpx;
  box-sizing: border-box;
}

.hero,
.panel,
.metric-card,
.search-row {
  padding: 24rpx;
  border: 1rpx solid $uni-border-color;
  border-radius: 10rpx;
  background: #ffffff;
}

.hero {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
  margin-bottom: 18rpx;
}

.hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;

  text {
    padding: 6rpx 14rpx;
    border-radius: 999rpx;
    background: #fff7e6;
    color: #9a5b00;
    font-size: 22rpx;
  }
}

.eyebrow,
.title,
.subtitle,
.board-title,
.board-meta,
.filter-label,
.section-title {
  display: block;
}

.eyebrow {
  color: $uni-color-primary;
  font-size: 22rpx;
  font-weight: 700;
}

.title {
  margin-top: 6rpx;
  color: #172033;
  font-size: 38rpx;
  font-weight: 800;
}

.title.small {
  font-size: 30rpx;
}

.subtitle {
  margin-top: 6rpx;
  color: $uni-text-color-grey;
  font-size: 24rpx;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12rpx;
  margin-bottom: 18rpx;
}

.metric-card {
  text {
    display: block;
  }

  text:first-child {
    color: $uni-text-color-grey;
    font-size: 22rpx;
  }

  text:nth-child(2) {
    margin-top: 8rpx;
    color: #172033;
    font-size: 34rpx;
    font-weight: 800;
  }

  text:nth-child(3) {
    margin-top: 4rpx;
    color: $uni-text-color-grey;
    font-size: 22rpx;
  }
}

.metric-card.compact text:nth-child(2) {
  font-size: 30rpx;
}

.panel {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
  margin-bottom: 18rpx;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16rpx;
}

.trend-toolbar-actions {
  display: flex;
  gap: 12rpx;
  align-items: center;
}

.filter-scroll {
  white-space: nowrap;
}

.filter-row {
  display: inline-flex;
  align-items: center;
  gap: 10rpx;
  padding: 4rpx 0;
}

.filter-label {
  margin-right: 6rpx;
  color: $uni-text-color-grey;
  font-size: 24rpx;
  font-weight: 700;
}

.empty-hint {
  color: $uni-text-color-grey;
  font-size: 24rpx;
}

.trend-context {
  display: flex;
  flex-wrap: wrap;
  gap: 10rpx;

  text {
    padding: 6rpx 14rpx;
    border-radius: 999rpx;
    background: #eef3fb;
    color: #1d3a6e;
    font-size: 22rpx;
  }
}

.trend-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12rpx;
}

.trend-range {
  display: flex;
  justify-content: space-between;
  color: $uni-text-color-grey;
  font-size: 24rpx;
}

.search-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  padding: 16rpx 24rpx;
}

.board-list {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.board-row {
  padding: 20rpx;
  border: 1rpx solid $uni-border-color;
  border-radius: 8rpx;
  background: #ffffff;
}

.board-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12rpx;
}

.board-title {
  color: #172033;
  font-size: 28rpx;
  font-weight: 800;
}

.board-meta {
  margin-top: 6rpx;
  color: $uni-text-color-grey;
  font-size: 22rpx;
}

.board-metric {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8rpx;
  margin-top: 14rpx;
}

.metric-pair {
  padding: 12rpx;
  border-radius: 6rpx;
  background: #f8fafc;
  text-align: center;

  text {
    display: block;
  }

  text:first-child {
    color: $uni-text-color-grey;
    font-size: 22rpx;
  }

  text:last-child {
    margin-top: 4rpx;
    color: #172033;
    font-size: 26rpx;
    font-weight: 800;
  }
}

.tone-warning { color: #9a5b00 !important; }
.tone-danger { color: #b42318 !important; }

.board-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 14rpx;
}

.empty-state {
  padding: 40rpx 24rpx;
  border: 1rpx dashed $uni-border-color;
  border-radius: 8rpx;
  color: $uni-text-color-grey;
  background: #ffffff;
  text-align: center;
  font-size: 26rpx;
}

.notice {
  padding: 18rpx;
  border-radius: 6rpx;
  font-size: 24rpx;
}

.error {
  color: #b42318;
  background: #fff1f0;
}

.detail-popup {
  padding: 24rpx;
  display: flex;
  flex-direction: column;
  gap: 18rpx;
  max-height: 80vh;
  overflow-y: auto;
}

.detail-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12rpx;
}

.detail-meta {
  display: flex;
  flex-direction: column;
  gap: 6rpx;
  color: $uni-text-color-grey;
  font-size: 24rpx;
}

.section-title {
  margin-top: 12rpx;
  color: #172033;
  font-size: 28rpx;
  font-weight: 800;
}

.sensor-list {
  display: flex;
  flex-direction: column;
  gap: 10rpx;
}

.sensor-row {
  padding: 14rpx;
  border: 1rpx solid $uni-border-color;
  border-radius: 8rpx;
  background: #f8fafc;

  text {
    display: block;
  }

  text:first-child {
    color: $uni-text-color-grey;
    font-size: 22rpx;
  }

  text:nth-child(2) {
    margin-top: 4rpx;
    color: #172033;
    font-size: 26rpx;
    font-weight: 700;
  }

  text:nth-child(3) {
    margin-top: 4rpx;
    color: $uni-text-color-grey;
    font-size: 22rpx;
  }
}

.sensor-list.compact .sensor-row {
  padding: 10rpx 14rpx;
}
</style>
