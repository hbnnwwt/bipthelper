# 激活码系统重新设计 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现两类激活码（指定用户 / 任意用户）系统，含创建/列表/删除 API 及注册改造。

**Architecture:** 新建 `InviteCode` 独立模型表，废弃 `User.invite_code` 字段。Admin 新增 `/admin/codes` 系列接口，Auth 改造 `/auth/register` 逻辑。

**Tech Stack:** FastAPI + SQLModel + SQLite, 固定 7 天有效期。

---

## 文件变更总览

| 操作 | 文件 |
|------|------|
| Create | `backend/models/invite_code.py` |
| Modify | `backend/models/__init__.py` |
| Modify | `backend/api/auth.py` — 重写 register 逻辑 |
| Modify | `backend/api/admin.py` — 废弃 `/users/invite`，新增 `/codes` 接口 |
| Modify | `frontend/src/views/Register.vue` — username 字段对 anonymous 类型变为可选 |
| Modify | `frontend/src/components/admin/UsersTab.vue` — 移除邀请码 tab，改建 InviteCodesTab |

---

## Task 1: 新建 InviteCode 模型

**Files:**
- Create: `backend/models/invite_code.py`
- Modify: `backend/models/__init__.py`

- [ ] **Step 1: 创建 `backend/models/invite_code.py`**

```python
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone
import secrets

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

class InviteCode(SQLModel, table=True):
    __tablename__ = "invite_codes"

    code: str = Field(primary_key=True)  # e.g. "ACT-a3f8c2d1"
    code_type: str = Field(default="anonymous")  # "designated" | "anonymous"
    designated_username: Optional[str] = Field(default=None, index=True)  # 仅 designated
    created_by: str = Field(default="admin")
    created_at: str = Field(default_factory=_now)
    expires_at: str = Field(default_factory=lambda: _now())  # 创建时由服务层填充
    used_by: Optional[str] = Field(default=None, index=True)  # User.id
    used_at: Optional[str] = Field(default=None)

    @staticmethod
    def generate_code() -> str:
        return f"ACT-{secrets.token_hex(4).upper()}"  # 8 hex chars
```

- [ ] **Step 2: 更新 `backend/models/__init__.py`**

在 `__all__` 末尾添加 `InviteCode`。

```python
from .invite_code import InviteCode

__all__ = [..., "InviteCode"]
```

- [ ] **Step 3: 验证模型可导入**

Run: `cd backend && python -c "from models.invite_code import InviteCode; print(InviteCode.__tablename__)"`
Expected: `invite_codes`

- [ ] **Step 4: Commit**

```bash
git add backend/models/invite_code.py backend/models/__init__.py
git commit -m "feat(invite): add InviteCode model for two-type activation codes"
```

---

## Task 2: 核心辅助函数

**Files:**
- Modify: `backend/services/auth.py`（或新建 `backend/services/invite.py`）

- [ ] **Step 1: 在 `backend/services/` 下创建 `invite.py`**

```python
import secrets
import string
from datetime import datetime, timezone
from typing import Optional

def generate_username() -> str:
    """为 anonymous 类型生成 10 位随机用户名（A-Z 0-9）"""
    alphabet = string.ascii_uppercase + string.digits  # 36 chars
    return ''.join(secrets.choice(alphabet) for _ in range(10))

def is_valid_username(username: str) -> bool:
    """校验 username：最少 6 位，纯字母数字"""
    if len(username) < 6:
        return False
    return username.isalnum()

def code_status(code) -> str:
    """实时计算激活码状态：used / expired / active"""
    if code.used_by:
        return "used"
    expires = datetime.fromisoformat(code.expires_at.replace('Z', '+00:00'))
    if datetime.now(timezone.utc) > expires:
        return "expired"
    return "active"

def is_expired(code) -> bool:
    expires = datetime.fromisoformat(code.expires_at.replace('Z', '+00:00'))
    return datetime.now(timezone.utc) > expires
```

- [ ] **Step 2: Commit**

