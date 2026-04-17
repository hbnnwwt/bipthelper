# 项目任务清单

> 生成时间: 2026-04-07
> 状态: ✅ = 已完成 | ⚠️ = 部分完成 | ❌ = 未开始 | 🔴 = 阻塞

---

## 一、后端修复

### 安全类 (CRITICAL / HIGH)

| # | 状态 | 文件 | 描述 |
|---|------|------|------|
| 1 | ✅ | `config.py` | 默认 SECRET_KEY 硬编码 → 改为随机生成并打印到控制台 |
| 2 | ✅ | `database.py` | 默认管理员 admin/admin123 后门 → 改为随机密码并打印 |
| 3 | ✅ | `main.py` | CORS `allow_origins=["*"]` + credentials → 限制为 `localhost:3000` |
| 4 | ✅ | `api/auth.py` | 邀请码只检查 `ADMIN-` 前缀 → 改为数据库 invite_code 字段验证 |
| 5 | ✅ | `services/encryption.py` | API 密钥明文存储 → 新增 Fernet 加密/解密模块 |
| 6 | ✅ | `api/ai.py` | save_provider 写入加密后的 API 密钥 |
| 7 | ✅ | `services/ai/client.py` | get_provider_config 解密后返回 API 密钥 |
| 8 | ✅ | `requirements.txt` + `main.py` + `api/auth.py` | `slowapi` 速率限制中间件已挂载，`/auth/login` 限流 5次/分钟 |

### Bug 修复

| # | 状态 | 文件 | 描述 |
|---|------|------|------|
| 9 | ✅ | `services/crawler.py` | 爬虫并发无防护 → 添加 `crawl_running` 前置检查 |
| 10 | ✅ | `services/crawler.py` | 停止标志不检查 → `_crawl_all_impl` 循环间检查 `crawl_stop_requested` |
| 11 | ✅ | `api/admin.py` | 批量删除计数错误 → 改为实际删除数而非提交 ID 数 |
| 12 | ✅ | `services/auth.py` | `datetime.utcnow()` 废弃 → 改为 `datetime.now(timezone.utc)` |
| 13 | ✅ | `services/ai/client.py` | 同步 `requests` 阻塞事件循环 → 改为 `httpx` |
| 14 | ✅ | `api/admin.py`, `api/ai.py` | 类型标注错误 (`str = None` → `Optional[str] = None`) |

### 代码质量

| # | 状态 | 文件 | 描述 |
|---|------|------|------|
| 15 | ✅ | `api/auth.py` | 移除未使用的 `uuid`, `secrets` 导入 |
| 16 | ✅ | `models/__init__.py` | 补全 `AIProvider`, `AICategoryScene` 导出 |

---

## 二、前端修复

### 基础设施

| # | 状态 | 文件 | 描述 |
|---|------|------|------|
| 17 | ✅ | `api/index.js` | 无错误处理 → 添加请求拦截器 (自动注入 token) + 响应拦截器 (401 自动跳转登录) |
| 18 | ✅ | `stores/auth.js` | Token 永不过期 → 添加 `tokenExpiry` 字段，过期自动登出 |
| 19 | ✅ | `router/index.js` | 无 404 路由 → 添加 `/:pathMatch(.*)*` 重定向到首页 |
| 20 | ✅ | `router/index.js` | 已登录用户可访问登录/注册页 → 添加重定向逻辑 |
| 21 | ✅ | `composables/toast.js` | 新建 Toast 通知 composable |
| 22 | ✅ | `components/ToastContainer.vue` | 新建 Toast 通知 UI 组件 (Teleport + TransitionGroup) |
| 23 | ✅ | `App.vue` | 全局挂载 ToastContainer |

### 页面修复

| # | 状态 | 文件 | 描述 |
|---|------|------|------|
| 24 | ✅ | `views/Home.vue` | XSS 漏洞 `v-html` → 改为纯文本 `{{ }}` 渲染 |
| 25 | ✅ | `views/Home.vue` | `searched` 状态误导 → 仅在 API 成功后设为 true |
| 26 | ✅ | `views/Admin.vue` | colspan=6 应为 7 → 已修正 |
| 27 | ✅ | `views/Admin.vue` | 12+ 个 API 调用无 try/catch → 全部添加错误处理 + Toast 反馈 |
| 28 | ✅ | `views/Admin.vue` | `alert()`/`confirm()` 滥用 → 全部替换为 Toast |
| 29 | ✅ | `views/Admin.vue` | 无防重复点击 → 添加 `crawlLoading`, `deleteLoading` 状态 |
| 30 | ✅ | `views/Admin.vue` | 空表格无空状态 → 添加 `colspan` 空行提示 |
| 31 | ✅ | `views/Admin.vue` | CSS 变量引用错误 (`--log-*`, `--color-success-dark`) → 改为硬编码色值 |
| 32 | ✅ | `views/Admin.vue` | 无响应式 → 添加 `@media (max-width: 768px)` 适配 |
| 33 | ✅ | `views/AISettings.vue` | `alert()`/`confirm()` → 替换为 Toast |
| 34 | ✅ | `views/AISettings.vue` | API 调用无错误处理 → 全部添加 try/catch |

