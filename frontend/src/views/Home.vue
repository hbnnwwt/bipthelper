<template>
  <div class="home">
    <!-- Header -->
    <header class="header">
      <div class="header-inner">
        <div class="header-brand">
          <svg width="20" height="20" viewBox="0 0 22 22" fill="none" aria-hidden="true">
            <rect width="22" height="22" rx="5" fill="var(--color-primary)"/>
            <path d="M6 16V8l5 4 5-4v8" stroke="white" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <span class="brand-name">石化助手</span>
        </div>
        <nav class="header-nav" aria-label="主要导航">
          <router-link to="/" class="nav-link">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
            对话
          </router-link>
          <button @click="toggleTheme" class="btn-icon" :title="theme === 'dark' ? '浅色模式' : '深色模式'" :aria-label="theme === 'dark' ? '切换到浅色模式' : '切换到深色模式'">
            <svg v-if="theme === 'dark'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>
            </svg>
            <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
            </svg>
          </button>
          <button @click="showPasswordChange = !showPasswordChange" class="btn-ghost-sm" :class="{ active: showPasswordChange }">{{ showPasswordChange ? '取消' : '修改密码' }}</button>
          <router-link v-if="authStore.isAdmin" to="/admin" class="nav-link">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="8" r="4"/><path d="M20 21a8 8 0 00-16 0"/>
            </svg>
            管理
          </router-link>
          <router-link to="/points" class="points-badge" title="积分">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>
            </svg>
            {{ authStore.points }}
          </router-link>
          <button @click="handleLogout" class="btn-ghost-sm">退出</button>
        </nav>
      </div>
    </header>

    <!-- Password change bar -->
    <div v-if="showPasswordChange" class="password-bar" role="region" aria-label="修改密码">
      <div class="password-bar-inner">
        <span class="password-label">修改密码</span>
        <label for="old-pwd" class="sr-only">旧密码</label>
        <input id="old-pwd" v-model="passwordForm.old_password" type="password" class="field-sm" placeholder="旧密码" autocomplete="current-password" />
        <label for="new-pwd" class="sr-only">新密码</label>
        <input id="new-pwd" v-model="passwordForm.new_password" type="password" class="field-sm" placeholder="新密码" autocomplete="new-password" />
        <label for="confirm-pwd" class="sr-only">确认密码</label>
        <input id="confirm-pwd" v-model="passwordForm.confirm_password" type="password" class="field-sm" placeholder="确认密码" autocomplete="new-password" @keyup.enter="handlePasswordChange" />
        <button @click="handlePasswordChange" class="btn-primary-xs" :disabled="passwordLoading">
          <span v-if="passwordLoading" class="spinner-xs" aria-hidden="true"></span>
          <span v-else>确认</span>
        </button>
      </div>
    </div>

    <main class="main">

      <!-- ═══════════════════════════════════════════
           HERO: Asymmetric — search dominant left
           ═══════════════════════════════════════════ -->
      <section class="hero" aria-label="搜索区域">

        <!-- Left: Search is the tool -->
        <div class="hero-search">
          <div class="search-instrument" :class="{ focused: searchFocused }">
            <div class="search-input-row">
              <svg class="search-sym" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
              </svg>
              <input
                v-model="query"
                type="search"
                aria-label="搜索学校通知与文档"
                placeholder="输入关键词搜索…"
                class="search-field"
                @keyup.enter="handleSearch"
                @focus="searchFocused = true"
                @blur="searchFocused = false"
              />
              <button @click="handleSearch" class="search-submit" :disabled="loading" aria-label="执行搜索">
                <span v-if="loading" class="spinner-xs" aria-hidden="true"></span>
                <span v-else>搜索</span>
              </button>
            </div>
          </div>

          <!-- Filter toolbar -->
          <div class="filter-bar" role="group" aria-label="搜索筛选">
            <div class="filter-seg">
              <label for="filter-cat" class="filter-lbl">分类</label>
              <select id="filter-cat" v-model="filters.category" class="filter-sel" @change="handleSearch">
                <option value="">全部</option>
                <option value="通知">通知</option>
                <option value="制度">制度</option>
              </select>
            </div>
            <div class="filter-seg">
              <label for="filter-dept" class="filter-lbl">部门</label>
              <input
                id="filter-dept"
                v-model="filters.department"
                type="text"
                class="filter-text"
                placeholder="输入部门名"
                @keyup.enter="handleSearch"
                aria-label="部门筛选"
              />
            </div>
            <button @click="showFilters = !showFilters" class="filter-more" :class="{ active: showFilters }" :aria-expanded="showFilters ? 'true' : 'false'">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <path d="m6 9 6 6 6-6"/>
              </svg>
              日期
            </button>
          </div>

          <!-- Date filter expand -->
          <div v-if="showFilters" class="date-filter" role="group" aria-label="日期范围">
            <span class="date-label">发布时间</span>
            <input v-model="filters.start_date" type="date" class="date-input" aria-label="开始日期" />
            <span class="date-sep">—</span>
            <input v-model="filters.end_date" type="date" class="date-input" aria-label="结束日期" />
            <button @click="handleSearch" class="date-apply">应用</button>
          </div>
        </div>

        <!-- Right: Editorial text -->
        <div class="hero-editorial">
          <p class="hero-eyebrow">学校通知搜索引擎</p>
          <h1 class="hero-heading">
            <span class="hero-heading-line">精确搜索</span>
            <span class="hero-heading-line hero-heading-accent">制度与通知</span>
          </h1>
          <p class="hero-desc">覆盖通知公告、规章制度、工作动态等文档。支持分类、部门、日期等多维度筛选。</p>
        </div>

      </section>

      <!-- ═══════════════════════════════════════════
           RESULTS
           ═══════════════════════════════════════════ -->
      <section class="results-area" aria-label="搜索结果">

        <!-- Results meta -->
        <div v-if="total" class="results-meta">
          <span class="results-n">{{ total }}</span>
          <span class="results-unit">条结果</span>
          <span v-if="query" class="results-query">/ {{ query }}</span>
        </div>

        <!-- ── Loading: geometric skeleton ── -->
        <div v-if="loading" class="result-list" aria-busy="true" aria-label="加载中">
          <div v-for="i in 5" :key="i" class="sk-block" :style="{ animationDelay: ((i - 1) * 55) + 'ms' }">
            <div class="sk-row sk-row--title"></div>
            <div class="sk-row sk-row--body"></div>
            <div class="sk-row sk-row--body sk-row--short"></div>
            <div class="sk-row sk-row--meta"></div>
          </div>
        </div>

        <!-- ── Empty state: teach the interface ── -->
        <div v-else-if="results.length === 0 && searched" class="empty-state" role="status">
          <div class="empty-panel">
            <div class="empty-left">
              <p class="empty-head">未找到相关结果</p>
              <p class="empty-sub">试试以下搜索方式，或浏览系统中的文档</p>

              <div class="query-examples" role="list" aria-label="搜索示例">
                <p class="examples-label">你可以尝试</p>
                <button
                  v-for="ex in exampleQueries"
                  :key="ex"
                  class="example-chip"
                  @click="query = ex; handleSearch()"
                  role="listitem"
                >{{ ex }}</button>
              </div>
            </div>

            <div class="empty-right">
              <p class="examples-label">或浏览热门文档</p>
              <div v-if="recentDocs.length > 0" class="doc-list" role="list">
                <a
                  v-for="item in recentDocs"
                  :key="item.id"
                  :href="item.url"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="doc-item"
                  role="listitem"
                >
                  <div class="doc-item-title">{{ item.title }}</div>
                  <div class="doc-item-meta">
                    <span v-if="item.category" class="doc-cat">{{ item.category }}</span>
                    <span v-if="item.department" class="doc-dept">{{ item.department }}</span>
                    <span v-if="item.publish_date" class="doc-date">{{ item.publish_date }}</span>
                  </div>
                </a>
              </div>
              <div v-else-if="recentLoading" class="recent-loading">
                <span class="spinner-xs"></span>
              </div>
            </div>
          </div>
        </div>

        <!-- ── Results list: typography-driven ── -->
        <div v-else-if="results.length > 0" class="result-list" role="list">
          <a
            v-for="(item, idx) in results"
            :key="item.id"
            :href="item.url"
            target="_blank"
            rel="noopener noreferrer"
            class="result-item"
            role="listitem"
            :style="{ animationDelay: (idx * 45) + 'ms' }"
          >
            <div class="result-body">
              <h3 class="result-title" v-html="sanitize(item._formatted?.title) || item.title"></h3>
              <p class="result-excerpt" v-html="sanitize(item._formatted?.content) || item.content"></p>
            </div>
            <div class="result-aside">
              <div class="result-meta">
                <span v-if="item.category" class="meta-cat">{{ item.category }}</span>
                <span v-if="item.department" class="meta-dept">{{ item.department }}</span>
              </div>
              <span v-if="item.publish_date" class="meta-date">{{ item.publish_date }}</span>
              <svg class="result-arrow" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M7 17L17 7M17 7H7M17 7v10"/>
              </svg>
            </div>
          </a>
        </div>

        <!-- ── Pagination ── -->
        <div v-if="totalPages > 1" class="pagination" role="navigation" aria-label="分页">
          <button @click="page--; handleSearch()" :disabled="page <= 1" class="btn-page">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="m15 18-6-6 6-6"/></svg>
            上一页
          </button>
          <span class="page-info" aria-current="page">{{ page }} / {{ totalPages }}</span>
          <button @click="page++; handleSearch()" :disabled="page >= totalPages" class="btn-page">
            下一页
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="m9 18 6-6-6-6"/></svg>
          </button>
        </div>

      </section>
    </main>
  </div>
