from datetime import datetime, timezone

from fastapi import HTTPException
from pymysql.err import IntegrityError
from pymysql.cursors import DictCursor

from app.core.database import get_connection
from app.features.auth.schemas import TokenResponse
from app.features.auth.security import create_access_token, hash_password, verify_password


def register_user(username: str, password: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO users (username, password_hash, created_at) VALUES (%s, %s, %s)",
                    (username, hash_password(password), now),
                )
    except IntegrityError as exc:
        raise HTTPException(status_code=400, detail="用户名已存在") from exc


def login_user(username: str, password: str) -> TokenResponse:
    with get_connection() as conn:
        with conn.cursor(cursor = DictCursor) as cursor:
            cursor.execute(
                "SELECT id, username, password_hash FROM users WHERE username = %s",
                (username,),
            )
            user = cursor.fetchone()

    if user is None or not verify_password(password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    return TokenResponse(
        access_token=create_access_token(user["id"], user["username"]),
        username=user["username"],
    )
