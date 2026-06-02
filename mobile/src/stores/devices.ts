import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import { fetchDevices } from '@/api/lab';
import type { Device, DeviceStatus, LabSlot, RealtimeMessage } from '@/types/domain';

export const useDeviceStore = defineStore('devices', () => {
  const devices = ref<Device[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);
  const selectedStatus = ref<DeviceStatus | 'all'>('all');
  let pendingRefresh: ReturnType<typeof setTimeout> | null = null;
  let lastRefreshAt = 0;

  const filteredDevices = computed(() =>
    selectedStatus.value === 'all'
      ? devices.value
      : devices.value.filter((device) => device.status === selectedStatus.value)
  );

  const focusDevices = computed(() => devices.value.filter((device) => device.slotNo <= 4));

  const labSlots = computed<LabSlot[]>(() => {
    const bySlot = new Map(devices.value.map((device) => [device.slotNo, device]));
    return Array.from({ length: 120 }, (_, index) => {
      const slotNo = index + 1;
      const device = bySlot.get(slotNo);
      return {
        slotNo,
        row: Math.floor(index / 12) + 1,
        column: (index % 12) + 1,
        status: device?.status ?? 'empty',
        device
      };
    });
  });

  const statusCounts = computed(() => {
    const counts: Record<DeviceStatus, number> = {
      online: 0,
      offline: 0,
      warning: 0,
      maintenance: 0
    };
    for (const device of devices.value) counts[device.status] += 1;
    return counts;
  });

  async function loadDevices(overrides: { status?: DeviceStatus | 'all'; includeInactive?: boolean } = {}) {
    loading.value = true;
    error.value = null;
    try {
      const status = overrides.status ?? selectedStatus.value;
      const response = await fetchDevices({
        status: status === 'all' ? undefined : status,
        includeInactive: overrides.includeInactive
      });
      devices.value = response.results;
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : '设备列表加载失败';
    } finally {
      loading.value = false;
      lastRefreshAt = Date.now();
    }
  }

  function scheduleRefresh() {
    if (pendingRefresh) return;
    const elapsed = Date.now() - lastRefreshAt;
    const delay = Math.max(0, 5000 - elapsed);
    pendingRefresh = setTimeout(() => {
      pendingRefresh = null;
      void loadDevices();
    }, delay);
  }

  function applyRealtime(message: RealtimeMessage) {
    const known = devices.value.some((device) => device.id === message.deviceId);
    if (!known) {
      const filter = selectedStatus.value;
      const matchFilter = filter === 'all' || (message.status && message.status === filter);
      if (matchFilter) scheduleRefresh();
      return;
    }

    const index = devices.value.findIndex((d) => d.id === message.deviceId);
    if (index >= 0) {
      const device = devices.value[index];
      const newStatus = message.status ?? device.status;
      const updated = {
        ...device,
        status: newStatus,
        lastSeen: message.ts,
        abnormalReason: newStatus === 'online' ? '' : device.abnormalReason,
        sensors: device.sensors.map((sensor) =>
          sensor.id === message.sensorId
            ? { ...sensor, latest: { ts: message.ts, value: message.value } }
            : sensor
        )
      };
      const next = devices.value.slice();
      next[index] = updated;
      devices.value = next;
    }
  }

  return {
    devices,
    filteredDevices,
    focusDevices,
    labSlots,
    loading,
    error,
    selectedStatus,
    statusCounts,
    loadDevices,
    applyRealtime
  };
});