</template>

<script setup>
import { ref, reactive, computed, inject } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useToast } from '../composables/toast'
import api from '../api'
import DOMPurify from 'dompurify'

const sanitize = (html) => DOMPurify.sanitize(html || '', { ALLOWED_TAGS: ['mark'] })

const router = useRouter()
const authStore = useAuthStore()
const toggleTheme = inject('toggleTheme')
const theme = inject('theme')
const toast = useToast()

const query = ref('')
const filters = reactive({ category: '', department: '', start_date: '', end_date: '' })
const showPasswordChange = ref(false)
const passwordForm = reactive({ old_password: '', new_password: '', confirm_password: '' })
const passwordLoading = ref(false)
const showFilters = ref(false)
const searchFocused = ref(false)
const results = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const searched = ref(false)
const recentDocs = ref([])
const recentLoading = ref(false)

const totalPages = computed(() => Math.ceil(total.value / pageSize))

const exampleQueries = [
  '考试安排', '奖学金申请', '请假制度', '实验室开放', '教务通知'
]

async function handleSearch() {
  if (!query.value.trim() && !filters.category && !filters.department) return
  loading.value = true
  page.value = 1
  try {
    const params = { q: query.value, page: page.value, page_size: pageSize }
    if (filters.category) params.category = filters.category
    if (filters.department) params.department = filters.department
    if (filters.start_date) params.start_date = filters.start_date
    if (filters.end_date) params.end_date = filters.end_date

    const { data } = await api.get('/search', { params })
    results.value = data.results
    total.value = data.total
    searched.value = true
    if (data.results.length === 0) loadRecentDocs()
  } catch (e) {
    console.error('Search failed:', e)
    results.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function handleLogout() {
  authStore.logout()
  router.push('/login')
}

async function loadRecentDocs() {
  recentLoading.value = true
  try {
    const { data } = await api.get('/search/recent')
    recentDocs.value = data.docs
  } catch (e) {
    console.error('Failed to load recent docs:', e)
  } finally {
    recentLoading.value = false
  }
}

async function handlePasswordChange() {
  if (!passwordForm.old_password) { toast.error('请输入旧密码'); return }
  if (!passwordForm.new_password) { toast.error('请输入新密码'); return }
  if (passwordForm.new_password.length < 6) { toast.error('新密码至少6个字符'); return }
  if (passwordForm.new_password !== passwordForm.confirm_password) { toast.error('两次输入的新密码不一致'); return }
  passwordLoading.value = true
  try {
    await api.put('/auth/password', null, {
      params: { old_password: passwordForm.old_password, new_password: passwordForm.new_password }
    })
    passwordForm.old_password = ''
    passwordForm.new_password = ''
    passwordForm.confirm_password = ''
    showPasswordChange.value = false
    toast.success('密码修改成功')
  } catch (e) { toast.error(e.response?.data?.detail || '修改密码失败') }
  finally { passwordLoading.value = false }
}
</script>

<style scoped>
/* ══════════════════════════════════════
   ROOT & TOKENS
   ══════════════════════════════════════ */
.home {
  min-height: 100dvh;
  background: var(--color-bg);
}

/* ── Header ── */
.header {
  position: sticky;
  top: 0;
  z-index: 20;
  background: var(--color-bg);
  border-bottom: 1px solid var(--color-border);
}
.header-inner {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 2rem;
  height: 54px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.header-brand {
  display: flex;
  align-items: center;
  gap: 9px;
}
.brand-name {
  font-size: 0.9375rem;
  font-weight: 700;
  letter-spacing: -0.03em;
  color: var(--color-text);
}
.header-nav {
  display: flex;
  align-items: center;
  gap: 2px;
}
.btn-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: var(--radius);
  color: var(--color-text-muted);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast);
}
.btn-icon:hover {
  background: var(--color-surface);
  color: var(--color-text);
}
.nav-link {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--color-text-secondary);
  text-decoration: none;
  padding: 0.3rem 0.6rem;
  border-radius: var(--radius);
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast);
}
.nav-link:hover { background: var(--color-surface); color: var(--color-text); }
.points-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--color-primary);
  text-decoration: none;
  padding: 0.3rem 0.6rem;
  border-radius: var(--radius);
  background: var(--color-primary-muted);
  transition: background var(--transition-fast), color var(--transition-fast);
}
.points-badge:hover { background: var(--color-primary); color: white; }
.btn-ghost-sm {
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--color-text-muted);
  padding: 0.3rem 0.6rem;
  border-radius: var(--radius);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast);
}
.btn-ghost-sm:hover { background: var(--color-surface); color: var(--color-text); }
.btn-ghost-sm.active { color: var(--color-primary); }

