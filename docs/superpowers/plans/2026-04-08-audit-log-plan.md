# 操作审计日志实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 记录管理员关键操作（文档删除、配置变更、爬取触发等）到审计日志，供管理员查看。

**Architecture:**
- `backend/models/audit_log.py` — AuditLog 模型
- `backend/database.py` — 注册 AuditLog 到 create_db_and_tables
- `backend/services/audit.py` — `add_audit_log(user_id, username, action, target, detail)` 函数
- `backend/api/admin.py` — 在各操作处调用 add_audit_log；新增 `GET /admin/audit` 端点
- `frontend/src/components/admin/AuditTab.vue` — 新建，审计日志 tab
- `frontend/src/views/Admin.vue` — 注册 AuditTab tab

---

## File Map

```
backend/models/audit_log.py   — 新建，AuditLog 模型
backend/database.py           — 修改，注册 AuditLog
backend/services/audit.py      — 新建，add_audit_log 服务函数
backend/api/admin.py          — 修改，在操作处调用 add_audit_log，新增 API
frontend/src/components/admin/AuditTab.vue — 新建，审计日志 UI
frontend/src/views/Admin.vue   — 修改，注册 AuditTab tab
```

---

## Task 1: 创建 AuditLog 模型

**Files:**
- Create: `backend/models/audit_log.py`

```python
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone
import uuid

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_id: str
    username: str
    action: str                    # "delete_doc", "batch_delete_docs", "add_config", "delete_config", "toggle_config", "trigger_crawl", "stop_crawl", "approve_category", "update_category", "reset_password", "create_invite"
    target: Optional[str] = None  # 操作的靶标，如文档 ID、配置 ID
    detail: Optional[str] = None  # 额外描述，如 "删除了 5 个文档"
    created_at: str = Field(default_factory=_now)
```

- [ ] **Step 1: 创建 audit_log.py 模型**
- [ ] **Step 2: 更新 database.py 注册 AuditLog**
- [ ] **Step 3: 提交**
- [ ] **Step 4: spec compliance review**
- [ ] **Step 5: code quality review**

---

## Task 2: 创建 audit 服务函数

**Files:**
- Create: `backend/services/audit.py`

```python
from database import get_session
from models.audit_log import AuditLog
from sqlmodel import Session

def add_audit_log(user_id: str, username: str, action: str, target: str = None, detail: str = None, session: Session = None):
    """记录审计日志"""
    def _write(sess):
        log = AuditLog(user_id=user_id, username=username, action=action, target=target, detail=detail)
        sess.add(log)
        sess.commit()

    if session:
        _write(session)
    else:
        with Session(engine) as sess:
            _write(sess)
```

- [ ] **Step 1: 创建 audit.py 服务**
- [ ] **Step 2: 提交**
- [ ] **Step 3: spec compliance review**
- [ ] **Step 4: code quality review**

---

## Task 3: admin.py 集成审计日志

**Files:**
- Modify: `backend/api/admin.py`

### 3a. 导入 add_audit_log

```python
from services.audit import add_audit_log
```

### 3b. 在各操作处调用 add_audit_log

**删除文档 `delete_document`** — 在 `session.delete(doc); session.commit()` 之前添加：
```python
add_audit_log(current_admin.id, current_admin.username, "delete_doc", doc_id, f"删除文档: {doc.title[:30]}", session)
```

**批量删除文档 `batch_delete_documents`** — 在 `session.commit()` 之后：
```python
add_audit_log(current_admin.id, current_admin.username, "batch_delete_docs", None, f"批量删除 {len(doc_ids)} 个文档", session)
```

**添加配置 `add_crawl_config` (via POST /admin/configs)** — 在 `session.add(config); session.commit()` 之后：
```python
add_audit_log(current_admin.id, current_admin.username, "add_config", config.id, f"添加配置: {config.name}", session)
```

**删除配置 `delete_crawl_config`** — 在 `session.delete(config); session.commit()` 之后：
```python
add_audit_log(current_admin.id, current_admin.username, "delete_config", config_id, f"删除配置: {config.name}", session)
```

**切换配置 `toggle_config`** — 在 `session.commit()` 之后：
```python
add_audit_log(current_admin.id, current_admin.username, "toggle_config", config_id, f"{'启用' if enabled else '禁用'}配置: {config.name}", session)
```

**触发爬取 `trigger_crawl`** — 在 `thread.start()` 之后：
```python
add_audit_log(current_admin.id, current_admin.username, "trigger_crawl", None, "手动触发爬取", session)
```

**停止爬取 `stop_crawl`** — 在 `request_crawl_stop()` 之后：
```python
add_audit_log(current_admin.id, current_admin.username, "stop_crawl", None, "请求停止爬取", session)
```

**采纳AI分类 `approve_document_category`** — 在 `session.commit()` 之后：
```python
add_audit_log(current_admin.id, current_admin.username, "approve_category", doc_id, f"采纳AI分类: {target}", session)
```

**手动修改分类 `update_document_category`** — 在 `session.commit()` 之后：
```python
add_audit_log(current_admin.id, current_admin.username, "update_category", doc_id, f"手动分类: {category}", session)
```

