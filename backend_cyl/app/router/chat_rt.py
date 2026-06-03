import logging
import os
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session as DbSession

from app.core.database import (
    create_knowledgebase_record,
    get_db,
    get_user_knowledgebase,
    insert_knowledgebase_file,
    knowledgebase_file_exists,
    list_user_knowledgebases,
)
from app.features.auth.security import get_current_user
from app.features.auth.schemas import UserInfo
from app.features.sessions.quick_parse_service import quick_parse_service
from app.features.sessions.schemas import ChatRequest, SessionResponse
from app.features.sessions.service import (
    create_session,
    get_chat_completion,
    user_owns_session,
)
from app.features.knowledgebase.schemas import (
    CreateKnowledgeBaseRequest,
    CreateKnowledgeBaseResponse,
    KnowledgeBaseItem,
    KnowledgeBaseListResponse,
)
from app.rag.utils.file_utils import get_project_base_dir
from app.features.file_parse.file_parse import execute_insert_file_to_es
from app.features.file_parse.schemas import DocumentUploadResponse, SessionDocumentsResponse
from app.features.retrieval.retrieval import retrieve_content


router = APIRouter(tags=["chat"])
logger = logging.getLogger(__name__)


##################创建会话接口##################
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


############### 创建知识库接口###############
@router.post("/insert_knowledgebase")
def create_knowledgebase(
    current_user: Annotated[UserInfo, Depends(get_current_user)],
    request: Annotated[CreateKnowledgeBaseRequest, Body()],
) -> CreateKnowledgeBaseResponse:
    knowledgebase_name = request.knowledgebase_name.strip()
    if not knowledgebase_name:
        raise HTTPException(status_code=400, detail="知识库名称不能为空")

    knowledgebase = create_knowledgebase_record(
        user_id=current_user.id,
        knowledgebase_name=knowledgebase_name,
        knowledgebase_dir=get_project_base_dir("storage"),
    )
    os.makedirs(knowledgebase.knowledgebase_dir, exist_ok=True)

    return CreateKnowledgeBaseResponse(
        knowledge_id=knowledgebase.knowledge_id,
        user_id=str(current_user.id),
        knowledgebase_name=knowledgebase.knowledgebase_name,
        knowledgebase_dir=knowledgebase.knowledgebase_dir,
        status="success",
        message=f"知识库 {knowledgebase.knowledgebase_name} 创建成功",
    )


