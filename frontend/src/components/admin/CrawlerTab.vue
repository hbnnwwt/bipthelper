<template>
  <div class="crawler-tab">
    <!-- ── Toolbar: status + actions ── -->
    <div class="crawler-toolbar">
      <div class="toolbar-left">
        <!-- ── Status badge ── -->
        <div class="crawl-status-badge" :class="crawlStatus.running ? 'badge-running' : 'badge-idle'">
          <span class="badge-dot"></span>
          <span class="badge-label">{{ crawlStatus.running ? '爬取中' : '空闲' }}</span>
        </div>

        <!-- ── Overall progress (only show when running) ── -->
        <div v-if="crawlStatus.running && crawlProgress.total_configs > 0" class="crawl-overall-progress">
          <span class="overall-label">
            整体进度 · {{ crawlProgress.config_index }}/{{ crawlProgress.total_configs }} 个配置
          </span>
          <span v-if="currentConfigSpeed > 0" class="speed-label">
            · {{ currentConfigSpeed }} 篇/秒
          </span>
          <div class="overall-track">
            <div class="overall-fill" :style="{ width: overallPercent + '%' }"></div>
          </div>
        </div>
      </div>
      <div class="toolbar-actions">
        <button v-if="!crawlStatus.running" @click="showTriggerModal = true" class="btn-primary btn-sm" :disabled="crawlLoading">
          手动触发爬取
        </button>
        <button v-else @click="stopCrawl" class="btn-danger btn-sm">停止爬取</button>
        <button @click="importNavigation" class="btn-outline btn-sm" :disabled="navLoading">
          {{ navLoading ? '抓取中...' : '从首页导入导航' }}
        </button>
        <button @click="toggleLogs" class="btn-outline btn-sm">
          {{ showLogs ? '隐藏日志' : '显示日志' }}
        </button>
      </div>
    </div>

    <!-- ── Trigger Crawl Modal ── -->
    <div v-if="showTriggerModal" class="modal-overlay" @click.self="showTriggerModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <span class="modal-title">选择要爬取的配置</span>
          <button class="modal-close" @click="showTriggerModal = false">×</button>
        </div>
        <div class="modal-body">
          <div class="select-all-row">
            <label class="checkbox-label">
              <input type="checkbox" v-model="selectAllConfigs" @change="toggleSelectAll" />
              <span>全选</span>
            </label>
          </div>
          <div class="config-select-list">
            <label
              v-for="c in configs"
              :key="c.id"
              class="config-select-item"
            >
              <input
                type="checkbox"
                :value="c.id"
                v-model="selectedConfigIds"
              />
              <span class="config-select-name">{{ c.name }}</span>
              <span class="config-select-parent">{{ c.parent_category || '' }}</span>
            </label>
          </div>
        </div>
        <div class="modal-footer">
          <button @click="showTriggerModal = false" class="btn-outline btn-sm">取消</button>
          <button
            @click="triggerCrawl"
            class="btn-primary btn-sm"
            :disabled="selectedConfigIds.length === 0"
          >
            爬取 {{ selectedConfigIds.length > 0 ? selectedConfigIds.length + ' 个配置' : '所选配置' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ── Add config form ── -->
    <div class="config-form">
      <div class="config-form-header">
        <span class="config-form-title">添加新配置</span>
        <button @click="showAdvanced = !showAdvanced" class="btn-ghost-xs toggle-advanced">
          {{ showAdvanced ? '收起' : '展开高级选项' }}
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" :style="{ transform: showAdvanced ? 'rotate(180deg)' : '' }">
            <path d="m6 9 6 6 6-6"/>
          </svg>
        </button>
      </div>
      <div class="config-form-grid">
        <input v-model="newConfig.name" type="text" placeholder="配置名称" class="input" />
        <input v-model="newConfig.url" type="url" placeholder="列表页URL" class="input input-full" />
        <input v-model="newConfig.category" type="text" placeholder="分类标签" class="input" />
        <input v-model="newConfig.parent_category" type="text" placeholder="大类" class="input" />
        <input v-model="newConfig.sub_category" type="text" placeholder="小类" class="input" />
      </div>
      <transition name="adv-fade">
        <div v-if="showAdvanced" class="advanced-fields">
          <div class="config-form-grid">
            <label class="checkbox-label">
              <input type="checkbox" v-model="newConfig.is_list_page" />
              <span>列表页模式</span>
            </label>
            <input v-model="newConfig.article_selector" type="text" placeholder="文章链接选择器" class="input" />
            <input v-model="newConfig.link_prefix" type="text" placeholder="链接前缀" class="input" />
            <input v-model="newConfig.pagination_selector" type="text" placeholder="分页选择器" class="input" />
            <input v-model.number="newConfig.pagination_max" type="number" placeholder="最大页数，0=不限制" class="input" style="width:140px" />
            <input v-model="newConfig.selector" type="text" placeholder="内容CSS选择器" class="input" />
          </div>
        </div>
      </transition>
      <div class="config-form-actions">
        <button @click="addConfig" class="btn-primary btn-sm">添加配置</button>
        <button @click="loadPreset" class="btn-outline btn-sm">加载BIPT预设</button>
      </div>
    </div>

    <!-- ── Config list ── -->
    <div class="config-list">
      <!-- Filter bar -->
      <div class="config-filters">
        <input v-model.lazy="filterSearch" type="search" placeholder="搜索配置名称..." class="filter-input" />
        <select v-model="filterParent" class="filter-select">
          <option value="">全部大类</option>
          <option v-for="p in parentOptions" :key="p" :value="p">{{ p }}</option>
        </select>
        <select v-model="filterSub" class="filter-select" :disabled="!filterParent">
          <option value="">全部分类</option>
          <option v-for="s in subOptions" :key="s" :value="s">{{ s }}</option>
        </select>
        <span class="filter-count">{{ filteredConfigs.length }} / {{ configs.length }}</span>
      </div>
      <div class="config-list-header">
        <span class="config-list-count">{{ filteredConfigs.length }} 个配置{{ filterSearch || filterParent || filterSub ? '（已过滤）' : '' }}</span>
      </div>
      <div class="table-wrapper">
        <table class="data-table">
          <thead>
            <tr>
              <th scope="col">名称</th>
              <th scope="col">大类</th>
              <th scope="col">小类</th>
              <th scope="col">分类</th>
              <th scope="col">模式</th>
              <th scope="col">自动间隔</th>
              <th scope="col">进度</th>
              <th scope="col">状态</th>
              <th scope="col">上次爬取</th>
              <th scope="col">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in filteredConfigs" :key="c.id">
              <td>
                <a :href="c.url" target="_blank" class="link">{{ c.name }}</a>
                <div class="cell-url">{{ c.url }}</div>
              </td>
              <td><span class="cell-tag">{{ c.parent_category || '—' }}</span></td>
              <td><span class="cell-tag">{{ c.sub_category || '—' }}</span></td>
              <td><span class="cell-tag">{{ c.category || '—' }}</span></td>
              <td>
                <span class="mode-badge" :class="c.initialized ? 'mode-incremental' : 'mode-full'">
                  {{ c.initialized ? '增量' : '全量' }}
                </span>
              </td>
              <td class="cell-interval">
                <select
                  class="interval-select"
                  :value="c.auto_interval_hours || 0"
                  @change="updateInterval(c.id, Number($event.target.value))"
                >
                  <option value="0">关闭</option>
                  <option value="4">4小时</option>
                  <option value="8">8小时</option>
                  <option value="12">12小时</option>
                  <option value="24">24小时</option>
                </select>
              </td>
              <!-- 进度列 -->
              <td class="cell-progress">
                <!-- 正在爬取此配置 -->
                <template v-if="getConfigProgressStatus(c.id) === 'running'">
                  <div class="row-progress">
                    <div class="row-progress-track">
                      <div class="row-progress-fill" :style="{ width: getRowProgress(c.id) + '%' }"></div>
                    </div>
                    <span class="row-progress-label">
                      {{ getConfigProgress(c.id).page }}/{{ getConfigProgress(c.id).total_pages || '?' }}页 ·
                      {{ getConfigProgress(c.id).articles_crawled }}{{ getConfigProgress(c.id).articles_total > 0 ? '/' + getConfigProgress(c.id).articles_total : '' }}篇
                    </span>
                  </div>
                </template>
                <!-- 已完成爬取（有 last_crawl） -->
                <template v-else-if="c.last_crawl">
                  <span class="crawled-check">✓ 已爬</span>
                </template>
                <!-- 未爬取 -->
                <template v-else>
                  <span class="not-crawled">—</span>
                </template>
              </td>
              <td>
                <span class="state-badge" :class="c.enabled ? 'state-on' : 'state-off'">
                  <span class="state-dot"></span>
                  {{ c.enabled ? '启用' : '禁用' }}
                </span>
              </td>
              <td class="cell-time">{{ c.last_crawl?.slice(0, 16) || '—' }}</td>
              <td class="cell-actions">
                <button @click="toggleConfig(c)" class="btn-ghost-xs">{{ c.enabled ? '禁用' : '启用' }}</button>
                <button v-if="c.initialized" @click="resetConfig(c)" class="btn-ghost-xs">重置</button>
                <button @click="deleteConfig(c.id)" class="btn-ghost-xs btn-text-danger">删除</button>
              </td>
            </tr>
            <tr v-if="configs.length === 0">
              <td colspan="10" class="cell-empty">暂无配置</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- ── Log panel ── -->
    <transition name="log-slide">
      <div v-if="showLogs" class="log-panel">
        <div class="log-panel-header">
          <span class="log-panel-title">爬虫日志</span>
          <div class="log-panel-actions">
            <button @click="loadLogs" class="btn-ghost-xs">刷新</button>
            <button @click="clearLogs" class="btn-ghost-xs">清空</button>
          </div>
        </div>
        <div class="log-box" ref="logBox">
          <div v-if="logs.length === 0" class="log-empty">暂无日志</div>
          <div v-for="(log, i) in logs" :key="i" class="log-line" :class="'log-' + log.level.toLowerCase()">
            <span class="log-time">{{ log.time }}</span>
            <span class="log-level">{{ log.level }}</span>
            <span class="log-msg">{{ log.message }}</span>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import api, { crawlerApi } from '../../api'
import { useToast } from '../../composables/toast'

const props = defineProps(['tab'])

const { success, error, info } = useToast()

const configs = ref([])
const showAdvanced = ref(false)
const showLogs = ref(false)
const showTriggerModal = ref(false)
const selectedConfigIds = ref([])
const logs = ref([])
const logBox = ref(null)
const crawlStatus = ref({ running: false })
const crawlProgress = ref({ phase: 'idle', configs: [], current_config: '', current_config_id: null, config_index: 0, total_configs: 0, page: 0, total_pages: 0, articles_crawled: 0, articles_total: 0 })
const crawlLoading = ref(false)
const navLoading = ref(false)
const filterSearch = ref('')
const filterParent = ref('')
const filterSub = ref('')
let logTimer = null
let statusTimer = null

// 整体进度百分比
const overallPercent = computed(() => {
  const { phase, configs } = crawlProgress.value

  if (phase !== 'running' || !configs?.length) return 0

  const doneCount = configs.filter(c => c.status === 'done' || c.status === 'stopped').length
  const runningIdx = configs.findIndex(c => c.status === 'running')
  if (runningIdx < 0) return Math.round(doneCount / configs.length * 100)

  const running = configs[runningIdx]
  const baseFrac = doneCount / configs.length
  const runningFrac = running.articles_total > 0
    ? (running.articles_crawled / running.articles_total) / configs.length
    : running.total_pages > 0
    ? (running.page / running.total_pages) / configs.length
    : 0
  return Math.round((baseFrac + runningFrac) * 100)
})

// 当前正在爬取配置的速度（篇/秒）
const currentConfigSpeed = computed(() => {
  const { phase, configs } = crawlProgress.value
  if (phase !== 'running' || !configs?.length) return 0
  const running = configs.find(c => c.status === 'running')
  if (!running) return 0
  const elapsed = running.elapsed_seconds || 0
  if (elapsed < 1) return 0
  const diff = running.articles_crawled - (running.articles_crawled_at_start || 0)
  if (diff <= 0) return 0
  return Math.round(diff / elapsed * 10) / 10
})

// 根据索引获取配置ID（1-based index）
function getConfigByIndex(index) {
  if (!index || index < 1) return null
  return configs.value[index - 1]?.id
}

// 获取某配置的当前行内进度百分比
function getRowProgress(configId) {
  const cfg = crawlProgress.value.configs?.find(c => c.id === configId)
  if (!cfg) return 0
  if (cfg.status === 'done' || cfg.status === 'stopped') return 100
  if (cfg.status === 'running') {
    if (cfg.articles_total > 0) return Math.round(cfg.articles_crawled / cfg.articles_total * 100)
    if (cfg.total_pages > 0) return Math.round(cfg.page / cfg.total_pages * 100)
    return 5
  }
  return 0
}

// 获取某配置的进度状态
function getConfigProgressStatus(configId) {
  return crawlProgress.value.configs?.find(c => c.id === configId)?.status || 'pending'
}

// 获取某配置的进度数据
function getConfigProgress(configId) {
  return crawlProgress.value.configs?.find(c => c.id === configId) || { page: 0, total_pages: 0, articles_crawled: 0, articles_total: 0 }
}

// 三级过滤
const parentOptions = computed(() => [...new Set(configs.value.map(c => c.parent_category).filter(Boolean))])
const subOptions = computed(() => {
  if (!filterParent.value) return [...new Set(configs.value.map(c => c.sub_category).filter(Boolean))]
  return [...new Set(configs.value.filter(c => c.parent_category === filterParent.value).map(c => c.sub_category).filter(Boolean))]
})
const filteredConfigs = computed(() => {
  let list = configs.value
  if (filterSearch.value) list = list.filter(c => c.name.toLowerCase().includes(filterSearch.value.toLowerCase()))
  if (filterParent.value) list = list.filter(c => c.parent_category === filterParent.value)
  if (filterSub.value) list = list.filter(c => c.sub_category === filterSub.value)
  return list
})

const newConfig = ref({
  name: '', url: '', selector: 'body', category: '',
  parent_category: '', sub_category: '',
  is_list_page: true, article_selector: 'ul.sub_list li a',
  link_prefix: '', pagination_selector: 'a[href*="index"]:has(img)', pagination_max: 0,
})

async function loadConfigs() {
  try {
    const { data } = await crawlerApi.get('/configs')
    configs.value = data.configs
  } catch (e) { error('加载爬虫配置失败') }
}

function loadPreset() {
  newConfig.value = {
    name: '通知公告', url: 'https://info.bipt.edu.cn/jgjf/bctzgg/index.htm',
    selector: 'body', category: '通知公告', parent_category: '机关教辅', sub_category: '通知公告',
    is_list_page: true,
    article_selector: 'ul.sub_list li a', link_prefix: 'https://info.bipt.edu.cn/jgjf/bctzgg/',
    pagination_selector: 'a[href*="index"]:has(img)', pagination_max: 0,
  }
}

async function importNavigation() {
  if (!confirm('将从首页抓取导航结构并批量创建配置，是否继续？')) return
  navLoading.value = true
  try {
    const { data: navData } = await crawlerApi.get('/crawl/navigation')
    const { data: batchData } = await crawlerApi.post('/crawl/configs/batch', { navigation: navData.navigation })
    await loadConfigs()
    success(`成功导入 ${batchData.count} 个配置`)
  } catch (e) {
    error('导入导航失败：' + (e.response?.data?.detail || e.message))
  } finally {
    navLoading.value = false
  }
}

function validateUrl(url) {
  try {
    const u = new URL(url)
    return u.protocol === 'http:' || u.protocol === 'https:'
  } catch { return false }
}

function validateSelector(selector) {
  if (!selector || !selector.trim()) return false
  const dangerous = ['<script', 'javascript:', 'onerror', 'onclick', 'onload']
  return !dangerous.some(d => selector.toLowerCase().includes(d))
}

async function addConfig() {
  if (!newConfig.value.name.trim()) { error('请输入配置名称'); return }
  if (!newConfig.value.url.trim()) { error('请输入列表页URL'); return }
  if (!validateUrl(newConfig.value.url)) { error('URL 格式无效，请输入以 http:// 或 https:// 开头的地址'); return }
  if (!newConfig.value.selector.trim()) { error('请输入内容CSS选择器'); return }
  if (!validateSelector(newConfig.value.selector)) { error('CSS选择器不能包含危险内容'); return }
  if (newConfig.value.is_list_page && !newConfig.value.article_selector.trim()) { error('列表页模式请输入文章链接选择器'); return }
  if (newConfig.value.article_selector && !validateSelector(newConfig.value.article_selector)) { error('文章链接选择器不能包含危险内容'); return }
  try {
    const params = { ...newConfig.value }
    await crawlerApi.post('/configs', null, { params })
    newConfig.value = { name: '', url: '', selector: 'body', category: '', parent_category: '', sub_category: '', is_list_page: true, article_selector: 'ul.sub_list li a', link_prefix: '', pagination_selector: 'a[href*="index"]:has(img)', pagination_max: 0 }
    await loadConfigs()
    success('配置已添加')
  } catch (e) { error(e.response?.data?.detail || '添加配置失败') }
}

async function toggleConfig(c) {
  try {
    await crawlerApi.put(`/configs/${c.id}`, null, { params: { enabled: !c.enabled } })
    await loadConfigs()
  } catch (e) { error('更新配置失败') }
}

async function deleteConfig(id) {
  try {
    await crawlerApi.delete(`/configs/${id}`)
    await loadConfigs()
    success('配置已删除')
  } catch (e) { error('删除配置失败') }
}

async function triggerCrawl() {
  try {
    crawlLoading.value = true
    showTriggerModal.value = false
    const configIdsParam = selectedConfigIds.value.length > 0
      ? selectedConfigIds.value.join(",")
      : null
    const params = configIdsParam ? { config_ids: configIdsParam } : {}
    await crawlerApi.post('/crawl/trigger', {}, { params })
    success('爬取已触发')
    // 立即获取进度（不等到下次轮询）
    loadCrawlStatus()
    loadCrawlProgress()
  } catch (e) { error('触发爬取失败') }
  finally { crawlLoading.value = false }
}

function toggleSelectAll() {
  if (selectAllConfigs.value) {
    selectedConfigIds.value = configs.value.map(c => c.id)
  } else {
    selectedConfigIds.value = []
  }
}

const selectAllConfigs = computed({
  get: () => configs.value.length > 0 && selectedConfigIds.value.length === configs.value.length,
  set: () => {}
})

function toggleLogs() {
  showLogs.value = !showLogs.value
  if (showLogs.value) {
    loadLogs()
    logTimer = setInterval(loadLogs, 3000)
  } else {
    clearInterval(logTimer); logTimer = null
  }
}

async function loadLogs() {
  try {
    const { data } = await api.get('/admin/logs')
    logs.value = data.logs
    await nextTick()
    if (logBox.value) logBox.value.scrollTop = logBox.value.scrollHeight
  } catch (e) { console.error('Failed to load logs:', e) }
}

async function clearLogs() {
  try {
    await api.delete('/admin/logs')
    logs.value = []
    success('日志已清空')
  } catch (e) { error('清空日志失败') }
}

async function loadCrawlStatus() {
  try {
    const { data } = await crawlerApi.get('/crawl/status')
    crawlStatus.value = data
    // 同时获取进度数据
    loadCrawlProgress()
  } catch (e) { console.error('Failed to load crawl status:', e) }
}

async function loadCrawlProgress() {
  try {
    const { data } = await crawlerApi.get('/crawl/progress')
    crawlProgress.value = data
  } catch (e) { console.error('Failed to load crawl progress:', e) }
}

async function stopCrawl() {
  try {
    await crawlerApi.post('/crawl/stop')
    info('已请求停止爬取')
    loadCrawlStatus()
  } catch (e) { error('停止爬取失败') }
}

async function resetConfig(c) {
  try {
    await crawlerApi.put(`/configs/${c.id}`, null, { params: { initialized: false, pagination_max: 0 } })
    await loadConfigs()
    success(`已重置"${c.name}"的爬取标记`)
  } catch (e) { error('重置配置失败') }
}

async function updateInterval(configId, hours) {
  try {
    await crawlerApi.put(`/configs/${configId}`, null, { params: { auto_interval_hours: hours } })
    await loadConfigs()
  } catch (e) { error('更新自动间隔失败') }
}

onMounted(() => { loadConfigs(); loadCrawlStatus() })

watch(() => props.tab, (newTab) => {
  if (newTab !== 'crawler') {
    clearInterval(logTimer); logTimer = null
    clearInterval(statusTimer); statusTimer = null
    showLogs.value = false
  } else {
    loadCrawlStatus()
    loadCrawlProgress()
    statusTimer = setInterval(() => { loadCrawlStatus(); loadCrawlProgress() }, 2000)
  }
})
</script>

<style scoped>
@import '../../assets/admin-shared.css';

.crawler-tab { --ease-out: cubic-bezier(0.16, 1, 0.3, 1); }

/* ── Crawler toolbar ── */
.crawler-toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-4);
  flex-wrap: wrap;
}
.toolbar-left {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  min-width: 0;
}
.toolbar-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
  flex-shrink: 0;
}

