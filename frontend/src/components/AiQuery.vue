<script setup lang="ts">
import { ChatLineSquare, Loading, Promotion, Refresh, Edit, Delete, VideoPause, Open, TurnOff } from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import MarkdownMessage from '@/components/MarkdownMessage.vue';
import { sendAiQuery, parseAiCommand, sendCommand, type AiCommandResult } from '@/api/lab';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  dataSource?: string;
  diagnostic?: Record<string, unknown> | null;
  status?: 'sending' | 'queued' | 'generating' | 'done' | 'error';
  error?: string;
  editing?: boolean;
  command?: AiCommandResult;
  commandStatus?: 'pending' | 'confirming' | 'executing' | 'executed' | 'rejected' | 'error';
  commandResult?: string;
}

const visible = ref(false);
const input = ref('');
const textareaRef = ref<HTMLTextAreaElement | null>(null);
const messages = ref<ChatMessage[]>([]);
const chatBody = ref<HTMLDivElement | null>(null);
const queue = ref<string[]>([]);
const generating = ref(false);
const abortController = ref<AbortController | null>(null);
const aiStatus = ref<'idle' | 'connecting' | 'thinking' | 'replying'>('idle');

const exampleQuestions = [
  '哪块板的功耗最高?',
  'A001板的温度怎么样?',
  '现在有哪些告警?',
  '哪些板是离线状态?',
];

let msgCounter = 0;
function nextId() {
  return `msg-${Date.now()}-${++msgCounter}`;
}

const queueLength = computed(() => queue.value.length);
const canSend = computed(() => input.value.trim().length > 0);

function buildHistory(): Array<{ role: string; content: string }> {
  return messages.value
    .filter((msg) => msg.status === 'done' && (msg.role === 'user' || msg.role === 'assistant'))
    .map((msg) => ({ role: msg.role, content: msg.content }));
}

function scrollToBottom() {
  nextTick(() => {
    if (chatBody.value) {
      chatBody.value.scrollTop = chatBody.value.scrollHeight;
    }
  });
}

// ── Send / Queue ──────────────────────────────────────────────
function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey && !event.ctrlKey && !event.metaKey) {
    event.preventDefault();
    sendMessage();
  } else if (event.key === 'Enter' && event.ctrlKey) {
    event.preventDefault();
    sendMessage(true);
  }
}

function sendMessage(withContext = false) {
  const question = input.value.trim();
  if (!question) return;

  if (generating.value) {
    queue.value.push(question);
    messages.value.push({
      id: nextId(),
      role: 'user',
      content: question,
      status: 'queued',
    });
    input.value = '';
    scrollToBottom();
    return;
  }

  const historyPrefix = withContext ? buildContextPrefix() : '';
  const fullQuestion = historyPrefix + question;

  const msgIndex = messages.value.length;
  messages.value.push({
    id: nextId(),
    role: 'user',
    content: question,
    status: 'done',
  });
  input.value = '';
  scrollToBottom();

  // Check if it looks like a device command
  if (looksLikeCommand(question)) {
    void detectAndShowCommand(msgIndex);
  } else {
    processQuestion(fullQuestion);
  }
}

function buildContextPrefix(): string {
  const recent = messages.value
    .filter((msg) => msg.status === 'done')
    .slice(-6)
    .map((msg) => `${msg.role === 'user' ? '用户' : 'AI'}: ${msg.content.slice(0, 200)}`)
    .join('\n');
  return recent ? `基于当前对话上下文:\n${recent}\n\n请回答:\n` : '';
}

