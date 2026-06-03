<script setup lang="ts">
import {
  ChatLineSquare, Loading, Promotion, Refresh, Edit, VideoPause,
  Delete, CopyDocument, CircleCheck
} from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import MarkdownMessage from '@/components/MarkdownMessage.vue';
import { sendAiQuery, parseAiCommand, sendCommand, type AiCommandResult } from '@/api/lab';

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
const autoScroll = ref(true);
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
function scrollDown(force = false) {
  nextTick(() => { if (chatBody.value && (force || autoScroll.value)) chatBody.value.scrollTop = chatBody.value.scrollHeight; });
}

function onScroll() {
  if (!chatBody.value) return;
  const { scrollTop, scrollHeight, clientHeight } = chatBody.value;
  autoScroll.value = scrollHeight - scrollTop - clientHeight < 60;
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
  currentSession.value.messages.push(msg); scrollDown(true);
  const ctrl = new AbortController(); abortController.value = ctrl;
  try {
    aiStatus.value = 'thinking';
    const r = await sendAiQuery(question, buildHistory()) as { reply: string; data_source?: string; diagnostic?: Record<string, unknown> };
    if (ctrl.signal.aborted) return;
    aiStatus.value = 'replying';
    msg.content = r.reply; msg.dataSource = r.data_source; msg.diagnostic = r.diagnostic ?? null; msg.status = 'done'; save();
  } catch (e) {
    if (ctrl.signal.aborted) return;
    msg.content = `请求失败: ${e instanceof Error ? e.message : '未知错误'}`; msg.status = 'error'; ElMessage.error(msg.content);
  } finally {
    abortController.value = null; generating.value = false; aiStatus.value = 'idle'; scrollDown(true);
    if (queue.value.length) { const n = queue.value.shift()!; const qm = currentSession.value.messages.find((m) => m.status === 'queued'); if (qm) qm.status = 'done'; await nextTick(); ask(n); }
  }
}

// ── Command ───────────────────────────────────────────────────
const cmdKw = ['打开', '关闭', '关掉', '开', '关', 'on', 'off', 'auto', '自动', '电机', '灯', '补光灯', '风扇'];
function looksCmd(t: string) { return cmdKw.some((k) => t.includes(k)) && /[aA]\d{3}|槽位\d+|bearpi/i.test(t); }

async function detectCmd(idx: number) {
  if (!currentSession.value) return;
  const user = currentSession.value.messages[idx]; if (!user) return;
  const cmd: ChatMessage = { id: nextId(), role: 'assistant', content: '正在解析指令…', ts: Date.now(), status: 'done', commandStatus: 'confirming' };
  currentSession.value.messages.splice(idx + 1, 0, cmd); scrollDown(true);
  try {
    const r = await parseAiCommand(user.content);
    cmd.command = r;
    if (r.detected && r.device_id) { cmd.content = `检测到控制指令: ${r.explanation || ''}`; }
    else { cmd.content = r.explanation || '未识别为设备控制指令'; cmd.commandStatus = 'rejected'; cmd.command = undefined; }
  } catch { cmd.content = '指令解析失败'; cmd.commandStatus = 'error'; }
  scrollDown(true);
}

async function execCmd(idx: number) {
  if (!currentSession.value) return;
  const cmd = currentSession.value.messages[idx]; if (!cmd?.command?.device_id) return;
  cmd.commandStatus = 'executing'; cmd.content = '正在执行…';
  try {
    const { device_id, actuator, mode } = cmd.command;
    const pk = actuator === 'motor' ? 'motor_override' : 'light_override';
    const p: Record<string, string | number | boolean> = {}; p[pk] = mode ?? 'on';
    await sendCommand(device_id!, { type: 'set_param', params: p });
    cmd.commandStatus = 'executed';
    const al = actuator === 'motor' ? '电机' : '补光灯';
    const ml = mode === 'on' ? '打开' : mode === 'off' ? '关闭' : '自动';
    cmd.content = `已下发: ${cmd.command.device_sn} ${al} ${ml}`; ElMessage.success('指令已下发');
  } catch (e) { cmd.commandStatus = 'error'; cmd.content = `执行失败: ${e instanceof Error ? e.message : '未知错误'}`; }
  scrollDown(true);
}

