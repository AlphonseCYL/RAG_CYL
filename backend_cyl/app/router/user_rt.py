from typing import Annotated

from fastapi import APIRouter, Depends

from app.features.auth.schemas import AuthRequest, TokenResponse, UserInfo
from app.features.auth.security import get_current_user
from app.features.auth.service import login_user, register_user


router = APIRouter(tags=["auth"])


@router.post("/register")
def register(request: AuthRequest) -> dict:
    register_user(request.username, request.password)
    return {"message": "注册成功"}


@router.post("/login", response_model=TokenResponse)
def login(request: AuthRequest) -> TokenResponse:
    return login_user(request.username, request.password)


@router.get("/me")
def me(current_user: Annotated[UserInfo, Depends(get_current_user)]) -> UserInfo:
    return current_user
