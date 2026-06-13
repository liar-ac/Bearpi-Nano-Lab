<script setup lang="ts">
import { onHide, onPullDownRefresh, onShow, onUnload } from '@dcloudio/uni-app';
import { subscribeRealtime } from '@/api/realtime';
import { useDeviceStore } from '@/stores/devices';
import type { Device, DeviceStatus } from '@/types/domain';
import { formatValue, relativeTime, statusLabel } from '@/utils/format';

const store = useDeviceStore();
let unsubscribe: (() => void) | null = null;
let refreshTimer: ReturnType<typeof setInterval> | null = null;

const filters: Array<{ label: string; value: DeviceStatus | 'all' }> = [
  { label: '全部', value: 'all' },
  { label: '在线', value: 'online' },
  { label: '异常', value: 'warning' },
  { label: '维护', value: 'maintenance' },
  { label: '离线', value: 'offline' }
];

onShow(() => {
  if (!unsubscribe) unsubscribe = subscribeRealtime(store.applyRealtime);
  if (!refreshTimer) {
    refreshTimer = setInterval(() => {
      void store.loadDevices();
    }, 10000);
  }
  void store.loadDevices();
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
  if (refreshTimer) {
    clearInterval(refreshTimer);
    refreshTimer = null;
  }
}

onPullDownRefresh(async () => {
  await store.loadDevices();
  uni.stopPullDownRefresh();
});

async function changeFilter(value: DeviceStatus | 'all') {
  store.selectedStatus = value;
  await store.loadDevices();
}

function openDevice(device: Device) {
  uni.navigateTo({ url: `/pages/devices/detail?id=${device.id}` });
}

function statusType(status: DeviceStatus) {
  return status === 'online' ? 'success' : status === 'warning' ? 'danger' : status === 'maintenance' ? 'warning' : 'primary';
}
</script>

<template>
  <view class="page">
    <view class="toolbar">
      <view>
        <text class="title">设备列表</text>
        <text class="subtitle">当前接入 {{ store.devices.length }} 台板卡</text>
      </view>
      <wd-button size="small" plain :loading="store.loading" @click="store.loadDevices">刷新</wd-button>
    </view>

    <view class="filter-row">
      <wd-button
        v-for="filter in filters"
        :key="filter.value"
        size="small"
        :plain="store.selectedStatus !== filter.value"
        :type="store.selectedStatus === filter.value ? 'primary' : 'info'"
        @click="changeFilter(filter.value)"
      >
        {{ filter.label }}
      </wd-button>
    </view>

    <view v-if="store.error" class="notice">{{ store.error }}</view>

    <view v-if="!store.loading && !store.filteredDevices.length" class="empty-state">暂无设备</view>
    <view v-else class="device-list">
      <view v-for="device in store.filteredDevices" :key="device.id" class="device-row" @click="openDevice(device)">
        <view class="device-head">
          <view>
            <text class="row-title">{{ device.sn }}</text>
            <text class="row-meta">{{ device.model }} / {{ device.firmwareVersion }}</text>
            <text class="row-meta">槽位 {{ device.slotNo }} / {{ device.location }} / {{ relativeTime(device.lastSeen) }}</text>
            <text class="row-meta">负责人 {{ device.member }}</text>
          </view>
          <wd-tag :type="statusType(device.status)">{{ statusLabel[device.status] }}</wd-tag>
        </view>
        <view v-if="device.sensors.length" class="sensor-strip">
          <view v-for="sensor in device.sensors.slice(0, 4)" :key="sensor.id">
            <text>{{ sensor.name }}</text>
            <text>{{ formatValue(sensor.latest?.value, sensor.unit) }}</text>
          </view>
        </view>
      </view>
    </view>

    <wd-loadmore v-if="store.loading || store.filteredDevices.length" :state="store.loading ? 'loading' : 'finished'" />
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
  align-items: center;
  gap: 20rpx;
  margin-bottom: 20rpx;
}

.title,
.subtitle {
  display: block;
}

.title {
  color: #172033;
  font-size: 38rpx;
  font-weight: 800;
}

.subtitle {
  margin-top: 6rpx;
  color: $uni-text-color-grey;
  font-size: 24rpx;
}

.filter-row {
  display: flex;
  gap: 12rpx;
  overflow-x: auto;
  padding-bottom: 18rpx;
}

.notice {
  margin-bottom: 18rpx;
  padding: 18rpx;
  border-radius: 6rpx;
  color: #b42318;
  background: #fff1f0;
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

.device-list {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}

.device-row {
  padding: 22rpx;
  border: 1rpx solid $uni-border-color;
  border-radius: 8rpx;
  background: #ffffff;
}

.device-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 18rpx;
}

.row-title,
.row-meta {
  display: block;
}

.row-title {
  color: #172033;
  font-size: 28rpx;
  font-weight: 700;
}

.row-meta {
  margin-top: 6rpx;
  color: $uni-text-color-grey;
  font-size: 24rpx;
}

.sensor-strip {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12rpx;
  margin-top: 16rpx;
  padding-top: 16rpx;
  border-top: 1rpx solid #f0f2f5;

  view {
    display: flex;
    justify-content: space-between;
    gap: 12rpx;
  }

  text:first-child {
    color: $uni-text-color-grey;
    font-size: 22rpx;
  }

  text:last-child {
    color: #172033;
    font-size: 24rpx;
    font-weight: 700;
  }
}
</style>
