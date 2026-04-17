<template>
  <div class="source-list" v-if="sources && sources.length > 0">
    <div v-if="fallback && !dismissFallback" class="fallback-notice">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/>
      </svg>
      <span>关键词提取未生效，使用了原始问题搜索，结果可能不够精准</span>
      <button class="fallback-close" @click="dismissFallback = true" aria-label="关闭提示">&times;</button>
    </div>

    <div class="source-label">来源：</div>
    <div v-for="s in sources" :key="s.doc_id || s.index" class="source-item">
      <a :href="s.url" target="_blank" class="source-link">
        <span v-if="s.index" class="source-index">[{{ s.index }}]</span>
        {{ s.title }}
      </a>
      <div class="source-meta">
        <span v-if="s.score" class="source-score">{{ Math.round(s.score * 100) }}%</span>
        <span v-if="s.source" class="source-tag" :class="'tag-' + s.source">
          {{ sourceLabel(s.source) }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  sources: {
    type: Array,
    default: () => [],
  },
  fallback: {
    type: String,
    default: null,
  },
})

const dismissFallback = ref(false)

function sourceLabel(source) {
  const labels = { keyword: '关键词', vector: '语义', both: '双重' }
  return labels[source] || source
}
</script>

<style scoped>
.source-list {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.fallback-notice {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 6px;
  background: #fef3cd;
  color: #856404;
  font-size: 0.75rem;
  line-height: 1.4;
}
[data-theme="dark"] .fallback-notice {
  background: #3d3415;
  color: #f0d060;
}
.fallback-close {
  margin-left: auto;
  background: none;
  border: none;
  color: inherit;
  cursor: pointer;
  font-size: 1rem;
  line-height: 1;
  padding: 0 2px;
}

.source-label {
  font-size: 0.75rem;
  color: var(--color-text-secondary);
  margin-bottom: 2px;
}

.source-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.source-link {
  font-size: 0.8125rem;
  color: var(--color-primary);
  text-decoration: none;
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.source-link:hover { text-decoration: underline; }

.source-index {
  font-weight: 600;
  font-size: 0.75rem;
  color: var(--color-primary);
  flex-shrink: 0;
}

.source-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.source-score {
  font-size: 0.6875rem;
  color: var(--color-text-secondary);
}

.source-tag {
  font-size: 0.625rem;
  font-weight: 600;
  padding: 1px 5px;
  border-radius: 3px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
.tag-keyword {
  background: #e0edff;
  color: #1a56db;
}
.tag-vector {
  background: #e6f9ed;
  color: #15803d;
}
.tag-both {
  background: #fff3e0;
  color: #c2410c;
}
[data-theme="dark"] .tag-keyword {
  background: #1e3a5f;
  color: #7cb3f0;
}
[data-theme="dark"] .tag-vector {
  background: #1a3d2a;
  color: #6ee7a0;
}
[data-theme="dark"] .tag-both {
  background: #3d2a15;
  color: #f0a060;
}
</style>