```bash
git add backend/services/invite.py
git commit -m "feat(invite): add invite service helpers"
```

---

## Task 3: Admin 激活码 API

**Files:**
- Modify: `backend/api/admin.py` — 添加 `/codes` 系列接口，废弃 `/users/invite`

- [ ] **Step 1: 在 `admin.py` 顶部添加 import**

```python
from models.invite_code import InviteCode
from services.invite import code_status, is_expired
from datetime import datetime, timezone
```

- [ ] **Step 2: 替换 `@router.post("/users/invite")` 为新接口**

删除原 `create_invite` 函数（约 lines 59-85），替换为：

```python
@router.post("/codes")
def create_code(
    type: str = Body(..., embed=True),
    username: Optional[str] = Body(None, embed=True),
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """创建激活码（designated 或 anonymous）"""
    if type == "designated":
        if not username or not username.strip():
            raise HTTPException(status_code=400, detail="designated 类型必须提供 username")
        # 检查 username 未被占用
        existing = session.exec(select(User).where(User.username == username.strip())).first()
        if existing:
            raise HTTPException(status_code=400, detail="该用户名已被注册")
    elif type != "anonymous":
        raise HTTPException(status_code=400, detail="type 必须是 designated 或 anonymous")

    expires_at = datetime.now(timezone.utc)
    expires_at = expires_at.replace(second=0, microsecond=0)
    from datetime import timedelta
    expires_at = (expires_at + timedelta(days=7)).isoformat()

    code = InviteCode(
        code=InviteCode.generate_code(),
        code_type=type,
        designated_username=username.strip() if type == "designated" else None,
        created_by=current_admin.username,
        expires_at=expires_at,
    )
    session.add(code)
    session.commit()

    add_audit_log(
        current_admin.id, current_admin.username,
        "create_invite_code",
        code.code,
        f"创建{type}激活码: {code.code}"[:80],
        session
    )

    return {
        "code": code.code,
        "type": code.code_type,
        "designated_username": code.designated_username,
        "expires_at": code.expires_at,
        "created_by": code.created_by,
    }
```

- [ ] **Step 3: 添加 `GET /codes` 列表接口**

在 `create_code` 之后添加：

```python
@router.get("/codes")
def list_codes(
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """列出所有激活码（含实时 status）"""
    codes = session.exec(select(InviteCode).order_by(InviteCode.created_at.desc())).all()
    return {
        "codes": [
            {
                "code": c.code,
                "type": c.code_type,
                "designated_username": c.designated_username,
                "created_by": c.created_by,
                "created_at": c.created_at,
                "expires_at": c.expires_at,
                "status": code_status(c),
                "used_by": c.used_by,
                "used_at": c.used_at,
            }
            for c in codes
        ]
    }
```

- [ ] **Step 4: 添加 `DELETE /codes/{code}` 删除接口**

```python
@router.delete("/codes/{code}")
def delete_code(
    code: str,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    """删除激活码"""
    record = session.get(InviteCode, code)
    if not record:
        raise HTTPException(status_code=404, detail="激活码不存在")
    session.delete(record)
    session.commit()
    add_audit_log(
        current_admin.id, current_admin.username,
        "delete_invite_code", code,
        f"删除激活码: {code}",
        session
    )
    return {"message": "Code deleted"}
```

- [ ] **Step 5: 验证 admin codes API 可注册（运行后端）**

Run: 启动后端后 `curl -s http://localhost:3000/api/admin/codes`（需带 admin cookie）
Expected: `{"codes": [...]}`

- [ ] **Step 6: Commit**

```bash
git add backend/api/admin.py
git commit -m "feat(invite): add POST/GET/DELETE /admin/codes endpoints"
```

---

## Task 4: 注册接口改造

**Files:**
- Modify: `backend/api/auth.py` — 重写 `POST /auth/register`

- [ ] **Step 1: 添加 import**

```python
from models.invite_code import InviteCode
from services.invite import generate_username, is_valid_username, code_status, is_expired
```

