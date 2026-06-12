<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import MarkdownMessage from '@/components/MarkdownMessage.vue';
import { sendAiQuery, parseAiCommand, sendCommand, sendBulkCommand } from '@/api/lab';
import type { AiCommandResult } from '@/api/lab';
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

// ── State ──────────────────────────────────────────────────
const visible = ref(false);
const input = ref('');
const sessions = ref<ChatSession[]>([]);
const currentSessionId = ref('');
const queue = ref<string[]>([]);
const generating = ref(false);
const abortController = ref<AbortController | null>(null);
const aiStatus = ref<'idle' | 'connecting' | 'thinking' | 'replying'>('idle');
const statusTick = ref(0);
let statusTimer: ReturnType<typeof setInterval> | null = null;
const showSessionBar = ref(false);
const selectMode = ref(false);
const selectedIds = ref<Set<string>>(new Set());
const renamingId = ref('');
const renameValue = ref('');
const editValue = ref('');
const showScrollBtn = ref(false);
const scrollTarget = ref('');
const scrollTopVal = ref(0);
const scrollHeightVal = ref(0);
const clientHeightVal = ref(0);
const diagExpanded = ref<Set<string>>(new Set());

// ── Constants ──────────────────────────────────────────────
const STORAGE_KEY = 'bearpi-ai-sessions';
let msgCounter = 0;
const nextId = () => `m-${Date.now()}-${++msgCounter}`;
const newSid = () => `s-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;

const examples = [
  '哪块板的功耗最高?',
  'A001板的温度怎么样?',
  '把所有电机打开',
  '关闭全部灯',
];

// ── Computed ────────────────────────────────────────────────
const currentSession = computed(() =>
  sessions.value.find((s) => s.id === currentSessionId.value) ?? sessions.value[0]
);
const msgs = computed(() => currentSession.value?.messages ?? []);
const queueLen = computed(() => queue.value.length);
const canSend = computed(() => input.value.trim().length > 0);

const statusText = computed(() => {
  const dots = '.'.repeat(statusTick.value % 4);
  if (aiStatus.value === 'connecting') return `连接中${dots}`;
  if (aiStatus.value === 'thinking') return `思考中${dots}`;
  if (aiStatus.value === 'replying') return `回复中${dots}`;
  return '';
});

// ── Storage ─────────────────────────────────────────────────
function load() {
  try { sessions.value = JSON.parse(uni.getStorageSync(STORAGE_KEY) || '[]'); } catch { sessions.value = []; }
  sessions.value.forEach((s) => s.messages.forEach((m) => {
    if (m.status === 'generating' || m.status === 'queued') {
      m.status = 'error';
      if (!m.content) m.content = '会话中断';
    }
    if (m.commandStatus === 'executing' || m.commandStatus === 'confirming') m.commandStatus = 'error';
    if (m.editing) m.editing = false;
  }));
  if (!sessions.value.length) create();
  if (!currentSessionId.value) currentSessionId.value = sessions.value[0].id;
}

function save() {
  try { uni.setStorageSync(STORAGE_KEY, JSON.stringify(sessions.value)); } catch { /* */ }
}

// ── Session management ──────────────────────────────────────
function create() {
  const num = sessions.value.length + 1;
  const s: ChatSession = { id: newSid(), title: `未命名对话 #${num}`, messages: [], createdAt: Date.now(), updatedAt: Date.now() };
  sessions.value.unshift(s);
  currentSessionId.value = s.id;
  save();
}

function switchTo(id: string) { currentSessionId.value = id; }

async function remove(id: string) {
  const s = sessions.value.find((x) => x.id === id);
  if (!s) return;
  const confirmed = await confirmModal('删除会话', `删除「${s.title}」？`);
  if (!confirmed) return;
  const i = sessions.value.findIndex((x) => x.id === id);
  if (i < 0) return;
  sessions.value.splice(i, 1);
  if (!sessions.value.length) create();
  if (currentSessionId.value === id) currentSessionId.value = sessions.value[0].id;
  save();
}

function startRename(id: string) {
  const s = sessions.value.find((x) => x.id === id);
  if (!s) return;
  renamingId.value = id;
  renameValue.value = s.title;
}

function confirmRename() {
  const s = sessions.value.find((x) => x.id === renamingId.value);
  if (s && renameValue.value.trim()) s.title = renameValue.value.trim();
  renamingId.value = '';
  renameValue.value = '';
  save();
}

function cancelRename() { renamingId.value = ''; renameValue.value = ''; }

function autoTitle(s: ChatSession) {
  const first = s.messages.find((m) => m.role === 'user');
  if (first) s.title = first.content.slice(0, 18) + (first.content.length > 18 ? '…' : '');
}

// ── Batch delete ────────────────────────────────────────────
function toggleSelectMode() {
  selectMode.value = !selectMode.value;
  if (!selectMode.value) selectedIds.value.clear();
}

function toggleSelect(id: string) {
  if (selectedIds.value.has(id)) selectedIds.value.delete(id);
  else selectedIds.value.add(id);
}

function selectAll() {
  if (selectedIds.value.size === sessions.value.length) selectedIds.value.clear();
  else sessions.value.forEach((s) => selectedIds.value.add(s.id));
}

