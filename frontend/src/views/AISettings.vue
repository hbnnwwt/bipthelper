<template>
  <div class="admin">
    <header class="header">
      <div class="header-inner">
        <h1 class="logo">AI 智能分类设置</h1>
        <router-link to="/" class="back-link">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="m15 18-6-6 6-6"/>
          </svg>
          返回搜索
        </router-link>
      </div>
    </header>

    <div class="page-body">
      <nav class="tabs" role="tablist">
        <button v-for="t in tabs" :key="t.key" role="tab" :aria-selected="tab === t.key"
          :class="{ active: tab === t.key }" @click="tab = t.key">{{ t.label }}</button>
      </nav>

      <!-- Providers Tab -->
      <section v-if="tab === 'providers'" class="tab-content">
        <div class="section-toolbar">
          <h2 class="section-title">AI Provider 配置</h2>
          <button @click="showProviderForm = !showProviderForm" class="btn-primary btn-sm">
            {{ showProviderForm ? '取消' : '添加 Provider' }}
          </button>
        </div>

        <div v-if="showProviderForm" class="card form-card">
          <h3 class="card-title">{{ editingProvider ? '编辑' : '添加' }} Provider</h3>
          <div class="form-grid">
            <div class="field">
              <label>Provider 类型</label>
              <select v-model="providerForm.id" :disabled="!!editingProvider" @change="loadProviderTemplate" class="input">
                <option value="">选择类型...</option>
                <option v-for="p in providerTemplates" :key="p.id" :value="p.id">{{ p.name }}</option>
              </select>
            </div>
            <div v-if="providerForm.id === 'custom'" class="field">
              <label>自定义 ID</label>
              <input v-model="providerForm.custom_id" type="text" placeholder="如 my-provider" class="input" />
            </div>
          </div>
          <div class="form-grid">
            <div class="field">
              <label>显示名称</label>
              <input v-model="providerForm.name" type="text" placeholder="如 我的模型" class="input" />
            </div>
            <div class="field">
              <label>API Base URL</label>
              <input v-model="providerForm.base_url" type="text" placeholder="https://api.example.com/v1" class="input" />
            </div>
          </div>
          <div class="form-grid">
            <div class="field">
              <label>默认模型</label>
              <input v-model="providerForm.default_model" type="text" placeholder="如 Qwen/Qwen3-8B" class="input" />
            </div>
            <div class="field">
              <label>API 格式</label>
              <select v-model="providerForm.api_format" class="input">
                <option value="openai">OpenAI 兼容格式</option>
                <option value="anthropic">Anthropic 格式</option>
              </select>
            </div>
          </div>
          <div class="field">
            <label>API Key</label>
            <input v-model="providerForm.api_key" type="password" placeholder="留空则保留已有" class="input input-full" />
          </div>
          <label class="checkbox-label">
            <input type="checkbox" v-model="providerForm.is_default" />
            <span>设为默认 Provider</span>
          </label>
          <div class="form-actions">
            <button @click="saveProvider" class="btn-primary">{{ editingProvider ? '保存修改' : '添加' }}</button>
            <button v-if="editingProvider" @click="cancelEditProvider" class="btn-outline btn-sm">取消编辑</button>
          </div>
        </div>

        <div class="card">
          <table class="data-table">
            <thead>
              <tr>
                <th scope="col">名称</th>
                <th scope="col">API格式</th>
                <th scope="col">默认模型</th>
                <th scope="col">Key状态</th>
                <th scope="col">默认</th>
                <th scope="col">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="p in providers" :key="p.id">
                <td class="cell-name">{{ p.name }}</td>
                <td><span class="badge badge-muted">{{ p.api_format }}</span></td>
                <td class="cell-mono">{{ p.default_model || '—' }}</td>
                <td>
                  <span class="badge" :class="p.has_api_key ? 'badge-success' : 'badge-warning'">
                    {{ p.has_api_key ? '已配置' : '未配置' }}
                  </span>
                </td>
                <td>{{ p.is_default ? '★' : '' }}</td>
                <td class="cell-actions">
                  <button @click="editProvider(p)" class="btn-ghost-xs">编辑</button>
                  <button @click="testProvider(p.id)" class="btn-ghost-xs" :disabled="!p.has_api_key">测试</button>
                  <button @click="deleteProvider(p.id)" class="btn-ghost-xs btn-text-danger">删除</button>
                </td>
              </tr>
            </tbody>
          </table>

          <div v-if="testResult" class="test-result" :class="testResult.ok ? 'result-ok' : 'result-error'">
            <strong>测试结果：</strong>{{ testResult.msg }}
          </div>
        </div>
      </section>

      <!-- Embedding Tab -->
      <section v-if="tab === 'embedding'" class="tab-content">
        <h2 class="section-title" style="margin-bottom:1rem">Embedding 向量配置</h2>
        <div class="card form-card">
          <div class="form-grid">
            <div class="field">
              <label>API Base URL</label>
              <input v-model="embeddingForm.base_url" type="text" placeholder="https://api.siliconflow.cn/v1" class="input input-full" />
            </div>
            <div class="field">
              <label>模型</label>
              <input v-model="embeddingForm.model" type="text" placeholder="BAAI/bge-m3" class="input" />
            </div>
          </div>
          <div class="field">
            <label>API Key</label>
            <input v-model="embeddingForm.api_key" type="password" placeholder="留空则保留已有" class="input input-full" />
          </div>
          <div class="form-actions">
            <button @click="saveEmbedding" class="btn-primary">保存配置</button>
            <button @click="testEmbedding" :disabled="embeddingTesting" class="btn-outline">
              <span v-if="embeddingTesting" class="spinner-sm"></span>
              {{ embeddingTesting ? '测试中...' : '测试连接' }}
            </button>
          </div>
          <div v-if="embeddingTestResult" class="test-result" :class="embeddingTestResult.ok ? 'result-ok' : 'result-error'" style="margin-top:1rem">
            <strong>测试结果：</strong>{{ embeddingTestResult.msg }}
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'
import { useToast } from '../composables/toast'

