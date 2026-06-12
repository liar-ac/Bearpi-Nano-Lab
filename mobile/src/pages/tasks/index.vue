<script setup lang="ts">
import { computed, ref } from 'vue';
import { onPullDownRefresh, onShow } from '@dcloudio/uni-app';
import { fetchBulkTasks, fetchDevices, retryBulkTask, sendBulkCommand } from '@/api/lab';
import { useAuthStore } from '@/stores/auth';
import type { BulkTask, BulkTaskActuator, BulkTaskMode, BulkTaskStatus, Device } from '@/types/domain';
import { formatDateTime } from '@/utils/format';

const auth = useAuthStore();
const tasks = ref<BulkTask[]>([]);
const devices = ref<Device[]>([]);
const loading = ref(false);
const creating = ref('');
const retryingId = ref('');
const error = ref('');
const target = ref<'online' | 'all'>('online');

const actionGroups: Array<{
  actuator: Exclude<BulkTaskActuator, 'unknown'>;
  title: string;
  actions: Array<{ label: string; mode: Exclude<BulkTaskMode, 'unknown'>; type?: 'success' | 'error' | 'primary' }>;
}> = [
  {
    actuator: 'light',
    title: '补光灯',
    actions: [
      { label: '开灯', mode: 'on', type: 'success' },
      { label: '关灯', mode: 'off', type: 'error' },
      { label: '自动', mode: 'auto', type: 'primary' }
    ]
  },
  {
    actuator: 'motor',
    title: '通风电机',
    actions: [
      { label: '开电机', mode: 'on', type: 'success' },
      { label: '关电机', mode: 'off', type: 'error' },
      { label: '自动', mode: 'auto', type: 'primary' }
    ]
  }
];

const stats = computed(() => ({
  total: tasks.value.length,
  running: tasks.value.filter((task) => task.status === 'queued' || task.status === 'running').length,
  failed: tasks.value.filter((task) => task.failed > 0).length
}));
const controllableCount = computed(() =>
  devices.value.filter((device) => device.status === 'online' || device.status === 'warning').length
);
const targetCount = computed(() =>
  target.value === 'online' ? controllableCount.value : devices.value.filter((device) => device.status !== 'offline').length
);

onShow(() => {
  void load();
});

onPullDownRefresh(async () => {
  await load();
  uni.stopPullDownRefresh();
});

async function load() {
  loading.value = true;
  error.value = '';
  try {
    const [taskResponse, deviceResponse] = await Promise.all([
      fetchBulkTasks({ limit: 50 }),
      fetchDevices()
    ]);
    tasks.value = taskResponse.results;
    devices.value = deviceResponse.results;
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '任务加载失败';
  } finally {
    loading.value = false;
  }
}

async function refreshTasksOnly() {
  try {
    tasks.value = (await fetchBulkTasks({ limit: 50 })).results;
  } catch {
    // 保留上一轮任务列表，避免短暂网络抖动清空页面。
  }
}

async function createTask(actuator: Exclude<BulkTaskActuator, 'unknown'>, mode: Exclude<BulkTaskMode, 'unknown'>) {
  if (!auth.canCommand) {
    uni.showToast({ title: '当前角色没有批量控制权限', icon: 'none' });
    return;
  }
  if (!targetCount.value) {
    uni.showToast({ title: '暂无可下发板卡', icon: 'none' });
    return;
  }
  const actuatorLabel = actuator === 'motor' ? '通风电机' : '补光灯';
  const modeLabel = mode === 'auto' ? '自动模式' : mode === 'on' ? '打开' : '关闭';
  const confirmed = await showConfirm(
    `确认向${targetCount.value}块板卡创建「${actuatorLabel}${modeLabel}」任务？`,
    '创建任务',
    '创建'
  );
  if (!confirmed) return;
  try {
    creating.value = `${actuator}-${mode}`;
    const response = await sendBulkCommand({ target: target.value, actuator, mode });
    uni.showToast({ title: `已创建${response.count}条子命令`, icon: 'success' });
    await refreshTasksOnly();
  } catch (cause) {
    uni.showToast({ title: cause instanceof Error ? cause.message : '创建任务失败', icon: 'none' });
  } finally {
    creating.value = '';
  }
}

