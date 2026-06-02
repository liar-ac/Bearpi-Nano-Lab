<script setup lang="ts">
import { RefreshCcw, Save, SlidersHorizontal, Sparkles } from 'lucide-vue-next';
import { ElMessage } from 'element-plus';
import { computed, onMounted, reactive, ref } from 'vue';
import EmptyState from '@/components/EmptyState.vue';
import MarkdownMessage from '@/components/MarkdownMessage.vue';
import { fetchRules, sendAiChat, updateRule } from '@/api/lab';
import { useAuthStore } from '@/stores/auth';
import type { RuleConfig } from '@/types/domain';
import { formatValue } from '@/utils/format';

const auth = useAuthStore();
const rules = ref<RuleConfig[]>([]);
const loading = ref(false);
const savingId = ref<number | null>(null);
const error = ref('');
const drafts = reactive<Record<number, { min: number | null; max: number | null }>>({});

const sortedRules = computed(() =>
  [...rules.value].sort((a, b) => a.slotNo - b.slotNo || a.deviceName.localeCompare(b.deviceName) || a.id - b.id)
);

const connectedDevices = computed(() => {
  const byDevice = new Map<number, { id: number; name: string; slotNo: number; sampleRate: number; ruleCount: number }>();
  for (const rule of rules.value) {
    const current = byDevice.get(rule.deviceId);
    if (current) {
      current.ruleCount += 1;
      continue;
    }
    byDevice.set(rule.deviceId, {
      id: rule.deviceId,
      name: rule.deviceName,
      slotNo: rule.slotNo,
      sampleRate: rule.sampleRate,
      ruleCount: 1
    });
  }
  return [...byDevice.values()].sort((a, b) => a.slotNo - b.slotNo);
});

const slotMap = computed(() => {
  const bySlot = new Map(connectedDevices.value.map((device) => [device.slotNo, device]));
  return Array.from({ length: 120 }, (_, index) => {
    const slotNo = index + 1;
    return {
      slotNo,
      device: bySlot.get(slotNo)
    };
  });
});

const stats = computed(() => ({
  devices: connectedDevices.value.length,
  total: rules.value.length,
  strict: rules.value.filter((item) => item.min !== null && item.max !== null).length,
  lowerOnly: rules.value.filter((item) => item.min !== null && item.max === null).length,
  upperOnly: rules.value.filter((item) => item.min === null && item.max !== null).length
}));

async function load() {
  loading.value = true;
  error.value = '';
  try {
    rules.value = await fetchRules();
    for (const rule of rules.value) {
      drafts[rule.id] = { min: rule.min, max: rule.max };
    }
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '规则配置加载失败';
  } finally {
    loading.value = false;
  }
}

async function save(rule: RuleConfig) {
  if (!auth.canCommand) {
    ElMessage.warning('当前角色没有规则配置权限');
    return;
  }
  const draft = drafts[rule.id];
  if (draft.min !== null && draft.max !== null && draft.min >= draft.max) {
    ElMessage.error('上限必须大于下限');
    return;
  }
  savingId.value = rule.id;
  try {
    const next = await updateRule(rule.id, { min: draft.min, max: draft.max });
    rules.value = rules.value.map((item) => (item.id === rule.id ? next : item));
    drafts[next.id] = { min: next.min, max: next.max };
    ElMessage.success('规则已保存');
  } catch (cause) {
    ElMessage.error(cause instanceof Error ? cause.message : '规则保存失败');
  } finally {
    savingId.value = null;
  }
}

function ruleRange(rule: RuleConfig) {
  const min = rule.min === null ? '无下限' : formatValue(rule.min, rule.unit);
  const max = rule.max === null ? '无上限' : formatValue(rule.max, rule.unit);
  return `${min} - ${max}`;
}

function buildRuleSuggestionContext() {
  return {
    rules: rules.value.map((r) => ({
      deviceName: r.deviceName,
      name: r.name,
      code: r.code,
      unit: r.unit,
      min: r.min,
      max: r.max,
      slotNo: r.slotNo,
    })),
  };
}

const aiVisible = ref(false);
const aiLoading = ref(false);
const aiReply = ref('');
const aiError = ref('');
const aiDataSource = ref('');