async function removeSelected() {
  if (selectedIds.value.size === 0) return;
  const confirmed = await confirmModal('批量删除', `删除选中的 ${selectedIds.value.size} 个对话？`);
  if (!confirmed) return;
  const idsToDelete = new Set(selectedIds.value);
  sessions.value = sessions.value.filter((s) => !idsToDelete.has(s.id));
  selectedIds.value.clear();
  selectMode.value = false;
  if (!sessions.value.length) create();
  if (idsToDelete.has(currentSessionId.value)) currentSessionId.value = sessions.value[0].id;
  save();
}

// ── History / Context ───────────────────────────────────────
function buildHistory(question: string) {
  const h = msgs.value.filter((m) => m.status === 'done').map((m) => ({ role: m.role, content: m.content }));
  if (h.length && h[h.length - 1].role === 'user' && h[h.length - 1].content === question) h.pop();
  return h;
}

// ── Scroll ──────────────────────────────────────────────────
function isNearBottom(): boolean {
  if (clientHeightVal.value === 0) return true;
  return scrollHeightVal.value - scrollTopVal.value - clientHeightVal.value < 120;
}

let wasNearBottom = true;

function snapshotScroll() {
  wasNearBottom = isNearBottom();
}

function scrollDown(force = false) {
  nextTick(() => {
    if (force || wasNearBottom) {
      scrollTarget.value = '';
      nextTick(() => { scrollTarget.value = 'scroll-bottom'; });
      showScrollBtn.value = false;
    } else {
      showScrollBtn.value = true;
    }
    wasNearBottom = true;
  });
}

function onScroll(e: { detail: { scrollTop: number; scrollHeight: number } }) {
  scrollTopVal.value = e.detail.scrollTop;
  scrollHeightVal.value = e.detail.scrollHeight;
  showScrollBtn.value = !isNearBottom();
}

function scrollToBottom() {
  scrollTarget.value = '';
  nextTick(() => { scrollTarget.value = 'scroll-bottom'; });
  showScrollBtn.value = false;
}

function measureScroll() {
  uni.createSelectorQuery()
    .select('.messages-scroll')
    .boundingClientRect((rect: any) => {
      if (typeof rect?.height === 'number') clientHeightVal.value = rect.height;
    })
    .exec();
}

// ── Send ────────────────────────────────────────────────────
function send() {
  const q = input.value.trim();
  if (!q || !currentSession.value) return;
  snapshotScroll();
  if (generating.value) {
    queue.value.push(q);
    currentSession.value.messages.push({ id: nextId(), role: 'user', content: q, ts: Date.now(), status: 'queued' });
    input.value = '';
    scrollDown(true);
    return;
  }
  const idx = currentSession.value.messages.length;
  currentSession.value.messages.push({ id: nextId(), role: 'user', content: q, ts: Date.now(), status: 'done' });
  autoTitle(currentSession.value);
  save();
  input.value = '';
  scrollDown(true);
  if (looksCmd(q)) void detectCmd(idx); else ask(q);
}

// ── AI ──────────────────────────────────────────────────────
async function ask(question: string) {
  if (!currentSession.value) return;
  generating.value = true;
  aiStatus.value = 'connecting';
  const msg: ChatMessage = { id: nextId(), role: 'assistant', content: '', ts: Date.now(), status: 'generating' };
  snapshotScroll();
  currentSession.value.messages.push(msg);
  scrollDown(true);
  const ctrl = new AbortController();
  abortController.value = ctrl;
  try {
    aiStatus.value = 'thinking';
    const r = await sendAiQuery(question, buildHistory(question), ctrl.signal) as { reply: string; data_source?: string; diagnostic?: Record<string, unknown> };
    if (ctrl.signal.aborted) return;
    aiStatus.value = 'replying';
    msg.content = r.reply;
    msg.dataSource = r.data_source;
    msg.diagnostic = r.diagnostic ?? null;
    msg.status = 'done';
    save();
  } catch (e) {
    if (ctrl.signal.aborted) return;
    msg.content = `请求失败: ${e instanceof Error ? e.message : '未知错误'}`;
    msg.status = 'error';
    uni.showToast({ title: msg.content, icon: 'none' });
  } finally {
    if (abortController.value === ctrl) {
      abortController.value = null;
      generating.value = false;
      aiStatus.value = 'idle';
    }
    scrollDown();
    if (!generating.value && queue.value.length) {
      const n = queue.value.shift()!;
      const qm = currentSession.value.messages.find((m) => m.status === 'queued');
      if (qm) qm.status = 'done';
      await nextTick();
      ask(n).catch(() => { /* swallowed: ask() already handles errors internally */ });
    }
  }
}

// ── Command detection ───────────────────────────────────────
const cmdKw = ['打开', '关闭', '关掉', 'on', 'off', 'auto', '自动', '电机', '灯', '补光灯', '风扇'];
const bulkKw = ['所有', '全部', '全部的', '所有的', '每个', '全都'];
const actuatorKw = ['电机', '灯', '补光灯', '风扇', 'motor', 'light'];