const { success, error } = useToast()

const tab = ref('providers')
const tabs = [
  { key: 'providers', label: 'Provider 配置' },
  { key: 'embedding', label: 'Embedding 配置' },
]

const providers = ref([])
const showProviderForm = ref(false)
const editingProvider = ref(null)
const testResult = ref(null)

const embeddingForm = ref({ api_key: '', base_url: '', model: 'BAAI/bge-m3' })
const embeddingTesting = ref(false)
const embeddingTestResult = ref(null)

const providerForm = ref({
  id: '', custom_id: '', name: '', base_url: '',
  default_model: '', api_format: 'openai', api_key: '', is_default: false,
})

const providerTemplates = [
  { id: 'openai', name: 'OpenAI', baseUrl: 'https://api.openai.com/v1', defaultModel: 'gpt-4o', apiFormat: 'openai' },
  { id: 'siliconflow', name: '硅基流动', baseUrl: 'https://api.siliconflow.cn/v1', defaultModel: 'Qwen/Qwen3-8B', apiFormat: 'openai' },
  { id: 'anthropic', name: 'Anthropic Claude', baseUrl: 'https://api.anthropic.com/v1', defaultModel: 'claude-sonnet-4-20250514', apiFormat: 'anthropic' },
  { id: 'minimax', name: 'MiniMax', baseUrl: 'https://api.minimaxi.com/anthropic', defaultModel: 'MiniMax-M2.7', apiFormat: 'anthropic' },
  { id: 'modelscope', name: 'ModelScope', baseUrl: 'https://api-inference.modelscope.cn/v1', defaultModel: 'qwen3.5-397b', apiFormat: 'openai' },
  { id: 'openrouter', name: 'OpenRouter', baseUrl: 'https://openrouter.ai/api/v1', defaultModel: 'inclusionai/ling-2.6-flash:free', apiFormat: 'openai' },
  { id: 'custom', name: '自定义', baseUrl: '', defaultModel: '', apiFormat: 'openai' },
]

onMounted(() => { loadProviders(); loadEmbeddingConfig() })

