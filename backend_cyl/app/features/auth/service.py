from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.core.database import SessionLocal
from app.features.auth.schemas import TokenResponse
from app.features.auth.security import create_access_token, hash_password, verify_password
from app.db_models.user import User


def register_user(username: str, password: str) -> None:
    db = SessionLocal()
    try:
        user = User(
            username=username,
            password_hash=hash_password(password),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        db.add(user)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="用户名已存在") from exc
    finally:
        db.close()


def login_user(username: str, password: str) -> TokenResponse:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
    finally:
        db.close()

    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    return TokenResponse(
        access_token=create_access_token(user.id, user.username),
        username=user.username,
    )
