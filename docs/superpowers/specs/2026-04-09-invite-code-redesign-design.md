# 激活码系统重新设计

## 背景

当前邀请码机制存在以下问题：
1. 邀请码挂在 User 表，生成时就要创建"幽灵用户"记录
2. 无法列出已生成但未激活的码
3. 无法区分码的类型（指定用户 vs 任意用户）
4. 码无法删除

## 设计目标

1. **两类激活码**：指定用户激活码、任意用户激活码
2. **可观测**：Admin 可查看所有激活码及其状态（待激活 / 已使用 / 已过期）
3. **可管理**：激活码可被删除
4. **安全**：固定 7 天有效期，自动过期

---

## 数据模型

### 新建 `InviteCode` 表（`backend/models/invite_code.py`）

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | str | 主键，激活码字符串 |
| `code_type` | str | `"designated"` 指定用户 / `"anonymous"` 任意用户 |
| `designated_username` | str | 预填用户名（仅 designated，null 表示 anonymous） |
| `created_by` | str | 创建者 admin username |
| `created_at` | datetime | 创建时间（UTC ISO 格式） |
| `expires_at` | datetime | 到期时间（created_at + 7天） |
| `used_by` | str | 激活者的 User ID（可空） |
| `used_at` | datetime | 激活时间（可空） |

**激活码格式**：`ACT-{8位十六进制}` 前缀 "ACT" = Activation Token，e.g. `ACT-a3f8c2d1`

**表名**：`invite_codes`

### User 表变更

- 废弃 `invite_code` 字段（ALTER TABLE 不做，通过迁移脚本重建完整表）

---

## API 设计

### Admin 接口

#### `POST /admin/codes` — 创建激活码
**权限**：仅 admin

**Request Body**：
```json
{
  "type": "designated" | "anonymous",
  "username": "xxx"   // designated 时必填，anonymous 时忽略（可省略）
}
```

**Response** `201`：
```json
{
  "code": "ACT-a3f8c2d1",
  "type": "designated" | "anonymous",
  "designated_username": "张三" | null,
  "expires_at": "2026-04-16T10:00:00Z",
  "created_by": "admin"
}
```

**错误**：
- `400` — designated 类型但未提供 username
- `400` — designated 类型 username 已存在或已有人使用该邀请码

#### `GET /admin/codes` — 列出所有激活码
**权限**：仅 admin

**Query Params**：无

**Response** `200`：
```json
{
  "codes": [
    {
      "code": "ACT-a3f8c2d1",
      "type": "designated",
      "designated_username": "张三",
      "created_by": "admin",
      "created_at": "2026-04-09T10:00:00Z",
      "expires_at": "2026-04-16T10:00:00Z",
      "status": "active",
      "used_by": null,
      "used_at": null
    },
    {
      "code": "ACT-b2e1d4f9",
      "type": "anonymous",
      "designated_username": null,
      "created_by": "admin",
      "created_at": "2026-04-09T09:00:00Z",
      "expires_at": "2026-04-16T09:00:00Z",
      "status": "used",
      "used_by": "user-uuid-here",
      "used_at": "2026-04-10T14:30:00Z"
    }
  ]
}
```

**status 枚举**：
- `active` — 未使用且未过期
- `used` — 已使用
- `expired` — 已过期

#### `DELETE /admin/codes/{code}` — 删除激活码
**权限**：仅 admin

**Response** `200`：`{ "message": "Code deleted" }`

**错误**：`404` — 码不存在

---

### 注册接口改造

#### `POST /auth/register`
**Request Body**：
```json
{
  "password": "xxx",
  "invite_code": "ACT-a3f8c2d1",
  "username": "xxx"   // designated 类型时必填，anonymous 时可选
}
```

**校验流程**：
1. 激活码存在
2. `status == "active"`（未使用且未过期）
3. **designated 类型**：提交的 `username` 必须等于 `designated_username`
4. **anonymous 类型**：
   - `username` 未填 → 自动生成 10 位字母数字（`secrets.token_hex(5).upper()`，即 10 个大写字母数字）
   - `username` 填写 → 校验最少 6 位字母数字组合，无重复
5. `password` 最少 6 位
6. `username` 全局唯一（不可与已有用户重复）

**成功响应** `200`：
```json
{
  "user": { "id": "uuid", "username": "张三" | "A3FZK9M2B1", "role": "user" },
  "token": "jwt..."
}
```

**错误**：
- `400` — 激活码不存在
- `400` — 激活码已使用
- `400` — 激活码已过期
- `400` — designated 激活码但用户名不匹配
- `400` — anonymous 激活码用户名已被占用
- `400` — 密码不足 6 位

**激活码状态更新**（注册成功后同步）：
```python
invite_code.used_by = new_user.id
invite_code.used_at = datetime.now(timezone.utc)
session.commit()
```

---

## 关键逻辑

### 自动过期判断
在 `GET /admin/codes` 和 `POST /auth/register` 中，status 字段不存储，由接口实时计算：
```python
def _code_status(code: InviteCode) -> str:
    if code.used_by:
        return "used"
    if datetime.now(timezone.utc) > code.expires_at:
        return "expired"
    return "active"
```

### anonymous 用户名自动生成
```python
import secrets
import string

def _generate_username() -> str:
    # 从 A-Z 0-9 中随机选 10 位
    alphabet = string.ascii_uppercase + string.digits  # 36 个字符
    return ''.join(secrets.choice(alphabet) for _ in range(10))
    # e.g. "A3FZK9M2B1"
```

### anonymous 用户名校验
```python
def _validate_username(username: str) -> bool:
    if len(username) < 6:
        return False
    return username.isalnum()  # 纯字母数字
```

---

## 数据库迁移

setup.bat 已删除旧数据库，重启后 `SQLModel.metadata.create_all()` 会创建新表。

User 表变更：
- 废弃 `invite_code` 字段（重建后不存在）

---

## 测试要点

1. **designated 激活码**：用匹配用户名注册成功，用不匹配用户名注册失败
2. **anonymous 激活码（不填用户名）**：自动生成 10 位用户名，注册成功
3. **anonymous 激活码（填写用户名）**：校验最少 6 位字母数字
4. **过期**：7 天后同一码自动变为 expired 状态
5. **重复使用**：同一码第二次注册返回"已使用"
6. **列表**：GET /admin/codes 返回所有码含实时 status
7. **删除**：已用过的码也可删除
