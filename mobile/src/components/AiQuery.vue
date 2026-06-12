<script setup lang="ts">
import { computed, nextTick, ref } from 'vue';
import MarkdownMessage from '@/components/MarkdownMessage.vue';
import { sendAiQuery, parseAiCommand, sendCommand, sendBulkCommand } from '@/api/lab';
import type { AiCommandResult } from '@/api/lab';
import { useAuthStore } from '@/stores/auth';

const auth = useAuthStore();

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  dataSource?: string;
  diagnostic?: Record<string, unknown> | null;
  command?: AiCommandResult & { _bulk?: boolean };
  commandStatus?: 'confirming' | 'executing' | 'executed' | 'rejected' | 'error';
}

const visible = ref(false);
const input = ref('');
const loading = ref(false);
const messages = ref<ChatMessage[]>([]);

const exampleQuestions = [
  '哪块板的功耗最高?',
  'A001板的温度怎么样?',
  '把所有电机打开',
  '关闭全部灯',
];

// ── Command detection ────────────────────────────────────────
const cmdKw = ['打开', '关闭', '关掉', '开', '关', 'on', 'off', 'auto', '自动', '电机', '灯', '补光灯', '风扇'];
const bulkKw = ['所有', '全部', '全部的', '所有的', '每个', '全都'];
const actuatorKw = ['电机', '灯', '补光灯', '风扇', 'motor', 'light'];

