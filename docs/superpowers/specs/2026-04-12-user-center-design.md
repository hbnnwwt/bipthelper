# User Center Design Spec

## Goal

Replace the minimal Profile.vue with a full-featured personal center page, merge Points.vue into it, and add a persistent user card entry in the Chat sidebar.

## Data Model Changes

### User model — new fields

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `nickname` | `Optional[str]` | `None` | Display name; fallback to `username` when None |
| `phone` | `Optional[str]` | `None` | Phone number for account binding |
| `avatar_url` | `Optional[str]` | `None` | Relative URL like `/avatars/{user_id}.jpg` |

### New backend API endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/auth/profile` | PUT | Update nickname and/or phone. Body: `{ nickname?, phone? }` |
| `/auth/avatar` | POST | Upload avatar image (multipart/form-data, field name `file`). Save to `backend/assets/avatars/{user_id}.{ext}`. Return `{ avatar_url }`. |
| `/auth/me` | GET | Already exists; extend response to include `nickname`, `phone`, `avatar_url`, `created_at` |

Existing endpoints unchanged:
- `PUT /auth/password` — change password (old_password + new_password)
- `POST /points/checkin` — daily checkin
- `GET /points/records` — paginated point records

### Avatar storage

- Directory: `backend/assets/avatars/` (served as static files via FastAPI `StaticFiles`)
- Filename: `{user_id}.{jpg|png|webp}` — one file per user, overwrite on re-upload
- Max size: 2MB
- Accepted formats: JPEG, PNG, WebP
- Response field `avatar_url` is a relative path like `/avatars/{user_id}.jpg`

## Chat Sidebar Entry

### Sidebar bottom area (desktop)

Add a fixed bottom section to the sidebar (`<aside>`) that does not scroll with the session list:

Layout:
```
┌─────────────────────────┐
│ sidebar-header          │
├─────────────────────────┤
│ session-list (scrolls)  │
│                         │
│                         │
├─────────────────────────┤
│ [avatar] nickname       │  ← user card, clickable → /profile
│          42 ★           │
│                    [⚙]  │  ← logout icon button
└─────────────────────────┘
```

Implementation:
- `session-list` keeps `flex: 1; overflow-y: auto`
- New `sidebar-footer` div with `flex-shrink: 0; border-top: 1px solid var(--color-border)`
- User avatar: 28px circle, show username first letter when no avatar_url
- Click card → `router.push('/profile')`
- Logout button: small icon, calls `authStore.logout()` then `router.push('/login')`

### Mobile

- Sidebar overlay: same bottom card when open
- Mobile header: add small avatar icon (24px) on the right side, links to `/profile`

## Profile Page Redesign

Merge Profile.vue + Points.vue into a single comprehensive page at `/profile`.

### Page sections

**Top navigation bar**
- Back button (→ /) + title "个人中心"

**Section 1: Avatar & Basic Info**
- Large avatar (80px circle), click triggers file picker for upload
- Nickname (editable inline, pencil icon to toggle edit mode)
- Username (read-only, gray)
- Role badge (管理员/普通用户)
- Registration date

**Section 2: Points & Checkin**
- Current points balance (large number + star icon)
- Daily checkin button (or "今日已签到" when done)
- Point records list (migrated from Points.vue):
  - Paginated with "加载更多"
  - Each record: type badge (register/checkin/qa/admin_set) + amount + note + date
  - Type badge colors: register=green, checkin=blue, qa=gray, admin_set=purple

**Section 3: Account Settings**
- Nickname field (text input, save button)
- Phone field (text input, save button)
- Password change (old + new + confirm, save button)

**Section 4: Logout**
- Red "退出登录" button at page bottom

### Route changes

| Old | New | Notes |
|-----|-----|-------|
| `/profile` | `/profile` | Same route, completely rewritten component |
| `/points` | redirect → `/profile` | Backward compatibility; remove Points.vue |
| `/user` | N/A | Not used |

### Files changed

| File | Action |
|------|--------|
| `backend/models/user.py` | Add `nickname`, `phone`, `avatar_url` fields |
| `backend/api/auth.py` | Add `PUT /auth/profile`, `POST /auth/avatar`; extend `/auth/me` response |
| `backend/main.py` | Mount `/avatars` static files directory |
| `frontend/src/views/Profile.vue` | Complete rewrite — full personal center |
| `frontend/src/views/Points.vue` | Delete (merged into Profile) |
| `frontend/src/views/Chat.vue` | Add sidebar footer user card + mobile header avatar |
| `frontend/src/stores/auth.js` | Add `nickname`, `phone`, `avatar_url` to stored state |
| `frontend/src/router/index.js` | `/points` → redirect to `/profile` |

## Error Handling

- Avatar upload: validate file type and size before sending; show toast on failure
- Profile update: optimistic UI, revert on error with toast
- Password change: validate new password length (≥6), confirm match; show specific error messages
- Checkin: same behavior as current Points.vue — 400 if already checked in

## Design Principles

- Single page, single responsibility: everything about the user in one place
- No unnecessary abstractions — direct API calls from the component
- Follow existing Chat.vue visual patterns (same CSS custom properties, spacing scale, colors)
- Mobile-first: the page must work well on phones since students primarily use mobile
