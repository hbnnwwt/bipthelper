# User Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace minimal Profile.vue with a full personal center page, merge Points.vue into it, add sidebar user card entry in Chat.vue, and extend the User model with nickname/phone/avatar.

**Architecture:** Backend-first approach — extend User model, add profile/avatar APIs, mount avatar static files. Then rewrite Profile.vue as a full personal center, update Chat.vue sidebar, update auth store, and redirect /points → /profile.

**Tech Stack:** FastAPI + SQLModel (backend), Vue 3 Composition API + Pinia (frontend), SQLite (DB)

---

### Task 1: Extend User model with nickname, phone, avatar_url fields

**Files:**
- Modify: `backend/models/user.py`

- [ ] **Step 1: Add three new fields to User model**

In `backend/models/user.py`, add after the `last_checkin_date` field (line 20):

```python
    nickname: Optional[str] = Field(default=None)
    phone: Optional[str] = Field(default=None)
    avatar_url: Optional[str] = Field(default=None)
```

The full model should be:

```python
class User(SQLModel, table=True):
    __tablename__ = "users"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    username: str = Field(unique=True, index=True)
    password_hash: str
    role: str = Field(default="user")  # admin or user
    invite_code: Optional[str] = Field(default=None, index=True)
    created_at: str = Field(default_factory=_now)
    is_active: bool = Field(default=True)
    points: int = Field(default=0)
    last_checkin_date: Optional[str] = Field(default=None)  # "YYYY-MM-DD" UTC
    nickname: Optional[str] = Field(default=None)
    phone: Optional[str] = Field(default=None)
    avatar_url: Optional[str] = Field(default=None)
```

- [ ] **Step 2: Verify model loads without error**

Run: `cd backend && python_portable/python.exe -c "from models.user import User; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/models/user.py
git commit -m "feat(user): add nickname, phone, avatar_url fields to User model"
```

---

### Task 2: Add profile update and avatar upload API endpoints

**Files:**
- Modify: `backend/api/auth.py`
- Create: `backend/assets/avatars/` directory

- [ ] **Step 1: Create avatars directory**

```bash
mkdir -p backend/assets/avatars
```

- [ ] **Step 2: Add imports at top of auth.py**

Add to the existing imports at `backend/api/auth.py`:

```python
import os
import uuid as uuid_mod
from fastapi import UploadFile, File
```

The full import block should be:

```python
import os
import uuid as uuid_mod
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Body, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select

from database import get_session
from limiter import limiter
from models.invite_code import InviteCode
from models.point_record import PointRecord
from models.user import User
from services.auth import hash_password, verify_password, create_access_token, get_current_user_from_cookie
from services.invite import generate_username, is_valid_username, code_status
```

- [ ] **Step 3: Extend /auth/me response to include new fields**

Replace the existing `get_me` function (lines 147-160) with:

```python
@router.get("/me")
def get_me(current_user: User = Depends(get_current_user_from_cookie)):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    checked_in_today = current_user.last_checkin_date == today
    return {
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "role": current_user.role,
            "nickname": current_user.nickname,
            "phone": current_user.phone,
            "avatar_url": current_user.avatar_url,
        },
        "points": current_user.points,
        "last_checkin_date": current_user.last_checkin_date,
        "checked_in_today": checked_in_today,
        "created_at": current_user.created_at,
    }
```

- [ ] **Step 4: Add PUT /auth/profile endpoint**

Add after the `change_password` function (after line 177):

```python
@router.put("/profile")
def update_profile(
    nickname: Optional[str] = Body(None),
    phone: Optional[str] = Body(None),
    current_user: User = Depends(get_current_user_from_cookie),
    session: Session = Depends(get_session),
):
    """Update nickname and/or phone"""
    if nickname is not None:
        nickname = nickname.strip()
        if len(nickname) > 20:
            raise HTTPException(status_code=400, detail="昵称不能超过20个字符")
        current_user.nickname = nickname or None
    if phone is not None:
        phone = phone.strip()
        if phone and not phone.isdigit():
            raise HTTPException(status_code=400, detail="手机号格式不正确")
        if len(phone) > 15:
            raise HTTPException(status_code=400, detail="手机号格式不正确")
        current_user.phone = phone or None
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return {
        "nickname": current_user.nickname,
        "phone": current_user.phone,
    }
```

