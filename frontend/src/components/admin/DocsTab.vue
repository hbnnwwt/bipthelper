<template>
  <div class="docs-tab">
    <!-- ── Table toolbar: count + actions + inline filter ── -->
    <div class="table-toolbar">
      <div class="toolbar-left">
        <span class="table-count">共 <strong>{{ totalDocs }}</strong> 条文档</span>
      </div>
      <div class="toolbar-right">
        <div class="inline-filter">
          <svg class="filter-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
          </svg>
          <input
            v-model="docKeyword"
            type="search"
            placeholder="搜索标题..."
            class="filter-input"
            @input="debounceLoadDocs"
          />
        </div>
        <select v-model="docFilterParentCategory" @change="docPage = 1; loadDocs()" class="filter-select">
          <option value="">全部大类</option>
          <option v-for="c in docParentCategories" :key="c" :value="c">{{ c || '(无大类)' }}</option>
        </select>
        <select v-model="docFilterCategory" @change="docPage = 1; loadDocs()" class="filter-select">
          <option value="">全部分类</option>
          <option v-for="c in docCategories" :key="c" :value="c">{{ c || '(无分类)' }}</option>
        </select>
        <select v-model="docSort" @change="docPage = 1; loadDocs()" class="filter-select">
          <option value="updated_desc">最新更新</option>
          <option value="updated_asc">最旧更新</option>
          <option value="publish_desc">最新发布</option>
          <option value="publish_asc">最旧发布</option>
        </select>
        <button @click="loadDocs" class="btn-outline btn-sm">刷新</button>
        <button @click="exportDocs" class="btn-outline btn-sm" :disabled="exportLoading">
          {{ exportLoading ? '导出中...' : '导出CSV' }}
        </button>
        <button
          v-if="selectedDocs.length > 0"
          @click="batchDeleteDocs"
          class="btn-danger btn-sm"
          :disabled="deleteLoading"
        >
          删除 ({{ selectedDocs.length }})
        </button>
      </div>
    </div>

    <!-- ── Document table ── -->
    <div class="table-wrapper">
      <table class="data-table">
        <thead>
          <tr>
            <th scope="col" style="width:2.5rem; min-width:2.5rem">
              <input type="checkbox" :checked="isAllSelected" @change="toggleSelectAllDocs" aria-label="全选" />
            </th>
            <th scope="col">标题</th>
            <th scope="col">大类</th>
            <th scope="col">小类</th>
            <th scope="col">分类</th>
            <th scope="col">发布单位</th>
            <th scope="col">发布日期</th>
            <th scope="col" style="width:5rem; min-width:5rem">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="d in docs" :key="d.id">
            <td><input type="checkbox" :value="d.id" v-model="selectedDocs" /></td>
            <td>
              <a :href="d.url" target="_blank" class="doc-link">{{ d.title }}</a>
              <div class="cell-url">{{ d.url }}</div>
            </td>
            <td><span class="cell-tag">{{ d.parent_category || '—' }}</span></td>
            <td><span class="cell-tag">{{ d.sub_category || '—' }}</span></td>
            <td><span class="cell-tag">{{ d.category || '—' }}</span></td>
            <td class="cell-dept">{{ d.department || '—' }}</td>
            <td class="cell-date">{{ d.publish_date || '—' }}</td>
            <td class="cell-actions">
              <button @click="editCategory(d)" class="btn-ghost-xs">修改</button>
              <button @click="deleteDoc(d.id)" class="btn-ghost-xs btn-text-danger">删除</button>
            </td>
          </tr>
          <tr v-if="docs.length === 0">
            <td colspan="8" class="cell-empty">暂无数据</td>
          </tr>
        </tbody>
      </table>

      <!-- Inline category editor -->
      <transition name="edit-slide">
        <div v-if="editingDocId" class="inline-editor">
          <div class="inline-editor-label">修改分类</div>
          <div class="inline-editor-body">
            <input
              v-model="editCategoryInput"
              type="text"
              class="input"
              placeholder="输入分类名称"
              @keyup.enter="confirmEditCategory"
            />
            <button @click="confirmEditCategory" class="btn-primary btn-sm">确认</button>
            <button @click="cancelEditCategory" class="btn-outline btn-sm">取消</button>
          </div>
        </div>
      </transition>

      <!-- Pagination -->
      <div v-if="totalDocs > docPageSize" class="pagination">
        <button @click="docPage--; loadDocs()" :disabled="docPage <= 1" class="btn-outline btn-sm">上一页</button>
        <span class="page-indicator">{{ docPage }} / {{ totalPages }}</span>
        <button @click="docPage++; loadDocs()" :disabled="docPage >= totalPages" class="btn-outline btn-sm">下一页</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import api from '../../api'
