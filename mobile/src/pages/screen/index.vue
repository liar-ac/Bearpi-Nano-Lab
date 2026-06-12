<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue';
import { onHide, onShow, onUnload } from '@dcloudio/uni-app';
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
let clockTimer: ReturnType<typeof setInterval> | null = null;
let refreshTimer: ReturnType<typeof setInterval> | null = null;

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

const slotPreview = computed(() => store.labSlots.filter((slot) => slot.device).slice(0, 36));

onShow(() => {
  if (!unsubscribe) unsubscribe = subscribeRealtime(store.applyRealtime);
  if (!clockTimer) {
    clockTimer = setInterval(() => {
      now.value = new Date();
    }, 1000);
  }
  if (!refreshTimer) {
    refreshTimer = setInterval(() => {
      void load();
    }, 10000);
  }
  void load();
});

onHide(() => {
  teardown();
});

onUnload(() => {
  teardown();
});

function teardown() {
  unsubscribe?.();
  unsubscribe = null;
  if (clockTimer !== null) {
    clearInterval(clockTimer);
    clockTimer = null;
  }
  if (refreshTimer !== null) {
    clearInterval(refreshTimer);
    refreshTimer = null;
  }
}

async function load() {
  if (loading.value) return;
  loading.value = true;
  error.value = '';
  try {
    try {
      await store.loadDevices({ status: 'all', includeInactive: true });
      if (store.error) error.value = store.error;
    } catch {
      error.value = '设备数据加载失败';
    }
    try {
      alarms.value = await fetchAlarms({ limit: 100 });
    } catch {
      error.value = error.value || '告警数据加载失败';
    }
  } finally {
    loading.value = false;
  }
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

function openDevice(device: Device) {
  uni.navigateTo({ url: `/pages/devices/detail?id=${device.id}` });
}

function goBack() {
  const pages = getCurrentPages();
  if (pages.length > 1) {
    uni.navigateBack();
  } else {
    uni.reLaunch({ url: '/pages/dashboard/index' });
  }
}
</script>

<template>
  <view class="screen-page">
    <view class="screen-header">
      <view class="screen-title">
        <view class="back-btn" @click="goBack">
          <text class="back-icon">&lt;</text>
        </view>
        <view>
          <text class="screen-eyebrow">BearPi Nano Lab / Real-Time Command Screen</text>
          <text class="screen-heading">实时大屏</text>
        </view>
      </view>
      <view class="screen-clock">
        <text class="clock-time">{{ timeText() }}</text>
        <text class="clock-date">{{ dateText() }}</text>
      </view>
    </view>

    <text v-if="loading" class="screen-loading">正在刷新大屏数据...</text>

    <view class="kpi-row">
      <view class="kpi-card kpi-good">
        <text class="kpi-label">在线率</text>
        <text class="kpi-value">{{ onlineRate }}%</text>
        <text class="kpi-detail">{{ store.statusCounts.online }} / {{ store.devices.length }} 台在线</text>
      </view>
      <view class="kpi-card kpi-warn">
        <text class="kpi-label">待处理告警</text>
        <text class="kpi-value">{{ activeAlarms.length }}</text>
        <text class="kpi-detail">严重 {{ criticalAlarms.length }} 条</text>
      </view>
    </view>

    <view class="kpi-row">
      <view class="kpi-card kpi-cyan">
        <text class="kpi-label">实时通道</text>
        <text class="kpi-value">{{ realtimeStatusLabel[realtimeState.status] }}</text>
        <text class="kpi-detail">{{ realtimeState.lastMessageAt ? relativeTime(realtimeState.lastMessageAt) : realtimeState.error || '等待数据' }}</text>
      </view>
      <view class="kpi-card kpi-blue">
        <text class="kpi-label">设备总数</text>
        <text class="kpi-value">{{ store.devices.length }}</text>
        <text class="kpi-detail">MySQL保存设备与历史数据</text>
      </view>
    </view>

    <view class="panel">
      <view class="panel-heading">
        <text class="panel-title">接入槽位</text>
        <text class="panel-badge">{{ slotPreview.length }} active</text>
      </view>
      <view v-if="slotPreview.length" class="slot-grid">
        <view
          v-for="slot in slotPreview"
          :key="slot.slotNo"
          :class="['slot-cell', slot.status]"
        >
          <text>{{ slot.slotNo }}</text>
        </view>
      </view>
      <view v-else class="empty-block">
        <text>暂无活跃接入板卡</text>
      </view>
    </view>

    <view class="panel">
      <view class="panel-heading">
        <text class="panel-title">异常优先队列</text>
        <text class="panel-badge">{{ riskDevices.length }} risk</text>
      </view>
      <view v-if="riskDevices.length" class="risk-list">
        <view
          v-for="item in riskDevices"
          :key="item.device.id"
          class="risk-row"
          @click="openDevice(item.device)"
        >
          <view class="risk-score">
            <text>{{ item.score }}</text>
          </view>
          <view class="risk-info">
            <text class="risk-sn">{{ item.device.sn }}</text>
            <text class="risk-reasons">{{ item.reasons.join(' / ') }}</text>
          </view>
          <text class="risk-time">{{ relativeTime(item.device.lastSeen) }}</text>
        </view>
      </view>
      <view v-else class="empty-block">
        <text>当前没有高优先级风险</text>
      </view>
    </view>

    <view class="panel">
      <view class="panel-heading">
        <text class="panel-title">最近告警</text>
        <text class="panel-badge">{{ recentAlarms.length }} shown</text>
      </view>
      <view v-if="recentAlarms.length" class="alarm-list">
        <view
          v-for="alarm in recentAlarms"
          :key="alarm.id"
          :class="['alarm-row', `alarm-${alarm.level}`]"
        >
          <text class="alarm-level">{{ alarmLevelLabel[alarm.level] }}</text>
          <view class="alarm-info">
            <text class="alarm-device">{{ alarm.deviceName }}</text>
            <text class="alarm-msg">{{ alarm.message }}</text>
          </view>
          <text class="alarm-time">{{ relativeTime(alarm.ts) }}</text>
        </view>
      </view>
      <view v-else class="empty-block">
        <text>暂无告警</text>
      </view>
    </view>

    <view class="panel">
      <view class="panel-heading">
        <text class="panel-title">链路健康度</text>
        <text :class="['health-tone', `tone-${realtimeTone}`]">{{ realtimeStatusLabel[realtimeState.status] }}</text>
      </view>
      <view class="health-flow">
        <view :class="['health-item', 'good']">
          <text>设备接入 {{ store.devices.length }}</text>
        </view>
        <view :class="['health-item', realtimeTone]">
          <text>Channels {{ realtimeStatusLabel[realtimeState.status] }}</text>
        </view>
      </view>
      <text v-if="error" class="screen-error">{{ error }}</text>
      <text v-else class="screen-note">大屏每10秒刷新REST统计，WebSocket消息会实时更新设备状态。</text>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.screen-page {
  min-height: 100vh;
  padding: 24rpx;
  box-sizing: border-box;
  background: #071018;
}

.screen-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24rpx;
}

