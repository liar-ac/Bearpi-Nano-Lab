<script setup lang="ts">
import { computed, ref } from 'vue';
import { onLoad, onPullDownRefresh } from '@dcloudio/uni-app';
import { fetchCommands, fetchDevice, sendCommand } from '@/api/lab';
import { useAuthStore } from '@/stores/auth';
import type { CommandPayload, CommandResult, Device, Sensor } from '@/types/domain';
import { formatDateTime, formatValue, relativeTime, statusLabel } from '@/utils/format';

const auth = useAuthStore();
const deviceId = ref<number | null>(null);
const device = ref<Device | null>(null);
const commandLogs = ref<CommandResult[]>([]);
const loading = ref(false);
const commandLoading = ref(false);
const error = ref('');
const motorMode = ref<'auto' | 'on' | 'off'>('auto');
const lightMode = ref<'auto' | 'on' | 'off'>('auto');

const sensorRows = computed(() => device.value?.sensors ?? []);
const environmentSensors = computed(() =>
  sensorRows.value.filter((sensor) => !['motor', 'fan', 'ventilation', 'lamp', 'led'].includes(sensor.code))
);
const actuatorSensors = computed(() =>
  sensorRows.value.filter((sensor) => ['motor', 'fan', 'ventilation', 'lamp', 'led'].includes(sensor.code))
);

onLoad((query) => {
  const id = Number(query?.id);
  if (!Number.isFinite(id)) {
    error.value = '设备 ID 无效';
    return;
  }
  deviceId.value = id;
  void load();
});

onPullDownRefresh(async () => {
  await load();
  uni.stopPullDownRefresh();
});

async function load() {
  if (!deviceId.value) return;
  loading.value = true;
  error.value = '';
  try {
    device.value = await fetchDevice(deviceId.value);
    commandLogs.value = await fetchCommands(deviceId.value);
    syncActuatorState(commandLogs.value);
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '设备详情加载失败';
  } finally {
    loading.value = false;
  }
}

function sensorThreshold(sensor: Sensor) {
  const parts = [];
  if (typeof sensor.min === 'number') parts.push(`下限 ${formatValue(sensor.min, sensor.unit)}`);
  if (typeof sensor.max === 'number') parts.push(`上限 ${formatValue(sensor.max, sensor.unit)}`);
  return parts.length ? parts.join(' / ') : '未设置';
}

function sensorState(sensor: Sensor) {
  const value = sensor.latest?.value;
  if (typeof value !== 'number') return '未知';
  if (typeof sensor.max === 'number' && value > sensor.max) return '越界';
  if (typeof sensor.min === 'number' && value < sensor.min) return '越界';
  return '正常';
}

function sensorTagType(sensor: Sensor) {
  const state = sensorState(sensor);
  return state === '正常' ? 'success' : state === '未知' ? 'primary' : 'danger';
}

function openRealtime(sensor: Sensor) {
  if (!device.value) return;
  uni.navigateTo({ url: `/pages/sensors/realtime?deviceId=${device.value.id}&sensorId=${sensor.id}` });
}

function openHistory(sensor: Sensor) {
  if (!device.value) return;
  uni.navigateTo({ url: `/pages/sensors/history?deviceId=${device.value.id}&sensorId=${sensor.id}` });
}

async function runCommand(payload: CommandPayload, displayName: string) {
  if (!auth.canCommand) {
    uni.showToast({ title: '当前角色没有指令下发权限', icon: 'none' });
    return null;
  }
  if (!device.value || commandLoading.value) return null;
  const confirmed = await showConfirm(`确认向 ${device.value.sn} 下发「${displayName}」指令？`);
  if (!confirmed) return null;

  commandLoading.value = true;
  try {
    const result = await sendCommand(device.value.id, payload);
    commandLogs.value = [result, ...commandLogs.value].slice(0, 20);
    uni.showToast({ title: result.message || '指令已下发', icon: 'success' });
    return result;
  } catch (cause) {
    uni.showToast({ title: cause instanceof Error ? cause.message : '指令下发失败', icon: 'none' });
    return null;
  } finally {
    commandLoading.value = false;
  }
}