function rejectCmd(idx: number) { if (currentSession.value) { const m = currentSession.value.messages[idx]; if (m) { m.commandStatus = 'rejected'; m.content = '已取消'; } } }

// ── Actions ───────────────────────────────────────────────────
function stop() {
  abortController.value?.abort(); generating.value = false; aiStatus.value = 'idle';
  if (!currentSession.value) return;
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

function useExample(q: string) { input.value = q; send(); }
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

  <el-dialog v-model="visible" :show-close="false" width="min(880px, 96vw)" append-to-body :close-on-click-modal="!generating" :z-index="9999" lock-scroll destroy-on-close>
    <div class="ws">
      <!-- Sidebar -->
      <aside class="side">
        <button class="side-new" @click="create" title="新建对话 (Ctrl+N)"><span class="side-new-icon" aria-hidden="true">+</span><span class="side-new-text">新建</span></button>
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
                <button class="side-btn" title="重命名" @click.stop="startRename(s.id)"><Edit :size="11" /></button>
                <button class="side-btn" title="删除" @click.stop="remove(s.id)"><Delete :size="11" /></button>
              </div>
            </template>
          </div>
        </div>
      </aside>

      <!-- Chat -->
      <div class="chat">
        <!-- Header -->
        <div class="head">
          <span class="head-title">实验室AI助手</span>
          <div class="head-actions">
            <button v-if="msgs.length" class="head-btn" @click="clear">清空</button>
            <button class="head-btn" @click="visible = false">关闭</button>
          </div>
        </div>

        <!-- Status -->
        <div v-if="generating || queueLen > 0" class="status-bar">
          <span v-if="generating" class="status-text"><Loading :size="13" class="spin" /> {{ statusText }}</span>
          <span v-if="queueLen > 0" class="queue-text">队列 {{ queueLen }}</span>
          <button v-if="generating" class="stop-btn" @click="stop"><VideoPause :size="12" /> 停止</button>
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
        <button v-if="!autoScroll" class="scroll-btn" @click="scrollDown(true)">↓</button>

        <!-- Input -->
        <div class="input-area" :class="{ focused: inputFocused }">
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
          <button class="send" :disabled="!canSend" @click="send()"><Promotion :size="16" /></button>
          <Transition name="fade">
            <div v-if="inputFocused" class="hints">
              <span>Enter 发送</span><span>Shift+Enter 换行</span><span>Ctrl+Enter 引用上下文</span>
            </div>
          </Transition>
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<style scoped>
/* ── Workspace ──────────────────────────────────────────────── */
.ws { display: flex; height: min(78vh, 660px); border-radius: 8px; overflow: hidden; }

/* ── Sidebar ────────────────────────────────────────────────── */
.side { width: 220px; border-right: 1px solid rgba(255,255,255,0.04); background: rgba(10,14,20,0.5); display: flex; flex-direction: column; flex-shrink: 0; }

.side-new {
  align-self: flex-start; display: inline-flex; align-items: center; justify-content: center; flex: 0 0 auto;
  gap: 3px; box-sizing: border-box; margin: 6px 8px 4px; padding: 0 8px;
  height: 26px; max-width: 74px; min-width: 0; width: auto; border: none; border-radius: 8px;
  background: transparent; color: var(--text-subtle); font-size: 12px; font-weight: 500; line-height: 1;
  white-space: nowrap; overflow: hidden; cursor: pointer; box-shadow: none; transition: color 150ms ease, background 150ms ease;
}
.side-new:hover { color: var(--text); background: rgba(255,255,255,0.04); }
.side-new:focus-visible { outline: 1px solid rgba(148,163,184,0.35); outline-offset: 1px; }
.side-new-icon {
  display: inline-flex; align-items: center; justify-content: center; flex: 0 0 12px;
  width: 12px; height: 12px; font-size: 14px; font-weight: 400; line-height: 10px;
}
.side-new-text { display: inline-block; flex: 0 1 auto; min-width: 0; line-height: 1; }

.side-list { flex: 1; overflow-y: auto; padding: 0 4px 4px; display: flex; flex-direction: column; gap: 1px; }

.side-item {
  display: flex; align-items: center; gap: 4px; padding: 6px 8px; border-radius: 8px;
  cursor: pointer; transition: all 150ms ease; min-height: 32px;
}
.side-item:hover { background: rgba(255,255,255,0.04); }
.side-item.active { background: rgba(255,255,255,0.06); }
.side-item.renaming { background: rgba(255,255,255,0.02); }

.side-title { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; color: var(--text-muted); line-height: 1.3; }
.side-item.active .side-title { color: var(--text); }

.rename-input {
  flex: 1; min-width: 0; padding: 3px 6px; border: 1px solid rgba(56,189,248,0.3); border-radius: 4px;
  background: rgba(5,12,18,0.5); color: var(--text); font-size: 13px; font-family: inherit; outline: none;
}
.rename-input:focus { border-color: rgba(56,189,248,0.5); }

.side-actions { display: flex; gap: 1px; opacity: 0; transition: opacity 150ms ease; flex-shrink: 0; }
.side-item:hover .side-actions { opacity: 1; }

.side-btn {
  display: inline-flex; align-items: center; justify-content: center; width: 22px; height: 22px;
  border: none; border-radius: 4px; background: transparent; color: var(--text-subtle);
  cursor: pointer; transition: all 150ms ease;
}
.side-btn:hover { background: rgba(255,255,255,0.05); color: var(--text); }
.side-btn:last-child:hover { color: var(--red); background: rgba(255,104,116,0.06); }

/* ── Chat ───────────────────────────────────────────────────── */
.chat { flex: 1; display: flex; flex-direction: column; min-width: 0; position: relative; }

.head {
  display: flex; align-items: center; justify-content: space-between; padding: 0 16px; height: 48px;
  border-bottom: 1px solid rgba(255,255,255,0.04); flex-shrink: 0;
}
.head-title { font-size: 14px; font-weight: 600; color: var(--text); }
.head-actions { display: flex; gap: 4px; }
.head-btn { padding: 5px 10px; border: none; border-radius: 6px; background: transparent; color: var(--text-subtle); font-size: 12px; cursor: pointer; transition: all 150ms ease; }
.head-btn:hover { color: var(--text); background: rgba(255,255,255,0.04); }

.status-bar {
  display: flex; align-items: center; gap: 10px; padding: 5px 16px;
  border-bottom: 1px solid rgba(255,255,255,0.03); font-size: 12px; color: var(--text-muted); flex-shrink: 0;
}
.status-text { display: flex; align-items: center; gap: 5px; }
.queue-text { color: var(--amber); }
.stop-btn { margin-left: auto; display: flex; align-items: center; gap: 4px; padding: 3px 10px; border: 1px solid rgba(255,104,116,0.2); border-radius: 5px; background: transparent; color: var(--red); font-size: 12px; cursor: pointer; transition: all 150ms ease; }
.stop-btn:hover { background: rgba(255,104,116,0.06); }

.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* ── Body ───────────────────────────────────────────────────── */
.body { flex: 1; overflow-y: auto; padding: 20px 16px; display: flex; flex-direction: column; gap: 16px; }

/* ── Welcome ────────────────────────────────────────────────── */
.welcome { display: flex; flex-direction: column; align-items: center; text-align: center; padding: 40px 20px; gap: 8px; }
.welcome-greeting { margin: 0; font-size: 20px; font-weight: 600; color: var(--text); }
.welcome-sub { margin: 0; font-size: 14px; color: var(--text-muted); }
.welcome-cards { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-top: 16px; max-width: 360px; }
.welcome-card {
  padding: 12px 16px; border: 1px solid rgba(255,255,255,0.06); border-radius: 10px;
  background: rgba(255,255,255,0.02); color: var(--text-muted); font-size: 13px; cursor: pointer;
  transition: all 150ms ease; text-align: left;
}
.welcome-card:hover { background: rgba(255,255,255,0.04); color: var(--text); border-color: rgba(255,255,255,0.1); }

/* ── Message Rows ───────────────────────────────────────────── */
.row { display: flex; }
.row.user { justify-content: flex-end; }
.row.assistant { justify-content: flex-start; }

/* ── User ───────────────────────────────────────────────────── */
.u-wrap { display: flex; flex-direction: column; align-items: flex-end; max-width: 65%; }

.u-bubble {
  padding: 10px 16px; border-radius: 18px 18px 4px 18px;
  background: var(--cyan); color: #061018;
}
.u-bubble pre { margin: 0; white-space: pre-wrap; word-wrap: break-word; font-family: inherit; font-size: 14px; line-height: 1.55; color: #061018; }

.u-bar { display: flex; align-items: center; gap: 4px; margin-top: 3px; opacity: 0; transition: opacity 150ms ease; }
.row.user:hover .u-bar { opacity: 1; }

/* ── Assistant ──────────────────────────────────────────────── */
.a-wrap { display: flex; flex-direction: column; max-width: 680px; }

.a-bubble {
  padding: 12px 16px; border-radius: 18px 18px 18px 4px;
  background: rgba(255,255,255,0.03); color: var(--text); line-height: 1.65; font-size: 14px;
}

.a-bar { display: flex; align-items: center; gap: 2px; margin-top: 3px; opacity: 0; transition: opacity 150ms ease; }
.row.assistant:hover .a-bar { opacity: 1; }

.ts { font-size: 11px; color: var(--text-subtle); margin-right: 4px; }

.act {
  display: inline-flex; align-items: center; justify-content: center; width: 26px; height: 26px;
  border: none; border-radius: 6px; background: transparent; color: var(--text-subtle); cursor: pointer;
  transition: all 150ms ease; font-size: 11px;
}
.act:hover { background: rgba(255,255,255,0.04); color: var(--text); }
.act.on { color: var(--cyan); }

/* ── Typing ─────────────────────────────────────────────────── */
.typing { display: flex; align-items: center; gap: 3px; padding: 12px 16px; }
.dot { width: 5px; height: 5px; border-radius: 50%; background: var(--text-subtle); animation: bounce 1.4s ease-in-out infinite; }
.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce { 0%,80%,100% { opacity: 0.3; } 40% { opacity: 1; } }
.typing-lbl { margin-left: 5px; color: var(--text-subtle); font-size: 13px; }

/* ── Command ────────────────────────────────────────────────── */
.cmd { display: flex; gap: 8px; padding: 10px 12px; border-radius: 10px; background: rgba(255,255,255,0.02); }
.cmd-icon { display: flex; align-items: center; justify-content: center; width: 28px; height: 28px; border-radius: 6px; flex-shrink: 0; }
.cmd-confirming .cmd-icon { color: var(--cyan); }
.cmd-executing .cmd-icon { color: var(--amber); }
.cmd-executed .cmd-icon { color: var(--green); }
.cmd-rejected .cmd-icon, .cmd-error .cmd-icon { color: var(--red); }
.cmd-body { flex: 1; display: flex; flex-direction: column; gap: 2px; font-size: 13px; }
.cmd-body b { color: var(--text); font-weight: 600; }
.cmd-body span { color: var(--text-muted); font-size: 12px; }
.cmd-btns { display: flex; gap: 6px; margin-top: 6px; }
.cmd-go { padding: 4px 12px; border: none; border-radius: 6px; background: rgba(45,212,125,0.12); color: var(--green); font-size: 12px; font-weight: 600; cursor: pointer; transition: all 150ms ease; }
.cmd-go:hover { background: rgba(45,212,125,0.2); }
.cmd-no { padding: 4px 12px; border: none; border-radius: 6px; background: transparent; color: var(--text-subtle); font-size: 12px; cursor: pointer; }
.cmd-no:hover { color: var(--text); }

/* ── Edit ───────────────────────────────────────────────────── */
.edit-box { display: flex; flex-direction: column; gap: 6px; width: 100%; }
.edit-ta { width: 100%; min-height: 44px; padding: 8px 10px; border: 1px solid rgba(56,189,248,0.3); border-radius: 8px; background: rgba(5,12,18,0.5); color: var(--text); font-size: 14px; font-family: inherit; resize: vertical; }
.edit-ta:focus { outline: none; }
.edit-btns { display: flex; gap: 6px; }
.btn-ok { padding: 4px 12px; border: none; border-radius: 5px; background: var(--cyan); color: #061018; font-size: 12px; font-weight: 600; cursor: pointer; }
.btn-no { padding: 4px 12px; border: none; border-radius: 5px; background: transparent; color: var(--text-subtle); font-size: 12px; cursor: pointer; }

/* ── Diagnostic ─────────────────────────────────────────────── */
.diag { margin-top: 8px; }
.diag summary { cursor: pointer; color: var(--text-subtle); font-size: 11px; }
.diag-pre { margin-top: 4px; padding: 6px; background: rgba(255,255,255,0.02); border-radius: 5px; color: var(--text-subtle); font-size: 11px; line-height: 1.4; white-space: pre-wrap; }

/* ── Scroll Button ──────────────────────────────────────────── */
.scroll-btn {
  position: absolute; bottom: 110px; right: 20px; width: 32px; height: 32px;
  display: grid; place-items: center; border: 1px solid rgba(255,255,255,0.06); border-radius: 50%;
  background: var(--panel); color: var(--text-subtle); cursor: pointer;
  box-shadow: 0 2px 8px rgba(0,0,0,0.2); transition: all 150ms ease; z-index: 5; font-size: 14px;
}
.scroll-btn:hover { color: var(--text); }

/* ── Input ──────────────────────────────────────────────────── */
.input-area {
  padding: 12px 16px; flex-shrink: 0;
  border-top: 1px solid rgba(255,255,255,0.04);
}

.input-area .ta {
  width: 100%; min-height: 56px; max-height: 120px; padding: 14px 48px 14px 16px;
  border: 1px solid rgba(255,255,255,0.06); border-radius: 16px;
  background: rgba(255,255,255,0.03); color: var(--text);
  font-size: 14px; font-family: inherit; line-height: 1.5; resize: none; overflow-y: auto;
  transition: border-color 200ms ease;
}
.input-area.focused .ta { border-color: rgba(255,255,255,0.12); }
.input-area .ta:focus { outline: none; }
.input-area .ta::placeholder { color: var(--text-subtle); }

.send {
  position: absolute; right: 24px; bottom: 20px;
  width: 36px; height: 36px; display: grid; place-items: center;
  border: none; border-radius: 10px;
  background: rgba(56,189,248,0.12); color: var(--cyan);
  cursor: pointer; transition: all 200ms ease;
}
.send:hover { background: rgba(56,189,248,0.2); }
.send:disabled { opacity: 0.3; cursor: not-allowed; }

.hints {
  display: flex; gap: 12px; margin-top: 6px; font-size: 11px; color: var(--text-subtle);
  padding: 0 4px;
}

/* ── Fade ────────────────────────────────────────────────────── */
.fade-enter-active, .fade-leave-active { transition: opacity 200ms ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

/* ── Input area position ─────────────────────────────────────── */
.input-area { position: relative; }

/* ── Responsive ──────────────────────────────────────────────── */
@media (max-width: 640px) {
  .side { width: 0; overflow: hidden; }
  .u-wrap { max-width: 85%; }
  .a-wrap { max-width: 100%; }
  .hints { display: none; }
  .welcome-cards { grid-template-columns: 1fr; }
}
</style>
