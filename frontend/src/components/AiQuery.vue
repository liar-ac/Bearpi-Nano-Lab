<script setup lang="ts">
import {
  ChatLineSquare, Loading, Promotion, Refresh, Edit, VideoPause,
  Delete, CopyDocument, CircleCheck, Close, Plus
} from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import MarkdownMessage from '@/components/MarkdownMessage.vue';
import { sendAiQuery, parseAiCommand, sendCommand, sendBulkCommand, type AiCommandResult } from '@/api/lab';
import { useAuthStore } from '@/stores/auth';

const auth = useAuthStore();

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
  commandStatus?: 'confirming' | 'executing' | 'executed' | 'rejected' | 'error';
  reaction?: 'up' | 'down' | null;
}

interface ChatSession {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: number;
  updatedAt: number;
}

const visible = ref(false);
const input = ref('');
const textareaRef = ref<HTMLTextAreaElement | null>(null);
const chatBody = ref<HTMLDivElement | null>(null);
const sessions = ref<ChatSession[]>([]);
const currentSessionId = ref('');
const queue = ref<string[]>([]);
const generating = ref(false);
const abortController = ref<AbortController | null>(null);
const aiStatus = ref<'idle' | 'connecting' | 'thinking' | 'replying'>('idle');
const inputFocused = ref(false);

const examples = [
  '查询设备状态',
  '查看告警信息',
  '分析传感器数据',
  '控制实验设备',
];

const STORAGE_KEY = 'bearpi-ai-sessions';
let msgCounter = 0;
const nextId = () => `m-${Date.now()}-${++msgCounter}`;
const newSid = () => `s-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;

const currentSession = computed(() =>
  sessions.value.find((s) => s.id === currentSessionId.value) ?? sessions.value[0]
);
const msgs = computed(() => currentSession.value?.messages ?? []);
const queueLen = computed(() => queue.value.length);
const canSend = computed(() => input.value.trim().length > 0);
const showScrollBtn = ref(false);

const statusText = computed(() => {
  const dots = '.'.repeat((Date.now() / 600 | 0) % 4);
  if (aiStatus.value === 'connecting') return `连接中${dots}`;
  if (aiStatus.value === 'thinking') return `思考中${dots}`;
  if (aiStatus.value === 'replying') return `回复中${dots}`;
  return '';
});

// ── Sessions ──────────────────────────────────────────────────
function load() {
  try { sessions.value = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]'); } catch { /* */ }
  if (!sessions.value.length) create();
  if (!currentSessionId.value) currentSessionId.value = sessions.value[0].id;
}

function save() {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions.value)); } catch { /* */ }
}

function create() {
  const num = sessions.value.length + 1;
  const s: ChatSession = { id: newSid(), title: `未命名对话 #${num}`, messages: [], createdAt: Date.now(), updatedAt: Date.now() };
  sessions.value.unshift(s);
  currentSessionId.value = s.id;
  save();
}

const renamingId = ref('');
const renameValue = ref('');

function switchTo(id: string) { currentSessionId.value = id; }

async function remove(id: string) {
  const s = sessions.value.find((s) => s.id === id);
  if (!s) return;
  try {
    await ElMessageBox.confirm(`删除「${s.title}」？`, '删除会话', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' });
  } catch { return; }
  const i = sessions.value.findIndex((s) => s.id === id);
  if (i < 0) return;
  sessions.value.splice(i, 1);
  if (!sessions.value.length) create();
  if (currentSessionId.value === id) currentSessionId.value = sessions.value[0].id;
  save();
}

function startRename(id: string) {
  const s = sessions.value.find((s) => s.id === id);
  if (!s) return;
  renamingId.value = id;
  renameValue.value = s.title;
  nextTick(() => {
    const el = document.querySelector('.rename-input') as HTMLInputElement;
    el?.focus();
    el?.select();
  });
}

function confirmRename() {
  const s = sessions.value.find((s) => s.id === renamingId.value);
  if (s && renameValue.value.trim()) s.title = renameValue.value.trim();
  renamingId.value = '';
  renameValue.value = '';
  save();
}

function cancelRename() { renamingId.value = ''; renameValue.value = ''; }

function onRenameKey(e: KeyboardEvent) {
  if (e.key === 'Enter') { e.preventDefault(); confirmRename(); }
  else if (e.key === 'Escape') { e.preventDefault(); cancelRename(); }
}

function autoTitle(s: ChatSession) {
  const first = s.messages.find((m) => m.role === 'user');
  if (first) s.title = first.content.slice(0, 18) + (first.content.length > 18 ? '…' : '');
}

// ── History ───────────────────────────────────────────────────
function buildHistory() {
  return msgs.value.filter((m) => m.status === 'done').map((m) => ({ role: m.role, content: m.content }));
}

function ctxPrefix() {
  const r = msgs.value.filter((m) => m.status === 'done').slice(-6)
    .map((m) => `${m.role === 'user' ? '用户' : 'AI'}: ${m.content.slice(0, 200)}`).join('\n');
  return r ? `基于当前对话上下文:\n${r}\n\n请回答:\n` : '';
}

// ── Scroll ────────────────────────────────────────────────────
function isNearBottom(): boolean {
  if (!chatBody.value) return true;
  const { scrollTop, scrollHeight, clientHeight } = chatBody.value;
  if (clientHeight === 0) return true;
  return scrollHeight - scrollTop - clientHeight < 120;
}

let wasNearBottom = true;

function snapshotScroll() {
  wasNearBottom = isNearBottom();
}

function scrollDown(force = false) {
  nextTick(() => {
    requestAnimationFrame(() => {
      if (!chatBody.value) return;
      const el = chatBody.value;
      if (force || wasNearBottom) {
        el.scrollTop = el.scrollHeight;
        showScrollBtn.value = false;
      } else {
        showScrollBtn.value = true;
      }
      wasNearBottom = true;
    });
  });
}

function onScroll() {
  showScrollBtn.value = !isNearBottom();
}

// ── Keyboard ──────────────────────────────────────────────────
function onKey(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.metaKey) { e.preventDefault(); send(); }
  else if (e.key === 'Enter' && e.ctrlKey) { e.preventDefault(); send(true); }
}

