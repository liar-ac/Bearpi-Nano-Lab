<script setup lang="ts">
import { computed, ref } from 'vue';
import { onHide, onLoad, onShow, onUnload } from '@dcloudio/uni-app';
import { fetchDevice, simulateRealtime } from '@/api/lab';
import { realtimeState, realtimeStatusLabel, subscribeRealtime } from '@/api/realtime';
import type { Device, Point, RealtimeMessage, Sensor } from '@/types/domain';
import { formatDateTime, formatValue } from '@/utils/format';

const deviceId = ref<number | null>(null);
const sensorId = ref<number | null>(null);
const device = ref<Device | null>(null);
const sensor = ref<Sensor | null>(null);
const points = ref<Point[]>([]);
const refreshMs = ref(1000);
const paused = ref(false);
const simulating = ref(false);
const error = ref('');
const lastAppendAt = ref(0);
let unsubscribe: (() => void) | null = null;
let alive = true;

const chartPoints = computed(() => points.value.slice(-36));
const maxValue = computed(() => Math.max(...chartPoints.value.map((point) => Math.abs(point.value)), 1));

const thresholdText = computed(() => {
  const s = sensor.value;
  if (!s || s.min == null && s.max == null) return '';
  const unit = s.unit || '';
  if (s.min != null && s.max != null) return `阈值 ${s.min}~${s.max} ${unit}`;
  if (s.min != null) return `下限 ${s.min} ${unit}`;
  return `上限 ${s.max} ${unit}`;
});
const isBreach = computed(() => {
  const s = sensor.value;
  const v = s?.latest?.value;
  if (v == null || !s) return false;
  return (s.min != null && v < s.min) || (s.max != null && v > s.max);
});

onLoad(async (query) => {
  const parsedDeviceId = Number(query?.deviceId) || 0;
  const parsedSensorId = Number(query?.sensorId) || 0;
  deviceId.value = Number.isFinite(parsedDeviceId) ? parsedDeviceId : 0;
  sensorId.value = Number.isFinite(parsedSensorId) ? parsedSensorId : 0;
  await load();
  if (!alive) return;
  if (deviceId.value && sensorId.value && !unsubscribe) {
    unsubscribe = subscribeRealtime(appendRealtimePoint);
  }
});

onShow(() => {
  if (alive && deviceId.value && sensorId.value && !unsubscribe) {
    unsubscribe = subscribeRealtime(appendRealtimePoint);
  }
});

onHide(() => {
  unsubscribe?.();
  unsubscribe = null;
});

onUnload(() => {
  alive = false;
  unsubscribe?.();
  unsubscribe = null;
});

async function load() {
  if (!deviceId.value || !sensorId.value) {
    error.value = '传感器参数无效';
    return;
  }
  try {
    device.value = await fetchDevice(deviceId.value);
    sensor.value = device.value.sensors.find((item) => item.id === sensorId.value) ?? null;
    points.value = sensor.value?.latest ? [{ ts: sensor.value.latest.ts, value: sensor.value.latest.value }] : [];
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '实时数据加载失败';
  }
}

function appendRealtimePoint(message: RealtimeMessage, options: { force?: boolean; throttle?: boolean } = {}) {
  if (message.sensorId !== sensorId.value) return;
  if (paused.value && !options.force) return;

  const latest = points.value[points.value.length - 1];
  if (latest?.ts === message.ts) return;

  const now = Date.now();
  if ((options.throttle ?? true) && now - lastAppendAt.value < refreshMs.value) return;
  lastAppendAt.value = now;

  sensor.value = sensor.value ? { ...sensor.value, latest: { ts: message.ts, value: message.value } } : sensor.value;
  points.value = [...points.value.slice(-119), { ts: message.ts, value: message.value }];
}

async function simulatePoint() {
  if (!sensor.value || simulating.value) return;
  simulating.value = true;
  try {
    const message = await simulateRealtime(sensor.value.id);
    appendRealtimePoint(message, { force: true, throttle: false });
    uni.showToast({ title: '已模拟上报', icon: 'success' });
  } catch (cause) {
    uni.showToast({ title: cause instanceof Error ? cause.message : '模拟上报失败', icon: 'none' });
  } finally {
    simulating.value = false;
  }
}

function setRefreshMs(value: number) {
  refreshMs.value = value;
}
</script>

