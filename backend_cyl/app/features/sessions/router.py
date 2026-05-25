from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.features.auth.security import get_current_user
from app.features.sessions.schemas import (
    ChatRequest,
    DeleteSessionResponse,
    SessionItem,
    SessionListResponse,
    SessionResponse,
)
from app.features.sessions.service import (
    create_session,
    delete_session,
    get_sessions,
    get_chat_completion,
    user_owns_session,
)


router = APIRouter(tags=["sessions"])

##################################################
#   创建一个新的对话 Session
#   输入：当前用户信息
#   输出：新创建的 Session ID
##################################################

@router.post("/create_session", response_model=SessionResponse)
def create_chat_session(
    current_user: Annotated[dict, Depends(get_current_user)],
) -> SessionResponse:
    session_id = create_session(current_user["id"])
    return SessionResponse(session_id=session_id)


##################################################
#   获取用户拥有的所有对话 Session 
#   输入：当前用户信息
#   输出：用户拥有的所有对话 Session 列表
##################################################
@router.get("/get_sessions", response_model=SessionListResponse)
def list_sessions(
    current_user: Annotated[dict, Depends(get_current_user)],
) -> SessionListResponse:
    sessions = get_sessions(current_user["id"])
    sessions_items = [SessionItem(**session) for session in sessions]
    return SessionListResponse(sessions=sessions_items)


##################################################
#   删除一个对话 Session
#   输入：待删除的session_id、当前用户信息
#   输出：删除信息
##################################################
@router.delete("/sessions/{session_id}", response_model=DeleteSessionResponse)
def remove_session(
    session_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> DeleteSessionResponse:
    deleted = delete_session(current_user["id"], session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="会话不存在或无权删除")
    return DeleteSessionResponse()


##################################################
#   在文档上进行对话
#   输入：当前用户信息、会话ID、对话请求
#   输出：对话响应的流式数据
##################################################
@router.post("/chat_on_docs")
async def chat_on_docs(
    current_user: Annotated[dict, Depends(get_current_user)],
    session_id: Annotated[str, Query()],
    request: Annotated[ChatRequest, Body()],
) -> StreamingResponse:
    if not user_owns_session(current_user["id"], session_id):
        raise HTTPException(status_code=404, detail="会话不存在或无权访问")

    return StreamingResponse(
        get_chat_completion(session_id, current_user["id"], request.message),
        media_type="text/event-stream",
    )


