from typing import Annotated

from fastapi import APIRouter, Depends

from app.features.auth.security import get_current_user
from app.features.sessions.schemas import SessionResponse
from app.features.sessions.service import create_session


router = APIRouter(tags=["sessions"])


@router.post("/create_session", response_model=SessionResponse)
def create_chat_session(
    current_user: Annotated[dict, Depends(get_current_user)],
) -> SessionResponse:
    session_id = create_session(current_user["id"])
    return SessionResponse(session_id=session_id)

