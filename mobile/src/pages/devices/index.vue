<script setup lang="ts">
import { onPullDownRefresh, onShow } from '@dcloudio/uni-app';
import { useDeviceStore } from '@/stores/devices';
import type { Device, DeviceStatus } from '@/types/domain';
import { relativeTime, statusLabel } from '@/utils/format';

const store = useDeviceStore();

const filters: Array<{ label: string; value: DeviceStatus | 'all' }> = [
  { label: '全部', value: 'all' },
  { label: '在线', value: 'online' },
  { label: '异常', value: 'warning' },
  { label: '维护', value: 'maintenance' },
  { label: '离线', value: 'offline' }
];

onShow(() => {
  void store.loadDevices();
});

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
    <wd-cell-group v-else border>
      <wd-cell
        v-for="device in store.filteredDevices"
        :key="device.id"
        is-link
        :title="device.sn"
        :label="`槽位 ${device.slotNo} / ${device.location} / ${relativeTime(device.lastSeen)}`"
        @click="openDevice(device)"
      >
        <template #value>
          <wd-tag :type="statusType(device.status)">{{ statusLabel[device.status] }}</wd-tag>
        </template>
      </wd-cell>
    </wd-cell-group>

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
</style>