/* ── Password bar ── */
.password-bar {
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  animation: slideDown 280ms cubic-bezier(0.16, 1, 0.3, 1);
}
.password-bar-inner {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0.625rem 2rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.password-label {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--color-text-secondary);
  white-space: nowrap;
  margin-right: 0.25rem;
}
.field-sm {
  padding: 0.3rem 0.6rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: 0.8125rem;
  color: var(--color-text);
  background: var(--color-bg);
  font-family: var(--font-sans);
  outline: none;
  transition: border-color var(--transition-fast);
  min-width: 110px;
}
.field-sm:focus { border-color: var(--color-primary); }
.field-sm::placeholder { color: var(--color-text-faint); }
.btn-primary-xs {
  padding: 0.3rem 0.75rem;
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: var(--radius-sm);
  font-size: 0.8125rem;
  font-weight: 500;
  cursor: pointer;
  transition: background var(--transition-fast), transform 80ms;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.btn-primary-xs:hover:not(:disabled) { background: var(--color-primary-hover); }
.btn-primary-xs:active:not(:disabled) { transform: scale(0.97); }
.btn-primary-xs:disabled { opacity: 0.5; cursor: not-allowed; }

/* ══════════════════════════════════════
   MAIN CONTAINER
   ══════════════════════════════════════ */
.main {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 2rem;
}

/* ══════════════════════════════════════
   HERO: Asymmetric grid
   Left = search dominant, Right = editorial
   ══════════════════════════════════════ */
.hero {
  display: grid;
  grid-template-columns: 3fr 2fr;
  gap: 3rem;
  align-items: center;
  padding: 4rem 0 3rem;
  border-bottom: 1px solid var(--color-border);
  margin-bottom: 2.5rem;
}

/* ── Search instrument (left) ── */
.hero-search {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.search-instrument {
  border: 1.5px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface-raised);
  transition: border-color 200ms cubic-bezier(0.16, 1, 0.3, 1);
}
.search-instrument.focused {
  border-color: var(--color-primary);
}

.search-input-row {
  display: flex;
  align-items: center;
  padding: 0 0.75rem;
  gap: 0;
}
.search-sym {
  color: var(--color-text-muted);
  flex-shrink: 0;
  margin-right: 10px;
}
.search-field {
  flex: 1;
  padding: 0.75rem 0;
  border: none;
  background: transparent;
  font-size: 1rem;
  color: var(--color-text);
  outline: none;
  min-width: 0;
  font-family: var(--font-sans);
}
.search-field::placeholder { color: var(--color-text-faint); }
.search-field::-webkit-search-cancel-button { display: none; }

.search-submit {
  flex-shrink: 0;
  padding: 0.5rem 1rem;
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: var(--radius-sm);
  font-size: 0.8125rem;
  font-weight: 600;
  cursor: pointer;
  transition: background var(--transition-fast), transform 80ms;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  letter-spacing: -0.01em;
  margin: 5px 0;
}
.search-submit:hover:not(:disabled) { background: var(--color-primary-hover); }
.search-submit:active:not(:disabled) { transform: scale(0.97); }
.search-submit:disabled { opacity: 0.55; cursor: not-allowed; }

/* ── Filter toolbar ── */
.filter-bar {
  display: flex;
  align-items: center;
  gap: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  overflow: hidden;
}
.filter-seg {
  display: flex;
  align-items: center;
  border-right: 1px solid var(--color-border);
}
.filter-seg:last-of-type { border-right: none; }
.filter-lbl {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--color-text-muted);
  padding: 0 0.5rem 0 0.625rem;
  white-space: nowrap;
  letter-spacing: 0.01em;
  text-transform: uppercase;
}
.filter-sel {
  padding: 0.45rem 0.5rem;
  border: none;
  background: transparent;
  font-size: 0.8125rem;
  color: var(--color-text-secondary);
  font-family: var(--font-sans);
  cursor: pointer;
  outline: none;
  -webkit-appearance: none;
  appearance: none;
}
.filter-sel:focus { background: var(--color-surface-hover); }
.filter-text {
  padding: 0.45rem 0.5rem;
  border: none;
  background: transparent;
  font-size: 0.8125rem;
  color: var(--color-text-secondary);
  font-family: var(--font-sans);
  outline: none;
  min-width: 90px;
}
.filter-text::placeholder { color: var(--color-text-faint); }
.filter-text:focus { background: var(--color-surface-hover); }
.filter-more {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--color-text-muted);
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 0.45rem 0.75rem;
  transition: background var(--transition-fast), color var(--transition-fast);
  white-space: nowrap;
  letter-spacing: 0.01em;
  text-transform: uppercase;
}
.filter-more:hover { background: var(--color-surface-hover); color: var(--color-text); }
.filter-more.active { color: var(--color-primary); }

