# Admin.vue 组件拆分计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 847 行 Admin.vue 拆分为 UsersTab、CrawlerTab、DocsTab 三个独立子组件，父组件 Admin.vue 只做 tab 路由分发。

**Architecture:**
- 新建 `frontend/src/components/admin/` 目录
- `UsersTab.vue`、`CrawlerTab.vue`、`DocsTab.vue` 各自独立
- Admin.vue 简化为布局 + tab 切换，状态通过 props/emit 传递
- 共享样式提取到 `Admin.vue` 保留（scoped 样式自然隔离）

---

## File Map

```
frontend/src/components/admin/UsersTab.vue    — 新建，用户管理 tab
frontend/src/components/admin/CrawlerTab.vue   — 新建，爬虫配置 tab
frontend/src/components/admin/DocsTab.vue     — 新建，文档管理 tab
frontend/src/views/Admin.vue                  — 修改，简化为布局 + tab 路由
```

---

## Task 1: 创建 UsersTab.vue

**Files:**
- Create: `frontend/src/components/admin/UsersTab.vue`

从 Admin.vue 提取：
- 模板：`<section v-if="tab === 'users'">` 整个 section（lines 28-78）
- Script：users、newUsername、generatedCode ref；loadUsers、createInvite、copyCode 函数
- 样式：属于 users 区域的 scoped 样式（invite-form、invite-code、code、cell-username、cell-muted、status-dot、dot-active、dot-inactive）

**Props:** 无（独立数据自己在 onMounted 加载）
**Emit:** 无

```vue
<template>
  <div class="tab-content">
    <!-- 完整 Users tab template -->
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../../api'
import { useToast } from '../../composables/toast'

const { success, error } = useToast()
// ... extracted users logic
</script>

<style scoped>
/* users-specific styles */
</style>
```

- [ ] **Step 1: 创建 UsersTab.vue，提取 users 相关代码**
- [ ] **Step 2: 提交**
- [ ] **Step 3: spec compliance review**
- [ ] **Step 4: code quality review**

---

## Task 2: 创建 CrawlerTab.vue

**Files:**
- Create: `frontend/src/components/admin/CrawlerTab.vue`

从 Admin.vue 提取：
- 模板：`<section v-if="tab === 'crawler'">` 整个 section（lines 81-188）
- Script：configs、showAdvanced、showLogs、logs、logBox、crawlStatus、crawlLoading、newConfig、logTimer、statusTimer ref；所有 crawler 相关函数
- 样式：log-card、log-actions、log-box、log-* 等 crawler 样式

**Props:** 无（自己在 onMounted 加载 configs，在 watch tab 时启动/停止 timers）

- [ ] **Step 1: 创建 CrawlerTab.vue，提取 crawler 相关代码**
- [ ] **Step 2: 提交**
- [ ] **Step 3: spec compliance review**
- [ ] **Step 4: code quality review**

---

## Task 3: 创建 DocsTab.vue

**Files:**
- Create: `frontend/src/components/admin/DocsTab.vue`

从 Admin.vue 提取：
- 模板：`<section v-if="tab === 'docs'">` 整个 section（lines 190-291）
- Script：docs、totalDocs、docPage、docPageSize、docKeyword、docFilterCategory、docCategories、selectedDocs、deleteLoading、docDebounceTimer、docFilterAiStatus、editingDocId、editCategoryInput、totalPages、isAllSelected computed、aiStatusBadge；所有 docs 相关函数
- 样式：filter-bar、input-search、filter-select、pagination、page-indicator、inline-edit-card、inline-edit-header、inline-edit-title、inline-edit-body 等 docs 样式

**注意：** `isAllSelected` 改为 `const isAllSelected = computed(() => ...)`

- [ ] **Step 1: 创建 DocsTab.vue，提取 docs 相关代码**
- [ ] **Step 2: 提交**
- [ ] **Step 3: spec compliance review**
- [ ] **Step 4: code quality review**

---

## Task 4: 重构 Admin.vue 为纯布局组件

**Files:**
- Modify: `frontend/src/views/Admin.vue`

1. **移除**：所有三个 tab 的模板内容，只保留 `<div class="admin">` 布局 + tab nav + `<component :is="currentTabComponent" />` 动态组件
2. **移除**：所有三个 tab 的 script 代码（ref、computed、functions）
3. **保留**：`<style scoped>` 中共享的布局样式（.admin、.header、.header-inner、.logo、.back-link、.page-body、.tabs、.tabs button、.tabs button.active、.section-toolbar、.section-title、.toolbar-actions、.card、.card-title、.card-header-row、.data-table、.data-table th、.data-table td、.data-table tr:hover td、.link、.link:hover、.badge、.badge-primary、.badge-success、.badge-warning、.badge-muted、.btn-primary、.btn-outline、.btn-danger、.btn-sm、.btn-ghost-xs、.btn-ghost-xs:hover、.btn-ghost-xs:disabled、.btn-text-danger、.btn-text-danger:hover）
4. **新增**：导入并注册三个子组件，tab 切换逻辑改为 `:is="currentTabComponent"` 动态组件
5. **保留**：tab state（用于 tab nav 高亮）+ tabs 定义 + switchTab 函数

**动态组件方式：**
```javascript
import UsersTab from '../components/admin/UsersTab.vue'
import CrawlerTab from '../components/admin/CrawlerTab.vue'
import DocsTab from '../components/admin/DocsTab.vue'

const tabComponents = { users: UsersTab, crawler: CrawlerTab, docs: DocsTab }
const currentTabComponent = computed(() => tabComponents[tab.value])
```

模板：
```html
<component :is="currentTabComponent" />
```

**注意**：tabs 中的 `role="tablist"` 保留在 Admin.vue；子组件不需要 role tab 结构。

- [ ] **Step 1: 重构 Admin.vue 为布局组件，动态加载子组件**
- [ ] **Step 2: 提交**
- [ ] **Step 3: spec compliance review**
- [ ] **Step 4: code quality review**

---

## 验证步骤

1. 启动前端 `npm run dev`
2. 访问 Admin 页面，切换三个 tab，确认每个 tab 内容正常渲染
3. Users tab：生成邀请码、查看用户列表
4. Crawler tab：添加配置、触发爬取、查看日志
5. Docs tab：搜索文档、批量选择、修改分类
6. 响应式测试：在 768px 以下切换 tab，确认布局正常

---

## 完成后

- [ ] 更新 `docs/opencode/task.md`：L5 从"MEDIUM"改为"✅"
- [ ] 提交: `git add docs/opencode/task.md && git commit -m "docs: mark L5 complete in task.md"`