function looksCmd(t: string): boolean {
  if (!cmdKw.some((k) => t.includes(k))) return false;
  return /[aA]\d{3}|槽位\d+|bearpi|所有|全部|全都|每个/i.test(t) ||
    actuatorKw.some((k) => t.includes(k));
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
  const user = currentSession.value.messages[idx];
  if (!user) return;
  const isBulk = bulkKw.some((k) => user.content.includes(k));
  const hasActuator = actuatorKw.some((k) => user.content.includes(k));
  const hasDevice = /[aA]\d{3}|槽位\d+|bearpi/i.test(user.content);
  const shouldBulk = isBulk || (hasActuator && !hasDevice);
  const cmd: ChatMessage = { id: nextId(), role: 'assistant', content: '正在解析指令…', ts: Date.now(), status: 'done', commandStatus: 'confirming' };
  snapshotScroll();
  currentSession.value.messages.splice(idx + 1, 0, cmd);
  scrollDown();
  try {
    if (shouldBulk) {
      const intent = parseBulkIntent(user.content);
      if (intent) {
        const al = intent.actuator === 'motor' ? '电机' : '补光灯';
        const ml = intent.mode === 'on' ? '打开' : intent.mode === 'off' ? '关闭' : '自动';
        cmd.content = `检测到批量控制指令: ${al} ${ml}（全部设备）`;
        cmd.command = { detected: true, actuator: intent.actuator, mode: intent.mode, device_sn: '全部设备', explanation: `批量${al}${ml}` } as AiCommandResult & { _bulk?: boolean };
        (cmd.command as AiCommandResult & { _bulk?: boolean })._bulk = true;
      } else {
        cmd.content = '未识别为设备控制指令';
        cmd.commandStatus = 'rejected';
      }
    } else {
      const r = await parseAiCommand(user.content);
      cmd.command = r;
      if (r.detected && r.device_id) {
        cmd.content = `检测到控制指令: ${r.explanation || ''}`;
      } else {
        cmd.content = r.explanation || '未识别为设备控制指令';
        cmd.commandStatus = 'rejected';
        cmd.command = undefined;
        ask(user.content);
      }
    }
  } catch {
    cmd.content = '指令解析失败';
    cmd.commandStatus = 'error';
  }
  scrollDown();
}

async function execCmd(idx: number) {
  if (!auth.canCommand) {
    uni.showToast({ title: '当前角色无权下发指令', icon: 'none' });
    return;
  }
  if (!currentSession.value) return;
  const cmd = currentSession.value.messages[idx];
  if (!cmd?.command) return;
  snapshotScroll();
  cmd.commandStatus = 'executing';
  cmd.content = '正在执行…';
  try {
    const { actuator, mode } = cmd.command;
    const isBulk = (cmd.command as AiCommandResult & { _bulk?: boolean })._bulk;
    if (isBulk) {
      await sendBulkCommand({ target: 'all', actuator: actuator as 'motor' | 'light', mode: (mode as 'auto' | 'on' | 'off') ?? 'on' });
      const al = actuator === 'motor' ? '电机' : '补光灯';
      const ml = mode === 'on' ? '打开' : mode === 'off' ? '关闭' : '自动';
      cmd.commandStatus = 'executed';
      cmd.content = `已批量下发: 全部设备 ${al} ${ml}`;
      uni.showToast({ title: '批量指令已下发', icon: 'success' });
    } else {
      if (!cmd.command.device_id) return;
      const pk = actuator === 'motor' ? 'motor_override' : 'light_override';
      const p: Record<string, string | number | boolean> = {};
      p[pk] = mode ?? 'on';
      await sendCommand(cmd.command.device_id, { type: 'set_param', params: p });
      cmd.commandStatus = 'executed';
      const al = actuator === 'motor' ? '电机' : '补光灯';
      const ml = mode === 'on' ? '打开' : mode === 'off' ? '关闭' : '自动';
      cmd.content = `已下发: ${cmd.command.device_sn} ${al} ${ml}`;
      uni.showToast({ title: '指令已下发', icon: 'success' });
    }
  } catch (e) {
    cmd.commandStatus = 'error';
    cmd.content = `执行失败: ${e instanceof Error ? e.message : '未知错误'}`;
  }
  scrollDown();
}

function rejectCmd(idx: number) {
  if (!currentSession.value) return;
  const m = currentSession.value.messages[idx];
  if (m) { m.commandStatus = 'rejected'; m.content = '已取消'; }
}

// ── Actions ─────────────────────────────────────────────────
function stop() {
  abortController.value?.abort();
  generating.value = false;
  aiStatus.value = 'idle';
  if (!currentSession.value) return;
  snapshotScroll();
  const last = currentSession.value.messages[currentSession.value.messages.length - 1];
  if (last?.role === 'assistant' && last.status === 'generating') {
    last.content = (last.content || '') + '\n\n*[已停止]*';
    last.status = 'done';
  }
  currentSession.value.messages.forEach((m) => { if (m.status === 'queued') m.status = 'done'; });
  queue.value = [];
  save();
}

function regen(idx: number) {
  if (!currentSession.value) return;
  const m = currentSession.value.messages[idx];
  if (!m || m.role !== 'assistant') return;
  let qi = -1;
  for (let i = idx - 1; i >= 0; i--) {
    if (currentSession.value.messages[i].role === 'user') { qi = i; break; }
  }
  if (qi < 0) return;
  const q = currentSession.value.messages[qi].content;
  snapshotScroll();
  currentSession.value.messages.splice(idx, 1);
  if (!generating.value) ask(q); else queue.value.push(q);
}

function editStart(i: number) {
  if (!currentSession.value) return;
  currentSession.value.messages.forEach((m) => { m.editing = false; });
  currentSession.value.messages[i].editing = true;
  editValue.value = currentSession.value.messages[i].content;
}

