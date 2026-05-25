from io import BytesIO
from pathlib import Path

from fastapi import HTTPException, UploadFile
from docx import Document
import pdfplumber


from app.core.config import QUICK_PARSE_EXPIRE_SECONDS
from app.core.database import get_connection
from app.features.sessions.redis_store import (
    get_quick_parse_ttl,
    load_quick_parse_document,
    store_quick_parse_document,
)


SUPPORTED_FORMATS = {"txt", "docx", "pdf"}
MAX_CHARACTERS = 14000
MAX_PDF_PAGES = 4


# 输入：文件名str
# 判断文件类型是否受支持（txt、docx、pdf）
# 返回：文件类型str（txt、docx、pdf）或抛出异常
def _get_file_type(filename: str) -> str:
    file_type = Path(filename or "").suffix.lower().lstrip(".")
    if file_type not in SUPPORTED_FORMATS:
        raise HTTPException(status_code=400, detail="仅支持 txt、docx、pdf 文件")
    return file_type


def _limit_text(content: str, file_type: str) -> str:
    ''' 限制文本长度，去除首尾空白 '''
    content = content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="文件中没有解析到文本内容")
    if len(content) > MAX_CHARACTERS:
        raise HTTPException(
            status_code=400,
            detail=f"{file_type.upper()} 文本超过 {MAX_CHARACTERS} 字符，请先上传更短的文档",
        )
    return content

# 输入：文件内容bytes
# 尝试使用多种编码解析文本内容，直到成功或所有编码都失败
# 返回：解析后的文本内容str或抛出异常
def _parse_txt(file_content: bytes) -> str:
    ''' 解析TXT文件，尝试多种编码，返回文本内容 '''
    for encoding in ("utf-8-sig", "utf-8", "gbk", "gb2312"):
        try:
            return file_content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise HTTPException(status_code=400, detail="无法识别 TXT 文件编码")

# 输入：文件内容bytes
# 使用 python-docx 库解析 DOCX 文件内容，提取文本并合并成一个字符串
# 返回：解析后的文本内容str或抛出异常
def _parse_docx(file_content: bytes) -> tuple[str, int]:
    ''' 解析DOCX文件，返回文本内容 和段落数 '''
    try:
        document = Document(BytesIO(file_content))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"DOCX 解析失败: {exc}") from exc

    paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    return "\n".join(paragraphs), len(document.paragraphs)

# 输入：文件内容bytes
# 使用 pdfplumber 库解析 PDF 文件内容，提取每页文本并合并成一个字符串
# 返回：解析后的文本内容str或抛出异常
def _parse_pdf(file_content: bytes) -> tuple[str, int]:
    ''' 解析PDF文件，返回文本内容 和页数 '''
    try:
        with pdfplumber.open(BytesIO(file_content)) as pdf:
            if len(pdf.pages) > MAX_PDF_PAGES:
                raise HTTPException(status_code=400, detail=f"PDF 页数不能超过 {MAX_PDF_PAGES} 页")
            page_texts = [page.extract_text() or "" for page in pdf.pages]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"PDF 解析失败: {exc}") from exc

    return "\n".join(text.strip() for text in page_texts if text.strip()), len(pdf.pages)

# 输入：用户id和会话id
# 判断该会话是否存在数据库
# 无返回
def _ensure_session_owner(user_id: int, session_id: str) -> None:
    ''' 判断该会话是否存在数据库 '''
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT 1
                FROM sessions
                WHERE session_id = %s AND user_id = %s
                LIMIT 1
                """,
                (session_id, user_id),
            )
            if cursor.fetchone() is None:
                raise HTTPException(status_code=404, detail="会话不存在或无权访问")


###############################################
#   输入：用户id、会话id、上传的文件
#   快速解析文件内容并存储到Redis，设置过期时间
#   返回：解析结果和相关信息
###############################################
# @router.post("/quick_parse")
async def _quick_parse_document_impl(
        user_id: int, 
        session_id: str, 
        file_content: bytes, 
        filename: str
        ) -> dict:
    
    _ensure_session_owner(user_id, session_id)

    file_type = _get_file_type(filename)
    if file_type == "txt":
        content = _parse_txt(file_content)
    elif file_type == "docx":
        content, para_count = _parse_docx(file_content)
    else:
        content, page_count = _parse_pdf(file_content)

    content = _limit_text(content, file_type)
    payload = {
        "session_id": session_id,
        "user_id": user_id,
        "filename": filename,
        "file_type": file_type,
        "content": content,
        "content_length": len(content),
    }
    store_quick_parse_document(session_id, payload)

    if file_type == "pdf":
        limit_info = f"PDF页数限制: {MAX_PDF_PAGES}页"
    else:
        limit_info = f"字符数限制: {MAX_CHARACTERS}字符"

    return {
        "status": "success",
        "message": "文档解析完成，后续提问会自动参考当前会话文档",
        "session_id": session_id,
        "filename": filename,
        "file_type": file_type,
        "content_length": len(content),
        "limit_info": limit_info,
        "expiry_hours": QUICK_PARSE_EXPIRE_SECONDS // 3600,
    }


# @router.get("/get_parsed_content")

# 输入：用户id、会话id
# 从Redis获取该会话id解析后的文档内容和相关信息
# 输出：redis存储的解析结果和相关信息，若无数据则抛出异常
def _get_quick_parse_document_impl(user_id: int, session_id: str) -> dict | None:
    document = load_quick_parse_document(session_id)
    if document is None:
        return None
    if str(document.get("user_id")) != str(user_id):
        return None
    return document


def _get_parsed_content_impl(user_id: int, session_id: str) -> dict:
    document = _get_quick_parse_document_impl(user_id, session_id)
    if document is None:
        raise HTTPException(status_code=404, detail="当前会话还没有快速解析文档，可能已过期或尚未上传")

    ttl = get_quick_parse_ttl(session_id)

    return {
        "status": "success",
        "session_id": session_id,
        "filename": document["filename"],
        "file_type": document["file_type"],
        "content": document["content"],
        "content_length": document["content_length"],
        "remaining_seconds": ttl,
    }


class QuickParseService:
    """Quick parse service for current-session temporary documents."""

    async def quick_parse_document(
        self,
        user_id: int,
        session_id: str,
        file_content: bytes,
        filename: str,
    ) -> dict:
        return await _quick_parse_document_impl(user_id, session_id, file_content, filename)

    def get_quick_parse_document(self, user_id: int, session_id: str) -> dict | None:
        return _get_quick_parse_document_impl(user_id, session_id)

    def get_parsed_content(self, user_id: int, session_id: str) -> dict:
        return _get_parsed_content_impl(user_id, session_id)


quick_parse_service = QuickParseService()