<template>
  <view class="page">
    <view v-if="error" class="notice error">{{ error }}</view>
    <template v-if="device && sensor">
      <view class="hero">
        <text class="eyebrow">{{ device.sn }} / {{ sensor.code }}</text>
        <text class="title">{{ sensor.name }}实时监测</text>
        <view class="runtime">
          <text>{{ realtimeStatusLabel[realtimeState.status] }}</text>
          <text>{{ realtimeState.error || 'Django Channels WebSocket' }}</text>
        </view>
      </view>

      <view class="value-card" :class="{ breach: isBreach }">
        <text>当前值</text>
        <text>{{ formatValue(sensor.latest?.value, sensor.unit) }}</text>
        <text v-if="isBreach" class="breach-tag">越界</text>
        <text v-if="thresholdText" class="threshold-text">{{ thresholdText }}</text>
        <text>{{ formatDateTime(sensor.latest?.ts) }}</text>
      </view>

      <view class="control-row">
        <wd-button size="small" :type="refreshMs === 1000 ? 'primary' : 'info'" :plain="refreshMs !== 1000" @click="setRefreshMs(1000)">1 秒</wd-button>
        <wd-button size="small" :type="refreshMs === 5000 ? 'primary' : 'info'" :plain="refreshMs !== 5000" @click="setRefreshMs(5000)">5 秒</wd-button>
        <wd-button size="small" :type="refreshMs === 10000 ? 'primary' : 'info'" :plain="refreshMs !== 10000" @click="setRefreshMs(10000)">10 秒</wd-button>
        <wd-button size="small" plain @click="paused = !paused">{{ paused ? '继续' : '暂停' }}</wd-button>
        <wd-button size="small" type="primary" :loading="simulating" @click="simulatePoint">模拟</wd-button>
      </view>

      <view class="trend-card">
        <view class="section-title">
          <text>最近 {{ chartPoints.length }} 个点位</text>
          <text>{{ paused ? '已暂停' : '实时刷新' }}</text>
        </view>
        <view class="bar-chart">
          <view
            v-for="point in chartPoints"
            :key="point.ts"
            class="bar"
            :class="{ 'bar-breach': sensor && ((sensor.min != null && point.value < sensor.min) || (sensor.max != null && point.value > sensor.max)) }"
            :style="{ height: `${Math.max(8, Math.round((Math.abs(point.value) / maxValue) * 160))}rpx` }"
          />
        </view>
      </view>

      <view class="point-list">
        <view v-for="point in points.slice(-8).reverse()" :key="point.ts" class="point-row">
          <text>{{ formatDateTime(point.ts) }}</text>
          <text>{{ formatValue(point.value, sensor.unit) }}</text>
        </view>
      </view>
    </template>
  </view>
</template>

<style lang="scss" scoped>
.page {
  min-height: 100vh;
  padding: 24rpx;
  box-sizing: border-box;
}

.hero,
.value-card,
.trend-card,
.point-list {
  padding: 24rpx;
  border: 1rpx solid $uni-border-color;
  border-radius: 8rpx;
  background: #ffffff;
  margin-bottom: 20rpx;
}

.eyebrow,
.title {
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

.runtime {
  display: flex;
  justify-content: space-between;
  gap: 16rpx;
  margin-top: 20rpx;
  padding: 18rpx;
  border-radius: 6rpx;
  color: #245d99;
  background: #eef7ff;
  font-size: 24rpx;
}

.value-card {
  display: flex;
  flex-direction: column;
  gap: 8rpx;

  text:first-child,
  text:last-child {
    color: $uni-text-color-grey;
    font-size: 24rpx;
  }

  text:nth-child(2) {
    color: #172033;
    font-size: 54rpx;
    font-weight: 800;
  }

  &.breach {
    border-color: #f56c6c;
    background: #fef0f0;
  }

  &.breach text:nth-child(2) {
    color: #b42318;
  }
}

.breach-tag {
  display: inline-block;
  padding: 2rpx 12rpx;
  border-radius: 6rpx;
  background: #f56c6c;
  color: #ffffff;
  font-size: 22rpx;
  font-weight: 700;
  align-self: flex-start;
}

.threshold-text {
  color: $uni-text-color-grey;
  font-size: 22rpx;
}

.control-row {
  display: flex;
  gap: 12rpx;
  overflow-x: auto;
  margin-bottom: 20rpx;
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
  background: linear-gradient(180deg, #2dd47d 0%, #409eff 100%);
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

  text:last-child {
    color: #172033;
    font-weight: 700;
  }
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
