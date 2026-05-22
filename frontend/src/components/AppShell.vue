<script setup lang="ts">
import {
  Activity,
  Bell,
  Cpu,
  FileClock,
  LayoutGrid,
  LayoutDashboard,
  ListChecks,
  LogOut,
  Menu,
  MonitorUp,
  RadioTower,
  SlidersHorizontal,
  Users,
  X,
  Zap
} from 'lucide-vue-next';
import { ElMessageBox } from 'element-plus';
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { realtimeState, realtimeStatusLabel } from '@/api/realtime';
import { useAuthStore } from '@/stores/auth';
import { relativeTime, roleLabel } from '@/utils/format';

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const title = computed(() => String(route.meta.title ?? '小熊派 Nano 实验室'));
const realtimeTone = computed(() => {
  if (realtimeState.status === 'online' || realtimeState.status === 'mock') return 'online';
  if (realtimeState.status === 'connecting' || realtimeState.status === 'reconnecting') return 'warning';
  if (realtimeState.status === 'idle') return 'idle';
  return 'offline';
});

const sidebarOpen = ref(false);

function toggleSidebar() {
  sidebarOpen.value = !sidebarOpen.value;
}

function closeSidebar() {
  sidebarOpen.value = false;
}

watch(() => route.fullPath, () => {
  sidebarOpen.value = false;
});

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    sidebarOpen.value = false;
  }
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown);
});

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown);
});

async function logout() {
  try {
    await ElMessageBox.confirm('确定要退出当前账号吗？', '退出登录', {
      type: 'warning',
      confirmButtonText: '退出',
      cancelButtonText: '取消'
    });
    auth.logout();
    router.replace({ name: 'login' });
  } catch {
    /* user canceled */
  }
}
</script>

<template>
  <div class="app-layout">
    <div
      class="sidebar-backdrop"
      :class="{ 'is-open': sidebarOpen }"
      aria-hidden="true"
      @click="closeSidebar"
    />

    <aside
      class="sidebar"
      :class="{ 'is-open': sidebarOpen }"
      aria-label="主导航"
    >
      <RouterLink class="brand" to="/dashboard" aria-label="进入设备总览">
        <span class="brand-mark"><Cpu :size="22" /></span>
        <span>
          <strong>BearPi Nano</strong>
          <small>Lab Console</small>
        </span>
      </RouterLink>

      <nav class="nav-list">
        <RouterLink to="/dashboard" class="nav-link">
          <LayoutDashboard :size="18" />
          <span>设备总览</span>
        </RouterLink>
        <RouterLink to="/screen" class="nav-link">
          <MonitorUp :size="18" />
          <span>实时大屏</span>
        </RouterLink>
        <RouterLink to="/topology" class="nav-link">
          <LayoutGrid :size="18" />
          <span>槽位拓扑</span>
        </RouterLink>
        <RouterLink to="/power" class="nav-link">
          <Zap :size="18" />
          <span>功耗监控</span>
        </RouterLink>
        <RouterLink to="/tasks" class="nav-link">
          <ListChecks :size="18" />
          <span>任务中心</span>
        </RouterLink>
        <RouterLink to="/alarms" class="nav-link">
          <Bell :size="18" />
          <span>告警中心</span>
        </RouterLink>
        <RouterLink to="/rules" class="nav-link">
          <SlidersHorizontal :size="18" />
          <span>规则配置</span>
        </RouterLink>
        <RouterLink v-if="auth.canManageUsers" to="/audit" class="nav-link">
          <FileClock :size="18" />
          <span>审计日志</span>
        </RouterLink>
        <RouterLink v-if="auth.canManageUsers" to="/users" class="nav-link">
          <Users :size="18" />
          <span>用户权限</span>
        </RouterLink>
      </nav>

      <div class="sidebar-panel">
        <div class="mini-kpi">
          <RadioTower :size="18" />
          <span>本地HTTP网关</span>
        </div>
        <div class="sidebar-status-list">
          <span class="status-online"><i />Django API</span>
          <span class="status-online"><i />MySQL 存储</span>
          <span :class="`status-${realtimeTone}`"><i />Channels {{ realtimeStatusLabel[realtimeState.status] }}</span>
        </div>
      </div>
    </aside>

    <div class="content-shell">
      <header class="topbar">
        <div class="topbar-left">
          <button
            class="menu-toggle"
            type="button"
            :aria-label="sidebarOpen ? '关闭侧边栏' : '打开侧边栏'"
            :aria-expanded="sidebarOpen"
            @click="toggleSidebar"
          >
            <component :is="sidebarOpen ? X : Menu" :size="20" />
          </button>
          <div>
            <p class="eyebrow">BearPi Nano Lab Console</p>
            <h1>{{ title }}</h1>
          </div>
        </div>
        <div class="topbar-actions">
          <div class="realtime-chip" :class="`status-${realtimeTone}`">
            <RadioTower :size="16" />
            <span>{{ realtimeStatusLabel[realtimeState.status] }}</span>
            <small v-if="realtimeState.attempts">第 {{ realtimeState.attempts }} 次重连</small>
            <small v-else-if="realtimeState.lastMessageAt">{{ relativeTime(realtimeState.lastMessageAt) }}</small>
          </div>
          <div class="user-chip">
            <Activity :size="16" />
            <span>{{ auth.user?.name ?? '未登录' }}</span>
            <el-tag v-if="auth.user" size="small" effect="dark">{{ roleLabel[auth.user.role] }}</el-tag>
          </div>
          <button class="icon-button" type="button" aria-label="退出登录" title="退出登录" @click="logout">
            <LogOut :size="18" />
          </button>
        </div>
      </header>

      <main class="page-content">
        <slot />
      </main>
    </div>
  </div>
</template>

<style scoped>
.topbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.topbar-left h1 {
  margin: 0;
  font-size: 20px;
  line-height: 1.2;
}

.topbar-left .eyebrow {
  margin: 0 0 2px;
}

@media (max-width: 760px) {
  .topbar-left h1 {
    font-size: 17px;
  }
}
</style>