/* ── Status badge ── */
.crawl-status-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.35rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.8125rem;
  font-weight: 600;
  width: fit-content;
}
.badge-running {
  background: linear-gradient(135deg, #dcfce7, #bbf7d0);
  color: #15803d;
  box-shadow: 0 1px 3px rgba(22, 163, 74, 0.2);
}
.badge-idle {
  background: var(--color-surface);
  color: var(--color-text-muted);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}
.badge-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
  flex-shrink: 0;
}
.badge-running .badge-dot {
  animation: badge-pulse 1.5s ease-in-out infinite;
}
@keyframes badge-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.85); }
}

/* ── Overall progress (toolbar) ── */
.crawl-overall-progress {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  min-width: 200px;
  max-width: 300px;
}
.overall-label {
  font-size: 0.75rem;
  color: var(--color-text-muted);
  font-variant-numeric: tabular-nums;
}
.speed-label {
  font-size: 0.75rem;
  color: var(--color-text-muted);
  margin-left: 0.5rem;
}
.overall-track {
  height: 6px;
  background: var(--color-border);
  border-radius: 3px;
  overflow: hidden;
}
.overall-fill {
  height: 100%;
  background: linear-gradient(90deg, #16a34a, #22c55e);
  border-radius: 3px;
  transition: width 0.3s var(--ease-out);
}

/* ── Row progress ── */
.cell-progress {
  min-width: 140px;
  max-width: 200px;
}
.row-progress {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}
.row-progress-track {
  height: 5px;
  background: var(--color-border);
  border-radius: 3px;
  overflow: hidden;
}
.row-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #16a34a, #4ade80);
  border-radius: 3px;
  transition: width 0.3s var(--ease-out);
}
.row-progress-label {
  font-size: 0.6875rem;
  color: var(--color-text-muted);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.crawled-check {
  font-size: 0.75rem;
  color: #16a34a;
  font-weight: 600;
}
.not-crawled {
  color: var(--color-text-faint);
}

/* ── Config form ── */
.config-form {
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-3) var(--space-4);
  margin-bottom: var(--space-3);
}
.config-form-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-3);
}
.config-form-title {
  font-size: 0.875rem;
  font-weight: 700;
  color: var(--color-text);
  letter-spacing: -0.01em;
}
.toggle-advanced {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.8125rem;
}
.toggle-advanced svg {
  transition: transform 200ms var(--ease-out);
}