function editOk(i: number) {
  if (!currentSession.value) return;
  const m = currentSession.value.messages[i];
  if (!m) return;
  m.content = editValue.value;
  m.editing = false;
  currentSession.value.messages.splice(i + 1);
  if (!generating.value) ask(editValue.value); else queue.value.push(editValue.value);
}

function editCancel(i: number) {
  if (currentSession.value) currentSession.value.messages[i].editing = false;
}

function copyText(t: string) {
  uni.setClipboardData({ data: t, success: () => uni.showToast({ title: '已复制', icon: 'success' }) });
}

function react(i: number, r: 'up' | 'down') {
  if (!currentSession.value) return;
  const m = currentSession.value.messages[i];
  if (m) m.reaction = m.reaction === r ? null : r;
}

function toggleDiag(id: string) {
  if (diagExpanded.value.has(id)) diagExpanded.value.delete(id);
  else diagExpanded.value.add(id);
}

// ── Utility ─────────────────────────────────────────────────
function useExample(q: string) {
  input.value = q;
  nextTick(() => send());
}

function open() { visible.value = true; }

function clear() {
  if (!currentSession.value) return;
  uni.showModal({
    title: '清空对话',
    content: '确定清空当前对话？',
    success: (res) => {
      if (res.confirm && currentSession.value) {
        if (generating.value) stop();
        currentSession.value.messages = [];
        queue.value = [];
        save();
      }
    },
  });
}

function fmtTime(ts: number) {
  const d = new Date(ts);
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;
}

function confirmModal(title: string, content: string): Promise<boolean> {
  return new Promise((resolve) => {
    uni.showModal({ title, content, success: (res) => resolve(!!res.confirm), fail: () => resolve(false) });
  });
}

function formatDiagnostic(diag: Record<string, unknown>): string {
  const parts: string[] = [];
  if (diag.upstream_status) parts.push(`HTTP ${diag.upstream_status}`);
  if (diag.model) parts.push(`模型: ${diag.model}`);
  if (diag.url_host) parts.push(`Host: ${diag.url_host}`);
  if (diag.reason) parts.push(diag.reason as string);
  return parts.join(' | ');
}

function startStatusTimer() {
  if (statusTimer !== null) return;
  statusTimer = setInterval(() => {
    statusTick.value++;
  }, 600);
}

function stopStatusTimer() {
  if (statusTimer === null) return;
  clearInterval(statusTimer);
  statusTimer = null;
}

// ── Lifecycle ───────────────────────────────────────────────
onBeforeUnmount(() => { if (generating.value) stop(); stopStatusTimer(); });

watch(aiStatus, (status) => {
  if (status === 'idle') stopStatusTimer();
  else startStatusTimer();
});

watch(visible, (v) => {
  if (v) {
    if (!sessions.value.length) load();
    nextTick(() => measureScroll());
  }
});
</script>

