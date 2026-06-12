<script setup lang="ts">
import { computed, ref } from 'vue';
import { onHide, onPullDownRefresh, onShow, onUnload } from '@dcloudio/uni-app';
import AiQuery from '@/components/AiQuery.vue';
import { fetchAlarms, sendBulkCommand } from '@/api/lab';
import { realtimeState, realtimeStatusLabel, subscribeRealtime } from '@/api/realtime';
import { useAuthStore } from '@/stores/auth';
import { useDeviceStore } from '@/stores/devices';
import type { Alarm, Device, DeviceStatus } from '@/types/domain';
import { alarmLevelLabel, formatValue, relativeTime, statusLabel } from '@/utils/format';

const store = useDeviceStore();
const auth = useAuthStore();
const alarms = ref<Alarm[]>([]);
const dashboardLoading = ref(false);
let unsubscribe: (() => void) | null = null;
let refreshTimer: ReturnType<typeof setInterval> | null = null;

const onlineRate = computed(() => {
  if (!store.devices.length) return '0%';
  return `${Math.round((store.statusCounts.online / store.devices.length) * 100)}%`;
});

const realtimeTone = computed(() => {
  if (realtimeState.status === 'online' || realtimeState.status === 'mock') return 'good';
  if (realtimeState.status === 'connecting' || realtimeState.status === 'reconnecting') return 'warn';
  return 'bad';
});

const priorityDevices = computed(() =>
  store.devices
    .map((device) => ({
      device,
      score: riskScore(device),
      reasons: riskReasons(device)
    }))
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 6)
);

const recentAlarms = computed(() => alarms.value.slice(0, 3));
const controllableDevices = computed(() =>
  store.devices.filter((device) => device.status === 'online' || device.status === 'warning')
);

onShow(async () => {
  if (!unsubscribe) unsubscribe = subscribeRealtime(store.applyRealtime);
  if (!refreshTimer) {
    refreshTimer = setInterval(() => {
      void load();
    }, 10000);
  }
  await load();
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
  await load();
  uni.stopPullDownRefresh();
});

async function load() {
  if (dashboardLoading.value) return;
  dashboardLoading.value = true;
  try {
    await store.loadDevices({ status: 'all' });
    try {
      alarms.value = await fetchAlarms();
    } catch {
      alarms.value = [];
    }
  } finally {
    dashboardLoading.value = false;
  }
}

function openDevice(device: Device) {
  uni.navigateTo({ url: `/pages/devices/detail?id=${device.id}` });
}

function openUsers() {
  uni.navigateTo({ url: '/pages/users/index' });
}

function openRules() {
  uni.navigateTo({ url: '/pages/rules/index' });
}

function openAudit() {
  uni.navigateTo({ url: '/pages/audit/index' });
}

function openTasks() {
  uni.navigateTo({ url: '/pages/tasks/index' });
}

function openTopology() {
  uni.navigateTo({ url: '/pages/topology/index' });
}

function openPower() {
  uni.navigateTo({ url: '/pages/power/index' });
}

function openScreen() {
  uni.navigateTo({ url: '/pages/screen/index' });
}

function logout() {
  auth.logout();
  uni.reLaunch({ url: '/pages/login/index' });
}

function statusType(status: DeviceStatus) {
  return status === 'online' ? 'success' : status === 'warning' ? 'danger' : status === 'maintenance' ? 'warning' : 'primary';
}

