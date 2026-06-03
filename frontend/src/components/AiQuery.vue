<script setup lang="ts">
import {
  ChatLineSquare, Loading, Promotion, Refresh, Edit, VideoPause,
  Plus, Delete, CopyDocument, CircleCheck, Top, Bottom
} from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import MarkdownMessage from '@/components/MarkdownMessage.vue';
import { sendAiQuery, parseAiCommand, sendCommand, type AiCommandResult } from '@/api/lab';

// ── Types ─────────────────────────────────────────────────────
interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  ts: number;
  dataSource?: string;
  diagnostic?: Record<string, unknown> | null;
  status?: 'sending' | 'queued' | 'generating' | 'done' | 'error';
  error?: string;
  editing?: boolean;
  command?: AiCommandResult;
  commandStatus?: 'pending' | 'confirming' | 'executing' | 'executed' | 'rejected' | 'error';
  commandResult?: string;
  reaction?: 'up' | 'down' | null;
}

interface ChatSession {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: number;
  updatedAt: number;
}

// ── State ─────────────────────────────────────────────────────
const visible = ref(false);
const input = ref('');
const textareaRef = ref<HTMLTextAreaElement | null>(null);
const chatBody = ref<HTMLDivElement | null>(null);
const sessions = ref<ChatSession[]>([]);
const currentSessionId = ref<string>('');
const queue = ref<string[]>([]);
const generating = ref(false);
const abortController = ref<AbortController | null>(null);
const aiStatus = ref<'idle' | 'connecting' | 'thinking' | 'replying'>('idle');
const autoScroll = ref(true);
const sidebarOpen = ref(true);

const exampleQuestions = [
  '哪块板的功耗最高?',
  'A001板的温度怎么样?',
  '现在有哪些告警?',
  '哪些板是离线状态?',
  '把A001的电机打开',
  '帮我分析最近的温度趋势',
];

