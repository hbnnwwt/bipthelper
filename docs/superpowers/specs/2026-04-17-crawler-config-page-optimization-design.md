# 爬虫配置页面优化设计

## 现状问题

### 后端：两套 API 职责重叠

| Router | 路径 | 认证 | 问题 |
|--------|------|------|------|
| `crawl_config.py` | `/api/crawl-configs/*` | **无认证** | 任何人可直接读写爬虫配置，极不安全 |
| `admin.py` | `/api/admin/configs/*`, `/api/admin/crawl/*` | admin 认证 | 完整功能 |

两套并存导致维护困难、职责不清。

### 前端：两个核心痛点

1. **进度看不清** — `crawl_progress` 只记录当前配置的 page/articles 数字，配置列表进度条只能靠 `current_config_id` 匹配。假设 10 个配置爬到第 3 个，用户只知道"第 3 个"，不知道前 2 个是否完成、卡在哪。
2. **列表太长找不到配置** — 配置数量已达 20+，无过滤无搜索，全靠肉眼扫。

---

## 方案

### 后端：合并 API

**删除 `backend/api/crawl_config.py`**，所有爬虫配置操作统一到 `/api/admin/configs` 和 `/api/admin/crawl/*`。

已有 `admin.py` 实现了完整功能，无需重复。

### 后端：`crawl_progress` 结构扩展

在 `crawl_progress` 中增加 `configs` 字段，记录每个配置的详细进度：

```python
crawl_progress = {
    "phase": "idle",        # idle | running | stopping
    "total_configs": 0,
    "configs": [            # 新增：每个配置一行进度
        {
            "id": "...",
            "name": "通知公告",
            "page": 2,
            "total_pages": 5,
            "articles_crawled": 12,
            "articles_total": 30,
            "status": "running",  # running | done | error
        }
    ],
    # 以下字段保留，兼容旧前端
    "current_config": "",
    "current_config_id": None,
    "config_index": 0,
    "page": 0,
    "total_pages": 0,
    "articles_crawled": 0,
    "articles_total": 0,
}
```

**更新时机：** 每完成一个配置的爬取（进入下一个配置前）更新 `configs` 条目。每轮询一次返回完整快照。

**旧字段兼容：** 保留 `current_config_id`、`current_config`、`config_index`、`page`、`total_pages`、`articles_crawled`、`articles_total`，前端可逐步迁移。

### 前端：配置列表三级过滤

在配置表格上方增加三个过滤器：

1. **搜索框** — 按名称模糊匹配（300ms 防抖）
2. **大类下拉** — 筛选 `parent_category`，选项动态从已有配置中提取
3. **小类下拉** — 筛选 `sub_category`，依赖大类选择

过滤在本地执行（无需请求），已有配置一次性拉回即可。

### 前端：进度展示改为逐配置明细

当前：全局进度条 + 每行根据 `current_config_id` 条件渲染

改为：每个配置一行独立进度条，字段直接来自 `configs[i]`，无需 ID 匹配。

---

## 实施步骤

1. 删除 `backend/api/crawl_config.py`（确认无外部调用）
2. 修改 `crawler.py` 中 `crawl_progress` 初始化和重置逻辑，增加 `configs` 字段
3. 修改 `_crawl_all_impl` 和 `_crawl_configs_impl`，在配置切换时更新 `configs` 条目
4. 前端：三级过滤逻辑
5. 前端：进度展示改为读 `configs` 字段
6. 测试完整流程

---

## 自检

- [x] 无 Placeholder/TODO
- [x] 前后端字段一致（configs[i].* vs crawl_progress.configs[i].*）
- [x] scope 聚焦（不涉及文档管理、审计日志等其他 Tab）
- [x] 两套 API 合并方案已与用户确认
