<script setup lang="ts">
import { computed, ref } from 'vue';
import { onLoad, onPullDownRefresh } from '@dcloudio/uni-app';
import { fetchDevice, fetchHistory } from '@/api/lab';
import type { Device, HistoryInterval, Point, PointsResponse, Sensor } from '@/types/domain';
import { formatDateTime, formatValue } from '@/utils/format';

const deviceId = ref<number | null>(null);
const sensorId = ref<number | null>(null);
const device = ref<Device | null>(null);
const sensor = ref<Sensor | null>(null);
const data = ref<PointsResponse | null>(null);
const interval = ref<HistoryInterval>('5m');
const rangeDays = ref(7);
const customMode = ref(false);
const customStart = ref(Date.now() - 7 * 24 * 60 * 60_000);
const customEnd = ref(Date.now());
const loading = ref(false);
const error = ref('');
let searchRequestId = 0;

const points = computed<Point[]>(() => data.value?.points ?? []);
const chartPoints = computed(() => points.value);
const maxValue = computed(() => Math.max(...chartPoints.value.map((point) => Math.abs(point.value)), 1));

const thresholdText = computed(() => {
  const s = sensor.value;
  if (!s || s.min == null && s.max == null) return '';
  const unit = s.unit || '';
  if (s.min != null && s.max != null) return `阈值 ${s.min}~${s.max} ${unit}`;
  if (s.min != null) return `下限 ${s.min} ${unit}`;
  return `上限 ${s.max} ${unit}`;
});

function isPointBreach(point: Point): boolean {
  const s = sensor.value;
  if (!s) return false;
  return (s.min != null && point.value < s.min) || (s.max != null && point.value > s.max);
}

onLoad(async (query) => {
  const parsedDeviceId = Number(query?.deviceId) || 0;
  const parsedSensorId = Number(query?.sensorId) || 0;
  deviceId.value = Number.isFinite(parsedDeviceId) ? parsedDeviceId : 0;
  sensorId.value = Number.isFinite(parsedSensorId) ? parsedSensorId : 0;
  await loadMeta();
  await search();
});

onPullDownRefresh(async () => {
  await search();
  uni.stopPullDownRefresh();
});

async function loadMeta() {
  if (!deviceId.value || !sensorId.value) {
    error.value = '传感器参数无效';
    return;
  }
  try {
    device.value = await fetchDevice(deviceId.value);
    sensor.value = device.value.sensors.find((item) => item.id === sensorId.value) ?? null;
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '传感器信息加载失败';
  }
}

async function search() {
  if (!sensorId.value) return;
  const localRequestId = ++searchRequestId;
  loading.value = true;
  const end = customMode.value ? new Date(customEnd.value) : new Date();
  const start = customMode.value ? new Date(customStart.value) : new Date(Date.now() - rangeDays.value * 24 * 60 * 60_000);
  try {
    error.value = '';
    const response = await fetchHistory(sensorId.value, {
      start: start.toISOString(),
      end: end.toISOString(),
      interval: interval.value
    });
    if (localRequestId !== searchRequestId) return;
    data.value = response;
  } catch (cause) {
    if (localRequestId !== searchRequestId) return;
    error.value = cause instanceof Error ? cause.message : '历史数据查询失败';
  } finally {
    if (localRequestId === searchRequestId) loading.value = false;
  }
}

function setIntervalValue(value: HistoryInterval) {
  interval.value = value;
}

function setRangeDays(value: number) {
  rangeDays.value = value;
  customMode.value = false;
}

function setCustomRange() {
  customMode.value = true;
  customEnd.value = Date.now();
  customStart.value = customEnd.value - rangeDays.value * 24 * 60 * 60_000;
}
</script>

