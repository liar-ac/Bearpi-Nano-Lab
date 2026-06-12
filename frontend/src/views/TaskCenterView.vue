<script setup lang="ts">
import {
  Activity,
  CheckCircle2,
  ClipboardList,
  Fan,
  Lightbulb,
  ListRestart,
  Play,
  RefreshCcw,
  RotateCcw,
  Search,
  TimerReset,
  TriangleAlert
} from 'lucide-vue-next';
import { ElMessage, ElMessageBox } from 'element-plus';
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import EmptyState from '@/components/EmptyState.vue';
import { fetchBulkTasks, fetchDevices, retryBulkTask, sendBulkCommand } from '@/api/lab';
import { realtimeState } from '@/api/realtime';
import { useAuthStore } from '@/stores/auth';
import type { BulkTask, BulkTaskActuator, BulkTaskMode, BulkTaskStatus, Device } from '@/types/domain';
import { formatDateTime, relativeTime } from '@/utils/format';

type TaskTarget = 'online' | 'all';

const auth = useAuthStore();
const tasks = ref<BulkTask[]>([]);
const devices = ref<Device[]>([]);
const loading = ref(false);
const creating = ref('');
const retrying = ref('');
const error = ref('');
const keyword = ref('');
const selectedStatus = ref<BulkTaskStatus | 'all'>('all');
const target = ref<TaskTarget>('online');
const selectedTask = ref<BulkTask | null>(null);
const detailOpen = ref(false);
let refreshTimer: number | null = null;

const taskStatusLabel: Record<BulkTaskStatus, string> = {
  queued: '排队中',
  running: '执行中',
  completed: '已完成',
  partial: '部分失败',
  failed: '失败'
};

const taskStatusType: Record<BulkTaskStatus, 'info' | 'warning' | 'success' | 'danger'> = {
  queued: 'info',
  running: 'warning',
  completed: 'success',
  partial: 'danger',
  failed: 'danger'
};

const actionGroups: Array<{
  actuator: Exclude<BulkTaskActuator, 'unknown'>;
  title: string;
  icon: typeof Fan;
  actions: Array<{ label: string; mode: Exclude<BulkTaskMode, 'unknown'>; type?: 'success' | 'danger' | 'primary' }>;
}> = [
  {
    actuator: 'light',
    title: '补光灯',
    icon: Lightbulb,
    actions: [
      { label: '开灯', mode: 'on', type: 'success' },
      { label: '关灯', mode: 'off', type: 'danger' },
      { label: '自动模式', mode: 'auto', type: 'primary' }
    ]
  },
  {
    actuator: 'motor',
    title: '通风电机',
    icon: Fan,
    actions: [
      { label: '开电机', mode: 'on', type: 'success' },
      { label: '关电机', mode: 'off', type: 'danger' },
      { label: '自动模式', mode: 'auto', type: 'primary' }
    ]
  }
];

const statusFilters: Array<{ label: string; value: BulkTaskStatus | 'all' }> = [
  { label: '全部', value: 'all' },
  { label: '排队中', value: 'queued' },
  { label: '执行中', value: 'running' },
  { label: '已完成', value: 'completed' },
  { label: '部分失败', value: 'partial' },
  { label: '失败', value: 'failed' }
];

const controllableCount = computed(() => {
  /* 使用后端 DeviceSerializer 计算的 status（已基于 TTL 判断在线状态），
     避免前端硬编码 TTL 与后端配置不一致。 */
  return devices.value.filter((device) => {
    if (target.value === 'all') return device.status !== 'offline';
    return device.status === 'online' || device.status === 'warning';
  }).length;
});

const summaryCards = computed(() => [
  {
    label: '任务总数',
    value: tasks.value.length,
    detail: '按批次聚合',
    icon: ClipboardList,
    tone: 'cyan'
  },
  {
    label: '执行中',
    value: tasks.value.filter((task) => task.status === 'queued' || task.status === 'running').length,
    detail: '等待板端拉取或ACK',
    icon: Activity,
    tone: 'amber'
  },
  {
    label: '失败板卡',
    value: tasks.value.reduce((sum, task) => sum + task.failed, 0),
    detail: '可按任务重试',
    icon: TriangleAlert,
    tone: 'red'
  },
  {
    label: '可控板卡',
    value: controllableCount.value,
    detail: target.value === 'online' ? '在线/异常板卡' : '全部已登记板卡',
    icon: CheckCircle2,
    tone: 'green'
  }
]);

