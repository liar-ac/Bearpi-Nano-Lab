<script setup lang="ts">
import { computed, reactive, ref } from 'vue';
import { onPullDownRefresh, onShow } from '@dcloudio/uni-app';
import { fetchRules, updateRule } from '@/api/lab';
import { useAuthStore } from '@/stores/auth';
import type { RuleConfig } from '@/types/domain';
import { formatValue } from '@/utils/format';

const auth = useAuthStore();
const rules = ref<RuleConfig[]>([]);
const loading = ref(false);
const savingId = ref<number | null>(null);
const error = ref('');
const drafts = reactive<Record<number, { min: string; max: string }>>({});

const connectedDevices = computed(() => {
  const byDevice = new Map<number, { id: number; name: string; slotNo: number; sampleRate: number; ruleCount: number }>();
  for (const rule of rules.value) {
    const current = byDevice.get(rule.deviceId);
    if (current) {
      current.ruleCount += 1;
    } else {
      byDevice.set(rule.deviceId, {
        id: rule.deviceId,
        name: rule.deviceName,
        slotNo: rule.slotNo,
        sampleRate: rule.sampleRate,
        ruleCount: 1
      });
    }
  }
  return [...byDevice.values()].sort((a, b) => a.slotNo - b.slotNo);
});

const slotMap = computed(() => {
  const bySlot = new Map(connectedDevices.value.map((device) => [device.slotNo, device]));
  return Array.from({ length: 120 }, (_, index) => {
    const slotNo = index + 1;
    return { slotNo, device: bySlot.get(slotNo) };
  });
});

const sortedRules = computed(() =>
  [...rules.value].sort((a, b) => a.slotNo - b.slotNo || a.deviceName.localeCompare(b.deviceName) || a.id - b.id)
);

const stats = computed(() => ({
  devices: connectedDevices.value.length,
  total: rules.value.length,
  complete: rules.value.filter((item) => item.min !== null && item.max !== null).length,
  partial: rules.value.filter((item) => (item.min === null) !== (item.max === null)).length
}));

onShow(() => {
  void load();
});

onPullDownRefresh(async () => {
  await load();
  uni.stopPullDownRefresh();
});

async function load() {
  loading.value = true;
  error.value = '';
  try {
    rules.value = await fetchRules();
    for (const rule of rules.value) {
      drafts[rule.id] = {
        min: rule.min === null ? '' : String(rule.min),
        max: rule.max === null ? '' : String(rule.max)
      };
    }
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '规则配置加载失败';
  } finally {
    loading.value = false;
  }
}

async function save(rule: RuleConfig) {
  if (!auth.canCommand) {
    uni.showToast({ title: '当前角色没有规则配置权限', icon: 'none' });
    return;
  }
  const draft = drafts[rule.id];
  const min = parseOptionalNumber(draft.min);
  const max = parseOptionalNumber(draft.max);
  if (min !== null && max !== null && min >= max) {
    uni.showToast({ title: '上限必须大于下限', icon: 'none' });
    return;
  }
  savingId.value = rule.id;
  try {
    const next = await updateRule(rule.id, { min, max });
    rules.value = rules.value.map((item) => (item.id === rule.id ? next : item));
    drafts[next.id] = {
      min: next.min === null ? '' : String(next.min),
      max: next.max === null ? '' : String(next.max)
    };
    uni.showToast({ title: '规则已保存', icon: 'success' });
  } catch (cause) {
    uni.showToast({ title: cause instanceof Error ? cause.message : '保存失败', icon: 'none' });
  } finally {
    savingId.value = null;
  }
}

function parseOptionalNumber(value: string) {
  const text = value.trim();
  if (!text) return null;
  const parsed = Number(text);
  return Number.isFinite(parsed) ? parsed : null;
}

function ruleRange(rule: RuleConfig) {
  const min = rule.min === null ? '无下限' : formatValue(rule.min, rule.unit);
  const max = rule.max === null ? '无上限' : formatValue(rule.max, rule.unit);
  return `${min} - ${max}`;
}
</script>