<template>
  <wd-button size="small" type="primary" plain @click="open">AI问答</wd-button>

  <wd-popup
    v-model="visible"
    position="bottom"
    closable
    custom-style="max-height: 85vh; padding: 0; border-radius: 28rpx 28rpx 0 0; background: #f7f8fa; overflow: hidden;"
  >
    <view class="ai-query">
      <!-- Header -->
      <view class="header">
        <view class="header-main">
          <text class="header-title">AI智能助手</text>
          <text v-if="currentSession" class="header-sub">{{ currentSession.title }}</text>
        </view>
        <view class="header-actions">
          <view class="header-btn" @click="showSessionBar = !showSessionBar">
            <text class="header-btn-icon">{{ showSessionBar ? '▼' : '▲' }}</text>
            <text class="header-btn-text">会话</text>
          </view>
          <view v-if="msgs.length" class="header-btn" @click="clear">
            <text class="header-btn-text">清空</text>
          </view>
        </view>
      </view>

      <!-- Session panel -->
      <view v-if="showSessionBar" class="session-panel">
        <view class="session-controls">
          <view class="ctrl-btn" @click="create">
            <text>+ 新建</text>
          </view>
          <view class="ctrl-btn" :class="{ active: selectMode }" @click="toggleSelectMode">
            <text>{{ selectMode ? '取消' : '多选' }}</text>
          </view>
          <view v-if="selectMode && selectedIds.size > 0" class="ctrl-btn danger" @click="removeSelected">
            <text>删除({{ selectedIds.size }})</text>
          </view>
          <view v-if="selectMode" class="ctrl-btn" @click="selectAll">
            <text>{{ selectedIds.size === sessions.length ? '取消全选' : '全选' }}</text>
          </view>
        </view>
        <scroll-view scroll-x class="session-list" :show-scrollbar="false">
          <view
            v-for="s in sessions"
            :key="s.id"
            class="session-item"
            :class="{ active: s.id === currentSessionId && !selectMode, selected: selectedIds.has(s.id) }"
            @click="selectMode ? toggleSelect(s.id) : switchTo(s.id)"
          >
            <template v-if="s.id === renamingId">
              <input
                class="rename-input"
                :value="renameValue"
                @input="(e: any) => renameValue = e.detail.value"
                @blur="confirmRename"
                @confirm="confirmRename"
                @click.stop
              />
            </template>
            <template v-else>
              <text v-if="selectMode" class="session-check">{{ selectedIds.has(s.id) ? '✓' : '○' }}</text>
              <text class="session-title">{{ s.title }}</text>
              <view v-if="!selectMode" class="session-actions">
                <view class="session-action" @click.stop="startRename(s.id)"><text>编辑</text></view>
                <view class="session-action danger" @click.stop="remove(s.id)"><text>删除</text></view>
              </view>
            </template>
          </view>
        </scroll-view>
      </view>

      <!-- Status bar -->
      <view v-if="generating || queueLen > 0" class="status-bar">
        <view v-if="generating" class="status-info">
          <view class="status-dots">
            <view class="status-dot"></view>
            <view class="status-dot"></view>
            <view class="status-dot"></view>
          </view>
          <text class="status-text">{{ statusText || '思考中' }}</text>
        </view>
        <text v-if="queueLen > 0" class="queue-text">队列{{ queueLen }}</text>
        <view v-if="generating" class="stop-btn" @click="stop">
          <text>停止</text>
        </view>
      </view>

      <!-- Messages -->
      <scroll-view
        scroll-y
        class="messages-scroll"
        :scroll-into-view="scrollTarget"
        scroll-with-animation
        enhanced
        :show-scrollbar="false"
        @scroll="onScroll"
      >
        <!-- Welcome -->
        <view v-if="!msgs.length" class="welcome">
          <text class="welcome-title">你好，我是实验室AI助手</text>
          <text class="welcome-sub">今天想了解什么？</text>
          <view class="example-list">
            <view v-for="e in examples" :key="e" class="example-card" @click="useExample(e)">
              <text>{{ e }}</text>
            </view>
          </view>
        </view>

        <!-- Messages -->
        <view
          v-for="(msg, idx) in msgs"
          :key="msg.id"
          :id="'msg-' + msg.id"
          :class="['msg-row', msg.role]"
        >
          <!-- User message -->
          <template v-if="msg.role === 'user'">
            <view class="u-wrap">
              <view v-if="msg.editing" class="edit-box">
                <textarea
                  class="edit-ta"
                  :value="editValue"
                  :maxlength="-1"
                  @input="(e: any) => editValue = e.detail.value"
                />
                <view class="edit-btns">
                  <view class="btn-ok" @click="editOk(idx)"><text>确认</text></view>
                  <view class="btn-no" @click="editCancel(idx)"><text>取消</text></view>
                </view>
              </view>
              <template v-else>
                <view class="u-bubble">
                  <text selectable>{{ msg.content }}</text>
                </view>
                <view class="msg-bar">
                  <text class="ts">{{ fmtTime(msg.ts) }}</text>
                  <view class="act" @click="editStart(idx)"><text>编辑</text></view>
                </view>
              </template>
            </view>
          </template>

          <!-- Assistant message -->
          <template v-else>
            <view class="a-wrap">
              <!-- Command message -->
              <template v-if="msg.commandStatus">
                <view class="cmd" :class="'cmd-' + msg.commandStatus">
                  <view class="cmd-icon-wrap">
                    <text v-if="msg.commandStatus === 'executed'" class="cmd-icon-ok">✓</text>
                    <view v-else-if="msg.commandStatus === 'executing'" class="cmd-spinner"></view>
                    <text v-else class="cmd-icon-wait">⏸</text>
                  </view>
                  <view class="cmd-body">
                    <template v-if="msg.command?.detected && msg.commandStatus === 'confirming'">
                      <text class="cmd-title">控制指令</text>
                      <text class="cmd-desc">{{ msg.command.device_sn }} · {{ msg.command.actuator === 'motor' ? '电机' : '补光灯' }} · {{ msg.command.mode === 'on' ? '打开' : msg.command.mode === 'off' ? '关闭' : '自动' }}</text>
                      <view class="cmd-btns">
                        <view class="cmd-go" @click="execCmd(idx)"><text>确认执行</text></view>
                        <view class="cmd-no" @click="rejectCmd(idx)"><text>取消</text></view>
                      </view>
                    </template>
                    <template v-else>
                      <text class="cmd-status-text">{{ msg.content }}</text>
                    </template>
                  </view>
                </view>
              </template>

              <!-- Normal assistant message -->
              <template v-else>
                <view v-if="msg.status === 'generating' && !msg.content" class="typing">
                  <view class="typing-dot"></view>
                  <view class="typing-dot"></view>
                  <view class="typing-dot"></view>
                  <text class="typing-lbl">{{ statusText || '思考中' }}</text>
                </view>
                <template v-else>
                  <view class="a-bubble">
                    <MarkdownMessage :content="msg.content" :data-source="msg.dataSource" />
                    <view v-if="msg.diagnostic" class="diag">
                      <text class="diag-toggle" @click="toggleDiag(msg.id)">调试 {{ diagExpanded.has(msg.id) ? '▲' : '▼' }}</text>
                      <view v-if="diagExpanded.has(msg.id)" class="diag-content">
                        <text class="diag-text">{{ formatDiagnostic(msg.diagnostic) }}</text>
                        <text class="diag-raw">{{ JSON.stringify(msg.diagnostic, null, 2) }}</text>
                      </view>
                    </view>
                  </view>
                  <view class="msg-bar">
                    <text class="ts">{{ fmtTime(msg.ts) }}</text>
                    <view class="act" :class="{ on: msg.reaction === 'up' }" @click="react(idx, 'up')"><text>👍</text></view>
                    <view class="act" :class="{ on: msg.reaction === 'down' }" @click="react(idx, 'down')"><text>👎</text></view>
                    <view class="act" @click="copyText(msg.content)"><text>复制</text></view>
                    <view v-if="msg.status === 'done' || msg.status === 'error'" class="act" @click="regen(idx)"><text>重试</text></view>
                  </view>
                </template>
              </template>
            </view>
          </template>
        </view>

        <!-- Scroll anchor -->
        <view id="scroll-bottom"></view>
      </scroll-view>

      <!-- Scroll-to-bottom FAB -->
      <view v-if="showScrollBtn" class="scroll-fab" @click="scrollToBottom">
        <text class="scroll-fab-icon">↓</text>
      </view>

      <!-- Input area -->
      <view class="input-area">
        <view class="input-frame">
          <input
            v-model="input"
            class="chat-input"
            placeholder="给实验室助手发送消息…"
            confirm-type="send"
            @confirm="send"
          />
          <view class="send-btn" :class="{ disabled: !canSend }" @click="canSend && send()">
            <text>发送</text>
          </view>
        </view>
      </view>
    </view>
  </wd-popup>
