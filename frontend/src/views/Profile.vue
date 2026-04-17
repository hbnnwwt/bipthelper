<template>
  <div class="profile-page">
    <!-- Top nav -->
    <header class="profile-nav">
      <router-link to="/" class="btn-back" aria-label="返回">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5"/><path d="m12 19-7-7 7-7"/></svg>
      </router-link>
      <h1 class="nav-title">个人中心</h1>
    </header>

    <!-- Section 1: Avatar & Info -->
    <section class="card profile-card">
      <div class="avatar-area" @click="triggerAvatarUpload">
        <img v-if="auth.avatarUrl" :src="auth.avatarUrl" alt="头像" class="avatar-img" />
        <div v-else class="avatar-letter">{{ (displayName || '?')[0].toUpperCase() }}</div>
        <div class="avatar-overlay">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>
        </div>
        <input ref="avatarInput" type="file" accept="image/jpeg,image/png,image/webp" style="display:none" @change="onAvatarSelected" />
      </div>
      <div class="profile-info">
        <div class="name-row">
          <span class="display-name">{{ displayName }}</span>
          <span v-if="auth.isAdmin" class="role-badge admin">管理员</span>
          <span v-else class="role-badge user">普通用户</span>
        </div>
        <span class="username">@{{ auth.user?.username }}</span>
        <span class="join-date">{{ formatDate(auth.user?.created_at) }} 加入</span>
      </div>
    </section>

    <!-- Section 2: Points & Checkin -->
    <section class="card">
      <div class="section-header">
        <h2 class="section-title">积分</h2>
      </div>
      <div class="points-row">
        <div class="points-num-area">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
          <span class="points-num">{{ auth.points }}</span>
        </div>
        <button v-if="!checkedInToday && !checkingIn" class="btn-checkin" @click="doCheckin">每日签到 +5</button>
        <button v-else-if="checkingIn" class="btn-checkin" disabled>签到中...</button>
        <span v-else class="checked-text">今日已签到</span>
      </div>

      <div class="records-area">
        <h3 class="subsection-title">积分明细</h3>
        <div v-if="records.length === 0" class="empty">暂无积分记录</div>
        <div v-else class="record-list">
          <div v-for="r in records" :key="r.id" class="record-item">
            <div class="record-left">
              <span class="type-badge" :class="'type-' + r.record_type">{{ typeLabel(r.record_type) }}</span>
              <span class="record-note">{{ r.note || '-' }}</span>
            </div>
            <div class="record-right">
              <span class="amount" :class="r.amount > 0 ? 'pos' : 'neg'">{{ r.amount > 0 ? '+' : '' }}{{ r.amount }}</span>
              <span class="record-time">{{ formatRecordTime(r.created_at) }}</span>
            </div>
          </div>
        </div>
        <button v-if="hasMore" class="btn-more" @click="loadMore">加载更多</button>
      </div>
    </section>

    <!-- Section 3: Account Settings -->
    <section class="card">
      <h2 class="section-title">账号设置</h2>

      <div class="setting-item">
        <label class="setting-label">昵称</label>
        <div class="setting-row">
          <input v-model="editNickname" type="text" class="setting-input" placeholder="设置昵称" maxlength="20" />
          <button class="btn-save" @click="saveProfile('nickname')" :disabled="savingProfile">保存</button>
        </div>
      </div>

      <div class="setting-item">
        <label class="setting-label">手机号</label>
        <div class="setting-row">
          <input v-model="editPhone" type="tel" class="setting-input" placeholder="绑定手机号" maxlength="15" />
          <button class="btn-save" @click="saveProfile('phone')" :disabled="savingProfile">保存</button>
        </div>
      </div>

      <div class="setting-item">
        <label class="setting-label">修改密码</label>
        <div class="password-form">
          <input v-model="oldPassword" type="password" class="setting-input" placeholder="当前密码" />
          <input v-model="newPassword" type="password" class="setting-input" placeholder="新密码（至少6位）" />
          <input v-model="confirmPassword" type="password" class="setting-input" placeholder="确认新密码" />
          <button class="btn-save" @click="savePassword" :disabled="savingPassword">修改密码</button>
        </div>
      </div>
    </section>

    <!-- Section 4: Logout -->
    <button class="btn-logout" @click="handleLogout">退出登录</button>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useToast } from '../composables/toast'
import api from '../api'

const auth = useAuthStore()
const router = useRouter()
const toast = useToast()

const checkedInToday = ref(false)
const checkingIn = ref(false)
const records = ref([])
const page = ref(1)
const hasMore = ref(false)
const savingProfile = ref(false)
const savingPassword = ref(false)

