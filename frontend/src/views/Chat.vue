<template>
  <div class="chat-layout">
    <!-- Mobile backdrop -->
    <div v-if="sidebarOpen" class="sidebar-backdrop" @click="sidebarOpen = false" aria-hidden="true"></div>

    <!-- Delete confirmation dialog -->
    <dialog ref="deleteDialog" class="confirm-dialog" @close="onDialogClose">
      <div class="confirm-body">
        <p class="confirm-title">确定删除该会话？</p>
        <p class="confirm-sub">删除后无法恢复，所有聊天记录将一并清除。</p>
      </div>
      <div class="confirm-actions">
        <button @click="cancelDelete" class="btn-confirm-cancel">取消</button>
        <button @click="confirmDelete" class="btn-confirm-delete">删除</button>
      </div>
    </dialog>

    <!-- Sidebar -->
    <aside class="sidebar" :class="{ open: sidebarOpen }">
      <div class="sidebar-header">
        <div class="sidebar-header-left">
          <router-link to="/search" class="btn-icon-sm" title="搜索" aria-label="搜索">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
            </svg>
          </router-link>
          <span class="sidebar-label">对话</span>
        </div>
        <button class="btn-new-chat" @click="createSession" title="新建会话" aria-label="新建会话">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
        </button>
      </div>
      <nav class="session-list" role="listbox" aria-label="会话列表">
        <div
          v-for="s in sessions"
          :key="s.id"
          class="session-item"
          :class="{ active: currentSessionId === s.id }"
          @click="selectSession(s.id)"
          role="option"
          :aria-selected="currentSessionId === s.id"
          tabindex="0"
          @keyup.enter="selectSession(s.id)"
        >
          <span class="session-title">{{ s.title || '新对话' }}</span>
          <button
            class="session-delete"
            tabindex="-1"
            @click.stop="deleteSession(s.id)"
            :title="'删除会话'"
            :aria-label="'删除会话 ' + (s.title || '新对话')"
          >
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
      </nav>
      <!-- Sidebar footer: user card -->
      <div class="sidebar-footer">
        <router-link to="/profile" class="user-card">
          <div class="user-avatar-sm">
            <img v-if="authStore.avatarUrl" :src="authStore.avatarUrl" alt="" class="user-avatar-img" />
            <span v-else class="user-avatar-letter">{{ (authStore.nickname || authStore.user?.username || '?')[0].toUpperCase() }}</span>
          </div>
          <div class="user-card-info">
            <span class="user-card-name">{{ authStore.nickname || authStore.user?.username || '用户' }}</span>
            <span class="user-card-points">{{ authStore.points }} 积分</span>
          </div>
        </router-link>
        <router-link v-if="authStore.isAdmin" to="/admin" class="btn-icon-sidebar" title="管理后台" aria-label="管理后台">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
        </router-link>
        <button class="btn-logout-sm" @click="handleSidebarLogout" title="退出登录" aria-label="退出登录">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
        </button>
      </div>
    </aside>

    <!-- Chat main -->
    <main class="chat-main">
      <!-- Mobile sidebar toggle -->
      <header class="mobile-nav">
        <button class="btn-menu" @click="sidebarOpen = true" aria-label="打开会话列表">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>
          </svg>
        </button>
        <span class="mobile-nav-title">{{ currentSessionId ? (sessions.find(s => s.id === currentSessionId)?.title || '新对话') : '石化助手' }}</span>
        <router-link to="/search" class="btn-icon-sm" title="搜索" aria-label="搜索">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
          </svg>
        </router-link>
        <router-link to="/profile" class="btn-icon-sm avatar-sm" title="个人中心" aria-label="个人中心">
          <span class="avatar-sm-letter">{{ (authStore.nickname || authStore.user?.username || '?')[0].toUpperCase() }}</span>
        </router-link>
      </header>

      <!-- Messages -->
      <div class="messages" ref="messagesEl" role="log" aria-live="polite" aria-label="对话消息">
        <div v-if="!currentSessionId" class="empty-state">
          <div class="empty-glyph" aria-hidden="true">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
          </div>
          <p class="empty-headline">选择或新建会话开始对话</p>
        </div>

        <div v-else-if="messages.length === 0" class="dashboard">
          <!-- Greeting -->
          <div class="dash-greeting">
            <div class="dash-title-row">
              <h2 class="dash-title">{{ greeting }}，{{ authStore.user?.username || '同学' }}</h2>
              <router-link to="/points" class="points-badge">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
                <span>{{ authStore.points }}</span>
              </router-link>
            </div>
            <p class="dash-subtitle">有什么我能帮你的？试试下面的问题，或者直接输入</p>
          </div>

          <div class="dash-grid">
            <!-- Quick Questions -->
            <section class="dash-section dash-questions">
              <h3 class="dash-section-title">快捷提问</h3>
              <div class="question-grid">
                <button
                  v-for="q in quickQuestions"
                  :key="q"
                  class="question-pill"
                  @click="askQuestion(q)"
                >{{ q }}</button>
              </div>
            </section>

            <!-- Recent Notices -->
            <section class="dash-section dash-notices">
              <h3 class="dash-section-title">最近通知</h3>
              <div v-if="recentDocs.length === 0" class="dash-empty">暂无通知</div>
              <a
                v-for="doc in recentDocs.slice(0, 4)"
                :key="doc.id"
                :href="doc.url"
                target="_blank"
                class="notice-item"
              >
                <span class="notice-title">{{ doc.title }}</span>
                <span class="notice-meta">
                  <span v-if="doc.department" class="notice-dept">{{ doc.department }}</span>
                  <span v-if="doc.publish_date" class="notice-date">{{ formatDate(doc.publish_date) }}</span>
                </span>
              </a>
            </section>

            <!-- Personal Stats -->
            <section class="dash-section dash-stats">
              <h3 class="dash-section-title">个人统计</h3>
              <div class="stats-grid">
                <div class="stat-item">
                  <span class="stat-value">{{ authStore.points }}</span>
                  <span class="stat-label">积分</span>
                </div>
                <div class="stat-item">
                  <span class="stat-value">{{ sessions.length }}</span>
                  <span class="stat-label">对话</span>
                </div>
              </div>
            </section>

            <!-- Campus Activity -->
            <section class="dash-section dash-activity">
              <h3 class="dash-section-title">校园动态</h3>
              <div v-if="campusNews.length === 0" class="dash-empty">暂无动态</div>
              <a
                v-for="doc in campusNews.slice(0, 3)"
                :key="doc.id"
                :href="doc.url"
                target="_blank"
                class="activity-item"
              >
                <span class="activity-cat">{{ doc.category || '通知' }}</span>
                <span class="activity-title">{{ doc.title }}</span>
              </a>
            </section>
          </div>
        </div>

        <div
          v-for="(msg, idx) in messages"
          :key="msg.id"
          :class="['message', msg.role]"
          :style="{ '--delay': idx * 30 + 'ms' }"
        >
          <!-- Role indicator -->
          <div class="message-avatar" aria-hidden="true">
            <svg v-if="msg.role === 'user'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M20 21a8 8 0 00-16 0"/>
            </svg>
            <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
            </svg>
          </div>

          <div class="message-body">
            <div class="message-bubble">
              <p class="message-text" v-html="renderContent(msg)"></p>
            </div>
            <SourceList v-if="msg.role === 'assistant' && msg.sources && msg.sources.length > 0" :sources="msg.sources" :fallback="msg.fallback" class="message-sources" />
            <div v-if="msg.role === 'assistant' && msg.timing" class="timing-summary">
              <span class="timing-item">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
                检索 {{ msg.timing.retrieval }}s
              </span>
              <span class="timing-sep">·</span>
              <span class="timing-item">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
                生成 {{ msg.timing.generating }}s
              </span>
              <span class="timing-sep">·</span>
              <span class="timing-item total">共 {{ msg.timing.total }}s</span>
            </div>
          </div>
        </div>

        <!-- Loading / Streaming -->
        <div v-if="loading" class="message assistant" aria-busy="true">
          <div class="message-avatar" aria-hidden="true">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
            </svg>
          </div>
          <div class="message-body">
            <!-- Streaming answer preview -->
            <div v-if="streamedAnswer" class="message-bubble streaming-answer">
              <p class="message-text" v-html="renderContent({ role: 'assistant', content: streamedAnswer, sources: [] })"></p>
            </div>
            <!-- Stage progress -->
            <div v-if="streamingStages.length > 0" class="stage-list" role="status" aria-live="polite" aria-label="处理进度">
              <div v-for="(s, i) in streamingStages" :key="i" class="stage-item">
                <span class="stage-dot" :class="{ done: s.time != null }" :aria-label="s.time != null ? '已完成' : '进行中'"></span>
                <span class="stage-msg">{{ s.message }}</span>
                <span v-if="s.time != null" class="stage-time" aria-label="耗时">{{ s.time }}s</span>
              </div>
            </div>
            <!-- Skeleton when no stages yet -->
            <div v-else class="skeleton-bubble">
              <div class="skel skel-1"></div>
              <div class="skel skel-2"></div>
              <div class="skel skel-3"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- Input -->
      <footer class="input-area">
        <div class="input-shell" :class="{ disabled: !currentSessionId || loading }">
          <textarea
            v-model="inputText"
            class="input-box"
            placeholder="输入问题，按 Enter 发送..."
            rows="1"
            :disabled="!currentSessionId || loading"
            @keydown.enter.exact.prevent="sendMessage"
            @input="autoResize"
            aria-label="输入消息"
          ></textarea>
          <button
            class="btn-send"
            @click="sendMessage"
            :disabled="!inputText.trim() || loading || !currentSessionId"
            aria-label="发送消息"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
            </svg>
          </button>
        </div>
      </footer>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import SourceList from '../components/chat/SourceList.vue'
