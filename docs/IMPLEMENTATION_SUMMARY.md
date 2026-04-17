# Spider Configuration Management Implementation

## Overview
This implementation adds a comprehensive spider configuration management page with crawl mode switching (full vs incremental) and batch management functionality.

## Features Implemented

### 1. User Interface (Frontend)
**File: `frontend/src/components/SpiderConfigManager.vue`**

- **Batch Operations Panel**: Toolbar for selecting multiple configurations with bulk actions
  - Full selection with checkbox
  - Batch delete
  - Batch start/crawl
  
- **Crawl Mode Switching**: Radio buttons to switch between:
  - **Full Crawl**: Crawls all pages (pagination_max = 0, no limit)
  - **Incremental Crawl**: Only crawls new pages (pagination_max = 1, first page only)
  
- **Configuration Management Table**: 
  - Display all configurations with status
  - Enable/disable toggle
  - Start/pause/stop individual crawls
  - Reset completed configurations
  - Delete configurations
  - Auto-interval scheduling (4h, 8h, 12h, 24h)

- **Add Configuration Form**:
  - Basic settings: name, URL, category, sub_category, parent_category
  - List page mode toggle
  - Advanced options: selectors, pagination, link prefixes
  - CSS selector validation

### 2. Backend API
**File: `backend/api/crawl_config.py`**

- `GET /api/crawl-configs` - List all configurations
- `POST /api/crawl-configs` - Create new configuration
- `GET /api/crawl-configs/{id}` - Get single configuration
- `PUT /api/crawl-configs/{id}` - Update configuration
- `PUT /api/crawl-configs/{id}/toggle` - Enable/disable
- `POST /api/crawl-configs/start` - Start crawl tasks
- `DELETE /api/crawl-configs/{id}` - Delete configuration
- `GET /api/crawl-configs/navigation` - Get navigation structure from homepage
- `POST /api/crawl-configs/batch` - Batch create configurations

### 3. Navigation Import
**File: `frontend/src/components/admin/CrawlerTab.vue`**

- **Import from Homepage**: Fetches navigation structure from `https://info.bipt.edu.cn/`
- Parses the `#nav > li` structure
- Creates individual configurations for each sub-category
- Allows batch creation of configurations

### 4. Integration with Existing System
**File: `backend/main.py`**
- Registered new API routes with `/api/crawl-configs` prefix
- Added "爬虫配置" (Crawler Config) tab to admin interface

### 5. Data Models
**File: `backend/models/crawl_config.py`**
- Extended with `auto_interval_hours` field for scheduling
- Supports incremental vs full crawl mode (`initialized` flag)

## Key Design Decisions

1. **Mode Switching**: The crawl mode is controlled by `pagination_max`:
   - `0` = Unlimited (full crawl)
   - `1` = First page only (incremental)

2. **Batch Operations**: Uses array of IDs for batch actions, allowing flexible multi-selection

3. **State Management**: Real-time status tracking with:
   - Individual config status (running/paused/completed)
   - Global crawl progress
   - Per-config progress bars

4. **Security**: Input validation for:
   - URL format validation
   - CSS selector security (prevent XSS)
   - Batch operation confirmation dialogs

## Usage Flow

1. **Navigate** to Admin → Crawler Config tab
2. **Import Navigation** (optional): Click "从首页导入导航" to auto-create configs
3. **Add New Config**: Fill form with URL, selectors, and settings
4. **Switch Mode**: Use radio buttons to choose full/incremental
5. **Batch Actions**: Select configs → Batch Start or Batch Delete
6. **Monitor**: View real-time progress in status badges and progress bars

## Testing Notes

- All API endpoints return proper HTTP status codes
- Frontend includes proper error handling with toast notifications
- Navigation parsing handles BIPT website structure
- Batch operations work with multiple selected IDs
- Mode switching properly updates configuration defaults

## Future Enhancements

- Add scheduled crawl execution (currently requires manual start)
- Implement detailed error reporting per configuration
- Add configuration import/export (JSON format)
- Support for more complex pagination patterns
- Add proxy rotation settings per configuration