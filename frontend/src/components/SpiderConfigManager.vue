<template>
  <div class="spider-config-manager">
    <!-- 批量操作栏 -->
    <div class="batch-actions" v-if="selectionCount > 0">
      <el-checkbox v-model="selectAll" @change="toggleAll">全选</el-checkbox>
      <span>已选择 {{ selectionCount }} 项</span>
      <el-button size="small" type="danger" @click="batchDelete" :disabled="selectionCount === 0">
        批量删除
      </el-button>
      <el-button size="small" type="primary" @click="batchStart" :disabled="selectionCount === 0">
        批量开始
      </el-button>
      <el-button size="small" @click="clearSelection">取消选择</el-button>
    </div>

    <!-- 爬取模式切换 -->
    <div class="mode-switch">
      <el-radio-group v-model="crawlMode" @change="handleModeChange">
        <el-radio label="full">全量爬取</el-radio>
        <el-radio label="incremental">增量爬取</el-radio>
      </el-radio-group>
      <el-tooltip content="全量会爬取全部页面，增量只爬取新增页面" placement="top">
        <el-icon class="help-icon">?<el-tooltip>
      </el-tooltip>
    </div>

    <!-- 配置列表 -->
    <div class="config-list">
      <div v-for="config in configs" :key="config.id" class="config-item">
        <el-checkbox
          v-model="selectedIds"
          :label="config.id"
          @change="(val) => handleSelection(config.id, val)"
        />
        <div class="config-info">
          <div class="config-name">{{ config.name }}</div>
          <div class="config-desc">
            <span>URL: {{ config.url }}</span>
            <span>分类: {{ config.category || '未设置' }}</span>
            <span>模式: {{ config.is_list_page ? '列表页' : '单页' }}</span>
          </div>
          <div class="config-stats">
            <span>已爬取: {{ config.initialized ? '是' : '否' }}</span>
            <span>状态: {{ config.enabled ? '启用' : '禁用' }}</span>
            <span v-if="config.last_crawl">最后: {{ formatTime(config.last_crawl) }}</span>
          </div>
        </div>
        <div class="config-actions">
          <el-button size="small" @click="toggleConfig(config)">
            {{ config.enabled ? '暂停' : '开始' }}
          </el-button>
          <el-button size="small" type="primary" @click="startCrawl(config)">
            立即爬取
          </el-button>
          <el-button size="small" type="danger" @click="deleteConfig(config)">
            删除
          </el-button>
        </div>
      </div>
    </div>

    <!-- 添加配置表单 -->
    <el-card class="add-config-card">
      <template #header>
        <span>添加新配置</span>
      </template>
      <el-form :model="newConfig" label-width="100px">
        <el-form-item label="名称">
          <el-input v-model="newConfig.name" placeholder="配置名称" />
        </el-form-item>
        <el-form-item label="URL">
          <el-input v-model="newConfig.url" placeholder="起始URL" />
        </el-form-item>
        <el-form-item label="分类">
          <el-input v-model="newConfig.category" placeholder="默认分类" />
        </el-form-item>
        <el-form-item label="大类">
          <el-input v-model="newConfig.parent_category" placeholder="父分类" />
        </el-form-item>
        <el-form-item label="小类">
          <el-input v-model="newConfig.sub_category" placeholder="子分类" />
        </el-form-item>
        <el-form-item label="是否为列表页">
          <el-switch v-model="newConfig.is_list_page" />
        </el-form-item>
        <el-form-item v-if="newConfig.is_list_page" label="文章选择器">
          <el-input v-model="newConfig.article_selector" placeholder="例如: a.article-link" />
        </el-form-item>
        <el-form-item v-if="newConfig.is_list_page" label="链接前缀">
          <el-input v-model="newConfig.link_prefix" placeholder="例如: https://example.com" />
        </el-form-item>
        <el-form-item label="分页选择器">
          <el-input v-model="newConfig.pagination_selector" placeholder="例如: .pagination a" />
        </el-form-item>
        <el-form-item label="最大页数">
          <el-input-number v-model="newConfig.pagination_max" :min="0" />
        </el-form-item>
        <el-form-item label="CSS选择器">
          <el-input v-model="newConfig.selector" placeholder="例如: .article-content" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="addConfig">添加配置</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const crawlMode = ref('incremental')
const selectedIds = ref([])
const configs = ref([])

const newConfig = reactive({
  name: '',
  url: '',
  category: '',
  parent_category: '',
  sub_category: '',
  is_list_page: true,
  article_selector: 'a',
  link_prefix: '',
  pagination_selector: '',
  pagination_max: 0,
  selector: 'body'
})

const selectionCount = computed(() => selectedIds.value.length)

// 初始化加载配置
const loadConfigs = async () => {
  try {
    const response = await fetch('/api/crawl-configs')
    configs.value = await response.json()
  } catch (error) {
    console.error('加载配置失败:', error)
    ElMessage.error('加载配置失败')
  }
}

// 全选切换
const toggleAll = (val) => {
  if (val) {
    selectedIds.value = configs.value.map(c => c.id)
  } else {
    selectedIds.value = []
  }
}

