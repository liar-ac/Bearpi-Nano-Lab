import type { AlarmLevel, DeviceStatus, UserRole } from '@/types/domain';

export const roleLabel: Record<UserRole, string> = {
  admin: '管理员',
  experimenter: '实验员',
  viewer: '只读'
};

export const statusLabel: Record<DeviceStatus, string> = {
  online: '在线',
  offline: '离线',
  warning: '异常',
  maintenance: '维护中'
};

export const alarmLevelLabel: Record<AlarmLevel, string> = {
  info: '提示',
  warning: '警告',
  critical: '严重'
};

export function formatDateTime(value: string | null | undefined) {
  if (!value) return '无记录';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN', { hour12: false });
}

export function formatValue(value: number | undefined, unit = '') {
  if (typeof value !== 'number') return '--';
  return `${Number(value.toFixed(2))}${unit}`;
}

export function relativeTime(value: string | null | undefined) {
  if (!value) return '从未上报';
  const diff = Date.now() - new Date(value).getTime();
  if (Number.isNaN(diff)) return value;
  if (diff < 60_000) return `${Math.max(1, Math.round(diff / 1000))} 秒前`;
  if (diff < 3_600_000) return `${Math.round(diff / 60_000)} 分钟前`;
  if (diff < 86_400_000) return `${Math.round(diff / 3_600_000)} 小时前`;
  return `${Math.round(diff / 86_400_000)} 天前`;
}