import { useToast } from '../../composables/toast'

const props = defineProps(['tab'])
const { success, error } = useToast()

// ── Documents ──
const docs = ref([])
const totalDocs = ref(0)
const docPage = ref(1)
const docPageSize = 20
const docKeyword = ref('')
const docFilterParentCategory = ref('')
const docFilterCategory = ref('')
const docParentCategories = ref([])
const docSubCategories = ref([])
const docCategories = ref([])
const docSort = ref('updated_desc')
const selectedDocs = ref([])
const deleteLoading = ref(false)
const exportLoading = ref(false)
let docDebounceTimer = null
const editingDocId = ref(null)
const editCategoryInput = ref('')
const totalPages = computed(() => Math.ceil(totalDocs.value / docPageSize))
const isAllSelected = computed(() => docs.value.length > 0 && selectedDocs.value.length === docs.value.length)

// ── Lifecycle ──
onMounted(() => { docPage.value = 1; loadDocCategories(); loadDocs() })

watch(() => props.tab, (newTab) => {
  if (newTab === 'docs') { docPage.value = 1; loadDocCategories(); loadDocs() }
})

// ── Document categories ──
async function loadDocCategories() {
  try {
    const { data } = await api.get('/admin/documents/categories')
    docParentCategories.value = data.parent_categories || []
    docSubCategories.value = data.sub_categories || []
    docCategories.value = data.categories || []
  } catch (e) {
    console.error('Failed to load categories:', e)
  }
}

// ── Documents ──
async function loadDocs() {
  try {
    const params = { page: docPage.value, page_size: docPageSize, sort: docSort.value }
    if (docFilterParentCategory.value) params.parent_category = docFilterParentCategory.value
    if (docFilterCategory.value) params.category = docFilterCategory.value
    if (docKeyword.value) params.keyword = docKeyword.value
    const { data } = await api.get('/admin/documents', { params })
    docs.value = data.docs
    totalDocs.value = data.total
    selectedDocs.value = []
  } catch (e) { console.error('Failed to load docs:', e); error('加载文档失败') }
}

function debounceLoadDocs() {
  clearTimeout(docDebounceTimer)
  docDebounceTimer = setTimeout(() => { docPage.value = 1; loadDocs() }, 300)
}

async function deleteDoc(id) {
  try {
    deleteLoading.value = true
    await api.delete(`/admin/documents/${id}`)
    await loadDocs()
    success('文档已删除')
  } catch (e) { error('删除文档失败') }
  finally { deleteLoading.value = false }
}

async function exportDocs() {
  exportLoading.value = true
  try {
    const params = { sort: docSort.value }
    if (docFilterParentCategory.value) params.parent_category = docFilterParentCategory.value
    if (docFilterCategory.value) params.category = docFilterCategory.value
    if (docKeyword.value) params.keyword = docKeyword.value
    const response = await api.get('/admin/documents/export', { params, responseType: 'blob' })
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', 'documents.csv')
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
    success('导出成功')
  } catch (e) { error('导出失败') }
  finally { exportLoading.value = false }
}

async function batchDeleteDocs() {
  try {
    deleteLoading.value = true
    await api.delete('/admin/documents', { data: { ids: selectedDocs.value } })
    selectedDocs.value = []
    await loadDocs()
    success('批量删除完成')
  } catch (e) { error('批量删除失败') }
  finally { deleteLoading.value = false }
}

async function approveCategory(d) {
  try {
    await api.post(`/admin/documents/${d.id}/approve`)
    success('已采纳 AI 分类')
    await loadDocs()
  } catch (e) { error(e.response?.data?.detail || '采纳失败') }
}

function editCategory(d) {
  editingDocId.value = d.id
  editCategoryInput.value = d.category || ''
}

async function confirmEditCategory() {
  if (!editingDocId.value || !editCategoryInput.value.trim()) return
  try {
    await api.put(`/admin/documents/${editingDocId.value}/category`, null, {
      params: { category: editCategoryInput.value.trim() }
    })
    success('分类已修改')
    editingDocId.value = null
    editCategoryInput.value = ''
    await loadDocs()
  } catch (e) { error(e.response?.data?.detail || '修改失败') }
}