// 选择单个
const handleSelection = (id, selected) => {
  if (!selected) {
    selectedIds.value = selectedIds.value.filter(uid => uid !== id)
  } else if (!selectedIds.value.includes(id)) {
    selectedIds.value.push(id)
  }
}

// 批量删除
const batchDelete = async () => {
  try {
    await ElMessageBox.confirm('确定要删除选中的配置吗？', '确认操作', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    const response = await fetch('/api/admin/crawl/configs', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids: selectedIds.value })
    })

    if (response.ok) {
      ElMessage.success('删除成功')
      loadConfigs()
    } else {
      ElMessage.error('删除失败')
    }
  } catch (error) {
    // 用户取消
  }
}

// 批量开始
const batchStart = async () => {
  try {
    await ElMessageBox.confirm('确定要启动选中的配置吗？', '确认操作', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'info'
    })

    const response = await fetch('/api/admin/crawl/configs/batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        navigation: selectedIds.value.map(id => {
          const config = configs.value.find(c => c.id === id)
          return {
            parent: config?.parent_category || '',
            subs: [{ name: config?.name || '', url: config?.url || '' }]
          }
        })
      })
    })

    if (response.ok) {
      ElMessage.success('启动成功')
      loadConfigs()
    } else {
      ElMessage.error('启动失败')
    }
  } catch (error) {
    // 用户取消
  }
}

// 清空选择
const clearSelection = () => {
  selectedIds.value = []
}

// 模式切换
const handleModeChange = (mode) => {
  // 根据模式调整默认配置
  if (mode === 'full') {
    newConfig.pagination_max = 0 // 全量爬取不限制页数
  } else {
    newConfig.pagination_max = 1 // 增量只爬第一页
  }
}

// 添加配置
const addConfig = async () => {
  try {
    const response = await fetch('/api/crawl-configs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newConfig)
    })

    if (response.ok) {
      ElMessage.success('添加成功')
      loadConfigs()
      // 重置表单
      Object.keys(newConfig).forEach(key => {
        if (typeof newConfig[key] === 'boolean') {
          newConfig[key] = false
        } else if (typeof newConfig[key] === 'number') {
          newConfig[key] = 0
        } else {
          newConfig[key] = ''
        }
      })
      newConfig.is_list_page = true
      newConfig.pagination_max = 0
    } else {
      ElMessage.error('添加失败')
    }
  } catch (error) {
    console.error('添加失败:', error)
    ElMessage.error('添加失败')
  }
}

// 切换配置状态
const toggleConfig = async (config) => {
  try {
    const newStatus = !config.enabled
    const response = await fetch(`/api/crawl-configs/${config.id}/toggle`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: newStatus })
    })

    if (response.ok) {
      config.enabled = newStatus
      ElMessage.success(newStatus ? '已启动' : '已暂停')
    } else {
      ElMessage.error('操作失败')
    }
  } catch (error) {
    console.error('操作失败:', error)
    ElMessage.error('操作失败')
  }
}

// 立即爬取
const startCrawl = async (config) => {
  try {
    const response = await fetch(`/api/crawl-configs/${config.id}/crawl`, {
      method: 'POST'
    })

    if (response.ok) {
      ElMessage.success('爬取任务已启动')
    } else {
      ElMessage.error('启动失败')
    }
  } catch (error) {
    console.error('启动失败:', error)
    ElMessage.error('启动失败')
  }
}

// 删除配置
const deleteConfig = async (config) => {
  try {
    await ElMessageBox.confirm('确定要删除此配置吗？', '确认操作', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    const response = await fetch(`/api/crawl-configs/${config.id}`, {
      method: 'DELETE'
    })

    if (response.ok) {
      ElMessage.success('删除成功')
      loadConfigs()
    } else {
      ElMessage.error('删除失败')
    }
  } catch (error) {
    // 用户取消
  }
}

// 格式化时间
const formatTime = (timeStr) => {
  const date = new Date(timeStr)
  return date.toLocaleString('zh-CN')
}

// 组件挂载
loadConfigs()
</script>

<style scoped>
.spider-config-manager {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

.batch-actions {
  display: flex;
  align-items: center;
  gap: 15px;
  margin-bottom: 20px;
  padding: 15px;
  background-color: #f5f7fa;
  border-radius: 4px;
}

.mode-switch {
  margin-bottom: 20px;
  padding: 15px;
  background-color: #f5f7fa;
  border-radius: 4px;
}

.config-list {
  margin-bottom: 30px;
}

.config-item {
  display: flex;
  align-items: flex-start;
  gap: 15px;
  padding: 15px;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  margin-bottom: 10px;
  transition: all 0.3s;
}

.config-item:hover {
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.config-info {
  flex: 1;
}

.config-name {
  font-size: 16px;
  font-weight: 500;
  margin-bottom: 8px;
}

.config-desc {
  display: flex;
  gap: 15px;
  font-size: 13px;
  color: #909399;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.config-stats {
  display: flex;
  gap: 15px;
  font-size: 13px;
  color: #606266;
}

.config-actions {
  display: flex;
  gap: 8px;
  flex-direction: column;
}

.add-config-card {
  margin-top: 20px;
}

.help-icon {
  margin-left: 5px;
  cursor: help;
}
</style>