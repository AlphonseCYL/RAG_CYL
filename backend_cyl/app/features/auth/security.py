from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
from typing import Annotated

from fastapi import Header, HTTPException, status
from jose import JWTError, jwt

from app.core.config import (
    ACCESS_TOKEN_EXPIRE_HOURS,
    JWT_ALGORITHM,
    JWT_SECRET_KEY,
)

# 生成一个随机salt，再根据密码生成hash值，输出格式为salt$hash
def hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}${digest.hex()}"

# 验证密码是否正确，输入密码和数据库中存储的salt$hash值
# 根据输入密码以及salt来计算一个hash值，并与数据库中的hash值进行比较
# 返回True或False
def verify_password(password: str, password_hash: str) -> bool:
    try:
        salt, expected_digest = password_hash.split("$", 1)
    except ValueError:
        return False

    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return hmac.compare_digest(digest.hex(), expected_digest)


def create_access_token(user_id: int, username: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {"sub": str(user_id), "username": username, "exp": expires_at}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def get_current_user(authorization: Annotated[str | None, Header()] = None) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录",
        )

    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录状态已失效",
        ) from exc

    return {"id": int(payload["sub"]), "username": payload["username"]}
