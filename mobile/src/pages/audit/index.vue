<script setup lang="ts">
import { computed, ref } from 'vue';
import { onPullDownRefresh, onShow } from '@dcloudio/uni-app';
import { fetchAuditLogs } from '@/api/lab';
import { useAuthStore } from '@/stores/auth';
import type { AuditLog } from '@/types/domain';
import { formatDateTime } from '@/utils/format';

const auth = useAuthStore();
const logs = ref<AuditLog[]>([]);
const loading = ref(false);
const error = ref('');
const actionFilter = ref('');

const actionOptions = [
  { label: '全部', value: '' },
  { label: '登录', value: 'login' },
  { label: '注册', value: 'register' },
  { label: '权限', value: 'role_update' },
  { label: '指令', value: 'command_create' },
  { label: '回执', value: 'command_ack' },
  { label: '告警', value: 'alarm_ack' },
  { label: '规则', value: 'rule_update' }
];

const actionLabel: Record<string, string> = {
  login: '登录',
  register: '注册',
  role_update: '权限',
  command_create: '指令',
  command_ack: '回执',
  alarm_ack: '告警',
  rule_update: '规则'
};

const stats = computed(() => ({
  total: logs.value.length,
  command: logs.value.filter((item) => item.action === 'command_create' || item.action === 'command_ack').length,
  rule: logs.value.filter((item) => item.action === 'rule_update').length
}));

onShow(() => {
  if (!auth.canManageUsers) {
    uni.showToast({ title: '仅管理员可查看审计日志', icon: 'none' });
    uni.switchTab({ url: '/pages/dashboard/index' });
    return;
  }
  void load();
});

onPullDownRefresh(async () => {
  if (!auth.canManageUsers) {
    uni.stopPullDownRefresh();
    return;
  }
  await load();
  uni.stopPullDownRefresh();
});

async function load() {
  loading.value = true;
  error.value = '';
  try {
    logs.value = await fetchAuditLogs({ action: actionFilter.value || undefined });
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '审计日志加载失败';
  } finally {
    loading.value = false;
  }
}

function selectAction(value: string) {
  actionFilter.value = value;
  void load();
}

function metadataText(log: AuditLog) {
  const text = JSON.stringify(log.metadata ?? {});
  return text === '{}' ? '无附加数据' : text;
}
</script>

<template>
  <view class="page">
    <view class="toolbar">
      <view>
        <text class="eyebrow">Audit Trail</text>
        <text class="title">审计日志</text>
        <text class="subtitle">移动端查看登录、指令、告警和规则变更。</text>
      </view>
      <wd-button size="small" plain :loading="loading" @click="load">刷新</wd-button>
    </view>

    <view v-if="error" class="notice error">{{ error }}</view>

    <view class="metric-grid">
      <view class="metric-card">
        <text>当前列表</text>
        <text>{{ stats.total }}</text>
      </view>
      <view class="metric-card">
        <text>指令链路</text>
        <text>{{ stats.command }}</text>
      </view>
      <view class="metric-card">
        <text>规则变更</text>
        <text>{{ stats.rule }}</text>
      </view>
    </view>

    <scroll-view class="filter-scroll" scroll-x>
      <view class="filter-row">
        <wd-button
          v-for="option in actionOptions"
          :key="option.value || 'all'"
          size="small"
          :type="actionFilter === option.value ? 'primary' : 'info'"
          :plain="actionFilter !== option.value"
          @click="selectAction(option.value)"
        >
          {{ option.label }}
        </wd-button>
      </view>
    </scroll-view>

    <view v-if="!loading && !logs.length" class="empty-state">暂无审计日志</view>
    <view v-else class="log-list">
      <view v-for="log in logs" :key="log.id" class="log-card">
        <view class="log-head">
          <wd-tag type="primary">{{ actionLabel[log.action] ?? log.action }}</wd-tag>
          <text>{{ formatDateTime(log.createdAt) }}</text>
        </view>
        <text class="target">{{ log.target }}</text>
        <text class="detail">{{ log.detail }}</text>
        <view class="kv">
          <text>操作者</text>
          <text>{{ log.actorName }}</text>
        </view>
        <view class="kv">
          <text>IP</text>
          <text>{{ log.ipAddress ?? '未知' }}</text>
        </view>
        <text class="metadata">{{ metadataText(log) }}</text>
      </view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.page {
  min-height: 100vh;
  padding: 24rpx;
  box-sizing: border-box;
}

.toolbar,
.log-card {
  padding: 24rpx;
  border: 1rpx solid $uni-border-color;
  border-radius: 10rpx;
  background: #ffffff;
}

.toolbar,
.log-head,
.kv {
  display: flex;
  justify-content: space-between;
  gap: 16rpx;
}

.eyebrow,
.title,
.subtitle,
.target,
.detail,
.metadata {
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

.subtitle {
  margin-top: 6rpx;
  color: $uni-text-color-grey;
  font-size: 24rpx;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12rpx;
  margin: 18rpx 0;
}

.metric-card {
  padding: 18rpx;
  border: 1rpx solid $uni-border-color;
  border-radius: 8rpx;
  background: #ffffff;

  text {
    display: block;
  }

  text:first-child {
    color: $uni-text-color-grey;
    font-size: 22rpx;
  }

  text:last-child {
    margin-top: 8rpx;
    color: #172033;
    font-size: 36rpx;
    font-weight: 800;
  }
}

.filter-scroll {
  white-space: nowrap;
}

.filter-row {
  display: inline-flex;
  gap: 12rpx;
  padding-bottom: 8rpx;
}

.log-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
  margin-top: 16rpx;
}

.log-head {
  align-items: center;
  color: $uni-text-color-grey;
  font-size: 22rpx;
}

.target {
  margin-top: 18rpx;
  color: #172033;
  font-size: 30rpx;
  font-weight: 800;
}

.detail {
  margin-top: 8rpx;
  color: $uni-text-color;
  font-size: 26rpx;
}

.kv {
  margin-top: 12rpx;
  color: $uni-text-color-grey;
  font-size: 24rpx;

  text:last-child {
    color: #172033;
  }
}

.metadata {
  margin-top: 14rpx;
  padding: 14rpx;
  border-radius: 8rpx;
  color: $uni-text-color-grey;
  background: #f8fafc;
  font-size: 22rpx;
  word-break: break-all;
}

.notice,
.empty-state {
  margin-top: 18rpx;
  padding: 18rpx;
  border-radius: 8rpx;
  font-size: 24rpx;
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
