<script setup lang="ts">
import { ref } from 'vue';
import { onLoad } from '@dcloudio/uni-app';
import { useAuthStore } from '@/stores/auth';

const auth = useAuthStore();
const username = ref('');
const name = ref('');
const password = ref('');
const confirmPassword = ref('');
const loading = ref(false);

onLoad(() => {
  if (auth.isAuthenticated) {
    uni.reLaunch({ url: '/pages/dashboard/index' });
  }
});

async function submit() {
  if (!username.value.trim() || !password.value) {
    uni.showToast({ title: '请填写账号和密码', icon: 'none' });
    return;
  }
  if (password.value !== confirmPassword.value) {
    uni.showToast({ title: '两次输入的密码不一致', icon: 'none' });
    return;
  }

  loading.value = true;
  try {
    await auth.register({
      username: username.value.trim(),
      name: name.value.trim(),
      password: password.value
    });
    uni.showToast({ title: '注册成功', icon: 'success' });
    uni.reLaunch({ url: '/pages/dashboard/index' });
  } catch (cause) {
    uni.showToast({ title: cause instanceof Error ? cause.message : '注册失败', icon: 'none' });
  } finally {
    loading.value = false;
  }
}

function goLogin() {
  uni.redirectTo({ url: '/pages/login/index' });
}
</script>

<template>
  <view class="auth-page">
    <view class="auth-card">
      <view class="brand">
        <text>BearPi Nano Lab</text>
        <text>注册实验室账号</text>
      </view>
      <wd-input v-model="username" label="账号" placeholder="至少 3 位，登录时使用" clearable />
      <wd-input v-model="name" label="姓名" placeholder="可选，用于页面显示" clearable />
      <wd-input v-model="password" label="密码" placeholder="至少 6 位" show-password clearable />
      <wd-input v-model="confirmPassword" label="确认密码" placeholder="再次输入密码" show-password clearable @confirm="submit" />
      <wd-button block type="primary" size="large" :loading="loading" @click="submit">创建只读账号</wd-button>
      <view class="note">
        <text>新注册账号只能查看设备、告警、历史和实时数据。</text>
        <text class="link" @click="goLogin">返回登录</text>
      </view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.auth-page {
  min-height: 100vh;
  padding: 80rpx 32rpx 40rpx;
  box-sizing: border-box;
  background: linear-gradient(180deg, #eef7ff 0%, #f5f7fa 52%, #ffffff 100%);
}

.auth-card {
  padding: 32rpx;
  border: 1rpx solid $uni-border-color;
  border-radius: 12rpx;
  background: #ffffff;
  box-shadow: 0 16rpx 48rpx rgba(31, 45, 61, 0.08);
}

.brand {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
  margin-bottom: 28rpx;

  text:first-child {
    color: $uni-color-primary;
    font-size: 24rpx;
    font-weight: 700;
  }

  text:last-child {
    color: #172033;
    font-size: 38rpx;
    font-weight: 800;
  }
}

.note {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
  margin-top: 24rpx;
  color: $uni-text-color-grey;
  font-size: 24rpx;
}

.link {
  color: $uni-color-primary;
  font-weight: 700;
}
</style>
