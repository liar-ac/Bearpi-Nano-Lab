import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import { AUTH_CLEARED_EVENT } from '@/api/http';
import { login as loginApi, register as registerApi } from '@/api/lab';
import { reconnectRealtime } from '@/api/realtime';
import { router } from '@/router';
import type { User } from '@/types/domain';

const TOKEN_KEY = 'access_token';
const REFRESH_KEY = 'refresh_token';
const USER_KEY = 'bearpi_user';

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem(TOKEN_KEY));
  const user = ref<User | null>(restoreUser());
  const isAuthenticated = computed(() => Boolean(token.value));
  const canCommand = computed(() => user.value?.role === 'admin' || user.value?.role === 'experimenter');
  const canAckAlarm = computed(() => user.value?.role === 'admin' || user.value?.role === 'experimenter');
  const canManageUsers = computed(() => user.value?.role === 'admin');

  async function login(username: string, password: string) {
    const response = await loginApi(username, password);
    setSession(response);
    reconnectRealtime();
  }

  async function register(payload: { username: string; password: string; name?: string }) {
    const response = await registerApi(payload);
    setSession(response);
    reconnectRealtime();
  }

  function setSession(response: { access_token: string; refresh_token: string; user: User }) {
    token.value = response.access_token;
    user.value = response.user;
    localStorage.setItem(TOKEN_KEY, response.access_token);
    localStorage.setItem(REFRESH_KEY, response.refresh_token);
    localStorage.setItem(USER_KEY, JSON.stringify(response.user));
  }

  function logout() {
    token.value = null;
    user.value = null;
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(USER_KEY);
  }

  window.addEventListener(AUTH_CLEARED_EVENT, () => {
    token.value = null;
    user.value = null;
    // 会话过期后,如果当前不在登录/注册页,主动跳回登录页,避免页面停留在401错误状态
    const current = router.currentRoute.value;
    if (current.name !== 'login' && current.name !== 'register') {
      void router.replace({ name: 'login', query: { redirect: current.fullPath } });
    }
  });

  return { token, user, isAuthenticated, canCommand, canAckAlarm, canManageUsers, login, register, logout };
});

function restoreUser() {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as User;
  } catch {
    return null;
  }
}