- [ ] **Step 5: Add POST /auth/avatar endpoint**

Add after the `update_profile` function:

```python
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
MAX_AVATAR_SIZE = 2 * 1024 * 1024  # 2MB

@router.post("/avatar")
def upload_avatar(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user_from_cookie),
    session: Session = Depends(get_session),
):
    """Upload avatar image. Accepts JPEG, PNG, WebP. Max 2MB."""
    # Validate extension
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type not allowed. Use: {', '.join(ALLOWED_EXTENSIONS)}")

    # Read and validate size
    content = file.file.read()
    if len(content) > MAX_AVATAR_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Max 2MB")

    # Save to backend/assets/avatars/{user_id}.{ext}
    avatars_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "avatars")
    os.makedirs(avatars_dir, exist_ok=True)

    # Delete old avatar files for this user
    for old_ext in ALLOWED_EXTENSIONS:
        old_path = os.path.join(avatars_dir, f"{current_user.id}.{old_ext}")
        if os.path.exists(old_path):
            os.remove(old_path)

    filename = f"{current_user.id}.{ext}"
    filepath = os.path.join(avatars_dir, filename)
    with open(filepath, "wb") as f:
        f.write(content)

    avatar_url = f"/avatars/{filename}"
    current_user.avatar_url = avatar_url
    session.add(current_user)
    session.commit()

    return {"avatar_url": avatar_url}
```

- [ ] **Step 6: Verify endpoints load**

Run: `cd backend && python_portable/python.exe -c "from api.auth import router; print('OK')"`
Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add backend/api/auth.py backend/assets/avatars/
git commit -m "feat(auth): add profile update and avatar upload endpoints"
```

---

### Task 3: Mount /avatars static directory in main.py

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Add avatars directory constant and mount**

In `backend/main.py`, add after line 24 (`ASSETS_DIR = FRONTEND_DIR / "assets"`):

```python
AVATARS_DIR = Path(__file__).resolve().parent / "assets" / "avatars"
```

Then add before the `/api/health` endpoint (before line 86), add the avatars mount:

```python
# Avatar static files
if AVATARS_DIR.exists():
    app.mount("/avatars", StaticFiles(directory=str(AVATARS_DIR), html=False), name="avatars")
```

Note: This must come AFTER the SPA fallback middleware and API routes but BEFORE the catch-all favicon route. Place it after line 84 (`app.include_router(points.router, ...)`) and before line 86 (`@app.get("/api/health")`).

- [ ] **Step 2: Verify app starts**

Run: `cd backend && python_portable/python.exe -c "from main import app; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/main.py
git commit -m "feat: mount /avatars static directory for avatar serving"
```

---

### Task 4: Update auth store with nickname, phone, avatar_url

**Files:**
- Modify: `frontend/src/stores/auth.js`

- [ ] **Step 1: Add new reactive refs**

In `frontend/src/stores/auth.js`, after line 10 (`const tokenExpiry = ...`), add:

```javascript
const nickname = ref(localStorage.getItem('nickname') || null)
const phone = ref(localStorage.getItem('phone') || null)
const avatarUrl = ref(localStorage.getItem('avatarUrl') || null)
```

- [ ] **Step 2: Update setAuth to persist new fields**

In the `setAuth` function, after `lastCheckinDate.value = newLastCheckinDate` (line 27), add:

```javascript
if (newUser) {
  nickname.value = newUser.nickname || null
  phone.value = newUser.phone || null
  avatarUrl.value = newUser.avatar_url || null
  localStorage.setItem('nickname', nickname.value || '')
  localStorage.setItem('phone', phone.value || '')
  localStorage.setItem('avatarUrl', avatarUrl.value || '')
}
```

- [ ] **Step 3: Update logout to clear new fields**

In the `logout` function, after `localStorage.removeItem('lastCheckinDate')` (line 48), add:

```javascript
localStorage.removeItem('nickname')
localStorage.removeItem('phone')
localStorage.removeItem('avatarUrl')
```

Also set the values to null:

```javascript
nickname.value = null
phone.value = null
avatarUrl.value = null
```

- [ ] **Step 4: Update syncFromServer to refresh new fields**

In the `syncFromServer` function, after `lastCheckinDate.value = data.last_checkin_date || null` (line 56), add:

```javascript
if (data.user) {
  nickname.value = data.user.nickname || null
  phone.value = data.user.phone || null
  avatarUrl.value = data.user.avatar_url || null
  localStorage.setItem('nickname', nickname.value || '')
  localStorage.setItem('phone', phone.value || '')
  localStorage.setItem('avatarUrl', avatarUrl.value || '')
}
```

- [ ] **Step 5: Update return statement**

Change the return statement (line 70) to include new fields:

```javascript
return { token, user, points, lastCheckinDate, nickname, phone, avatarUrl, isLoggedIn, isAdmin, setAuth, logout, syncFromServer }
```

- [ ] **Step 6: Verify store compiles**

Run: `cd frontend && npx vue-tsc --noEmit 2>&1 | head -5` or simply `cd frontend && npm run build 2>&1 | tail -5`
Expected: Build succeeds with no errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/stores/auth.js
git commit -m "feat(auth): add nickname, phone, avatarUrl to auth store"
```