async function loadProviders() {
  try { const { data } = await api.get('/admin/ai/providers'); providers.value = data.providers }
  catch (e) { error('加载Provider列表失败') }
}

async function loadEmbeddingConfig() {
  try {
    const { data } = await api.get('/admin/ai/embedding-config')
    embeddingForm.value = { api_key: '', base_url: data.base_url || '', model: data.model || 'BAAI/bge-m3' }
  } catch (e) { error('加载 Embedding 配置失败') }
}

async function saveEmbedding() {
  try {
    await api.put('/admin/ai/embedding-config', null, { params: {
      api_key: embeddingForm.value.api_key || undefined,
      base_url: embeddingForm.value.base_url || '',
      model: embeddingForm.value.model || 'BAAI/bge-m3',
    }})
    embeddingForm.value.api_key = ''
    success('Embedding 配置已保存')
  } catch (e) { error(e.response?.data?.detail || '保存失败') }
}

async function testEmbedding() {
  embeddingTesting.value = true
  embeddingTestResult.value = null
  try {
    // 先保存
    await api.put('/admin/ai/embedding-config', null, { params: {
      api_key: embeddingForm.value.api_key || undefined,
      base_url: embeddingForm.value.base_url || '',
      model: embeddingForm.value.model || 'BAAI/bge-m3',
    }})
    const { data } = await api.post('/admin/ai/embedding-test')
    embeddingTestResult.value = { ok: data.success, msg: data.message }
  } catch (e) { embeddingTestResult.value = { ok: false, msg: e.response?.data?.detail || e.message } }
  finally { embeddingTesting.value = false }
}

function loadProviderTemplate() {
  const tpl = providerTemplates.find(p => p.id === providerForm.value.id)
  if (tpl && !editingProvider.value) {
    if (tpl.id === 'custom') {
      providerForm.value.name = ''; providerForm.value.base_url = ''
      providerForm.value.default_model = ''; providerForm.value.api_format = 'openai'
      providerForm.value.custom_id = ''
    } else {
      providerForm.value.name = tpl.name; providerForm.value.base_url = tpl.baseUrl
      providerForm.value.default_model = tpl.defaultModel; providerForm.value.api_format = tpl.apiFormat
    }
  }
}

async function saveProvider() {
  if (!providerForm.value.id || !providerForm.value.name) return
  if (providerForm.value.id === 'custom' && !providerForm.value.custom_id) { error('请输入自定义 Provider ID'); return }
  const actualId = providerForm.value.id === 'custom' ? providerForm.value.custom_id : providerForm.value.id
  try {
    await api.post('/admin/ai/providers', null, { params: {
      id: actualId, name: providerForm.value.name, api_key: providerForm.value.api_key,
      base_url: providerForm.value.base_url, default_model: providerForm.value.default_model,
      api_format: providerForm.value.api_format, is_default: providerForm.value.is_default,
    }})
    providerForm.value = { id: '', custom_id: '', name: '', base_url: '', default_model: '', api_format: 'openai', api_key: '', is_default: false }
    editingProvider.value = null; showProviderForm.value = false
    await loadProviders()
    success('Provider已保存')
  } catch (e) { error(e.response?.data?.detail || '保存失败') }
}

function editProvider(p) {
  editingProvider.value = p.id
  providerForm.value = { id: p.id, custom_id: '', name: p.name, base_url: p.base_url, default_model: p.default_model, api_format: p.api_format, api_key: '', is_default: p.is_default }
  showProviderForm.value = true
}

function cancelEditProvider() {
  editingProvider.value = null
  providerForm.value = { id: '', custom_id: '', name: '', base_url: '', default_model: '', api_format: 'openai', api_key: '', is_default: false }
  showProviderForm.value = false
}

async function deleteProvider(id) {
  try {
    await api.delete(`/admin/ai/providers/${id}`)
    await loadProviders()
    success('Provider已删除')
  } catch (e) { error('删除Provider失败') }
}