// ── Send ──────────────────────────────────────────────────────
function send(withCtx = false) {
  const q = input.value.trim();
  if (!q || !currentSession.value) return;
  snapshotScroll();
  if (generating.value) {
    queue.value.push(q);
    currentSession.value.messages.push({ id: nextId(), role: 'user', content: q, ts: Date.now(), status: 'queued' });
    input.value = ''; scrollDown(true); return;
  }
  const full = (withCtx ? ctxPrefix() : '') + q;
  const idx = currentSession.value.messages.length;
  currentSession.value.messages.push({ id: nextId(), role: 'user', content: q, ts: Date.now(), status: 'done' });
  autoTitle(currentSession.value); save(); input.value = ''; scrollDown(true);
  if (looksCmd(q)) void detectCmd(idx); else ask(full);
}

// ── AI ────────────────────────────────────────────────────────
async function ask(question: string) {
  if (!currentSession.value) return;
  generating.value = true; aiStatus.value = 'connecting';
  const msg: ChatMessage = { id: nextId(), role: 'assistant', content: '', ts: Date.now(), status: 'generating' };
  snapshotScroll();
  currentSession.value.messages.push(msg); scrollDown(true);
  const ctrl = new AbortController(); abortController.value = ctrl;
  try {
    aiStatus.value = 'thinking';
    const r = await sendAiQuery(question, buildHistory(), ctrl.signal) as { reply: string; data_source?: string; diagnostic?: Record<string, unknown> };
    if (ctrl.signal.aborted) return;
    aiStatus.value = 'replying';
    msg.content = r.reply; msg.dataSource = r.data_source; msg.diagnostic = r.diagnostic ?? null; msg.status = 'done'; save();
  } catch (e) {
    if (ctrl.signal.aborted) return;
    msg.content = `请求失败: ${e instanceof Error ? e.message : '未知错误'}`; msg.status = 'error'; ElMessage.error(msg.content);
  } finally {
    if (abortController.value === ctrl) { abortController.value = null; generating.value = false; aiStatus.value = 'idle'; }
    scrollDown();
    if (!generating.value && queue.value.length) { const n = queue.value.shift()!; const qm = currentSession.value.messages.find((m) => m.status === 'queued'); if (qm) qm.status = 'done'; await nextTick(); ask(n); }
  }
}

// ── Command ───────────────────────────────────────────────────
const cmdKw = ['打开', '关闭', '关掉', '开', '关', 'on', 'off', 'auto', '自动', '电机', '灯', '补光灯', '风扇'];
const bulkKw = ['所有', '全部', '全部的', '所有的', '每个', '全都'];
function looksCmd(t: string) {
  if (!cmdKw.some((k) => t.includes(k))) return false;
  return /[aA]\d{3}|槽位\d+|bearpi|所有|全部|全都|每个/i.test(t);
}

function parseBulkIntent(text: string): { actuator: 'motor' | 'light'; mode: 'auto' | 'on' | 'off' } | null {
  const t = text.toLowerCase();
  let actuator: 'motor' | 'light' | null = null;
  let mode: 'auto' | 'on' | 'off' | null = null;
  if (/(电机|风扇|通风|motor)/.test(t)) actuator = 'motor';
  else if (/(灯|补光|照明|light)/.test(t)) actuator = 'light';
  if (/(打开|开|开启|点亮|on)/.test(t)) mode = 'on';
  else if (/(关闭|关|关掉|熄灭|off)/.test(t)) mode = 'off';
  else if (/(自动|auto)/.test(t)) mode = 'auto';
  return actuator && mode ? { actuator, mode } : null;
}

