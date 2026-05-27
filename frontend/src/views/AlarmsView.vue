<script setup lang="ts">
import { CheckCircle2, Filter, RefreshCcw, Sparkles, Siren } from 'lucide-vue-next';
import { ElMessage, ElMessageBox } from 'element-plus';
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import EmptyState from '@/components/EmptyState.vue';
import MarkdownMessage from '@/components/MarkdownMessage.vue';
import { ackAlarm, fetchAlarms, sendAiChat } from '@/api/lab';
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
let refreshTimer: number | null = null;

const statusOptions: Array<{ label: string; value: AlarmStatus | '' }> = [
  { label: '未关闭', value: '' },
  { label: '待确认', value: 'new' },
  { label: '已确认', value: 'acknowledged' },
  { label: '已关闭', value: 'closed' }
];

const levelOptions: Array<{ label: string; value: AlarmLevel | '' }> = [
  { label: '全部级别', value: '' },
  { label: '提示', value: 'info' },
  { label: '预警', value: 'warning' },
  { label: '严重', value: 'critical' }
];

const alarmStats = computed(() => {
  const total = alarms.value.length;
  const pending = alarms.value.filter((item) => item.status === 'new').length;
  const critical = alarms.value.filter((item) => item.level === 'critical').length;
  const acknowledged = alarms.value.filter((item) => item.status === 'acknowledged').length;
  return { total, pending, critical, acknowledged };
});

const aiVisible = ref(false);
const aiLoading = ref(false);
const aiReply = ref('');
const aiError = ref('');
const aiAlarmName = ref('');
const aiDataSource = ref('');

async function diagnoseAlarm(alarm: Alarm) {
  aiVisible.value = true;
  aiLoading.value = true;
  aiReply.value = '';
  aiError.value = '';
  aiDataSource.value = '';
  aiAlarmName.value = alarm.deviceName;
  try {
    const context = {
      alarm: { level: alarm.level, message: alarm.message, ts: alarm.ts, status: alarm.status },
      device: { sn: alarm.deviceName },
    };
    const result = await sendAiChat('alarm_diagnosis', context) as { reply: string; data_source?: string };
    aiReply.value = result.reply;
    aiDataSource.value = result.data_source ?? '';
  } catch (cause) {
    aiError.value = cause instanceof Error ? cause.message : 'AI分析请求失败';
    ElMessage.error(aiError.value);
  } finally {
    aiLoading.value = false;
  }
}