import { useToast } from '../composables/toast'
import { useAuthStore } from '../stores/auth'

const toast = useToast()
const authStore = useAuthStore()
const router = useRouter()

const recentDocs = ref([])
const campusNews = ref([])

const quickQuestions = [
  '食堂营业时间',
  '奖学金申请流程',
  '考试安排',
  '图书馆开放时间',
  '校园卡充值',
  '宿舍管理规定',
]

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 6) return '夜深了'
  if (h < 12) return '上午好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
})

function formatDate(dateStr) {
  if (!dateStr) return ''
  try {
    const d = new Date(dateStr)
    return `${d.getMonth() + 1}月${d.getDate()}日`
  } catch {
    return dateStr
  }
}

function askQuestion(q) {
  inputText.value = q
  sendMessage()
}

async function loadDashboard() {
  try {
    const { data } = await api.get('/search/recent')
    const docs = data.docs || data.documents || []
    recentDocs.value = docs
    // 校园动态 = all recent docs (filter for activity-like categories if available)
    campusNews.value = docs.filter(d =>
      d.category && ['校园活动', '学术活动', '工作动态', '通知公告'].includes(d.category)
    )
    if (campusNews.value.length === 0) campusNews.value = docs.slice(0, 3)
  } catch (e) {
    console.warn('Failed to load dashboard data', e)
  }
}