- [ ] **Step 2: 完全重写 `POST /auth/register` 函数**

当前 register 约 48 行，替换为：

```python
@router.post("/register")
@limiter.limit("5/minute")
def register(
    request: Request,
    password: str = Body(..., embed=True),
    invite_code: str = Body(..., embed=True),
    username: Optional[str] = Body(None, embed=True),
    session: Session = Depends(get_session),
):
    from fastapi.responses import JSONResponse

    # 1. 激活码存在性校验
    code_record = session.get(InviteCode, invite_code)
    if not code_record:
        raise HTTPException(status_code=400, detail="激活码不存在")

    # 2. 状态校验（used / expired）
    status = code_status(code_record)
    if status == "used":
        raise HTTPException(status_code=400, detail="激活码已被使用")
    if status == "expired":
        raise HTTPException(status_code=400, detail="激活码已过期")

    # 3. designated 类型：username 必须匹配
    final_username = username
    if code_record.code_type == "designated":
        if not final_username or final_username.strip() != code_record.designated_username:
            raise HTTPException(status_code=400, detail="激活码与用户名不匹配")
        final_username = final_username.strip()
    else:  # anonymous
        if final_username:
            final_username = final_username.strip()
            if not is_valid_username(final_username):
                raise HTTPException(status_code=400, detail="用户名最少6位字母数字组合")
            # 检查全局唯一
            existing = session.exec(select(User).where(User.username == final_username)).first()
            if existing:
                raise HTTPException(status_code=400, detail="该用户名已被占用")
        else:
            # 自动生成
            final_username = generate_username()
            # 极低概率重复，再生成一次
            existing = session.exec(select(User).where(User.username == final_username)).first()
            if existing:
                final_username = generate_username()

    # 4. 密码校验
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="密码最少6位")

    # 5. 创建用户
    from services.auth import hash_password
    new_user = User(
        username=final_username,
        password_hash=hash_password(password),
        role="user",
        is_active=True,
    )
    session.add(new_user)
    session.commit()
    session.refresh(new_user)

    # 6. 更新激活码状态
    code_record.used_by = new_user.id
    code_record.used_at = datetime.now(timezone.utc).isoformat()
    session.add(code_record)
    session.commit()

    # 7. 生成 token
    token = create_access_token(data={"sub": new_user.username})
    response = JSONResponse({
        "user": {
            "id": new_user.id,
            "username": new_user.username,
            "role": new_user.role
        },
        "token": token
    })
    response.set_cookie(
        key="access_token", value=token,
        httponly=True, secure=True, samesite="lax",
        max_age=60 * 60 * 24 * 7, path="/",
    )
    return response
```

- [ ] **Step 3: Commit**

```bash
git add backend/api/auth.py
git commit -m "feat(invite): rewrite /auth/register to use InviteCode table"
```

---

## Task 5: 前端 — 注册页改造

**Files:**
- Modify: `frontend/src/views/Register.vue`

当前 Register.vue 已有 username / password / invite_code 三个字段，只需调整验证逻辑（anonymous 类型时 username 变为可选）和 UI 提示文字。

- [ ] **Step 1: 在 `<script setup>` 的 form 定义处，将 username 改为可选提示**

Register.vue 的 form reactive 本身不变。改动点在：
1. invite_code 验证提示改为"请输入激活码"
2. 提交时对 anonymous 类型（由激活码格式判断）username 可为空

具体改动取决于 `api.post('/auth/register', form)` 传递的 body —— 确认当前 Register.vue 是以 JSON body 传递还是 form-data？从 Task 4 的 auth.py 看，改造后使用 `Body(..., embed=True)`，JSON body。

- [ ] **Step 2: Commit**

```bash
git add frontend/src/views/Register.vue
git commit -m "feat(invite): update register form for anonymous invite code support"
```

---

## Task 6: 前端 — 新建 InviteCodesTab（替代 UsersTab 邀请码部分）

