# Spider Configuration Management Design

## Overview
This document describes the design for the spider configuration management page, which allows administrators to manage web crawler configurations with support for full/incremental crawl modes and batch operations.

## Project Context
- **System**: School information intelligent retrieval system
- **Role**: Administrator configuration and management of crawler jobs
- **Integration point**: Existing Admin UI with "爬虫配置" (Crawler Config) tab

## Requirements
### Functional Requirements
1. **Crawl mode switching**: Support full crawl (unlimited pages) and incremental crawl (first page only)
2. **Batch operations**: 
   - Batch delete multiple configurations
   - Batch start with navigation import from homepage
3. **Navigation import**: Parse BIPT homepage navigation structure and create configs in batch
4. **Real-time monitoring**: Show crawl status, progress bars, and auto-refresh every 2s
5. **Auto-interval scheduling**: Configurable intervals (4/8/12/24 hours)
6. **Configuration management**: Add/edit/delete/reset/toggle configurations
7. **Progress tracking**: Visual indicators for each config's crawl progress

### Non-Functional Requirements
- Responsive design with mobile support
- Input validation and security checks
- Error handling with user-friendly messages
- Real-time status updates without page reload

## Architecture

### Backend (FastAPI)
- **API Router**: `/api/crawl-configs` (prefix registered in `main.py`)
- **Database**: SQLite via SQLModel, separate `crawl.db` for crawler data
- **Navigation**: `services/crawler.py` provides `parse_homepage_navigation()` and `crawl_homepage_navigation()`

### Key API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/crawl-configs` | List all configs |
| POST | `/api/crawl-configs` | Create config |
| GET | `/api/crawl-configs/{id}` | Get single config |
| PUT | `/api/crawl-configs/{id}` | Update config |
| PUT | `/api/crawl-configs/{id}/toggle` | Enable/disable |
| POST | `/api/crawl-configs/batch` | Batch create from navigation |
| POST | `/api/crawl-configs/start` | Start crawl task |
| DELETE | `/api/crawl-configs/{id}` | Delete config |
| GET | `/api/crawl-configs/navigation` | Get homepage navigation structure |
| POST | `/api/admin/crawl/configs/batch` | Admin batch create |

### Frontend Components
- **`SpiderConfigManager.vue`**: Main component with all management features
- **`CrawlerTab.vue`**: Admin tab integration, includes "从首页导入导航" button
- **`SpiderConfigPage.vue`**: Standalone page entry point

## Data Model
```python
class CrawlConfig(SQLModel):
    id: str (UUID, primary key)
    name: str
    url: str
    category: Optional[str]
    parent_category: Optional[str]  # 大类
    sub_category: Optional[str]    # 小类
    selector: str = "body"          # 正文选择器
    is_list_page: bool = True       # 是否为列表页
    article_selector: str = "a"     # 文章链接选择器
    link_prefix: Optional[str]      # 链接前缀
    pagination_selector: str = ""   # 分页选择器
    pagination_max: int = 0         # 0=不限制, 1=仅第一页
    enabled: bool = True
    initialized: bool = False       # 是否已完成首次全量爬取
    auto_interval_hours: int = 0    # 自动爬取间隔
```

## Crawl Mode Logic
- **Full mode**: `pagination_max = 0` (用户可设其他值), 不限制抓取页数
- **Incremental mode**: `pagination_max = 1`, 只抓取第一页新内容
- 模式切换通过 `PUT /api/crawl-configs/{id}` 更新 `initialized` 字段并可重置 `pagination_max`

## Navigation Import Flow
1. 用户点击 "从首页导入导航"
2. 前端调用 `GET /api/crawl-configs/navigation`
3. 后端调用 `services/crawler.parse_homepage_navigation()` 解析 `#nav > li`
4. 返回结构: `[{"parent": "大类", "subs": [{"name": "小类", "url": "..."}]}]`
5. 前端批量创建配置: `POST /api/admin/crawl/configs/batch`
6. 每个 sub 创建一条配置: `parent_category=parent, sub_category=name, url=url`

## UI Components

### Toolbar
- 全选/取消全选 checkbox
- 已选择 N 项计数
- 批量删除按钮
- 批量开始按钮 (调用 batch endpoint)
- 状态徽章: 运行中/空闲 (带脉冲动画)

### Crawl Mode Switch
- 全量爬取 / 增量爬取 radio group
- 根据模式自动调整默认配置:
  - 全量: `pagination_max = 0`
  - 增量: `pagination_max = 1`

### Configuration Table
列: 名称 | 大类 | 小类 | 分类 | 模式 | 自动间隔 | 进度 | 状态 | 上次爬取 | 操作
- 进度列: 显示页数/文章数百分比条
- 状态列: 启用/禁用 badge
- 操作列: 开始/暂停/停止/重置/删除 (根据当前状态变化)

### Add Config Form
基础:
- 名称 (必填)
- URL (必填, URL 格式验证)
- 分类 / 大类 / 小类
- 是否为列表页 (switch)

高级 (可展开):
- 文章选择器 (仅列表页, 必填)
- 链接前缀
- 分页选择器
- 最大页数
- 内容 CSS 选择器

### Batch Operation Confirm Dialogs
- 批量删除: 确认删除 N 个配置
- 批量开始: 确认从选中配置创建 N 个任务

## Real-time Monitoring
- 前端每 2 秒轮询:
  - `GET /api/crawl-configs/status` - 所有配置状态
  - `GET /api/crawl-configs/progress` - 详细进度
- WebSocket 备选方案 (未来可扩展)
- 进度条平滑更新动画

## Security Considerations
- URL 格式验证 (仅允许 http/https)
- CSS 选择器 XSS 检查 (禁止 script/javascript/on* 等)
- 批量操作二次确认
- 管理员权限控制 (JWT + RBAC)
- SQL 注入防护 (SQLModel 参数化)

## Error Handling
- 网络错误: 自动重试 + 提示
- API 错误: 显示具体错误信息
- 表单验证: 实时字段校验
- 爬虫异常: 记录日志 + 前端提示

## Future Enhancements
- 代理配置 per config
- 爬取速率限制
- 邮件/钉钉通知
- 历史记录对比
- 导出/导入配置 (JSON)
- 更复杂的导航解析规则