async function setActuatorOverride(key: 'motor_override' | 'light_override', mode: 'auto' | 'on' | 'off') {
  const label = key === 'motor_override' ? '通风电机' : '补光灯';
  const result = await runCommand({ type: 'set_param', params: { [key]: mode } }, `${label}${modeLabel(mode)}`);
  if (!result) return;
  if (key === 'motor_override') motorMode.value = mode;
  if (key === 'light_override') lightMode.value = mode;
}

function showConfirm(content: string) {
  return new Promise<boolean>((resolve) => {
    uni.showModal({
      title: '设备指令确认',
      content,
      confirmText: '确认',
      cancelText: '取消',
      success: (res) => resolve(res.confirm),
      fail: () => resolve(false)
    });
  });
}

function syncActuatorState(logs: CommandResult[]) {
  for (const command of logs) {
    if (command.command !== 'set_param' || !command.params) continue;
    const motor = command.params.motor_override;
    const light = command.params.light_override;
    if (motor === 'auto' || motor === 'on' || motor === 'off') motorMode.value = motor;
    if (light === 'auto' || light === 'on' || light === 'off') lightMode.value = light;
  }
}

function modeLabel(mode: 'auto' | 'on' | 'off') {
  return mode === 'auto' ? '自动' : mode === 'on' ? '强制开' : '强制关';
}

function commandText(command: CommandResult) {
  if (command.command === 'reboot') return '重启';
  if (command.command === 'upgrade') return '固件升级';
  if (!command.params) return '参数设置';
  const parts = [];
  if (command.params.sample_rate) parts.push(`采样率 ${command.params.sample_rate}s`);
  if (command.params.motor_override) parts.push(`电机${modeLabel(command.params.motor_override as 'auto' | 'on' | 'off')}`);
  if (command.params.light_override) parts.push(`补光灯${modeLabel(command.params.light_override as 'auto' | 'on' | 'off')}`);
  return parts.length ? parts.join(' / ') : '参数设置';
}
</script>