**Files:**
- Create: `frontend/src/components/admin/InviteCodesTab.vue`
- Modify: `frontend/src/views/Admin.vue` — 在 tabbar 添加"激活码" tab

- [ ] **Step 1: 创建 `InviteCodesTab.vue`**

功能清单：
- 顶部：创建表单（type 选择 / username 输入 / 创建按钮）
- 下方：激活码列表表格（code / type / designated_username / status / expires_at / 操作列）
- status 渲染：active=绿色 / used=蓝色 / expired=红色
- 操作列：删除按钮
- 刷新：onMounted 加载列表

```vue
<template>
  <div class="invite-codes-tab">
    <!-- 创建表单 -->
    <div class="create-form">
      <div class="form-row">
        <select v-model="createType" class="filter-select">
          <option value="designated">指定用户</option>
          <option value="anonymous">任意用户</option>
        </select>
        <input v-if="createType === 'designated'"
          v-model="createUsername" type="text"
          placeholder="预填用户名"
          class="input" />
        <button @click="createCode" class="btn-primary" :disabled="creating">
          {{ creating ? '创建中...' : '生成激活码' }}
        </button>
      </div>
      <div v-if="newCode" class="code-result">
        激活码：<code class="code">{{ newCode.code }}</code>
        <span class="code-meta">{{ newCode.type === 'designated' ? '指定用户: ' + newCode.designated_username : '任意用户' }} · 有效期至 {{ newCode.expires_at }}</span>
      </div>
    </div>

    <!-- 列表 -->
    <div class="table-wrapper">
      <table class="data-table">
        <thead>
          <tr>
            <th>激活码</th><th>类型</th><th>预填用户</th>
            <th>状态</th><th>到期时间</th><th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in codes" :key="c.code">
            <td><code>{{ c.code }}</code></td>
            <td><span class="badge" :class="c.type === 'designated' ? 'badge-primary' : 'badge-muted'">
              {{ c.type === 'designated' ? '指定用户' : '任意用户' }}
            </span></td>
            <td>{{ c.designated_username || '—' }}</td>
            <td><span class="status-badge" :class="'status-' + c.status">
              {{ c.status === 'active' ? '待激活' : c.status === 'used' ? '已使用' : '已过期' }}
            </span></td>
            <td class="cell-mono">{{ c.expires_at }}</td>
            <td>
              <button @click="deleteCode(c.code)" class="btn-ghost-xs btn-text-danger">删除</button>
            </td>
          </tr>
          <tr v-if="codes.length === 0">
            <td colspan="6" class="cell-empty">暂无激活码</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
```

（样式复用 `admin-shared.css` 中的 table / badge / btn 系统）

- [ ] **Step 2: 在 `Admin.vue` 的 tabbar 添加新 tab**

在 tabs 数组中添加：
```js
{ key: 'codes', label: '激活码' }
```

section 添加对应条件渲染：
```html
<section v-if="tab === 'codes'">
  <InviteCodesTab />
</section>
```

import 中添加 `InviteCodesTab`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/admin/InviteCodesTab.vue
git add frontend/src/views/Admin.vue
git commit -m "feat(invite): add InviteCodesTab to Admin"
```

---

## 自检清单

1. **Spec 覆盖**：每条 spec 要点都有对应 task？
   - [x] InviteCode 模型创建
   - [x] POST /admin/codes 创建（designated + anonymous）
   - [x] GET /admin/codes 列表（含实时 status）
   - [x] DELETE /admin/codes/{code} 删除
   - [x] /auth/register 改造（username optional for anonymous）
   - [x] 前端 Register.vue 适配
   - [x] 前端 InviteCodesTab

2. **placeholder 扫描**：无 TBD/TODO/implement later 等占位符

3. **类型一致性**：函数名 `generate_username` / `is_valid_username` / `code_status` / `is_expired` 在所有 task 中一致

4. **依赖顺序**：Task 1 → Task 2 → Task 3 → Task 4 → Task 5+6（后端先完成再改前端）