async function detectCmd(idx: number) {
  if (!currentSession.value) return;
  const user = currentSession.value.messages[idx]; if (!user) return;
  const isBulk = bulkKw.some((k) => user.content.includes(k));
  const cmd: ChatMessage = { id: nextId(), role: 'assistant', content: '正在解析指令…', ts: Date.now(), status: 'done', commandStatus: 'confirming' };
  snapshotScroll();
  currentSession.value.messages.splice(idx + 1, 0, cmd); scrollDown();
  try {
    if (isBulk) {
      const intent = parseBulkIntent(user.content);
      if (intent) {
        const al = intent.actuator === 'motor' ? '电机' : '补光灯';
        const ml = intent.mode === 'on' ? '打开' : intent.mode === 'off' ? '关闭' : '自动';
        cmd.content = `检测到批量控制指令: ${al} ${ml}（全部设备）`;
        cmd.command = { detected: true, actuator: intent.actuator, mode: intent.mode, device_sn: '全部设备', explanation: `批量${al}${ml}` } as AiCommandResult & { _bulk: boolean };
        (cmd.command as unknown as Record<string, boolean>)._bulk = true;
      } else {
        cmd.content = '未识别为设备控制指令';
        cmd.commandStatus = 'rejected';
      }
    } else {
      const r = await parseAiCommand(user.content);
      cmd.command = r;
      if (r.detected && r.device_id) { cmd.content = `检测到控制指令: ${r.explanation || ''}`; }
      else { cmd.content = r.explanation || '未识别为设备控制指令'; cmd.commandStatus = 'rejected'; cmd.command = undefined; }
    }
  } catch { cmd.content = '指令解析失败'; cmd.commandStatus = 'error'; }
  scrollDown();
}

async function execCmd(idx: number) {
  if (!auth.canCommand) {
    ElMessage.warning('当前角色无权下发指令');
    return;
  }
  if (!currentSession.value) return;
  const cmd = currentSession.value.messages[idx]; if (!cmd?.command) return;
  snapshotScroll();
  cmd.commandStatus = 'executing'; cmd.content = '正在执行…';
  try {
    const { actuator, mode } = cmd.command;
    const isBulk = (cmd.command as unknown as Record<string, boolean>)._bulk;
    if (isBulk) {
      await sendBulkCommand({ target: 'all', actuator: actuator as 'motor' | 'light', mode: (mode as 'auto' | 'on' | 'off') ?? 'on' });
      const al = actuator === 'motor' ? '电机' : '补光灯';
      const ml = mode === 'on' ? '打开' : mode === 'off' ? '关闭' : '自动';
      cmd.commandStatus = 'executed';
      cmd.content = `已批量下发: 全部设备 ${al} ${ml}`;
      ElMessage.success('批量指令已下发');
    } else {
      if (!cmd.command.device_id) return;
      const pk = actuator === 'motor' ? 'motor_override' : 'light_override';
      const p: Record<string, string | number | boolean> = {}; p[pk] = mode ?? 'on';
      await sendCommand(cmd.command.device_id, { type: 'set_param', params: p });
      cmd.commandStatus = 'executed';
      const al = actuator === 'motor' ? '电机' : '补光灯';
      const ml = mode === 'on' ? '打开' : mode === 'off' ? '关闭' : '自动';
      cmd.content = `已下发: ${cmd.command.device_sn} ${al} ${ml}`;
      ElMessage.success('指令已下发');
    }
  } catch (e) { cmd.commandStatus = 'error'; cmd.content = `执行失败: ${e instanceof Error ? e.message : '未知错误'}`; }
  scrollDown();
}

function rejectCmd(idx: number) { if (currentSession.value) { const m = currentSession.value.messages[idx]; if (m) { m.commandStatus = 'rejected'; m.content = '已取消'; } } }

// ── Actions ───────────────────────────────────────────────────
function stop() {
  abortController.value?.abort(); generating.value = false; aiStatus.value = 'idle';
  if (!currentSession.value) return;
  snapshotScroll();
  const last = currentSession.value.messages[currentSession.value.messages.length - 1];
  if (last?.role === 'assistant' && last.status === 'generating') { last.content = (last.content || '') + '\n\n*[已停止]*'; last.status = 'done'; }
  queue.value = [];
}

function regen(idx: number) {
  if (!currentSession.value) return;
  const m = currentSession.value.messages[idx]; if (!m || m.role !== 'assistant') return;
  let qi = -1; for (let i = idx - 1; i >= 0; i--) { if (currentSession.value.messages[i].role === 'user') { qi = i; break; } }
  if (qi < 0) return;
  const q = currentSession.value.messages[qi].content;
  snapshotScroll();
  currentSession.value.messages.splice(idx, 1);
  if (!generating.value) ask(q); else queue.value.push(q);
}

function editStart(i: number) { if (currentSession.value) currentSession.value.messages[i].editing = true; }
function editOk(i: number, v: string) {
  if (!currentSession.value) return; const m = currentSession.value.messages[i]; if (!m) return;
  m.content = v; m.editing = false; currentSession.value.messages.splice(i + 1);
  if (!generating.value) ask(v); else queue.value.push(v);
}
function editCancel(i: number) { if (currentSession.value) currentSession.value.messages[i].editing = false; }

