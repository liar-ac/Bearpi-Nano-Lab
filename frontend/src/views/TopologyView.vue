<script setup lang="ts">
import { Activity, AlertTriangle, CheckCircle2, Cpu, Gauge, RadioTower, RefreshCcw, Search, Zap } from 'lucide-vue-next';
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import EmptyState from '@/components/EmptyState.vue';
import StatusBadge from '@/components/StatusBadge.vue';
import { realtimeState, realtimeStatusLabel } from '@/api/realtime';
import { useDeviceStore } from '@/stores/devices';
import type { Device, DeviceStatus, LabSlot } from '@/types/domain';
import { formatValue, relativeTime, statusLabel } from '@/utils/format';

type TopologyFilter = DeviceStatus | 'all' | 'empty' | 'high_power' | 'stale';
type TopologyLayer = 'status' | 'power' | 'freshness';

const store = useDeviceStore();
const keyword = ref('');
const selectedFilter = ref<TopologyFilter>('all');
const selectedLayer = ref<TopologyLayer>('status');
const selectedSlotNo = ref(1);
let refreshTimer: number | null = null;

const filters: Array<{ label: string; value: TopologyFilter }> = [
  { label: '全部', value: 'all' },
  { label: '在线', value: 'online' },
  { label: '异常', value: 'warning' },
  { label: '离线', value: 'offline' },
  { label: '维护', value: 'maintenance' },
  { label: '空槽', value: 'empty' },
  { label: '高功耗', value: 'high_power' },
  { label: '延迟', value: 'stale' }
];

const layerOptions: Array<{ label: string; value: TopologyLayer }> = [
  { label: '状态', value: 'status' },
  { label: '功耗', value: 'power' },
  { label: '活跃度', value: 'freshness' }
];

const occupiedSlots = computed(() => store.labSlots.filter((slot) => slot.device));
const onlineSlots = computed(() =>
  occupiedSlots.value.filter((slot) => slot.device?.status === 'online' || slot.device?.status === 'warning')
);
const highPowerSlots = computed(() => occupiedSlots.value.filter((slot) => slot.device && isHighPower(slot.device)));
const staleSlots = computed(() => occupiedSlots.value.filter((slot) => slot.device && isStale(slot.device)));

const totalPower = computed(() =>
  onlineSlots.value.reduce((sum, slot) => sum + powerValue(slot.device), 0)
);

const summaryCards = computed(() => [
  {
    label: '接入槽位',
    value: `${occupiedSlots.value.length}/120`,
    detail: `空槽${120 - occupiedSlots.value.length}个`,
    icon: Cpu,
    tone: 'cyan'
  },
  {
    label: '在线板卡',
    value: onlineSlots.value.length,
    detail: '在线和异常都参与监控',
    icon: Activity,
    tone: 'green'
  },
  {
    label: '总功耗',
    value: formatValue(totalPower.value, 'mW'),
    detail: '当前在线板卡合计',
    icon: Zap,
    tone: 'amber'
  },
  {
    label: '需关注',
    value: highPowerSlots.value.length + staleSlots.value.length,
    detail: '高功耗/上报延迟',
    icon: AlertTriangle,
    tone: 'red'
  }
]);

const filteredSlots = computed(() => {
  const query = keyword.value.trim().toLowerCase();
  return store.labSlots.filter((slot) => {
    if (!matchesFilter(slot)) return false;
    if (!query) return true;
    const device = slot.device;
    return [String(slot.slotNo), device?.sn, device?.member, device?.location, device?.ipAddress]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(query));
  });
});

const selectedSlot = computed(() =>
  store.labSlots.find((slot) => slot.slotNo === selectedSlotNo.value) ?? store.labSlots[0]
);

onMounted(async () => {
  await store.loadDevices({ status: 'all', includeInactive: true });
  refreshTimer = window.setInterval(() => {
    void store.loadDevices({ status: 'all', includeInactive: true });
  }, 10_000);
});

onBeforeUnmount(() => {
  if (refreshTimer !== null) {
    window.clearInterval(refreshTimer);
  }
});

function sensorByCode(device: Device | undefined, code: string) {
  return device?.sensors.find((sensor) => sensor.code === code);
}