@router.get("/knowledgebases", response_model=KnowledgeBaseListResponse)
def list_knowledgebase(
    current_user: Annotated[UserInfo, Depends(get_current_user)],
) -> KnowledgeBaseListResponse:
    items = [
        KnowledgeBaseItem(**item)
        for item in list_user_knowledgebases(current_user.id)
    ]
    return KnowledgeBaseListResponse(knowledgebases=items)

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
    try:
        if not user_owns_session(current_user.id, session_id):
            raise HTTPException(status_code=404, detail="会话不存在或无权访问")
        
        logger.info(f"开始处理用户 {str(current_user.id)} 的请求")
        logger.info(f"问题内容: {request.message}")

        question = request.message
        references = []

        # 从知识库检索，可以不返回内容
        references = []
        try:
            logger.info("开始从知识库检索相关内容...")
            knowledge_ids = [
                item["knowledge_id"]
                for item in list_user_knowledgebases(current_user.id)
            ]
            if knowledge_ids:
                references = retrieve_content(index_name=knowledge_ids, user_question=question)
            logger.info(f"检索到f{len(references)}个相关片段")
        


        except Exception as e:
            logger.warning(f"Knowledge base retrieval failed, continue without references: {e}")

        return StreamingResponse(
            get_chat_completion(session_id, str(current_user.id), question, references),
            media_type="text/event-stream",
        )
    except HTTPException as e:
        logger.error(f"HTTP错误:{str(e)}")
        raise e
    except Exception as e:
        logger.exception(f"发生未知错误:{str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


################################
#   上传文档
################################
@router.post("/upload_files")
async def upload_files(
    current_user: Annotated[UserInfo, Depends(get_current_user)],
    files: Annotated[list[UploadFile], File()],
    db: Annotated[DbSession, Depends(get_db)],
    session_id: Annotated[str, Query()],
    knowledge_id: Annotated[str, Form()],
):
    try:
        # 确保当前用户已认证
        user_id = str(current_user.id)
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

        # 确保会话ID存在且属于当前用户
        if not user_owns_session(current_user.id, session_id):
            raise HTTPException(status_code=404, detail="会话不存在或无权访问")

        knowledgebase = get_user_knowledgebase(current_user.id, knowledge_id)
        if knowledgebase is None:
            raise HTTPException(status_code=404, detail="知识库不存在或无权访问")

        # 保存路径为 storage/{user_id}/{knowledge_id}
        knowledge_dir = knowledgebase.knowledgebase_dir
        if not os.path.exists(knowledge_dir):
            os.makedirs(knowledge_dir)

        upload_filenames: list[str] = []# 用于记录本次上传的文件名，后续检查重复
        duplicate_filenames: set[str] = set()# 用于记录本次上传中与已存在文件名重复的文件
        seen_filenames: set[str] = set()# 用于检测本次上传中是否有重复文件名
        for file in files:
            file_name = Path(file.filename or "").name
            if not file_name:
                raise HTTPException(status_code=400, detail="文件名不能为空")
            if file_name in seen_filenames:
                duplicate_filenames.add(file_name)
            seen_filenames.add(file_name)
            upload_filenames.append(file_name)

        # 获取知识库目录中的现有文件名
        existing_filenames = {
            entry.name for entry in Path(knowledge_dir).iterdir() if entry.is_file()
        }
        # 检查上传文件名与文件夹已存在文件名的重复情况，避免覆盖已存在的文件
        duplicate_filenames.update(
            filename
            for filename in upload_filenames
            if filename in existing_filenames
            or knowledgebase_file_exists(current_user.id, knowledge_id, filename)
        )

        # 如果有重复文件名，拒绝上传并返回错误提示，要求用户修改文件名后重新上传
        if duplicate_filenames:
            raise HTTPException(
                status_code=400,
                detail={
                    "status": "failed",
                    "message": "文件名重复，请修改文件名后重新上传，避免覆盖已存在的文件",
                    "duplicate_files": sorted(duplicate_filenames),
                },
            )
        
        # 文件上传
        successfully_uploaded_files: list[str] = []
        failed_uploaded_files: list[str] = []

        for file in files:
            file_name = Path(file.filename or "").name
            file_path = os.path.join(knowledge_dir, file_name)
            try:
                # 以二进制方式写入文件内容，确保文件内容不受编码问题影响
                file_content = await file.read()

                # 验证内容是否为空，避免创建空文件
                if not file_content:
                    failed_uploaded_files.append(f"{file_name}: 文件内容为空")
                    continue
                
                # 将文件内容写入磁盘，确保文件正确保存到服务器指定位置
                with open(file_path, "wb") as f:
                    f.write(file_content)
                
                # 验证文件大小是否与上传内容匹配，确保文件内容完整无损地保存到服务器
                if os.path.getsize(file_path) != len(file_content):
                    failed_uploaded_files.append(f"{file_name}: 文件保存失败，内容不匹配")
                    os.remove(file_path)  # 删除不匹配的文件
                
                file_url = file_path

                # 解析和插入ES
                try:
                    execute_insert_file_to_es(file_url=file_url, file_name=file_name, index_name=knowledge_id)
                    print(f"数据插入es索引{knowledge_id}成功:{file_url}")
                    logger.info(f"数据插入es索引{knowledge_id}成功:{file_url}")

                    insert_knowledgebase_file(
                        current_user.id,
                        knowledge_id,
                        session_id,
                        file_name,
                        file_url,
                    )
                    print((f"数据插入knowledgebase成功: {file_name}"))
                    logger.info(f"数据插入knowledgebase成功: {file_name}")

                    successfully_uploaded_files.append(file_name)

                except Exception as parse_and_insert_error:
                    print((f"文件解析失败 {file_name}: {str(parse_and_insert_error)}"))
                    logger.error(f"文件解析失败 {file_name}: {str(parse_and_insert_error)}")
                    failed_uploaded_files.append(f"{file_name}: 文件解析失败 - {str(parse_and_insert_error)}")
                    # 删除已保存的文件
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    continue
            
            except Exception as exc:
                logger.error(f"处理文件失败 {file_name}: {str(exc)}")
                failed_uploaded_files.append(f"{file_name}: 处理失败 - {str(exc)}")

        # 构建返回结果
        if successfully_uploaded_files and not failed_uploaded_files:
            return {
                "status": "success",
                "message": "所有文件解析成功",
                "successful_files": successfully_uploaded_files,
                "total_files": len(files)
            }
        elif successfully_uploaded_files and failed_uploaded_files:
            return {
                "status": "partial_success",
                "message": f"部分文件解析成功，{len(successfully_uploaded_files)} 个成功，{len(failed_uploaded_files)} 个失败",
                "successful_files": successfully_uploaded_files,
                "failed_files": failed_uploaded_files,
                "total_files": len(files)
            }
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "status": "failed",
                    "message": "所有文件解析失败",
                    "failed_files": failed_uploaded_files,
                    "total_files": len(files)
                }
            )


    except HTTPException as e:
        raise e
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc



##################################
# 快速解析路段查询会话文档上传信息接口
##################################
@router.get("sessions/{session_id}/documents",response_model = SessionDocumentsResponse)
async def get_session_documents(
    session_id: str,
    current_user: Annotated[UserInfo, Depends(get_current_user)],
    db:DbSession = Depends(get_db)
):
    '''
    获取指定会话的文档上传摘要信息
    '''
    try:
        user_id = str(current_user.id)
        if not user_id:
            raise HTTPException(status_code=401, detail="用户验证未通过")
        
        # 检查是否有上传的文档

        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