const filteredTasks = computed(() => {
  const query = keyword.value.trim().toLowerCase();
  return tasks.value.filter((task) => {
    if (selectedStatus.value !== 'all' && task.status !== selectedStatus.value) return false;
    if (!query) return true;
    return [
      task.batchId,
      task.title,
      task.retryOf,
      ...task.commands.flatMap((command) => [command.sn, String(command.slotNo)])
    ]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(query));
  });
});

onMounted(async () => {
  await load();
  refreshTimer = window.setInterval(() => {
    void loadTasksOnly();
  }, 5000);
});

onBeforeUnmount(() => {
  if (refreshTimer !== null) {
    window.clearInterval(refreshTimer);
  }
});

async function load() {
  loading.value = true;
  error.value = '';
  try {
    const [taskResponse, deviceResponse] = await Promise.all([fetchBulkTasks(), fetchDevices()]);
    tasks.value = taskResponse.results;
    devices.value = deviceResponse.results;
    syncSelectedTask();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '任务中心加载失败';
  } finally {
    loading.value = false;
  }
}

async function loadTasksOnly() {
  try {
    tasks.value = (await fetchBulkTasks()).results;
    syncSelectedTask();
  } catch {
    /* keep last known queue while a refresh fails */
  }
}

function syncSelectedTask() {
  if (!selectedTask.value) return;
  selectedTask.value = tasks.value.find((task) => task.batchId === selectedTask.value?.batchId) ?? selectedTask.value;
}

async function createTask(actuator: Exclude<BulkTaskActuator, 'unknown'>, mode: Exclude<BulkTaskMode, 'unknown'>) {
  if (!auth.canCommand) {
    ElMessage.warning('当前角色没有批量控制权限');
    return;
  }
  if (!controllableCount.value) {
    ElMessage.warning('当前没有可下发的板卡');
    return;
  }
  const actuatorLabel = actuator === 'motor' ? '通风电机' : '补光灯';
  const modeLabel = { auto: '自动模式', on: '打开', off: '关闭' }[mode];
  try {
    await ElMessageBox.confirm(
      `确认向${controllableCount.value}块板卡创建「${actuatorLabel}${modeLabel}」任务？`,
      '创建批量控制任务',
      {
        type: 'warning',
        confirmButtonText: '创建任务',
        cancelButtonText: '取消'
      }
    );
    creating.value = `${actuator}-${mode}`;
    const response = await sendBulkCommand({ target: target.value, actuator, mode });
    ElMessage.success(`已创建${response.count}条子命令`);
    await loadTasksOnly();
    if (response.task) {
      selectedTask.value = response.task;
      detailOpen.value = true;
    }
  } catch (cause) {
    if (cause !== 'cancel') {
      ElMessage.error(cause instanceof Error ? cause.message : '创建任务失败');
    }
  } finally {
    creating.value = '';
  }
}

async function retryTask(task: BulkTask) {
  if (!auth.canCommand) {
    ElMessage.warning('当前角色没有批量控制权限');
    return;
  }
  if (!task.failedDevices.length) {
    ElMessage.info('该任务没有失败板卡');
    return;
  }
  try {
    await ElMessageBox.confirm(
      `确认重试${task.failedDevices.length}块失败板卡？`,
      '重试失败板卡',
      {
        type: 'warning',
        confirmButtonText: '重试',
        cancelButtonText: '取消'
      }
    );
    retrying.value = task.batchId;
    const response = await retryBulkTask(task.batchId);
    ElMessage.success(`已创建${response.count}条重试子命令`);
    await loadTasksOnly();
    if (response.task) {
      selectedTask.value = response.task;
      detailOpen.value = true;
    }
  } catch (cause) {
    if (cause !== 'cancel') {
      ElMessage.error(cause instanceof Error ? cause.message : '重试失败');
    }
  } finally {
    retrying.value = '';
  }
}

function openDetail(task: BulkTask) {
  selectedTask.value = task;
  detailOpen.value = true;
}

function progressStatus(task: BulkTask) {
  if (task.status === 'completed') return 'success';
  if (task.status === 'failed' || task.status === 'partial') return 'exception';
  return undefined;
}

function taskLabel(status: BulkTaskStatus) {
  return taskStatusLabel[status];
}

function taskType(status: BulkTaskStatus) {
  return taskStatusType[status];
}
</script>

