<script setup lang="ts">
import { ChatLineSquare, Loading, Promotion } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
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
const chatBody = ref<HTMLDivElement | null>(null);

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
    const result = await sendAiQuery(question) as { reply: string; error?: string; diagnostic?: Record<string, unknown> };
    messages.value.push({
      role: 'assistant',
      content: result.reply,
      diagnostic: result.diagnostic ?? null,
    });
  } catch (cause) {
    const error = cause instanceof Error ? cause.message : 'AI查询失败';
    messages.value.push({ role: 'assistant', content: `请求失败: ${error}`, diagnostic: null });
    ElMessage.error(error);
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
  if (chatBody.value) {
    chatBody.value.scrollTop = chatBody.value.scrollHeight;
  }
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
  <el-button type="primary" plain @click="open">
    <ChatLineSquare :size="16" />
    AI问答
  </el-button>

  <el-dialog v-model="visible" title="AI智能问答" width="min(720px, 95vw)" :close-on-click-modal="!loading">
    <div class="ai-query-container">
      <div ref="chatBody" class="chat-body">
        <div v-if="messages.length === 0" class="chat-welcome">
          <p>你好!我是实验室AI助手,可以回答关于设备、传感器、告警等任何问题。</p>
          <p>试试问:</p>
          <div class="example-list">
            <el-button
              v-for="q in exampleQuestions"
              :key="q"
              size="small"
              plain
              @click="useExample(q)"
            >
              {{ q }}
            </el-button>
          </div>
        </div>

        <div v-for="(msg, index) in messages" :key="index" :class="['chat-message', msg.role]">
          <div class="message-bubble">
            <pre>{{ msg.content }}</pre>
            <details v-if="msg.diagnostic" class="diagnostic-details">
              <summary>开发调试信息</summary>
              <pre class="diagnostic-pre">{{ formatDiagnostic(msg.diagnostic) }}</pre>
            </details>
          </div>
        </div>

        <div v-if="loading" class="chat-message assistant">
          <div class="message-bubble loading-bubble">
            <el-icon class="is-loading"><Loading /></el-icon>
            <span>思考中...</span>
          </div>
        </div>
      </div>

      <div class="chat-input">
        <el-input
          v-model="input"
          placeholder="输入你的问题,比如:哪块板功耗最高?"
          :disabled="loading"
          @keyup.enter="send"
        >
          <template #append>
            <el-button :disabled="!canSend" @click="send">
              <Promotion :size="16" />
            </el-button>
          </template>
        </el-input>
        <el-button v-if="messages.length" size="small" plain @click="clearChat">清空对话</el-button>
      </div>
    </div>
  </el-dialog>
</template>

<style scoped>
.ai-query-container {
  display: flex;
  flex-direction: column;
  height: min(60vh, 500px);
}

.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.chat-welcome {
  text-align: center;
  padding: 24px 16px;
  color: var(--text-muted);
}

.chat-welcome p {
  margin: 0 0 12px;
}

.example-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  margin-top: 16px;
}

.chat-message {
  display: flex;
}

.chat-message.user {
  justify-content: flex-end;
}

.chat-message.assistant {
  justify-content: flex-start;
}

.message-bubble {
  max-width: 85%;
  padding: 12px 16px;
  border-radius: 12px;
  line-height: 1.6;
}

.message-bubble pre {
  margin: 0;
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: inherit;
  font-size: 14px;
}

.chat-message.user .message-bubble {
  background: var(--cyan);
  color: #061018;
  border-bottom-right-radius: 4px;
}

.chat-message.user .message-bubble pre {
  color: #061018;
}

.chat-message.assistant .message-bubble {
  background: var(--panel-soft);
  border: 1px solid var(--border);
  color: var(--text);
  border-bottom-left-radius: 4px;
}

.loading-bubble {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-muted);
}

.diagnostic-details {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--border);
}

.diagnostic-details summary {
  cursor: pointer;
  color: var(--amber);
  font-size: 12px;
  font-weight: 700;
}

.diagnostic-pre {
  margin-top: 6px;
  padding: 8px;
  background: rgba(246, 184, 75, 0.08);
  border-radius: 6px;
  color: var(--amber);
  font-size: 12px;
  line-height: 1.5;
}

.chat-input {
  display: flex;
  gap: 8px;
  align-items: center;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}

.chat-input .el-input {
  flex: 1;
}
</style>
