<script setup lang="ts">
import { onLaunch, onShow } from '@dcloudio/uni-app';

onLaunch(() => {
  // 启动时检查登录态。无 token 且不在登录页则跳到登录页。
  const token = uni.getStorageSync('access_token');
  const pages = getCurrentPages();
  const current = pages[pages.length - 1];
  const route = current?.route ?? '';

  const publicRoutes = new Set(['pages/login/index', 'pages/register/index']);
  if (!token && !publicRoutes.has(route)) {
    uni.reLaunch({ url: '/pages/login/index' });
  }
});

onShow(() => {
  // 应用从后台恢复时无需特别处理，预留扩展点
});
</script>

<style lang="scss">
/* 全局样式 */
page {
  background-color: $uni-bg-color-grey;
  color: $uni-text-color;
  font-size: $uni-font-size-base;
  line-height: $uni-line-height-base;
}

.app-container {
  min-height: 100vh;
  padding: $uni-spacing-row-base;
  box-sizing: border-box;
}

.app-card {
  background: $uni-bg-color;
  border-radius: $uni-border-radius-lg;
  padding: 24rpx;
  margin-bottom: 20rpx;
  box-shadow: 0 2rpx 12rpx rgba(0, 0, 0, 0.04);
}

.app-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.text-grey {
  color: $uni-text-color-grey;
}

.text-primary {
  color: $uni-color-primary;
}

.text-success {
  color: $uni-color-success;
}

.text-warning {
  color: $uni-color-warning;
}

.text-error {
  color: $uni-color-error;
}
</style>
