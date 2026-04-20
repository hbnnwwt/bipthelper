<template>
  <div class="admin">
    <!-- ── Topbar ── -->
    <header class="topbar">
      <div class="topbar-inner">
        <div class="topbar-left">
          <span class="topbar-divider" aria-hidden="true"></span>
          <h1 class="topbar-title">爬虫管理</h1>
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
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import CrawlerTab from '../components/admin/CrawlerTab.vue'
import DocsTab from '../components/admin/DocsTab.vue'
import AuditTab from '../components/admin/AuditTab.vue'

const tab = ref('crawler')
const tabs = [
  { key: 'crawler', label: '爬虫配置' },
  { key: 'docs', label: '文档管理' },
  { key: 'audit', label: '审计日志' },
]

const tabComponents = {
  crawler: CrawlerTab,
  docs: DocsTab,
  audit: AuditTab,
}
const currentTabComponent = computed(() => tabComponents[tab.value])
const router = useRouter()

const username = ref(sessionStorage.getItem('username') || 'Admin')

function switchTab(key) {
  tab.value = key
}

async function handleLogout() {
  try {
    await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' })
  } catch {}
  sessionStorage.removeItem('username')
  window.location.href = '/login'
}
</script>