/* ── Date filter expand ── */
.date-filter {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  animation: expandDown 280ms cubic-bezier(0.16, 1, 0.3, 1);
}
.date-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--color-text-muted);
  white-space: nowrap;
  letter-spacing: 0.01em;
  text-transform: uppercase;
}
.date-sep { color: var(--color-text-faint); font-size: 0.875rem; }
.date-input {
  padding: 0.3rem 0.4rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: 0.8125rem;
  background: var(--color-bg);
  color: var(--color-text);
  font-family: var(--font-sans);
  outline: none;
  transition: border-color var(--transition-fast);
}
.date-input:focus { border-color: var(--color-primary); }
.date-apply {
  margin-left: auto;
  padding: 0.3rem 0.75rem;
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: var(--radius-sm);
  font-size: 0.75rem;
  font-weight: 600;
  cursor: pointer;
  transition: background var(--transition-fast);
}
.date-apply:hover { background: var(--color-primary-hover); }

/* ── Editorial (right) ── */
.hero-editorial {
  padding-left: 0.5rem;
  border-left: 1px solid var(--color-border);
}
.hero-eyebrow {
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--color-primary);
  margin-bottom: 0.875rem;
}
.hero-heading {
  display: flex;
  flex-direction: column;
  gap: 0;
  margin-bottom: 1rem;
}
.hero-heading-line {
  font-size: clamp(1.75rem, 3.5vw, 2.5rem);
  font-weight: 800;
  letter-spacing: -0.04em;
  line-height: 1.05;
  color: var(--color-text);
  display: block;
}
.hero-heading-accent {
  color: var(--color-primary);
}
.hero-desc {
  font-size: 0.875rem;
  color: var(--color-text-muted);
  line-height: 1.7;
  max-width: 300px;
}