async function retry(task: BulkTask) {
  if (retryingId.value) return;
  if (!auth.canCommand) {
    uni.showToast({ title: '当前角色没有重试权限', icon: 'none' });
    return;
  }
  if (!task.failedDevices.length) {
    uni.showToast({ title: '没有失败板卡可重试', icon: 'none' });
    return;
  }
  const confirmed = await showConfirm(`确认重试${task.failedDevices.length}块失败板卡？`, '任务重试', '重试');
  if (!confirmed) return;
  retryingId.value = task.batchId;
  try {
    await retryBulkTask(task.batchId);
    uni.showToast({ title: '重试任务已创建', icon: 'success' });
    await load();
  } catch (cause) {
    uni.showToast({ title: cause instanceof Error ? cause.message : '重试失败', icon: 'none' });
  } finally {
    retryingId.value = '';
  }
}

function showConfirm(content: string, title = '任务确认', confirmText = '确认') {
  return new Promise<boolean>((resolve) => {
    uni.showModal({
      title,
      content,
      confirmText,
      cancelText: '取消',
      success: (res) => resolve(res.confirm),
      fail: () => resolve(false)
    });
  });
}

function statusLabel(status: BulkTaskStatus) {
  const labels: Record<BulkTaskStatus, string> = {
    queued: '排队中',
    running: '执行中',
    completed: '已完成',
    partial: '部分失败',
    failed: '失败'
  };
  return labels[status];
}

function statusType(status: BulkTaskStatus) {
  if (status === 'completed') return 'success';
  if (status === 'failed' || status === 'partial') return 'danger';
  if (status === 'running') return 'warning';
  return 'primary';
}
</script>

<template>
  <view class="page">
    <view class="toolbar">
      <view>
        <text class="eyebrow">BulkTaskQueue</text>
        <text class="title">任务中心</text>
        <text class="subtitle">查看批量控制进度、失败板卡和任务日志。</text>
      </view>
      <wd-button size="small" plain :loading="loading" @click="load">刷新</wd-button>
    </view>

    <view v-if="error" class="notice error">{{ error }}</view>

    <view class="create-panel">
      <view class="panel-head">
        <view>
          <text class="panel-title">创建批量任务</text>
          <text class="panel-meta">{{ targetCount }}块板卡可下发</text>
        </view>
        <view class="target-toggle">
          <wd-button size="small" :type="target === 'online' ? 'primary' : 'info'" :plain="target !== 'online'" @click="target = 'online'">
            在线/异常
          </wd-button>
          <wd-button size="small" :type="target === 'all' ? 'primary' : 'info'" :plain="target !== 'all'" @click="target = 'all'">
            全部非离线
          </wd-button>
        </view>
      </view>
      <view class="action-grid">
        <view v-for="group in actionGroups" :key="group.actuator" class="action-card">
          <text class="action-title">{{ group.title }}</text>
          <view class="action-buttons">
            <wd-button
              v-for="action in group.actions"
              :key="`${group.actuator}-${action.mode}`"
              size="small"
              :type="action.type ?? 'primary'"
              :plain="action.mode === 'auto'"
              :loading="creating === `${group.actuator}-${action.mode}`"
              :disabled="!auth.canCommand || !targetCount || Boolean(creating)"
              @click="createTask(group.actuator, action.mode)"
            >
              {{ action.label }}
            </wd-button>
          </view>
        </view>
      </view>
      <view v-if="!auth.canCommand" class="notice info">当前为只读权限：可以查看任务，不能创建或重试。</view>
    </view>

    <view class="metric-grid">
      <view class="metric-card">
        <text>任务数</text>
        <text>{{ stats.total }}</text>
      </view>
      <view class="metric-card">
        <text>执行中</text>
        <text>{{ stats.running }}</text>
      </view>
      <view class="metric-card">
        <text>有失败</text>
        <text>{{ stats.failed }}</text>
      </view>
    </view>

    <view v-if="loading" class="empty-state">正在加载任务...</view>
    <view v-else-if="!tasks.length" class="empty-state">暂无批量任务</view>

    <view v-else class="task-list">
      <view v-for="task in tasks" :key="task.batchId" class="task-card">
        <view class="task-head">
          <view>
            <text class="task-title">{{ task.title }}</text>
            <text class="task-meta">{{ formatDateTime(task.createdAt) }}</text>
          </view>
          <wd-tag :type="statusType(task.status)">{{ statusLabel(task.status) }}</wd-tag>
        </view>

        <view class="progress-track">
          <view class="progress-fill" :style="{ width: `${task.progress}%` }" />
        </view>
        <view class="task-counters">
          <text>总计{{ task.total }}</text>
          <text>成功{{ task.acked }}</text>
          <text>失败{{ task.failed }}</text>
          <text>待处理{{ task.pending }}</text>
        </view>

        <view v-if="task.failedDevices.length" class="failed-list">
          <text class="failed-title">失败板卡</text>
          <text v-for="item in task.failedDevices" :key="item.id" class="failed-item">
            槽位{{ item.slotNo }}·{{ item.sn }}·{{ item.message }}
          </text>
        </view>

        <view class="log-list">
          <text class="log-title">最近日志</text>
          <text v-for="log in task.logs.slice(0, 4)" :key="`${log.ts}-${log.commandId || log.message}`" class="log-item">
            {{ formatDateTime(log.ts) }}·{{ log.message }}
          </text>
        </view>

        <wd-button
          v-if="task.failedDevices.length"
          size="small"
          type="primary"
          :loading="retryingId === task.batchId"
          :disabled="!auth.canCommand || Boolean(retryingId)"
          @click="retry(task)"
        >
          重试失败板卡
        </wd-button>
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