</template>

<style lang="scss" scoped>
/* ── Container ─────────────────────────────────── */
.ai-query {
  display: flex;
  flex-direction: column;
  height: 76vh;
  background: #f7f8fa;
}

/* ── Header ────────────────────────────────────── */
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24rpx 28rpx 20rpx;
  border-bottom: 2rpx solid rgba(0, 0, 0, 0.07);
  background: rgba(255, 255, 255, 0.78);
}

.header-main {
  display: flex;
  flex-direction: column;
  gap: 4rpx;
  min-width: 0;
  flex: 1;
}

.header-title {
  color: #101828;
  font-size: 30rpx;
  font-weight: 700;
  line-height: 1.2;
}

.header-sub {
  overflow: hidden;
  color: #98a2b3;
  font-size: 22rpx;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.header-actions {
  display: flex;
  gap: 12rpx;
  flex-shrink: 0;
}

.header-btn {
  display: flex;
  align-items: center;
  gap: 6rpx;
  height: 56rpx;
  padding: 0 18rpx;
  border: 2rpx solid rgba(0, 0, 0, 0.1);
  border-radius: 14rpx;
  background: rgba(255, 255, 255, 0.72);
}

.header-btn-icon {
  font-size: 20rpx;
  color: #667085;
}

.header-btn-text {
  color: #344054;
  font-size: 24rpx;
  font-weight: 600;
}

/* ── Session panel ─────────────────────────────── */
.session-panel {
  border-bottom: 2rpx solid rgba(0, 0, 0, 0.06);
  background: rgba(255, 255, 255, 0.58);
}

.session-controls {
  display: flex;
  gap: 10rpx;
  padding: 14rpx 20rpx 10rpx;
}

.ctrl-btn {
  display: flex;
  align-items: center;
  height: 52rpx;
  padding: 0 18rpx;
  border: 2rpx solid rgba(0, 0, 0, 0.1);
  border-radius: 12rpx;
  background: transparent;

  text {
    color: #1d2430;
    font-size: 22rpx;
    font-weight: 500;
    white-space: nowrap;
  }
}

.ctrl-btn.active {
  background: #0a84ff;
  border-color: #0a84ff;

  text {
    color: #ffffff;
  }
}

.ctrl-btn.danger {
  border-color: rgba(255, 69, 58, 0.3);

  text {
    color: #ff453a;
  }
}

.session-list {
  display: flex;
  gap: 10rpx;
  padding: 0 20rpx 16rpx;
  white-space: nowrap;
}

.session-item {
  display: inline-flex;
  align-items: center;
  gap: 8rpx;
  min-height: 60rpx;
  padding: 0 16rpx;
  border: 2rpx solid transparent;
  border-radius: 14rpx;
  flex-shrink: 0;
  max-width: 340rpx;
  background: rgba(255, 255, 255, 0.5);
}

.session-item.active {
  border-color: rgba(10, 132, 255, 0.28);
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 2rpx 6rpx rgba(16, 24, 40, 0.06);
}

.session-item.selected {
  background: rgba(10, 132, 255, 0.08);
  border-color: rgba(10, 132, 255, 0.2);
}

.session-check {
  font-size: 26rpx;
  color: #0a84ff;
  flex-shrink: 0;
}

.session-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  color: #344054;
  font-size: 24rpx;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-actions {
  display: flex;
  gap: 4rpx;
  flex-shrink: 0;
}

.session-action {
  padding: 4rpx 10rpx;
  border-radius: 8rpx;

  text {
    color: #667085;
    font-size: 20rpx;
  }
}

.session-action.danger text {
  color: #ff453a;
}

.rename-input {
  flex: 1;
  min-width: 0;
  height: 48rpx;
  padding: 0 12rpx;
  border: 2rpx solid rgba(10, 132, 255, 0.4);
  border-radius: 10rpx;
  background: #ffffff;
  color: #101828;
  font-size: 24rpx;
}

/* ── Status bar ────────────────────────────────── */
.status-bar {
  display: flex;
  align-items: center;
  gap: 14rpx;
  min-height: 64rpx;
  padding: 0 28rpx;
  border-bottom: 2rpx solid rgba(0, 0, 0, 0.06);
  background: rgba(247, 248, 250, 0.82);
}

.status-info {
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.status-dots {
  display: flex;
  gap: 6rpx;
}

.status-dot {
  width: 10rpx;
  height: 10rpx;
  border-radius: 999rpx;
  background: #98a2b3;
  animation: dotBounce 1.4s ease-in-out infinite;
}

.status-dot:nth-child(2) { animation-delay: 0.2s; }
.status-dot:nth-child(3) { animation-delay: 0.4s; }

.status-text {
  color: #667085;
  font-size: 24rpx;
  white-space: nowrap;
}

.queue-text {
  color: #ff9f0a;
  font-size: 24rpx;
  white-space: nowrap;
}

.stop-btn {
  margin-left: auto;
  display: flex;
  align-items: center;
  height: 50rpx;
  padding: 0 18rpx;
  border: 2rpx solid rgba(255, 69, 58, 0.2);
  border-radius: 12rpx;
  background: rgba(255, 69, 58, 0.08);

  text {
    color: #ff453a;
    font-size: 24rpx;
    font-weight: 600;
  }
}

/* ── Messages scroll ───────────────────────────── */
.messages-scroll {
  flex: 1;
  overflow: hidden;
  padding: 20rpx 24rpx;
  box-sizing: border-box;
}

/* ── Welcome ───────────────────────────────────── */
.welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12rpx;
  padding: 120rpx 24rpx 40rpx;
  text-align: center;
}

.welcome-title {
  color: #101828;
  font-size: 34rpx;
  font-weight: 750;
}

.welcome-sub {
  color: #667085;
  font-size: 26rpx;
}

.example-list {
  display: flex;
  flex-wrap: wrap;
  gap: 14rpx;
  justify-content: center;
  margin-top: 28rpx;
}

.example-card {
  min-height: 60rpx;
  padding: 0 24rpx;
  border: 2rpx solid #d8dee8;
  border-radius: 999rpx;
  background: #ffffff;
  display: flex;
  align-items: center;

  text {
    color: #344054;
    font-size: 24rpx;
  }
}

/* ── Message rows ──────────────────────────────── */
.msg-row {
  display: flex;
  margin-bottom: 24rpx;
}

.msg-row.user {
  justify-content: flex-end;
}

.msg-row.assistant {
  justify-content: flex-start;
}

/* ── User messages ─────────────────────────────── */
.u-wrap {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  max-width: 82%;
}

.u-bubble {
  padding: 18rpx 24rpx;
  border-radius: 32rpx 32rpx 10rpx 32rpx;
  background: #0a84ff;
  box-shadow: 0 2rpx 6rpx rgba(16, 24, 40, 0.06);

  text {
    color: #ffffff;
    font-size: 26rpx;
    line-height: 1.6;
    white-space: pre-wrap;
    word-break: break-word;
  }
}

/* ── Assistant messages ────────────────────────── */
.a-wrap {
  display: flex;
  flex-direction: column;
  max-width: 88%;
}

.a-bubble {
  padding: 22rpx 26rpx;
  border: 2rpx solid #e5e9f0;
  border-radius: 32rpx 32rpx 32rpx 10rpx;
  background: #ffffff;
  box-shadow: 0 2rpx 6rpx rgba(16, 24, 40, 0.04);
}

/* ── Command messages ──────────────────────────── */
.cmd {
  display: flex;
  gap: 16rpx;
  padding: 20rpx;
  border: 2rpx solid #e5e9f0;
  border-radius: 24rpx;
  background: #ffffff;
  box-shadow: 0 2rpx 6rpx rgba(16, 24, 40, 0.04);
}

.cmd-icon-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 56rpx;
  height: 56rpx;
  border-radius: 14rpx;
  background: rgba(10, 132, 255, 0.08);
  flex-shrink: 0;
}

