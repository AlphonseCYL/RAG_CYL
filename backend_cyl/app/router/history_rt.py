from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.features.auth.security import get_current_user
from app.features.sessions.schemas import (
    DeleteSessionResponse,
    SessionItem,
    SessionListResponse,
)
from app.features.sessions.service import delete_session, get_sessions


router = APIRouter(tags=["history"])


@router.get("/get_sessions", response_model=SessionListResponse)
def list_sessions(
    current_user: Annotated[dict, Depends(get_current_user)],
) -> SessionListResponse:
    sessions = get_sessions(current_user["id"])
    session_items = [SessionItem(**session) for session in sessions]
    return SessionListResponse(sessions=session_items)


@router.delete("/sessions/{session_id}", response_model=DeleteSessionResponse)
def remove_session(
    session_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> DeleteSessionResponse:
    deleted = delete_session(current_user["id"], session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="会话不存在或无权删除")
    return DeleteSessionResponse()
