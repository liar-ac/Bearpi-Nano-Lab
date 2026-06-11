<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue';
import { onHide, onPullDownRefresh, onShow, onUnload } from '@dcloudio/uni-app';
import { realtimeState, realtimeStatusLabel, subscribeRealtime } from '@/api/realtime';
import { useDeviceStore } from '@/stores/devices';
import type { Device, DeviceStatus, LabSlot } from '@/types/domain';
import { formatValue, relativeTime, statusLabel } from '@/utils/format';

type TopologyFilter = DeviceStatus | 'all' | 'empty' | 'high_power' | 'stale';
type TopologyLayer = 'status' | 'power' | 'freshness';

const store = useDeviceStore();
const keyword = ref('');
const selectedFilter = ref<TopologyFilter>('all');
const selectedLayer = ref<TopologyLayer>('status');
const selectedSlotNo = ref(1);
let unsubscribe: (() => void) | null = null;
let refreshTimer: ReturnType<typeof setInterval> | null = null;
let alive = true;

const filters: Array<{ label: string; value: TopologyFilter }> = [
  { label: '全部', value: 'all' },
  { label: '在线', value: 'online' },
  { label: '异常', value: 'warning' },
  { label: '离线', value: 'offline' },
  { label: '维护', value: 'maintenance' },
  { label: '空槽', value: 'empty' },
  { label: '高功耗', value: 'high_power' },
  { label: '延迟', value: 'stale' }
];

const layerOptions: Array<{ label: string; value: TopologyLayer }> = [
  { label: '状态', value: 'status' },
  { label: '功耗', value: 'power' },
  { label: '活跃度', value: 'freshness' }
];

const occupiedSlots = computed(() => store.labSlots.filter((slot) => slot.device));
const onlineSlots = computed(() =>
  occupiedSlots.value.filter((slot) => slot.device?.status === 'online' || slot.device?.status === 'warning')
);
const highPowerSlots = computed(() => occupiedSlots.value.filter((slot) => slot.device && isHighPower(slot.device)));
const staleSlots = computed(() => occupiedSlots.value.filter((slot) => slot.device && isStale(slot.device)));

const totalPower = computed(() => onlineSlots.value.reduce((sum, slot) => sum + powerValue(slot.device), 0));

const summaryCards = computed(() => [
  { label: '接入槽位', value: `${occupiedSlots.value.length}/120`, detail: `空槽${120 - occupiedSlots.value.length}个` },
  { label: '在线板卡', value: String(onlineSlots.value.length), detail: '在线和异常计入' },
  { label: '总功耗', value: formatValue(totalPower.value, 'mW'), detail: '在线板卡合计' },
  {
    label: '需关注',
    value: String(highPowerSlots.value.length + staleSlots.value.length),
    detail: '高功耗/上报延迟'
  }
]);

const filteredSlots = computed(() => {
  const query = keyword.value.trim().toLowerCase();
  return store.labSlots.filter((slot) => {
    if (!matchesFilter(slot)) return false;
    if (!query) return true;
    const device = slot.device;
    return [String(slot.slotNo), device?.sn, device?.member, device?.location, device?.ipAddress]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(query));
  });
});

const selectedSlot = computed(
  () => store.labSlots.find((slot) => slot.slotNo === selectedSlotNo.value) ?? store.labSlots[0]
);

onShow(async () => {
  await store.loadDevices({ status: 'all', includeInactive: true });
  if (!alive) return;
  if (!unsubscribe) unsubscribe = subscribeRealtime(store.applyRealtime);
  if (!refreshTimer) {
    refreshTimer = setInterval(() => {
      void store.loadDevices({ status: 'all', includeInactive: true });
    }, 10000);
  }
});

onHide(() => {
  teardown();
});

onUnload(() => {
  alive = false;
  teardown();
});

onBeforeUnmount(() => {
  teardown();
});