**管理员重置密码 `reset_user_password`** — 在 `session.commit()` 之后：
```python
add_audit_log(current_admin.id, current_admin.username, "reset_password", user_id, f"重置用户 {user.username} 的密码", session)
```

**生成邀请码 `create_invite_code`** — 在 `session.commit()` 之后：
```python
add_audit_log(current_admin.id, current_admin.username, "create_invite", invite_code, f"为 {username} 生成邀请码", session)
```

### 3c. 新增审计日志 API

```python
@router.get("/audit")
def list_audit_logs(
    page: int = 1,
    page_size: int = 50,
    action: Optional[str] = None,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """获取审计日志"""
    count_query = select(func.count()).select_from(AuditLog)
    if action:
        count_query = count_query.where(AuditLog.action == action)
    total = session.exec(count_query).one()

    query = select(AuditLog)
    if action:
        query = query.where(AuditLog.action == action)
    query = query.order_by(AuditLog.created_at.desc())
    logs = session.exec(query.offset((page - 1) * page_size).limit(page_size)).all()

    return {
        "logs": [
            {
                "id": log.id,
                "username": log.username,
                "action": log.action,
                "target": log.target or "",
                "detail": log.detail or "",
                "created_at": log.created_at,
            }
            for log in logs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
```

- [ ] **Step 1: 在 admin.py 中集成审计日志**
- [ ] **Step 2: 提交**
- [ ] **Step 3: spec compliance review**
- [ ] **Step 4: code quality review**

---

## Task 4: 创建 AuditTab.vue

**Files:**
- Create: `frontend/src/components/admin/AuditTab.vue`

模板结构参考 UsersTab 和 DocsTab：

```html
<template>
  <div class="tab-content">
    <div class="section-toolbar">
      <h2 class="section-title">操作审计</h2>
    </div>
    <div class="card">
      <table class="data-table">
        <thead>
          <tr>
            <th>时间</th>
            <th>用户</th>
            <th>操作</th>
            <th>详情</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="log in logs" :key="log.id">
            <td class="cell-muted">{{ log.created_at?.slice(0, 16) }}</td>
            <td>{{ log.username }}</td>
            <td><span class="badge badge-muted">{{ actionLabel(log.action) }}</span></td>
            <td class="cell-muted">{{ log.detail || '—' }}</td>
          </tr>
          <tr v-if="logs.length === 0">
            <td colspan="4" class="cell-empty">暂无日志</td>
          </tr>
        </tbody>
      </table>
      <div v-if="totalPages > 1" class="pagination">
        <button @click="page--; loadLogs()" :disabled="page <= 1" class="btn-outline btn-sm">上一页</button>
        <span class="page-indicator">第 {{ page }} / {{ totalPages }} 页</span>
        <button @click="page++; loadLogs()" :disabled="page >= totalPages" class="btn-outline btn-sm">下一页</button>
      </div>
    </div>
  </div>
</template>
```

Script: `ref` for logs, total, page, pageSize, loading; `loadLogs()` calling `GET /admin/audit`; `actionLabel()` mapping action codes to Chinese labels; `onMounted(() => loadLogs())`; `watch(() => props.tab)` to reload when tab active.

样式: 复用 `tab-content`, `section-toolbar`, `section-title`, `card`, `card-title`, `data-table`, `badge`, `badge-muted`, `cell-muted`, `cell-empty`, `pagination`, `page-indicator`, `btn-outline`, `btn-sm`.

Action label mapping:
```javascript
const actionLabel = (action) => ({
  delete_doc: '删除文档',
  batch_delete_docs: '批量删除',
  add_config: '添加配置',
  delete_config: '删除配置',
  toggle_config: '切换配置',
  trigger_crawl: '触发爬取',
  stop_crawl: '停止爬取',
  approve_category: '采纳AI',
  update_category: '修改分类',
  reset_password: '重置密码',
  create_invite: '生成邀请码',
}[action] || action)
```

- [ ] **Step 1: 创建 AuditTab.vue**
- [ ] **Step 2: 提交**
- [ ] **Step 3: spec compliance review**
- [ ] **Step 4: code quality review**

---

## Task 5: Admin.vue 注册 AuditTab

**Files:**
- Modify: `frontend/src/views/Admin.vue`

1. 导入 AuditTab: `import AuditTab from '../components/admin/AuditTab.vue'`
2. 在 `tabComponents` 中添加: `{ audit: AuditTab }`
3. 在 `tabs` 数组中添加: `{ key: 'audit', label: '审计日志' }`
4. `<component :is="currentTabComponent" :tab="tab" />` 不需要修改（已经动态）

- [ ] **Step 1: 注册 AuditTab 到 Admin.vue**
- [ ] **Step 2: 提交**
- [ ] **Step 3: spec compliance review**
- [ ] **Step 4: code quality review**

---

## 验证步骤

1. 触发爬取，检查审计日志出现 "触发爬取" 记录
2. 添加一个配置，检查审计日志
3. 删除一个文档，检查审计日志
4. 切换到审计 tab，确认列表正确显示
5. 翻页确认分页正常

---

## 完成后

- [ ] 更新 `docs/opencode/task.md`：F2 从"MEDIUM"改为"✅"
- [ ] 提交: `git add docs/opencode/task.md && git commit -m "docs: mark F2 complete in task.md"`