const sessions = ref([])
const currentSessionId = ref(null)
const messages = ref([])
const inputText = ref('')
const loading = ref(false)
const messagesEl = ref(null)
const sidebarOpen = ref(false)
const deleteDialog = ref(null)
const pendingDeleteId = ref(null)
const streamingStages = ref([]) // 当前正在显示的阶段列表 [{stage, message, time}]
const streamedAnswer = ref('') // 流式中已经接收到的回答片段

onMounted(() => { loadSessions(); loadDashboard() })

async function loadSessions() {
  const { data } = await api.get('/chat/sessions')
  sessions.value = data.sessions
  // 首次进入时自动创建新会话，展示仪表盘
  if (!currentSessionId.value) {
    await createSession()
  }
}

async function createSession() {
  const { data } = await api.post('/chat/sessions', { title: '新对话' })
  sessions.value.unshift(data)
  selectSession(data.id)
}

async function selectSession(id) {
  currentSessionId.value = id
  const { data } = await api.get(`/chat/sessions/${id}/messages`)
  messages.value = data.messages.map(m => {
    let parsed = m.sources
    if (typeof parsed === 'string') {
      try { parsed = JSON.parse(parsed || '{}') } catch { parsed = {} }
    }
    if (Array.isArray(parsed)) {
      return { ...m, sources: parsed, fallback: null }
    }
    return {
      ...m,
      sources: parsed.sources || parsed || [],
      fallback: parsed.fallback || null,
    }
  })
  scrollBottom()
}