.config-form-grid {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
  align-items: center;
}
.config-form-grid .input {
  min-width: 130px;
  transition: border-color 200ms var(--ease-out), box-shadow 200ms var(--ease-out);
}

.advanced-fields {
  margin-top: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px solid var(--color-border);
}
.advanced-fields .config-form-grid {
  gap: var(--space-2);
}

.config-form-actions {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-3);
  align-items: center;
}

/* ── Config list ── */
.config-list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-2);
}
.config-list-count {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--color-text-muted);
  letter-spacing: 0.02em;
}

/* ── Filter bar ── */
.config-filters {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
  flex-wrap: wrap;
}
.filter-input {
  width: 160px;
}
.filter-select {
  min-width: 100px;
}
.filter-count {
  font-size: 0.75rem;
  color: var(--color-text-muted);
  white-space: nowrap;
}

/* ── Table wrapper ── */
.table-wrapper {
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

/* ── Table ── */
.data-table {
  font-size: 0.875rem;
  width: 100%;
}
.data-table th {
  text-align: left;
  padding: 0.55rem 0.875rem;
  font-size: 0.6875rem;
  font-weight: 700;
  color: var(--color-text-muted);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
}
.data-table td {
  padding: 0.65rem 0.875rem;
  border-bottom: 1px solid var(--color-border);
  vertical-align: middle;
  font-size: 0.8125rem;
}
.data-table tr:last-child td { border-bottom: none; }
.data-table tr:hover td { background: var(--color-surface); }

.cell-url {
  font-size: 0.6875rem;
  color: var(--color-text-faint);
  word-break: break-all;
  margin-top: 2px;
  max-width: 280px;
}
.cell-time {
  color: var(--color-text-muted);
  font-size: 0.8125rem;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.cell-empty {
  text-align: center;
  color: var(--color-text-faint);
  padding: var(--space-5) !important;
}
.cell-actions {
  display: flex;
  gap: 2px;
  align-items: center;
  white-space: nowrap;
}
.cell-tag {
  display: inline-block;
  font-size: 0.75rem;
  color: var(--color-text-secondary);
}

/* ── Mode / State badges ── */
.mode-badge {
  display: inline-block;
  padding: 0.125rem 0.45rem;
  border-radius: var(--radius-sm);
  font-size: 0.75rem;
  font-weight: 600;
}
.mode-incremental {
  background: var(--color-success-bg);
  color: var(--color-success-text);
}
.mode-full {
  background: var(--color-warning-bg);
  color: var(--color-warning-text);
}

.state-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.8125rem;
  font-weight: 600;
}
.state-on { color: #16a34a; }
.state-off { color: var(--color-text-muted); }
.state-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}
.state-on .state-dot { background: #22c55e; }
.state-off .state-dot { background: var(--color-border-strong); }

/* ── Interval select ── */
.cell-interval {
  min-width: 90px;
}
.interval-select {
  font-size: 0.75rem;
  padding: 0.2rem 0.4rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-bg);
  color: var(--color-text);
  cursor: pointer;
}
.interval-select:hover {
  border-color: var(--color-primary);
}

/* ── Link ── */
.link {
  color: var(--color-primary);
  font-weight: 500;
  text-decoration: none;
  font-size: 0.875rem;
}
.link:hover { text-decoration: underline; }

/* ── Log panel ── */
.log-panel {
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}
.log-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface);
}
.log-panel-title {
  font-size: 0.875rem;
  font-weight: 700;
  color: var(--color-text);
}
.log-panel-actions {
  display: flex;
  gap: 2px;
}

