<script setup lang="ts">
import type { DeviceStatus, LabSlot } from '@/types/domain';
import { statusLabel } from '@/utils/format';

const props = defineProps<{
  slots: LabSlot[];
  filter: DeviceStatus | 'all';
}>();

function slotTitle(slot: LabSlot) {
  if (!slot.device) return `槽位 ${slot.slotNo}：空闲`;
  return `槽位 ${slot.slotNo}：${slot.device.sn} / ${statusLabel[slot.device.status]}`;
}

function isFilteredOut(slot: LabSlot) {
  return props.filter !== 'all' && slot.status !== props.filter;
}
</script>

<template>
  <div class="lab-grid" aria-label="120 块小熊派 Nano 实验室网格">
    <RouterLink
      v-for="slot in slots"
      :key="slot.slotNo"
      :to="slot.device ? `/devices/${slot.device.id}` : '/dashboard'"
      class="lab-slot"
      :class="[slot.status, { 'has-device': Boolean(slot.device), 'filtered-out': isFilteredOut(slot) }]"
      :aria-label="slotTitle(slot)"
      :title="slotTitle(slot)"
    >
      <span class="slot-no">{{ String(slot.slotNo).padStart(3, '0') }}</span>
      <span v-if="slot.device" class="slot-device" />
    </RouterLink>
  </div>
</template>
