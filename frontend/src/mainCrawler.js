import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import routerCrawler from './routerCrawler'

const app = createApp(App)
app.use(createPinia())
app.use(routerCrawler)
app.mount('#app')
