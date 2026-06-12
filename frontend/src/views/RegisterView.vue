<script setup lang="ts">
import { Cpu, UserPlus } from 'lucide-vue-next';
import { ElMessage } from 'element-plus';
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

const router = useRouter();
const auth = useAuthStore();

const username = ref('');
const name = ref('');
const password = ref('');
const confirmPassword = ref('');
const loading = ref(false);

async function submit() {
  if (!username.value.trim() || !password.value) {
    ElMessage.warning('请填写账号和密码');
    return;
  }
  if (username.value.trim().length < 3) {
    ElMessage.warning('账号至少需要3位');
    return;
  }
  if (password.value.length < 8) {
    ElMessage.warning('密码至少需要8位');
    return;
  }
  if (/^\d+$/.test(password.value)) {
    ElMessage.warning('密码不能全为数字');
    return;
  }
  if (password.value !== confirmPassword.value) {
    ElMessage.warning('两次输入的密码不一致');
    return;
  }

  loading.value = true;
  try {
    await auth.register({
      username: username.value.trim(),
      name: name.value.trim(),
      password: password.value
    });
    ElMessage.success('注册成功，当前账号为只读权限');
    router.replace('/dashboard');
  } catch (cause) {
    ElMessage.error(cause instanceof Error ? cause.message : '注册失败');
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <main class="login-page auth-only">
    <section class="login-panel">
      <div class="login-brand">
        <span><Cpu :size="28" /></span>
        <div>
          <p>BearPi Nano Lab</p>
          <h1>注册实验室账号</h1>
        </div>
      </div>

      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="账号">
          <el-input v-model.trim="username" autocomplete="username" placeholder="至少 3 位，登录时使用" />
        </el-form-item>
        <el-form-item label="姓名">
          <el-input v-model.trim="name" autocomplete="name" placeholder="可选，用于页面显示" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="password" autocomplete="new-password" type="password" show-password placeholder="至少 8 位，不能全为数字" />
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input v-model="confirmPassword" autocomplete="new-password" type="password" show-password placeholder="再次输入密码" />
        </el-form-item>
        <el-button class="full-button" type="primary" native-type="submit" :loading="loading">
          <UserPlus :size="18" />
          创建只读账号
        </el-button>
      </el-form>

      <div class="login-note">
        新注册账号只能查看设备、告警、历史和实时数据；管理员可在“用户权限”页面升级为实验员或管理员。
        <RouterLink class="text-link" to="/login">返回登录</RouterLink>
      </div>
    </section>
  </main>
</template>
