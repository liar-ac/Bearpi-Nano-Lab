<script setup lang="ts">
import { computed, nextTick, ref } from 'vue';
import { sendAiQuery } from '@/api/lab';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

const visible = ref(false);
const input = ref('');
const loading = ref(false);
const messages = ref<ChatMessage[]>([]);
const chatBody = ref<any>(null);

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
  scrollToBottom();

  try {
    const result = await sendAiQuery(question);
    messages.value.push({ role: 'assistant', content: result.reply });
  } catch (cause) {
    const error = cause instanceof Error ? cause.message : 'AI查询失败';
    messages.value.push({ role: 'assistant', content: `错误: ${error}` });
    uni.showToast({ title: error, icon: 'none' });
  } finally {
    loading.value = false;
    await nextTick();
    scrollToBottom();
  }
}

function useExample(question: string) {
  input.value = question;
  void send();
}

function scrollToBottom() {
  // scroll-into-view prop handles scrolling inside scroll-view
}

function open() {
  visible.value = true;
}

function clearChat() {
  messages.value = [];
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

.chat-message.user {
  justify-content: flex-end;
}

.chat-message.assistant {
  justify-content: flex-start;
}

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

  text {
    color: #ffffff;
  }
}

.chat-message.assistant .message-bubble {
  background: #f0f2f5;
  border: 1rpx solid $uni-border-color;
  border-bottom-left-radius: 4rpx;

  text {
    color: #172033;
  }
}

.loading-bubble {
  display: flex;
  align-items: center;
  gap: 12rpx;

  text {
    color: $uni-text-color-grey;
    font-size: 24rpx;
  }
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
