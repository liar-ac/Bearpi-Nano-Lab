<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue';
import { onHide, onPullDownRefresh, onShow, onUnload } from '@dcloudio/uni-app';
import { ackAlarm, fetchAlarms } from '@/api/lab';
import { subscribeAlarmEvents } from '@/api/realtime';
import { useAuthStore } from '@/stores/auth';
import type { Alarm, AlarmLevel, AlarmStatus, RealtimeAlarmEvent } from '@/types/domain';
import { alarmLevelLabel, formatDateTime } from '@/utils/format';

const auth = useAuthStore();
const alarms = ref<Alarm[]>([]);
const loading = ref(false);
const error = ref('');
const statusFilter = ref<AlarmStatus | ''>('');
const levelFilter = ref<AlarmLevel | ''>('');
let unsubscribeAlarm: (() => void) | null = null;
let refreshTimer: ReturnType<typeof setInterval> | null = null;

const statusOptions: Array<{ label: string; value: AlarmStatus | '' }> = [
  { label: '未关闭', value: '' },
  { label: '待确认', value: 'new' },
  { label: '已确认', value: 'acknowledged' },
  { label: '已关闭', value: 'closed' }
];

const levelOptions: Array<{ label: string; value: AlarmLevel | '' }> = [
  { label: '全部级别', value: '' },
  { label: '提示', value: 'info' },
  { label: '警告', value: 'warning' },
  { label: '严重', value: 'critical' }
];

const alarmStats = computed(() => {
  const total = alarms.value.length;
  const pending = alarms.value.filter((item) => item.status === 'new').length;
  const critical = alarms.value.filter((item) => item.level === 'critical').length;
  const acknowledged = alarms.value.filter((item) => item.status === 'acknowledged').length;
  return { total, pending, critical, acknowledged };
});

