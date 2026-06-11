<script setup lang="ts">
import { Close, Loading, MagicStick } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import { computed, nextTick, ref } from 'vue';
import { sendAiChat } from '@/api/lab';

type AiFeature = 'alarm_diagnosis' | 'data_analysis' | 'rule_suggestion';

const props = defineProps<{
  feature: AiFeature;
  context: Record<string, unknown>;
  triggerText?: string;
  title?: string;
}>();

const visible = ref(false);
const loading = ref(false);
const reply = ref('');
const error = ref('');
let abortController: AbortController | null = null;

const featureTitles: Record<AiFeature, string> = {
  alarm_diagnosis: 'AI告警诊断',
  data_analysis: 'AI数据分析',
  rule_suggestion: 'AI规则建议',
};

const displayTitle = computed(() => props.title ?? featureTitles[props.feature] ?? 'AI分析');

async function analyze() {
  abortController?.abort();
  abortController = new AbortController();
  visible.value = true;
  loading.value = true;
  error.value = '';
  reply.value = '';
  await nextTick();
  try {
    const result = await sendAiChat(props.feature, props.context, abortController.signal);
    reply.value = result.reply;
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') return;
    error.value = cause instanceof Error ? cause.message : 'AI分析请求失败';
    ElMessage.error(error.value);
  } finally {
    loading.value = false;
    abortController = null;
  }
}

function close() {
  if (loading.value) {
    abortController?.abort();
    loading.value = false;
  }
  visible.value = false;
}
</script>

<template>
  <el-button size="small" type="primary" plain @click="analyze">
    <MagicStick :size="15" />
    {{ triggerText ?? 'AI分析' }}
  </el-button>

  <el-dialog
    v-model="visible"
    :title="displayTitle"
    width="min(640px, 90vw)"
    append-to-body
    :close-on-click-modal="!loading"
    :z-index="9999"
    lock-scroll
    destroy-on-close
    @close="close"
  >
    <div v-if="loading" class="ai-loading">
      <el-icon class="is-loading" :size="28"><Loading /></el-icon>
      <p>AI正在分析中,请稍候...</p>
    </div>

    <div v-else-if="error" class="ai-error">
      <p>{{ error }}</p>
    </div>

    <div v-else-if="reply" class="ai-reply">
      <pre>{{ reply }}</pre>
    </div>

    <template #footer>
      <el-button @click="close">
        <Close :size="15" />
        关闭
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.ai-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 40px 0;
  color: var(--text-muted);
}

.ai-loading p {
  margin: 0;
}

.ai-error {
  padding: 20px;
  color: var(--red);
  background: rgba(255, 104, 116, 0.08);
  border-radius: var(--radius);
}

.ai-error p {
  margin: 0;
}

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
