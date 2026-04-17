# Token httpOnly Cookie 迁移计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** 将 JWT token 从 localStorage 迁移到 httpOnly cookie，消除 XSS 风险。登录时后端设置 httpOnly cookie，后续请求自动带上（无需前端手动注入 Authorization header）。

**Architecture:**
- 后端 `login`/`register` 在响应中设置 `access_token` httpOnly cookie
- 新增 `get_current_user_from_cookie` 依赖，优先从 cookie 读取 token
- 前端 `api/index.js` 配置 `withCredentials: true`，不再从 localStorage 读 token
- `OAuth2PasswordBearer` 保留（向后兼容 header 方式）

---

## File Map

```
backend/services/auth.py    — 修改：新增 cookie 读取依赖
backend/api/auth.py        — 修改：login/register 返回 token 为 cookie
backend/main.py            — 修改：CORS 配置允许 credentials
frontend/src/api/index.js  — 修改：移除 Authorization 注入，添加 withCredentials
frontend/src/stores/auth.js — 修改：移除 localStorage token 读写
```

---

## Task 1: 后端 — services/auth.py 新增 cookie 读取

**Files:**
- Modify: `backend/services/auth.py`

新增一个从 cookie 读取 token 的依赖，替代 `OAuth2PasswordBearer` 的 header 读取：

```python
from fastapi import Cookie

def get_current_user_from_cookie(
    access_token: Optional[str] = Cookie(None),
    session: Session = Depends(get_session),
) -> User:
    """从 httpOnly cookie 读取 JWT token 并验证用户"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not access_token:
        raise credentials_exception

    try:
        payload = jwt.decode(access_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = session.exec(select(User).where(User.username == username)).first()
    if user is None or not user.is_active:
        raise credentials_exception
    return user
```

同时保留原有的 `get_current_user`（基于 OAuth2PasswordBearer header）和 `get_current_admin`（复用 `get_current_user`）。

- [ ] **Step 1: 修改 services/auth.py，添加 get_current_user_from_cookie**
- [ ] **Step 2: 提交**
- [ ] **Step 3: spec compliance review**
- [ ] **Step 4: code quality review**

---

## Task 2: 后端 — auth.py login/register 设置 cookie

**Files:**
- Modify: `backend/api/auth.py`

修改 `login` 和 `register` 函数，在返回响应时设置 httpOnly cookie。

**login 函数改动：**

在 `return {"user": {...}, "token": token}` 之前，添加：

```python
from fastapi.responses import JSONResponse

response = JSONResponse({"user": {"id": user.id, "username": user.username, "role": user.role}, "token": token})
response.set_cookie(
    key="access_token",
    value=token,
    httponly=True,
    secure=True,          # HTTPS only in production
    samesite="lax",
    max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    path="/",
)
return response
```

**register 函数改动：**

同样改为 `JSONResponse` 并设置 cookie：

```python
response = JSONResponse({"user": {"id": invite_user.id, "username": invite_user.username, "role": invite_user.role}, "token": token})
response.set_cookie(
    key="access_token",
    value=token,
    httponly=True,
    secure=True,
    samesite="lax",
    max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    path="/",
)
return response
```

**注意**：`register` 函数的 `@router.post("/register")` 仍然是 `def register(...)`，需要把最后的 `return {...}` 改为上面的形式。

- [ ] **Step 1: 修改 login 和 register 设置 httpOnly cookie**
- [ ] **Step 2: 提交**
- [ ] **Step 3: spec compliance review**
- [ ] **Step 4: code quality review**

---

## Task 3: 后端 — main.py CORS credentials

**Files:**
- Modify: `backend/main.py`

找到现有的 CORS 配置，添加 `allow_credentials=True`。

如果现有配置是 `allow_origins=["*"]`，需要改为具体域名列表。

检查 `backend/main.py` 的 CORS 配置，确保：
- `allow_credentials=True`
- `allow_origins` 是具体域名列表（不能是 `*`）

如果需要支持 localhost 开发：
```python
allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"]
```

- [ ] **Step 1: 检查并更新 main.py CORS 配置支持 credentials**
- [ ] **Step 2: 提交**
- [ ] **Step 3: spec compliance review**
- [ ] **Step 4: code quality review**

---

## Task 4: 前端 — api/index.js 移除 header 注入

**Files:**
- Modify: `frontend/src/api/index.js`

移除 token 注入 interceptor，添加 `withCredentials: true`：

```javascript
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  withCredentials: true,  // 发送 cookies 到同源后端
})

// 移除 Authorization header 注入（改用 httpOnly cookie）

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      if (window.location.pathname !== '/login' && window.location.pathname !== '/register') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default api
```

- [ ] **Step 1: 修改 api/index.js，移除 token header 注入，添加 withCredentials**
- [ ] **Step 2: 提交**
- [ ] **Step 3: spec compliance review**
- [ ] **Step 4: code quality review**

---

## Task 5: 前端 — stores/auth.js 移除 token localStorage

**Files:**
- Modify: `frontend/src/stores/auth.js`

移除 `localStorage.getItem('token')` 和 `localStorage.setItem('token', token)` 相关的逻辑。

**关键变更：**
- `login` 响应中的 `token` 字段不再存储到 localStorage（后端已设置 cookie）
- `logout` 函数中移除 `localStorage.removeItem('token')`
- 其他地方对 `localStorage.getItem('token')` 的调用不再需要（因为不再从 localStorage 读 token）

检查 auth.js 中所有对 `token` 的引用并移除 localStorage 相关逻辑。

- [ ] **Step 1: 修改 auth.js，移除 token 的 localStorage 读写**
- [ ] **Step 2: 提交**
- [ ] **Step 3: spec compliance review**
- [ ] **Step 4: code quality review**

---

## 验证步骤

1. 清除浏览器 localStorage 中的 token
2. 登录，检查浏览器 DevTools Application > Cookies 中有 `access_token`（httpOnly）
3. 刷新页面，确认已登录状态正确恢复
4. 搜索文档，确认请求带上 cookie
5. 退出登录，确认 cookie 被清除

---

## 完成后

- [ ] 更新 `docs/opencode/task.md`：L9 从"LOW"改为"✅"
- [ ] 提交: `git add docs/opencode/task.md && git commit -m "docs: mark L9 complete in task.md"`