function powerValue(device: Device | undefined) {
  return sensorByCode(device, 'power')?.latest?.value ?? 0;
}

function voltageValue(device: Device | undefined) {
  return sensorByCode(device, 'voltage')?.latest?.value;
}

function currentValue(device: Device | undefined) {
  return sensorByCode(device, 'current')?.latest?.value;
}

function isHighPower(device: Device) {
  const power = powerValue(device);
  const max = sensorByCode(device, 'power')?.max;
  return power > (typeof max === 'number' ? max : 1200);
}

function isStale(device: Device) {
  if (!device.lastSeen || device.status === 'offline') return false;
  const diff = Date.now() - new Date(device.lastSeen).getTime();
  return Number.isFinite(diff) && diff > 2 * 60_000;
}

function matchesFilter(slot: LabSlot) {
  const device = slot.device;
  if (selectedFilter.value === 'all') return true;
  if (selectedFilter.value === 'empty') return !device;
  if (!device) return false;
  if (selectedFilter.value === 'high_power') return isHighPower(device);
  if (selectedFilter.value === 'stale') return isStale(device);
  return device.status === selectedFilter.value;
}

function slotTone(slot: LabSlot) {
  const device = slot.device;
  if (!device) return 'empty';
  if (selectedLayer.value === 'power') {
    if (isHighPower(device)) return 'high-power';
    if (powerValue(device) > 1200) return 'power-warn';
    return 'power-ok';
  }
  if (selectedLayer.value === 'freshness') {
    if (isStale(device)) return 'stale';
    if (device.status === 'offline') return 'offline';
    return 'fresh';
  }
  if (isHighPower(device)) return 'high-power';
  return device.status;
}

function slotTitle(slot: LabSlot) {
  if (!slot.device) return `槽位${slot.slotNo}：空闲`;
  return [
    `槽位${slot.slotNo}`,
    slot.device.sn,
    statusLabel[slot.device.status],
    `功耗${formatValue(powerValue(slot.device), 'mW')}`,
    `最近${relativeTime(slot.device.lastSeen)}`
  ].join(' / ');
}

function selectSlot(slot: LabSlot) {
  selectedSlotNo.value = slot.slotNo;
}
</script>