async function processQuestion(question: string) {
  generating.value = true;
  aiStatus.value = 'connecting';

  const assistantMsg: ChatMessage = {
    id: nextId(),
    role: 'assistant',
    content: '',
    status: 'generating',
  };
  messages.value.push(assistantMsg);
  scrollToBottom();

  const controller = new AbortController();
  abortController.value = controller;

  try {
    aiStatus.value = 'thinking';
    const history = buildHistory();
    const result = await sendAiQuery(question, history) as {
      reply: string;
      error?: string;
      format?: string;
      data_source?: string;
      diagnostic?: Record<string, unknown>;
    };

    if (controller.signal.aborted) return;

    aiStatus.value = 'replying';
    assistantMsg.content = result.reply;
    assistantMsg.dataSource = result.data_source;
    assistantMsg.diagnostic = result.diagnostic ?? null;
    assistantMsg.status = 'done';
  } catch (cause) {
    if (controller.signal.aborted) return;
    const errorMsg = cause instanceof Error ? cause.message : 'AI查询失败';
    assistantMsg.content = `请求失败: ${errorMsg}`;
    assistantMsg.error = errorMsg;
    assistantMsg.status = 'error';
    ElMessage.error(errorMsg);
  } finally {
    abortController.value = null;
    generating.value = false;
    aiStatus.value = 'idle';
    scrollToBottom();

    // Process queue
    if (queue.value.length > 0) {
      const next = queue.value.shift()!;
      const queuedMsg = messages.value.find((m) => m.status === 'queued');
      if (queuedMsg) queuedMsg.status = 'done';
      await nextTick();
      processQuestion(next);
    }
  }
}

// ── Command Detection ──────────────────────────────────────────
const commandKeywords = ['打开', '关闭', '关掉', '开', '关', 'on', 'off', 'auto', '自动', '电机', '灯', '补光灯', '风扇', '通风'];

function looksLikeCommand(text: string): boolean {
  const lower = text.toLowerCase();
  const hasKeyword = commandKeywords.some((kw) => lower.includes(kw));
  const hasDevice = /[aA]\d{3}|槽位\d+|bearpi/i.test(text);
  return hasKeyword && hasDevice;
}

async function detectAndShowCommand(msgIndex: number) {
  const userMsg = messages.value[msgIndex];
  if (!userMsg || userMsg.role !== 'user') return;

  // Add a command card message after the user message
  const cmdMsg: ChatMessage = {
    id: nextId(),
    role: 'assistant',
    content: '',
    status: 'done',
    commandStatus: 'confirming',
  };
  messages.value.splice(msgIndex + 1, 0, cmdMsg);
  scrollToBottom();

  try {
    const result = await parseAiCommand(userMsg.content);
    cmdMsg.command = result;

    if (result.detected && result.device_id) {
      cmdMsg.content = `检测到控制指令: ${result.explanation || ''}`;
      cmdMsg.commandStatus = 'confirming';
    } else {
      cmdMsg.content = result.explanation || '未识别为设备控制指令';
      cmdMsg.commandStatus = 'rejected';
      cmdMsg.command = undefined;
    }
  } catch {
    cmdMsg.content = '指令解析失败';
    cmdMsg.commandStatus = 'error';
  }
  scrollToBottom();
}

async function executeCommand(msgIndex: number) {
  const cmdMsg = messages.value[msgIndex];
  if (!cmdMsg?.command?.device_id) return;

  cmdMsg.commandStatus = 'executing';
  cmdMsg.content = '正在执行指令...';

  try {
    const { device_id, actuator, mode } = cmdMsg.command;
    const paramKey = actuator === 'motor' ? 'motor_override' : 'light_override';
    const params: Record<string, string | number | boolean> = {};
    params[paramKey] = mode ?? 'on';
    await sendCommand(device_id!, {
      type: 'set_param',
      params,
    });
    cmdMsg.commandStatus = 'executed';
    cmdMsg.content = `指令已下发: ${cmdMsg.command.device_sn} ${actuator === 'motor' ? '电机' : '补光灯'} ${mode === 'on' ? '打开' : mode === 'off' ? '关闭' : '自动'}`;
    ElMessage.success('指令已下发');
  } catch (cause) {
    cmdMsg.commandStatus = 'error';
    cmdMsg.content = `指令执行失败: ${cause instanceof Error ? cause.message : '未知错误'}`;
    ElMessage.error('指令执行失败');
  }
  scrollToBottom();
}

function rejectCommand(msgIndex: number) {
  const cmdMsg = messages.value[msgIndex];
  if (cmdMsg) {
    cmdMsg.commandStatus = 'rejected';
    cmdMsg.content = '已取消执行';
  }
}

