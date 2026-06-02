<script setup lang="ts">
import { LineChart as ELineChart } from 'echarts/charts';
import {
  DataZoomComponent,
  GridComponent,
  MarkLineComponent,
  MarkPointComponent,
  TooltipComponent
} from 'echarts/components';
import { init, use, type ECharts } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import type { Point } from '@/types/domain';

use([ELineChart, GridComponent, TooltipComponent, DataZoomComponent, MarkLineComponent, MarkPointComponent, CanvasRenderer]);

const props = defineProps<{
  points: Point[];
  title?: string;
  unit?: string;
  color?: string;
  thresholds?: Array<{ name: string; value: number; color?: string }>;
  alarmPoints?: Array<{ ts: string; value: number; label?: string }>;
}>();

const chartRef = ref<HTMLDivElement | null>(null);
let chart: ECharts | null = null;

const option = computed(() => ({
  backgroundColor: 'transparent',
  grid: { left: 44, right: 18, top: 34, bottom: 42 },
  tooltip: {
    trigger: 'axis',
    backgroundColor: '#111a22',
    borderColor: '#334858',
    textStyle: { color: '#edf4f8' },
    valueFormatter: (value: unknown) => `${value}${props.unit ?? ''}`
  },
  xAxis: {
    type: 'time',
    axisLine: { lineStyle: { color: '#334858' } },
    axisLabel: { color: '#9baab4' },
    splitLine: { show: false }
  },
  yAxis: {
    type: 'value',
    name: props.unit,
    nameTextStyle: { color: '#9baab4' },
    axisLabel: { color: '#9baab4' },
    splitLine: { lineStyle: { color: 'rgba(155,170,180,0.12)' } }
  },
  dataZoom: [{ type: 'inside' }, { type: 'slider', height: 18, bottom: 10, borderColor: '#334858' }],
  series: [
    {
      name: props.title ?? 'sensor',
      type: 'line',
      smooth: true,
      showSymbol: false,
      lineStyle: { width: 2.2, color: props.color ?? '#2dd47d' },
      areaStyle: { opacity: 0.14, color: props.color ?? '#2dd47d' },
      data: props.points.map((point) => [point.ts, point.value]),
      markLine: {
        silent: true,
        symbol: 'none',
        label: {
          color: '#d6e6ef',
          formatter: (params: { name: string; value: number }) =>
            `${params.name} ${params.value}${props.unit ?? ''}`
        },
        lineStyle: { width: 1.4, type: 'dashed' },
        data: (props.thresholds ?? []).map((threshold) => ({
          name: threshold.name,
          yAxis: threshold.value,
          lineStyle: { color: threshold.color ?? '#f6b84b' },
          label: { color: threshold.color ?? '#f6b84b' }
        }))
      },
      markPoint: {
        symbol: 'pin',
        symbolSize: 42,
        label: {
          color: '#0b1117',
          fontWeight: 800,
          formatter: '!'
        },
        itemStyle: { color: '#ff6874' },
        data: (props.alarmPoints ?? []).map((point) => ({
          name: point.label ?? '告警点',
          coord: [point.ts, point.value],
          value: point.value
        }))
      }
    }
  ]
}));

function render() {
  if (!chartRef.value) return;
  if (!chart) chart = init(chartRef.value);
  chart.setOption(option.value);
}

function resize() {
  chart?.resize();
}

onMounted(async () => {
  await nextTick();
  render();
  window.addEventListener('resize', resize);
});

watch(option, render, { deep: true });

onBeforeUnmount(() => {
  window.removeEventListener('resize', resize);
  chart?.dispose();
  chart = null;
});
</script>

<template>
  <div ref="chartRef" class="line-chart" role="img" :aria-label="title ?? '传感器趋势图'" />
</template>
