<template>
  <div class="tab-content">
    <div class="section-toolbar">
      <h2 class="section-title">用户管理</h2>
    </div>

    <div class="card">
      <h3 class="card-title">邀请新用户</h3>
      <div class="invite-form">
        <input v-model="newUsername" type="text" placeholder="输入用户名" class="input" @keyup.enter="createInvite" />
        <button @click="createInvite" class="btn-primary btn-sm">生成邀请码</button>
      </div>
      <div v-if="generatedCode" class="invite-code">
        邀请码：<code class="code">{{ generatedCode }}</code>
        <button @click="copyCode" class="btn-ghost-xs" title="复制">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>
          </svg>
        </button>
      </div>
    </div>

    <div class="card">
      <h3 class="card-title">已有用户</h3>
      <table class="data-table">
        <thead>
          <tr>
            <th scope="col">用户名</th>
            <th scope="col">角色</th>
            <th scope="col">状态</th>
            <th scope="col">积分</th>
            <th scope="col">创建时间</th>
            <th scope="col">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.id">
            <td class="cell-username">{{ u.username }}</td>
            <td><span class="badge" :class="u.role === 'admin' ? 'badge-primary' : 'badge-muted'">{{ u.role }}</span></td>
            <td><span class="status-dot" :class="u.is_active ? 'dot-active' : 'dot-inactive'"></span>{{ u.is_active ? '活跃' : '未激活' }}</td>
            <td class="cell-points">{{ u.points ?? 0 }}</td>
            <td class="cell-muted">{{ u.created_at?.slice(0, 16) }}</td>
            <td class="cell-actions">
              <button @click="openPointsModal(u)" class="btn-ghost-xs">修改积分</button>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- 修改积分 Modal -->
      <div v-if="showPointsModal" class="modal-overlay" @click.self="closePointsModal">
        <div class="modal">
          <h3 class="modal-title">修改积分 - {{ pointsModalUser?.username }}</h3>
          <div class="modal-body">
            <div class="current-points">当前积分：{{ pointsModalUser?.points ?? 0 }}</div>
            <div class="field">
              <label>操作类型</label>
              <select v-model="pointsForm.type" class="input">
                <option value="delta">增减积分</option>
                <option value="set">设置积分为</option>
              </select>
            </div>
            <div class="field">
              <label>{{ pointsForm.type === 'delta' ? '增减数量（正数增加，负数扣除）' : '积分值' }}</label>
              <input v-model.number="pointsForm.value" type="number" class="input" placeholder="0" />
            </div>
          </div>
          <div class="modal-actions">
            <button @click="closePointsModal" class="btn-outline">取消</button>
            <button @click="submitPoints" :disabled="pointsSubmitting" class="btn-primary">
              {{ pointsSubmitting ? '提交中...' : '确认' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../../api'
import { useToast } from '../../composables/toast'

const { success, error } = useToast()

const users = ref([])
const newUsername = ref('')
const generatedCode = ref('')
const showPointsModal = ref(false)
const pointsModalUser = ref(null)
const pointsForm = ref({ type: 'delta', value: 0 })
const pointsSubmitting = ref(false)

async function loadUsers() {
  try {
    const { data } = await api.get('/admin/users')
    users.value = data.users
  } catch (e) { error('加载用户列表失败') }
}

async function createInvite() {
  if (!newUsername.value.trim()) return
  try {
    const { data } = await api.post('/admin/users/invite', null, { params: { username: newUsername.value } })
    generatedCode.value = data.invite_code
    success('邀请码已生成')
  } catch (e) { error(e.response?.data?.detail || '生成邀请码失败') }
}

function copyCode() {
  navigator.clipboard.writeText(generatedCode.value)
  success('已复制到剪贴板')
}

function openPointsModal(u) {
  pointsModalUser.value = u
  pointsForm.value = { type: 'delta', value: 0 }
  showPointsModal.value = true
}

function closePointsModal() {
  showPointsModal.value = false
  pointsModalUser.value = null
}

async function submitPoints() {
  if (pointsForm.value.value === 0) return
  try {
    const params = pointsForm.value.type === 'delta'
      ? { delta: pointsForm.value.value }
      : { set_value: pointsForm.value.value }
    await api.patch(`/admin/users/${pointsModalUser.value.id}/points`, null, { params })
    success('积分已更新')
    closePointsModal()
    loadUsers()
  } catch (e) { error(e.response?.data?.detail || '更新积分失败') }
}

onMounted(() => { loadUsers() })
</script>

<style scoped>
.tab-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.section-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--space-3);
}