// ── Stop ──────────────────────────────────────────────────────
function stopGeneration() {
  abortController.value?.abort();
  abortController.value = null;
  generating.value = false;
  aiStatus.value = 'idle';
  const last = messages.value[messages.value.length - 1];
  if (last?.role === 'assistant' && last.status === 'generating') {
    if (!last.content) {
      messages.value.pop();
    } else {
      last.status = 'done';
      last.content += '\n\n*[已停止生成]*';
    }
  }
  queue.value = [];
  messages.value.forEach((m) => {
    if (m.status === 'queued') m.status = 'done';
  });
}

// ── Regenerate ────────────────────────────────────────────────
function regenerate(index: number) {
  const msg = messages.value[index];
  if (!msg || msg.role !== 'assistant') return;

  // Find the user question before this assistant message
  let questionIndex = -1;
  for (let i = index - 1; i >= 0; i--) {
    if (messages.value[i].role === 'user') {
      questionIndex = i;
      break;
    }
  }
  if (questionIndex < 0) return;

  const question = messages.value[questionIndex].content;

  // Remove the old assistant response
  messages.value.splice(index, 1);

  // Re-process
  if (!generating.value) {
    processQuestion(question);
  } else {
    queue.value.push(question);
  }
}

// ── Edit & Resend ─────────────────────────────────────────────
function startEdit(index: number) {
  const msg = messages.value[index];
  if (!msg || msg.role !== 'user') return;
  msg.editing = true;
}

function confirmEdit(index: number, newContent: string) {
  const msg = messages.value[index];
  if (!msg || msg.role !== 'user') return;
  msg.content = newContent;
  msg.editing = false;

  // Remove all messages after this one
  messages.value.splice(index + 1);

  // Re-send
  if (!generating.value) {
    processQuestion(newContent);
  } else {
    queue.value.push(newContent);
  }
}

function cancelEdit(index: number) {
  const msg = messages.value[index];
  if (msg) msg.editing = false;
}

// ── Utils ─────────────────────────────────────────────────────
function useExample(question: string) {
  input.value = question;
  sendMessage();
}

function open() {
  visible.value = true;
  nextTick(() => textareaRef.value?.focus());
}

function clearChat() {
  messages.value = [];
  queue.value = [];
  if (generating.value) stopGeneration();
}

function formatDiagnostic(diag: Record<string, unknown>): string {
  const parts: string[] = [];
  if (diag.upstream_status) parts.push(`HTTP ${diag.upstream_status}`);
  if (diag.model) parts.push(`模型: ${diag.model}`);
  if (diag.url_host) parts.push(`Host: ${diag.url_host}`);
  if (diag.reason) parts.push(diag.reason as string);
  return parts.join(' | ');
}

const statusLabel = computed(() => {
  switch (aiStatus.value) {
    case 'connecting': return '正在连接模型...';
    case 'thinking': return 'AI正在思考...';
    case 'replying': return 'AI正在回复...';
    default: return '';
  }
});

onBeforeUnmount(() => {
  if (generating.value) stopGeneration();
});

watch(visible, (val) => {
  if (val) nextTick(() => textareaRef.value?.focus());
});
</script>