onPullDownRefresh(async () => {
  await store.loadDevices({ status: 'all', includeInactive: true });
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

function refreshDevices() {
  void store.loadDevices({ status: 'all', includeInactive: true });
}

function sensorByCode(device: Device | undefined, code: string) {
  return device?.sensors.find((sensor) => sensor.code === code);
}

function powerValue(device: Device | undefined) {
  return sensorByCode(device, 'power')?.latest?.value ?? 0;
}

function voltageValue(device: Device | undefined) {
  return sensorByCode(device, 'voltage')?.latest?.value;
}

function currentValue(device: Device | undefined) {
  return sensorByCode(device, 'current')?.latest?.value;
}

function isHighPower(device: Device) {
  const power = powerValue(device);
  const max = sensorByCode(device, 'power')?.max;
  return power > (typeof max === 'number' ? max : 1200);
}

function isStale(device: Device) {
  if (!device.lastSeen || device.status === 'offline') return false;
  const diff = Date.now() - new Date(device.lastSeen).getTime();
  return Number.isFinite(diff) && diff > 2 * 60_000;
}

function matchesFilter(slot: LabSlot) {
  const device = slot.device;
  if (selectedFilter.value === 'all') return true;
  if (selectedFilter.value === 'empty') return !device;
  if (!device) return false;
  if (selectedFilter.value === 'high_power') return isHighPower(device);
  if (selectedFilter.value === 'stale') return isStale(device);
  return device.status === selectedFilter.value;
}

function slotTone(slot: LabSlot) {
  const device = slot.device;
  if (!device) return 'empty';
  if (selectedLayer.value === 'power') {
    if (isHighPower(device)) return 'high-power';
    if (powerValue(device) > 1200) return 'power-warn';
    return 'power-ok';
  }
  if (selectedLayer.value === 'freshness') {
    if (isStale(device)) return 'stale';
    if (device.status === 'offline') return 'offline';
    return 'fresh';
  }
  if (isHighPower(device)) return 'high-power';
  return device.status;
}

function selectSlot(slot: LabSlot) {
  selectedSlotNo.value = slot.slotNo;
}

function selectFilter(value: TopologyFilter) {
  selectedFilter.value = value;
}

function selectLayer(value: TopologyLayer) {
  selectedLayer.value = value;
}

function openDeviceDetail(device: Device) {
  uni.navigateTo({ url: `/pages/devices/detail?id=${device.id}` });
}

function slotShortLabel(slot: LabSlot) {
  if (!slot.device) return '空闲';
  if (selectedLayer.value === 'power') return `${Math.round(powerValue(slot.device))}`;
  return slot.device.sn.replace('BEARPI-NANO-', '');
}
</script>

<template>
  <view class="page">
    <view class="hero">
      <view>
        <text class="eyebrow">SlotTopology</text>
        <text class="title">120槽位拓扑总览</text>
        <text class="subtitle">先接入先占位，按状态、功耗、活跃度三种视图查看实验室板卡分布。</text>
      </view>
      <view class="hero-meta">
        <text>{{ realtimeStatusLabel[realtimeState.status] }}</text>
        <text>{{ occupiedSlots.length }}块板</text>
        <text>{{ formatValue(totalPower, 'mW') }}</text>
      </view>
    </view>

    <view class="metric-grid">
      <view v-for="card in summaryCards" :key="card.label" class="metric-card">
        <text>{{ card.label }}</text>
        <text>{{ card.value }}</text>
        <text>{{ card.detail }}</text>
      </view>
    </view>

    <view v-if="store.error" class="notice error">{{ store.error }}</view>

    <scroll-view class="filter-scroll" scroll-x>
      <view class="filter-row">
        <text class="filter-label">状态</text>
        <wd-button
          v-for="item in filters"
          :key="item.value"
          size="small"
          :type="selectedFilter === item.value ? 'primary' : 'info'"
          :plain="selectedFilter !== item.value"
          @click="selectFilter(item.value)"
        >
          {{ item.label }}
        </wd-button>
      </view>
    </scroll-view>

    <scroll-view class="filter-scroll" scroll-x>
      <view class="filter-row">
        <text class="filter-label">视图</text>
        <wd-button
          v-for="layer in layerOptions"
          :key="layer.value"
          size="small"
          :type="selectedLayer === layer.value ? 'primary' : 'info'"
          :plain="selectedLayer !== layer.value"
          @click="selectLayer(layer.value)"
        >
          {{ layer.label }}
        </wd-button>
      </view>
    </scroll-view>

    <view class="search-row">
      <wd-input v-model="keyword" placeholder="搜索槽位、SN、成员、IP" clearable />
      <wd-button size="small" plain :loading="store.loading" @click="refreshDevices">刷新</wd-button>
    </view>

    <view class="legend">
      <text class="legend-item is-online">在线</text>
      <text class="legend-item is-warning">异常</text>
      <text class="legend-item is-high">高功耗</text>
      <text class="legend-item is-stale">延迟</text>
      <text class="legend-item is-empty">空槽</text>
    </view>

    <view v-if="!filteredSlots.length" class="empty-state">没有匹配槽位，调整筛选或搜索条件。</view>
    <view v-else class="topology-grid" aria-label="120槽位拓扑网格">
      <view
        v-for="slot in filteredSlots"
        :key="slot.slotNo"
        class="topology-cell"
        :class="[slotTone(slot), { 'is-selected': selectedSlotNo === slot.slotNo }]"
        @click="selectSlot(slot)"
      >
        <text class="slot-index">{{ String(slot.slotNo).padStart(3, '0') }}</text>
        <text v-if="slot.device" class="slot-label">{{ slotShortLabel(slot) }}</text>
        <text v-else class="slot-label">空</text>
      </view>
    </view>

    <view class="detail-card">
      <template v-if="selectedSlot?.device">
        <view class="detail-head">
          <view>
            <text class="eyebrow">Slot{{ selectedSlot.slotNo }}</text>
            <text class="title small">{{ selectedSlot.device.sn }}</text>
          </view>
          <wd-tag :type="selectedSlot.device.status === 'online' ? 'success' : selectedSlot.device.status === 'warning' ? 'danger' : selectedSlot.device.status === 'maintenance' ? 'warning' : 'primary'">
            {{ statusLabel[selectedSlot.device.status] }}
          </wd-tag>
        </view>

        <view class="detail-power">
          <view class="power-cell">
            <text>功耗</text>
            <text>{{ formatValue(powerValue(selectedSlot.device), 'mW') }}</text>
          </view>
          <view class="power-cell">
            <text>电压</text>
            <text>{{ formatValue(voltageValue(selectedSlot.device), 'V') }}</text>
          </view>
          <view class="power-cell">
            <text>电流</text>
            <text>{{ formatValue(currentValue(selectedSlot.device), 'mA') }}</text>
          </view>
        </view>

        <view class="detail-list">
          <text>成员：{{ selectedSlot.device.member }}</text>
          <text>位置：{{ selectedSlot.device.location }}</text>
          <text>IP：{{ selectedSlot.device.ipAddress ?? '未登记' }}</text>
          <text>最近上报：{{ relativeTime(selectedSlot.device.lastSeen) }}</text>
          <text>数据链路：HTTP上报到后端</text>
        </view>

        <view class="flag-row">
          <wd-tag v-if="isHighPower(selectedSlot.device)" type="danger">高功耗</wd-tag>
          <wd-tag v-if="isStale(selectedSlot.device)" type="warning">上报延迟</wd-tag>
          <wd-tag
            v-if="!isHighPower(selectedSlot.device) && !isStale(selectedSlot.device)"
            type="success"
          >
            状态稳定
          </wd-tag>
        </view>

        <wd-button type="primary" block @click="openDeviceDetail(selectedSlot.device)">
          打开板卡详情
        </wd-button>
      </template>
      <template v-else>
        <view class="empty-slot">
          <text class="title small">槽位{{ selectedSlot?.slotNo ?? selectedSlotNo }}空闲</text>
          <text class="subtitle">下一块接入的开发板会按数据库空槽顺序占用。</text>
        </view>
      </template>
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
.metric-card,
.search-row,
.legend,
.detail-card {
  padding: 24rpx;
  border: 1rpx solid $uni-border-color;
  border-radius: 10rpx;
  background: #ffffff;
}

.hero {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;

  text {
    padding: 6rpx 14rpx;
    border-radius: 999rpx;
    background: #eef3fb;
    color: #1d3a6e;
    font-size: 22rpx;
  }
}

.eyebrow,
.title,
.subtitle,
.slot-index,
.slot-label,
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
  margin: 18rpx 0;
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

.filter-scroll {
  white-space: nowrap;
  margin-bottom: 12rpx;
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

.search-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 14rpx;
}

.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 14rpx;
  margin-bottom: 14rpx;
  padding: 14rpx 24rpx;
}

.legend-item {
  font-size: 22rpx;
}

.legend-item.is-online { color: #2f7d32; }
.legend-item.is-warning { color: #9a5b00; }
.legend-item.is-high { color: #b42318; }
.legend-item.is-stale { color: #5b6770; }
.legend-item.is-empty { color: #a0a8b3; }

.notice {
  margin-bottom: 14rpx;
  padding: 16rpx;
  border-radius: 6rpx;
  font-size: 24rpx;
}

.error {
  color: #b42318;
  background: #fff1f0;
}

.topology-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 8rpx;
  margin-bottom: 18rpx;
}

.topology-cell {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-height: 96rpx;
  padding: 10rpx;
  border: 1rpx solid #dde3ec;
  border-radius: 8rpx;
  background: #ffffff;
}

.slot-index {
  font-size: 20rpx;
  color: #5b6770;
  font-weight: 700;
}

.slot-label {
  font-size: 22rpx;
  color: #172033;
  font-weight: 700;
  word-break: break-all;
}

.topology-cell.is-selected {
  border-color: #1989fa;
  box-shadow: 0 0 0 2rpx rgba(25, 137, 250, 0.25);
}

.topology-cell.empty { background: #f6f8fc; }
.topology-cell.online,
.topology-cell.fresh,
.topology-cell.power-ok {
  border-color: #b6e0bf;
  background: #f0fbf3;
}
.topology-cell.warning,
.topology-cell.power-warn {
  border-color: #f0c878;
  background: #fff7e6;
}
.topology-cell.high-power {
  border-color: #f0a8a8;
  background: #fff1f0;
}
.topology-cell.offline,
.topology-cell.stale {
  border-color: #d6dae0;
  background: #f3f4f6;
}
.topology-cell.maintenance {
  border-color: #b6d5f5;
  background: #eaf3ff;
}

.empty-state {
  margin-bottom: 18rpx;
  padding: 56rpx 24rpx;
  border: 1rpx dashed $uni-border-color;
  border-radius: 8rpx;
  color: $uni-text-color-grey;
  background: #ffffff;
  text-align: center;
  font-size: 26rpx;
}

.detail-card {
  display: flex;
  flex-direction: column;
  gap: 18rpx;
}

.detail-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 18rpx;
}

.detail-power {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12rpx;
}

.power-cell {
  padding: 16rpx;
  border: 1rpx solid $uni-border-color;
  border-radius: 8rpx;
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
    margin-top: 6rpx;
    color: #172033;
    font-size: 28rpx;
    font-weight: 800;
  }
}

.detail-list {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
  color: $uni-text-color-grey;
  font-size: 24rpx;

  text {
    color: $uni-text-color;
  }
}

.flag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10rpx;
}

.empty-slot {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
  padding: 32rpx 0;
  text-align: center;
}
</style>