.screen-title {
  display: flex;
  align-items: center;
  gap: 16rpx;
  flex: 1;
  min-width: 0;
}

.back-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 68rpx;
  height: 68rpx;
  border: 1rpx solid rgba(56, 189, 248, 0.32);
  border-radius: 12rpx;
  background: rgba(56, 189, 248, 0.1);
}

.back-icon {
  color: #38bdf8;
  font-size: 32rpx;
  font-weight: 700;
}

.screen-eyebrow {
  display: block;
  color: rgba(255, 255, 255, 0.5);
  font-size: 20rpx;
  font-weight: 700;
}

.screen-heading {
  display: block;
  margin-top: 4rpx;
  color: #ffffff;
  font-size: 36rpx;
  font-weight: 800;
}

.screen-clock {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.clock-time {
  font-family: monospace;
  font-size: 40rpx;
  font-weight: 700;
  color: #22c55e;
}

.clock-date {
  margin-top: 4rpx;
  color: rgba(255, 255, 255, 0.5);
  font-size: 22rpx;
}

.screen-loading {
  display: block;
  margin-bottom: 16rpx;
  color: rgba(255, 255, 255, 0.5);
  font-size: 24rpx;
}

.kpi-row {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16rpx;
  margin-bottom: 16rpx;
}

.kpi-card {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
  padding: 24rpx;
  border-radius: 12rpx;
  border: 1rpx solid rgba(188, 238, 255, 0.15);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.055), rgba(255, 255, 255, 0.012)), rgba(17, 26, 34, 0.88);
}

.kpi-label {
  color: rgba(255, 255, 255, 0.5);
  font-size: 22rpx;
  font-weight: 800;
}

.kpi-value {
  color: #ffffff;
  font-size: 40rpx;
  font-weight: 800;
}

.kpi-detail {
  color: rgba(255, 255, 255, 0.4);
  font-size: 22rpx;
}

