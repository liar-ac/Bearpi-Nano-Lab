<script setup lang="ts">
import { ArrowLeft, Download, FileSpreadsheet, Search } from 'lucide-vue-next';
import { ElMessage } from 'element-plus';
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import LineChart from '@/components/LineChart.vue';
import { fetchDevice, fetchHistory } from '@/api/lab';
import type { Device, HistoryInterval, PointsResponse, Sensor } from '@/types/domain';
import { downloadCsv, downloadExcel } from '@/utils/exportCsv';
import { formatDateTime } from '@/utils/format';

const route = useRoute();
let searchSeq = 0;
const deviceId = computed(() => Number(route.params.deviceId));
const sensorId = computed(() => Number(route.params.sensorId));
const device = ref<Device | null>(null);
const sensor = ref<Sensor | null>(null);
const data = ref<PointsResponse | null>(null);
const interval = ref<HistoryInterval>('5m');
const loading = ref(false);
const error = ref('');
const range = ref<[Date, Date] | null>([new Date(Date.now() - 7 * 24 * 60 * 60_000), new Date()]);

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
  (data.value?.points ?? [])
    .filter((point) => {
      if (typeof sensor.value?.min === 'number' && point.value < sensor.value.min) return true;
      if (typeof sensor.value?.max === 'number' && point.value > sensor.value.max) return true;
      return false;
    })
    .map((point) => ({ ts: point.ts, value: point.value, label: '阈值越界' }))
);

async function loadMeta(): Promise<boolean> {
  try {
    device.value = await fetchDevice(deviceId.value);
    sensor.value = device.value.sensors.find((item) => item.id === sensorId.value) ?? null;
    return true;
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '设备信息加载失败';
    return false;
  }
}

async function search(seq?: number) {
  if (!range.value || !range.value[0] || !range.value[1]) {
    error.value = '请选择时间范围';
    return;
  }
  loading.value = true;
  error.value = '';
  try {
    const result = await fetchHistory(sensorId.value, {
      start: range.value[0].toISOString(),
      end: range.value[1].toISOString(),
      interval: interval.value
    });
    if (seq !== undefined && seq !== searchSeq) return;
    data.value = result;
  } catch (cause) {
    if (seq !== undefined && seq !== searchSeq) return;
    error.value = cause instanceof Error ? cause.message : '历史数据查询失败';
  } finally {
    if (seq === undefined || seq === searchSeq) loading.value = false;
  }
}

function rows() {
  return (data.value?.points ?? []).map((point) => ({
    time: formatDateTime(point.ts),
    value: point.value,
    unit: sensor.value?.unit ?? ''
  }));
}

function exportCsv() {
  if (!data.value?.points.length) {
    ElMessage.warning('暂无可导出的历史数据');
    return;
  }
  downloadCsv(`${sensor.value?.code ?? 'sensor'}-${interval.value}-history.csv`, rows());
}

function exportExcel() {
  if (!data.value?.points.length) {
    ElMessage.warning('暂无可导出的历史数据');
    return;
  }
  downloadExcel(`${sensor.value?.code ?? 'sensor'}-${interval.value}-history.xls`, rows());
}

onMounted(async () => {
  if (!(await loadMeta())) return;
  await search(++searchSeq);
});

watch([deviceId, sensorId], async () => {
  const metaOk = await loadMeta();
  data.value = null;
  if (!metaOk) return;
  await search(++searchSeq);
});

watch([interval, range], () => {
  if (data.value !== null) {
    search(++searchSeq);
  }
});
</script>

<template>
  <div class="stack gap-lg">
    <RouterLink v-if="device" class="text-link" :to="`/devices/${device.id}`">
      <ArrowLeft :size="16" />
      返回板卡详情
    </RouterLink>

    <section class="toolbar">
      <div>
        <p class="eyebrow">{{ device?.sn ?? 'Device' }} / {{ sensor?.code ?? 'Sensor' }}</p>
        <h2>{{ sensor?.name ?? '传感器' }}历史查询</h2>
        <p>严格对应需求：时间范围、1m/5m/1h/1d 聚合、折线图、表格、CSV/Excel 导出。</p>
      </div>
    </section>

    <el-card shadow="never">
      <div class="query-panel">
        <label>
          时间范围
          <el-date-picker
            v-model="range"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
          />
        </label>
        <label>
          聚合粒度
          <el-select v-model="interval">
            <el-option label="1 分钟" value="1m" />
            <el-option label="5 分钟" value="5m" />
            <el-option label="1 小时" value="1h" />
            <el-option label="1 天" value="1d" />
          </el-select>
        </label>
        <el-button type="primary" :loading="loading" @click="search(++searchSeq)">
          <Search :size="17" />
          查询
        </el-button>
        <el-button :disabled="!data?.points.length" @click="exportCsv">
          <Download :size="17" />
          CSV
        </el-button>
        <el-button :disabled="!data?.points.length" @click="exportExcel">
          <FileSpreadsheet :size="17" />
          Excel
        </el-button>
      </div>
    </el-card>

    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />

    <el-card shadow="never">
      <template #header>
        <div class="section-heading">
          <div>
            <p class="eyebrow">History Trend</p>
            <h2>{{ loading ? '正在查询...' : `共 ${data?.points.length ?? 0} 个点位` }}</h2>
          </div>
        </div>
      </template>
      <LineChart
        :points="data?.points ?? []"
        :title="sensor?.name"
        :unit="sensor?.unit"
        color="#38bdf8"
        :thresholds="chartThresholds"
        :alarm-points="alarmPoints"
      />
    </el-card>

    <el-card shadow="never">
      <el-table :data="data?.points ?? []" stripe max-height="520">
        <el-table-column label="时间" min-width="220">
          <template #default="{ row }">{{ formatDateTime(row.ts) }}</template>
        </el-table-column>
        <el-table-column prop="value" label="平均值" min-width="120" />
        <el-table-column label="单位" width="100">
          <template #default>{{ sensor?.unit }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>