async function deleteSession(id) {
  pendingDeleteId.value = id
  deleteDialog.value?.showModal()
}

function cancelDelete() {
  pendingDeleteId.value = null
  deleteDialog.value?.close()
}

function onDialogClose() {
  pendingDeleteId.value = null
}

async function confirmDelete() {
  const id = pendingDeleteId.value
  if (!id) return
  deleteDialog.value?.close()
  pendingDeleteId.value = null
  try {
    await api.delete(`/chat/sessions/${id}`)
    sessions.value = sessions.value.filter(s => s.id !== id)
    if (currentSessionId.value === id) {
      currentSessionId.value = sessions.value[0]?.id || null
      messages.value = []
    }
  } catch (e) {
    toast.error('删除会话失败')
  }
}

async function sendMessage() {
  const content = inputText.value.trim()
  if (!content || loading.value || !currentSessionId.value) return

  inputText.value = ''
  loading.value = true
  streamingStages.value = []
  streamedAnswer.value = ''

  const tempId = crypto.randomUUID()
  messages.value.push({ id: tempId, role: 'user', content, sources: [], fallback: null, _failed: false })
  scrollBottom()

  // 用于收集最终数据
  let finalAnswer = ''
  let finalSources = []
  let finalFallback = null
  let finalTiming = null
  let msgId = null

  try {
    const response = await fetch(`/api/chat/sessions/${currentSessionId.value}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
      credentials: 'include',
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() // 保留不完整的行

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const data = JSON.parse(line.slice(6))

        if (data.type === 'stage') {
          // 新的阶段开始，没有耗时
          const existing = streamingStages.value.findIndex(s => s.stage === data.stage)
          if (existing >= 0) {
            streamingStages.value.splice(existing)
          }
          streamingStages.value.push({ stage: data.stage, message: data.message, time: null })
          scrollBottom()
        } else if (data.type === 'keywords') {
          // 关键词提取完成
          const s = streamingStages.value.find(s => s.stage === 'keywords')
          if (s) s.time = data.time
          else streamingStages.value.push({ stage: 'keywords', message: `关键词: ${data.keywords.join('、')}`, time: data.time })
          scrollBottom()
        } else if (data.type === 'retrieval') {
          // 检索完成
          const s = streamingStages.value.find(s => s.stage === 'retrieval')
          if (s) s.time = data.time
          else streamingStages.value.push({ stage: 'retrieval', message: `检索到 ${data.count} 条文档`, time: data.time })
          scrollBottom()
        } else if (data.type === 'answer') {
          // 最终回答（可能是部分）
          finalAnswer = data.content
          finalSources = data.sources || []
          finalFallback = data.fallback || null
          finalTiming = data.timing
          streamedAnswer.value = data.content
          scrollBottom()
        } else if (data.type === 'done') {
          msgId = data.id
        }
      }
    }

    // 移除临时用户消息
    const idx = messages.value.findIndex(m => m.id === tempId)
    if (idx !== -1) {
      messages.value.splice(idx, 1)
    }

    // 添加最终助手消息
    if (finalAnswer) {
      messages.value.push({
        id: msgId || crypto.randomUUID(),
        role: 'assistant',
        content: finalAnswer,
        sources: finalSources,
        fallback: finalFallback,
        timing: finalTiming,
      })
    }

    const s = sessions.value.find(s => s.id === currentSessionId.value)
    if (s && !s.title) s.title = content.slice(0, 30)

  } catch (e) {
    const idx = messages.value.findIndex(m => m.id === tempId)
    if (idx !== -1) messages.value[idx] = { ...messages.value[idx], _failed: true }
    console.error(e)
    toast.error('发送失败，请检查网络后重试')
  } finally {
    loading.value = false
    streamingStages.value = []
    streamedAnswer.value = ''
    scrollBottom()
  }
}

function scrollBottom() {
  nextTick(() => {
    if (messagesEl.value) {
      messagesEl.value.scrollTop = messagesEl.value.scrollHeight
    }
  })
}

function autoResize(e) {
  e.target.style.height = 'auto'
  e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px'
}

async function handleSidebarLogout() {
  await authStore.logout()
  router.push('/login')
}

function renderContent(msg) {
  if (msg.role !== 'assistant' || !msg.sources || msg.sources.length === 0) {
    const div = document.createElement('div')
    div.textContent = msg.content
    return div.innerHTML
  }
  const div = document.createElement('div')
  div.textContent = msg.content
  let html = div.innerHTML
  html = html.replace(/\[(\d+)\]/g, (match, num) => {
    const idx = parseInt(num)
    const source = msg.sources.find(s => s.index === idx)
    if (source && source.url) {
      return `<a href="${source.url}" target="_blank" rel="noopener" class="cite-link">${match}</a>`
    }
    return match
  })
  return html
}
</script>

<style scoped>
/* ═══════════════════════════════════════
   CHAT — Precision Instrument Redesign
   ═══════════════════════════════════════ */

/* ── Layout ── */
.chat-layout {
  display: flex;
  height: 100dvh;
  background: var(--color-bg);
}

/* ── Sidebar ── */
.sidebar {
  width: 200px;
  flex-shrink: 0;
  border-right: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  background: var(--color-surface);
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-3);
  height: 52px;
  border-bottom: 1px solid var(--color-border);
  flex-shrink: 0;
}

.sidebar-label {
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-text-faint);
}

.btn-new-chat {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 6px;
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border);
  color: var(--color-text-muted);
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast), border-color var(--transition-fast);
  flex-shrink: 0;
}
.btn-new-chat:hover {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: white;
}

.sidebar-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.btn-icon-sm {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 6px;
  color: var(--color-text-muted);
  text-decoration: none;
  transition: color var(--transition-fast), background var(--transition-fast);
}
.btn-icon-sm:hover {
  color: var(--color-primary);
  background: var(--color-surface-hover);
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-2);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.session-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 7px;
  cursor: pointer;
  transition: background var(--transition-fast);
  position: relative;
}
.session-item:hover { background: var(--color-surface-hover); }
.session-item.active { background: var(--color-primary-muted); }

.session-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.8125rem;
  color: var(--color-text-muted);
  line-height: 1.3;
}
.session-item.active .session-title {
  color: var(--color-primary-text);
  font-weight: 600;
}

.session-delete {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 4px;
  background: transparent;
  color: var(--color-text-faint);
  border: none;
  cursor: pointer;
  opacity: 0;
  transition: opacity var(--transition-fast), background var(--transition-fast), color var(--transition-fast);
  flex-shrink: 0;
  padding: 0;
}
.session-item:hover .session-delete { opacity: 1; }
.session-delete:hover {
  background: var(--color-danger-bg);
  color: var(--color-error);
}

/* ── Sidebar footer ── */
.sidebar-footer {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-top: 1px solid var(--color-border);
  background: var(--color-surface);
}

.user-card {
  flex: 1;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 6px 8px;
  border-radius: var(--radius-md);
  text-decoration: none;
  transition: background var(--transition-fast);
  min-width: 0;
}
.user-card:hover {
  background: var(--color-surface-hover);
}

.user-avatar-sm {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  overflow: hidden;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-primary-muted);
}

.user-avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.user-avatar-letter {
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--color-primary);
}

.user-card-info {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.user-card-name {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-card-points {
  font-size: 0.6875rem;
  color: var(--color-text-faint);
}

.btn-logout-sm {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: var(--color-text-faint);
  cursor: pointer;
  flex-shrink: 0;
  transition: color var(--transition-fast), background var(--transition-fast);
}
.btn-logout-sm:hover {
  color: var(--color-error);
  background: var(--color-danger-bg);
}

.btn-icon-sidebar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 6px;
  color: var(--color-text-faint);
  text-decoration: none;
  flex-shrink: 0;
  transition: color var(--transition-fast), background var(--transition-fast);
}
.btn-icon-sidebar:hover {
  color: var(--color-primary);
  background: var(--color-surface-hover);
}

.avatar-sm {
  position: relative;
}
.avatar-sm-letter {
  font-size: 0.625rem;
  font-weight: 700;
  color: var(--color-primary);
}

/* ── Main ── */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--color-bg);
}

/* ── Mobile nav ── */
.mobile-nav {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: 0 var(--space-4);
  height: 52px;
  border-bottom: 1px solid var(--color-border);
  flex-shrink: 0;
  background: var(--color-bg);
}
.btn-menu {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 7px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  color: var(--color-text-muted);
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast);
}
.btn-menu:hover { background: var(--color-surface-hover); color: var(--color-text); }
.mobile-nav-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── Messages ── */
.messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-6) var(--space-8);
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

.message {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  max-width: 72%;
  animation: msg-enter 280ms cubic-bezier(0.16, 1, 0.3, 1) both;
  animation-delay: var(--delay, 0ms);
}
.message.user { align-self: flex-end; flex-direction: row-reverse; }
.message.assistant { align-self: flex-start; }

.message-avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 2px;
}
.message.user .message-avatar {
  background: var(--color-primary);
  color: white;
}
.message.assistant .message-avatar {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  color: var(--color-primary);
}

.message-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.message-bubble {
  padding: 10px 14px;
  border-radius: 12px;
  line-height: 1.65;
  font-size: 0.9375rem;
  max-width: 100%;
}
.message.user .message-bubble {
  background: var(--color-primary);
  color: #fff;
  border-bottom-right-radius: 3px;
}
.message.assistant .message-bubble {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  color: var(--color-text);
  border-bottom-left-radius: 3px;
}

.message-text {
  white-space: pre-wrap;
  word-break: break-word;
}

.cite-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 0.6875rem;
  font-weight: 600;
  min-width: 18px;
  height: 18px;
  padding: 0 3px;
  border-radius: 3px;
  background: var(--color-primary-muted);
  color: var(--color-primary);
  text-decoration: none;
  vertical-align: super;
  line-height: 1;
  transition: background var(--transition-fast);
}
.cite-link:hover {
  background: var(--color-primary);
  color: white;
}

.message-sources { margin-top: 4px; }

/* ── Timing summary ── */
.timing-summary {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 0.6875rem;
  color: var(--color-text-faint);
  margin-top: 4px;
  padding: 0 2px;
}
.timing-item {
  display: inline-flex;
  align-items: center;
  gap: 3px;
}
.timing-item svg {
  opacity: 0.6;
}
.timing-item.total {
  font-weight: 600;
  color: var(--color-text-muted);
}
.timing-sep {
  opacity: 0.4;
}

/* ── Geometric skeleton ── */
.skeleton-bubble {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 180px;
}
.skel {
  border-radius: 4px;
  background: var(--color-border);
  animation: skel-pulse 1.6s cubic-bezier(0.4, 0, 0.6, 1) infinite alternate;
}
.skel-1 { height: 10px; width: 90%; }
.skel-2 { height: 10px; width: 65%; }
.skel-3 { height: 10px; width: 45%; }
@keyframes skel-pulse {
  0%   { background: var(--color-border); }
  100% { background: var(--color-surface-hover); }
}

/* ── Streaming answer preview ── */
.streaming-answer {
  background: var(--color-surface) !important;
  border: 1px solid var(--color-border) !important;
  opacity: 0.85;
}
.streaming-answer .message-text {
  color: var(--color-text-secondary);
}

/* ── Stage progress list ── */
.stage-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 4px 0;
  min-width: 200px;
}
.stage-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.8125rem;
  color: var(--color-text-muted);
}
.stage-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--color-border);
  flex-shrink: 0;
  transition: background 200ms;
  display: flex;
  align-items: center;
  justify-content: center;
}
.stage-dot::after {
  content: '';
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--color-text-faint);
  transition: all 200ms;
}
.stage-dot.done {
  background: var(--color-primary-muted);
}
.stage-dot.done::after {
  background: var(--color-primary);
  width: 6px;
  height: 6px;
}
.stage-msg {
  flex: 1;
}
.stage-time {
  font-variant-numeric: tabular-nums;
  color: var(--color-primary);
  font-size: 0.75rem;
  font-weight: 600;
}

/* ── Empty state (no session selected) ── */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  text-align: center;
  padding: var(--space-8);
  animation: fadeIn 250ms ease;
}
.empty-glyph {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  color: var(--color-text-faint);
  margin-bottom: var(--space-4);
}
.empty-headline {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--color-text-secondary);
  margin-bottom: 4px;
}
.empty-sub {
  font-size: 0.8125rem;
  color: var(--color-text-faint);
}

/* ── Dashboard ── */
.dashboard {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
  padding: var(--space-8) var(--space-8);
  max-width: 760px;
  width: 100%;
  margin: 0 auto;
  animation: fadeIn 300ms ease;
}

.dash-greeting {
  padding-bottom: var(--space-4);
}

.dash-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--color-text);
  margin: 0;
  line-height: 1.3;
}

.dash-title-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: 4px;
}

.points-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  border-radius: 20px;
  background: var(--color-primary-muted);
  color: var(--color-primary);
  font-size: 0.8125rem;
  font-weight: 600;
  text-decoration: none;
  flex-shrink: 0;
  transition: background var(--transition-fast);
}
.points-badge:hover {
  background: var(--color-primary);
  color: white;
}

.dash-subtitle {
  font-size: 0.875rem;
  color: var(--color-text-muted);
  margin: 0;
}

.dash-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
}

.dash-section {
  border-radius: var(--radius-xl);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.dash-section-title {
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-text-faint);
  margin: 0;
}

/* Quick questions */
.question-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}

.question-pill {
  font-family: var(--font-sans);
  font-size: 0.8125rem;
  text-align: left;
  padding: 8px 10px;
  border-radius: var(--radius-md);
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: border-color var(--transition-fast), color var(--transition-fast), background var(--transition-fast);
  line-height: 1.3;
}
.question-pill:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
  background: var(--color-primary-muted);
}

/* Recent notices */
.notice-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 6px 0;
  text-decoration: none;
  border-bottom: 1px solid var(--color-border);
}
.notice-item:last-child { border-bottom: none; }

.notice-title {
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--color-text);
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.notice-item:hover .notice-title {
  color: var(--color-primary);
}

.notice-meta {
  display: flex;
  gap: 8px;
  font-size: 0.6875rem;
  color: var(--color-text-faint);
}

.notice-dept {
  color: var(--color-primary);
  opacity: 0.7;
}

/* Stats */
.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: var(--color-bg);
}

.stat-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--color-primary);
  font-variant-numeric: tabular-nums;
  line-height: 1;
}

.stat-label {
  font-size: 0.6875rem;
  color: var(--color-text-faint);
}

/* Campus activity */
.activity-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 0;
  text-decoration: none;
}
.activity-item:hover .activity-title {
  color: var(--color-primary);
}

.activity-cat {
  font-size: 0.625rem;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 3px;
  background: var(--color-primary-muted);
  color: var(--color-primary-text);
  white-space: nowrap;
  flex-shrink: 0;
}

.activity-title {
  font-size: 0.8125rem;
  color: var(--color-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: color var(--transition-fast);
}

.dash-empty {
  font-size: 0.8125rem;
  color: var(--color-text-faint);
  padding: var(--space-2) 0;
}

/* ── Dashboard Responsive ── */
@media (max-width: 640px) {
  .dashboard {
    padding: var(--space-4);
  }
  .dash-grid {
    grid-template-columns: 1fr;
  }
  .dash-title {
    font-size: 1.25rem;
  }
}

/* ── Input ── */
.input-area {
  padding: var(--space-3) var(--space-8) var(--space-4);
  background: var(--color-bg);
  flex-shrink: 0;
}

.input-shell {
  display: flex;
  align-items: flex-end;
  gap: var(--space-2);
  background: var(--color-surface);
  border: 1.5px solid var(--color-border);
  border-radius: 10px;
  padding: 5px 5px 5px 14px;
  transition: border-color 160ms ease, box-shadow 160ms ease;
}
.input-shell:focus-within {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-muted);
}
.input-shell.disabled {
  opacity: 0.5;
  pointer-events: none;
}

.input-box {
  flex: 1;
  padding: 0.45rem 0;
  border: none;
  background: transparent;
  font-family: var(--font-sans);
  font-size: 0.9375rem;
  line-height: 1.5;
  color: var(--color-text);
  resize: none;
  max-height: 120px;
  overflow-y: auto;
  outline: none;
}
.input-box::placeholder { color: var(--color-text-faint); }

.btn-send {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  flex-shrink: 0;
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: 7px;
  cursor: pointer;
  transition: background var(--transition-fast), transform 80ms;
}
.btn-send:hover:not(:disabled) { background: var(--color-primary-hover); }
.btn-send:active:not(:disabled) { transform: scale(0.92); }
.btn-send:disabled {
  background: var(--color-border);
  cursor: not-allowed;
}

/* ── Dialog ── */
.confirm-dialog {
  border: none;
  border-radius: 14px;
  padding: var(--space-6);
  max-width: 340px;
  width: calc(100vw - 48px);
  box-shadow: var(--shadow-lg);
  color: var(--color-text);
  background: var(--color-surface-raised);
}
.confirm-dialog::backdrop {
  background: rgba(0, 0, 0, 0.45);
  backdrop-filter: blur(2px);
}
.confirm-body { margin-bottom: var(--space-5); }
.confirm-title {
  font-size: 0.9375rem;
  font-weight: 700;
  color: var(--color-text);
  margin-bottom: var(--space-2);
}
.confirm-sub {
  font-size: 0.875rem;
  color: var(--color-text-muted);
  line-height: 1.55;
}
.confirm-actions {
  display: flex;
  gap: var(--space-2);
  justify-content: flex-end;
}
.btn-confirm-cancel {
  padding: 0.45rem 0.875rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  font-size: 0.8125rem;
  font-weight: 500;
  background: var(--color-bg);
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: background var(--transition-fast);
}
.btn-confirm-cancel:hover { background: var(--color-surface); }
.btn-confirm-delete {
  padding: 0.45rem 0.875rem;
  border: none;
  border-radius: var(--radius);
  font-size: 0.8125rem;
  font-weight: 600;
  background: var(--color-error);
  color: white;
  cursor: pointer;
  transition: background var(--transition-fast);
}
.btn-confirm-delete:hover { background: var(--color-error-hover); }

/* ── Animations ── */
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

@keyframes msg-enter {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* ── Responsive ── */
@media (max-width: 640px) {
  .sidebar {
    position: fixed;
    top: 0;
    left: 0;
    height: 100dvh;
    width: 200px;
    z-index: 50;
    transform: translateX(-100%);
    transition: transform var(--transition);
  }
  .sidebar.open { transform: translateX(0); }
  .sidebar-backdrop {
    display: block;
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.45);
    z-index: 49;
  }
  .message { max-width: 88%; }
  .messages { padding: var(--space-4) var(--space-4); gap: var(--space-5); }
  .input-area { padding: var(--space-3) var(--space-4) var(--space-3); }
}

@media (min-width: 641px) {
  .mobile-nav { display: none; }
  .sidebar-backdrop { display: none !important; }
}
</style>