<template>
  <view class="page">
    <view v-if="error" class="notice">{{ error }}</view>
    <wd-loadmore v-if="loading && !device" state="loading" />

    <template v-if="device">
      <view class="hero">
        <view class="hero-top">
          <view>
            <text class="title">{{ device.sn }}</text>
            <text class="subtitle">槽位 {{ device.slotNo }} / {{ device.model }} / {{ device.location }}</text>
          </view>
          <wd-tag :type="device.status === 'online' ? 'success' : device.status === 'warning' ? 'danger' : device.status === 'maintenance' ? 'warning' : 'primary'">
            {{ statusLabel[device.status] }}
          </wd-tag>
        </view>
        <view class="meta-grid">
          <view>
            <text>负责人</text>
            <text>{{ device.member }}</text>
          </view>
          <view>
            <text>采样率</text>
            <text>{{ device.sampleRate }} 秒</text>
          </view>
          <view>
            <text>最近上报</text>
            <text>{{ relativeTime(device.lastSeen) }}</text>
          </view>
          <view>
            <text>IP</text>
            <text>{{ device.ipAddress ?? '未登记' }}</text>
          </view>
        </view>
      </view>

      <view class="info-card">
        <view class="section-title">
          <text>设备上下文</text>
          <text>{{ device.labId }}</text>
        </view>
        <view class="kv">
          <text>注册时间</text>
          <text>{{ formatDateTime(device.registerTime) }}</text>
        </view>
        <view class="kv">
          <text>固件版本</text>
          <text>{{ device.firmwareVersion }}</text>
        </view>
        <view class="kv">
          <text>异常原因</text>
          <text>{{ device.abnormalReason ?? '无异常' }}</text>
        </view>
        <view class="kv">
          <text>数据链路</text>
          <text>HTTP上报到后端</text>
        </view>
      </view>

      <view class="info-card">
        <view class="section-title">
          <text>设备指令</text>
          <text>{{ auth.canCommand ? '可下发' : '只读' }}</text>
        </view>
        <view class="command-grid">
          <wd-button size="small" type="error" plain :disabled="!auth.canCommand" :loading="commandLoading" @click="runCommand({ type: 'reboot' }, '重启')">重启</wd-button>
          <wd-button size="small" type="warning" plain :disabled="!auth.canCommand" :loading="commandLoading" @click="runCommand({ type: 'upgrade' }, '升级固件')">升级固件</wd-button>
          <wd-button size="small" type="primary" plain :disabled="!auth.canCommand" :loading="commandLoading" @click="runCommand({ type: 'set_param', params: { sample_rate: 1 } }, '设置采样率')">采样 1s</wd-button>
        </view>
        <view v-if="!auth.canCommand" class="hint">当前角色可以查看设备数据，不能下发设备指令。</view>
      </view>

      <view class="info-card">
        <view class="section-title">
          <text>执行器覆盖</text>
          <text>IA1 策略</text>
        </view>
        <view class="actuator-panel">
          <view>
            <text class="sensor-name">通风电机</text>
            <text class="sensor-code">温度 > 32℃ 或湿度 > 75% 时自动开启</text>
          </view>
          <view class="mode-row">
            <wd-button size="small" :type="motorMode === 'auto' ? 'primary' : 'info'" :plain="motorMode !== 'auto'" :disabled="!auth.canCommand" @click="setActuatorOverride('motor_override', 'auto')">自动</wd-button>
            <wd-button size="small" :type="motorMode === 'on' ? 'success' : 'info'" :plain="motorMode !== 'on'" :disabled="!auth.canCommand" @click="setActuatorOverride('motor_override', 'on')">开</wd-button>
            <wd-button size="small" :type="motorMode === 'off' ? 'error' : 'info'" :plain="motorMode !== 'off'" :disabled="!auth.canCommand" @click="setActuatorOverride('motor_override', 'off')">关</wd-button>
          </view>
        </view>
        <view class="actuator-panel">
          <view>
            <text class="sensor-name">补光灯</text>
            <text class="sensor-code">光照 < 20lx 时自动开启</text>
          </view>
          <view class="mode-row">
            <wd-button size="small" :type="lightMode === 'auto' ? 'primary' : 'info'" :plain="lightMode !== 'auto'" :disabled="!auth.canCommand" @click="setActuatorOverride('light_override', 'auto')">自动</wd-button>
            <wd-button size="small" :type="lightMode === 'on' ? 'success' : 'info'" :plain="lightMode !== 'on'" :disabled="!auth.canCommand" @click="setActuatorOverride('light_override', 'on')">开</wd-button>
            <wd-button size="small" :type="lightMode === 'off' ? 'error' : 'info'" :plain="lightMode !== 'off'" :disabled="!auth.canCommand" @click="setActuatorOverride('light_override', 'off')">关</wd-button>
          </view>
        </view>
        <view v-if="actuatorSensors.length" class="actuator-telemetry">
          <view v-for="sensor in actuatorSensors" :key="sensor.id" class="kv compact">
            <text>{{ sensor.name }}</text>
            <text>{{ formatValue(sensor.latest?.value, sensor.unit) }}</text>
          </view>
        </view>
      </view>

      <view class="section-title sensor-heading">
        <text>传感器</text>
        <text>{{ environmentSensors.length }} 项</text>
      </view>
      <view v-if="!environmentSensors.length" class="empty-state">暂无传感器</view>
      <view v-else class="sensor-list">
        <view v-for="sensor in environmentSensors" :key="sensor.id" class="sensor-card">
          <view class="sensor-top">
            <view>
              <text class="sensor-name">{{ sensor.name }}</text>
              <text class="sensor-code">{{ sensor.code }} / {{ sensor.description }}</text>
            </view>
            <wd-tag :type="sensorTagType(sensor)">{{ sensorState(sensor) }}</wd-tag>
          </view>
          <view class="sensor-value">
            <text>{{ formatValue(sensor.latest?.value, sensor.unit) }}</text>
            <text>{{ formatDateTime(sensor.latest?.ts) }}</text>
          </view>
          <view class="kv compact">
            <text>阈值</text>
            <text>{{ sensorThreshold(sensor) }}</text>
          </view>
          <view class="sensor-actions">
            <wd-button size="small" type="primary" plain @click="openRealtime(sensor)">实时</wd-button>
            <wd-button size="small" plain @click="openHistory(sensor)">历史</wd-button>
          </view>
        </view>
      </view>

      <view class="info-card command-card">
        <view class="section-title">
          <text>指令记录</text>
          <text>{{ commandLogs.length }} 条</text>
        </view>
        <view v-if="!commandLogs.length" class="empty-state">暂无指令记录</view>
        <view v-else class="command-list">
          <view v-for="command in commandLogs.slice(0, 8)" :key="command.id" class="command-row">
            <view>
              <text class="sensor-name">{{ commandText(command) }}</text>
              <text class="sensor-code">{{ command.message }}</text>
            </view>
            <wd-tag :type="command.status === 'failed' ? 'danger' : command.status === 'queued' ? 'warning' : 'success'">
              {{ command.status }}
            </wd-tag>
          </view>
        </view>
      </view>
    </template>
  </view>