---

### Task 5: Rewrite Profile.vue as full personal center

**Files:**
- Modify: `frontend/src/views/Profile.vue` (complete rewrite)

- [ ] **Step 1: Write the complete rewritten Profile.vue**

Replace the entire contents of `frontend/src/views/Profile.vue` with the following. This merges Profile + Points functionality into one page:

```vue
<template>
  <div class="profile-page">
    <!-- Top nav -->
    <header class="profile-nav">
      <router-link to="/" class="btn-back" aria-label="返回">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5"/><path d="m12 19-7-7 7-7"/></svg>
      </router-link>
      <h1 class="nav-title">个人中心</h1>
    </header>

    <!-- Section 1: Avatar & Info -->
    <section class="card profile-card">
      <div class="avatar-area" @click="triggerAvatarUpload">
        <img v-if="auth.avatarUrl" :src="auth.avatarUrl" alt="头像" class="avatar-img" />
        <div v-else class="avatar-letter">{{ (displayName || '?')[0].toUpperCase() }}</div>
        <div class="avatar-overlay">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>
        </div>
        <input ref="avatarInput" type="file" accept="image/jpeg,image/png,image/webp" style="display:none" @change="onAvatarSelected" />
      </div>
      <div class="profile-info">
        <div class="name-row">
          <span class="display-name">{{ displayName }}</span>
          <span v-if="auth.isAdmin" class="role-badge admin">管理员</span>
          <span v-else class="role-badge user">普通用户</span>
        </div>
        <span class="username">@{{ auth.user?.username }}</span>
        <span class="join-date">{{ formatDate(auth.user?.created_at) }} 加入</span>
      </div>
    </section>

    <!-- Section 2: Points & Checkin -->
    <section class="card">
      <div class="section-header">
        <h2 class="section-title">积分</h2>
      </div>
      <div class="points-row">
        <div class="points-num-area">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
          <span class="points-num">{{ auth.points }}</span>
        </div>
        <button v-if="!checkedInToday && !checkingIn" class="btn-checkin" @click="doCheckin">每日签到 +5</button>
        <button v-else-if="checkingIn" class="btn-checkin" disabled>签到中...</button>
        <span v-else class="checked-text">今日已签到</span>
      </div>

      <div class="records-area">
        <h3 class="subsection-title">积分明细</h3>
        <div v-if="records.length === 0" class="empty">暂无积分记录</div>
        <div v-else class="record-list">
          <div v-for="r in records" :key="r.id" class="record-item">
            <div class="record-left">
              <span class="type-badge" :class="'type-' + r.record_type">{{ typeLabel(r.record_type) }}</span>
              <span class="record-note">{{ r.note || '-' }}</span>
            </div>
            <div class="record-right">
              <span class="amount" :class="r.amount > 0 ? 'pos' : 'neg'">{{ r.amount > 0 ? '+' : '' }}{{ r.amount }}</span>
              <span class="record-time">{{ formatRecordTime(r.created_at) }}</span>
            </div>
          </div>
        </div>
        <button v-if="hasMore" class="btn-more" @click="loadMore">加载更多</button>
      </div>
    </section>

    <!-- Section 3: Account Settings -->
    <section class="card">
      <h2 class="section-title">账号设置</h2>

      <div class="setting-item">
        <label class="setting-label">昵称</label>
        <div class="setting-row">
          <input v-model="editNickname" type="text" class="setting-input" placeholder="设置昵称" maxlength="20" />
          <button class="btn-save" @click="saveProfile('nickname')" :disabled="savingProfile">保存</button>
        </div>
      </div>

      <div class="setting-item">
        <label class="setting-label">手机号</label>
        <div class="setting-row">
          <input v-model="editPhone" type="tel" class="setting-input" placeholder="绑定手机号" maxlength="15" />
          <button class="btn-save" @click="saveProfile('phone')" :disabled="savingProfile">保存</button>
        </div>
      </div>

      <div class="setting-item">
        <label class="setting-label">修改密码</label>
        <div class="password-form">
          <input v-model="oldPassword" type="password" class="setting-input" placeholder="当前密码" />
          <input v-model="newPassword" type="password" class="setting-input" placeholder="新密码（至少6位）" />
          <input v-model="confirmPassword" type="password" class="setting-input" placeholder="确认新密码" />
          <button class="btn-save" @click="savePassword" :disabled="savingPassword">修改密码</button>
        </div>
      </div>
    </section>

    <!-- Section 4: Logout -->
    <button class="btn-logout" @click="handleLogout">退出登录</button>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useToast } from '../composables/toast'
import api from '../api'

const auth = useAuthStore()
const router = useRouter()
const toast = useToast()

const checkedInToday = ref(false)
const checkingIn = ref(false)
const records = ref([])
const page = ref(1)
const hasMore = ref(false)
const savingProfile = ref(false)
const savingPassword = ref(false)

const editNickname = ref(auth.nickname || '')
const editPhone = ref(auth.phone || '')
const oldPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')

const avatarInput = ref(null)

const displayName = computed(() => auth.nickname || auth.user?.username || '用户')

function formatDate(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  } catch { return iso }
}

function typeLabel(type) {
  return { register: '注册', checkin: '签到', qa: '问答', admin_set: '管理员' }[type] || type
}

function formatRecordTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('zh-CN', { timeZone: 'UTC' })
}

// Avatar
function triggerAvatarUpload() {
  avatarInput.value?.click()
}

async function onAvatarSelected(e) {
  const file = e.target.files?.[0]
  if (!file) return
  if (file.size > 2 * 1024 * 1024) {
    toast.error('图片不能超过 2MB')
    return
  }
  const formData = new FormData()
  formData.append('file', file)
  try {
    const { data } = await api.post('/auth/avatar', formData)
    auth.avatarUrl = data.avatar_url
    localStorage.setItem('avatarUrl', data.avatar_url)
    toast.success('头像更新成功')
  } catch (err) {
    toast.error(err.response?.data?.detail || '头像上传失败')
  }
  e.target.value = ''
}

// Checkin
async function doCheckin() {
  checkingIn.value = true
  try {
    const { data } = await api.post('/points/checkin')
    auth.points = data.points
    checkedInToday.value = data.checked_in_today !== undefined ? data.checked_in_today : true
    auth.lastCheckinDate = data.last_checkin_date || ''
    localStorage.setItem('points', String(data.points))
    if (auth.lastCheckinDate) localStorage.setItem('lastCheckinDate', auth.lastCheckinDate)
    await loadRecords(1)
    toast.success('签到成功 +5')
  } catch (e) {
    toast.error(e.response?.data?.detail || '签到失败')
  } finally {
    checkingIn.value = false
  }
}

// Records
async function loadRecords(p = 1) {
  const { data } = await api.get(`/points/records?page=${p}&page_size=20`)
  if (p === 1) records.value = data.records
  else records.value.push(...data.records)
  hasMore.value = records.value.length < data.total
  page.value = p
}

function loadMore() {
  loadRecords(page.value + 1)
}

// Profile update
async function saveProfile(field) {
  savingProfile.value = true
  try {
    const body = {}
    if (field === 'nickname') body.nickname = editNickname.value
    if (field === 'phone') body.phone = editPhone.value
    await api.put('/auth/profile', body)
    if (field === 'nickname') {
      auth.nickname = editNickname.value || null
      localStorage.setItem('nickname', auth.nickname || '')
    }
    if (field === 'phone') {
      auth.phone = editPhone.value || null
      localStorage.setItem('phone', auth.phone || '')
    }
    toast.success('保存成功')
  } catch (e) {
    toast.error(e.response?.data?.detail || '保存失败')
  } finally {
    savingProfile.value = false
  }
}

// Password
async function savePassword() {
  if (newPassword.value.length < 6) {
    toast.error('新密码至少6个字符')
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    toast.error('两次密码输入不一致')
    return
  }
  savingPassword.value = true
  try {
    await api.put('/auth/password', { old_password: oldPassword.value, new_password: newPassword.value })
    oldPassword.value = ''
    newPassword.value = ''
    confirmPassword.value = ''
    toast.success('密码修改成功')
  } catch (e) {
    toast.error(e.response?.data?.detail || '密码修改失败')
  } finally {
    savingPassword.value = false
  }
}

// Logout
async function handleLogout() {
  await auth.logout()
  router.push('/login')
}

onMounted(async () => {
  try {
    const { data } = await api.get('/auth/me')
    checkedInToday.value = data.checked_in_today || false
    editNickname.value = data.user?.nickname || ''
    editPhone.value = data.user?.phone || ''
  } catch {}
  loadRecords(1)
})
</script>

<style scoped>
.profile-page {
  max-width: 640px;
  margin: 0 auto;
  padding: var(--space-4) var(--space-6) var(--space-8);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

/* Nav */
.profile-nav {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-2);
}

.btn-back {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: var(--radius-md);
  color: var(--color-text-muted);
  text-decoration: none;
  transition: color var(--transition-fast), background var(--transition-fast);
}
.btn-back:hover {
  color: var(--color-text);
  background: var(--color-surface-hover);
}

.nav-title {
  font-size: 1.125rem;
  font-weight: 700;
  color: var(--color-text);
  margin: 0;
}

/* Card */
.card {
  padding: var(--space-5);
  background: var(--color-surface);
  border-radius: var(--radius-xl);
  border: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.section-title {
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-text-faint);
  margin: 0;
}

.subsection-title {
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--color-text-muted);
  margin: 0 0 var(--space-2);
}

/* Avatar & info */
.profile-card {
  flex-direction: row;
  align-items: center;
  gap: var(--space-4);
}

.avatar-area {
  position: relative;
  width: 80px;
  height: 80px;
  border-radius: 50%;
  overflow: hidden;
  flex-shrink: 0;
  cursor: pointer;
  background: var(--color-primary-muted);
}

.avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-letter {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.75rem;
  font-weight: 700;
  color: var(--color-primary);
  background: var(--color-primary-muted);
}

.avatar-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.4);
  opacity: 0;
  transition: opacity var(--transition-fast);
}
.avatar-area:hover .avatar-overlay {
  opacity: 1;
}

.profile-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.name-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.display-name {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--color-text);
}

.role-badge {
  font-size: 0.6875rem;
  font-weight: 600;
  padding: 1px 7px;
  border-radius: 999px;
}
.role-badge.admin {
  background: rgba(234, 179, 8, 0.12);
  color: #b45309;
}
.role-badge.user {
  background: var(--color-primary-muted);
  color: var(--color-primary);
}

.username {
  font-size: 0.8125rem;
  color: var(--color-text-muted);
}

.join-date {
  font-size: 0.75rem;
  color: var(--color-text-faint);
}

/* Points */
.points-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.points-num-area {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.points-num {
  font-size: 2rem;
  font-weight: 700;
  color: var(--color-text);
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.btn-checkin {
  padding: 0.5rem 1rem;
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: background var(--transition-fast);
}
.btn-checkin:hover { background: var(--color-primary-hover); }
.btn-checkin:disabled { opacity: 0.5; cursor: not-allowed; }

.checked-text {
  font-size: 0.875rem;
  color: var(--color-success);
  font-weight: 500;
}

/* Records */
.records-area {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px solid var(--color-border);
}

.record-list {
  display: flex;
  flex-direction: column;
  gap: 1px;
  background: var(--color-border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.record-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-3) var(--space-4);
  background: var(--color-surface);
}

.record-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-width: 0;
}

.type-badge {
  font-size: 0.6875rem;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 999px;
  flex-shrink: 0;
}
.type-register { background: rgba(34,197,94,0.1); color: #16a34a; }
.type-checkin { background: rgba(59,130,246,0.1); color: #2563eb; }
.type-qa { background: rgba(156,163,175,0.2); color: #6b7280; }
.type-admin_set { background: rgba(168,85,247,0.1); color: #7c3aed; }

.record-note {
  font-size: 0.8125rem;
  color: var(--color-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.record-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  flex-shrink: 0;
}

.amount { font-weight: 700; font-size: 0.875rem; }
.amount.pos { color: #16a34a; }
.amount.neg { color: #dc2626; }

.record-time { font-size: 0.6875rem; color: var(--color-text-faint); }

.empty {
  padding: var(--space-6);
  text-align: center;
  color: var(--color-text-faint);
  font-size: 0.8125rem;
}

.btn-more {
  width: 100%;
  padding: var(--space-3);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  font-size: 0.8125rem;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: border-color var(--transition-fast);
}
.btn-more:hover { border-color: var(--color-primary); color: var(--color-primary); }

/* Settings */
.setting-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding-top: var(--space-3);
  border-top: 1px solid var(--color-border);
}
.setting-item:first-of-type {
  border-top: none;
  padding-top: 0;
}

.setting-label {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--color-text);
}

.setting-row {
  display: flex;
  gap: var(--space-2);
}

.setting-input {
  flex: 1;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-family: var(--font-sans);
  font-size: 0.875rem;
  color: var(--color-text);
  background: var(--color-bg);
  outline: none;
  transition: border-color var(--transition-fast);
}
.setting-input:focus { border-color: var(--color-primary); }
.setting-input::placeholder { color: var(--color-text-faint); }

.password-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.btn-save {
  padding: 0.5rem 1rem;
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: 0.8125rem;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  transition: background var(--transition-fast);
}
.btn-save:hover { background: var(--color-primary-hover); }
.btn-save:disabled { opacity: 0.5; cursor: not-allowed; }

/* Logout */
.btn-logout {
  padding: 0.75rem;
  background: transparent;
  border: 1px solid var(--color-error);
  border-radius: var(--radius-lg);
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--color-error);
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast);
}
.btn-logout:hover {
  background: var(--color-error);
  color: white;
}

/* Mobile */
@media (max-width: 640px) {
  .profile-page { padding: var(--space-3) var(--space-4) var(--space-6); }
  .profile-card { flex-direction: column; text-align: center; }
  .profile-info { align-items: center; }
  .points-row { flex-direction: column; gap: var(--space-3); align-items: flex-start; }
}
</style>
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npm run build 2>&1 | tail -5`
Expected: Build succeeds with no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/Profile.vue
git commit -m "feat(profile): rewrite Profile.vue as full personal center"
```

---

### Task 6: Add sidebar user card to Chat.vue

**Files:**
- Modify: `frontend/src/views/Chat.vue`

- [ ] **Step 1: Add sidebar footer template**

In `frontend/src/views/Chat.vue`, after the `</nav>` closing tag of `session-list` (around line 60, before `</aside>`), add:

```html
      <!-- Sidebar footer: user card -->
      <div class="sidebar-footer">
        <router-link to="/profile" class="user-card">
          <div class="user-avatar-sm">
            <img v-if="authStore.avatarUrl" :src="authStore.avatarUrl" alt="" class="user-avatar-img" />
            <span v-else class="user-avatar-letter">{{ (authStore.nickname || authStore.user?.username || '?')[0].toUpperCase() }}</span>
          </div>
          <div class="user-card-info">
            <span class="user-card-name">{{ authStore.nickname || authStore.user?.username || '用户' }}</span>
            <span class="user-card-points">{{ authStore.points }} 积分</span>
          </div>
        </router-link>
        <button class="btn-logout-sm" @click="handleSidebarLogout" title="退出登录" aria-label="退出登录">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
        </button>
      </div>
