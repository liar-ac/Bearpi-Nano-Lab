<script setup lang="ts">
import { ref } from 'vue';
import { onLoad } from '@dcloudio/uni-app';
import { useAuthStore } from '@/stores/auth';

const auth = useAuthStore();
const username = ref('');
const password = ref('');
const loading = ref(false);

onLoad(() => {
  if (auth.isAuthenticated) {
    uni.reLaunch({ url: '/pages/dashboard/index' });
  }
});

async function submit() {
  if (loading.value) return;
  if (!username.value.trim() || !password.value) {
    uni.showToast({ title: '请填写账号和密码', icon: 'none' });
    return;
  }

  loading.value = true;
  try {
    await auth.login(username.value.trim(), password.value);
    uni.showToast({ title: '登录成功', icon: 'success' });
    uni.reLaunch({ url: '/pages/dashboard/index' });
  } catch (cause) {
    uni.showToast({
      title: cause instanceof Error ? cause.message : '登录失败',
      icon: 'none'
    });
  } finally {
    loading.value = false;
  }
}

function goRegister() {
  uni.redirectTo({ url: '/pages/register/index' });
}
</script>

<template>
  <view class="login-page">
    <view class="login-hero">
      <text class="brand">BearPi Nano Lab</text>
      <text class="title">小熊派 Nano 实验室</text>
      <text class="subtitle">设备监控、后端接入、实时告警移动端</text>
      <view class="hero-tags">
        <text>JWT</text>
        <text>WebSocket</text>
        <text>HTTPJSON</text>
      </view>
    </view>

    <view class="login-panel">
      <view class="panel-title">
        <text>登录控制台</text>
        <text>Secure Console</text>
      </view>
      <wd-input
        v-model="username"
        label="账号"
        placeholder="admin / exp / lab / viewer"
        clearable
        custom-class="form-input"
      />
      <wd-input
        v-model="password"
        label="密码"
        placeholder="admin123"
        show-password
        clearable
        custom-class="form-input"
        @confirm="submit"
      />
      <wd-button block type="primary" size="large" :loading="loading" @click="submit">
        进入控制台
      </wd-button>
      <view class="login-note">
        <text>角色示例：admin 为管理员，exp/lab 为实验员，viewer 为只读。</text>
        <text>新账号注册后默认为只读，需要管理员升级权限。</text>
        <text class="login-link" @click="goRegister">注册新账号</text>
      </view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.login-page {
  min-height: 100vh;
  padding: 72rpx 32rpx 40rpx;
  box-sizing: border-box;
  background: linear-gradient(180deg, #eef7ff 0%, #f5f7fa 45%, #ffffff 100%);
}

.login-hero {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
  margin-bottom: 40rpx;
}

.brand {
  color: $uni-color-primary;
  font-size: 26rpx;
  font-weight: 700;
}

.title {
  color: #172033;
  font-size: 48rpx;
  font-weight: 800;
  line-height: 1.2;
}

.subtitle {
  color: $uni-text-color-grey;
  font-size: 28rpx;
}

.hero-tags {
  display: flex;
  gap: 12rpx;
  flex-wrap: wrap;
  margin-top: 8rpx;

  text {
    padding: 8rpx 16rpx;
    border: 1rpx solid rgba(64, 158, 255, 0.22);
    border-radius: 6rpx;
    color: #245d99;
    background: rgba(64, 158, 255, 0.08);
    font-size: 24rpx;
  }
}

.login-panel {
  padding: 32rpx;
  border: 1rpx solid $uni-border-color;
  border-radius: 12rpx;
  background: #ffffff;
  box-shadow: 0 16rpx 48rpx rgba(31, 45, 61, 0.08);
}

.panel-title {
  display: flex;
  flex-direction: column;
  gap: 6rpx;
  margin-bottom: 28rpx;

  text:first-child {
    color: #172033;
    font-size: 36rpx;
    font-weight: 700;
  }

  text:last-child {
    color: $uni-text-color-grey;
    font-size: 24rpx;
  }
}

.form-input {
  margin-bottom: 18rpx;
}

.login-note {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
  margin-top: 24rpx;
  color: $uni-text-color-grey;
  font-size: 24rpx;
  line-height: 1.5;
}

.login-link {
  color: $uni-color-primary;
  font-weight: 700;
}
</style>
