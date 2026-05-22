<script setup lang="ts">
import { Inbox } from 'lucide-vue-next';

defineProps<{
  title: string;
  detail?: string;
}>();
</script>

<template>
  <div class="empty-state">
    <Inbox :size="32" />
    <strong>{{ title }}</strong>
    <p v-if="detail">{{ detail }}</p>
  </div>
</template>