async function testProvider(id) {
  testResult.value = null
  try { const { data } = await api.post(`/admin/ai/providers/${id}/test`); testResult.value = { ok: data.success, msg: data.message } }
  catch (e) { testResult.value = { ok: false, msg: e.response?.data?.detail || e.message } }
}
</script>

<style scoped>
/* ── Same base layout as Admin.vue ── */
.admin { min-height: 100dvh; background: var(--color-surface); }
.header { background: var(--color-bg); border-bottom: 1px solid var(--color-border); position: sticky; top: 0; z-index: 10; }
.header-inner { max-width: 1000px; margin: 0 auto; padding: 0 var(--space-4); height: 52px; display: flex; align-items: center; justify-content: space-between; }
.logo { font-size: 1rem; font-weight: 700; letter-spacing: -0.01em; }
.back-link { display: inline-flex; align-items: center; gap: 0.25rem; font-size: 0.8125rem; font-weight: 500; color: var(--color-text-muted); text-decoration: none; padding: 0.3rem 0.6rem; border-radius: var(--radius); transition: background var(--transition-fast), color var(--transition-fast); }
.back-link:hover { background: var(--color-surface); color: var(--color-text); }
.page-body { max-width: 1000px; margin: 0 auto; padding: var(--space-4); }

/* ── Tabs ── */
.tabs { display: flex; gap: 2px; margin-bottom: var(--space-4); background: var(--color-bg); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: 3px; width: fit-content; }
.tabs button { padding: 0.45rem 1rem; border: none; border-radius: var(--radius-md); font-size: 0.875rem; font-weight: 500; color: var(--color-text-muted); background: none; cursor: pointer; transition: all var(--transition-fast); white-space: nowrap; }
.tabs button:hover { color: var(--color-text); background: var(--color-surface); }
.tabs button.active { background: var(--color-primary); color: white; box-shadow: 0 1px 3px rgba(37,99,235,0.25); }

.tab-content { display: flex; flex-direction: column; gap: var(--space-4); }
.section-toolbar { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: var(--space-3); }
.section-title { font-size: 0.9375rem; font-weight: 600; letter-spacing: -0.01em; }

/* ── Card ── */
.card { background: var(--color-bg); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--space-4); }
.form-card { }
.card-title { font-size: 0.875rem; font-weight: 600; color: var(--color-text-secondary); margin-bottom: var(--space-3); }

