<script setup lang="ts">
import { Cpu, RadioTower, ShieldCheck, Sparkles, Zap } from 'lucide-vue-next';
import { ElMessage } from 'element-plus';
import { ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const username = ref('');
const password = ref('');
const loading = ref(false);

async function submit() {
  if (!username.value.trim() || !password.value) {
    ElMessage.warning('请填写账号和密码');
    return;
  }
  loading.value = true;
  try {
    await auth.login(username.value.trim(), password.value);
    ElMessage.success('登录成功');
    const redirect = route.query.redirect;
    const target = Array.isArray(redirect) ? redirect[0] : (redirect ?? '/dashboard');
    const safe = typeof target === 'string' && target.startsWith('/') && !target.startsWith('//') ? target : '/dashboard';
    router.replace(safe);
  } catch (cause) {
    ElMessage.error(cause instanceof Error ? cause.message : '登录失败');
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <main class="login-page">
    <section class="login-hero">
      <div class="login-hero-badge">
        <Cpu :size="18" />
        BearPi Nano Lab
      </div>
      <h1 class="login-title">
        <span>小熊派 Nano 开发板</span>
        <span>实验室管理系统</span>
      </h1>
      <p class="login-hero-copy">
        <span>面向嵌入式实验室的设备监控、后端接入</span>
        <span>告警处理与远程执行器控制平台</span>
      </p>
      <div class="login-hero-metrics">
        <span><RadioTower :size="16" /> HTTPJSON</span>
        <span><Zap :size="16" /> WebSocket 实时</span>
        <span><Sparkles :size="16" /> IA1 执行器控制</span>
      </div>
    </section>

    <section class="login-panel">
      <div class="login-brand">
        <span><Cpu :size="28" /></span>
        <div>
          <p>Secure Console</p>
          <h2>登录控制台</h2>
        </div>
      </div>

      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="账号">
          <el-input v-model.trim="username" autocomplete="username" placeholder="admin / exp / lab / viewer" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="password"
            autocomplete="current-password"
            placeholder="admin123"
            show-password
            type="password"
            @keyup.enter="submit"
          />
        </el-form-item>
        <el-button class="full-button" type="primary" native-type="submit" :loading="loading">
          <ShieldCheck :size="18" />
          进入控制台
        </el-button>
      </el-form>

      <div class="login-note">
        <p class="login-note-line"><strong>角色示例：</strong>admin 为管理员，exp/lab 为实验员，viewer 为只读。</p>
        <p>新账号注册后默认为只读，需要管理员升级权限。</p>
        <RouterLink class="login-register-link" to="/register">注册新账号</RouterLink>
      </div>
    </section>
  </main>
</template>

<style scoped>
.login-note-line {
  white-space: nowrap;
}

@media (max-width: 760px) {
  .login-note-line {
    white-space: normal;
  }
}
</style>
