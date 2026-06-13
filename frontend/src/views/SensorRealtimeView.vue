<script setup lang="ts">
import { ArrowLeft, Gauge, Pause, Play, RadioTower, Send } from 'lucide-vue-next';
import { ElMessage } from 'element-plus';
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import LineChart from '@/components/LineChart.vue';
import MetricCard from '@/components/MetricCard.vue';
import { fetchDevice, simulateRealtime } from '@/api/lab';
import { subscribeRealtime } from '@/api/realtime';
import type { Device, Point, RealtimeMessage, Sensor } from '@/types/domain';
import { formatDateTime, formatValue } from '@/utils/format';

const route = useRoute();
const deviceId = computed(() => Number(route.params.deviceId));
const sensorId = computed(() => Number(route.params.sensorId));
const device = ref<Device | null>(null);
const sensor = ref<Sensor | null>(null);
const points = ref<Point[]>([]);
const refreshMs = ref(1000);
const paused = ref(false);
const lastAppendAt = ref(0);
const simulating = ref(false);
const error = ref('');

let unsubscribe: (() => void) | null = null;
let cancelled = false;

const chartThresholds = computed(() => {
  const thresholds = [];
  if (typeof sensor.value?.min === 'number') {
    thresholds.push({ name: '下限', value: sensor.value.min, color: '#38bdf8' });
  }
  if (typeof sensor.value?.max === 'number') {
    thresholds.push({ name: '上限', value: sensor.value.max, color: '#f6b84b' });
  }
  return thresholds;
});

const alarmPoints = computed(() =>
  points.value
    .filter((point) => {
      if (typeof sensor.value?.min === 'number' && point.value < sensor.value.min) return true;
      if (typeof sensor.value?.max === 'number' && point.value > sensor.value.max) return true;
      return false;
    })
    .map((point) => ({ ts: point.ts, value: point.value, label: '阈值越界' }))
);

async function load() {
  try {
    device.value = await fetchDevice(deviceId.value);
    sensor.value = device.value.sensors.find((item) => item.id === sensorId.value) ?? null;
    points.value = sensor.value?.latest
      ? [{ ts: sensor.value.latest.ts, value: sensor.value.latest.value }]
      : [];
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '实时数据加载失败';
  }
}

function appendRealtimePoint(message: RealtimeMessage, options: { force?: boolean; throttle?: boolean } = {}) {
  if (message.sensorId !== sensorId.value) return;
  if (paused.value && !options.force) return;

  const latest = points.value[points.value.length - 1];
  if (latest?.ts === message.ts) return;

  const shouldThrottle = options.throttle ?? true;
  const now = Date.now();
  if (shouldThrottle && now - lastAppendAt.value < refreshMs.value) return;
  lastAppendAt.value = now;

  sensor.value = sensor.value
    ? { ...sensor.value, latest: { ts: message.ts, value: message.value } }
    : sensor.value;
  points.value = [...points.value.slice(-119), { ts: message.ts, value: message.value }];
}

async function simulatePoint() {
  if (!sensor.value || simulating.value) return;
  simulating.value = true;
  try {
    const message = await simulateRealtime(sensor.value.id);
    appendRealtimePoint(message, { force: true, throttle: false });
    ElMessage.success('已模拟上报一条实时数据');
  } catch (cause) {
    ElMessage.error(cause instanceof Error ? cause.message : '模拟上报失败');
  } finally {
    simulating.value = false;
  }
}

let subGen = 0;

async function resubscribe() {
  const gen = ++subGen;
  unsubscribe?.();
  unsubscribe = null;
  await load();
  if (cancelled || gen !== subGen) return;
  unsubscribe = subscribeRealtime((message) => {
    appendRealtimePoint(message);
  });
}

onMounted(async () => {
  await resubscribe();
});

watch([deviceId, sensorId], async () => {
  points.value = [];
  await resubscribe();
});

onBeforeUnmount(() => {
  cancelled = true;
  subGen += 1;
  unsubscribe?.();
});
</script>

<template>
  <div class="stack gap-lg">
    <RouterLink v-if="device" class="text-link" :to="`/devices/${device.id}`">
      <ArrowLeft :size="16" />
      返回板卡详情
    </RouterLink>

    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />

    <template v-if="device && sensor">
      <section class="toolbar">
        <div>
          <p class="eyebrow">{{ device.sn }} / {{ sensor.code }}</p>
          <h2>{{ sensor.name }}实时监测</h2>
          <p>Django Channels WebSocket 推送；前端支持 1s / 5s / 10s 节流展示。</p>
        </div>
        <div class="command-row">
          <label class="field-inline">
            刷新频率
            <el-select v-model="refreshMs" style="width: 120px">
              <el-option label="1 秒" :value="1000" />
              <el-option label="5 秒" :value="5000" />
              <el-option label="10 秒" :value="10000" />
            </el-select>
          </label>
          <el-button @click="paused = !paused">
            <Pause v-if="!paused" :size="17" />
            <Play v-else :size="17" />
            {{ paused ? '继续' : '暂停' }}
          </el-button>
          <el-button type="primary" :loading="simulating" @click="simulatePoint">
            <Send v-if="!simulating" :size="17" />
            模拟上报
          </el-button>
        </div>
      </section>

      <section class="dashboard-summary two">
        <MetricCard
          label="当前值"
          :value="formatValue(sensor.latest?.value, sensor.unit)"
          :detail="formatDateTime(sensor.latest?.ts)"
          tone="green"
          :icon="Gauge"
        />
        <MetricCard
          label="实时通道"
          value="WebSocket"
          detail="Django Channels 实时推送"
          tone="cyan"
          :icon="RadioTower"
        />
      </section>

      <el-card shadow="never">
        <template #header>
          <div class="section-heading">
            <div>
              <p class="eyebrow">Realtime Trend</p>
              <h2>最近 {{ points.length }} 个点位</h2>
            </div>
          </div>
        </template>
        <LineChart
          :points="points"
          :title="sensor.name"
          :unit="sensor.unit"
          color="#2dd47d"
          :thresholds="chartThresholds"
          :alarm-points="alarmPoints"
        />
      </el-card>
    </template>
  </div>
</template>