/* ── Table ── */
.data-table { font-size: 0.875rem; }
.data-table th { text-align: left; padding: 0.625rem 0.75rem; font-size: 0.75rem; font-weight: 600; color: var(--color-text-muted); letter-spacing: 0.04em; text-transform: uppercase; border-bottom: 1px solid var(--color-border); }
.data-table td { padding: 0.75rem 0.75rem; border-bottom: 1px solid var(--color-border); vertical-align: middle; }
.data-table tr:last-child td { border-bottom: none; }
.data-table tr:hover td { background: var(--color-surface); }
.cell-name { font-weight: 500; }
.cell-muted { color: var(--color-text-muted); font-size: 0.8125rem; }
.cell-mono { font-family: var(--font-mono); font-size: 0.8125rem; color: var(--color-text-secondary); }
.cell-categories { font-size: 0.8125rem; color: var(--color-text-muted); max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cell-actions { display: flex; gap: 2px; align-items: center; }

/* ── Badges ── */
.badge { display: inline-block; padding: 0.15rem 0.5rem; border-radius: var(--radius-full); font-size: 0.75rem; font-weight: 500; }
.badge-success { background: var(--color-success-bg); color: var(--color-success-text); }
.badge-warning { background: var(--color-warning-bg); color: var(--color-warning-text); }
.badge-muted { background: var(--color-surface); color: var(--color-text-muted); border: 1px solid var(--color-border); }

/* ── Form ── */
.form-grid { display: flex; gap: var(--space-3); flex-wrap: wrap; margin-bottom: var(--space-3); }
.form-grid .field { min-width: 160px; flex: 1; }
.field { display: flex; flex-direction: column; gap: var(--space-1); }
.field label { font-size: 0.8125rem; font-weight: 500; color: var(--color-text-secondary); }
.input { padding: 0.5rem 0.75rem; border: 1px solid var(--color-border); border-radius: var(--radius); font-size: 0.875rem; color: var(--color-text); background: var(--color-bg); font-family: var(--font-sans); outline: none; transition: border-color var(--transition-fast), box-shadow var(--transition-fast); }
.input:focus { border-color: var(--color-primary); box-shadow: 0 0 0 3px rgba(37,99,235,0.10); }
.input::placeholder { color: var(--color-text-faint); }
.input-full { flex: 1; }
.textarea { resize: vertical; min-height: 100px; }
.checkbox-label { display: flex; align-items: center; gap: var(--space-2); font-size: 0.875rem; cursor: pointer; margin-bottom: var(--space-3); }
.checkbox-label input { width: 15px; height: 15px; accent-color: var(--color-primary); cursor: pointer; }
.form-actions { display: flex; gap: var(--space-2); margin-top: var(--space-3); }

/* ── Buttons ── */
.btn-primary { padding: 0.5rem 1rem; background: var(--color-primary); color: white; border: none; border-radius: var(--radius); font-size: 0.875rem; font-weight: 500; cursor: pointer; transition: background var(--transition-fast), transform var(--transition-fast), box-shadow var(--transition-fast); box-shadow: 0 1px 2px rgba(37,99,235,0.2); display: inline-flex; align-items: center; gap: var(--space-2); }
.btn-primary:hover { background: var(--color-primary-hover); box-shadow: 0 3px 6px rgba(37,99,235,0.25); }
.btn-primary:active { background: var(--color-primary-active); transform: translateY(1px); box-shadow: none; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-outline { padding: 0.5rem 1rem; background: var(--color-bg); color: var(--color-primary); border: 1px solid var(--color-border); border-radius: var(--radius); font-size: 0.875rem; font-weight: 500; cursor: pointer; transition: all var(--transition-fast); }
.btn-outline:hover { border-color: var(--color-primary); background: var(--color-primary-muted); }
.btn-sm { padding: 0.375rem 0.75rem; font-size: 0.8125rem; }
.btn-ghost-xs { font-size: 0.8125rem; font-weight: 500; color: var(--color-text-muted); background: none; border: none; cursor: pointer; padding: 0.2rem 0.4rem; border-radius: var(--radius); transition: background var(--transition-fast), color var(--transition-fast); }
.btn-ghost-xs:hover { background: var(--color-surface); color: var(--color-text); }
.btn-ghost-xs:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-text-danger { color: var(--color-error); }
.btn-text-danger:hover { background: var(--color-danger-bg); color: var(--color-error); }

/* ── Test result ── */
.test-result { margin-top: 1rem; padding: 0.75rem; border-radius: var(--radius); font-size: 0.875rem; }
.result-ok { background: var(--color-success-bg); color: var(--color-success-text); border: 1px solid rgba(22,101,52,0.15); }
.result-error { background: var(--color-danger-bg); color: var(--color-danger-text); border: 1px solid rgba(220,38,38,0.15); }

.test-output { margin-top: 1rem; }
.output-section { margin-bottom: 1rem; }
.output-label { display: block; font-size: 0.8125rem; font-weight: 600; color: var(--color-text-secondary); margin-bottom: var(--space-2); }
.output-pre { background: var(--output-bg); color: var(--output-text); padding: 0.75rem; border-radius: var(--radius); font-size: 0.75rem; max-height: 200px; overflow: auto; white-space: pre-wrap; font-family: var(--font-mono); line-height: 1.6; }
.tag-list { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.tag { display: inline-block; padding: 0.2rem 0.6rem; background: var(--color-primary-muted); color: var(--color-primary-text); border-radius: var(--radius-full); font-size: 0.8rem; font-weight: 500; }
.tag-error { background: var(--color-danger-bg); color: var(--color-danger-text); }

.spinner-sm { width: 12px; height: 12px; border: 2px solid rgba(255,255,255,0.3); border-top-color: white; border-radius: 50%; animation: spin 0.7s linear infinite; flex-shrink: 0; display: inline-block; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
