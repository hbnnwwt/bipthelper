<template>
  <div class="login-page">
    <!-- Background brand mark -->
    <div class="brand-mark" aria-hidden="true">
      <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
        <rect width="48" height="48" rx="12" fill="var(--color-primary)"/>
        <path d="M14 34V16l10 9 10-9v18" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
        <circle cx="24" cy="13" r="3" fill="white"/>
      </svg>
    </div>

    <div class="login-card">
      <div class="card-header">
        <h1>石化助手</h1>
        <p class="subtitle">登录到管理后台</p>
      </div>

      <form @submit.prevent="handleLogin" novalidate>
        <div class="field">
          <label for="username">用户名</label>
          <input
            id="username"
            v-model="form.username"
            type="text"
            autocomplete="username"
            placeholder="请输入用户名"
            :class="{ error: errors.username }"
            @blur="validateField('username')"
          />
          <span v-if="errors.username" class="field-error">{{ errors.username }}</span>
        </div>

        <div class="field">
          <label for="password">密码</label>
          <input
            id="password"
            v-model="form.password"
            type="password"
            autocomplete="current-password"
            placeholder="请输入密码"
            :class="{ error: errors.password }"
            @blur="validateField('password')"
          />
          <span v-if="errors.password" class="field-error">{{ errors.password }}</span>
        </div>

        <div v-if="error" class="alert alert-error" role="alert">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
            <path d="M8 1.5a6.5 6.5 0 100 13 6.5 6.5 0 000-13zM0 8a8 8 0 1116 0A8 8 0 010 8zm8-3a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 018 5zm0 8a1 1 0 110-2 1 1 0 010 2z"/>
          </svg>
          {{ error }}
        </div>

        <button type="submit" :disabled="loading" class="btn-primary">
          <span v-if="loading" class="spinner" aria-hidden="true"></span>
          {{ loading ? '登录中...' : '登录' }}
        </button>
      </form>

      <p class="register-link">
        没有账号？<router-link to="/register">注册账号</router-link>
      </p>
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

const form = reactive({ username: '', password: '' })
const errors = reactive({ username: '', password: '' })
const error = ref('')
const loading = ref(false)

function validateField(field) {
  if (field === 'username' && !form.username.trim()) {
    errors.username = '请输入用户名'
  } else {
    errors.username = ''
  }
  if (field === 'password' && !form.password) {
    errors.password = '请输入密码'
  } else {
    errors.password = ''
  }
}

function validate() {
  validateField('username')
  validateField('password')
  return !errors.username && !errors.password
}

async function handleLogin() {
  error.value = ''
  if (!validate()) return

  loading.value = true
  try {
    const params = new URLSearchParams()
    params.append('username', form.username)
    params.append('password', form.password)
    const { data } = await api.post('/auth/login', params)
    authStore.setAuth(data.token, data.user)
    router.push('/')
  } catch (e) {
    error.value = e.response?.data?.detail || '登录失败，请检查用户名和密码'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-4);
  background: var(--color-surface);
  /* Subtle geometric background pattern */
  background-image:
    radial-gradient(circle at 20% 20%, rgba(37,99,235,0.04) 0%, transparent 50%),
    radial-gradient(circle at 80% 80%, rgba(37,99,235,0.03) 0%, transparent 50%);
}

.brand-mark {
  margin-bottom: var(--space-6);
  filter: drop-shadow(0 4px 12px rgba(37,99,235,0.25));
}

.login-card {
  width: 100%;
  max-width: 380px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  padding: var(--space-8);
  box-shadow: var(--shadow-lg);
}

.card-header {
  margin-bottom: var(--space-6);
  text-align: center;
}

.card-header h1 {
  font-size: 1.375rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--color-text);
  margin-bottom: var(--space-1);
}

.subtitle {
  font-size: 0.875rem;
  color: var(--color-text-muted);
}

.field {
  margin-bottom: var(--space-4);
}

.field label {
  display: block;
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--color-text-secondary);
  margin-bottom: var(--space-1);
  letter-spacing: 0.01em;
}

.field input {
  width: 100%;
  padding: 0.625rem var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  font-size: 0.9375rem;
  color: var(--color-text);
  background: var(--color-bg);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
  /* Remove browser defaults */
  appearance: none;
  -webkit-appearance: none;
}

.field input::placeholder {
  color: var(--color-text-faint);
}

.field input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(37,99,235,0.12);
}

.field input.error {
  border-color: var(--color-error);
}

.field-error {
  display: block;
  margin-top: var(--space-1);
  font-size: 0.8125rem;
  color: var(--color-error);
}

.alert {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3);
  border-radius: var(--radius);
  font-size: 0.875rem;
  margin-bottom: var(--space-4);
}

.alert-error {
  background: var(--color-danger-bg);
  color: var(--color-danger-text);
  border: 1px solid rgba(220,38,38,0.15);
}

.btn-primary {
  width: 100%;
  padding: 0.6875rem var(--space-4);
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: var(--radius);
  font-size: 0.9375rem;
  font-weight: 500;
  cursor: pointer;
  transition: background var(--transition-fast), transform var(--transition-fast), box-shadow var(--transition-fast);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  box-shadow: 0 1px 2px rgba(37,99,235,0.20);
}

.btn-primary:hover:not(:disabled) {
  background: var(--color-primary-hover);
  box-shadow: 0 4px 8px rgba(37,99,235,0.25);
}

.btn-primary:active:not(:disabled) {
  background: var(--color-primary-active);
  transform: translateY(1px);
  box-shadow: none;
}

.btn-primary:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  flex-shrink: 0;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.register-link {
  margin-top: var(--space-5);
  text-align: center;
  font-size: 0.875rem;
  color: var(--color-text-muted);
}

.register-link a {
  color: var(--color-primary);
  font-weight: 500;
  text-decoration: none;
  transition: color var(--transition-fast);
}

.register-link a:hover {
  color: var(--color-primary-hover);
  text-decoration: underline;
}
</style>