.log-box {
  background: var(--log-bg, #1e1e1e);
  color: var(--log-text, #d4d4d4);
  padding: var(--space-3) var(--space-4);
  max-height: 280px;
  overflow-y: auto;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  line-height: 1.7;
}
.log-empty { color: var(--log-empty, #555); text-align: center; padding: var(--space-4); }
.log-line { display: flex; gap: var(--space-2); align-items: baseline; }
.log-time { color: var(--log-time, #666); white-space: nowrap; flex-shrink: 0; font-size: 0.6875rem; }
.log-level {
  font-weight: 700;
  white-space: nowrap;
  width: 52px;
  text-align: center;
  flex-shrink: 0;
  font-size: 0.6875rem;
}
.log-info .log-level { color: var(--log-info, #4fc3f7); }
.log-warning .log-level { color: var(--log-warning, #ffb74d); }
.log-error .log-level { color: var(--log-error, #f87171); }
.log-success .log-level { color: var(--log-success, #81c784); }
.log-debug .log-level { color: var(--log-debug, #888); }
.log-msg { word-break: break-all; }

/* ── Transitions ── */
.log-slide-enter-active,
.log-slide-leave-active {
  transition: opacity 200ms var(--ease-out), transform 200ms var(--ease-out);
}
.log-slide-enter-from,
.log-slide-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

.adv-fade-enter-active,
.adv-fade-leave-active {
  transition: opacity 180ms var(--ease-out), max-height 200ms var(--ease-out);
  max-height: 200px;
  overflow: hidden;
}
.adv-fade-enter-from,
.adv-fade-leave-to {
  opacity: 0;
  max-height: 0;
}

/* ── Responsive ── */
@media (max-width: 768px) {
  .crawler-toolbar { flex-direction: column; align-items: flex-start; }
  .toolbar-actions { width: 100%; }
  .config-form-grid { flex-direction: column; }
  .config-form-grid .input { min-width: 100%; }
  .data-table { display: block; overflow-x: auto; }
  .cell-url { max-width: 180px; }
  .crawl-overall-progress { min-width: 0; width: 100%; }
  .cell-progress { min-width: 120px; }
}

/* ── Modal ── */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.modal-content {
  background: var(--color-bg);
  border-radius: var(--radius-lg);
  width: 90%;
  max-width: 480px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.2);
}
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--color-border);
}
.modal-title {
  font-size: 0.9375rem;
  font-weight: 700;
  color: var(--color-text);
}
.modal-close {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  border: none;
  background: transparent;
  color: var(--color-text-muted);
  font-size: 1.25rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.modal-close:hover {
  background: var(--color-surface);
  color: var(--color-text);
}
.modal-body {
  padding: var(--space-3) var(--space-4);
  overflow-y: auto;
  flex: 1;
}
.modal-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  border-top: 1px solid var(--color-border);
}

/* ── Config select list ── */
.select-all-row {
  margin-bottom: var(--space-2);
  padding-bottom: var(--space-2);
  border-bottom: 1px solid var(--color-border);
}
.config-select-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-height: 320px;
  overflow-y: auto;
}
.config-select-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem 0.5rem;
  border-radius: var(--radius-sm);
  cursor: pointer;
}
.config-select-item:hover {
  background: var(--color-surface);
}
.config-select-item input[type="checkbox"] {
  width: 16px;
  height: 16px;
  cursor: pointer;
}
.config-select-name {
  font-size: 0.8125rem;
  color: var(--color-text);
  flex: 1;
}
.config-select-parent {
  font-size: 0.6875rem;
  color: var(--color-text-muted);
}

/* ── Checkbox label ── */
.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  cursor: pointer;
  font-size: 0.8125rem;
}
</style>
