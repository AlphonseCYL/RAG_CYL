from io import BytesIO
from pathlib import Path

from docx import Document
from fastapi import HTTPException
import pdfplumber

from app.core.config import QUICK_PARSE_EXPIRE_SECONDS
from app.core.database import SessionLocal
from app.features.sessions.redis_store import (
    get_quick_parse_ttl,
    load_quick_parse_document,
    store_quick_parse_document,
)
from app.models.session import Session


SUPPORTED_FORMATS = {"txt", "docx", "pdf"}
MAX_CHARACTERS = 14000
MAX_PDF_PAGES = 4


def _get_file_type(filename: str) -> str:
    file_type = Path(filename or "").suffix.lower().lstrip(".")
    if file_type not in SUPPORTED_FORMATS:
        raise HTTPException(status_code=400, detail="仅支持 txt、docx、pdf 文件")
    return file_type


def _limit_text(content: str, file_type: str) -> str:
    content = content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="文件中没有解析到文本内容")
    if len(content) > MAX_CHARACTERS:
        raise HTTPException(
            status_code=400,
            detail=f"{file_type.upper()} 文本超过 {MAX_CHARACTERS} 字符，请先上传更短的文档",
        )
    return content


def _parse_txt(file_content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gbk", "gb2312"):
        try:
            return file_content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise HTTPException(status_code=400, detail="无法识别 TXT 文件编码")


def _parse_docx(file_content: bytes) -> tuple[str, int]:
    try:
        document = Document(BytesIO(file_content))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"DOCX 解析失败: {exc}") from exc

    paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    return "\n".join(paragraphs), len(document.paragraphs)


def _parse_pdf(file_content: bytes) -> tuple[str, int]:
    try:
        with pdfplumber.open(BytesIO(file_content)) as pdf:
            if len(pdf.pages) > MAX_PDF_PAGES:
                raise HTTPException(status_code=400, detail=f"PDF 页数不能超过 {MAX_PDF_PAGES} 页")
            page_count = len(pdf.pages)
            page_texts = [page.extract_text() or "" for page in pdf.pages]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"PDF 解析失败: {exc}") from exc

    return "\n".join(text.strip() for text in page_texts if text.strip()), page_count


def _ensure_session_owner(user_id: int, session_id: str) -> None:
    db = SessionLocal()
    try:
        session = (
            db.query(Session)
            .filter(Session.session_id == session_id, Session.user_id == user_id)
            .first()
        )
        if session is None:
            raise HTTPException(status_code=404, detail="会话不存在或无权访问")
    finally:
        db.close()


async def _quick_parse_document_impl(
    user_id: int,
    session_id: str,
    file_content: bytes,
    filename: str,
) -> dict:
    _ensure_session_owner(user_id, session_id)

    file_type = _get_file_type(filename)
    if file_type == "txt":
        content = _parse_txt(file_content)
    elif file_type == "docx":
        content, _ = _parse_docx(file_content)
    else:
        content, _ = _parse_pdf(file_content)

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