<template>
  <div class="stack gap-lg">
    <section class="ops-overview priority-overview">
      <div>
        <p class="eyebrow">BatchTaskCenter</p>
        <h2>批量控制任务中心</h2>
        <p>把开灯、关灯、开电机和自动模式变成可追踪任务，按板卡查看进度、失败和日志。</p>
      </div>
      <div class="ops-status-grid">
        <span><Activity :size="16" />{{ realtimeState.status }}</span>
        <span><ClipboardList :size="16" />{{ tasks.length }}个任务</span>
        <span><TriangleAlert :size="16" />{{ tasks.reduce((sum, task) => sum + task.failed, 0) }}个失败</span>
      </div>
    </section>

    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />

    <section class="metric-grid">
      <article v-for="card in summaryCards" :key="card.label" class="metric-card" :class="`tone-${card.tone}`">
        <component :is="card.icon" :size="22" />
        <div>
          <span>{{ card.label }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.detail }}</small>
        </div>
      </article>
    </section>

    <section class="task-create-panel">
      <div class="task-create-head">
        <div>
          <p class="eyebrow">CreateTask</p>
          <h3>创建控制任务</h3>
        </div>
        <el-radio-group v-model="target">
          <el-radio-button label="online">在线/异常</el-radio-button>
          <el-radio-button label="all">全部板卡</el-radio-button>
        </el-radio-group>
      </div>
      <div class="task-action-grid">
        <section v-for="group in actionGroups" :key="group.actuator" class="task-action-group">
          <div class="task-action-title">
            <component :is="group.icon" :size="20" />
            <strong>{{ group.title }}</strong>
            <small>{{ controllableCount }}块目标板卡</small>
          </div>
          <div class="task-action-buttons">
            <el-button
              v-for="action in group.actions"
              :key="`${group.actuator}-${action.mode}`"
              :type="action.type"
              :plain="action.mode === 'off'"
              :loading="creating === `${group.actuator}-${action.mode}`"
              :disabled="!auth.canCommand || !controllableCount"
              @click="createTask(group.actuator, action.mode)"
            >
              <Play v-if="action.mode === 'on'" :size="15" />
              <TimerReset v-else-if="action.mode === 'auto'" :size="15" />
              <RotateCcw v-else :size="15" />
              {{ action.label }}
            </el-button>
          </div>
        </section>
      </div>
    </section>

    <section class="panel-section task-queue-panel">
      <div class="section-heading">
        <div>
          <p class="eyebrow">TaskQueue</p>
          <h3>任务队列</h3>
        </div>
        <div class="task-toolbar">
          <el-input v-model="keyword" clearable placeholder="搜索批次、槽位、SN" class="task-search">
            <template #prefix><Search :size="16" /></template>
          </el-input>
          <el-radio-group v-model="selectedStatus">
            <el-radio-button v-for="filter in statusFilters" :key="filter.value" :label="filter.value">
              {{ filter.label }}
            </el-radio-button>
          </el-radio-group>
          <el-button :loading="loading" @click="load">
            <RefreshCcw :size="16" />
            刷新
          </el-button>
        </div>
      </div>

      <EmptyState v-if="!loading && !filteredTasks.length" title="暂无批量任务" detail="创建批量控制任务后会出现在这里。" />

      <el-table v-else v-loading="loading" :data="filteredTasks" row-key="batchId">
        <el-table-column label="任务" min-width="230">
          <template #default="{ row }">
            <div class="task-title-cell">
              <strong>{{ row.title }}</strong>
              <small>{{ row.batchId }}</small>
              <small v-if="row.retryOf">重试自{{ row.retryOf }}</small>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="taskType(row.status)" effect="dark">{{ taskLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="进度" min-width="210">
          <template #default="{ row }">
            <div class="task-progress-cell">
              <el-progress :percentage="row.progress" :status="progressStatus(row)" />
              <small>成功{{ row.acked }} / 失败{{ row.failed }} / 待处理{{ row.pending }}</small>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="目标" width="110">
          <template #default="{ row }">{{ row.total }}块</template>
        </el-table-column>
        <el-table-column label="执行时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.executeAt) }}</template>
        </el-table-column>
        <el-table-column label="最近更新" width="120">
          <template #default="{ row }">{{ relativeTime(row.latestAt) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" @click="openDetail(row)">
              <ClipboardList :size="15" />
              详情
            </el-button>
            <el-button
              text
              type="warning"
              :loading="retrying === row.batchId"
              :disabled="!row.failedDevices.length || !auth.canCommand"
              @click="retryTask(row)"
            >
              <ListRestart :size="15" />
              重试
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-drawer v-model="detailOpen" size="520px" title="任务详情" append-to-body :z-index="9998" lock-scroll>
      <template v-if="selectedTask">
        <div class="task-detail-head">
          <div>
            <h3>{{ selectedTask.title }}</h3>
            <p>{{ selectedTask.batchId }}</p>
          </div>
          <el-tag :type="taskType(selectedTask.status)" effect="dark">
            {{ taskLabel(selectedTask.status) }}
          </el-tag>
        </div>

        <div class="task-detail-stats">
          <span><small>总数</small><strong>{{ selectedTask.total }}</strong></span>
          <span><small>成功</small><strong>{{ selectedTask.acked }}</strong></span>
          <span><small>失败</small><strong>{{ selectedTask.failed }}</strong></span>
          <span><small>待处理</small><strong>{{ selectedTask.pending }}</strong></span>
        </div>

        <el-progress :percentage="selectedTask.progress" :status="progressStatus(selectedTask)" />

        <div v-if="selectedTask.failedDevices.length" class="failed-section">
          <div class="drawer-heading">
            <h4>失败板卡</h4>
            <el-button
              size="small"
              type="warning"
              :loading="retrying === selectedTask.batchId"
              :disabled="!auth.canCommand"
              @click="retryTask(selectedTask)"
            >
              <ListRestart :size="14" />
              重试失败板卡
            </el-button>
          </div>
          <div class="failed-list">
            <div v-for="device in selectedTask.failedDevices" :key="device.id" class="failed-row">
              <strong>槽位{{ device.slotNo }} / {{ device.sn }}</strong>
              <small>{{ device.message }}</small>
            </div>
          </div>
        </div>

        <h4>子命令</h4>
        <div class="command-list">
          <div v-for="command in selectedTask.commands" :key="command.id" class="command-row-item">
            <span>槽位{{ command.slotNo }}</span>
            <strong>{{ command.sn }}</strong>
            <el-tag size="small" :type="command.status === 'acked' ? 'success' : command.status === 'failed' ? 'danger' : 'info'">
              {{ command.status }}
            </el-tag>
          </div>
        </div>

        <h4>任务日志</h4>
        <el-timeline>
          <el-timeline-item
            v-for="log in selectedTask.logs"
            :key="`${log.ts}-${log.commandId}-${log.status}`"
            :timestamp="formatDateTime(log.ts)"
            :type="log.level === 'error' ? 'danger' : log.level === 'success' ? 'success' : 'primary'"
          >
            {{ log.message }}
          </el-timeline-item>
        </el-timeline>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.task-create-panel {
  display: grid;
  gap: 14px;
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background:
    linear-gradient(90deg, rgba(56, 189, 248, 0.08), rgba(45, 212, 125, 0.055) 50%, transparent),
    var(--panel);
  box-shadow: var(--shadow-soft);
}

.task-create-head,
.task-toolbar,
.drawer-heading,
.task-detail-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.task-create-head h3,
.task-detail-head h3,
.drawer-heading h4 {
  margin: 0;
}

.task-action-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.task-action-group {
  display: grid;
  gap: 12px;
  min-height: 128px;
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: rgba(255, 255, 255, 0.03);
}

.task-action-title {
  display: flex;
  align-items: center;
  gap: 9px;
}

.task-action-title svg {
  color: var(--green);
}

.task-action-title small {
  margin-left: auto;
  color: var(--text-muted);
}

.task-action-buttons,
.task-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.task-search {
  width: min(280px, 100%);
}

.task-title-cell,
.task-progress-cell {
  display: grid;
  gap: 4px;
}

.task-title-cell small,
.task-progress-cell small,
.task-detail-head p,
.failed-row small {
  color: var(--text-muted);
}

.task-detail-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin: 16px 0;
}

.task-detail-stats span {
  display: grid;
  gap: 4px;
  min-height: 66px;
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--panel-soft);
}

.task-detail-stats small {
  color: var(--text-muted);
}

.task-detail-stats strong {
  font-size: 20px;
}

.failed-section {
  display: grid;
  gap: 10px;
  margin-top: 18px;
}

.failed-list,
.command-list {
  display: grid;
  gap: 8px;
}

.failed-row,
.command-row-item {
  display: grid;
  gap: 4px;
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--panel-soft);
}

.command-row-item {
  grid-template-columns: 72px minmax(0, 1fr) auto;
  align-items: center;
}

h4 {
  margin: 18px 0 10px;
}

@media (max-width: 900px) {
  .task-action-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .task-detail-stats,
  .command-row-item {
    grid-template-columns: 1fr;
  }
}
</style>