function closeAiDialog() {
  if (aiLoading.value) return;
  aiVisible.value = false;
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

async function acknowledge(alarm: Alarm) {
  if (!auth.canAckAlarm) {
    ElMessage.warning('当前角色没有确认告警权限');
    return;
  }
  try {
    await ElMessageBox.confirm(`确认处理告警：${alarm.message}`, '告警确认', {
      type: 'warning',
      confirmButtonText: '确认',
      cancelButtonText: '取消'
    });
    const next = await ackAlarm(alarm.id);
    alarms.value = alarms.value.map((item) => (item.id === next.id ? next : item));
    ElMessage.success('告警已确认');
  } catch (cause) {
    if (cause !== 'cancel') {
      ElMessage.error(cause instanceof Error ? cause.message : '告警确认失败');
    }
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

onMounted(() => {
  void load();
  unsubscribeAlarm = subscribeAlarmEvents(applyRealtimeAlarm);
  refreshTimer = window.setInterval(() => {
    void load();
  }, 10000);
});

onBeforeUnmount(() => {
  if (unsubscribeAlarm) {
    unsubscribeAlarm();
    unsubscribeAlarm = null;
  }
  if (refreshTimer !== null) {
    window.clearInterval(refreshTimer);
    refreshTimer = null;
  }
});

function levelText(alarm: Alarm) {
  return alarmLevelLabel[alarm.level];
}

function statusText(status: AlarmStatus) {
  return status === 'new' ? '待确认' : status === 'acknowledged' ? '已确认' : '已关闭';
}

function statusTagType(status: AlarmStatus) {
  return status === 'new' ? 'danger' : status === 'closed' ? 'info' : 'success';
}
</script>

<template>
  <div class="stack gap-lg">
    <section class="toolbar">
      <div>
        <p class="eyebrow">Reserved Alarm Module</p>
        <h2>告警中心</h2>
        <p>阈值越界、离线告警、固件维护提示，后续可接邮件、短信和企业微信。</p>
      </div>
      <el-button :loading="loading" @click="load">
        <RefreshCcw :size="17" />
        刷新
      </el-button>
    </section>

    <section class="alarm-command-panel">
      <div class="alarm-stat-grid">
        <span>
          <small>当前列表</small>
          <strong>{{ alarmStats.total }}</strong>
        </span>
        <span>
          <small>待确认</small>
          <strong>{{ alarmStats.pending }}</strong>
        </span>
        <span>
          <small>严重告警</small>
          <strong>{{ alarmStats.critical }}</strong>
        </span>
        <span>
          <small>已确认</small>
          <strong>{{ alarmStats.acknowledged }}</strong>
        </span>
      </div>
      <div class="alarm-filter-row">
        <span class="filter-label">
          <Filter :size="16" />
          筛选
        </span>
        <el-segmented v-model="statusFilter" :options="statusOptions" @change="load" />
        <el-select v-model="levelFilter" class="alarm-level-select" @change="load">
          <el-option v-for="option in levelOptions" :key="option.value || 'all'" :label="option.label" :value="option.value" />
        </el-select>
      </div>
    </section>

    <el-alert
      v-if="!auth.canAckAlarm"
      title="当前为只读权限：可以查看告警，不能确认或关闭告警。"
      type="info"
      show-icon
      :closable="false"
    />
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />
    <div v-if="loading" class="loading-block">正在加载告警...</div>
    <EmptyState v-else-if="alarms.length === 0" title="暂无告警" detail="所有板卡状态正常。" />

    <el-card v-else shadow="never">
      <el-table :data="alarms" stripe>
        <el-table-column label="级别" width="120">
          <template #default="{ row }">
            <span class="alarm-pill" :class="`alarm-${row.level}`">
              <Siren :size="15" />
              {{ levelText(row) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="deviceName" label="设备" min-width="180" />
        <el-table-column prop="message" label="消息" min-width="260" />
        <el-table-column label="时间" min-width="180">
          <template #default="{ row }">{{ formatDateTime(row.ts) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)">
              {{ statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <div style="display:flex;gap:6px;align-items:center;">
              <el-button size="small" type="primary" plain @click="diagnoseAlarm(row)">
                <Sparkles :size="15" />
                AI诊断
              </el-button>
              <el-button
                size="small"
                :disabled="row.status !== 'new' || !auth.canAckAlarm"
                @click="acknowledge(row)"
              >
                <CheckCircle2 :size="15" />
                确认
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog
      v-model="aiVisible"
      :title="`AI告警诊断 - ${aiAlarmName}`"
      width="min(640px, 90vw)"
      append-to-body
      :close-on-click-modal="!aiLoading"
      @close="closeAiDialog"
    >
      <div v-if="aiLoading" class="ai-loading">
        <el-icon class="is-loading" :size="28"><Sparkles /></el-icon>
        <p>AI正在分析告警,请稍候...</p>
      </div>
      <div v-else-if="aiError" class="ai-error">
        <p>{{ aiError }}</p>
      </div>
      <div v-else-if="aiReply" class="ai-reply">
        <MarkdownMessage :content="aiReply" :data-source="aiDataSource" />
      </div>
      <template #footer>
        <el-button @click="closeAiDialog">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.alarm-command-panel {
  display: grid;
  gap: 12px;
  padding: 14px;
  border: 1px solid rgba(188, 238, 255, 0.13);
  border-radius: var(--radius);
  background:
    linear-gradient(90deg, rgba(246, 184, 75, 0.08), transparent 52%),
    var(--panel);
  box-shadow: var(--shadow-soft);
}

.alarm-stat-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.alarm-stat-grid span {
  min-height: 76px;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: rgba(255, 255, 255, 0.03);
}

.alarm-stat-grid small,
.alarm-stat-grid strong {
  display: block;
}

.alarm-stat-grid small {
  color: var(--text-muted);
}

.alarm-stat-grid strong {
  margin-top: 8px;
  font-size: 26px;
}

.alarm-filter-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.filter-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--text-muted);
  font-weight: 700;
}

.alarm-level-select {
  width: 150px;
}

.ai-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 40px 0;
  color: var(--text-muted);
}

.ai-loading p { margin: 0; }

.ai-error {
  padding: 20px;
  color: var(--red);
  background: rgba(255, 104, 116, 0.08);
  border-radius: var(--radius);
}

.ai-error p { margin: 0; }

.ai-reply pre {
  margin: 0;
  padding: 20px;
  white-space: pre-wrap;
  word-wrap: break-word;
  line-height: 1.7;
  color: var(--text);
  background: var(--panel-soft);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-family: inherit;
  font-size: 14px;
}

@media (max-width: 760px) {
  .alarm-stat-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .alarm-filter-row {
    align-items: stretch;
    flex-direction: column;
  }

  .alarm-level-select {
    width: 100%;
  }
}
</style>
