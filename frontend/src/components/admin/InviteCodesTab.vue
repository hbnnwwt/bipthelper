<template>
  <div class="invite-codes-tab">
    <!-- 创建表单 -->
    <div class="create-form">
      <div class="form-row">
        <select v-model="createType" class="filter-select">
          <option value="designated">指定用户</option>
          <option value="anonymous">任意用户</option>
        </select>
        <input v-if="createType === 'designated'"
          v-model="createUsername" type="text"
          placeholder="预填用户名"
          class="input" />
        <button @click="createCode" class="btn-primary" :disabled="creating">
          {{ creating ? '创建中...' : '生成激活码' }}
        </button>
      </div>
      <div v-if="newCode" class="code-result">
        激活码：<code class="code">{{ newCode.code }}</code>
        <span class="code-meta">{{ newCode.type === 'designated' ? '指定用户: ' + newCode.designated_username : '任意用户' }} · 有效期至 {{ newCode.expires_at }}</span>
      </div>
    </div>

    <!-- 列表 -->
    <div class="table-wrapper">
      <table class="data-table">
        <thead>
          <tr>
            <th>激活码</th><th>类型</th><th>预填用户</th>
            <th>状态</th><th>到期时间</th><th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in codes" :key="c.code">
            <td><code>{{ c.code }}</code></td>
            <td><span class="badge" :class="c.type === 'designated' ? 'badge-primary' : 'badge-muted'">
              {{ c.type === 'designated' ? '指定用户' : '任意用户' }}
            </span></td>
            <td>{{ c.designated_username || '—' }}</td>
            <td><span class="status-badge" :class="'status-' + c.status">
              {{ c.status === 'active' ? '待激活' : c.status === 'used' ? '已使用' : '已过期' }}
            </span></td>
            <td class="cell-mono">{{ c.expires_at }}</td>
            <td>
              <button @click="deleteCode(c.code)" class="btn-ghost-xs btn-text-danger">删除</button>
            </td>
          </tr>
          <tr v-if="codes.length === 0">
            <td colspan="6" class="cell-empty">暂无激活码</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../../api'

const codes = ref([])
const createType = ref('designated')
const createUsername = ref('')
const creating = ref(false)
const newCode = ref(null)

async function loadCodes() {
  const { data } = await api.get('/admin/codes')
  codes.value = data.codes
}

async function createCode() {
  if (createType.value === 'designated' && !createUsername.value.trim()) {
    alert('请输入预填用户名')
    return
  }
  creating.value = true
  try {
    const payload = { type: createType.value }
    if (createType.value === 'designated') {
      payload.username = createUsername.value
    }
    const { data } = await api.post('/admin/codes', payload)
    newCode.value = data
    createUsername.value = ''
    await loadCodes()
  } catch (e) {
    newCode.value = null
    alert(e.response?.data?.detail || '创建失败')
  } finally {
    creating.value = false
  }
}

async function deleteCode(code) {
  if (!confirm('确定删除该激活码？')) return
  try {
    await api.delete(`/admin/codes/${code}`)
    await loadCodes()
  } catch (e) {
    alert(e.response?.data?.detail || '删除失败')
  }
}

onMounted(loadCodes)
</script>

<style scoped>
.invite-codes-tab {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

.create-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.form-row {
  display: flex;
  gap: var(--space-3);
  align-items: center;
}

.filter-select {
  padding: 0.5rem 0.75rem;
  border: 1.5px solid var(--color-border);
  border-radius: var(--radius-lg);
  font-size: 0.875rem;
  background: var(--color-bg);
  color: var(--color-text);
}

.input {
  padding: 0.5rem 0.75rem;
  border: 1.5px solid var(--color-border);
  border-radius: var(--radius-lg);
  font-size: 0.875rem;
  background: var(--color-bg);
  color: var(--color-text);
  outline: none;
}

.input:focus {
  border-color: var(--color-primary);
}

.btn-primary {
  padding: 0.5rem 1rem;
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: var(--radius-lg);
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
}

.btn-primary:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.code-result {
  padding: var(--space-3);
  background: var(--color-surface);
  border-radius: var(--radius-lg);
  font-size: 0.875rem;
}

.code {
  font-family: var(--font-mono);
  font-weight: 600;
  letter-spacing: 0.04em;
}

.code-meta {
  margin-left: var(--space-3);
  color: var(--color-text-muted);
}

.table-wrapper {
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}

.data-table th {
  text-align: left;
  padding: var(--space-2) var(--space-3);
  border-bottom: 1.5px solid var(--color-border);
  font-weight: 600;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--color-text-muted);
}

.data-table td {
  padding: var(--space-3);
  border-bottom: 1px solid var(--color-border);
  color: var(--color-text);
}

.cell-mono {
  font-family: var(--font-mono);
  font-size: 0.8125rem;
}

.cell-empty {
  text-align: center;
  color: var(--color-text-faint);
  padding: var(--space-8);
}

.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
}

.badge-primary {
  background: var(--color-primary-bg, rgba(59,130,246,0.1));
  color: var(--color-primary);
}

.badge-muted {
  background: var(--color-surface);
  color: var(--color-text-muted);
}

.status-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
}

.status-active {
  background: rgba(34,197,94,0.1);
  color: #16a34a;
}

.status-used {
  background: rgba(59,130,246,0.1);
  color: #2563eb;
}

.status-expired {
  background: rgba(220,38,38,0.1);
  color: #dc2626;
}

.btn-ghost-xs {
  padding: 2px 8px;
  background: transparent;
  border: none;
  border-radius: var(--radius);
  font-size: 0.8125rem;
  cursor: pointer;
}

.btn-text-danger {
  color: var(--color-danger, #dc2626);
}

.btn-text-danger:hover {
  background: rgba(220,38,38,0.1);
}
</style>