function isStale(device: Device) {
  if (!device.lastSeen || device.status === 'offline') return false;
  const diff = Date.now() - new Date(device.lastSeen).getTime();
  return Number.isFinite(diff) && diff > 2 * 60_000;
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

async function runBulkControl(actuator: 'motor' | 'light', mode: 'auto' | 'on' | 'off') {
  if (!auth.canCommand) {
    uni.showToast({ title: '当前角色没有批量控制权限', icon: 'none' });
    return;
  }
  if (!controllableDevices.value.length) {
    uni.showToast({ title: '暂无可控在线板卡', icon: 'none' });
    return;
  }
  const actuatorLabel = actuator === 'motor' ? '电机' : '补光灯';
  const modeLabel = mode === 'auto' ? '自动' : mode === 'on' ? '打开' : '关闭';
  const confirmed = await showConfirm(`确认向 ${controllableDevices.value.length} 台板卡下发「${actuatorLabel}${modeLabel}」？`);
  if (!confirmed) return;
  try {
    const result = await sendBulkCommand({ target: 'online', actuator, mode });
    const t = result.executeAt ? new Date(result.executeAt).toLocaleTimeString() : '';
    uni.showToast({ title: `已创建${result.count}条同步指令${t ? `，预计${t}执行` : ''}`, icon: 'success' });
  } catch (cause) {
    uni.showToast({ title: cause instanceof Error ? cause.message : '批量控制失败', icon: 'none' });
  }
}

function showConfirm(content: string) {
  return new Promise<boolean>((resolve) => {
    uni.showModal({
      title: '批量控制确认',
      content,
      confirmText: '确认',
      cancelText: '取消',
      success: (res) => resolve(res.confirm),
      fail: () => resolve(false)
    });
  });
}
</script>

<template>
  <view class="page">
    <view class="header-band">
      <view>
        <text class="eyebrow">Incident First Console</text>
        <text class="title">异常优先值班台</text>
        <text class="copy">实时查看板卡接入、离线、告警与云同步状态。</text>
      </view>
      <view class="quick-actions">
        <AiQuery />
        <wd-button size="small" plain @click="openTopology">槽位拓扑</wd-button>
        <wd-button size="small" plain @click="openScreen">实时大屏</wd-button>
        <wd-button size="small" plain @click="openPower">功耗监控</wd-button>
        <wd-button size="small" plain @click="openRules">规则配置</wd-button>
        <wd-button size="small" plain @click="openTasks">任务中心</wd-button>
        <wd-button v-if="auth.canManageUsers" size="small" plain @click="openAudit">审计日志</wd-button>
        <wd-button v-if="auth.canManageUsers" size="small" plain @click="openUsers">用户权限</wd-button>
        <wd-button size="small" plain @click="logout">退出</wd-button>
      </view>
      <view class="runtime" :class="`runtime-${realtimeTone}`">
        <text>{{ realtimeStatusLabel[realtimeState.status] }}</text>
        <text v-if="realtimeState.lastMessageAt">最近 {{ relativeTime(realtimeState.lastMessageAt) }}</text>
        <text v-else>{{ realtimeState.error || '等待实时数据' }}</text>
      </view>
    </view>

    <view class="metric-grid">
      <view class="metric-card danger">
        <text>待处理</text>
        <text>{{ priorityDevices.length }}</text>
        <text>{{ priorityDevices.length ? '按状态优先展示' : '当前稳定' }}</text>
      </view>
      <view class="metric-card success">
        <text>在线率</text>
        <text>{{ onlineRate }}</text>
        <text>在线 {{ store.statusCounts.online }} / 总计 {{ store.devices.length }}</text>
      </view>
      <view class="metric-card warning">
        <text>异常</text>
        <text>{{ store.statusCounts.warning }}</text>
        <text>维护 {{ store.statusCounts.maintenance }} / 离线 {{ store.statusCounts.offline }}</text>
      </view>
    </view>

    <view v-if="store.error" class="notice error">{{ store.error }}</view>

    <view class="bulk-card">
      <view class="section-title tight">
        <text>多板同步控制</text>
        <text>{{ controllableDevices.length }} 台可控</text>
      </view>
      <view class="bulk-copy">对当前在线/异常板卡批量下发执行器指令，设备端按原有拉取指令流程执行。</view>
      <view class="bulk-section">
        <view>
          <text class="bulk-title">通风电机</text>
          <text class="bulk-meta">适合温湿度异常演示</text>
        </view>
        <view class="bulk-actions">
          <wd-button size="small" type="success" :disabled="!controllableDevices.length || !auth.canCommand" @click="runBulkControl('motor', 'on')">全部打开</wd-button>
          <wd-button size="small" plain :disabled="!controllableDevices.length || !auth.canCommand" @click="runBulkControl('motor', 'auto')">自动</wd-button>
          <wd-button size="small" type="error" plain :disabled="!controllableDevices.length || !auth.canCommand" @click="runBulkControl('motor', 'off')">关闭</wd-button>
        </view>
      </view>
      <view class="bulk-section">
        <view>
          <text class="bulk-title">补光灯</text>
          <text class="bulk-meta">适合暗光联动演示</text>
        </view>
        <view class="bulk-actions">
          <wd-button size="small" type="success" :disabled="!controllableDevices.length || !auth.canCommand" @click="runBulkControl('light', 'on')">全部照亮</wd-button>
          <wd-button size="small" plain :disabled="!controllableDevices.length || !auth.canCommand" @click="runBulkControl('light', 'auto')">自动</wd-button>
          <wd-button size="small" type="error" plain :disabled="!controllableDevices.length || !auth.canCommand" @click="runBulkControl('light', 'off')">关闭</wd-button>
        </view>
      </view>
    </view>

    <view class="section-title">
      <text>当前最需要处理</text>
      <text>{{ store.loading ? '刷新中' : '按设备状态' }}</text>
    </view>
    <view v-if="!store.loading && !store.devices.length" class="empty-state">当前没有接入板卡</view>
    <view v-else-if="!store.loading && !priorityDevices.length" class="empty-state">全部设备运行稳定，暂无风险</view>
    <view v-else class="device-list">
      <view v-for="item in priorityDevices" :key="item.device.id" class="device-row" @click="openDevice(item.device)">
        <view>
          <text class="row-title">{{ item.device.sn }}</text>
          <text class="row-meta">槽位 {{ item.device.slotNo }} / {{ item.device.location }} / {{ relativeTime(item.device.lastSeen) }}</text>
          <text class="row-meta">风险{{ item.score }}分：{{ item.reasons.join(' / ') }}</text>
        </view>
        <wd-tag :type="statusType(item.device.status)">{{ statusLabel[item.device.status] }}</wd-tag>
      </view>
    </view>

    <view class="section-title">
      <text>最近告警</text>
      <text>预览</text>
    </view>
    <view v-if="!recentAlarms.length" class="empty-state">暂无告警</view>
    <view v-else class="alarm-list">
      <view v-for="alarm in recentAlarms" :key="alarm.id" class="alarm-row">
        <wd-tag :type="alarm.level === 'critical' ? 'danger' : alarm.level === 'warning' ? 'warning' : 'primary'">
          {{ alarmLevelLabel[alarm.level] }}
        </wd-tag>
        <view>
          <text class="row-title">{{ alarm.deviceName }}</text>
          <text class="row-meta">{{ alarm.message }}</text>
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

.header-band {
  display: flex;
  flex-direction: column;
  gap: 24rpx;
  padding: 28rpx;
  border-radius: 12rpx;
  background: #ffffff;
  border: 1rpx solid $uni-border-color;
}

.eyebrow {
  display: block;
  color: $uni-color-primary;
  font-size: 22rpx;
  font-weight: 700;
}

.title {
  display: block;
  margin-top: 8rpx;
  color: #172033;
  font-size: 38rpx;
  font-weight: 800;
}

.copy {
  display: block;
  margin-top: 8rpx;
  color: $uni-text-color-grey;
  font-size: 26rpx;
}

.runtime {
  display: flex;
  justify-content: space-between;
  gap: 16rpx;
  padding: 18rpx;
  border-radius: 6rpx;
  font-size: 24rpx;
}

.quick-actions {
  display: flex;
  gap: 12rpx;
  flex-wrap: wrap;
}

.runtime-good {
  color: #2f7d32;
  background: #eef8ec;
}

.runtime-warn {
  color: #9a5b00;
  background: #fff7e6;
}

.runtime-bad {
  color: #b42318;
  background: #fff1f0;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16rpx;
  margin: 20rpx 0;
}

.metric-card {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
  min-height: 150rpx;
  padding: 20rpx;
  border-radius: 8rpx;
  background: #ffffff;
  border: 1rpx solid $uni-border-color;

  text:first-child,
  text:last-child {
    color: $uni-text-color-grey;
    font-size: 22rpx;
  }

  text:nth-child(2) {
    color: #172033;
    font-size: 38rpx;
    font-weight: 800;
  }
}

.section-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: 28rpx 0 14rpx;

  text:first-child {
    color: #172033;
    font-size: 30rpx;
    font-weight: 700;
  }

  text:last-child {
    color: $uni-text-color-grey;
    font-size: 24rpx;
  }
}