const STORAGE_KEY = 'bearpi-ai-sessions';
let msgCounter = 0;
const nextId = () => `msg-${Date.now()}-${++msgCounter}`;
const newSessionId = () => `sess-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

// ── Computed ──────────────────────────────────────────────────
const currentSession = computed(() =>
  sessions.value.find((s) => s.id === currentSessionId.value) ?? sessions.value[0]
);
const messages = computed(() => currentSession.value?.messages ?? []);
const queueLength = computed(() => queue.value.length);
const canSend = computed(() => input.value.trim().length > 0);

const statusLabel = computed(() => {
  switch (aiStatus.value) {
    case 'connecting': return '正在连接模型';
    case 'thinking': return 'AI正在思考';
    case 'replying': return 'AI正在回复';
    default: return '';
  }
});

const formattedStatus = computed(() => {
  const dots = '.'.repeat((Date.now() / 500 | 0) % 4);
  return statusLabel.value ? `${statusLabel.value}${dots}` : '';
});

// ── Session Management ────────────────────────────────────────
function loadSessions() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) sessions.value = JSON.parse(raw);
  } catch { /* ignore */ }
  if (!sessions.value.length) createSession();
  if (!currentSessionId.value) currentSessionId.value = sessions.value[0].id;
}

function saveSessions() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions.value));
  } catch { /* ignore */ }
}

function createSession() {
  const session: ChatSession = {
    id: newSessionId(),
    title: '新对话',
    messages: [],
    createdAt: Date.now(),
    updatedAt: Date.now(),
  };
  sessions.value.unshift(session);
  currentSessionId.value = session.id;
  saveSessions();
}

function switchSession(id: string) {
  currentSessionId.value = id;
}

function deleteSession(id: string) {
  const index = sessions.value.findIndex((s) => s.id === id);
  if (index < 0) return;
  sessions.value.splice(index, 1);
  if (!sessions.value.length) createSession();
  if (currentSessionId.value === id) currentSessionId.value = sessions.value[0].id;
  saveSessions();
}

function autoTitle(session: ChatSession) {
  const firstUser = session.messages.find((m) => m.role === 'user');
  if (firstUser) session.title = firstUser.content.slice(0, 20) + (firstUser.content.length > 20 ? '...' : '');
}

// ── History Builder ───────────────────────────────────────────
function buildHistory(): Array<{ role: string; content: string }> {
  return messages.value
    .filter((msg) => msg.status === 'done' && (msg.role === 'user' || msg.role === 'assistant'))
    .map((msg) => ({ role: msg.role, content: msg.content }));
}

function buildContextPrefix(): string {
  const recent = messages.value
    .filter((msg) => msg.status === 'done')
    .slice(-6)
    .map((msg) => `${msg.role === 'user' ? '用户' : 'AI'}: ${msg.content.slice(0, 200)}`)
    .join('\n');
  return recent ? `基于当前对话上下文:\n${recent}\n\n请回答:\n` : '';
}

// ── Scroll ────────────────────────────────────────────────────
function scrollToBottom(force = false) {
  nextTick(() => {
    if (!chatBody.value) return;
    if (force || autoScroll.value) {
      chatBody.value.scrollTop = chatBody.value.scrollHeight;
    }
  });
}

function onScroll() {
  if (!chatBody.value) return;
  const { scrollTop, scrollHeight, clientHeight } = chatBody.value;
  autoScroll.value = scrollHeight - scrollTop - clientHeight < 80;
}

// ── Keyboard ──────────────────────────────────────────────────
function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey && !event.ctrlKey && !event.metaKey) {
    event.preventDefault();
    sendMessage();
  } else if (event.key === 'Enter' && event.ctrlKey) {
    event.preventDefault();
    sendMessage(true);
  }
}

// ── Send / Queue ──────────────────────────────────────────────
function sendMessage(withContext = false) {
  const question = input.value.trim();
  if (!question || !currentSession.value) return;

  if (generating.value) {
    queue.value.push(question);
    currentSession.value.messages.push({
      id: nextId(), role: 'user', content: question, ts: Date.now(), status: 'queued',
    });
    input.value = '';
    scrollToBottom(true);
    return;
  }

  const historyPrefix = withContext ? buildContextPrefix() : '';
  const fullQuestion = historyPrefix + question;
  const msgIndex = currentSession.value.messages.length;

  currentSession.value.messages.push({
    id: nextId(), role: 'user', content: question, ts: Date.now(), status: 'done',
  });
  autoTitle(currentSession.value);
  saveSessions();
  input.value = '';
  scrollToBottom(true);

  if (looksLikeCommand(question)) {
    void detectAndShowCommand(msgIndex);
  } else {
    processQuestion(fullQuestion);
  }
}

// ── AI Processing ─────────────────────────────────────────────
async function processQuestion(question: string) {
  if (!currentSession.value) return;
  generating.value = true;
  aiStatus.value = 'connecting';

  const assistantMsg: ChatMessage = {
    id: nextId(), role: 'assistant', content: '', ts: Date.now(), status: 'generating',
  };
  currentSession.value.messages.push(assistantMsg);
  scrollToBottom(true);

  const controller = new AbortController();
  abortController.value = controller;

  try {
    aiStatus.value = 'thinking';
    const history = buildHistory();
    const result = await sendAiQuery(question, history) as {
      reply: string; error?: string; data_source?: string; diagnostic?: Record<string, unknown>;
    };
    if (controller.signal.aborted) return;

    aiStatus.value = 'replying';
    assistantMsg.content = result.reply;
    assistantMsg.dataSource = result.data_source;
    assistantMsg.diagnostic = result.diagnostic ?? null;
    assistantMsg.status = 'done';
    saveSessions();
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
    scrollToBottom(true);
    if (queue.value.length > 0) {
      const next = queue.value.shift()!;
      const queuedMsg = currentSession.value.messages.find((m) => m.status === 'queued');
      if (queuedMsg) queuedMsg.status = 'done';
      await nextTick();
      processQuestion(next);
    }
  }
}

// ── Command Detection ─────────────────────────────────────────
const commandKeywords = ['打开', '关闭', '关掉', '开', '关', 'on', 'off', 'auto', '自动', '电机', '灯', '补光灯', '风扇', '通风'];

function looksLikeCommand(text: string): boolean {
  const lower = text.toLowerCase();
  return commandKeywords.some((kw) => lower.includes(kw)) && /[aA]\d{3}|槽位\d+|bearpi/i.test(text);
}

async function detectAndShowCommand(msgIndex: number) {
  if (!currentSession.value) return;
  const userMsg = currentSession.value.messages[msgIndex];
  if (!userMsg || userMsg.role !== 'user') return;

  const cmdMsg: ChatMessage = {
    id: nextId(), role: 'assistant', content: '正在解析指令...', ts: Date.now(), status: 'done', commandStatus: 'confirming',
  };
  currentSession.value.messages.splice(msgIndex + 1, 0, cmdMsg);
  scrollToBottom(true);

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
  scrollToBottom(true);
}

async function executeCommand(msgIndex: number) {
  if (!currentSession.value) return;
  const cmdMsg = currentSession.value.messages[msgIndex];
  if (!cmdMsg?.command?.device_id) return;
  cmdMsg.commandStatus = 'executing';
  cmdMsg.content = '正在执行指令...';
  try {
    const { device_id, actuator, mode } = cmdMsg.command;
    const paramKey = actuator === 'motor' ? 'motor_override' : 'light_override';
    const params: Record<string, string | number | boolean> = {};
    params[paramKey] = mode ?? 'on';
    await sendCommand(device_id!, { type: 'set_param', params });
    cmdMsg.commandStatus = 'executed';
    const actLabel = actuator === 'motor' ? '电机' : '补光灯';
    const modeLabel = mode === 'on' ? '打开' : mode === 'off' ? '关闭' : '自动';
    cmdMsg.content = `指令已下发: ${cmdMsg.command.device_sn} ${actLabel} ${modeLabel}`;
    ElMessage.success('指令已下发');
  } catch (cause) {
    cmdMsg.commandStatus = 'error';
    cmdMsg.content = `指令执行失败: ${cause instanceof Error ? cause.message : '未知错误'}`;
  }
  scrollToBottom(true);
}

function rejectCommand(msgIndex: number) {
  if (!currentSession.value) return;
  const cmdMsg = currentSession.value.messages[msgIndex];
  if (cmdMsg) { cmdMsg.commandStatus = 'rejected'; cmdMsg.content = '已取消执行'; }
}

// ── Stop / Regenerate / Edit ──────────────────────────────────
function stopGeneration() {
  abortController.value?.abort();
  generating.value = false;
  aiStatus.value = 'idle';
  if (!currentSession.value) return;
  const last = currentSession.value.messages[currentSession.value.messages.length - 1];
  if (last?.role === 'assistant' && last.status === 'generating') {
    last.content = last.content || '已停止生成';
    last.status = 'done';
    last.content += '\n\n*[已停止]*';
  }
  queue.value = [];
  currentSession.value.messages.forEach((m) => { if (m.status === 'queued') m.status = 'done'; });
}

function regenerate(index: number) {
  if (!currentSession.value) return;
  const msg = currentSession.value.messages[index];
  if (!msg || msg.role !== 'assistant') return;
  let questionIndex = -1;
  for (let i = index - 1; i >= 0; i--) {
    if (currentSession.value.messages[i].role === 'user') { questionIndex = i; break; }
  }
  if (questionIndex < 0) return;
  const question = currentSession.value.messages[questionIndex].content;
  currentSession.value.messages.splice(index, 1);
  if (!generating.value) processQuestion(question);
  else queue.value.push(question);
}

function startEdit(index: number) {
  if (!currentSession.value) return;
  currentSession.value.messages[index].editing = true;
}

function confirmEdit(index: number, newContent: string) {
  if (!currentSession.value) return;
  const msg = currentSession.value.messages[index];
  if (!msg) return;
  msg.content = newContent;
  msg.editing = false;
  currentSession.value.messages.splice(index + 1);
  if (!generating.value) processQuestion(newContent);
  else queue.value.push(newContent);
}

function cancelEdit(index: number) {
  if (!currentSession.value) return;
  const msg = currentSession.value.messages[index];
  if (msg) msg.editing = false;
}

// ── Message Actions ───────────────────────────────────────────
function copyMessage(content: string) {
  navigator.clipboard.writeText(content).then(() => ElMessage.success('已复制'));
}

function reactMessage(index: number, reaction: 'up' | 'down') {
  if (!currentSession.value) return;
  const msg = currentSession.value.messages[index];
  if (msg) msg.reaction = msg.reaction === reaction ? null : reaction;
}

// ── Utils ─────────────────────────────────────────────────────
function useExample(question: string) {
  input.value = question;
  sendMessage();
}

function open() {
  visible.value = true;
  loadSessions();
  nextTick(() => textareaRef.value?.focus());
}

function clearChat() {
  if (!currentSession.value) return;
  currentSession.value.messages = [];
  queue.value = [];
  if (generating.value) stopGeneration();
  saveSessions();
}

function formatTime(ts: number): string {
  const d = new Date(ts);
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;
}

function formatDiagnostic(diag: Record<string, unknown>): string {
  const parts: string[] = [];
  if (diag.upstream_status) parts.push(`HTTP ${diag.upstream_status}`);
  if (diag.model) parts.push(`模型: ${diag.model}`);
  if (diag.url_host) parts.push(`Host: ${diag.url_host}`);
  if (diag.reason) parts.push(diag.reason as string);
  return parts.join(' | ');
}

function autoResizeTextarea() {
  const el = textareaRef.value;
  if (!el) return;
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

onBeforeUnmount(() => { if (generating.value) stopGeneration(); });
watch(visible, (val) => { if (val) { loadSessions(); nextTick(() => textareaRef.value?.focus()); } });
watch(input, () => nextTick(autoResizeTextarea));
</script>

<template>
  <el-button type="primary" plain @click="open">
    <ChatLineSquare :size="16" />
    AI问答
  </el-button>

  <el-dialog
    v-model="visible"
    title="AI智能问答"
    width="min(900px, 96vw)"
    append-to-body
    :close-on-click-modal="!generating"
    :z-index="9999"
    lock-scroll
    destroy-on-close
  >
    <div class="ai-workspace">
      <!-- Session Sidebar -->
      <aside class="session-sidebar" :class="{ collapsed: !sidebarOpen }">
        <div class="sidebar-header">
          <button class="new-session-btn" @click="createSession">
            <Plus :size="14" />
            <span>新建会话</span>
          </button>
        </div>
        <div class="session-list">
          <div
            v-for="session in sessions"
            :key="session.id"
            class="session-item"
            :class="{ active: session.id === currentSessionId }"
            @click="switchSession(session.id)"
          >
            <span class="session-title">{{ session.title }}</span>
            <button class="session-delete" @click.stop="deleteSession(session.id)" title="删除">
              <Delete :size="12" />
            </button>
          </div>
        </div>
      </aside>

      <!-- Chat Area -->
      <div class="chat-area">
        <!-- Status Bar -->
        <div v-if="generating || queueLength > 0" class="status-bar">
          <div v-if="generating" class="status-item generating">
            <el-icon class="is-loading"><Loading /></el-icon>
            <span>{{ formattedStatus }}</span>
            <button class="stop-btn" @click="stopGeneration">
              <VideoPause :size="13" />
              停止生成
            </button>
          </div>
          <div v-if="queueLength > 0" class="status-item queued">
            <span>队列中: {{ queueLength }} 条</span>
          </div>
        </div>

        <!-- Messages -->
        <div ref="chatBody" class="chat-body" @scroll="onScroll">
          <!-- Welcome -->
          <div v-if="messages.length === 0" class="welcome-card">
            <div class="welcome-icon">
              <ChatLineSquare :size="32" />
            </div>
            <h3>实验室AI助手</h3>
            <p>我可以帮助您:</p>
            <div class="welcome-features">
              <span>查询设备状态</span>
              <span>查看传感器数据</span>
              <span>分析异常告警</span>
              <span>查询历史日志</span>
              <span>控制实验设备</span>
              <span>智能数据分析</span>
            </div>
            <div class="example-grid">
              <button
                v-for="q in exampleQuestions"
                :key="q"
                class="example-btn"
                @click="useExample(q)"
              >
                {{ q }}
              </button>
            </div>
          </div>

          <!-- Message List -->
          <div
            v-for="(msg, index) in messages"
            :key="msg.id"
            :class="['message-row', msg.role, `status-${msg.status}`]"
          >
            <!-- User Message -->
            <template v-if="msg.role === 'user'">
              <div class="user-bubble-wrap">
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
                  <div class="user-bubble">
                    <pre>{{ msg.content }}</pre>
                  </div>
                  <div class="user-actions">
                    <span class="msg-time">{{ formatTime(msg.ts) }}</span>
                    <button class="action-btn" title="编辑" @click="startEdit(index)">
                      <Edit :size="11" />
                    </button>
                  </div>
                </template>
              </div>
            </template>

            <!-- Assistant Message -->
            <template v-else>
              <div class="assistant-bubble-wrap">
                <!-- Command Card -->
                <template v-if="msg.commandStatus">
                  <div class="command-card" :class="`cmd-${msg.commandStatus}`">
                    <div class="cmd-icon">
                      <el-icon v-if="msg.commandStatus === 'confirming' || msg.commandStatus === 'executing'" class="is-loading"><Loading /></el-icon>
                      <CircleCheck v-else-if="msg.commandStatus === 'executed'" :size="18" />
                      <VideoPause v-else :size="18" />
                    </div>
                    <div class="cmd-body">
                      <template v-if="msg.command?.detected && msg.commandStatus === 'confirming'">
                        <strong>设备控制指令</strong>
                        <span>设备: {{ msg.command.device_sn }} (槽位{{ msg.command.slot_no }})</span>
                        <span>执行器: {{ msg.command.actuator === 'motor' ? '电机' : '补光灯' }}</span>
                        <span>动作: {{ msg.command.mode === 'on' ? '打开' : msg.command.mode === 'off' ? '关闭' : '自动' }}</span>
                        <div class="cmd-actions">
                          <button class="cmd-confirm" @click="executeCommand(index)">确认执行</button>
                          <button class="cmd-reject" @click="rejectCommand(index)">取消</button>
                        </div>
                      </template>
                      <template v-else>
                        <span>{{ msg.content }}</span>
                      </template>
                    </div>
                  </div>
                </template>

                <!-- Normal AI Response -->
                <template v-else>
                  <div v-if="msg.status === 'generating' && !msg.content" class="typing-indicator">
                    <span class="dot"></span><span class="dot"></span><span class="dot"></span>
                    <span class="typing-text">{{ formattedStatus || '思考中' }}</span>
                  </div>
                  <template v-else>
                    <div class="ai-bubble">
                      <MarkdownMessage :content="msg.content" :data-source="msg.dataSource" />
                      <details v-if="msg.diagnostic" class="diagnostic-details">
                        <summary>调试信息</summary>
                        <pre class="diagnostic-pre">{{ formatDiagnostic(msg.diagnostic) }}</pre>
                      </details>
                    </div>
                    <!-- AI Message Actions -->
                    <div class="ai-actions">
                      <span class="msg-time">{{ formatTime(msg.ts) }}</span>
                      <button class="action-btn" :class="{ active: msg.reaction === 'up' }" title="有帮助" @click="reactMessage(index, 'up')">👍</button>
                      <button class="action-btn" :class="{ active: msg.reaction === 'down' }" title="没帮助" @click="reactMessage(index, 'down')">👎</button>
                      <button class="action-btn" title="复制" @click="copyMessage(msg.content)">
                        <CopyDocument :size="12" />
                      </button>
                      <button v-if="msg.status === 'done' || msg.status === 'error'" class="action-btn" title="重新生成" @click="regenerate(index)">
                        <Refresh :size="12" />
                      </button>
                    </div>
                  </template>
                </template>
              </div>
            </template>
          </div>
        </div>

        <!-- Scroll to bottom -->
        <button v-if="!autoScroll" class="scroll-bottom-btn" @click="scrollToBottom(true)">
          <Bottom :size="16" />
        </button>

        <!-- Input Area -->
        <div class="input-area">
          <div class="input-row">
            <textarea
              ref="textareaRef"
              v-model="input"
              class="chat-textarea"
              placeholder="输入问题..."
              rows="1"
              @keydown="handleKeydown"
            />
            <button
              class="send-btn"
              :disabled="!canSend"
              @click="sendMessage()"
            >
              <Top :size="16" />
              <span>发送</span>
            </button>
          </div>
          <div class="input-hints">
            <span>Enter 发送</span>
            <span>Shift+Enter 换行</span>
            <span>Ctrl+Enter 引用上下文</span>
          </div>
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<style scoped>
/* ── Workspace Layout ─────────────────────────────────────────── */
.ai-workspace {
  display: flex;
  height: min(75vh, 640px);
  gap: 0;
  overflow: hidden;
  border-radius: 8px;
}

/* ── Session Sidebar ──────────────────────────────────────────── */
.session-sidebar {
  width: 200px;
  border-right: 1px solid var(--border);
  background: rgba(10, 14, 20, 0.6);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.session-sidebar.collapsed { width: 0; overflow: hidden; }

.sidebar-header {
  padding: 12px;
  border-bottom: 1px solid var(--border);
}

.new-session-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 8px 12px;
  border: 1px dashed var(--border);
  border-radius: 6px;
  background: transparent;
  color: var(--text-muted);
  font-size: 13px;
  cursor: pointer;
  transition: all 150ms ease;
}

.new-session-btn:hover {
  border-color: var(--cyan);
  color: var(--cyan);
  background: rgba(56, 189, 248, 0.04);
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.session-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 150ms ease;
}

.session-item:hover { background: rgba(255, 255, 255, 0.03); }
.session-item.active { background: rgba(56, 189, 248, 0.08); border: 1px solid rgba(56, 189, 248, 0.15); }

.session-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  color: var(--text-muted);
}

.session-item.active .session-title { color: var(--text); }

.session-delete {
  display: none;
  padding: 2px;
  border: none;
  background: transparent;
  color: var(--text-subtle);
  cursor: pointer;
  border-radius: 4px;
  transition: all 150ms ease;
}

.session-item:hover .session-delete { display: flex; }
.session-delete:hover { color: var(--red); background: rgba(255, 104, 116, 0.1); }

/* ── Chat Area ────────────────────────────────────────────────── */
.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  position: relative;
}

/* ── Status Bar ───────────────────────────────────────────────── */
.status-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 14px;
  border-bottom: 1px solid var(--border);
  background: rgba(56, 189, 248, 0.03);
  font-size: 12px;
}

.status-item { display: flex; align-items: center; gap: 6px; }
.status-item.generating { color: var(--cyan); }
.status-item.queued { color: var(--amber); }

.stop-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
  padding: 3px 10px;
  border: 1px solid rgba(255, 104, 116, 0.3);
  border-radius: 5px;
  background: rgba(255, 104, 116, 0.06);
  color: var(--red);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 150ms ease;
}

.stop-btn:hover { background: rgba(255, 104, 116, 0.12); border-color: rgba(255, 104, 116, 0.5); }

/* ── Chat Body ────────────────────────────────────────────────── */
.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ── Welcome Card ─────────────────────────────────────────────── */
.welcome-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 32px 24px;
  gap: 12px;
}

.welcome-icon {
  display: grid;
  place-items: center;
  width: 56px;
  height: 56px;
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(56, 189, 248, 0.12), rgba(45, 212, 125, 0.08));
  color: var(--cyan);
  margin-bottom: 4px;
}

.welcome-card h3 { margin: 0; font-size: 18px; color: var(--text); }
.welcome-card p { margin: 0; color: var(--text-muted); font-size: 14px; }

.welcome-features {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: center;
  margin: 8px 0;
}

.welcome-features span {
  padding: 4px 10px;
  border: 1px solid var(--border);
  border-radius: 999px;
  font-size: 12px;
  color: var(--text-muted);
  background: rgba(255, 255, 255, 0.02);
}

.example-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: center;
  margin-top: 8px;
}

.example-btn {
  padding: 6px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--panel);
  color: var(--text-muted);
  font-size: 13px;
  cursor: pointer;
  transition: all 150ms ease;
}

.example-btn:hover {
  border-color: var(--cyan);
  color: var(--cyan);
  background: rgba(56, 189, 248, 0.04);
}

/* ── Message Rows ─────────────────────────────────────────────── */
.message-row { display: flex; }
.message-row.user { justify-content: flex-end; }
.message-row.assistant { justify-content: flex-start; }

/* ── User Bubble ──────────────────────────────────────────────── */
.user-bubble-wrap { display: flex; flex-direction: column; align-items: flex-end; max-width: 65%; }

.user-bubble {
  padding: 10px 16px;
  border-radius: 16px 16px 4px 16px;
  background: var(--cyan);
  color: #061018;
  max-width: 100%;
}

.user-bubble pre {
  margin: 0;
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.55;
  color: #061018;
}

.user-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 4px;
  opacity: 0;
  transition: opacity 150ms ease;
}

.message-row.user:hover .user-actions { opacity: 1; }

/* ── Assistant Bubble ─────────────────────────────────────────── */
.assistant-bubble-wrap { display: flex; flex-direction: column; max-width: 720px; }

.ai-bubble {
  padding: 12px 16px;
  border-radius: 16px 16px 16px 4px;
  background: var(--panel-soft);
  border: 1px solid var(--border);
  color: var(--text);
  line-height: 1.65;
  font-size: 14px;
}

/* ── Typing Indicator ─────────────────────────────────────────── */
.typing-indicator {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 12px 16px;
  border-radius: 16px 16px 16px 4px;
  background: var(--panel-soft);
  border: 1px solid var(--border);
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-muted);
  animation: dotBounce 1.4s ease-in-out infinite;
}

.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes dotBounce {
  0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
  40% { opacity: 1; transform: scale(1); }
}

.typing-text { margin-left: 6px; color: var(--text-muted); font-size: 13px; }

/* ── Message Actions ──────────────────────────────────────────── */
.ai-actions, .user-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 4px;
}

.ai-actions { opacity: 0; transition: opacity 150ms ease; }
.message-row.assistant:hover .ai-actions { opacity: 1; }

.msg-time {
  font-size: 11px;
  color: var(--text-subtle);
  margin-right: 4px;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--text-subtle);
  cursor: pointer;
  transition: all 150ms ease;
  font-size: 12px;
}

.action-btn:hover { background: rgba(255, 255, 255, 0.05); color: var(--text); }
.action-btn.active { color: var(--cyan); background: rgba(56, 189, 248, 0.08); }

/* ── Command Card ─────────────────────────────────────────────── */
.command-card {
  display: flex;
  gap: 10px;
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--panel-soft);
}

.cmd-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  flex-shrink: 0;
}

.cmd-confirming .cmd-icon { background: rgba(56, 189, 248, 0.1); color: var(--cyan); }
.cmd-executing .cmd-icon { background: rgba(246, 184, 75, 0.1); color: var(--amber); }
.cmd-executed .cmd-icon { background: rgba(45, 212, 125, 0.1); color: var(--green); }
.cmd-rejected .cmd-icon, .cmd-error .cmd-icon { background: rgba(255, 104, 116, 0.1); color: var(--red); }

.cmd-body { flex: 1; display: flex; flex-direction: column; gap: 3px; font-size: 13px; }
.cmd-body strong { color: var(--text); font-size: 13px; }
.cmd-body span { color: var(--text-muted); font-size: 12px; }

.cmd-actions { display: flex; gap: 8px; margin-top: 8px; }

.cmd-confirm {
  padding: 5px 14px;
  border: 1px solid rgba(45, 212, 125, 0.4);
  border-radius: 6px;
  background: rgba(45, 212, 125, 0.1);
  color: var(--green);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 150ms ease;
}

.cmd-confirm:hover { background: rgba(45, 212, 125, 0.18); border-color: rgba(45, 212, 125, 0.6); }

.cmd-reject {
  padding: 5px 14px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: transparent;
  color: var(--text-muted);
  font-size: 12px;
  cursor: pointer;
  transition: all 150ms ease;
}

.cmd-reject:hover { border-color: var(--border-strong); color: var(--text); }

.cmd-confirming { border-color: rgba(56, 189, 248, 0.15); }
.cmd-executing { border-color: rgba(246, 184, 75, 0.15); }
.cmd-executed { border-color: rgba(45, 212, 125, 0.15); }
.cmd-rejected, .cmd-error { border-color: rgba(255, 104, 116, 0.1); opacity: 0.7; }

/* ── Edit Area ────────────────────────────────────────────────── */
.edit-area { display: flex; flex-direction: column; gap: 6px; width: 100%; }

.edit-textarea {
  width: 100%;
  min-height: 50px;
  padding: 8px 10px;
  border: 1px solid var(--cyan);
  border-radius: 8px;
  background: rgba(5, 12, 18, 0.6);
  color: var(--text);
  font-size: 14px;
  font-family: inherit;
  resize: vertical;
}

.edit-textarea:focus { outline: none; box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.12); }

.edit-actions { display: flex; gap: 6px; }

.edit-confirm, .edit-cancel {
  padding: 4px 12px;
  border: 1px solid var(--border);
  border-radius: 5px;
  font-size: 12px;
  cursor: pointer;
  transition: all 150ms ease;
}

.edit-confirm { background: var(--cyan); border-color: var(--cyan); color: #061018; font-weight: 600; }
.edit-cancel { background: transparent; color: var(--text-muted); }

/* ── Diagnostic ───────────────────────────────────────────────── */
.diagnostic-details { margin-top: 8px; padding-top: 8px; border-top: 1px dashed var(--border); }
.diagnostic-details summary { cursor: pointer; color: var(--amber); font-size: 11px; font-weight: 700; }

.diagnostic-pre {
  margin-top: 4px;
  padding: 6px;
  background: rgba(246, 184, 75, 0.06);
  border-radius: 5px;
  color: var(--amber);
  font-size: 11px;
  line-height: 1.4;
}

/* ── Scroll to Bottom ─────────────────────────────────────────── */
.scroll-bottom-btn {
  position: absolute;
  bottom: 120px;
  right: 20px;
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border: 1px solid var(--border);
  border-radius: 50%;
  background: var(--panel);
  color: var(--text-muted);
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
  transition: all 150ms ease;
  z-index: 5;
}

.scroll-bottom-btn:hover { border-color: var(--cyan); color: var(--cyan); }

/* ── Input Area ───────────────────────────────────────────────── */
.input-area {
  padding: 12px 16px;
  border-top: 1px solid var(--border);
  background: rgba(10, 14, 20, 0.4);
}

.input-row {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}

.chat-textarea {
  flex: 1;
  min-height: 40px;
  max-height: 120px;
  padding: 10px 14px;
  border: 1px solid var(--border);
  border-radius: 10px;
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
  border-color: rgba(56, 189, 248, 0.35);
  box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.06);
}

.chat-textarea::placeholder { color: var(--text-subtle); }

.send-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  min-width: 72px;
  height: 40px;
  padding: 0 14px;
  border: 1px solid rgba(56, 189, 248, 0.3);
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(56, 189, 248, 0.12), rgba(45, 212, 125, 0.08));
  color: #e0f2fe;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 200ms cubic-bezier(0.25, 1, 0.5, 1);
  white-space: nowrap;
}

.send-btn:hover:not(:disabled) {
  background: linear-gradient(135deg, rgba(56, 189, 248, 0.2), rgba(45, 212, 125, 0.14));
  border-color: rgba(56, 189, 248, 0.5);
  box-shadow: 0 0 10px rgba(56, 189, 248, 0.12);
  transform: translateY(-1px);
}

.send-btn:active:not(:disabled) { transform: translateY(0); }

.send-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
  border-color: rgba(56, 189, 248, 0.08);
  background: rgba(17, 26, 34, 0.4);
  color: var(--text-subtle);
}

.input-hints {
  display: flex;
  gap: 12px;
  margin-top: 6px;
  font-size: 11px;
  color: var(--text-subtle);
}

/* ── Responsive ───────────────────────────────────────────────── */
@media (max-width: 640px) {
  .session-sidebar { width: 0; overflow: hidden; }
  .user-bubble-wrap { max-width: 85%; }
  .assistant-bubble-wrap { max-width: 100%; }
  .send-btn { min-width: 56px; height: 36px; font-size: 13px; }
  .input-hints { display: none; }
}
</style>