<template>
  <el-button type="primary" plain @click="open">
    <ChatLineSquare :size="16" />
    AI问答
  </el-button>

  <el-dialog
    v-model="visible"
    title="AI智能问答"
    width="min(800px, 95vw)"
    append-to-body
    :close-on-click-modal="!generating"
    :z-index="9999"
    lock-scroll
    destroy-on-close
  >
    <div class="ai-query-container">
      <!-- Status bar -->
      <div v-if="generating || queueLength > 0" class="status-bar">
        <div v-if="generating" class="status-item generating">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span>{{ statusLabel }}</span>
          <button class="stop-btn" @click="stopGeneration">
            <VideoPause :size="14" />
            停止
          </button>
        </div>
        <div v-if="queueLength > 0" class="status-item queued">
          <span>队列中: {{ queueLength }} 条</span>
        </div>
      </div>

      <!-- Chat body -->
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
          <div class="shortcut-hint">
            <span>Enter 发送</span>
            <span>Shift+Enter 换行</span>
            <span>Ctrl+Enter 引用上下文</span>
          </div>
        </div>

        <div v-for="(msg, index) in messages" :key="msg.id" :class="['chat-message', msg.role, `status-${msg.status}`]">
          <div class="message-bubble">
            <!-- User message: editable -->
            <template v-if="msg.role === 'user'">
              <div v-if="msg.editing" class="edit-area">
                <textarea
                  :value="msg.content"
                  class="edit-textarea"
                  @keydown.enter.exact.prevent="confirmEdit(index, ($event.target as HTMLTextAreaElement).value)"
                  @keydown.esc.prevent="cancelEdit(index)"
                />
                <div class="edit-actions">
                  <button class="edit-confirm" @click="confirmEdit(index, ($event.target as HTMLElement).closest('.edit-area')?.querySelector('textarea')?.value ?? msg.content)">确认</button>
                  <button class="edit-cancel" @click="cancelEdit(index)">取消</button>
                </div>
              </div>
              <template v-else>
                <pre>{{ msg.content }}</pre>
                <div class="msg-actions">
                  <button class="msg-action-btn" title="编辑" @click="startEdit(index)">
                    <Edit :size="12" />
                  </button>
                </div>
              </template>
            </template>

            <!-- Assistant message -->
            <template v-else>
              <!-- Command card -->
              <template v-if="msg.commandStatus">
                <div class="command-card" :class="`cmd-${msg.commandStatus}`">
                  <div class="cmd-icon">
                    <el-icon v-if="msg.commandStatus === 'confirming'" class="is-loading"><Loading /></el-icon>
                    <el-icon v-else-if="msg.commandStatus === 'executing'" class="is-loading"><Loading /></el-icon>
                    <el-icon v-else-if="msg.commandStatus === 'executed'"><Open /></el-icon>
                    <el-icon v-else-if="msg.commandStatus === 'rejected'"><TurnOff /></el-icon>
                    <el-icon v-else><TurnOff /></el-icon>
                  </div>
                  <div class="cmd-info">
                    <div v-if="msg.command?.detected && msg.commandStatus === 'confirming'" class="cmd-detail">
                      <strong>设备控制指令</strong>
                      <span>设备: {{ msg.command.device_sn }} (槽位{{ msg.command.slot_no }})</span>
                      <span>执行器: {{ msg.command.actuator === 'motor' ? '电机' : '补光灯' }}</span>
                      <span>动作: {{ msg.command.mode === 'on' ? '打开' : msg.command.mode === 'off' ? '关闭' : '自动' }}</span>
                      <span v-if="msg.command.confidence">置信度: {{ Math.round(msg.command.confidence * 100) }}%</span>
                      <div class="cmd-actions">
                        <button class="cmd-confirm" @click="executeCommand(index)">确认执行</button>
                        <button class="cmd-reject" @click="rejectCommand(index)">取消</button>
                      </div>
                    </div>
                    <template v-else>
                      <span>{{ msg.content }}</span>
                    </template>
                  </div>
                </div>
              </template>

              <!-- Normal AI response -->
              <template v-else-if="msg.status === 'generating' && !msg.content">
                <div class="loading-bubble">
                  <el-icon class="is-loading"><Loading /></el-icon>
                  <span>{{ statusLabel || '思考中...' }}</span>
                </div>
              </template>
              <template v-else>
                <MarkdownMessage :content="msg.content" :data-source="msg.dataSource" />
                <details v-if="msg.diagnostic" class="diagnostic-details">
                  <summary>开发调试信息</summary>
                  <pre class="diagnostic-pre">{{ formatDiagnostic(msg.diagnostic) }}</pre>
                </details>
                <div v-if="msg.status === 'done' || msg.status === 'error'" class="msg-actions">
                  <button class="msg-action-btn" title="重新生成" @click="regenerate(index)">
                    <Refresh :size="12" />
                    <span>重新生成</span>
                  </button>
                </div>
              </template>
            </template>
          </div>
        </div>
      </div>

      <!-- Input area -->
      <div class="chat-input">
        <div class="input-wrapper">
          <textarea
            ref="textareaRef"
            v-model="input"
            class="chat-textarea"
            placeholder="输入问题... Enter发送, Shift+Enter换行, Ctrl+Enter引用上下文"
            rows="1"
            @keydown="handleKeydown"
          />
        </div>
        <button
          class="send-btn"
          :disabled="!canSend"
          @click="sendMessage()"
        >
          <Promotion :size="16" />
          <span>发送</span>
        </button>
        <button v-if="messages.length" class="clear-btn" @click="clearChat">清空</button>
      </div>
    </div>
  </el-dialog>
