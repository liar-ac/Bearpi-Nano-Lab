<script setup lang="ts">
import type { Component } from 'vue';

defineProps<{
  label: string;
  value: string | number;
  detail?: string;
  tone?: 'green' | 'amber' | 'red' | 'cyan' | 'violet';
  icon?: Component;
}>();
</script>

<template>
  <section class="metric-card" :class="tone ? `tone-${tone}` : ''">
    <div class="metric-icon" v-if="icon">
      <component :is="icon" :size="20" />
    </div>
    <div>
      <p>{{ label }}</p>
      <strong>{{ value }}</strong>
      <span v-if="detail">{{ detail }}</span>
    </div>
  </section>
</template>