/* ══════════════════════════════════════
   RESULTS AREA
   ══════════════════════════════════════ */
.results-area {
  padding-bottom: 5rem;
}

/* ── Results meta ── */
.results-meta {
  display: flex;
  align-items: baseline;
  gap: 0.25rem;
  margin-bottom: 1.5rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--color-border);
}
.results-n {
  font-size: 1.5rem;
  font-weight: 800;
  color: var(--color-text);
  letter-spacing: -0.04em;
  font-variant-numeric: tabular-nums;
}
.results-unit {
  font-size: 0.875rem;
  color: var(--color-text-muted);
}
.results-query {
  font-size: 0.875rem;
  color: var(--color-text-faint);
  margin-left: 0.25rem;
  font-family: var(--font-mono);
}

/* ══════════════════════════════════════
   RESULT LIST
   ══════════════════════════════════════ */
.result-list {
  display: flex;
  flex-direction: column;
}

/* ── Skeleton: geometric blocks ── */
.sk-block {
  padding: 1.25rem 0;
  border-bottom: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  animation: skEnter 350ms cubic-bezier(0.16, 1, 0.3, 1) both;
}
.sk-row {
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  height: 12px;
}
.sk-row--title {
  width: 42%;
  height: 16px;
  background: var(--color-surface-hover);
}
.sk-row--body { width: 88%; }
.sk-row--short { width: 60%; }
.sk-row--meta { width: 25%; height: 10px; }

