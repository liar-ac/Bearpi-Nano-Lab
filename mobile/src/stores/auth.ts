import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import { AUTH_CLEARED_EVENT } from '@/api/http';
import { login as loginApi, register as registerApi } from '@/api/lab';
import { reconnectRealtime } from '@/api/realtime';
import type { User } from '@/types/domain';

const TOKEN_KEY = 'access_token';
const REFRESH_KEY = 'refresh_token';
const USER_KEY = 'bearpi_user';

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(uni.getStorageSync(TOKEN_KEY) || null);
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
    uni.setStorageSync(TOKEN_KEY, response.access_token);
    uni.setStorageSync(REFRESH_KEY, response.refresh_token);
    uni.setStorageSync(USER_KEY, JSON.stringify(response.user));
  }

  function logout() {
    token.value = null;
    user.value = null;
    uni.removeStorageSync(TOKEN_KEY);
    uni.removeStorageSync(REFRESH_KEY);
    uni.removeStorageSync(USER_KEY);
  }

  uni.$on(AUTH_CLEARED_EVENT, () => {
    token.value = null;
    user.value = null;
    uni.reLaunch({ url: '/pages/login/index' });
  });

  return {
    token,
    user,
    isAuthenticated,
    canCommand,
    canAckAlarm,
    canManageUsers,
    login,
    register,
    logout
  };
});

function restoreUser() {
  const raw = uni.getStorageSync(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(String(raw)) as User;
  } catch {
    return null;
  }
}