.toolbar,
.create-panel,
.action-card,
.task-card,
.metric-card {
  border: 1rpx solid $uni-border-color;
  border-radius: 10rpx;
  background: #ffffff;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  gap: 16rpx;
  padding: 24rpx;
}

.create-panel {
  margin-top: 18rpx;
  padding: 24rpx;
}

.eyebrow,
.title,
.subtitle,
.panel-title,
.panel-meta,
.action-title,
.task-title,
.task-meta,
.failed-title,
.failed-item,
.log-title,
.log-item {
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

.subtitle,
.task-meta,
.task-counters,
.log-item {
  color: $uni-text-color-grey;
  font-size: 24rpx;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  gap: 16rpx;
  align-items: flex-start;
}

.panel-title {
  color: #172033;
  font-size: 30rpx;
  font-weight: 800;
}

.panel-meta {
  margin-top: 6rpx;
  color: $uni-text-color-grey;
  font-size: 24rpx;
}

.target-toggle,
.action-buttons {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10rpx;
}

.action-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12rpx;
  margin-top: 18rpx;
}

.action-card {
  padding: 18rpx;
}

.action-title {
  margin-bottom: 14rpx;
  color: #172033;
  font-size: 28rpx;
  font-weight: 800;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12rpx;
  margin: 18rpx 0;
}

.metric-card {
  padding: 18rpx;

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
    font-size: 36rpx;
    font-weight: 800;
  }
}

.notice,
.empty-state {
  margin-top: 18rpx;
  padding: 18rpx;
  border-radius: 8rpx;
  font-size: 24rpx;
}

.error {
  color: #b42318;
  background: #fff1f0;
}

.info {
  color: #245d99;
  background: #eef7ff;
}

.empty-state {
  border: 1rpx dashed $uni-border-color;
  color: $uni-text-color-grey;
  background: #ffffff;
  text-align: center;
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.task-card {
  padding: 24rpx;
}

.task-head {
  display: flex;
  justify-content: space-between;
  gap: 16rpx;
  align-items: flex-start;
}

.task-title {
  color: #172033;
  font-size: 30rpx;
  font-weight: 800;
}

.progress-track {
  height: 14rpx;
  margin: 22rpx 0 12rpx;
  overflow: hidden;
  border-radius: 999rpx;
  background: #edf2f7;
}

.progress-fill {
  height: 100%;
  border-radius: inherit;
  background: $uni-color-primary;
}

.task-counters {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8rpx;
}

.failed-list,
.log-list {
  margin: 18rpx 0;
  padding: 16rpx;
  border-radius: 8rpx;
  background: #f8fafc;
}

.failed-title,
.log-title {
  margin-bottom: 8rpx;
  color: #172033;
  font-size: 26rpx;
  font-weight: 700;
}

.failed-item,
.log-item {
  margin-top: 6rpx;
  line-height: 1.5;
}

.failed-item {
  color: #b42318;
  font-size: 24rpx;
}
</style>
