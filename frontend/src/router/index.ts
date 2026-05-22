import { createRouter, createWebHistory } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: '/dashboard'
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { public: true }
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('@/views/RegisterView.vue'),
      meta: { public: true }
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: () => import('@/views/DashboardView.vue'),
      meta: { title: '设备总览' }
    },
    {
      path: '/screen',
      name: 'screen',
      component: () => import('@/views/ScreenView.vue'),
      meta: { title: '实时大屏', fullscreen: true }
    },
    {
      path: '/topology',
      name: 'topology',
      component: () => import('@/views/TopologyView.vue'),
      meta: { title: '槽位拓扑' }
    },
    {
      path: '/power',
      name: 'power',
      component: () => import('@/views/PowerMonitorView.vue'),
      meta: { title: '功耗监控' }
    },
    {
      path: '/tasks',
      name: 'tasks',
      component: () => import('@/views/TaskCenterView.vue'),
      meta: { title: '任务中心' }
    },
    {
      path: '/devices/:deviceId',
      name: 'device-detail',
      alias: '/device/:deviceId',
      component: () => import('@/views/DeviceDetailView.vue'),
      meta: { title: '板卡详情' }
    },
    {
      path: '/devices/:deviceId/sensors/:sensorId/realtime',
      name: 'sensor-realtime',
      alias: '/device/:deviceId/sensor/:sensorId',
      component: () => import('@/views/SensorRealtimeView.vue'),
      meta: { title: '实时数据' }
    },
    {
      path: '/devices/:deviceId/sensors/:sensorId/history',
      name: 'sensor-history',
      alias: '/device/:deviceId/sensor/:sensorId/history',
      component: () => import('@/views/SensorHistoryView.vue'),
      meta: { title: '历史查询' }
    },
    {
      path: '/alarms',
      name: 'alarms',
      component: () => import('@/views/AlarmsView.vue'),
      meta: { title: '告警中心' }
    },
    {
      path: '/rules',
      name: 'rules',
      component: () => import('@/views/RulesView.vue'),
      meta: { title: '规则配置' }
    },
    {
      path: '/audit',
      name: 'audit',
      component: () => import('@/views/AuditLogsView.vue'),
      meta: { title: '审计日志', requiresAdmin: true }
    },
    {
      path: '/users',
      name: 'users',
      component: () => import('@/views/UsersView.vue'),
      meta: { title: '用户权限', requiresAdmin: true }
    }
  ]
});

router.beforeEach((to) => {
  const auth = useAuthStore();
  if (!to.meta.public && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } };
  }
  if (to.meta.requiresAdmin && auth.user?.role !== 'admin') {
    return { name: 'dashboard' };
  }
  if (to.name === 'login' && auth.isAuthenticated) {
    return { name: 'dashboard' };
  }
  return true;
});