const editNickname = ref(auth.nickname || '')
const editPhone = ref(auth.phone || '')
const oldPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')

const avatarInput = ref(null)

const displayName = computed(() => auth.nickname || auth.user?.username || '用户')

function formatDate(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  } catch { return iso }
}

function typeLabel(type) {
  return { register: '注册', checkin: '签到', qa: '问答', admin_set: '管理员' }[type] || type
}

function formatRecordTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('zh-CN', { timeZone: 'UTC' })
}

// Avatar
function triggerAvatarUpload() {
  avatarInput.value?.click()
}

async function onAvatarSelected(e) {
  const file = e.target.files?.[0]
  if (!file) return
  if (file.size > 2 * 1024 * 1024) {
    toast.error('图片不能超过 2MB')
    return
  }
  const formData = new FormData()
  formData.append('file', file)
  try {
    const { data } = await api.post('/auth/avatar', formData)
    auth.avatarUrl = data.avatar_url
    localStorage.setItem('avatarUrl', data.avatar_url)
    toast.success('头像更新成功')
  } catch (err) {
    toast.error(err.response?.data?.detail || '头像上传失败')
  }
  e.target.value = ''
}

// Checkin
async function doCheckin() {
  checkingIn.value = true
  try {
    const { data } = await api.post('/points/checkin')
    auth.points = data.points
    checkedInToday.value = data.checked_in_today !== undefined ? data.checked_in_today : true
    auth.lastCheckinDate = data.last_checkin_date || ''
    localStorage.setItem('points', String(data.points))
    if (auth.lastCheckinDate) localStorage.setItem('lastCheckinDate', auth.lastCheckinDate)
    await loadRecords(1)
    toast.success('签到成功 +5')
  } catch (e) {
    toast.error(e.response?.data?.detail || '签到失败')
  } finally {
    checkingIn.value = false
  }
}

// Records
async function loadRecords(p = 1) {
  const { data } = await api.get(`/points/records?page=${p}&page_size=20`)
  if (p === 1) records.value = data.records
  else records.value.push(...data.records)
  hasMore.value = records.value.length < data.total
  page.value = p
}

function loadMore() {
  loadRecords(page.value + 1)
}

// Profile update
async function saveProfile(field) {
  savingProfile.value = true
  try {
    const body = {}
    if (field === 'nickname') body.nickname = editNickname.value
    if (field === 'phone') body.phone = editPhone.value
    await api.put('/auth/profile', body)
    if (field === 'nickname') {
      auth.nickname = editNickname.value || null
      localStorage.setItem('nickname', auth.nickname || '')
    }
    if (field === 'phone') {
      auth.phone = editPhone.value || null
      localStorage.setItem('phone', auth.phone || '')
    }
    toast.success('保存成功')
  } catch (e) {
    toast.error(e.response?.data?.detail || '保存失败')
  } finally {
    savingProfile.value = false
  }
}

// Password
async function savePassword() {
  if (newPassword.value.length < 6) {
    toast.error('新密码至少6个字符')
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    toast.error('两次密码输入不一致')
    return
  }
  savingPassword.value = true
  try {
    await api.put('/auth/password', { old_password: oldPassword.value, new_password: newPassword.value })
    oldPassword.value = ''
    newPassword.value = ''
    confirmPassword.value = ''
    toast.success('密码修改成功')
  } catch (e) {
    toast.error(e.response?.data?.detail || '密码修改失败')
  } finally {
    savingPassword.value = false
  }
}

// Logout
async function handleLogout() {
  await auth.logout()
  router.push('/login')
}

onMounted(async () => {
  try {
    const { data } = await api.get('/auth/me')
    checkedInToday.value = data.checked_in_today || false
    editNickname.value = data.user?.nickname || ''
    editPhone.value = data.user?.phone || ''
  } catch {}
  loadRecords(1)
})
</script>

<style scoped>
.profile-page {
  max-width: 640px;
  margin: 0 auto;
  padding: var(--space-4) var(--space-6) var(--space-8);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.profile-nav {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-2);
}

.btn-back {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: var(--radius-md);
  color: var(--color-text-muted);
  text-decoration: none;
  transition: color var(--transition-fast), background var(--transition-fast);
}
.btn-back:hover {
  color: var(--color-text);
  background: var(--color-surface-hover);
}

.nav-title {
  font-size: 1.125rem;
  font-weight: 700;
  color: var(--color-text);
  margin: 0;
}

.card {
  padding: var(--space-5);
  background: var(--color-surface);
  border-radius: var(--radius-xl);
  border: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.section-title {
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-text-faint);
  margin: 0;
}

