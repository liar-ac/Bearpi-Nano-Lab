<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue';
import MarkdownMessage from '@/components/MarkdownMessage.vue';
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
const dataSource = ref('');
const abortController = ref<AbortController | null>(null);

const featureTitles: Record<AiFeature, string> = {
  alarm_diagnosis: 'AI告警诊断',
  data_analysis: 'AI数据分析',
  rule_suggestion: 'AI规则建议',
};

const displayTitle = computed(() => props.title ?? featureTitles[props.feature] ?? 'AI分析');

async function analyze() {
  if (loading.value) return;
  visible.value = true;
  loading.value = true;
  error.value = '';
  reply.value = '';
  dataSource.value = '';
  abortController.value?.abort();
  abortController.value = new AbortController();
  try {
    const result = await sendAiChat(props.feature, props.context, abortController.value.signal);
    reply.value = result.reply;
    dataSource.value = result.data_source ?? '';
  } catch (cause) {
    if (abortController.value?.signal.aborted) return;
    error.value = cause instanceof Error ? cause.message : 'AI分析请求失败';
    uni.showToast({ title: error.value, icon: 'none' });
  } finally {
    loading.value = false;
    abortController.value = null;
  }
}

function cancel() {
  abortController.value?.abort();
}

onBeforeUnmount(() => {
  abortController.value?.abort();
});

function close() {
  if (loading.value) return;
  visible.value = false;
}
</script>

<template>
  <wd-button size="small" type="primary" plain @click="analyze">
    {{ triggerText ?? 'AI分析' }}
  </wd-button>

  <wd-popup :model-value="visible" position="bottom" closable custom-style="max-height: 80vh; padding: 24rpx; border-radius: 24rpx 24rpx 0 0;" @update:model-value="(v: any) => { if (!loading) visible = v; }">
    <view class="ai-popup">
      <view class="ai-title">
        <text>{{ displayTitle }}</text>
      </view>

      <view v-if="loading" class="ai-loading">
        <wd-loading />
        <text>AI正在分析中,请稍候...</text>
        <wd-button size="small" plain @click="cancel">取消</wd-button>
      </view>

      <view v-else-if="error" class="ai-error">
        <text>{{ error }}</text>
      </view>

      <view v-else-if="reply" class="ai-reply">
        <MarkdownMessage :content="reply" />
        <text v-if="dataSource" class="data-source">数据来源: {{ dataSource }}</text>
      </view>

      <wd-button block plain @click="close">关闭</wd-button>
    </view>
  </wd-popup>
</template>

<style lang="scss" scoped>
.ai-popup {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
  padding: 12rpx 0;
}

.ai-title {
  text {
    color: #172033;
    font-size: 32rpx;
    font-weight: 800;
  }
}

.ai-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20rpx;
  padding: 60rpx 0;

  text {
    color: $uni-text-color-grey;
    font-size: 26rpx;
  }
}

.data-source {
  display: block;
  margin-top: 16rpx;
  padding-top: 16rpx;
  border-top: 1rpx solid $uni-border-color;
  color: $uni-text-color-grey;
  font-size: 22rpx;
}

.ai-error {
  padding: 24rpx;
  border-radius: 8rpx;
  background: #fff1f0;

  text {
    color: #b42318;
    font-size: 26rpx;
  }
}

.ai-reply {
  padding: 24rpx;
  border: 1rpx solid $uni-border-color;
  border-radius: 8rpx;
  background: #f8fafc;

  text {
    color: #172033;
    font-size: 26rpx;
    line-height: 1.8;
  }
}
</style>