function looksCmd(t: string): boolean {
  if (!cmdKw.some((k) => t.includes(k))) return false;
  // 匹配设备标识 或 包含执行器关键词（如"关闭灯"、"打开电机"）
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

const canSend = computed(() => input.value.trim().length > 0 && !loading.value);

async function send() {
  const question = input.value.trim();
  if (!question || loading.value) return;

  messages.value.push({ role: 'user', content: question });
  input.value = '';
  loading.value = true;

  await nextTick();

  // Check if this looks like a command
  if (looksCmd(question)) {
    loading.value = false;
    await detectCmd(messages.value.length - 1);
    return;
  }

  try {
    const history = messages.value
      .filter((msg) => msg.role === 'user' || msg.role === 'assistant')
      .slice(0, -1)
      .map((msg) => ({ role: msg.role, content: msg.content }));
    const result = await sendAiQuery(question, history) as {
      reply: string;
      error?: string;
      data_source?: string;
      diagnostic?: Record<string, unknown>;
    };
    messages.value.push({
      role: 'assistant',
      content: result.reply,
      dataSource: result.data_source,
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

async function detectCmd(idx: number) {
  const user = messages.value[idx];
  if (!user) return;
  const isBulk = bulkKw.some((k) => user.content.includes(k));
  const hasActuator = actuatorKw.some((k) => user.content.includes(k));
  const hasDevice = /[aA]\d{3}|槽位\d+|bearpi/i.test(user.content);
  // 当包含执行器关键词但没有指定设备时，默认对所有设备执行
  const shouldBulk = isBulk || (hasActuator && !hasDevice);
  const cmd: ChatMessage = { role: 'assistant', content: '正在解析指令…', commandStatus: 'confirming' };
  messages.value.splice(idx + 1, 0, cmd);

  try {
    if (shouldBulk) {
      const intent = parseBulkIntent(user.content);
      if (intent) {
        const al = intent.actuator === 'motor' ? '电机' : '补光灯';
        const ml = intent.mode === 'on' ? '打开' : intent.mode === 'off' ? '关闭' : '自动';
        cmd.content = `检测到批量控制指令: ${al} ${ml}（全部设备）`;
        cmd.command = { detected: true, actuator: intent.actuator, mode: intent.mode, device_sn: '全部设备', explanation: `批量${al}${ml}`, _bulk: true } as AiCommandResult & { _bulk: boolean };
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
      }
    }
  } catch {
    cmd.content = '指令解析失败';
    cmd.commandStatus = 'error';
  }
}

async function execCmd(idx: number) {
  if (!auth.canCommand) {
    uni.showToast({ title: '当前角色无权下发指令', icon: 'none' });
    return;
  }
  const cmd = messages.value[idx];
  if (!cmd?.command) return;
  cmd.commandStatus = 'executing';
  cmd.content = '正在执行…';

  try {
    const { actuator, mode } = cmd.command;
    const isBulk = cmd.command._bulk;

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
}

function rejectCmd(idx: number) {
  const m = messages.value[idx];
  if (m) {
    m.commandStatus = 'rejected';
    m.content = '已取消';
  }
}

function useExample(question: string) {
  input.value = question;
  nextTick(() => send());
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

  <wd-popup v-model="visible" position="bottom" closable custom-style="max-height: 85vh; padding: 0; border-radius: 28rpx 28rpx 0 0; background: #f7f8fa; overflow: hidden;">
    <view class="ai-query">
      <view class="ai-query-title">
        <text>AI智能问答</text>
      </view>

      <scroll-view class="chat-body" scroll-y :scroll-into-view="messages.length ? 'msg-' + (messages.length - 1) : ''">
        <view v-if="messages.length === 0" class="chat-welcome">
          <text class="welcome-title">你好,我是实验室AI助手</text>
          <text class="welcome-sub">今天想了解什么?</text>
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
            <template v-if="msg.role === 'user'">
              <text selectable>{{ msg.content }}</text>
            </template>
            <template v-else>
              <MarkdownMessage :content="msg.content" :data-source="msg.dataSource" />
              <view v-if="msg.diagnostic" class="diagnostic-box">
                <text class="diagnostic-title">调试信息</text>
                <text class="diagnostic-text">{{ formatDiagnostic(msg.diagnostic) }}</text>
              </view>
              <view v-if="msg.command?.detected && msg.commandStatus === 'confirming'" class="cmd-confirm">
                <view class="cmd-btns">
                  <wd-button size="small" type="primary" @click="execCmd(index)">确认执行</wd-button>
                  <wd-button size="small" plain @click="rejectCmd(index)">取消</wd-button>
                </view>
              </view>
            </template>
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
  height: 72vh;
  background: #f7f8fa;
}

.ai-query-title {
  padding: 28rpx 28rpx 18rpx;
  border-bottom: 1rpx solid #dde3eb;
  background: rgba(255, 255, 255, 0.78);

  text {
    color: #101828;
    font-size: 30rpx;
    font-weight: 700;
  }
}

.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 24rpx 24rpx 8rpx;
  box-sizing: border-box;
}

.chat-welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12rpx;
  padding: 96rpx 16rpx 32rpx;
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
  margin-top: 20rpx;
}

.example-list :deep(.wd-button) {
  min-height: 60rpx;
  border-color: #d8dee8;
  border-radius: 999rpx;
  background: #ffffff;
  color: #344054;
  font-size: 24rpx;
}

.chat-message {
  display: flex;
  margin-bottom: 18rpx;
}

.chat-message.user { justify-content: flex-end; }
.chat-message.assistant { justify-content: flex-start; }

.message-bubble {
  max-width: 85%;
  padding: 20rpx 24rpx;
  border-radius: 28rpx;
  line-height: 1.6;
  box-shadow: 0 2rpx 6rpx rgba(16, 24, 40, 0.05);
}

.chat-message.user .message-bubble {
  background: #0a84ff;
  border-bottom-right-radius: 10rpx;

  text {
    color: #ffffff;
    font-size: 26rpx;
    white-space: pre-wrap;
    word-wrap: break-word;
  }
}

.chat-message.assistant .message-bubble {
  background: #ffffff;
  border: 1rpx solid #e5e9f0;
  border-bottom-left-radius: 10rpx;
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

.diagnostic-box {
  margin-top: 14rpx;
  padding: 14rpx;
  border-radius: 16rpx;
  background: #f2f4f7;
}

.diagnostic-title {
  display: block;
  color: #b54708;
  font-size: 22rpx;
  font-weight: 700;
  margin-bottom: 6rpx;
}

.diagnostic-text {
  display: block;
  color: #667085;
  font-size: 22rpx;
  line-height: 1.5;
}

.chat-input {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
  padding: 18rpx 24rpx 24rpx;
  border-top: 1rpx solid #dde3eb;
  background: rgba(247, 248, 250, 0.94);
}

.input-row {
  display: flex;
  gap: 14rpx;
  align-items: center;
}

.chat-input-field {
  flex: 1;
  height: 76rpx;
  padding: 0 24rpx;
  border: 1rpx solid #d8dee8;
  border-radius: 20rpx;
  background: #ffffff;
  color: #101828;
  font-size: 26rpx;
  box-shadow: 0 2rpx 5rpx rgba(16, 24, 40, 0.04);
}

.chat-input :deep(.wd-button) {
  border-radius: 18rpx;
}

.input-row :deep(.wd-button) {
  min-width: 112rpx;
  height: 76rpx;
  flex-shrink: 0;
  font-weight: 700;
}

.cmd-confirm {
  margin-top: 16rpx;
  padding-top: 16rpx;
  border-top: 1rpx solid #e5e9f0;
}

.cmd-btns {
  display: flex;
  gap: 16rpx;
}
</style>