.subsection-title {
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--color-text-muted);
  margin: 0 0 var(--space-2);
}

.profile-card {
  flex-direction: row;
  align-items: center;
  gap: var(--space-4);
}

.avatar-area {
  position: relative;
  width: 80px;
  height: 80px;
  border-radius: 50%;
  overflow: hidden;
  flex-shrink: 0;
  cursor: pointer;
  background: var(--color-primary-muted);
}

.avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-letter {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.75rem;
  font-weight: 700;
  color: var(--color-primary);
  background: var(--color-primary-muted);
}

.avatar-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.4);
  opacity: 0;
  transition: opacity var(--transition-fast);
}
.avatar-area:hover .avatar-overlay {
  opacity: 1;
}

.profile-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.name-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.display-name {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--color-text);
}

.role-badge {
  font-size: 0.6875rem;
  font-weight: 600;
  padding: 1px 7px;
  border-radius: 999px;
}
.role-badge.admin {
  background: rgba(234, 179, 8, 0.12);
  color: #b45309;
}
.role-badge.user {
  background: var(--color-primary-muted);
  color: var(--color-primary);
}

.username {
  font-size: 0.8125rem;
  color: var(--color-text-muted);
}

.join-date {
  font-size: 0.75rem;
  color: var(--color-text-faint);
}

.points-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.points-num-area {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.points-num {
  font-size: 2rem;
  font-weight: 700;
  color: var(--color-text);
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.btn-checkin {
  padding: 0.5rem 1rem;
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: background var(--transition-fast);
}
.btn-checkin:hover { background: var(--color-primary-hover); }
.btn-checkin:disabled { opacity: 0.5; cursor: not-allowed; }

.checked-text {
  font-size: 0.875rem;
  color: var(--color-success);
  font-weight: 500;
}

.records-area {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px solid var(--color-border);
}

.record-list {
  display: flex;
  flex-direction: column;
  gap: 1px;
  background: var(--color-border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.record-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-3) var(--space-4);
  background: var(--color-surface);
}

.record-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-width: 0;
}

.type-badge {
  font-size: 0.6875rem;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 999px;
  flex-shrink: 0;
}
.type-register { background: rgba(34,197,94,0.1); color: #16a34a; }
.type-checkin { background: rgba(59,130,246,0.1); color: #2563eb; }
.type-qa { background: rgba(156,163,175,0.2); color: #6b7280; }
.type-admin_set { background: rgba(168,85,247,0.1); color: #7c3aed; }

.record-note {
  font-size: 0.8125rem;
  color: var(--color-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.record-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  flex-shrink: 0;
}

.amount { font-weight: 700; font-size: 0.875rem; }
.amount.pos { color: #16a34a; }
.amount.neg { color: #dc2626; }

.record-time { font-size: 0.6875rem; color: var(--color-text-faint); }

.empty {
  padding: var(--space-6);
  text-align: center;
  color: var(--color-text-faint);
  font-size: 0.8125rem;
}

.btn-more {
  width: 100%;
  padding: var(--space-3);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  font-size: 0.8125rem;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: border-color var(--transition-fast);
}
.btn-more:hover { border-color: var(--color-primary); color: var(--color-primary); }

.setting-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding-top: var(--space-3);
  border-top: 1px solid var(--color-border);
}
.setting-item:first-of-type {
  border-top: none;
  padding-top: 0;
}

.setting-label {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--color-text);
}

.setting-row {
  display: flex;
  gap: var(--space-2);
}

.setting-input {
  flex: 1;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-family: var(--font-sans);
  font-size: 0.875rem;
  color: var(--color-text);
  background: var(--color-bg);
  outline: none;
  transition: border-color var(--transition-fast);
}
.setting-input:focus { border-color: var(--color-primary); }
.setting-input::placeholder { color: var(--color-text-faint); }

.password-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.btn-save {
  padding: 0.5rem 1rem;
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: 0.8125rem;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  transition: background var(--transition-fast);
}
.btn-save:hover { background: var(--color-primary-hover); }
.btn-save:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-logout {
  padding: 0.75rem;
  background: transparent;
  border: 1px solid var(--color-error);
  border-radius: var(--radius-lg);
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--color-error);
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast);
}
.btn-logout:hover {
  background: var(--color-error);
  color: white;
}

@media (max-width: 640px) {
  .profile-page { padding: var(--space-3) var(--space-4) var(--space-6); }
  .profile-card { flex-direction: column; text-align: center; }
  .profile-info { align-items: center; }
  .points-row { flex-direction: column; gap: var(--space-3); align-items: flex-start; }
}
</style>