function copy(t: string) { navigator.clipboard.writeText(t).then(() => ElMessage.success('已复制')); }
function react(i: number, r: 'up' | 'down') { if (currentSession.value) { const m = currentSession.value.messages[i]; if (m) m.reaction = m.reaction === r ? null : r; } }

function useExample(q: string) {
  input.value = q;
  nextTick(() => send());
}
function open() { visible.value = true; load(); nextTick(() => textareaRef.value?.focus()); }
function clear() { if (currentSession.value) { currentSession.value.messages = []; queue.value = []; if (generating.value) stop(); save(); } }
function fmtTime(ts: number) { const d = new Date(ts); return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`; }
function autoH() { const el = textareaRef.value; if (el) { el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, 120) + 'px'; } }

function onGlobalKey(e: KeyboardEvent) {
  if (!visible.value) return;
  if ((e.ctrlKey || e.metaKey) && e.key === 'n') { e.preventDefault(); create(); }
  if (e.key === 'Delete' && !inputFocused.value && renamingId.value === '') {
    const s = currentSession.value;
    if (s) void remove(s.id);
  }
}

onBeforeUnmount(() => { if (generating.value) stop(); window.removeEventListener('keydown', onGlobalKey); });
watch(visible, (v) => {
  if (v) { load(); nextTick(() => textareaRef.value?.focus()); window.addEventListener('keydown', onGlobalKey); }
  else { window.removeEventListener('keydown', onGlobalKey); }
});
watch(input, () => nextTick(autoH));
</script>

<template>
  <el-button type="primary" plain @click="open">
    <ChatLineSquare :size="16" /> AI问答
  </el-button>

  <el-dialog v-model="visible" class="ai-dialog" :show-close="false" width="min(980px, 96vw)" append-to-body :close-on-click-modal="!generating" :z-index="9999" lock-scroll destroy-on-close>
    <div class="ws">
      <!-- Sidebar -->
      <aside class="side">
        <div class="side-head">
          <div class="window-dots" aria-hidden="true"><span></span><span></span><span></span></div>
          <button class="side-new" type="button" @click="create" title="新建对话(Ctrl+N)"><Plus :size="13" /><span>新建对话</span></button>
        </div>
        <div class="side-list">
          <div
            v-for="s in sessions"
            :key="s.id"
            class="side-item"
            :class="{ active: s.id === currentSessionId, renaming: s.id === renamingId }"
            @click="switchTo(s.id)"
          >
            <template v-if="s.id === renamingId">
              <input
                class="rename-input"
                v-model="renameValue"
                @keydown="onRenameKey"
                @blur="confirmRename"
                @click.stop
              />
            </template>
            <template v-else>
              <span class="side-title">{{ s.title }}</span>
              <div class="side-actions">
                <button class="side-btn" type="button" title="重命名" @click.stop="startRename(s.id)"><Edit :size="12" /></button>
                <button class="side-btn" type="button" title="删除" @click.stop="remove(s.id)"><Delete :size="12" /></button>
              </div>
            </template>
          </div>
        </div>
      </aside>

      <!-- Chat -->
      <div class="chat">
        <!-- Header -->
        <div class="head">
          <div class="head-main">
            <span class="head-title">实验室AI助手</span>
            <span v-if="currentSession" class="head-sub">{{ currentSession.title }}</span>
          </div>
          <div class="head-actions">
            <button v-if="msgs.length" class="head-btn" type="button" title="清空对话" @click="clear"><Delete :size="14" /></button>
            <button class="head-btn" type="button" title="关闭" @click="visible = false"><Close :size="15" /></button>
          </div>
        </div>

        <!-- Status -->
        <div v-if="generating || queueLen > 0" class="status-bar">
          <span v-if="generating" class="status-text"><Loading :size="14" class="spin" /> {{ statusText || '思考中' }}</span>
          <span v-if="queueLen > 0" class="queue-text">队列{{ queueLen }}</span>
          <button v-if="generating" class="stop-btn" type="button" @click="stop"><VideoPause :size="13" />停止</button>
        </div>

        <!-- Messages -->
        <div ref="chatBody" class="body" @scroll="onScroll">
          <!-- Welcome -->
          <div v-if="!msgs.length" class="welcome">
            <p class="welcome-greeting">您好，我是实验室AI助手</p>
            <p class="welcome-sub">今天想了解什么？</p>
            <div class="welcome-cards">
              <button v-for="e in examples" :key="e" class="welcome-card" @click="useExample(e)">{{ e }}</button>
            </div>
          </div>

          <!-- Messages -->
          <div v-for="(msg, idx) in msgs" :key="msg.id" :class="['row', msg.role]">
            <!-- User -->
            <template v-if="msg.role === 'user'">
              <div class="u-wrap">
                <div v-if="msg.editing" class="edit-box">
                  <textarea :value="msg.content" class="edit-ta" @keydown.enter.exact.prevent="editOk(idx, ($event.target as HTMLTextAreaElement).value)" @keydown.esc.prevent="editCancel(idx)" />
                  <div class="edit-btns"><button class="btn-ok" @click="editOk(idx, ($event.target as HTMLElement).closest('.edit-box')?.querySelector('textarea')?.value ?? msg.content)">确认</button><button class="btn-no" @click="editCancel(idx)">取消</button></div>
                </div>
                <template v-else>
                  <div class="u-bubble"><pre>{{ msg.content }}</pre></div>
                  <div class="u-bar"><span class="ts">{{ fmtTime(msg.ts) }}</span><button class="act" @click="editStart(idx)"><Edit :size="11" /></button></div>
                </template>
              </div>
            </template>

            <!-- Assistant -->
            <template v-else>
              <div class="a-wrap">
                <!-- Command -->
                <template v-if="msg.commandStatus">
                  <div class="cmd" :class="`cmd-${msg.commandStatus}`">
                    <span class="cmd-icon"><CircleCheck v-if="msg.commandStatus==='executed'" :size="16" /><Loading v-else-if="msg.commandStatus==='executing'" :size="16" class="spin" /><VideoPause v-else :size="16" /></span>
                    <div class="cmd-body">
                      <template v-if="msg.command?.detected && msg.commandStatus==='confirming'">
                        <b>控制指令</b>
                        <span>{{ msg.command.device_sn }} · {{ msg.command.actuator==='motor'?'电机':'补光灯' }} · {{ msg.command.mode==='on'?'打开':msg.command.mode==='off'?'关闭':'自动' }}</span>
                        <div class="cmd-btns"><button class="cmd-go" @click="execCmd(idx)">确认执行</button><button class="cmd-no" @click="rejectCmd(idx)">取消</button></div>
                      </template>
                      <template v-else><span>{{ msg.content }}</span></template>
                    </div>
                  </div>
                </template>

                <!-- Normal -->
                <template v-else>
                  <div v-if="msg.status==='generating' && !msg.content" class="typing"><span class="dot"></span><span class="dot"></span><span class="dot"></span><span class="typing-lbl">{{ statusText || '思考中' }}</span></div>
                  <template v-else>
                    <div class="a-bubble">
                      <MarkdownMessage :content="msg.content" :data-source="msg.dataSource" />
                      <details v-if="msg.diagnostic" class="diag"><summary>调试</summary><pre class="diag-pre">{{ JSON.stringify(msg.diagnostic, null, 2) }}</pre></details>
                    </div>
                    <div class="a-bar">
                      <span class="ts">{{ fmtTime(msg.ts) }}</span>
                      <button class="act" :class="{ on: msg.reaction==='up' }" @click="react(idx,'up')">👍</button>
                      <button class="act" :class="{ on: msg.reaction==='down' }" @click="react(idx,'down')">👎</button>
                      <button class="act" @click="copy(msg.content)"><CopyDocument :size="12" /></button>
                      <button v-if="msg.status==='done'||msg.status==='error'" class="act" @click="regen(idx)"><Refresh :size="12" /></button>
                    </div>
                  </template>
                </template>
              </div>
            </template>
          </div>
        </div>

        <!-- Scroll btn -->
        <button v-if="showScrollBtn" class="scroll-btn" @click="scrollDown(true)">↓</button>

        <!-- Input -->
        <div class="input-area" :class="{ focused: inputFocused }">
          <div class="input-frame">
            <textarea
              ref="textareaRef"
              v-model="input"
              class="ta"
              placeholder="给实验室助手发送消息…"
              rows="1"
              @keydown="onKey"
              @focus="inputFocused = true"
              @blur="inputFocused = false"
            />
            <button class="send" type="button" title="发送" :disabled="!canSend" @click="send()">
              <Promotion :size="15" />
              <span>发送</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<style scoped>
:global(.ai-dialog.el-dialog) {
  padding: 0;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.52) !important;
  border-radius: 18px !important;
  background: #f6f7f9 !important;
  box-shadow:
    0 30px 90px rgba(0, 0, 0, 0.42),
    0 0 0 1px rgba(0, 0, 0, 0.04),
    0 1px 0 rgba(255, 255, 255, 0.78) inset !important;
}

:global(.ai-dialog .el-dialog__header) {
  display: none;
}

:global(.ai-dialog .el-dialog__body) {
  padding: 0 !important;
  overflow: hidden;
}

.ws {
  --text: #1d2430;
  --text-muted: #667085;
  --text-subtle: #98a2b3;
  --border: #dde3eb;
  --border-strong: #c8d0da;
  --cyan: #0a84ff;
  --green: #34c759;
  --amber: #ff9f0a;
  --red: #ff453a;
  display: grid;
  grid-template-columns: 238px minmax(0, 1fr);
  height: min(82vh, 720px);
  min-height: 560px;
  overflow: hidden;
  color: var(--text);
  background: #f7f8fa;
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
  letter-spacing: 0;
}

.side {
  display: flex;
  flex-direction: column;
  min-width: 0;
  border-right: 1px solid rgba(0, 0, 0, 0.08);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.72), rgba(241, 244, 248, 0.78)),
    #eef1f5;
}

.side-head {
  display: grid;
  gap: 14px;
  padding: 14px 14px 10px;
}

.window-dots {
  display: flex;
  gap: 7px;
  height: 12px;
}

.window-dots span {
  width: 11px;
  height: 11px;
  border-radius: 999px;
  box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.06) inset;
}

.window-dots span:nth-child(1) { background: #ff5f57; }
.window-dots span:nth-child(2) { background: #febc2e; }
.window-dots span:nth-child(3) { background: #28c840; }

.side-new {
  display: inline-flex;
  align-items: center;
  justify-content: flex-start;
  gap: 6px;
  width: 100%;
  min-width: 132px;
  height: 32px;
  padding: 0 12px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.72);
  color: #344054;
  box-sizing: border-box;
  font-size: 12px;
  font-weight: 600;
  line-height: 1;
  white-space: nowrap;
  box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
  transition: background 160ms ease, border-color 160ms ease, color 160ms ease, transform 160ms ease;
}

.side-new :deep(svg) {
  flex: 0 0 13px;
  width: 13px;
  height: 13px;
}

.side-new:hover {
  transform: translateY(-1px);
  border-color: rgba(10, 132, 255, 0.26);
  background: #ffffff;
  color: #0a84ff;
  box-shadow: 0 6px 14px rgba(16, 24, 40, 0.08);
}

.side-list {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 3px;
  min-height: 0;
  padding: 0 10px 12px;
  overflow-y: auto;
}

.side-item {
  display: flex;
  align-items: center;
  gap: 6px;
  min-height: 34px;
  padding: 0 8px;
  border: 1px solid transparent;
  border-radius: 9px;
  color: #667085;
  cursor: pointer;
  transition: background 150ms ease, border-color 150ms ease, color 150ms ease;
}

.side-item:hover {
  background: rgba(255, 255, 255, 0.58);
  color: #344054;
}

.side-item.active {
  border-color: rgba(10, 132, 255, 0.18);
  background: rgba(255, 255, 255, 0.86);
  color: #101828;
  box-shadow: 0 1px 2px rgba(16, 24, 40, 0.05);
}

.side-item.renaming {
  background: rgba(255, 255, 255, 0.78);
}

.side-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  color: inherit;
  font-size: 13px;
  line-height: 1.25;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rename-input {
  flex: 1;
  min-width: 0;
  height: 26px;
  padding: 0 7px;
  border: 1px solid rgba(10, 132, 255, 0.28);
  border-radius: 7px;
  outline: none;
  background: #ffffff;
  color: #101828;
  font-size: 13px;
  font-family: inherit;
}

.rename-input:focus {
  border-color: rgba(10, 132, 255, 0.7);
  box-shadow: 0 0 0 3px rgba(10, 132, 255, 0.1);
}

.side-actions {
  display: flex;
  flex-shrink: 0;
  gap: 2px;
  opacity: 0;
  transition: opacity 150ms ease;
}

.side-item:hover .side-actions,
.side-item.active .side-actions {
  opacity: 1;
}

.side-btn,
.head-btn,
.act {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: var(--text-subtle);
  transition: background 150ms ease, color 150ms ease, transform 150ms ease;
}

.side-btn {
  width: 24px;
  height: 24px;
  border-radius: 7px;
}

.side-btn:hover,
.act:hover {
  background: rgba(16, 24, 40, 0.06);
  color: #344054;
}

.side-btn:last-child:hover {
  color: var(--red);
  background: rgba(255, 69, 58, 0.1);
}

.chat {
  position: relative;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  background: #fbfcfd;
}

.head {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  height: 58px;
  padding: 0 22px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.07);
  background: rgba(255, 255, 255, 0.74);
  backdrop-filter: blur(18px) saturate(1.25);
  -webkit-backdrop-filter: blur(18px) saturate(1.25);
}

.head-main {
  display: grid;
  min-width: 0;
  gap: 2px;
}

.head-title {
  color: #101828;
  font-size: 14px;
  font-weight: 700;
  line-height: 1.2;
}

.head-sub {
  overflow: hidden;
  color: #98a2b3;
  font-size: 12px;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.head-actions {
  display: flex;
  flex-shrink: 0;
  gap: 6px;
}

.head-btn {
  width: 30px;
  height: 30px;
  border-radius: 9px;
}

.head-btn:hover {
  transform: translateY(-1px);
  background: rgba(16, 24, 40, 0.06);
  color: #344054;
}

.status-bar {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  gap: 10px;
  min-height: 38px;
  padding: 0 22px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  background: rgba(247, 248, 250, 0.78);
  color: #667085;
  font-size: 12px;
}

.status-text,
.stop-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}

.queue-text {
  color: var(--amber);
  white-space: nowrap;
}

.stop-btn {
  margin-left: auto;
  min-height: 28px;
  padding: 0 10px;
  border: 1px solid rgba(255, 69, 58, 0.18);
  border-radius: 8px;
  background: rgba(255, 69, 58, 0.08);
  color: var(--red);
  font-size: 12px;
  font-weight: 600;
}

.stop-btn:hover {
  border-color: rgba(255, 69, 58, 0.28);
  background: rgba(255, 69, 58, 0.12);
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.body {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 18px;
  min-height: 0;
  padding: 24px 28px;
  overflow-y: auto;
  background:
    linear-gradient(180deg, #fbfcfd 0%, #f7f8fa 100%);
}

.welcome {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 320px;
  text-align: center;
}

.welcome-greeting {
  margin: 0;
  color: #101828;
  font-size: 21px;
  font-weight: 750;
  line-height: 1.25;
}

.welcome-sub {
  margin: 0;
  color: #667085;
  font-size: 14px;
}

.welcome-cards {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
  max-width: 460px;
  margin-top: 18px;
}

.welcome-card {
  min-height: 34px;
  padding: 0 13px;
  border: 1px solid #d8dee8;
  border-radius: 999px;
  background: #ffffff;
  color: #344054;
  font-size: 13px;
  box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
  transition: border-color 150ms ease, background 150ms ease, color 150ms ease, transform 150ms ease;
}

.welcome-card:hover {
  transform: translateY(-1px);
  border-color: rgba(10, 132, 255, 0.32);
  color: #0a84ff;
}

.row {
  display: flex;
}

.row.user {
  justify-content: flex-end;
}

.row.assistant {
  justify-content: flex-start;
}

.u-wrap,
.a-wrap {
  display: flex;
  flex-direction: column;
}

.u-wrap {
  align-items: flex-end;
  max-width: min(70%, 560px);
}

.a-wrap {
  max-width: min(76%, 680px);
}

.u-bubble,
.a-bubble,
.cmd,
.typing {
  box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
}

.u-bubble {
  padding: 10px 14px;
  border-radius: 18px 18px 6px 18px;
  background: #0a84ff;
  color: #ffffff;
}

.u-bubble pre {
  margin: 0;
  color: #ffffff;
  font-size: 14px;
  font-family: inherit;
  line-height: 1.55;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
  word-break: break-word;
}

.a-bubble {
  padding: 13px 15px;
  border: 1px solid #e5e9f0;
  border-radius: 18px 18px 18px 6px;
  background: #ffffff;
  color: #253040;
  font-size: 14px;
  line-height: 1.68;
}

.u-bar,
.a-bar {
  display: flex;
  align-items: center;
  gap: 3px;
  margin-top: 5px;
  opacity: 0;
  transition: opacity 150ms ease;
}

.row.user:hover .u-bar,
.row.assistant:hover .a-bar {
  opacity: 1;
}

.ts {
  margin-right: 4px;
  color: #98a2b3;
  font-size: 11px;
}

.act {
  width: 26px;
  height: 26px;
  border-radius: 8px;
  font-size: 11px;
}

.act.on {
  color: #0a84ff;
  background: rgba(10, 132, 255, 0.08);
}

.typing {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  width: fit-content;
  padding: 10px 13px;
  border: 1px solid #e5e9f0;
  border-radius: 999px;
  background: #ffffff;
}

.dot {
  width: 5px;
  height: 5px;
  border-radius: 999px;
  background: #98a2b3;
  animation: bounce 1.4s ease-in-out infinite;
}

.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes bounce {
  0%, 80%, 100% { opacity: 0.28; transform: translateY(0); }
  40% { opacity: 1; transform: translateY(-2px); }
}

.typing-lbl {
  margin-left: 6px;
  color: #667085;
  font-size: 13px;
}

.cmd {
  display: flex;
  gap: 10px;
  padding: 12px;
  border: 1px solid #e5e9f0;
  border-radius: 14px;
  background: #ffffff;
}

.cmd-icon {
  display: flex;
  flex: 0 0 30px;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 9px;
  background: rgba(10, 132, 255, 0.08);
}

.cmd-confirming .cmd-icon { color: var(--cyan); }
.cmd-executing .cmd-icon { color: var(--amber); }
.cmd-executed .cmd-icon { color: var(--green); }
.cmd-rejected .cmd-icon,
.cmd-error .cmd-icon {
  color: var(--red);
  background: rgba(255, 69, 58, 0.08);
}

.cmd-body {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
  font-size: 13px;
}

.cmd-body b {
  color: #101828;
  font-weight: 700;
}

.cmd-body span {
  color: #667085;
  font-size: 12px;
  line-height: 1.45;
}

.cmd-btns {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.cmd-go,
.cmd-no,
.btn-ok,
.btn-no {
  min-height: 28px;
  padding: 0 11px;
  border: none;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 650;
}

.cmd-go,
.btn-ok {
  background: #0a84ff;
  color: #ffffff;
}

.cmd-go:hover,
.btn-ok:hover {
  background: #0071e3;
}

.cmd-no,
.btn-no {
  background: rgba(16, 24, 40, 0.06);
  color: #475467;
}

.cmd-no:hover,
.btn-no:hover {
  background: rgba(16, 24, 40, 0.1);
}

.edit-box {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: min(560px, 100%);
}

.edit-ta {
  width: 100%;
  min-height: 72px;
  padding: 10px 12px;
  border: 1px solid #d8dee8;
  border-radius: 12px;
  outline: none;
  background: #ffffff;
  color: #101828;
  font-size: 14px;
  font-family: inherit;
  line-height: 1.55;
  resize: vertical;
}

.edit-ta:focus {
  border-color: rgba(10, 132, 255, 0.62);
  box-shadow: 0 0 0 3px rgba(10, 132, 255, 0.1);
}

.edit-btns {
  display: flex;
  gap: 6px;
}

.diag {
  margin-top: 9px;
}

.diag summary {
  cursor: pointer;
  color: #98a2b3;
  font-size: 11px;
}

.diag-pre {
  margin-top: 6px;
  padding: 9px;
  border-radius: 9px;
  background: #f2f4f7;
  color: #667085;
  font-size: 11px;
  line-height: 1.45;
  white-space: pre-wrap;
}

.scroll-btn {
  position: absolute;
  right: 24px;
  bottom: 92px;
  z-index: 5;
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border: 1px solid #d8dee8;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.92);
  color: #667085;
  box-shadow: 0 8px 20px rgba(16, 24, 40, 0.12);
  transition: transform 150ms ease, color 150ms ease, border-color 150ms ease;
}

.scroll-btn:hover {
  transform: translateY(-1px);
  border-color: rgba(10, 132, 255, 0.32);
  color: #0a84ff;
}

.input-area {
  flex-shrink: 0;
  padding: 15px 24px 18px;
  border-top: 1px solid rgba(0, 0, 0, 0.07);
  background: rgba(247, 248, 250, 0.94);
}

.input-frame {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  width: 100%;
  padding: 5px 5px 5px 15px;
  border: 1px solid #d8dee8;
  border-radius: 15px;
  background: #ffffff;
  box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
  transition: border-color 160ms ease, box-shadow 160ms ease;
}

.input-area .ta {
  flex: 1;
  width: auto;
  min-height: 50px;
  max-height: 118px;
  padding: 10px 0;
  border: none;
  outline: none;
  background: transparent;
  color: #101828;
  font-size: 14px;
  font-family: inherit;
  line-height: 1.5;
  resize: none;
}

.input-area.focused .input-frame {
  border-color: rgba(10, 132, 255, 0.62);
  box-shadow: 0 0 0 3px rgba(10, 132, 255, 0.1), 0 1px 2px rgba(16, 24, 40, 0.04);
}

.input-area .ta::placeholder {
  color: #98a2b3;
}

.send {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-width: 82px;
  height: 40px;
  padding: 0 14px;
  border: none;
  border-radius: 12px;
  background: #0a84ff;
  color: #ffffff;
  font-size: 13px;
  font-weight: 700;
  line-height: 1;
  white-space: nowrap;
  box-shadow: 0 8px 18px rgba(10, 132, 255, 0.22);
  transition: background 150ms ease, transform 150ms ease, opacity 150ms ease;
}

.send :deep(svg) {
  flex: 0 0 15px;
  width: 15px;
  height: 15px;
}

.send:hover:not(:disabled) {
  transform: translateY(-1px);
  background: #0071e3;
}

.send:disabled {
  opacity: 0.28;
  box-shadow: none;
}

@media (max-width: 700px) {
  :global(.ai-dialog.el-dialog) {
    width: 96vw !important;
  }

  .ws {
    grid-template-columns: 1fr;
    grid-template-rows: auto minmax(0, 1fr);
    height: 86vh;
    min-height: 0;
  }

  .side {
    width: 100%;
    max-height: 118px;
    border-right: none;
    border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  }

  .side-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 12px 12px 8px;
  }

  .side-new {
    width: auto;
    min-width: 118px;
    justify-content: center;
  }

  .side-list {
    flex-direction: row;
    gap: 6px;
    padding: 0 12px 10px;
    overflow-x: auto;
    overflow-y: hidden;
  }

  .side-item {
    flex: 0 0 min(190px, 64vw);
  }

  .chat {
    min-height: 0;
  }

  .head {
    height: 54px;
    padding: 0 16px;
  }

  .body {
    padding: 18px 16px;
  }

  .status-bar {
    padding: 0 16px;
  }

  .u-wrap,
  .a-wrap {
    max-width: 90%;
  }

  .input-area {
    padding: 12px 14px 14px;
  }

  .send {
    min-width: 74px;
    height: 38px;
    padding: 0 12px;
  }
}
</style>
