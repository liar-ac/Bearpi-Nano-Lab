<script setup lang="ts">
import { FileClock, RefreshCcw, Search } from 'lucide-vue-next';
import { computed, onMounted, ref } from 'vue';
import EmptyState from '@/components/EmptyState.vue';
import { fetchAuditLogs } from '@/api/lab';
import type { AuditLog } from '@/types/domain';
import { formatDateTime } from '@/utils/format';

const logs = ref<AuditLog[]>([]);
const loading = ref(false);
const error = ref('');
const actionFilter = ref('');

const actionOptions = [
  { label: '全部动作', value: '' },
  { label: '登录', value: 'login' },
  { label: '注册', value: 'register' },
  { label: '权限变更', value: 'role_update' },
  { label: '指令下发', value: 'command_create' },
  { label: '设备回执', value: 'command_ack' },
  { label: '告警确认', value: 'alarm_ack' },
  { label: '规则更新', value: 'rule_update' }
];

const actionLabel: Record<string, string> = Object.fromEntries(actionOptions.map((item) => [item.value, item.label]));

const stats = computed(() => ({
  total: logs.value.length,
  rules: logs.value.filter((item) => item.action === 'rule_update').length,
  commands: logs.value.filter((item) => item.action === 'command_create' || item.action === 'command_ack').length,
  security: logs.value.filter((item) => ['login', 'register', 'role_update'].includes(item.action)).length
}));

async function load() {
  loading.value = true;
  error.value = '';
  try {
    logs.value = await fetchAuditLogs({ action: actionFilter.value || undefined });
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '审计日志加载失败';
  } finally {
    loading.value = false;
  }
}

function metadataText(log: AuditLog) {
  const text = JSON.stringify(log.metadata ?? {});
  return text === '{}' ? '无附加数据' : text;
}

onMounted(load);
</script>

<template>
  <div class="stack gap-lg">
    <section class="toolbar">
      <div>
        <p class="eyebrow">Audit Trail</p>
        <h2>审计日志</h2>
        <p>记录登录、权限、指令、告警和规则变更，便于答辩演示和问题追踪。</p>
      </div>
      <el-button :loading="loading" @click="load">
        <RefreshCcw :size="17" />
        刷新
      </el-button>
    </section>

    <section class="audit-overview">
      <span><small>当前列表</small><strong>{{ stats.total }}</strong></span>
      <span><small>规则变更</small><strong>{{ stats.rules }}</strong></span>
      <span><small>指令链路</small><strong>{{ stats.commands }}</strong></span>
      <span><small>安全事件</small><strong>{{ stats.security }}</strong></span>
    </section>

    <section class="audit-filter-row">
      <span class="filter-label">
        <Search :size="16" />
        动作类型
      </span>
      <el-select v-model="actionFilter" class="action-select" @change="load">
        <el-option v-for="option in actionOptions" :key="option.value || 'all'" :label="option.label" :value="option.value" />
      </el-select>
    </section>

    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />
    <div v-if="loading" class="loading-block">正在加载审计日志...</div>
    <EmptyState v-else-if="logs.length === 0" title="暂无审计日志" detail="系统产生操作后会自动记录在这里。" />

    <el-card v-else shadow="never">
      <el-table :data="logs" stripe>
        <el-table-column label="动作" width="130">
          <template #default="{ row }">
            <span class="audit-action-pill">
              <FileClock :size="15" />
              {{ actionLabel[row.action] ?? row.action }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="actorName" label="操作者" width="140" />
        <el-table-column prop="target" label="对象" min-width="190" />
        <el-table-column prop="detail" label="详情" min-width="260" />
        <el-table-column label="附加数据" min-width="240">
          <template #default="{ row }">
            <code class="metadata-code">{{ metadataText(row) }}</code>
          </template>
        </el-table-column>
        <el-table-column prop="ipAddress" label="IP" width="150" />
        <el-table-column label="时间" min-width="180">
          <template #default="{ row }">{{ formatDateTime(row.createdAt) }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.audit-overview {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.audit-overview span,
.audit-filter-row {
  border: 1px solid rgba(188, 238, 255, 0.13);
  border-radius: var(--radius);
  background: var(--panel);
  box-shadow: var(--shadow-soft);
}

.audit-overview span {
  min-height: 78px;
  padding: 12px;
}

.audit-overview small,
.audit-overview strong {
  display: block;
}

.audit-overview small {
  color: var(--text-muted);
}

.audit-overview strong {
  margin-top: 8px;
  font-size: 26px;
}

.audit-filter-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
}

.filter-label,
.audit-action-pill {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

.filter-label {
  color: var(--text-muted);
  font-weight: 700;
}

.action-select {
  width: 180px;
}

.audit-action-pill {
  min-height: 30px;
  padding: 0 10px;
  border: 1px solid rgba(56, 189, 248, 0.26);
  border-radius: 999px;
  color: var(--cyan);
  background: rgba(56, 189, 248, 0.08);
  font-weight: 700;
}

.metadata-code {
  color: var(--text-muted);
  white-space: normal;
  overflow-wrap: anywhere;
}

@media (max-width: 760px) {
  .audit-overview {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .audit-filter-row {
    align-items: stretch;
    flex-direction: column;
  }

  .action-select {
    width: 100%;
  }
}
</style>