async function runAiSuggestion() {
  aiVisible.value = true;
  aiLoading.value = true;
  aiReply.value = '';
  aiError.value = '';
  aiDataSource.value = '';
  try {
    const result = await sendAiChat('rule_suggestion', buildRuleSuggestionContext()) as { reply: string; data_source?: string };
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

onMounted(load);
</script>

<template>
  <div class="stack gap-lg">
    <section class="toolbar">
      <div>
        <p class="eyebrow">Rule Engine</p>
        <h2>规则配置</h2>
        <p>配置温度、湿度、光照等传感器阈值，实时上报时会直接触发告警判定。</p>
      </div>
      <div style="display:flex;gap:8px;align-items:center;">
        <el-button :loading="loading" @click="load">
          <RefreshCcw :size="17" />
          刷新
        </el-button>
        <el-button @click="runAiSuggestion">
          <Sparkles :size="17" />
          AI建议
        </el-button>
      </div>
    </section>

    <el-alert
      v-if="!auth.canCommand"
      title="当前为只读权限：可以查看规则，不能修改阈值。"
      type="info"
      show-icon
      :closable="false"
    />
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />

    <section class="rule-overview">
      <span><small>实时接入板卡</small><strong>{{ stats.devices }}</strong></span>
      <span><small>规则总数</small><strong>{{ stats.total }}</strong></span>
      <span><small>上下限完整</small><strong>{{ stats.strict }}</strong></span>
      <span><small>单边阈值</small><strong>{{ stats.lowerOnly + stats.upperOnly }}</strong></span>
    </section>

    <el-card class="slot-map-card" shadow="never">
      <template #header>
        <div class="section-heading">
          <div>
            <p class="eyebrow">120 Slots</p>
            <h2>实验室槽位接入图</h2>
          </div>
          <el-tag type="info" effect="dark">只显示真实上报设备</el-tag>
        </div>
      </template>
      <div class="rule-slot-grid" aria-label="120 个设备槽位">
        <button
          v-for="slot in slotMap"
          :key="slot.slotNo"
          class="rule-slot"
          :class="{ connected: slot.device }"
          type="button"
          :title="slot.device ? `${slot.device.name} / ${slot.device.ruleCount} 条规则` : `槽位 ${slot.slotNo} 未接入`"
        >
          <span>{{ slot.slotNo }}</span>
          <strong v-if="slot.device">{{ slot.device.name.replace('BEARPI-NANO-', '') }}</strong>
        </button>
      </div>
    </el-card>

    <EmptyState v-if="!loading && rules.length === 0" title="暂无实时接入板卡" detail="板子真实上报 telemetry 后，才会在这里显示槽位和规则。" />

    <el-card v-else shadow="never">
      <el-table :data="sortedRules" stripe>
        <el-table-column label="设备 / 槽位" min-width="190">
          <template #default="{ row }">
            <strong>{{ row.deviceName }}</strong>
            <small>槽位 {{ row.slotNo }} / 采样 {{ row.sampleRate }}s / 实时接入</small>
          </template>
        </el-table-column>
        <el-table-column label="传感器" min-width="180">
          <template #default="{ row }">
            <strong>{{ row.name }}</strong>
            <small>{{ row.code }} / {{ row.description }}</small>
          </template>
        </el-table-column>
        <el-table-column label="当前阈值" min-width="180">
          <template #default="{ row }">{{ ruleRange(row) }}</template>
        </el-table-column>
        <el-table-column label="下限" width="150">
          <template #default="{ row }">
            <el-input-number v-model="drafts[row.id].min" :disabled="!auth.canCommand" :controls="false" />
          </template>
        </el-table-column>
        <el-table-column label="上限" width="150">
          <template #default="{ row }">
            <el-input-number v-model="drafts[row.id].max" :disabled="!auth.canCommand" :controls="false" />
          </template>
        </el-table-column>
        <el-table-column label="动作" width="130" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" :loading="savingId === row.id" :disabled="!auth.canCommand" @click="save(row)">
              <Save :size="15" />
              保存
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <section class="rule-note">
      <SlidersHorizontal :size="18" />
      <span>规则保存后，后续遥测进入后端时会用新的 min/max 立即判定告警；设备端无需重新烧录。</span>
    </section>

    <el-dialog
      v-model="aiVisible"
      title="AI规则建议"
      width="min(640px, 90vw)"
      append-to-body
      :close-on-click-modal="!aiLoading"
      :z-index="9999"
      lock-scroll
      destroy-on-close
      @close="closeAiDialog"
    >
      <div v-if="aiLoading" class="ai-loading">
        <el-icon class="is-loading" :size="28"><Sparkles /></el-icon>
        <p>AI正在分析规则配置,请稍候...</p>
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
.rule-overview {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.rule-overview span,
.rule-note {
  border: 1px solid rgba(188, 238, 255, 0.13);
  border-radius: var(--radius);
  background: var(--panel);
  box-shadow: var(--shadow-soft);
}

.rule-overview span {
  min-height: 78px;
  padding: 12px;
}

.rule-overview small,
.rule-overview strong {
  display: block;
}

.rule-overview small {
  color: var(--text-muted);
}

.rule-overview strong {
  margin-top: 8px;
  font-size: 26px;
}

.rule-note {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  color: var(--text-muted);
}

.slot-map-card :deep(.el-card__body) {
  padding: 14px;
}

.rule-slot-grid {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 7px;
}

.rule-slot {
  position: relative;
  display: grid;
  align-content: space-between;
  min-height: 58px;
  padding: 7px;
  border: 1px solid var(--border);
  border-radius: 5px;
  color: var(--text-subtle);
  text-align: left;
  background: rgba(255, 255, 255, 0.018);
}

.rule-slot.connected {
  color: var(--text);
  border-color: rgba(45, 212, 125, 0.62);
  background:
    linear-gradient(135deg, rgba(45, 212, 125, 0.14), transparent 58%),
    rgba(255, 255, 255, 0.035);
  box-shadow: 0 0 0 1px rgba(45, 212, 125, 0.06) inset;
}

.rule-slot span {
  font-size: 11px;
  font-weight: 800;
}

.rule-slot strong {
  overflow: hidden;
  font-size: 11px;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 760px) {
  .rule-overview {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .rule-slot-grid {
    grid-template-columns: repeat(6, minmax(0, 1fr));
  }
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
</style>