<template>
  <view class="page">
    <view class="toolbar">
      <view>
        <text class="eyebrow">Rule Engine</text>
        <text class="title">规则配置</text>
        <text class="subtitle">只显示真实上报的板卡；未接入槽位保持空位。</text>
      </view>
      <wd-button size="small" plain :loading="loading" @click="load">刷新</wd-button>
    </view>

    <view v-if="!auth.canCommand" class="notice info">当前为只读权限：可以查看规则，不能修改阈值。</view>
    <view v-if="error" class="notice error">{{ error }}</view>

    <view class="metric-grid">
      <view class="metric-card">
        <text>实时接入</text>
        <text>{{ stats.devices }}</text>
      </view>
      <view class="metric-card">
        <text>规则总数</text>
        <text>{{ stats.total }}</text>
      </view>
      <view class="metric-card">
        <text>完整阈值</text>
        <text>{{ stats.complete }}</text>
      </view>
      <view class="metric-card">
        <text>单边阈值</text>
        <text>{{ stats.partial }}</text>
      </view>
    </view>

    <view class="card">
      <view class="section-title">
        <text>120 槽位接入图</text>
        <text>真实上报</text>
      </view>
      <view class="slot-grid">
        <view v-for="slot in slotMap" :key="slot.slotNo" class="slot" :class="{ connected: slot.device }">
          <text>{{ slot.slotNo }}</text>
          <text v-if="slot.device">{{ slot.device.name.replace('BEARPI-NANO-', '') }}</text>
        </view>
      </view>
    </view>

    <view class="section-title list-title">
      <text>接入板卡规则</text>
      <text>{{ sortedRules.length }} 条</text>
    </view>
    <view v-if="!loading && !sortedRules.length" class="empty-state">板子真实上报 telemetry 后，才会显示规则。</view>
    <view v-else class="rule-list">
      <view v-for="rule in sortedRules" :key="rule.id" class="rule-card">
        <view class="rule-head">
          <view>
            <text class="rule-device">{{ rule.deviceName }}</text>
            <text class="rule-meta">槽位 {{ rule.slotNo }} / 采样 {{ rule.sampleRate }}s</text>
          </view>
          <wd-tag type="primary">{{ rule.name }}</wd-tag>
        </view>
        <view class="kv">
          <text>当前阈值</text>
          <text>{{ ruleRange(rule) }}</text>
        </view>
        <view class="edit-row">
          <view class="field">
            <text>下限</text>
            <input v-model="drafts[rule.id].min" type="digit" :disabled="!auth.canCommand" placeholder="无" />
          </view>
          <view class="field">
            <text>上限</text>
            <input v-model="drafts[rule.id].max" type="digit" :disabled="!auth.canCommand" placeholder="无" />
          </view>
          <wd-button size="small" type="primary" :loading="savingId === rule.id" :disabled="!auth.canCommand" @click="save(rule)">
            保存
          </wd-button>
        </view>
      </view>
    </view>

    <view class="notice info">保存后，后续遥测进入后端时会按新的 min/max 判定告警；设备端无需重新登录。</view>
  </view>
</template>

<style lang="scss" scoped>
.page {
  min-height: 100vh;
  padding: 24rpx;
  box-sizing: border-box;
}

.toolbar,
.card,
.rule-card {
  padding: 24rpx;
  border: 1rpx solid $uni-border-color;
  border-radius: 10rpx;
  background: #ffffff;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  gap: 20rpx;
}

.eyebrow,
.title,
.subtitle,
.rule-device,
.rule-meta {
  display: block;
}

.eyebrow {
  color: $uni-color-primary;
  font-size: 22rpx;
  font-weight: 700;
}

.title {
  margin-top: 6rpx;
  color: #172033;
  font-size: 38rpx;
  font-weight: 800;
}

.subtitle,
.rule-meta {
  margin-top: 6rpx;
  color: $uni-text-color-grey;
  font-size: 24rpx;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12rpx;
  margin: 18rpx 0;
}

.metric-card {
  padding: 18rpx 12rpx;
  border: 1rpx solid $uni-border-color;
  border-radius: 8rpx;
  background: #ffffff;

  text {
    display: block;
    text-align: center;
  }

  text:first-child {
    color: $uni-text-color-grey;
    font-size: 21rpx;
  }

  text:last-child {
    margin-top: 8rpx;
    color: #172033;
    font-size: 34rpx;
    font-weight: 800;
  }
}

.section-title,
.rule-head,
.kv,
.edit-row {
  display: flex;
  justify-content: space-between;
  gap: 16rpx;
}

.section-title {
  align-items: center;
  margin-bottom: 16rpx;

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

.slot-grid {
  display: grid;
  grid-template-columns: repeat(10, minmax(0, 1fr));
  gap: 8rpx;
}

.slot {
  min-height: 56rpx;
  padding: 6rpx;
  border: 1rpx solid #eef1f5;
  border-radius: 6rpx;
  color: #b0b8c4;
  background: #f8fafc;

  text {
    display: block;
    overflow: hidden;
    font-size: 19rpx;
    line-height: 1.15;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.slot.connected {
  color: #1b5e20;
  border-color: #bfe7c2;
  background: #eef8ec;
}

.list-title {
  margin-top: 26rpx;
}

.rule-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.rule-device {
  color: #172033;
  font-size: 28rpx;
  font-weight: 800;
}

.kv {
  margin-top: 18rpx;
  padding-top: 14rpx;
  border-top: 1rpx solid #f0f2f5;
  color: $uni-text-color-grey;
  font-size: 24rpx;

  text:last-child {
    color: #172033;
  }
}

.edit-row {
  align-items: flex-end;
  margin-top: 18rpx;
}

.field {
  flex: 1;

  text {
    display: block;
    margin-bottom: 8rpx;
    color: $uni-text-color-grey;
    font-size: 22rpx;
  }

  input {
    height: 70rpx;
    padding: 0 16rpx;
    border: 1rpx solid $uni-border-color;
    border-radius: 8rpx;
    background: #f8fafc;
    color: #172033;
    font-size: 26rpx;
    box-sizing: border-box;
  }
}

.notice,
.empty-state {
  margin-top: 18rpx;
  padding: 18rpx;
  border-radius: 8rpx;
  font-size: 24rpx;
}

.info {
  color: #245d99;
  background: #eef7ff;
}

.error {
  color: #b42318;
  background: #fff1f0;
}

.empty-state {
  border: 1rpx dashed $uni-border-color;
  color: $uni-text-color-grey;
  background: #ffffff;
  text-align: center;
}
</style>