.kpi-good .kpi-value { color: #22c55e; }
.kpi-warn .kpi-value { color: #f59e0b; }
.kpi-cyan .kpi-value { color: #38bdf8; }
.kpi-blue .kpi-value { color: #60a5fa; }

.panel {
  padding: 24rpx;
  margin-bottom: 16rpx;
  border-radius: 12rpx;
  border: 1rpx solid rgba(188, 238, 255, 0.15);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.055), rgba(255, 255, 255, 0.012)), rgba(17, 26, 34, 0.88);
}

.panel-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16rpx;
}

.panel-title {
  color: #ffffff;
  font-size: 28rpx;
  font-weight: 800;
}

.panel-badge {
  padding: 4rpx 16rpx;
  border: 1rpx solid rgba(56, 189, 248, 0.25);
  border-radius: 999rpx;
  color: #38bdf8;
  background: rgba(56, 189, 248, 0.08);
  font-size: 22rpx;
}

.slot-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 10rpx;
}

.slot-cell {
  display: flex;
  align-items: center;
  justify-content: center;
  aspect-ratio: 1;
  min-height: 56rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  border-radius: 8rpx;
  background: rgba(255, 255, 255, 0.03);

  text {
    color: rgba(255, 255, 255, 0.4);
    font-family: monospace;
    font-size: 22rpx;
    font-weight: 800;
  }
}

.slot-cell.online {
  border-color: rgba(45, 212, 125, 0.58);
  background: rgba(45, 212, 125, 0.1);

  text { color: #22c55e; }
}

.slot-cell.warning {
  border-color: rgba(246, 184, 75, 0.65);
  background: rgba(246, 184, 75, 0.1);

  text { color: #f59e0b; }
}

.slot-cell.offline {
  border-color: rgba(112, 129, 141, 0.42);

  text { color: rgba(255, 255, 255, 0.25); }
}

.slot-cell.maintenance {
  border-color: rgba(56, 189, 248, 0.56);
  background: rgba(56, 189, 248, 0.09);

  text { color: #38bdf8; }
}

.risk-list,
.alarm-list {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.risk-row {
  display: flex;
  align-items: center;
  gap: 16rpx;
  padding: 16rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  border-radius: 10rpx;
  background: rgba(255, 255, 255, 0.03);
}

.risk-score {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 64rpx;
  height: 64rpx;
  border-radius: 10rpx;
  background: #f59e0b;

  text {
    color: #160b04;
    font-family: monospace;
    font-size: 24rpx;
    font-weight: 800;
  }
}

.risk-info {
  flex: 1;
  min-width: 0;
}

.risk-sn {
  display: block;
  color: #ffffff;
  font-size: 26rpx;
  font-weight: 800;
}

.risk-reasons {
  display: block;
  margin-top: 4rpx;
  color: rgba(255, 255, 255, 0.4);
  font-size: 22rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.risk-time {
  color: rgba(255, 255, 255, 0.4);
  font-size: 22rpx;
  white-space: nowrap;
}

.alarm-row {
  display: flex;
  align-items: center;
  gap: 16rpx;
  padding: 16rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  border-radius: 10rpx;
  background: rgba(255, 255, 255, 0.03);
}

.alarm-level {
  min-width: 80rpx;
  text-align: center;
  font-size: 22rpx;
  font-weight: 900;
}

.alarm-info {
  flex: 1;
  min-width: 0;
}

.alarm-device {
  display: block;
  color: #ffffff;
  font-size: 26rpx;
  font-weight: 800;
}

.alarm-msg {
  display: block;
  margin-top: 4rpx;
  color: rgba(255, 255, 255, 0.4);
  font-size: 22rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.alarm-time {
  color: rgba(255, 255, 255, 0.4);
  font-size: 22rpx;
  white-space: nowrap;
}

.alarm-info .alarm-level { color: #38bdf8; }
.alarm-warning .alarm-level { color: #f59e0b; }
.alarm-critical .alarm-level { color: #ef4444; }

.health-flow {
  display: flex;
  flex-direction: column;
  gap: 10rpx;
}

.health-item {
  padding: 14rpx 20rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  border-radius: 10rpx;
  background: rgba(255, 255, 255, 0.03);

  text {
    font-size: 26rpx;
    font-weight: 800;
  }
}

.health-item.good text { color: #22c55e; }
.health-item.warn text { color: #f59e0b; }
.health-item.bad text { color: #ef4444; }

.health-tone {
  font-size: 24rpx;
  font-weight: 700;
}

.tone-good { color: #22c55e; }
.tone-warn { color: #f59e0b; }
.tone-bad { color: #ef4444; }

.screen-note {
  display: block;
  margin-top: 16rpx;
  color: rgba(255, 255, 255, 0.4);
  font-size: 22rpx;
  line-height: 1.6;
}

.screen-error {
  display: block;
  margin-top: 16rpx;
  color: #ef4444;
  font-size: 22rpx;
  line-height: 1.6;
}

.empty-block {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 180rpx;
  border: 1rpx dashed rgba(255, 255, 255, 0.15);
  border-radius: 10rpx;

  text {
    color: rgba(255, 255, 255, 0.4);
    font-size: 26rpx;
  }
}
</style>