function cancelEditCategory() {
  editingDocId.value = null
  editCategoryInput.value = ''
}

function toggleSelectAllDocs() {
  selectedDocs.value = isAllSelected.value ? [] : docs.value.map(d => d.id)
}
</script>

<style scoped>
@import '../../assets/admin-shared.css';

.docs-tab { --ease-out: cubic-bezier(0.16, 1, 0.3, 1); }

/* ── Toolbar ── */
.table-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
  flex-wrap: wrap;
}
.toolbar-left {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-shrink: 0;
}
.toolbar-right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.table-count {
  font-size: 0.8125rem;
  color: var(--color-text-muted);
  white-space: nowrap;
}
.table-count strong {
  color: var(--color-text);
  font-weight: 700;
}

/* ── Inline filter ── */
.inline-filter {
  position: relative;
  display: flex;
  align-items: center;
}
.filter-icon {
  position: absolute;
  left: 0.6rem;
  color: var(--color-text-faint);
  pointer-events: none;
}
.filter-input {
  padding: 0.5rem 0.75rem 0.5rem 2rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  font-size: 0.875rem;
  color: var(--color-text);
  background: var(--color-bg);
  font-family: var(--font-sans);
  outline: none;
  width: 200px;
  transition: border-color 200ms var(--ease-out), box-shadow 200ms var(--ease-out);
}
.filter-input:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(37,99,235,0.10);
}
.filter-input::placeholder { color: var(--color-text-faint); }

.filter-select {
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  font-size: 0.875rem;
  background: var(--color-bg);
  color: var(--color-text);
  font-family: var(--font-sans);
  cursor: pointer;
  transition: border-color 200ms var(--ease-out);
}
.filter-select:focus { outline: none; border-color: var(--color-primary); }

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

/* ── Cells ── */
.cell-url {
  font-size: 0.6875rem;
  color: var(--color-text-faint);
  word-break: break-all;
  margin-top: 2px;
  max-width: 280px;
}
.cell-tag {
  display: inline-block;
  font-size: 0.75rem;
  color: var(--color-text-secondary);
}
.cell-dept {
  color: var(--color-text-muted);
  font-size: 0.8125rem;
  white-space: nowrap;
}
.cell-date {
  color: var(--color-text-muted);
  font-size: 0.8125rem;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.cell-empty {
  text-align: center;
  color: var(--color-text-faint);
  padding: var(--space-6) !important;
}
.cell-actions {
  display: flex;
  gap: 2px;
  align-items: center;
  white-space: nowrap;
}

/* ── Doc link ── */
.doc-link {
  color: var(--color-text);
  font-weight: 500;
  text-decoration: none;
  font-size: 0.875rem;
}
.doc-link:hover { color: var(--color-primary); text-decoration: underline; }

/* ── Category cell ── */
.category-cell {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
}
.category-text {
  font-size: 0.8125rem;
  color: var(--color-text-secondary);
}

/* ── Inline editor ── */
.inline-editor {
  padding: var(--space-3) var(--space-4);
  background: var(--color-surface);
  border-top: 1px solid var(--color-border);
}
.inline-editor-label {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: var(--space-2);
}
.inline-editor-body {
  display: flex;
  gap: var(--space-2);
  align-items: center;
}
.inline-editor-body .input {
  flex: 1;
  max-width: 300px;
  transition: border-color 200ms var(--ease-out), box-shadow 200ms var(--ease-out);
}

/* ── Pagination ── */
.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  padding: var(--space-3);
  border-top: 1px solid var(--color-border);
}
.page-indicator {
  font-size: 0.8125rem;
  color: var(--color-text-muted);
  font-variant-numeric: tabular-nums;
}

/* ── Transitions ── */
.edit-slide-enter-active,
.edit-slide-leave-active {
  transition: opacity 200ms var(--ease-out), max-height 200ms var(--ease-out);
  max-height: 120px;
  overflow: hidden;
}
.edit-slide-enter-from,
.edit-slide-leave-to {
  opacity: 0;
  max-height: 0;
}

/* ── Responsive ── */
@media (max-width: 768px) {
  .table-toolbar { flex-direction: column; align-items: flex-start; }
  .toolbar-right { width: 100%; flex-wrap: wrap; }
  .filter-input { width: 100%; }
  .data-table { display: block; overflow-x: auto; }
  .cell-url { max-width: 160px; }
}
</style>
