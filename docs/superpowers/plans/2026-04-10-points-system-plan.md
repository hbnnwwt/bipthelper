# 积分系统实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现积分系统（注册+10 / 每日签到+5 / 问答-1），含数据模型、API、前端展示。

**Architecture:** `User.points` 存余额，`PointRecord` 存明细，`send_message` 中先扣积分再调用 RAG。

**Tech Stack:** FastAPI + SQLModel + SQLite + Vue 3

---

## 文件变更总览

| 操作 | 文件 |
|------|------|
| Create | `backend/models/point_record.py` |
| Modify | `backend/models/user.py` — 新增 `points`、`last_checkin_date` 字段 |
| Modify | `backend/models/__init__.py` |
| Modify | `backend/database.py` — 添加 PointRecord 导入 |
| Modify | `backend/main.py` — 挂载 points router |
| Modify | `backend/api/auth.py` — 注册 +10、GET /me 附加 points |
| Modify | `backend/api/chat.py` — 问答 -1 |
| Modify | `backend/api/admin.py` — GET/PATCH /admin/users/{id}/points |
| Create | `backend/api/points.py` — POST /checkin、GET /records，挂在 /api/points |
| Create | `frontend/src/views/Points.vue` — 独立积分页 |
| Modify | `frontend/src/stores/auth.js` — points 加入 state |
| Modify | `frontend/src/components/layout/AppNavbar.vue` — 积分徽章 |
| Modify | `frontend/src/views/Profile.vue` — 积分概览卡片 |
| Modify | `frontend/src/router/index.js` — 添加 /points 路由 |

---

## Task 1: 数据模型

**Files:**
- Create: `backend/models/point_record.py`
- Modify: `backend/models/user.py`
- Modify: `backend/models/__init__.py`
- Modify: `backend/database.py`

- [ ] **Step 1: 创建 `backend/models/point_record.py`**

```python
from sqlmodel import SQLModel, Field
from datetime import datetime, timezone
import uuid

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

class PointRecord(SQLModel, table=True):
    __tablename__ = "point_records"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_id: str = Field(index=True)
    amount: int  # 正=收入，负=消耗
    type: str    # "register" | "checkin" | "qa" | "admin_set"
    note: str = Field(default="")
    created_at: str = Field(default_factory=_now)
```

- [ ] **Step 2: 更新 `backend/models/__init__.py`**

添加导出：
```python
from .point_record import PointRecord
__all__ = [..., "PointRecord"]
```

- [ ] **Step 3: 修改 `backend/models/user.py`**

在 `User` 类中添加两个字段：

```python
points: int = Field(default=0)
last_checkin_date: Optional[str] = Field(default=None)  # "YYYY-MM-DD" UTC
```

- [ ] **Step 4: 验证 `database.py` 导入 PointRecord**

确认 `backend/database.py` 中已有：
```python
from models.point_record import PointRecord
```
（如果缺少则添加）

- [ ] **Step 5: Commit**

```bash
git add backend/models/point_record.py backend/models/__init__.py backend/models/user.py backend/database.py
git commit -m "feat(points): add PointRecord model and User.points field"
```

---

## Task 2: 注册送积分（auth.py）

**Files:**
- Modify: `backend/api/auth.py`

- [ ] **Step 1: 修改 `register()` 函数**

在 `# 7. 生成 token` 注释上方，添加积分逻辑（在 `session.refresh(new_user)` 之后）：

```python
    # 7. 写入注册积分记录
    register_record = PointRecord(
        user_id=new_user.id,
        amount=10,
        type="register",
        note="注册激活",
    )
    session.add(register_record)
    # points 字段在 User 模型中默认为 0，这里直接 +10
    new_user.points = 10
    session.add(new_user)
    session.commit()

    # 8. 生成 token
```

（注意：原有 `session.commit()` 在注册积分写入之后执行，所以注册积分和用户创建在同一个事务中）

- [ ] **Step 2: Commit**

```bash
git add backend/api/auth.py
git commit -m "feat(points): award 10 points on user registration"
```

---

## Task 3: 积分不足拦截（chat.py）

**Files:**
- Modify: `backend/api/chat.py`

- [ ] **Step 1: 添加 import**

在 `backend/api/chat.py` 顶部 import 区域添加：
```python
from models.point_record import PointRecord
```

- [ ] **Step 2: 修改 `send_message()` 函数**

在 `user_content` 校验之后、`session.add(user_msg)` 之前，添加积分扣减：

```python
    # 保存用户消息
    user_msg = ChatMessage(...)

    # 积分不足拦截（先扣再调用 RAG）
    if current_user.points < 1:
        raise HTTPException(status_code=403, detail="积分不足，无法提问")
    current_user.points -= 1
    qa_record = PointRecord(
        user_id=current_user.id,
        amount=-1,
        type="qa",
        note="问答消耗",
    )
    session.add(qa_record)
    session.add(current_user)
    session.commit()
```