</template>

<style scoped>
.ai-query-container {
  display: flex;
  flex-direction: column;
  height: min(70vh, 600px);
}

/* ── Status Bar ──────────────────────────────────────────────── */
.status-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  margin-bottom: 8px;
  border-radius: 8px;
  background: rgba(56, 189, 248, 0.05);
  border: 1px solid rgba(56, 189, 248, 0.1);
  font-size: 13px;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.status-item.generating {
  color: var(--cyan);
}

.status-item.queued {
  color: var(--amber);
}

.stop-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
  padding: 4px 10px;
  border: 1px solid rgba(255, 104, 116, 0.3);
  border-radius: 6px;
  background: rgba(255, 104, 116, 0.08);
  color: var(--red);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 150ms ease;
}

.stop-btn:hover {
  background: rgba(255, 104, 116, 0.15);
  border-color: rgba(255, 104, 116, 0.5);
}

/* ── Chat Body ───────────────────────────────────────────────── */
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

.shortcut-hint {
  display: flex;
  gap: 16px;
  justify-content: center;
  margin-top: 20px;
  font-size: 12px;
  color: var(--text-subtle);
}

.shortcut-hint span {
  padding: 3px 8px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.02);
}

/* ── Messages ────────────────────────────────────────────────── */
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
  position: relative;
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

.chat-message.status-queued .message-bubble {
  opacity: 0.6;
}

.chat-message.status-error .message-bubble {
  border-color: rgba(255, 104, 116, 0.3);
}

.loading-bubble {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-muted);
}

/* ── Command Card ────────────────────────────────────────────── */
.command-card {
  display: flex;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--panel-soft);
}

.cmd-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  flex-shrink: 0;
}

.cmd-confirming .cmd-icon {
  background: rgba(56, 189, 248, 0.1);
  color: var(--cyan);
}

.cmd-executing .cmd-icon {
  background: rgba(246, 184, 75, 0.1);
  color: var(--amber);
}

.cmd-executed .cmd-icon {
  background: rgba(45, 212, 125, 0.1);
  color: var(--green);
}

.cmd-rejected .cmd-icon,
.cmd-error .cmd-icon {
  background: rgba(255, 104, 116, 0.1);
  color: var(--red);
}

.cmd-info {
  flex: 1;
  min-width: 0;
}

.cmd-detail {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.cmd-detail strong {
  color: var(--text);
  font-size: 14px;
}

.cmd-detail span {
  color: var(--text-muted);
  font-size: 13px;
}

.cmd-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

.cmd-confirm {
  padding: 6px 16px;
  border: 1px solid rgba(45, 212, 125, 0.4);
  border-radius: 6px;
  background: rgba(45, 212, 125, 0.12);
  color: var(--green);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 150ms ease;
}

.cmd-confirm:hover {
  background: rgba(45, 212, 125, 0.2);
  border-color: rgba(45, 212, 125, 0.6);
  box-shadow: 0 0 10px rgba(45, 212, 125, 0.15);
}

.cmd-reject {
  padding: 6px 16px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: transparent;
  color: var(--text-muted);
  font-size: 13px;
  cursor: pointer;
  transition: all 150ms ease;
}

.cmd-reject:hover {
  border-color: var(--border-strong);
  color: var(--text);
}

.cmd-confirming {
  border-color: rgba(56, 189, 248, 0.2);
}

.cmd-executing {
  border-color: rgba(246, 184, 75, 0.2);
}

.cmd-executed {
  border-color: rgba(45, 212, 125, 0.2);
}

.cmd-rejected,
.cmd-error {
  border-color: rgba(255, 104, 116, 0.15);
  opacity: 0.7;
}

/* ── Message Actions ─────────────────────────────────────────── */
.msg-actions {
  display: flex;
  gap: 6px;
  margin-top: 8px;
  opacity: 0;
  transition: opacity 150ms ease;
}

.chat-message:hover .msg-actions {
  opacity: 1;
}

.msg-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border: 1px solid var(--border);
  border-radius: 5px;
  background: transparent;
  color: var(--text-muted);
  font-size: 11px;
  cursor: pointer;
  transition: all 150ms ease;
}