.cmd-confirming .cmd-icon-wrap { background: rgba(10, 132, 255, 0.08); }
.cmd-executing .cmd-icon-wrap { background: rgba(255, 159, 10, 0.08); }
.cmd-executed .cmd-icon-wrap { background: rgba(52, 199, 89, 0.08); }
.cmd-rejected .cmd-icon-wrap,
.cmd-error .cmd-icon-wrap { background: rgba(255, 69, 58, 0.08); }

.cmd-icon-ok {
  color: #34c759;
  font-size: 28rpx;
  font-weight: 700;
}

.cmd-icon-wait {
  color: #0a84ff;
  font-size: 28rpx;
}

.cmd-spinner {
  width: 28rpx;
  height: 28rpx;
  border: 4rpx solid rgba(255, 159, 10, 0.3);
  border-top-color: #ff9f0a;
  border-radius: 999rpx;
  animation: spin 0.8s linear infinite;
}

.cmd-body {
  display: flex;
  flex-direction: column;
  gap: 6rpx;
  flex: 1;
  min-width: 0;
}

.cmd-title {
  color: #101828;
  font-size: 26rpx;
  font-weight: 700;
}

.cmd-desc {
  color: #667085;
  font-size: 24rpx;
  line-height: 1.5;
}

.cmd-status-text {
  color: #667085;
  font-size: 24rpx;
  line-height: 1.5;
}

.cmd-btns {
  display: flex;
  gap: 12rpx;
  margin-top: 12rpx;
}