- [ ] **Step 3: Commit**

```bash
git add backend/api/chat.py
git commit -m "feat(points): deduct 1 point before each Q&A"
```

---

## Task 4: User API + Admin API

**Files:**
- Create: `backend/api/points.py`
- Modify: `backend/api/admin.py`
- Modify: `backend/api/auth.py`（GET /me 变更）

- [ ] **Step 1: 创建 `backend/api/points.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel
from datetime import datetime, timezone

from database import get_session
from models.user import User
from models.point_record import PointRecord
from services.auth import get_current_user_from_cookie

router = APIRouter()

@router.post("/checkin")
def checkin(
    current_user: User = Depends(get_current_user_from_cookie),
    session: Session = Depends(get_session),
):
    """每日签到"""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if current_user.last_checkin_date == today:
        raise HTTPException(status_code=400, detail="今日已签到")

    current_user.points += 5
    current_user.last_checkin_date = today
    record = PointRecord(
        user_id=current_user.id,
        amount=5,
        type="checkin",
        note="每日签到",
    )
    session.add(record)
    session.add(current_user)
    session.commit()

    return {
        "points": current_user.points,
        "checked_in_today": True,
        "earned": 5,
    }

class PointRecordResponse(BaseModel):
    id: str
    amount: int
    type: str
    note: str
    created_at: str

class PaginatedRecords(BaseModel):
    records: list[PointRecordResponse]
    total: int
    page: int
    page_size: int

@router.get("/records", response_model=PaginatedRecords)
def list_records(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user_from_cookie),
    session: Session = Depends(get_session),
):
    """积分明细（当前用户）"""
    offset = (page - 1) * page_size
    query = (
        select(PointRecord)
        .where(PointRecord.user_id == current_user.id)
        .order_by(PointRecord.created_at.desc())
    )
    total = session.exec(select(PointRecord).where(PointRecord.user_id == current_user.id)).count()
    records = session.exec(query.offset(offset).limit(page_size)).all()
    return {
        "records": [
            {
                "id": r.id,
                "amount": r.amount,
                "type": r.type,
                "note": r.note,
                "created_at": r.created_at,
            }
            for r in records
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
```

- [ ] **Step 2: 修改 `backend/api/auth.py` 中 GET /me**

修改 `get_me` 函数，在返回中附加 `points` 和 `last_checkin_date`：

```python
@router.get("/me")
def get_me(current_user: User = Depends(get_current_user_from_cookie)):
    return {
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "role": current_user.role
        },
        "points": current_user.points,
        "last_checkin_date": current_user.last_checkin_date,
    }
```

- [ ] **Step 3: 修改 `backend/api/admin.py` — 添加积分管理接口**

在 `backend/api/admin.py` 顶部添加 import：
```python
from models.point_record import PointRecord
```

在文件末尾添加两个新 endpoint：

```python
@router.get("/users/{user_id}/points")
def get_user_points(
    user_id: str,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """查看指定用户积分"""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {
        "user_id": user.id,
        "username": user.username,
        "points": user.points,
        "last_checkin_date": user.last_checkin_date,
    }

@router.patch("/users/{user_id}/points")
def patch_user_points(
    user_id: str,
    delta: int | None = None,
    set_value: int | None = None,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """修改用户积分（delta 或 set）"""
    if delta is None and set_value is None:
        raise HTTPException(status_code=400, detail="必须提供 delta 或 set")
    if delta is not None and set_value is not None:
        raise HTTPException(status_code=400, detail="delta 和 set 不可同时提供")

    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    old_points = user.points
    if set_value is not None:
        user.points = set_value
    else:
        user.points += delta

    record = PointRecord(
        user_id=user.id,
        amount=user.points - old_points,
        type="admin_set",
        note=f"Admin {current_admin.username} 修改",
    )
    session.add(user)
    session.add(record)
    session.commit()

    return {
        "user_id": user.id,
        "username": user.username,
        "old_points": old_points,
        "new_points": user.points,
        "changed_by": current_admin.username,
    }
```

（注意：`Body(...)` 在 PATCH 中用 query param 更简洁，这里用 `delta: int | None = None` 和 `set_value: int | None = None` 作为 query 参数）

- [ ] **Step 4: 在 `backend/main.py` 挂载 points 路由**

在 `backend/main.py` 中添加：
```python
from api.points import router as points_router
app.include_router(points_router, prefix="/api/points", tags=["points"])
```

- [ ] **Step 5: Commit**

```bash
git add backend/api/points.py backend/api/auth.py backend/api/admin.py backend/main.py
git commit -m "feat(points): add checkin, records, admin points APIs"
```

---

## Task 5: 前端 — 路由和状态