@keyframes skEnter {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

/* ── Result item: typography-driven list ── */
.result-item {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 1.5rem;
  align-items: start;
  padding: 1.25rem 0;
  border-bottom: 1px solid var(--color-border);
  text-decoration: none;
  color: inherit;
  transition: background 200ms cubic-bezier(0.16, 1, 0.3, 1);
  animation: resultEnter 350ms cubic-bezier(0.16, 1, 0.3, 1) both;
}
.result-item:hover { background: var(--color-surface); margin: 0 -1rem; padding-left: 1rem; padding-right: 1rem; }

.result-body {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
  min-width: 0;
}
.result-title {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--color-text);
  letter-spacing: -0.015em;
  line-height: 1.4;
}
.result-title :deep(mark) {
  background: var(--color-highlight-bg);
  color: inherit;
  padding: 0 2px;
  border-radius: 2px;
}
.result-excerpt {
  font-size: 0.8125rem;
  color: var(--color-text-secondary);
  line-height: 1.65;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.result-excerpt :deep(mark) {
  background: var(--color-highlight-bg);
  color: inherit;
  padding: 0 2px;
  border-radius: 2px;
}

.result-aside {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.375rem;
  flex-shrink: 0;
  padding-top: 2px;
}
.result-meta {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.meta-cat {
  display: inline-block;
  font-size: 0.6875rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 0.15rem 0.4rem;
  border-radius: var(--radius-sm);
  background: var(--color-primary-muted);
  color: var(--color-primary-text);
}
.meta-dept {
  font-size: 0.6875rem;
  font-weight: 600;
  color: var(--color-text-muted);
  white-space: nowrap;
}
.meta-date {
  font-size: 0.6875rem;
  color: var(--color-text-faint);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.result-arrow {
  color: var(--color-text-faint);
  transition: color var(--transition-fast), transform 200ms cubic-bezier(0.16, 1, 0.3, 1);
  margin-top: 2px;
}
.result-item:hover .result-arrow {
  color: var(--color-primary);
  transform: translate(2px, -2px);
}

@keyframes resultEnter {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}

/* ══════════════════════════════════════
   EMPTY STATE: teach the interface
   ══════════════════════════════════════ */
.empty-state {
  animation: fadeIn 300ms ease;
}
.empty-panel {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 2.5rem;
  padding: 1.5rem 0;
}
.empty-left,
.empty-right {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.empty-head {
  font-size: 1.0625rem;
  font-weight: 700;
  color: var(--color-text);
  letter-spacing: -0.02em;
}
.empty-sub {
  font-size: 0.875rem;
  color: var(--color-text-muted);
  line-height: 1.6;
}
.query-examples {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-top: 0.25rem;
}
.examples-label {
  font-size: 0.6875rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--color-text-faint);
}
.example-chip {
  display: block;
  width: fit-content;
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--color-text-secondary);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 0.4rem 0.75rem;
  cursor: pointer;
  text-align: left;
  transition: border-color var(--transition-fast), color var(--transition-fast), background var(--transition-fast);
  font-family: var(--font-sans);
}
.example-chip:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
  background: var(--color-primary-muted);
}

.doc-list {
  display: flex;
  flex-direction: column;
  gap: 0;
}
.doc-item {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.625rem 0;
  border-bottom: 1px solid var(--color-border);
  text-decoration: none;
  color: inherit;
  transition: background var(--transition-fast);
}
.doc-item:last-child { border-bottom: none; }
.doc-item:hover .doc-item-title { color: var(--color-primary); }
.doc-item-title {
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--color-text);
  transition: color var(--transition-fast);
  line-height: 1.4;
  flex: 1;
}
.doc-item-meta {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  flex-shrink: 0;
}
.doc-cat {
  font-size: 0.6875rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 0.1rem 0.35rem;
  border-radius: var(--radius-sm);
  background: var(--color-primary-muted);
  color: var(--color-primary-text);
}
.doc-dept, .doc-date {
  font-size: 0.6875rem;
  color: var(--color-text-faint);
}
.recent-loading {
  display: flex;
  justify-content: center;
  padding: 1rem;
}

