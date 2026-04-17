<template>
  <div class="auth-layout">
    <!-- Brand panel -->
    <div class="brand-panel" aria-hidden="true">
      <div class="brand-inner">
        <div class="brand-logo">
          <svg width="40" height="40" viewBox="0 0 44 44" fill="none">
            <rect width="44" height="44" rx="12" fill="var(--color-primary)"/>
            <path d="M12 32V16l10 8 10-8v16" stroke="white" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round"/>
            <circle cx="22" cy="13" r="2.75" fill="white"/>
          </svg>
        </div>
        <div class="brand-text">
          <span class="brand-name">石化助手</span>
          <span class="brand-tagline">精准检索校园信息</span>
        </div>
      </div>
      <div class="brand-footer">
        <p class="brand-meta">内部信息系统 &middot; 完成注册以开始使用</p>
      </div>
    </div>

    <!-- Form panel -->
    <div class="form-panel">
      <div class="form-container">
        <div class="form-header">
          <h1 class="form-title">创建账号</h1>
          <p class="form-sub">注册后即可使用石化助手搜索</p>
        </div>

        <!-- Step indicator -->
        <div class="steps" aria-label="注册进度">
          <div class="step" :class="{ 'step--active': true, 'step--done': false }">
            <span class="step-dot"></span>
            <span class="step-label">账号信息</span>
          </div>
          <div class="step-line"></div>
          <div class="step" :class="{ 'step--active': false, 'step--done': false }">
            <span class="step-dot"></span>
            <span class="step-label">完成注册</span>
          </div>
        </div>

        <form @submit.prevent="handleRegister" novalidate class="form">
          <div class="field">
            <label for="username" class="label">用户名（匿名邀请码可选）</label>
            <input
              id="username"
              v-model="form.username"
              type="text"
              autocomplete="username"
              class="input"
              :class="{ 'input--error': errors.username }"
              @blur="validateField('username')"
            />
            <span v-if="errors.username" class="field-error" role="alert">{{ errors.username }}</span>
          </div>

          <div class="field">
            <label for="password" class="label">密码</label>
            <input
              id="password"
              v-model="form.password"
              type="password"
              autocomplete="new-password"
              class="input"
              :class="{ 'input--error': errors.password }"
              @blur="validateField('password')"
            />
            <span v-if="errors.password" class="field-error" role="alert">{{ errors.password }}</span>
          </div>

          <div class="field">
            <label for="invite_code" class="label">邀请码</label>
            <input
              id="invite_code"
              v-model="form.invite_code"
              type="text"
              autocomplete="off"
              spellcheck="false"
              class="input input--mono"
              :class="{ 'input--error': errors.invite_code }"
              @blur="validateField('invite_code')"
            />
            <span v-if="errors.invite_code" class="field-error" role="alert">{{ errors.invite_code }}</span>
          </div>

          <div v-if="error" class="alert-error" role="alert">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            {{ error }}
          </div>

          <button type="submit" :disabled="loading" class="btn-submit">
            <span v-if="loading" class="spinner" aria-hidden="true"></span>
            {{ loading ? '注册中...' : '注册' }}
          </button>
        </form>

        <p class="alt-link">
          已有账号？<router-link to="/login" class="link">直接登录</router-link>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import api from '../api'

const router = useRouter()
const authStore = useAuthStore()

const form = reactive({ username: '', password: '', invite_code: '' })
const errors = reactive({ username: '', password: '', invite_code: '' })
const error = ref('')
const loading = ref(false)

function validateField(field) {
  if (field === 'username' && form.username.trim() && form.username.trim().length < 6) {
    errors.username = '用户名至少6个字符'
  } else {
    errors.username = ''
  }
  if (field === 'password' && form.password.length < 6) {
    errors.password = '密码至少6个字符'
  } else {
    errors.password = ''
  }
  if (field === 'invite_code' && !form.invite_code.trim()) {
    errors.invite_code = '请输入邀请码'
  } else {
    errors.invite_code = ''
  }
}

function validate() {
  // username is optional (anonymous codes don't need it; designated codes validated server-side)
  validateField('password')
  validateField('invite_code')
  return !errors.password && !errors.invite_code
}

