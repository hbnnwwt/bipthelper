<template>
  <div class="tab-content">
    <div class="section-toolbar">
      <h2 class="section-title">操作审计</h2>
      <div class="toolbar-actions">
        <button @click="loadLogs" class="btn-outline btn-sm">刷新</button>
      </div>
    </div>

    <div class="card">
      <table class="data-table">
        <thead>
          <tr>
            <th>时间</th>
            <th>用户</th>
            <th>操作</th>
            <th>详情</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="log in logs" :key="log.id">
            <td class="cell-muted">{{ log.created_at?.slice(0, 16) }}</td>
            <td>{{ log.username }}</td>
            <td><span class="badge badge-muted">{{ actionLabel(log.action) }}</span></td>
            <td class="cell-muted">{{ log.detail || '—' }}</td>
          </tr>
          <tr v-if="logs.length === 0">
            <td colspan="4" class="cell-empty">暂无日志</td>
          </tr>
        </tbody>
      </table>

      <div v-if="totalPages > 1" class="pagination">
        <button @click="page--; loadLogs()" :disabled="page <= 1" class="btn-outline btn-sm">上一页</button>
        <span class="page-indicator">第 {{ page }} / {{ totalPages }} 页</span>
        <button @click="page++; loadLogs()" :disabled="page >= totalPages" class="btn-outline btn-sm">下一页</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import api from '../../api'
import { useToast } from '../../composables/toast'

const props = defineProps(['tab'])
const { success, error } = useToast()

const logs = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)

const totalPages = computed(() => Math.ceil(total.value / pageSize))

const actionLabel = (action) => ({
  delete_doc: '删除文档',
  batch_delete_docs: '批量删除',
  add_config: '添加配置',
  delete_config: '删除配置',
  toggle_config: '切换配置',
  trigger_crawl: '触发爬取',
  stop_crawl: '停止爬取',
  approve_category: '采纳AI',
  update_category: '修改分类',
  reset_password: '重置密码',
  create_invite: '生成邀请码',
}[action] || action)

async function loadLogs() {
  loading.value = true
  try {
    const { data } = await api.get('/admin/audit', { params: { page: page.value, page_size: pageSize } })
    logs.value = data.logs
    total.value = data.total
  } catch (e) {
    error('加载审计日志失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => { loadLogs() })

watch(() => props.tab, (newTab) => {
  if (newTab === 'audit') { page.value = 1; loadLogs() }
})
</script>

<style scoped>
.audit-tab { display: flex; flex-direction: column; gap: var(--space-4); }
</style>