<template>
  <div class="stack gap-lg">
    <section class="ops-overview priority-overview">
      <div>
        <p class="eyebrow">SlotTopology</p>
        <h2>120槽位拓扑总览</h2>
        <p>按先接入先占位的槽位顺序查看板卡状态、功耗风险和最近上报情况。</p>
      </div>
      <div class="ops-status-grid">
        <span><RadioTower :size="16" />{{ realtimeStatusLabel[realtimeState.status] }}</span>
        <span><Cpu :size="16" />{{ occupiedSlots.length }}块板</span>
        <span><Zap :size="16" />{{ formatValue(totalPower, 'mW') }}</span>
      </div>
    </section>

    <section class="metric-grid topology-metrics">
      <article v-for="card in summaryCards" :key="card.label" class="metric-card" :class="`tone-${card.tone}`">
        <component :is="card.icon" :size="22" />
        <div>
          <span>{{ card.label }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.detail }}</small>
        </div>
      </article>
    </section>

    <section class="topology-toolbar panel-section">
      <div class="toolbar-group">
        <el-radio-group v-model="selectedFilter">
          <el-radio-button v-for="filter in filters" :key="filter.value" :value="filter.value">
            {{ filter.label }}
          </el-radio-button>
        </el-radio-group>
      </div>
      <div class="toolbar-group">
        <el-radio-group v-model="selectedLayer">
          <el-radio-button v-for="layer in layerOptions" :key="layer.value" :value="layer.value">
            {{ layer.label }}
          </el-radio-button>
        </el-radio-group>
        <el-input v-model="keyword" clearable placeholder="搜索槽位、SN、成员、IP" class="topology-search">
          <template #prefix><Search :size="16" /></template>
        </el-input>
        <el-button :loading="store.loading" @click="store.loadDevices({ status: 'all', includeInactive: true })">
          <RefreshCcw :size="16" />
          刷新
        </el-button>
      </div>
    </section>

    <section class="topology-layout">
      <div class="topology-map panel-section">
        <div class="section-heading">
          <div>
            <p class="eyebrow">SlotMap</p>
            <h3>槽位地图</h3>
          </div>
          <div class="topology-legend">
            <span class="legend-online">在线</span>
            <span class="legend-warning">异常</span>
            <span class="legend-high">高功耗</span>
            <span class="legend-stale">延迟</span>
            <span class="legend-empty">空槽</span>
          </div>
        </div>

        <el-alert v-if="store.error" :title="store.error" type="error" show-icon :closable="false" />

        <div v-if="filteredSlots.length" class="topology-grid" aria-label="120槽位拓扑网格">
          <button
            v-for="slot in filteredSlots"
            :key="slot.slotNo"
            type="button"
            class="topology-cell"
            :class="[slotTone(slot), { 'is-selected': selectedSlotNo === slot.slotNo }]"
            :title="slotTitle(slot)"
            :aria-label="slotTitle(slot)"
            @click="selectSlot(slot)"
          >
            <span class="slot-index">{{ String(slot.slotNo).padStart(3, '0') }}</span>
            <strong v-if="slot.device && selectedLayer === 'power'">{{ Math.round(powerValue(slot.device)) }}</strong>
            <small v-else-if="slot.device">{{ slot.device.sn.replace('BEARPI-NANO-', '') }}</small>
            <i v-if="slot.device" />
          </button>
        </div>
        <EmptyState v-else title="没有匹配槽位" detail="调整筛选或搜索条件后再查看。" />
      </div>

      <aside class="topology-detail panel-section">
        <template v-if="selectedSlot?.device">
          <div class="detail-head">
            <div>
              <p class="eyebrow">Slot{{ selectedSlot.slotNo }}</p>
              <h3>{{ selectedSlot.device.sn }}</h3>
            </div>
            <StatusBadge :status="selectedSlot.device.status" />
          </div>

          <div class="detail-power">
            <span>
              <small>功耗</small>
              <strong>{{ formatValue(powerValue(selectedSlot.device), 'mW') }}</strong>
            </span>
            <span>
              <small>电压</small>
              <strong>{{ formatValue(voltageValue(selectedSlot.device), 'V') }}</strong>
            </span>
            <span>
              <small>电流</small>
              <strong>{{ formatValue(currentValue(selectedSlot.device), 'mA') }}</strong>
            </span>
          </div>

          <div class="detail-list">
            <span>成员：{{ selectedSlot.device.member }}</span>
            <span>位置：{{ selectedSlot.device.location }}</span>
            <span>IP：{{ selectedSlot.device.ipAddress ?? '未登记' }}</span>
            <span>最近上报：{{ relativeTime(selectedSlot.device.lastSeen) }}</span>
            <span>数据链路：HTTP上报到后端</span>
          </div>

          <div class="detail-flags">
            <el-tag v-if="isHighPower(selectedSlot.device)" type="danger" effect="dark">
              <AlertTriangle :size="14" />
              高功耗
            </el-tag>
            <el-tag v-if="isStale(selectedSlot.device)" type="warning" effect="dark">
              <Gauge :size="14" />
              上报延迟
            </el-tag>
            <el-tag v-if="!isHighPower(selectedSlot.device) && !isStale(selectedSlot.device)" type="success" effect="dark">
              <CheckCircle2 :size="14" />
              状态稳定
            </el-tag>
          </div>

          <RouterLink class="detail-link" :to="`/devices/${selectedSlot.device.id}`">
            打开板卡详情
          </RouterLink>
        </template>
        <template v-else>
          <div class="empty-slot-detail">
            <Cpu :size="28" />
            <h3>槽位{{ selectedSlot?.slotNo ?? selectedSlotNo }}空闲</h3>
            <p>下一块新接入开发板会按当前数据库空槽顺序占位。</p>
          </div>
        </template>
      </aside>
    </section>
  </div>
</template>

<style scoped>
.topology-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px;
}

.toolbar-group {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.topology-search {
  width: min(300px, 100%);
}

.topology-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 16px;
}

