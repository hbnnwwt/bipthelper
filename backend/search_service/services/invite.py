import secrets
import string
from datetime import datetime, timezone

def generate_username() -> str:
    """为 anonymous 类型生成 10 位随机用户名（A-Z 0-9）"""
    alphabet = string.ascii_uppercase + string.digits  # 36 chars
    return ''.join(secrets.choice(alphabet) for _ in range(10))

def is_valid_username(username: str) -> bool:
    """校验 username：最少 6 位，纯字母数字"""
    if len(username) < 6:
        return False
    return username.isalnum()

def code_status(code) -> str:  # type: ignore
    """实时计算激活码状态：used / expired / active"""
    if code.used_by:
        return "used"
    expires = datetime.fromisoformat(code.expires_at.replace('Z', '+00:00'))
    if datetime.now(timezone.utc) > expires:
        return "expired"
    return "active"

def is_expired(code) -> bool:  # type: ignore
    """检查激活码是否已过期"""
    expires = datetime.fromisoformat(code.expires_at.replace('Z', '+00:00'))
    return datetime.now(timezone.utc) > expires
