<script setup lang="ts">
import { RefreshCcw, ShieldCheck, Users } from 'lucide-vue-next';
import { ElMessage, ElMessageBox } from 'element-plus';
import { onMounted, ref } from 'vue';
import { fetchAccountUsers, updateAccountUserRole } from '@/api/lab';
import type { AccountUser, UserRole } from '@/types/domain';
import { formatDateTime, roleLabel } from '@/utils/format';

const users = ref<AccountUser[]>([]);
const loading = ref(false);
const error = ref('');

const roleOptions: Array<{ label: string; value: UserRole; detail: string }> = [
  { label: '只读', value: 'viewer', detail: '只能查看数据，不能确认告警或下发指令' },
  { label: '实验员', value: 'experimenter', detail: '可确认告警、下发设备指令' },
  { label: '管理员', value: 'admin', detail: '可管理用户权限，并拥有实验员权限' }
];

async function load() {
  loading.value = true;
  error.value = '';
  try {
    users.value = await fetchAccountUsers();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '用户列表加载失败';
  } finally {
    loading.value = false;
  }
}

async function changeRole(user: AccountUser, role: UserRole) {
  if (user.role === role) return;

  const target = roleOptions.find((item) => item.value === role);
  try {
    await ElMessageBox.confirm(`确认把 ${user.username} 的权限调整为「${target?.label ?? role}」？`, '权限调整', {
      type: 'warning',
      confirmButtonText: '确认调整',
      cancelButtonText: '取消'
    });
    const next = await updateAccountUserRole(user.id, role);
    users.value = users.value.map((item) => (item.id === next.id ? next : item));
    ElMessage.success('权限已更新');
  } catch (cause) {
    if (cause !== 'cancel') {
      ElMessage.error(cause instanceof Error ? cause.message : '权限更新失败');
      await load();
    }
  }
}

function roleTagType(role: UserRole) {
  if (role === 'admin') return 'danger';
  if (role === 'experimenter') return 'warning';
  return 'info';
}

function getRoleLabel(role: UserRole) {
  return roleLabel[role];
}

onMounted(load);
</script>

<template>
  <div class="stack gap-lg">
    <section class="toolbar">
      <div>
        <p class="eyebrow">Access Control</p>
        <h2>用户权限</h2>
        <p>新注册账号默认为只读；管理员可按实验需要升级为实验员或管理员。</p>
      </div>
      <el-button :loading="loading" @click="load">
        <RefreshCcw :size="17" />
        刷新
      </el-button>
    </section>

    <section class="dashboard-summary">
      <section v-for="option in roleOptions" :key="option.value" class="metric-card">
        <div class="metric-icon">
          <ShieldCheck v-if="option.value === 'admin'" :size="20" />
          <Users v-else :size="20" />
        </div>
        <div>
          <p>{{ option.label }}</p>
          <strong>{{ users.filter((user) => user.role === option.value).length }}</strong>
          <span>{{ option.detail }}</span>
        </div>
      </section>
    </section>

    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />

    <el-card shadow="never">
      <el-table v-loading="loading" :data="users" stripe>
        <el-table-column prop="username" label="账号" min-width="160" />
        <el-table-column prop="name" label="姓名" min-width="160" />
        <el-table-column label="当前权限" width="130">
          <template #default="{ row }">
            <el-tag :type="roleTagType(row.role)" effect="dark">{{ getRoleLabel(row.role) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="账号状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.isActive ? 'success' : 'info'">{{ row.isActive ? '启用' : '禁用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="注册时间" min-width="180">
          <template #default="{ row }">{{ formatDateTime(row.createdAt) }}</template>
        </el-table-column>
        <el-table-column label="调整权限" width="190" fixed="right">
          <template #default="{ row }">
            <el-select :model-value="row.role" @change="(role: UserRole) => changeRole(row, role)">
              <el-option
                v-for="option in roleOptions"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>