async function handleRegister() {
  error.value = ''
  if (!validate()) return

  loading.value = true
  try {
    const { data } = await api.post('/auth/register', form)
    authStore.setAuth(data.token, data.user)
    router.push('/')
  } catch (e) {
    error.value = e.response?.data?.detail || '注册失败，请检查邀请码是否正确'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
/* ─── Layout ─── */
.auth-layout {
  min-height: 100dvh;
  display: grid;
  grid-template-columns: 420px 1fr;
}

/* ─── Brand Panel ─── */
.brand-panel {
  background: var(--color-surface);
  border-right: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: var(--space-8);
  position: relative;
  overflow: hidden;
}

.brand-panel::before {
  content: '';
  position: absolute;
  top: -80px;
  right: -80px;
  width: 280px;
  height: 280px;
  border: 1px solid var(--color-border);
  border-radius: 50%;
  pointer-events: none;
}
.brand-panel::after {
  content: '';
  position: absolute;
  top: -40px;
  right: -40px;
  width: 160px;
  height: 160px;
  border: 1px solid var(--color-border-strong);
  border-radius: 50%;
  pointer-events: none;
}

.brand-inner {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  animation: fadeSlideDown 300ms cubic-bezier(0.16, 1, 0.3, 1) both;
}

.brand-logo {
  flex-shrink: 0;
}

.brand-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.brand-name {
  font-size: 1.125rem;
  font-weight: 700;
  letter-spacing: -0.03em;
  color: var(--color-text);
  line-height: 1.2;
}

.brand-tagline {
  font-size: 0.8125rem;
  color: var(--color-text-muted);
  letter-spacing: 0.01em;
}

.brand-footer {
  animation: fadeSlideUp 300ms cubic-bezier(0.16, 1, 0.3, 1) 80ms both;
}

.brand-meta {
  font-size: 0.75rem;
  color: var(--color-text-faint);
  letter-spacing: 0.02em;
}

/* ─── Form Panel ─── */
.form-panel {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-8);
  background: var(--color-bg);
}

.form-container {
  width: 100%;
  max-width: 360px;
  animation: fadeSlideUp 300ms cubic-bezier(0.16, 1, 0.3, 1) 120ms both;
}

.form-header {
  margin-bottom: var(--space-6);
}

.form-title {
  font-size: 1.75rem;
  font-weight: 700;
  letter-spacing: -0.04em;
  color: var(--color-text);
  margin-bottom: 6px;
}

.form-sub {
  font-size: 0.9375rem;
  color: var(--color-text-muted);
}

/* ─── Step Indicator ─── */
.steps {
  display: flex;
  align-items: center;
  gap: 0;
  margin-bottom: var(--space-6);
  animation: fadeSlideUp 300ms cubic-bezier(0.16, 1, 0.3, 1) 160ms both;
}

.step {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.step-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-border-strong);
  flex-shrink: 0;
  transition: background 200ms;
}

.step--active .step-dot {
  background: var(--color-primary);
}

.step-label {
  font-size: 0.6875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--color-text-muted);
  transition: color 200ms;
}

.step--active .step-label {
  color: var(--color-text-secondary);
}

.step-line {
  flex: 1;
  height: 1px;
  background: var(--color-border);
  margin: 0 var(--space-3);
  min-width: 24px;
}

/* ─── Form Fields ─── */
.form {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.field {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.label {
  font-size: 0.6875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--color-text-secondary);
}

.input {
  width: 100%;
  padding: 0.75rem var(--space-3);
  border: 1.5px solid var(--color-border);
  border-radius: var(--radius-lg);
  font-size: 1rem;
  color: var(--color-text);
  background: var(--color-bg);
  font-family: var(--font-sans);
  transition: border-color 150ms, box-shadow 150ms;
  outline: none;
}

.input::placeholder { color: var(--color-text-faint); }

.input:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-muted);
}

.input--error {
  border-color: var(--color-error);
}
.input--error:focus {
  box-shadow: 0 0 0 3px var(--color-danger-bg);
}

/* Monospace for invite code — precision feel */
.input--mono {
  font-family: var(--font-mono);
  font-size: 0.9375rem;
  letter-spacing: 0.04em;
}

.field-error {
  font-size: 0.8rem;
  color: var(--color-error);
  display: flex;
  align-items: center;
  gap: 4px;
}

/* ─── Alert ─── */
.alert-error {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-3);
  background: var(--color-danger-bg);
  color: var(--color-danger-text);
  border: 1px solid rgba(220, 38, 38, 0.2);
  border-radius: var(--radius-lg);
  font-size: 0.875rem;
  line-height: 1.4;
}

/* ─── Submit Button ─── */
.btn-submit {
  width: 100%;
  padding: 0.875rem;
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: var(--radius-lg);
  font-size: 0.9375rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 150ms, transform 80ms, box-shadow 150ms;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  letter-spacing: -0.01em;
  margin-top: var(--space-2);
}
.btn-submit:hover:not(:disabled) {
  background: var(--color-primary-hover);
}
.btn-submit:active:not(:disabled) {
  transform: scale(0.985);
}
.btn-submit:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.65s linear infinite;
  flex-shrink: 0;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ─── Alt Link ─── */
.alt-link {
  margin-top: var(--space-6);
  text-align: center;
  font-size: 0.875rem;
  color: var(--color-text-muted);
}
.link {
  color: var(--color-primary);
  font-weight: 500;
  text-decoration: underline;
  text-underline-offset: 2px;
}
.link:hover {
  color: var(--color-primary-hover);
}

/* ─── Animations ─── */
@keyframes fadeSlideUp {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes fadeSlideDown {
  from { opacity: 0; transform: translateY(-12px); }
  to { opacity: 1; transform: translateY(0); }
}

/* ─── Mobile ─── */
@media (max-width: 768px) {
  .auth-layout {
    grid-template-columns: 1fr;
    grid-template-rows: auto 1fr;
  }

  .brand-panel {
    border-right: none;
    border-bottom: 1px solid var(--color-border);
    padding: var(--space-6);
    justify-content: flex-start;
    gap: var(--space-4);
  }

  .brand-panel::before,
  .brand-panel::after {
    display: none;
  }

  .brand-footer {
    display: none;
  }

  .form-panel {
    padding: var(--space-6);
    align-items: flex-start;
  }

  .form-container {
    max-width: 100%;
  }

  .form-header {
    margin-bottom: var(--space-6);
  }
}

@media (max-width: 480px) {
  .brand-panel {
    padding: var(--space-5) var(--space-4);
  }

  .form-panel {
    padding: var(--space-5) var(--space-4);
  }
}
</style>
