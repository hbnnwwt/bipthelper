<template>
  <div class="spider-config-page">
    <h1>爬虫配置管理</h1>

    <SpiderConfigManager />
  </div>
</template>

<script setup>
import SpiderConfigManager from '../components/SpiderConfigManager.vue'
</script>

<style scoped>
.spider-config-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

h1 {
  text-align: center;
  margin-bottom: 30px;
}
</style>