</template>

<style lang="scss" scoped>
.page {
  min-height: 100vh;
  padding: 24rpx;
  box-sizing: border-box;
}

.hero,
.info-card,
.sensor-card {
  padding: 24rpx;
  border: 1rpx solid $uni-border-color;
  border-radius: 8rpx;
  background: #ffffff;
}

.hero-top,
.section-title,
.sensor-top,
.kv {
  display: flex;
  justify-content: space-between;
  gap: 20rpx;
}

.title,
.subtitle {
  display: block;
}

.title {
  color: #172033;
  font-size: 36rpx;
  font-weight: 800;
}

.subtitle {
  margin-top: 8rpx;
  color: $uni-text-color-grey;
  font-size: 24rpx;
}

.meta-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16rpx;
  margin-top: 24rpx;

  view {
    display: flex;
    flex-direction: column;
    gap: 6rpx;
    padding: 16rpx;
    border-radius: 6rpx;
    background: #f7f9fc;
  }

  text:first-child {
    color: $uni-text-color-grey;
    font-size: 22rpx;
  }

  text:last-child {
    color: #172033;
    font-size: 26rpx;
    font-weight: 700;
  }
}

.info-card {
  margin-top: 20rpx;
}

.command-grid,
.mode-row,
.sensor-actions {
  display: flex;
  gap: 12rpx;
  flex-wrap: wrap;
}

.hint {
  margin-top: 16rpx;
  color: $uni-text-color-grey;
  font-size: 24rpx;
}

.actuator-panel,
.command-row {
  display: flex;
  justify-content: space-between;
  gap: 20rpx;
  padding: 18rpx 0;
  border-top: 1rpx solid #f0f2f5;
}

.actuator-telemetry {
  margin-top: 8rpx;
}

.section-title {
  align-items: center;
  margin-bottom: 18rpx;

  text:first-child {
    color: #172033;
    font-size: 30rpx;
    font-weight: 700;
  }

  text:last-child {
    color: $uni-text-color-grey;
    font-size: 24rpx;
  }
}

.sensor-heading {
  margin-top: 28rpx;
}

.kv {
  padding: 12rpx 0;
  border-top: 1rpx solid #f0f2f5;
  color: $uni-text-color-grey;
  font-size: 24rpx;

  text:last-child {
    color: #172033;
    text-align: right;
  }
}

.compact {
  padding-bottom: 0;
}

.sensor-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.sensor-name,
.sensor-code {
  display: block;
}

.sensor-name {
  color: #172033;
  font-size: 28rpx;
  font-weight: 700;
}

.sensor-code {
  margin-top: 6rpx;
  color: $uni-text-color-grey;
  font-size: 22rpx;
}

.sensor-value {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin: 20rpx 0 8rpx;

  text:first-child {
    color: #172033;
    font-size: 42rpx;
    font-weight: 800;
  }

  text:last-child {
    color: $uni-text-color-grey;
    font-size: 22rpx;
  }
}

.sensor-actions {
  margin-top: 18rpx;
}

.command-card {
  margin-top: 20rpx;
}

.command-list {
  display: flex;
  flex-direction: column;
}

.notice {
  margin-bottom: 18rpx;
  padding: 18rpx;
  border-radius: 6rpx;
  color: #b42318;
  background: #fff1f0;
  font-size: 24rpx;
}

.empty-state {
  padding: 56rpx 24rpx;
  border: 1rpx dashed $uni-border-color;
  border-radius: 8rpx;
  color: $uni-text-color-grey;
  background: #ffffff;
  text-align: center;
  font-size: 26rpx;
}
</style>
