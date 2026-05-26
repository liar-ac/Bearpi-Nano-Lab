<script setup lang="ts">
import { computed, nextTick, ref } from 'vue';
import { sendAiQuery } from '@/api/lab';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  diagnostic?: Record<string, unknown> | null;
}

const visible = ref(false);
const input = ref('');
const loading = ref(false);
const messages = ref<ChatMessage[]>([]);

const exampleQuestions = [
  '哪块板的功耗最高?',
  'A001板的温度怎么样?',
  '现在有哪些告警?',
  '哪些板是离线状态?',
];

const canSend = computed(() => input.value.trim().length > 0 && !loading.value);

async function send() {
  const question = input.value.trim();
  if (!question || loading.value) return;

  messages.value.push({ role: 'user', content: question });
  input.value = '';
  loading.value = true;

  await nextTick();

  try {
    const result = await sendAiQuery(question) as { reply: string; error?: string; diagnostic?: Record<string, unknown> };
    messages.value.push({
      role: 'assistant',
      content: result.reply,
      diagnostic: result.diagnostic ?? null,
    });
  } catch (cause) {
    const error = cause instanceof Error ? cause.message : 'AI查询失败';
    messages.value.push({ role: 'assistant', content: `请求失败: ${error}`, diagnostic: null });
    uni.showToast({ title: error, icon: 'none' });
  } finally {
    loading.value = false;
    await nextTick();
  }
}

function useExample(question: string) {
  input.value = question;
  void send();
}

function open() {
  visible.value = true;
}

function clearChat() {
  messages.value = [];
}

function formatDiagnostic(diag: Record<string, unknown>): string {
  const parts: string[] = [];
  if (diag.upstream_status) parts.push(`HTTP ${diag.upstream_status}`);
  if (diag.model) parts.push(`模型: ${diag.model}`);
  if (diag.url_host) parts.push(`Host: ${diag.url_host}`);
  if (diag.reason) parts.push(diag.reason as string);
  return parts.join(' | ');
}
</script>

<template>
  <wd-button size="small" type="primary" plain @click="open">AI问答</wd-button>

  <wd-popup v-model="visible" position="bottom" closable custom-style="max-height: 85vh; padding: 24rpx; border-radius: 24rpx 24rpx 0 0;">
    <view class="ai-query">
      <view class="ai-query-title">
        <text>AI智能问答</text>
      </view>

      <scroll-view class="chat-body" scroll-y :scroll-into-view="messages.length ? 'msg-' + (messages.length - 1) : ''">
        <view v-if="messages.length === 0" class="chat-welcome">
          <text>你好!我是实验室AI助手,可以回答关于设备、传感器、告警等任何问题。</text>
          <text>试试问:</text>
          <view class="example-list">
            <wd-button
              v-for="q in exampleQuestions"
              :key="q"
              size="small"
              plain
              @click="useExample(q)"
            >
              {{ q }}
            </wd-button>
          </view>
        </view>

        <view
          v-for="(msg, index) in messages"
          :key="index"
          :id="'msg-' + index"
          :class="['chat-message', msg.role]"
        >
          <view class="message-bubble">
            <text selectable>{{ msg.content }}</text>
            <view v-if="msg.diagnostic" class="diagnostic-box">
              <text class="diagnostic-title">调试信息</text>
              <text class="diagnostic-text">{{ formatDiagnostic(msg.diagnostic) }}</text>
            </view>
          </view>
        </view>

        <view v-if="loading" class="chat-message assistant">
          <view class="message-bubble loading-bubble">
            <wd-loading size="20" />
            <text>思考中...</text>
          </view>
        </view>
      </scroll-view>

      <view class="chat-input">
        <view class="input-row">
          <input
            v-model="input"
            class="chat-input-field"
            placeholder="输入你的问题..."
            :disabled="loading"
            confirm-type="send"
            @confirm="send"
          />
          <wd-button size="small" type="primary" :disabled="!canSend" @click="send">发送</wd-button>
        </view>
        <wd-button v-if="messages.length" size="small" plain @click="clearChat">清空对话</wd-button>
      </view>
    </view>
  </wd-popup>
</template>

<style lang="scss" scoped>
.ai-query {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
  height: 70vh;
}

.ai-query-title {
  text {
    color: #172033;
    font-size: 32rpx;
    font-weight: 800;
  }
}

.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 12rpx 0;
}

.chat-welcome {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
  padding: 32rpx 16rpx;
  text-align: center;
  color: $uni-text-color-grey;
  font-size: 26rpx;
}

.example-list {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
  justify-content: center;
  margin-top: 16rpx;
}

.chat-message {
  display: flex;
  margin-bottom: 16rpx;
}

.chat-message.user { justify-content: flex-end; }
.chat-message.assistant { justify-content: flex-start; }

.message-bubble {
  max-width: 85%;
  padding: 20rpx 24rpx;
  border-radius: 16rpx;
  line-height: 1.6;
}

.message-bubble text {
  font-size: 26rpx;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.chat-message.user .message-bubble {
  background: $uni-color-primary;
  border-bottom-right-radius: 4rpx;
  text { color: #ffffff; }
}

.chat-message.assistant .message-bubble {
  background: #f0f2f5;
  border: 1rpx solid $uni-border-color;
  border-bottom-left-radius: 4rpx;
  text { color: #172033; }
}

.loading-bubble {
  display: flex;
  align-items: center;
  gap: 12rpx;
  text { color: $uni-text-color-grey; font-size: 24rpx; }
}

.diagnostic-box {
  margin-top: 12rpx;
  padding: 12rpx;
  border-top: 1rpx dashed $uni-border-color;
}

.diagnostic-title {
  display: block;
  color: #9a5b00;
  font-size: 22rpx;
  font-weight: 700;
  margin-bottom: 6rpx;
}

.diagnostic-text {
  display: block;
  color: #9a5b00;
  font-size: 22rpx;
  line-height: 1.5;
}

.chat-input {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
  padding-top: 16rpx;
  border-top: 1rpx solid $uni-border-color;
}

.input-row {
  display: flex;
  gap: 12rpx;
  align-items: center;
}

.chat-input-field {
  flex: 1;
  height: 72rpx;
  padding: 0 20rpx;
  border: 1rpx solid $uni-border-color;
  border-radius: 8rpx;
  background: #f8fafc;
  color: #172033;
  font-size: 26rpx;
}
</style>
