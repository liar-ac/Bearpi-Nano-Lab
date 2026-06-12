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
const loading = ref(false);
const error = ref('');

const points = computed<Point[]>(() => data.value?.points ?? []);
const maxValue = computed(() => Math.max(...points.value.map((point) => Math.abs(point.value)), 1));
const chartPoints = computed(() => points.value.slice(-40));

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
  loading.value = true;
  const end = new Date();
  const start = new Date(Date.now() - rangeDays.value * 24 * 60 * 60_000);
  try {
    error.value = '';
    data.value = await fetchHistory(sensorId.value, {
      start: start.toISOString(),
      end: end.toISOString(),
      interval: interval.value
    });
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '历史数据查询失败';
  } finally {
    loading.value = false;
  }
}

function setIntervalValue(value: HistoryInterval) {
  interval.value = value;
}

function setRangeDays(value: number) {
  rangeDays.value = value;
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
        <wd-button size="small" :type="rangeDays === 1 ? 'primary' : 'info'" :plain="rangeDays !== 1" @click="setRangeDays(1)">1 天</wd-button>
        <wd-button size="small" :type="rangeDays === 7 ? 'primary' : 'info'" :plain="rangeDays !== 7" @click="setRangeDays(7)">7 天</wd-button>
        <wd-button size="small" :type="rangeDays === 30 ? 'primary' : 'info'" :plain="rangeDays !== 30" @click="setRangeDays(30)">30 天</wd-button>
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
        <text>{{ interval }}</text>
      </view>
      <view v-if="!points.length" class="empty-state">暂无历史数据</view>
      <view v-else class="bar-chart">
        <view
          v-for="point in chartPoints"
          :key="point.ts"
          class="bar"
          :style="{ height: `${Math.max(8, Math.round((Math.abs(point.value) / maxValue) * 160))}rpx` }"
        />
      </view>
    </view>

    <view class="point-list">
      <view v-for="point in points.slice(-20).reverse()" :key="point.ts" class="point-row">
        <text>{{ formatDateTime(point.ts) }}</text>
        <text>{{ formatValue(point.value, sensor?.unit ?? '') }}</text>
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