```

- [ ] **Step 2: Add mobile header avatar link**

In the mobile nav header section (inside `<header class="mobile-nav">`), after the search router-link (around line 77), add:

```html
        <router-link to="/profile" class="btn-icon-sm avatar-sm" title="个人中心" aria-label="个人中心">
          <span class="avatar-sm-letter">{{ (authStore.nickname || authStore.user?.username || '?')[0].toUpperCase() }}</span>
        </router-link>
```

- [ ] **Step 3: Add handleSidebarLogout function**

In the `<script setup>` section, after the existing function definitions, add:

```javascript
async function handleSidebarLogout() {
  await authStore.logout()
  router.push('/login')
}
```

Also add the router import if not present. Check if `useRouter` is imported. If not, add:

```javascript
import { useRouter } from 'vue-router'
```

And add after the existing store declarations:

```javascript
const router = useRouter()
```

Note: Check if `useRouter` is already imported. The current Chat.vue does NOT import `useRouter`, so it must be added.

- [ ] **Step 4: Add sidebar footer CSS**

Add these styles in the `<style scoped>` section, after the `.session-delete:hover` rule and before the `/* ── Main ── */` comment:

```css
/* ── Sidebar footer ── */
.sidebar-footer {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-top: 1px solid var(--color-border);
  background: var(--color-surface);
}