.msg-action-btn:hover {
  border-color: var(--border-strong);
  color: var(--text);
  background: rgba(255, 255, 255, 0.03);
}

/* ── Edit Area ───────────────────────────────────────────────── */
.edit-area {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.edit-textarea {
  width: 100%;
  min-height: 60px;
  padding: 8px;
  border: 1px solid var(--cyan);
  border-radius: 6px;
  background: rgba(5, 12, 18, 0.6);
  color: var(--text);
  font-size: 14px;
  font-family: inherit;
  resize: vertical;
}

.edit-textarea:focus {
  outline: none;
  box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.15);
}

.edit-actions {
  display: flex;
  gap: 6px;
}

.edit-confirm,
.edit-cancel {
  padding: 4px 12px;
  border: 1px solid var(--border);
  border-radius: 5px;
  font-size: 12px;
  cursor: pointer;
  transition: all 150ms ease;
}

.edit-confirm {
  background: var(--cyan);
  border-color: var(--cyan);
  color: #061018;
  font-weight: 600;
}

.edit-cancel {
  background: transparent;
  color: var(--text-muted);
}

/* ── Diagnostic ──────────────────────────────────────────────── */
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

/* ── Input Area ──────────────────────────────────────────────── */
.chat-input {
  display: flex;
  gap: 10px;
  align-items: flex-end;
  padding-top: 14px;
  border-top: 1px solid var(--border);
}

.input-wrapper {
  flex: 1;
}

.chat-textarea {
  width: 100%;
  min-height: 40px;
  max-height: 120px;
  padding: 10px 14px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: rgba(5, 12, 18, 0.5);
  color: var(--text);
  font-size: 14px;
  font-family: inherit;
  line-height: 1.5;
  resize: none;
  overflow-y: auto;
  transition: border-color 200ms ease, box-shadow 200ms ease;
}

.chat-textarea:focus {
  outline: none;
  border-color: rgba(56, 189, 248, 0.4);
  box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.08);
}

.chat-textarea::placeholder {
  color: var(--text-subtle);
}

.send-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-width: 80px;
  height: 40px;
  padding: 0 16px;
  border: 1px solid rgba(56, 189, 248, 0.3);
  border-radius: 8px;
  background: linear-gradient(135deg, rgba(56, 189, 248, 0.15), rgba(45, 212, 125, 0.1));
  color: #e0f2fe;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 200ms cubic-bezier(0.25, 1, 0.5, 1);
  white-space: nowrap;
}

.send-btn:hover:not(:disabled) {
  background: linear-gradient(135deg, rgba(56, 189, 248, 0.25), rgba(45, 212, 125, 0.18));
  border-color: rgba(56, 189, 248, 0.5);
  box-shadow: 0 0 12px rgba(56, 189, 248, 0.15);
  transform: translateY(-1px);
}

.send-btn:active:not(:disabled) {
  transform: translateY(0);
}

.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  border-color: rgba(56, 189, 248, 0.1);
  background: rgba(17, 26, 34, 0.5);
  color: var(--text-subtle);
}

.clear-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 40px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: transparent;
  color: var(--text-muted);
  font-size: 13px;
  cursor: pointer;
  transition: all 200ms cubic-bezier(0.25, 1, 0.5, 1);
  white-space: nowrap;
}

.clear-btn:hover {
  border-color: var(--border-strong);
  color: var(--text);
  background: rgba(255, 255, 255, 0.03);
}

@media (max-width: 480px) {
  .send-btn {
    min-width: 64px;
    height: 36px;
    padding: 0 12px;
    font-size: 13px;
  }

  .clear-btn {
    height: 36px;
    padding: 0 10px;
    font-size: 12px;
  }

  .shortcut-hint {
    flex-direction: column;
    gap: 6px;
  }
}
</style>