<template>
  <view class="page">
    <view class="hero">
      <text class="eyebrow">{{ device?.sn ?? 'Device' }} / {{ sensor?.code ?? 'Sensor' }}</text>
      <text class="title">{{ sensor?.name ?? '传感器' }}历史查询</text>
      <text class="copy">支持 1/7/30 天范围与 1m/5m/1h/1d 聚合。</text>
    </view>

    <view class="filter-card">
      <view class="filter-title">时间范围</view>
      <view class="control-row">
        <wd-button size="small" :type="!customMode && rangeDays === 1 ? 'primary' : 'info'" :plain="customMode || rangeDays !== 1" @click="setRangeDays(1)">1 天</wd-button>
        <wd-button size="small" :type="!customMode && rangeDays === 7 ? 'primary' : 'info'" :plain="customMode || rangeDays !== 7" @click="setRangeDays(7)">7 天</wd-button>
        <wd-button size="small" :type="!customMode && rangeDays === 30 ? 'primary' : 'info'" :plain="customMode || rangeDays !== 30" @click="setRangeDays(30)">30 天</wd-button>
        <wd-button size="small" :type="customMode ? 'primary' : 'info'" :plain="!customMode" @click="setCustomRange">自定义</wd-button>
      </view>
      <view v-if="customMode" class="custom-range">
        <view class="range-row">
          <text class="range-label">开始</text>
          <wd-datetime-picker v-model="customStart" type="datetime" />
        </view>
        <view class="range-row">
          <text class="range-label">结束</text>
          <wd-datetime-picker v-model="customEnd" type="datetime" />
        </view>
      </view>
      <view class="filter-title">聚合粒度</view>
      <view class="control-row">
        <wd-button size="small" :type="interval === '1m' ? 'primary' : 'info'" :plain="interval !== '1m'" @click="setIntervalValue('1m')">1 分钟</wd-button>
        <wd-button size="small" :type="interval === '5m' ? 'primary' : 'info'" :plain="interval !== '5m'" @click="setIntervalValue('5m')">5 分钟</wd-button>
        <wd-button size="small" :type="interval === '1h' ? 'primary' : 'info'" :plain="interval !== '1h'" @click="setIntervalValue('1h')">1 小时</wd-button>
        <wd-button size="small" :type="interval === '1d' ? 'primary' : 'info'" :plain="interval !== '1d'" @click="setIntervalValue('1d')">1 天</wd-button>
      </view>
      <wd-button block type="primary" :loading="loading" @click="search">查询历史数据</wd-button>
    </view>

    <view v-if="error" class="notice error">{{ error }}</view>

    <view class="trend-card">
      <view class="section-title">
        <text>{{ loading ? '正在查询...' : `共 ${points.length} 个点位` }}</text>
        <text>{{ interval }}{{ thresholdText ? ` · ${thresholdText}` : '' }}</text>
      </view>
      <view v-if="!points.length" class="empty-state">暂无历史数据</view>
      <view v-else class="bar-chart">
        <view
          v-for="point in chartPoints"
          :key="point.ts"
          class="bar"
          :class="{ 'bar-breach': isPointBreach(point) }"
          :style="{ height: `${Math.max(8, Math.round((Math.abs(point.value) / maxValue) * 160))}rpx` }"
        />
      </view>
    </view>

    <view class="point-list">
      <view v-for="point in points.slice(-20).reverse()" :key="point.ts" class="point-row" :class="{ 'row-breach': isPointBreach(point) }">
        <text>{{ formatDateTime(point.ts) }}</text>
        <view class="point-value">
          <text>{{ formatValue(point.value, sensor?.unit ?? '') }}</text>
          <text v-if="isPointBreach(point)" class="breach-tag">越界</text>
        </view>
      </view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.page {
  min-height: 100vh;
  padding: 24rpx;
  box-sizing: border-box;
}

.hero,
.filter-card,
.trend-card,
.point-list {
  padding: 24rpx;
  border: 1rpx solid $uni-border-color;
  border-radius: 8rpx;
  background: #ffffff;
  margin-bottom: 20rpx;
}

.eyebrow,
.title,
.copy {
  display: block;
}

.eyebrow {
  color: $uni-color-primary;
  font-size: 22rpx;
  font-weight: 700;
}

.title {
  margin-top: 8rpx;
  color: #172033;
  font-size: 36rpx;
  font-weight: 800;
}

.copy {
  margin-top: 8rpx;
  color: $uni-text-color-grey;
  font-size: 24rpx;
}

.filter-title {
  margin: 16rpx 0 12rpx;
  color: #172033;
  font-size: 26rpx;
  font-weight: 700;
}

.control-row {
  display: flex;
  gap: 12rpx;
  overflow-x: auto;
  margin-bottom: 18rpx;
}

.custom-range {
  margin-top: 16rpx;
  padding: 16rpx;
  border: 1rpx solid $uni-border-color;
  border-radius: 8rpx;
  background: #f8fafc;
}

.range-row {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin-bottom: 12rpx;

  &:last-child {
    margin-bottom: 0;
  }
}

.range-label {
  flex-shrink: 0;
  width: 60rpx;
  color: #172033;
  font-size: 24rpx;
  font-weight: 700;
}

.section-title,
.point-row {
  display: flex;
  justify-content: space-between;
  gap: 16rpx;
}

.section-title {
  margin-bottom: 20rpx;
  color: #172033;
  font-size: 28rpx;
  font-weight: 700;

  text:last-child {
    color: $uni-text-color-grey;
    font-size: 24rpx;
    font-weight: 400;
  }
}

.bar-chart {
  height: 180rpx;
  display: flex;
  align-items: flex-end;
  gap: 6rpx;
  padding: 16rpx 0;
  border-bottom: 1rpx solid $uni-border-color;
}

.bar {
  flex: 1;
  min-width: 6rpx;
  border-radius: 4rpx 4rpx 0 0;
  background: linear-gradient(180deg, #38bdf8 0%, #409eff 100%);
}

.bar-breach {
  background: linear-gradient(180deg, #f56c6c 0%, #e6a23c 100%) !important;
}

.point-row {
  padding: 16rpx 0;
  border-bottom: 1rpx solid #f0f2f5;
  font-size: 24rpx;

  text:first-child {
    color: $uni-text-color-grey;
  }

  &.row-breach {
    background: #fef0f0;
  }
}

.point-value {
  display: flex;
  align-items: center;
  gap: 8rpx;

  text:first-child {
    color: #172033;
    font-weight: 700;
  }
}

.breach-tag {
  display: inline-block;
  padding: 2rpx 12rpx;
  border-radius: 6rpx;
  background: #f56c6c;
  color: #ffffff;
  font-size: 20rpx;
  font-weight: 700;
}

.empty-state {
  padding: 48rpx 24rpx;
  color: $uni-text-color-grey;
  text-align: center;
  font-size: 26rpx;
}

.notice {
  margin-bottom: 18rpx;
  padding: 18rpx;
  border-radius: 6rpx;
  font-size: 24rpx;
}

.error {
  color: #b42318;
  background: #fff1f0;
}
</style>
