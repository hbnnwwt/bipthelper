<template>
  <div class="admin">
    <!-- ── Topbar ── -->
    <header class="topbar">
      <div class="topbar-inner">
        <div class="topbar-left">
          <router-link to="/" class="back-link">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="m15 18-6-6 6-6"/>
            </svg>
            返回搜索
          </router-link>
          <span class="topbar-divider" aria-hidden="true"></span>
          <h1 class="topbar-title">管理后台</h1>
        </div>
        <div class="topbar-right">
          <span class="topbar-user">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/>
            </svg>
            {{ username }}
          </span>
          <button @click="handleLogout" class="topbar-logout">退出</button>
        </div>
      </div>
    </header>

    <!-- ── Tab bar ── -->
    <nav class="tabbar" role="tablist">
      <button
        v-for="t in tabs"
        :key="t.key"
        role="tab"
        :aria-selected="tab === t.key"
        :class="{ active: tab === t.key }"
        @click="switchTab(t.key)"
      >{{ t.label }}</button>
    </nav>

    <!-- ── Tab content ── -->
    <main class="content">
      <component :is="currentTabComponent" :tab="tab" />
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import UsersTab from '../components/admin/UsersTab.vue'
import CrawlerTab from '../components/admin/CrawlerTab.vue'
import DocsTab from '../components/admin/DocsTab.vue'
import AuditTab from '../components/admin/AuditTab.vue'
import InviteCodesTab from '../components/admin/InviteCodesTab.vue'

const tab = ref('users')
const tabs = [
  { key: 'users', label: '用户管理' },
  { key: 'crawler', label: '爬虫配置' },
  { key: 'docs', label: '文档管理' },
  { key: 'audit', label: '审计日志' },
  { key: 'codes', label: '激活码' },
  { key: 'ai', label: 'AI 配置' },
]

const tabComponents = {
  users: UsersTab,
  crawler: CrawlerTab,
  docs: DocsTab,
  audit: AuditTab,
  codes: InviteCodesTab,
}
const currentTabComponent = computed(() => tabComponents[tab.value])
const router = useRouter()

// Read username from sessionStorage (set by Login.vue after auth)
const username = ref(sessionStorage.getItem('username') || 'Admin')

function switchTab(key) {
  if (key === 'ai') {
    router.push('/admin/ai')
  } else {
    tab.value = key
  }
}

function handleLogout() {
  sessionStorage.removeItem('token')
  sessionStorage.removeItem('username')
  router.push('/login')
}
</script>

<style scoped>
/* ── Easing curve for all state transitions ── */
.admin { --ease-out: cubic-bezier(0.16, 1, 0.3, 1); }

/* ── Topbar ── */
.topbar {
  background: var(--color-bg);
  border-bottom: 1px solid var(--color-border);
  position: sticky;
  top: 0;
  z-index: 10;
}
.topbar-inner {
  max-width: 100%;
  padding: 0 var(--space-5);
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.topbar-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.topbar-right {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.back-link {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--color-text-muted);
  text-decoration: none;
  transition: color var(--transition-fast);
}
.back-link:hover { color: var(--color-text); }

.topbar-divider {
  display: block;
  width: 1px;
  height: 16px;
  background: var(--color-border);
}

.topbar-title {
  font-size: 0.9375rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--color-text);
}

.topbar-user {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.8125rem;
  color: var(--color-text-muted);
}

.topbar-logout {
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--color-text-muted);
  background: none;
  border: none;
  cursor: pointer;
  padding: 0.25rem 0.5rem;
  border-radius: var(--radius);
  transition: color var(--transition-fast), background var(--transition-fast);
}
.topbar-logout:hover {
  color: var(--color-text);
  background: var(--color-surface);
}

/* ── Tab bar ── */
.tabbar {
  display: flex;
  gap: 0;
  background: var(--color-bg);
  border-bottom: 1px solid var(--color-border);
  padding: 0 var(--space-5);
  overflow-x: auto;
}
.tabbar button {
  position: relative;
  padding: 0.75rem 1.125rem 0.7rem;
  border: none;
  background: none;
  cursor: pointer;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--color-text-muted);
  white-space: nowrap;
  transition: color 200ms var(--ease-out);
}
.tabbar button::after {
  content: '';
  position: absolute;
  bottom: -1px;
  left: 0;
  right: 0;
  height: 2px;
  background: var(--color-primary);
  border-radius: 2px 2px 0 0;
  transform: scaleX(0);
  transition: transform 200ms var(--ease-out);
}
.tabbar button:hover { color: var(--color-text); }
.tabbar button.active {
  color: var(--color-primary);
}
.tabbar button.active::after {
  transform: scaleX(1);
}

/* ── Content area ── */
.content {
  padding: var(--space-5);
  max-width: 100%;
}

/* ── Responsive ── */
@media (max-width: 768px) {
  .topbar-inner { padding: 0 var(--space-3); }
  .topbar-title { font-size: 0.875rem; }
  .tabbar { padding: 0 var(--space-3); }
  .content { padding: var(--space-3); }
  .tabbar button { padding: 0.6rem 0.75rem 0.55rem; }
}
</style>
