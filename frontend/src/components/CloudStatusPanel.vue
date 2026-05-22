<script setup lang="ts">
import { formatDateTime } from '@/utils/format';

interface LocalGatewayStatus {
  platform: string;
  productId: string;
  deviceId: string;
  nodeId: string;
  connectionStatus: 'connected' | 'disconnected' | 'unknown';
  shadowVersion: number;
  ruleEngine: 'enabled' | 'disabled' | 'pending';
  lastSync: string | null;
  syncStatus: 'synced' | 'delayed' | 'disconnected' | 'unbound';
}

defineProps<{
  gateway: LocalGatewayStatus;
  compact?: boolean;
}>();

const syncLabel: Record<LocalGatewayStatus['syncStatus'], string> = {
  synced: '已入库',
  delayed: '上报延迟',
  disconnected: '连接中断',
  unbound: '未接入'
};

const connectionLabel: Record<LocalGatewayStatus['connectionStatus'], string> = {
  connected: 'HTTP已接入',
  disconnected: 'HTTP已断开',
  unknown: '未知'
};
</script>

<template>
  <el-card class="panel-card" shadow="never">
    <template #header>
      <div class="section-heading">
        <div>
          <p class="eyebrow">Local Gateway</p>
          <h2>本地后端接入状态</h2>
        </div>
        <el-tag
          :type="gateway.syncStatus === 'synced' ? 'success' : gateway.syncStatus === 'delayed' ? 'warning' : 'danger'"
          effect="dark"
        >
          {{ syncLabel[gateway.syncStatus] }}
        </el-tag>
      </div>
    </template>

    <div class="gateway-grid" :class="{ compact }">
      <div class="gateway-cell">
        <span>接入方式</span>
        <strong>HTTPJSON</strong>
      </div>
      <div class="gateway-cell">
        <span>后端服务</span>
        <strong>DjangoREST</strong>
      </div>
      <div class="gateway-cell">
        <span>设备ID</span>
        <strong>{{ gateway.deviceId }}</strong>
      </div>
      <div class="gateway-cell">
        <span>Node ID</span>
        <strong>{{ gateway.nodeId }}</strong>
      </div>
      <div class="gateway-cell">
        <span>连接状态</span>
        <strong>{{ connectionLabel[gateway.connectionStatus] }}</strong>
      </div>
      <div class="gateway-cell">
        <span>状态版本</span>
        <strong>v{{ gateway.shadowVersion }}</strong>
      </div>
      <div class="gateway-cell">
        <span>规则引擎</span>
        <strong>{{ gateway.ruleEngine === 'enabled' ? '已启用' : gateway.ruleEngine === 'pending' ? '待配置' : '未启用' }}</strong>
      </div>
      <div class="gateway-cell">
        <span>最近入库</span>
        <strong>{{ formatDateTime(gateway.lastSync) }}</strong>
      </div>
    </div>
  </el-card>
</template>
