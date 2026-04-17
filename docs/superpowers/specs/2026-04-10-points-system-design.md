# 积分系统设计

## 背景

为石化助手增加积分激励机制：
- 注册激活送积分，鼓励用户完成注册流程
- 每日签到送积分，提升留存
- 问答消耗积分，控制资源消耗
- Admin 可管理所有用户积分

## 设计目标

1. 积分无限累积，无上限
2. 积分变动有完整明细记录（可追溯）
3. 签到按 UTC 自然日（0点）刷新，不可重复签到
4. Admin 可查看和修改任意用户积分

---

## 数据模型

### User 表变更

| 字段 | 类型 | 说明 |
|------|------|------|
| `points` | int | 积分余额，默认 0 |
| `last_checkin_date` | Optional[str] | 上次签到日期（UTC，"YYYY-MM-DD"），null 表示从未签到 |

### 新建 `PointRecord` 表（`backend/models/point_record.py`）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | str | 主键（uuid） |
| `user_id` | str | 外键到 User.id，indexed |
| `amount` | int | 积分变动数量，正=收入，负=消耗 |
| `type` | str | `"register"` \| `"checkin"` \| `"qa"` \| `"admin_set"` |
| `note` | str | 备注文字 |
| `created_at` | str | UTC ISO 时间 |

**表名**：`point_records`

---

## 积分规则

| 触发时机 | 积分变化 | PointRecord type | 说明 |
|------|------|------|------|
| 注册激活 | +10 | `"register"` | 注册成功后写入 |
| 每日签到 | +5 | `"checkin"` | UTC 0点刷新，last_checkin_date != 今天可签 |
| 每次问答 | -1 | `"qa"` | 在 send_message 中先扣再调用 RAG |
| Admin 修改 | ±任意 | `"admin_set"` | Admin 操作时记录 |

### 签到逻辑

```python
today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
if user.last_checkin_date == today:
    raise HTTPException(status_code=400, detail="今日已签到")
user.points += 5
user.last_checkin_date = today
```

### 问答扣积分逻辑

在 `send_message` API（RAG 调用前）中：

```python
if user.points < 1:
    raise HTTPException(status_code=403, detail="积分不足，无法提问")
user.points -= 1
record = PointRecord(user_id=user.id, amount=-1, type="qa", note="问答消耗")
session.add(record)
session.commit()
# 然后再调用 RAG
```

---

## API 设计

### 用户接口

#### `POST /points/checkin` — 签到
**权限**：登录用户

**Request Body**：无

**Response `200`**：
```json
{
  "points": 15,
  "checked_in_today": true,
  "earned": 5
}
```

**错误**：`400` — 今日已签到

---

#### `GET /points/records` — 积分明细
**权限**：登录用户（仅查看自己的记录）

**Query Params**：`page`（默认1），`page_size`（默认20）

**Response `200`**：
```json
{
  "records": [
    {
      "id": "uuid",
      "amount": 10,
      "type": "register",
      "note": "注册激活",
      "created_at": "2026-04-10T08:00:00Z"
    }
  ],
  "total": 25,
  "page": 1,
  "page_size": 20
}
```

---

#### `GET /auth/me` 变更
在现有响应中附加：
```json
{
  "points": 15,
  "last_checkin_date": "2026-04-10"
}
```

---

### Admin 接口

#### `GET /admin/users/{user_id}/points` — 查看用户积分
**权限**：仅 admin

**Response `200`**：
```json
{
  "user_id": "uuid",
  "username": "张三",
  "points": 15,
  "last_checkin_date": "2026-04-10"
}
```

**错误**：`404` — 用户不存在

---

#### `PATCH /admin/users/{user_id}/points` — 修改积分
**权限**：仅 admin

**Request Body**（二选一）：
```json
{ "delta": 5 }   // 增减积分
```
或
```json
{ "set": 100 }   // 直接设置绝对值
```

**Response `200`**：
```json
{
  "user_id": "uuid",
  "username": "张三",
  "old_points": 15,
  "new_points": 20,
  "changed_by": "admin"
}
```

**规则**：`set` 和 `delta` 不可同时传。`set` 时积分数可以为 0。

---

## 触发时机与实现位置

| 触发点 | 文件 | 逻辑 |
|------|------|------|
| 注册激活 | `backend/api/auth.py` — `register()` | 注册成功后 `points += 10`，写入 PointRecord |
| 每日签到 | `backend/api/points.py`（新建）— `checkin()` | 检查 last_checkin_date，签到成功 +5 |
| 问答消耗 | `backend/api/chat.py` — `send_message()` | RAG 调用前检查 points，够则扣 -1 |
| Admin 修改积分 | `backend/api/admin.py` — `patch_user_points()` | 新增 endpoint |

---

## 数据库迁移

`setup.bat` 删除 `data/app.db` 后重启，`SQLModel.metadata.create_all()` 自动创建新表。

---

## 测试要点

1. **注册**：新用户注册后 points = 10，有一条 `register` 记录
2. **签到**：当天第一次签到成功 +5，第二次签到返回 "今日已签到"，跨天后可再签
3. **问答扣积分**：积分足够时每次提问 -1，积分不足（0）时返回 403
4. **Admin 修改积分**：delta 正负均可，set 直接设值，均生成 `admin_set` 记录
5. **明细查询**：记录按时间倒序，支持分页
6. **积分不足拦截**：points=0 时 send_message 返回 403，不调用 RAG
