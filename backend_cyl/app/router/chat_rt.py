from typing import Annotated

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.features.auth.security import get_current_user
from app.features.auth.schemas import UserInfo
from app.features.sessions.quick_parse_service import quick_parse_service
from app.features.sessions.schemas import ChatRequest, SessionResponse
from app.features.sessions.service import (
    create_session,
    get_chat_completion,
    user_owns_session,
)


router = APIRouter(tags=["chat"])


@router.post("/create_session", response_model=SessionResponse)
def create_chat_session(
    current_user: Annotated[UserInfo, Depends(get_current_user)],
) -> SessionResponse:
    session_id = create_session(current_user.id)
    return SessionResponse(session_id=session_id)

# 上传文档并快速解析，解析内容存储在redis中，供后续聊天使用
# 返回：解析结果摘要和文档标题，供前端展示
@router.post("/quick_parse")
async def quick_parse_current_session_document(
    current_user: Annotated[UserInfo, Depends(get_current_user)],
    session_id: Annotated[str, Query()],
    file: Annotated[UploadFile, File()],
) -> dict:
    file_content = await file.read()
    if not file_content:
        raise HTTPException(status_code=400, detail="文件内容为空")

    filename = file.filename or "未命名文档"
    return await quick_parse_service.quick_parse_document(
        current_user.id,
        session_id,
        file_content,
        filename,
    )

# 从redis获取解析后的内容，避免重复解析同一文档
@router.get("/get_parsed_content")
def read_parsed_content(
    current_user: Annotated[UserInfo, Depends(get_current_user)],
    session_id: Annotated[str, Query()],
) -> dict:
    return quick_parse_service.get_quick_parsed_document(str(current_user.id), session_id)


# 基于解析后的文档内容进行聊天
# 返回：流式响应
@router.post("/chat_on_docs")
async def chat_on_docs(
    current_user: Annotated[UserInfo, Depends(get_current_user)],
    session_id: Annotated[str, Query()],
    request: Annotated[ChatRequest, Body()],
) -> StreamingResponse:
    if not user_owns_session(current_user.id, session_id):
        raise HTTPException(status_code=404, detail="会话不存在或无权访问")

    return StreamingResponse(
        get_chat_completion(session_id, str(current_user.id), request.message),
        media_type="text/event-stream",
    )
