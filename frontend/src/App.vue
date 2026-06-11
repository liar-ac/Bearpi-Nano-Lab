<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import AppShell from '@/components/AppShell.vue';

const route = useRoute();
const router = useRouter();
const isPublic = computed(() => route.meta.public === true);
const isFullscreen = computed(() => route.meta.fullscreen === true);
const isLoading = ref(false);
let timer: number | null = null;

router.beforeEach((to, from, next) => {
  if (to.fullPath !== from.fullPath) {
    if (timer !== null) window.clearTimeout(timer);
    isLoading.value = true;
  }
  next();
});

router.afterEach(() => {
  if (timer !== null) window.clearTimeout(timer);
  timer = window.setTimeout(() => {
    isLoading.value = false;
    timer = null;
  }, 320);
});

watch(
  () => route.meta.title,
  (next) => {
    document.title = next ? `${next} · 小熊派 Nano 实验室` : '小熊派 Nano 实验室管理系统';
  },
  { immediate: true }
);
</script>

<template>
  <Transition name="fade">
    <div v-if="isLoading" class="route-progress" aria-hidden="true" />
  </Transition>

  <RouterView v-if="isPublic || isFullscreen" v-slot="{ Component, route: r }">
    <Transition name="fade" mode="out-in">
      <component :is="Component" :key="r.fullPath" />
    </Transition>
  </RouterView>
  <AppShell v-else>
    <RouterView v-slot="{ Component, route: r }">
      <Transition name="fade" mode="out-in">
        <component :is="Component" :key="r.fullPath" />
      </Transition>
    </RouterView>
  </AppShell>
</template>
