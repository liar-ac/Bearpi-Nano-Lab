<script setup lang="ts">
import { ref } from 'vue';
import { onPullDownRefresh, onShow } from '@dcloudio/uni-app';
import { fetchAccountUsers, updateAccountUserRole } from '@/api/lab';
import { useAuthStore } from '@/stores/auth';
import type { AccountUser, UserRole } from '@/types/domain';
import { formatDateTime, roleLabel } from '@/utils/format';

const auth = useAuthStore();
const users = ref<AccountUser[]>([]);
const loading = ref(false);
const error = ref('');

const roleOptions: Array<{ label: string; value: UserRole; detail: string }> = [
  { label: '只读', value: 'viewer', detail: '只能查看数据' },
  { label: '实验员', value: 'experimenter', detail: '可确认告警、下发指令' },
  { label: '管理员', value: 'admin', detail: '可管理权限' }
];

onShow(() => {
  if (!auth.canManageUsers) {
    uni.showToast({ title: '仅管理员可访问用户权限', icon: 'none' });
    uni.switchTab({ url: '/pages/dashboard/index' });
    return;
  }
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
    users.value = await fetchAccountUsers();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '用户列表加载失败';
  } finally {
    loading.value = false;
  }
}

async function changeRole(user: AccountUser, role: UserRole) {
  if (user.role === role) return;
  const confirmed = await showConfirm(`确认把 ${user.username} 的权限调整为「${roleLabel[role]}」？`);
  if (!confirmed) return;

  try {
    const next = await updateAccountUserRole(user.id, role);
    users.value = users.value.map((item) => (item.id === next.id ? next : item));
    uni.showToast({ title: '权限已更新', icon: 'success' });
  } catch (cause) {
    uni.showToast({ title: cause instanceof Error ? cause.message : '权限更新失败', icon: 'none' });
  }
}

function showConfirm(content: string) {
  return new Promise<boolean>((resolve) => {
    uni.showModal({
      title: '权限调整',
      content,
      confirmText: '确认',
      cancelText: '取消',
      success: (res) => resolve(res.confirm),
      fail: () => resolve(false)
    });
  });
}

function roleType(role: UserRole) {
  if (role === 'admin') return 'danger';
  if (role === 'experimenter') return 'warning';
  return 'primary';
}

function roleButtonType(role: UserRole) {
  if (role === 'admin') return 'error';
  if (role === 'experimenter') return 'warning';
  return 'primary';
}
</script>

<template>
  <view class="page">
    <view class="hero">
      <text class="eyebrow">Access Control</text>
      <text class="title">用户权限</text>
      <text class="copy">新注册账号默认为只读，管理员可按实验需要升级权限。</text>
    </view>

    <view class="role-grid">
      <view v-for="option in roleOptions" :key="option.value" class="role-card">
        <text>{{ option.label }}</text>
        <text>{{ users.filter((user) => user.role === option.value).length }}</text>
        <text>{{ option.detail }}</text>
      </view>
    </view>

    <view v-if="error" class="notice error">{{ error }}</view>

    <view class="user-list">
      <view v-for="user in users" :key="user.id" class="user-card">
        <view class="user-top">
          <view>
            <text class="name">{{ user.name || user.username }}</text>
            <text class="meta">{{ user.username }} / {{ formatDateTime(user.createdAt) }}</text>
          </view>
          <wd-tag :type="roleType(user.role)">{{ roleLabel[user.role] }}</wd-tag>
        </view>
        <view class="mode-row">
          <wd-button
            v-for="option in roleOptions"
            :key="option.value"
            size="small"
            :type="user.role === option.value ? roleButtonType(option.value) : 'info'"
            :plain="user.role !== option.value"
            @click="changeRole(user, option.value)"
          >
            {{ option.label }}
          </wd-button>
        </view>
      </view>
    </view>
    <wd-loadmore v-if="loading || users.length" :state="loading ? 'loading' : 'finished'" />
  </view>
</template>

<style lang="scss" scoped>
.page {
  min-height: 100vh;
  padding: 24rpx;
  box-sizing: border-box;
}

.hero,
.role-card,
.user-card {
  padding: 24rpx;
  border: 1rpx solid $uni-border-color;
  border-radius: 8rpx;
  background: #ffffff;
}

.eyebrow,
.title,
.copy,
.name,
.meta {
  display: block;
}

.eyebrow {
  color: $uni-color-primary;
  font-size: 22rpx;
  font-weight: 700;
}

.title {
  margin-top: 8rpx;
  color: #172033;
  font-size: 36rpx;
  font-weight: 800;
}

.copy {
  margin-top: 8rpx;
  color: $uni-text-color-grey;
  font-size: 24rpx;
}

.role-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14rpx;
  margin: 20rpx 0;
}

.role-card {
  display: flex;
  flex-direction: column;
  gap: 6rpx;

  text:first-child,
  text:last-child {
    color: $uni-text-color-grey;
    font-size: 22rpx;
  }

  text:nth-child(2) {
    color: #172033;
    font-size: 40rpx;
    font-weight: 800;
  }
}

.user-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.user-top {
  display: flex;
  justify-content: space-between;
  gap: 18rpx;
  align-items: center;
}

.name {
  color: #172033;
  font-size: 30rpx;
  font-weight: 700;
}

.meta {
  margin-top: 6rpx;
  color: $uni-text-color-grey;
  font-size: 22rpx;
}

.mode-row {
  display: flex;
  gap: 12rpx;
  flex-wrap: wrap;
  margin-top: 20rpx;
}

.notice {
  margin-bottom: 18rpx;
  padding: 18rpx;
  border-radius: 6rpx;
  font-size: 24rpx;
}

.error {
  color: #b42318;
  background: #fff1f0;
}
</style>
