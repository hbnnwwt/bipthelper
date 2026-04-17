from cryptography.fernet import Fernet
import base64
import hashlib
from functools import lru_cache

@lru_cache
def _get_fernet():
    from config import get_settings
    settings = get_settings()
    key_material = settings.SECRET_KEY.encode()
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(key_material).digest()))

def encrypt_value(value: str) -> str:
    if not value:
        return value
    return _get_fernet().encrypt(value.encode()).decode()

def decrypt_value(value: str) -> str:
    if not value:
        return value
    return _get_fernet().decrypt(value.encode()).decode()