.section-title {
  font-size: 0.9375rem;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.card {
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
}

.card-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--color-text-secondary);
  margin-bottom: var(--space-3);
}

.data-table {
  font-size: 0.875rem;
}

.data-table th {
  text-align: left;
  padding: 0.625rem 0.75rem;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--color-text-muted);
  letter-spacing: 0.04em;
  text-transform: uppercase;
  border-bottom: 1px solid var(--color-border);
}

.data-table td {
  padding: 0.75rem 0.75rem;
  border-bottom: 1px solid var(--color-border);
  vertical-align: middle;
}

.data-table tr:last-child td {
  border-bottom: none;
}

.data-table tr:hover td {
  background: var(--color-surface);
}

.cell-username {
  font-weight: 500;
}

.cell-muted {
  color: var(--color-text-muted);
  font-size: 0.8125rem;
}

.cell-points {
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}

.cell-actions {
  white-space: nowrap;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
}

.modal {
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  width: 360px;
  max-width: 90vw;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
}

.modal-title {
  font-size: 0.9375rem;
  font-weight: 600;
  margin-bottom: var(--space-3);
}

.modal-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.current-points {
  font-size: 0.875rem;
  color: var(--color-text-secondary);
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.field label {
  font-size: 0.8125rem;
  color: var(--color-text-muted);
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-4);
}

.btn-outline {
  padding: 0.5rem 1rem;
  background: transparent;
  color: var(--color-text);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: background var(--transition-fast);
}

.btn-outline:hover {
  background: var(--color-surface);
}

.badge {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: var(--radius-full);
  font-size: 0.75rem;
  font-weight: 500;
  letter-spacing: 0.01em;
}

.badge-primary {
  background: var(--color-primary-muted);
  color: var(--color-primary-text);
}

.badge-muted {
  background: var(--color-surface);
  color: var(--color-text-muted);
  border: 1px solid var(--color-border);
}

.status-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  margin-right: 5px;
  vertical-align: middle;
}

.dot-active {
  background: #22c55e;
}

.dot-inactive {
  background: var(--color-text-faint);
}

.invite-form {
  display: flex;
  gap: var(--space-2);
  align-items: center;
  margin-bottom: var(--space-3);
}

.invite-form .input {
  width: 200px;
}

.invite-code {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  font-size: 0.875rem;
}

.code {
  font-family: var(--font-mono);
  font-size: 0.9375rem;
  font-weight: 600;
  background: var(--color-bg);
  padding: 0.1rem 0.4rem;
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-border);
}

.btn-primary {
  padding: 0.5rem 1rem;
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: var(--radius);
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: background var(--transition-fast), transform var(--transition-fast), box-shadow var(--transition-fast);
  box-shadow: 0 1px 2px rgba(37, 99, 235, 0.2);
}

.btn-primary:hover {
  background: var(--color-primary-hover);
  box-shadow: 0 3px 6px rgba(37, 99, 235, 0.25);
}

.btn-primary:active {
  background: var(--color-primary-active);
  transform: translateY(1px);
  box-shadow: none;
}

.btn-sm {
  padding: 0.375rem 0.75rem;
  font-size: 0.8125rem;
}

.btn-ghost-xs {
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--color-text-muted);
  background: none;
  border: none;
  cursor: pointer;
  padding: 0.2rem 0.4rem;
  border-radius: var(--radius);
  transition: background var(--transition-fast), color var(--transition-fast);
}

.btn-ghost-xs:hover {
  background: var(--color-surface);
  color: var(--color-text);
}

.btn-ghost-xs:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.input {
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  font-size: 0.875rem;
  background: var(--color-bg);
  color: var(--color-text);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.input::placeholder {
  color: var(--color-text-faint);
}
</style>
