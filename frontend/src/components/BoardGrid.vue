<script setup lang="ts">
import { Cpu, ExternalLink, MapPin, UserRound } from 'lucide-vue-next';
import type { Device } from '@/types/domain';
import StatusBadge from '@/components/StatusBadge.vue';
import { formatValue, relativeTime } from '@/utils/format';

defineProps<{
  devices: Device[];
}>();
</script>

<template>
  <section class="board-grid" aria-label="小熊派 Nano 重点板卡">
    <article v-for="device in devices" :key="device.id" class="board-card">
      <div class="board-card-top">
        <span class="board-chip"><Cpu :size="18" /> 槽位 {{ device.slotNo }}</span>
        <StatusBadge :status="device.status" />
      </div>

      <h2>{{ device.sn }}</h2>
      <p class="muted">{{ device.model }} / {{ device.firmwareVersion }}</p>

      <div class="board-meta">
        <span><UserRound :size="15" /> {{ device.member }}</span>
        <span><MapPin :size="15" /> {{ device.location }}</span>
      </div>

      <div class="sensor-strip">
        <div v-for="sensor in device.sensors.slice(0, 4)" :key="sensor.id">
          <span>{{ sensor.name }}</span>
          <strong>{{ formatValue(sensor.latest?.value, sensor.unit) }}</strong>
        </div>
      </div>

      <div class="board-footer">
        <small>最近上报：{{ relativeTime(device.lastSeen) }}</small>
        <RouterLink class="text-link" :to="`/devices/${device.id}`">
          详情
          <ExternalLink :size="15" />
        </RouterLink>
      </div>
    </article>
  </section>
</template>