---

## 三、遗留问题 (待处理)

### 🔴 阻塞性问题

| # | 优先级 | 文件 | 描述 | 建议方案 |
|---|--------|------|------|----------|
| L1 | ✅ | `api/admin.py` | 添加 `PUT /admin/users/{user_id}/password` 密码重置接口 | 管理员可重置任意用户密码 |
| L2 | ✅ | `api/auth.py` | 邀请码流程已确认正确：admin 创建用户 → 注册时激活 | — |

### ⚠️ 待优化

| # | 优先级 | 文件 | 描述 | 建议方案 |
|---|--------|------|------|----------|
| L3 | ✅ | `main.py` + `api/auth.py` | slowapi 速率限制中间件已挂载，`/auth/login` 限流 5次/分钟 | — |
| L4 | ✅ | `services/crawler.py` | Playwright 爬虫在 Windows 上可能需要 `playwright install` | 在 README 中添加安装说明 |
| L5 | ✅ | `views/Admin.vue` | 538 行单体组件，未拆分 | 拆分为 UsersTab, CrawlerTab, DocsTab 子组件 |
| L6 | ✅ | 全局 | 前端无输入长度/格式校验（如 URL 格式、CSS 选择器合法性） | 添加表单验证规则 |
| L7 | ✅ | 全部 | AI 分类降级与人工复核队列已完成：Document 新增 ai_status/ai_suggested_categories/ai_reviewed_at 字段；categorize_article 简化为标题模式；爬虫集成 ai_status 状态机；Admin API 新增 pending 列表/approve/manual_category 端点；Admin.vue DocsTab 新增状态筛选/badge/采纳/修改按钮 | — |
| L8 | ✅ | `views/Home.vue` | 搜索结果为空时无初始引导内容 | 添加热门搜索/推荐内容 |
| L9 | ✅ | `stores/auth.js` + `backend/services/auth.py` + `backend/api/` | Token 存储在 localStorage，有 XSS 风险 → 已迁移到 httpOnly cookie（后端 endpoints 全部改用 `get_current_user_from_cookie`，logout 清除 cookie） | — |
| L10 | ✅ | `api/admin.py` | `trigger_crawl` 使用 `threading.Thread` → 改为 `scheduler.add_job()` 使用 APScheduler 持久化调度，进程重启后任务不丢失 | — |
| L11 | ✅ | `models/document.py` | `created_at`/`updated_at` 改为 `datetime.now(timezone.utc).isoformat()` | 统一为 timezone-aware |
| L12 | ✅ | `models/user.py` | `created_at` 改为 `datetime.now(timezone.utc).isoformat()` | 统一为 timezone-aware |

### 💡 功能增强建议

| # | 优先级 | 描述 |
|---|--------|------|
| F1 | ✅ | 添加用户密码修改功能（`PUT /auth/password`，验证旧密码后修改） |
| F2 | ✅ | 添加操作审计日志（谁删除了文档、修改了配置等） |
| F3 | ✅ | 前端添加深色模式支持 |
| F4 | ✅ | 添加全文搜索高亮（后端 `_formatted` 字段返回 `<mark>` 标签，前端 Home.vue 渲染 `item._formatted?.title` 和 `item._formatted?.content`） |
| F5 | ✅ | 爬虫进度实时显示（当前只有 running/idle 二态） |
| F6 | ✅ | 添加数据导出功能（CSV/Excel） |
| F7 | MEDIUM | 自然语言问答系统（RAG + Qdrant 向量检索 + 多会话对话） |

---

## 四、部署检查清单

- [ ] 设置环境变量 `SECRET_KEY`（或使用首次启动时生成的密钥）
- [ ] 记录首次启动时打印的 admin 随机密码
- [ ] 配置 Meilisearch 服务并设置 `MEILISEARCH_MASTER_KEY`
- [ ] 运行 `playwright install` 安装浏览器
- [ ] 配置生产环境 CORS 允许的域名
- [ ] 启用 HTTPS
- [ ] 配置数据库备份策略
- [ ] 设置日志轮转

---

## 五、统计

| 类别 | 已完成 | 待处理 | 总计 |
|------|--------|--------|------|
| 安全修复 | 8 | 0 | 8 |
| Bug 修复 | 6 | 0 | 6 |
| 代码质量 | 2 | 0 | 2 |
| 前端基础设施 | 7 | 0 | 7 |
| 前端页面修复 | 12 | 0 | 12 |
| 遗留问题 | 12 | 0 | 12 |
| 功能增强 | 7 | 0 | 7 |
| **总计** | **54** | **0** | **54** |
