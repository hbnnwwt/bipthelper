# 爬虫执行逻辑重构设计

## 问题

### 问题 1：停止时状态不更新
- `crawl_stop_requested` 时，`crawl_list_page` 的循环直接 `break`，没有把当前 config 的 `status` 设为 `"stopped"`
- 调用方（`_crawl_all_impl` / `_crawl_configs_impl`）无法区分"正常完成"和"用户停止"

### 问题 2：crawlSpeed 计算错误
- `crawlSpeed` 依赖全局 `articles_crawled` 计数器
- 多配置爬取时，全局计数器跨配置累加，切换配置时不清零，导致速度显示为负数或跳跃

## 方案

### 1. `crawl_list_page` 返回结构化结果

**当前：**
```python
def crawl_list_page(config, session) -> int:  # 返回新增文章数
```

**改为：**
```python
from dataclasses import dataclass

@dataclass
class CrawlResult:
    articles_crawled: int   # 本次爬取的文章数（含新爬和重复跳过）
    new_articles: int      # 本次新增的文章数
    pages_crawled: int     # 本次爬取的分页数
    stopped: bool          # 是否被用户主动停止

def crawl_list_page(config, session) -> CrawlResult
```

**停止处理：**
当 `crawl_stop_requested` 为 True 时，在 break 前设置 `stopped = True`，并设置当前 config 的 `status = "stopped"`。

**分页计数：**
循环退出时 `pages_crawled = page_count`。

### 2. 调用方状态更新逻辑

`_crawl_all_impl` 和 `_crawl_configs_impl` 中：

```python
result = crawl_list_page(config, session)
# 根据 result.stopped 决定状态
if result.stopped:
    crawl_progress["configs"][i]["status"] = "stopped"
else:
    crawl_progress["configs"][i]["status"] = "done"
```

### 3. 前端速度计算改为 per-config

**删除：** 全局 `crawlSpeed` computed

**新增：** 每个 config 的速度计算

在 `crawlProgress.configs[i]` 中增加两个字段：
```python
{
    "id": "...",
    "name": "...",
    "articles_crawled": 12,
    "articles_crawled_at_start": 0,  # 爬取开始时的文章数（用于计算速度）
    "elapsed_seconds": 0,            # 本配置已耗时
    ...
}
```

前端根据 `articles_crawled - articles_crawled_at_start` 差值计算当前配置的速度。

### 4. crawlProgress 结构调整

```python
crawl_progress = {
    "phase": "idle",        # idle | running | stopping
    "total_configs": 0,
    "configs": [
        {
            "id": "...",
            "name": "...",
            "page": 2,
            "total_pages": 5,
            "articles_crawled": 12,
            "articles_total": 30,
            "articles_crawled_at_start": 0,  # 新增
            "elapsed_seconds": 0,              # 新增
            "status": "running",  # pending | running | done | stopped | error
        }
    ],
    ...
}
```

## 自检

- [ ] 无 Placeholder/TODO
- [ ] `crawl_list_page` 返回类型变化不影响现有调用方（调用方已有结果对象）
- [ ] `stopped` 状态与 `done` 状态不混淆
- [ ] 前端速度计算基于 per-config 而非全局