/* ══════════════════════════════════════
   PAGINATION
   ══════════════════════════════════════ */
.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1.5rem;
  margin-top: 3rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--color-border);
}
.btn-page {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 0.5rem 1rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--color-text-secondary);
  background: var(--color-bg);
  cursor: pointer;
  transition: border-color 180ms, color 180ms, transform 80ms;
}
.btn-page:hover:not(:disabled) {
  border-color: var(--color-primary);
  color: var(--color-primary);
}
.btn-page:active:not(:disabled) { transform: scale(0.98); }
.btn-page:disabled { opacity: 0.35; cursor: not-allowed; }
.page-info {
  font-size: 0.8125rem;
  color: var(--color-text-muted);
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.01em;
}

/* ══════════════════════════════════════
   SPINNER
   ══════════════════════════════════════ */
.spinner-xs {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 1.5px solid rgba(255,255,255,0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ══════════════════════════════════════
   ANIMATIONS
   ══════════════════════════════════════ */
@keyframes slideDown {
  from { opacity: 0; transform: translateY(-8px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes expandDown {
  from { opacity: 0; transform: translateY(-6px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

/* ══════════════════════════════════════
   RESPONSIVE
   ══════════════════════════════════════ */
@media (max-width: 900px) {
  .hero {
    grid-template-columns: 1fr;
    gap: 2rem;
    padding: 2.5rem 0 2rem;
  }
  .hero-editorial {
    padding-left: 0;
    border-left: none;
    padding-top: 0;
    border-top: 1px solid var(--color-border);
  }
  .hero-desc { max-width: 100%; }
  .empty-panel { grid-template-columns: 1fr; gap: 1.5rem; }
}

@media (max-width: 640px) {
  .main { padding: 0 1.25rem; }
  .header-inner { padding: 0 1.25rem; }
  .password-bar-inner { padding: 0.625rem 1.25rem; }
  .hero { padding: 2rem 0 1.5rem; }
  .result-item {
    grid-template-columns: 1fr;
    gap: 0.75rem;
  }
  .result-aside {
    flex-direction: row;
    align-items: center;
    flex-wrap: wrap;
  }
  .result-meta { justify-content: flex-start; }
  .result-item:hover { margin: 0 -1.25rem; padding-left: 1.25rem; padding-right: 1.25rem; }
  .filter-bar { flex-wrap: wrap; }
  .hero-heading-line { font-size: 1.75rem; }
}

@media (max-width: 400px) {
  .date-filter { flex-wrap: wrap; }
  .filter-seg { flex: 1 1 auto; }
}
</style>