.topology-map,
.topology-detail {
  display: grid;
  gap: 14px;
}

.topology-grid {
  display: grid;
  grid-template-columns: repeat(12, minmax(42px, 1fr));
  gap: 8px;
}

.topology-cell {
  position: relative;
  display: grid;
  align-content: space-between;
  min-height: 58px;
  aspect-ratio: 1;
  padding: 7px;
  border: 1px solid var(--border);
  border-radius: 5px;
  color: var(--text-subtle);
  background: rgba(255, 255, 255, 0.024);
  text-align: left;
  transition: transform 150ms ease, border-color 150ms ease, background 150ms ease, box-shadow 150ms ease;
}

.topology-cell:hover,
.topology-cell.is-selected {
  transform: translateY(-1px);
  border-color: var(--cyan);
  box-shadow: 0 0 0 1px rgba(56, 189, 248, 0.28), 0 14px 28px rgba(0, 0, 0, 0.18);
}

.topology-cell strong {
  align-self: end;
  color: var(--text);
  font-size: 14px;
}

.topology-cell small {
  align-self: end;
  max-width: 100%;
  overflow: hidden;
  color: var(--text-muted);
  font-size: 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.topology-cell i {
  position: absolute;
  right: 6px;
  bottom: 6px;
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: currentColor;
}

.slot-index {
  font-size: 11px;
  font-weight: 800;
}

.topology-cell.empty { background: rgba(255, 255, 255, 0.018); }
.topology-cell.online,
.topology-cell.fresh,
.topology-cell.power-ok { color: var(--green); border-color: rgba(45, 212, 125, 0.55); background: rgba(45, 212, 125, 0.1); }
.topology-cell.warning,
.topology-cell.power-warn { color: var(--amber); border-color: rgba(246, 184, 75, 0.62); background: rgba(246, 184, 75, 0.12); }
.topology-cell.high-power { color: var(--red); border-color: rgba(255, 104, 116, 0.78); background: rgba(255, 104, 116, 0.14); }
.topology-cell.offline,
.topology-cell.stale { color: var(--text-subtle); border-color: rgba(117, 130, 141, 0.45); background: rgba(117, 130, 141, 0.08); }
.topology-cell.maintenance { color: var(--cyan); border-color: rgba(56, 189, 248, 0.58); background: rgba(56, 189, 248, 0.1); }

.topology-legend,
.detail-flags {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.topology-legend span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--text-muted);
  font-size: 12px;
}

.topology-legend span::before {
  content: "";
  width: 9px;
  height: 9px;
  border-radius: 999px;
  background: currentColor;
}

.legend-online { color: var(--green) !important; }
.legend-warning { color: var(--amber) !important; }
.legend-high { color: var(--red) !important; }
.legend-stale { color: var(--text-subtle) !important; }
.legend-empty { color: var(--border-strong) !important; }

.detail-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.detail-head h3,
.empty-slot-detail h3 {
  margin: 0;
}

.detail-power {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.detail-power span {
  display: grid;
  gap: 4px;
  min-height: 68px;
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--panel-soft);
}

.detail-power small,
.detail-list,
.empty-slot-detail p {
  color: var(--text-muted);
}

.detail-power strong {
  font-size: 17px;
}

.detail-list {
  display: grid;
  gap: 8px;
}

.detail-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 40px;
  border: 1px solid var(--cyan);
  border-radius: var(--radius);
  color: #061018;
  background: var(--cyan);
  font-weight: 800;
}

.empty-slot-detail {
  display: grid;
  place-items: center;
  align-content: center;
  min-height: 280px;
  text-align: center;
}

@media (max-width: 1180px) {
  .topology-layout {
    grid-template-columns: 1fr;
  }

  .topology-grid {
    grid-template-columns: repeat(10, minmax(42px, 1fr));
  }
}

@media (max-width: 760px) {
  .topology-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .topology-grid {
    grid-template-columns: repeat(6, minmax(38px, 1fr));
    gap: 7px;
  }

  .topology-cell {
    min-height: 48px;
    padding: 6px;
  }

  .detail-power {
    grid-template-columns: 1fr;
  }
}
</style>