**Files:**
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/stores/auth.js`
- Modify: `frontend/src/api/index.js`（如果需要添加 points API）

- [ ] **Step 1: 添加 `/points` 路由**

在 `frontend/src/router/index.js` 中添加：
```js
{
  path: '/points',
  name: 'Points',
  component: () => import('../views/Points.vue'),
  meta: { requiresAuth: true },
}
```

- [ ] **Step 2: 修改 `frontend/src/stores/auth.js`**

在 state 中添加 `points` 和 `last_checkin_date`：
```js
points: 0,
lastCheckinDate: null,
```

在 `setAuth` 中保留这两个字段：
```js
setAuth(token, user, points = 0, lastCheckinDate = null) { ... }
```

在 `fetchUserInfo()`（如果有）中从 `/auth/me` 响应解析 `points` 和 `last_checkin_date`。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/router/index.js frontend/src/stores/auth.js
git commit -m "feat(points): add /points route and auth store points state"
```

---

## Task 6: 前端 — 独立积分页 Points.vue

**Files:**
- Create: `frontend/src/views/Points.vue`

- [ ] **Step 1: 创建 `frontend/src/views/Points.vue`**

功能清单：
- 顶部：积分余额大字显示 + 签到按钮
- 今日状态提示（已签到 / 未签到）
- 下方：积分明细列表（type 标签 / amount / note / 时间）

```vue
<template>
  <div class="points-page">
    <div class="points-hero">
      <div class="balance-card">
        <span class="balance-label">积分余额</span>
        <span class="balance-num">{{ points }}</span>
      </div>
      <button
        class="btn-checkin"
        :disabled="checkedInToday || checkingIn"
        @click="doCheckin"
      >
        {{ checkingIn ? '签到中...' : checkedInToday ? '今日已签到' : '每日签到 +5' }}
      </button>
    </div>

    <div class="records-section">
      <h3 class="section-title">积分明细</h3>
      <div class="record-list">
        <div v-for="r in records" :key="r.id" class="record-item">
          <div class="record-left">
            <span class="type-badge" :class="'type-' + r.type">
              {{ typeLabel(r.type) }}
            </span>
            <span class="record-note">{{ r.note }}</span>
          </div>
          <div class="record-right">
            <span class="amount" :class="r.amount > 0 ? 'pos' : 'neg'">
              {{ r.amount > 0 ? '+' : '' }}{{ r.amount }}
            </span>
            <span class="record-time">{{ formatTime(r.created_at) }}</span>
          </div>
        </div>
        <div v-if="records.length === 0" class="empty">暂无积分记录</div>
      </div>
      <button v-if="hasMore" class="btn-more" @click="loadMore">加载更多</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import api from '../api'

const auth = useAuthStore()
const points = ref(auth.points || 0)
const checkedInToday = ref(auth.lastCheckinDate === todayStr())
const checkingIn = ref(false)
const records = ref([])
const page = ref(1)
const hasMore = ref(false)

function todayStr() {
  return new Date().toISOString().slice(0, 10)
}

function typeLabel(type) {
  return { register: '注册', checkin: '签到', qa: '问答', admin_set: '管理员' }[type] || type
}

function formatTime(iso) {
  return new Date(iso).toLocaleString('zh-CN', { timeZone: 'UTC' })
}

async function loadRecords(p = 1) {
  const { data } = await api.get(`/points/records?page=${p}&page_size=20`)
  if (p === 1) records.value = data.records
  else records.value.push(...data.records)
  hasMore.value = records.value.length < data.total
  page.value = p
}

async function doCheckin() {
  checkingIn.value = true
  try {
    const { data } = await api.post('/points/checkin')
    points.value = data.points
    checkedInToday.value = true
    auth.points = data.points
    auth.lastCheckinDate = todayStr()
    await loadRecords(1)
  } catch (e) {
    alert(e.response?.data?.detail || '签到失败')
  } finally {
    checkingIn.value = false
  }
}

onMounted(() => loadRecords(1))
</script>

<style scoped>
.points-page { max-width: 640px; margin: 0 auto; padding: var(--space-6); display: flex; flex-direction: column; gap: var(--space-6); }
.points-hero { display: flex; align-items: center; justify-content: space-between; padding: var(--space-5); background: var(--color-surface); border-radius: var(--radius-xl); border: 1px solid var(--color-border); }
.balance-card { display: flex; flex-direction: column; gap: 4px; }
.balance-label { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--color-text-muted); font-weight: 600; }
.balance-num { font-size: 2.5rem; font-weight: 700; letter-spacing: -0.04em; color: var(--color-text); line-height: 1; }
.btn-checkin { padding: 0.625rem 1.25rem; background: var(--color-primary); color: white; border: none; border-radius: var(--radius-lg); font-size: 0.9375rem; font-weight: 600; cursor: pointer; }
.btn-checkin:disabled { opacity: 0.5; cursor: not-allowed; }
.section-title { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--color-text-muted); font-weight: 600; margin-bottom: var(--space-3); }
.record-list { display: flex; flex-direction: column; gap: 1px; background: var(--color-border); border-radius: var(--radius-lg); overflow: hidden; }
.record-item { display: flex; justify-content: space-between; align-items: center; padding: var(--space-3) var(--space-4); background: var(--color-surface); }
.record-left { display: flex; align-items: center; gap: var(--space-3); }
.type-badge { font-size: 0.75rem; font-weight: 600; padding: 2px 8px; border-radius: 999px; }
.type-register { background: rgba(34,197,94,0.1); color: #16a34a; }
.type-checkin { background: rgba(59,130,246,0.1); color: #2563eb; }
.type-qa { background: rgba(156,163,175,0.2); color: #6b7280; }
.type-admin_set { background: rgba(168,85,247,0.1); color: #7c3aed; }
.record-note { font-size: 0.875rem; color: var(--color-text-secondary); }
.record-right { display: flex; flex-direction: column; align-items: flex-end; gap: 2px; }
.amount { font-weight: 700; font-size: 0.9375rem; }
.amount.pos { color: #16a34a; }
.amount.neg { color: #dc2626; }
.record-time { font-size: 0.75rem; color: var(--color-text-faint); }
.empty { padding: var(--space-8); text-align: center; color: var(--color-text-faint); font-size: 0.875rem; }
.btn-more { width: 100%; padding: var(--space-3); background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); font-size: 0.875rem; color: var(--color-text-secondary); cursor: pointer; }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/views/Points.vue
git commit -m "feat(points): add Points.vue page with checkin and records"
```