.cmd-go,
.cmd-no {
  display: flex;
  align-items: center;
  height: 56rpx;
  padding: 0 22rpx;
  border-radius: 14rpx;

  text {
    font-size: 24rpx;
    font-weight: 650;
  }
}

.cmd-go {
  background: #0a84ff;

  text { color: #ffffff; }
}

.cmd-no {
  background: rgba(16, 24, 40, 0.06);

  text { color: #475467; }
}

/* ── Typing animation ──────────────────────────── */
.typing {
  display: inline-flex;
  align-items: center;
  gap: 10rpx;
  padding: 18rpx 24rpx;
  border: 2rpx solid #e5e9f0;
  border-radius: 999rpx;
  background: #ffffff;
  box-shadow: 0 2rpx 6rpx rgba(16, 24, 40, 0.04);
}

.typing-dot {
  width: 10rpx;
  height: 10rpx;
  border-radius: 999rpx;
  background: #98a2b3;
  animation: dotBounce 1.4s ease-in-out infinite;
}

.typing-dot:nth-child(2) { animation-delay: 0.2s; }
.typing-dot:nth-child(3) { animation-delay: 0.4s; }

.typing-lbl {
  margin-left: 6rpx;
  color: #667085;
  font-size: 24rpx;
}

/* ── Edit mode ─────────────────────────────────── */
.edit-box {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
  width: 100%;
}

.edit-ta {
  width: 100%;
  min-height: 120rpx;
  padding: 16rpx 20rpx;
  border: 2rpx solid #d8dee8;
  border-radius: 20rpx;
  background: #ffffff;
  color: #101828;
  font-size: 26rpx;
  line-height: 1.6;
}

.edit-btns {
  display: flex;
  gap: 12rpx;
}

.btn-ok,
.btn-no {
  display: flex;
  align-items: center;
  height: 56rpx;
  padding: 0 22rpx;
  border-radius: 14rpx;

  text {
    font-size: 24rpx;
    font-weight: 650;
  }
}

.btn-ok {
  background: #0a84ff;

  text { color: #ffffff; }
}

.btn-no {
  background: rgba(16, 24, 40, 0.06);

  text { color: #475467; }
}

/* ── Message bar (actions) ─────────────────────── */
.msg-bar {
  display: flex;
  align-items: center;
  gap: 6rpx;
  margin-top: 8rpx;
  flex-wrap: wrap;
}

.ts {
  margin-right: 6rpx;
  color: #98a2b3;
  font-size: 22rpx;
}

.act {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 48rpx;
  height: 44rpx;
  padding: 0 10rpx;
  border-radius: 12rpx;

  text {
    color: #98a2b3;
    font-size: 22rpx;
  }
}

.act.on {
  background: rgba(10, 132, 255, 0.08);

  text {
    color: #0a84ff;
  }
}

/* ── Diagnostic ────────────────────────────────── */
.diag {
  margin-top: 14rpx;
  padding-top: 14rpx;
  border-top: 2rpx solid #f0f2f5;
}

.diag-toggle {
  color: #98a2b3;
  font-size: 22rpx;
}

.diag-content {
  margin-top: 10rpx;
  padding: 14rpx;
  border-radius: 14rpx;
  background: #f2f4f7;
}

.diag-text {
  display: block;
  color: #667085;
  font-size: 22rpx;
  line-height: 1.5;
}

.diag-raw {
  display: block;
  margin-top: 8rpx;
  color: #98a2b3;
  font-size: 20rpx;
  line-height: 1.5;
  word-break: break-all;
}

/* ── Scroll FAB ────────────────────────────────── */
.scroll-fab {
  position: absolute;
  right: 32rpx;
  bottom: 160rpx;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 64rpx;
  height: 64rpx;
  border: 2rpx solid #d8dee8;
  border-radius: 999rpx;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 8rpx 24rpx rgba(16, 24, 40, 0.14);
}

.scroll-fab-icon {
  color: #667085;
  font-size: 28rpx;
  font-weight: 700;
}

/* ── Input area ────────────────────────────────── */
.input-area {
  flex-shrink: 0;
  padding: 18rpx 24rpx 28rpx;
  border-top: 2rpx solid rgba(0, 0, 0, 0.07);
  background: rgba(247, 248, 250, 0.94);
}

.input-frame {
  display: flex;
  align-items: center;
  gap: 14rpx;
  padding: 6rpx 6rpx 6rpx 24rpx;
  border: 2rpx solid #d8dee8;
  border-radius: 28rpx;
  background: #ffffff;
  box-shadow: 0 2rpx 6rpx rgba(16, 24, 40, 0.04);
}

.chat-input {
  flex: 1;
  height: 72rpx;
  font-size: 26rpx;
  color: #101828;
}

.send-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  min-width: 120rpx;
  height: 68rpx;
  border-radius: 22rpx;
  background: #0a84ff;
  box-shadow: 0 8rpx 20rpx rgba(10, 132, 255, 0.22);

  text {
    color: #ffffff;
    font-size: 26rpx;
    font-weight: 700;
  }
}

.send-btn.disabled {
  opacity: 0.36;
  box-shadow: none;
}

/* ── Animations ────────────────────────────────── */
@keyframes dotBounce {
  0%, 80%, 100% { opacity: 0.28; transform: translateY(0); }
  40% { opacity: 1; transform: translateY(-4rpx); }
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