onShow(() => {
  void load();
  if (!unsubscribeAlarm) unsubscribeAlarm = subscribeAlarmEvents(applyRealtimeAlarm);
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
  if (unsubscribeAlarm) {
    unsubscribeAlarm();
    unsubscribeAlarm = null;
  }
  if (refreshTimer) {
    clearInterval(refreshTimer);
    refreshTimer = null;
  }
}

async function load() {
  loading.value = true;
  error.value = '';
  try {
    alarms.value = await fetchAlarms({
      status: statusFilter.value || undefined,
      level: levelFilter.value || undefined
    });
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '告警加载失败';
  } finally {
    loading.value = false;
  }
}

function matchesCurrentFilter(alarm: RealtimeAlarmEvent) {
  if (statusFilter.value && alarm.status !== statusFilter.value) return false;
  if (levelFilter.value && alarm.level !== levelFilter.value) return false;
  return true;
}

function applyRealtimeAlarm(alarm: RealtimeAlarmEvent) {
  const rest = alarms.value.filter((item) => item.id !== alarm.id);
  alarms.value = matchesCurrentFilter(alarm) ? [alarm, ...rest] : rest;
}

function selectStatus(value: AlarmStatus | '') {
  statusFilter.value = value;
  void load();
}

function selectLevel(value: AlarmLevel | '') {
  levelFilter.value = value;
  void load();
}

async function acknowledge(alarm: Alarm) {
  if (!auth.canAckAlarm) {
    uni.showToast({ title: '当前角色没有确认告警权限', icon: 'none' });
    return;
  }

  const confirm = await showConfirm(`确认处理告警：${alarm.message}`);
  if (!confirm) return;

  try {
    const next = await ackAlarm(alarm.id);
    alarms.value = alarms.value.map((item) => (item.id === next.id ? next : item));
    uni.showToast({ title: '告警已确认', icon: 'success' });
  } catch (cause) {
    uni.showToast({
      title: cause instanceof Error ? cause.message : '告警确认失败',
      icon: 'none'
    });
  }
}

function showConfirm(content: string) {
  return new Promise<boolean>((resolve) => {
    uni.showModal({
      title: '告警确认',
      content,
      confirmText: '确认',
      cancelText: '取消',
      success: (res) => resolve(res.confirm),
      fail: () => resolve(false)
    });
  });
}

function levelType(alarm: Alarm) {
  return alarm.level === 'critical' ? 'danger' : alarm.level === 'warning' ? 'warning' : 'primary';
}

function statusText(status: AlarmStatus) {
  return status === 'new' ? '待确认' : status === 'acknowledged' ? '已确认' : '已关闭';
}

function statusType(status: AlarmStatus) {
  return status === 'new' ? 'danger' : status === 'closed' ? 'primary' : 'success';
}
</script>

<template>
  <view class="page">
    <view class="toolbar">
      <view>
        <text class="eyebrow">Reserved Alarm Module</text>
        <text class="title">告警中心</text>
        <text class="subtitle">阈值越界、离线告警与维护提示，10秒自动刷新。</text>
      </view>
      <wd-button size="small" plain :loading="loading" @click="load">刷新</wd-button>
    </view>

    <view class="metric-grid">
      <view class="metric-card">
        <text>当前列表</text>
        <text>{{ alarmStats.total }}</text>
      </view>
      <view class="metric-card">
        <text>待确认</text>
        <text>{{ alarmStats.pending }}</text>
      </view>
      <view class="metric-card">
        <text>严重告警</text>
        <text>{{ alarmStats.critical }}</text>
      </view>
      <view class="metric-card">
        <text>已确认</text>
        <text>{{ alarmStats.acknowledged }}</text>
      </view>
    </view>

    <scroll-view class="filter-scroll" scroll-x>
      <view class="filter-row">
        <text class="filter-label">状态</text>
        <wd-button
          v-for="option in statusOptions"
          :key="option.value || 'all'"
          size="small"
          :type="statusFilter === option.value ? 'primary' : 'info'"
          :plain="statusFilter !== option.value"
          @click="selectStatus(option.value)"
        >
          {{ option.label }}
        </wd-button>
      </view>
    </scroll-view>

    <scroll-view class="filter-scroll" scroll-x>
      <view class="filter-row">
        <text class="filter-label">级别</text>
        <wd-button
          v-for="option in levelOptions"
          :key="option.value || 'all'"
          size="small"
          :type="levelFilter === option.value ? 'primary' : 'info'"
          :plain="levelFilter !== option.value"
          @click="selectLevel(option.value)"
        >
          {{ option.label }}
        </wd-button>
      </view>
    </scroll-view>

    <view v-if="!auth.canAckAlarm" class="notice info">
      当前为只读权限：可以查看告警，不能确认或关闭告警。
    </view>
    <view v-if="error" class="notice error">{{ error }}</view>

    <view v-if="!loading && !alarms.length" class="empty-state">暂无告警</view>
    <view v-else class="alarm-list">
      <view v-for="alarm in alarms" :key="alarm.id" class="alarm-card">
        <view class="alarm-top">
          <wd-tag :type="levelType(alarm)">{{ alarmLevelLabel[alarm.level] }}</wd-tag>
          <wd-tag :type="statusType(alarm.status)">
            {{ statusText(alarm.status) }}
          </wd-tag>
        </view>
        <text class="device">{{ alarm.deviceName }}</text>
        <text class="message">{{ alarm.message }}</text>
        <view class="alarm-footer">
          <text>{{ formatDateTime(alarm.ts) }}</text>
          <wd-button
            v-if="alarm.status === 'new'"
            size="small"
            type="primary"
            :disabled="!auth.canAckAlarm"
            @click="acknowledge(alarm)"
          >
            确认
          </wd-button>
        </view>
      </view>
    </view>

    <wd-loadmore v-if="loading || alarms.length" :state="loading ? 'loading' : 'finished'" />
  </view>
</template>

<style lang="scss" scoped>
.page {
  min-height: 100vh;
  padding: 24rpx;
  box-sizing: border-box;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 20rpx;
  margin-bottom: 20rpx;
  padding: 24rpx;
  border: 1rpx solid $uni-border-color;
  border-radius: 10rpx;
  background: #ffffff;
}

.eyebrow,
.title,
.subtitle,
.device,
.message,
.filter-label {
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

.subtitle {
  margin-top: 6rpx;
  color: $uni-text-color-grey;
  font-size: 24rpx;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12rpx;
  margin: 18rpx 0;
}

.metric-card {
  padding: 18rpx;
  border: 1rpx solid $uni-border-color;
  border-radius: 8rpx;
  background: #ffffff;

  text {
    display: block;
  }

  text:first-child {
    color: $uni-text-color-grey;
    font-size: 22rpx;
  }

  text:last-child {
    margin-top: 8rpx;
    color: #172033;
    font-size: 34rpx;
    font-weight: 800;
  }
}

.filter-scroll {
  white-space: nowrap;
  margin-bottom: 12rpx;
}

.filter-row {
  display: inline-flex;
  align-items: center;
  gap: 12rpx;
  padding-bottom: 8rpx;
}

.filter-label {
  margin-right: 8rpx;
  color: $uni-text-color-grey;
  font-size: 24rpx;
  font-weight: 700;
}

.notice {
  margin-bottom: 18rpx;
  padding: 18rpx;
  border-radius: 6rpx;
  font-size: 24rpx;
}

.info {
  color: #245d99;
  background: #eef7ff;
}

.error {
  color: #b42318;
  background: #fff1f0;
}

.alarm-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.alarm-card {
  padding: 24rpx;
  border: 1rpx solid $uni-border-color;
  border-radius: 8rpx;
  background: #ffffff;
}

.alarm-top,
.alarm-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16rpx;
}

.device {
  margin-top: 20rpx;
  color: #172033;
  font-size: 30rpx;
  font-weight: 700;
}

.message {
  margin-top: 8rpx;
  color: $uni-text-color;
  font-size: 26rpx;
  line-height: 1.5;
}

.alarm-footer {
  margin-top: 20rpx;
  color: $uni-text-color-grey;
  font-size: 24rpx;
}

.empty-state {
  padding: 56rpx 24rpx;
  border: 1rpx dashed $uni-border-color;
  border-radius: 8rpx;
  color: $uni-text-color-grey;
  background: #ffffff;
  text-align: center;
  font-size: 26rpx;
}
</style>