---

## Task 7: 前端 — 导航栏积分徽章 + 个人中心积分卡片

**Files:**
- Modify: `frontend/src/components/layout/AppNavbar.vue`
- Modify: `frontend/src/views/Profile.vue`

- [ ] **Step 1: 在导航栏添加积分徽章**

在导航栏右侧（用户名旁边或下拉菜单中）添加积分显示，例如在用户下拉菜单中添加：
```html
<div class="points-badge">
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
  {{ auth.points }} 积分
</div>
```

如果 AppNavbar.vue 不存在，先找到正确的导航栏文件：
```bash
grep -r "navbar\|NavBar\|nav-bar" frontend/src --include="*.vue" -l
```

- [ ] **Step 2: 在 `Profile.vue` 添加积分概览卡片**

在个人中心页面（`frontend/src/views/Profile.vue`）中找到合适位置，添加积分卡片：
```html
<div class="points-overview-card">
  <div class="po-header">
    <span>积分</span>
    <router-link to="/points" class="po-link">明细 →</router-link>
  </div>
  <div class="po-balance">{{ auth.points }}</div>
  <button
    v-if="auth.lastCheckinDate !== todayStr()"
    class="btn-checkin-sm"
    @click="quickCheckin"
  >
    每日签到 +5
  </button>
  <div v-else class="po-checkin-done">今日已签到</div>
</div>
```

对应的 JS：
```js
function todayStr() { return new Date().toISOString().slice(0, 10) }
async function quickCheckin() {
  const { data } = await api.post('/points/checkin')
  auth.points = data.points
  auth.lastCheckinDate = todayStr()
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/layout/AppNavbar.vue frontend/src/views/Profile.vue
git commit -m "feat(points): add points badge to navbar and profile card"
```

---

## 自检清单

1. **Spec 覆盖**：每条 spec 要点都有对应 task？
   - [x] PointRecord 模型创建
   - [x] User.points / last_checkin_date 字段
   - [x] 注册激活 +10（写入 PointRecord）
   - [x] 每日签到 +5（checkin API）
   - [x] 问答 -1（send_message 中拦截）
   - [x] 积分不足 403
   - [x] GET /points/records（分页）
   - [x] GET /auth/me 附加 points
   - [x] Admin GET/PATCH /admin/users/{id}/points
   - [x] 前端独立积分页 /points
   - [x] 前端导航栏积分徽章
   - [x] 前端个人中心积分卡片

2. **placeholder 扫描**：无 TBD/TODO/implement later 等占位符

3. **类型一致性**：
   - `PointRecord.type` 值：register / checkin / qa / admin_set（Task 1-4 一致）
   - `amount`：正数=收入，负数=消耗（Task 1-4 一致）
   - `last_checkin_date`："YYYY-MM-DD" UTC 格式（Task 1, 2, 4 一致）

4. **依赖顺序**：Task 1 → Task 2+3+4 → Task 5+6+7（后端先完成再改前端）

5. **API 路由 mount**：确认 `points.py` 路由被挂载到正确路径（检查 `backend/main.py` 中是否有 `api/points.py` 的 router 注册）
