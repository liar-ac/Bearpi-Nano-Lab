<script setup lang="ts">
import type { DeviceStatus } from '@/types/domain';
import { statusLabel } from '@/utils/format';

defineProps<{
  status: DeviceStatus;
}>();
</script>

<template>
  <span class="status-badge" :class="`status-${status}`">
    <span class="status-dot" />
    {{ statusLabel[status] }}
  </span>
</template>