.device-list,
.alarm-list {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}

.device-row,
.alarm-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18rpx;
  padding: 22rpx;
  border: 1rpx solid $uni-border-color;
  border-radius: 8rpx;
  background: #ffffff;
}

.alarm-row {
  justify-content: flex-start;
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

.notice {
  padding: 18rpx;
  border-radius: 6rpx;
  font-size: 24rpx;
}

.bulk-card {
  margin-bottom: 20rpx;
  padding: 24rpx;
  border: 1rpx solid $uni-border-color;
  border-radius: 8rpx;
  background: #ffffff;
}

.tight {
  margin: 0 0 12rpx;
}

.bulk-copy {
  color: $uni-text-color-grey;
  font-size: 24rpx;
  line-height: 1.5;
}

.bulk-section {
  display: flex;
  justify-content: space-between;
  gap: 18rpx;
  padding: 18rpx 0 0;
  margin-top: 16rpx;
  border-top: 1rpx solid #f0f2f5;
}

.bulk-title,
.bulk-meta {
  display: block;
}

.bulk-title {
  color: #172033;
  font-size: 28rpx;
  font-weight: 800;
}

.bulk-meta {
  margin-top: 6rpx;
  color: $uni-text-color-grey;
  font-size: 22rpx;
}

.bulk-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10rpx;
  flex-wrap: wrap;
}

.error {
  color: #b42318;
  background: #fff1f0;
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