.user-card {
  flex: 1;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 6px 8px;
  border-radius: var(--radius-md);
  text-decoration: none;
  transition: background var(--transition-fast);
  min-width: 0;
}
.user-card:hover {
  background: var(--color-surface-hover);
}

.user-avatar-sm {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  overflow: hidden;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-primary-muted);
}

.user-avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.user-avatar-letter {
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--color-primary);
}

.user-card-info {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.user-card-name {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-card-points {
  font-size: 0.6875rem;
  color: var(--color-text-faint);
}

.btn-logout-sm {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: var(--color-text-faint);
  cursor: pointer;
  flex-shrink: 0;
  transition: color var(--transition-fast), background var(--transition-fast);
}
.btn-logout-sm:hover {
  color: var(--color-error);
  background: var(--color-danger-bg);
}

.avatar-sm {
  position: relative;
}
.avatar-sm-letter {
  font-size: 0.625rem;
  font-weight: 700;
  color: var(--color-primary);
}
```

- [ ] **Step 5: Verify build**

Run: `cd frontend && npm run build 2>&1 | tail -5`
Expected: Build succeeds.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/Chat.vue
git commit -m "feat(chat): add sidebar user card and mobile avatar link"
```

---

### Task 7: Update routes — redirect /points to /profile, remove Points.vue

**Files:**
- Modify: `frontend/src/router/index.js`
- Delete: `frontend/src/views/Points.vue`

- [ ] **Step 1: Replace /points route with redirect**

In `frontend/src/router/index.js`, replace the `/points` route entry (lines 29-33):

```javascript
  {
    path: '/points',
    redirect: '/profile'
  },
```

- [ ] **Step 2: Delete Points.vue**

```bash
rm frontend/src/views/Points.vue
```

- [ ] **Step 3: Verify build**

Run: `cd frontend && npm run build 2>&1 | tail -5`
Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/router/index.js frontend/src/views/Points.vue
git commit -m "refactor: redirect /points to /profile, remove Points.vue"
```

---

### Task 8: Final build and integration test

**Files:** None (verification only)

- [ ] **Step 1: Full frontend build**

Run: `cd frontend && npm run build 2>&1`
Expected: Build succeeds with zero errors.

- [ ] **Step 2: Backend startup check**

Run: `cd backend && python_portable/python.exe -c "from main import app; print('App loads OK')"`
Expected: `App loads OK`

- [ ] **Step 3: Manual integration test checklist**

Start the full application and verify:

1. Login → Chat page shows sidebar footer with user card
2. Click user card → navigates to /profile
3. Profile page shows avatar, name, points, checkin, records, settings
4. Upload avatar → image appears in sidebar + profile
5. Edit nickname → updates in sidebar + profile
6. Click checkin → points increase, record appears
7. Change password → success toast
8. Mobile: avatar icon in header links to /profile
9. Navigate to /points → redirects to /profile
10. Click logout → redirected to /login

- [ ] **Step 4: Commit build artifacts**

```bash
git add backend/assets/frontend/
git commit -m "build: update frontend assets with user center"
```
