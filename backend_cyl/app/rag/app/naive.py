from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path
from typing import Any, Callable

import pdfplumber
from docx import Document


Callback = Callable[..., None]
DEFAULT_CHUNK_TOKEN_NUM = 128
DEFAULT_DELIMITER = "\n!?;。；！？"


def _noop_callback(*args: Any, **kwargs: Any) -> None:
    pass


def _guess_encoding(blob: bytes) -> str:
    for encoding in ("utf-8", "gb18030", "gbk"):
        try:
            blob.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    return "utf-8"


def _read_text(filename: str, binary: bytes | None = None) -> str:
    if binary is not None:
        return binary.decode(_guess_encoding(binary), errors="ignore")

    with open(filename, "rb") as file:
        blob = file.read()
    return blob.decode(_guess_encoding(blob), errors="ignore")


def _simple_tokenize(text: str) -> str:
    '''
    找到中文、英文单词、数字、下划线、连字符、标点符号等，并用空格分隔开来，作为简单的分词结果
    '''
    return " ".join(re.findall(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+|[^\s]", text))


def _fine_grained_tokenize(tokenized_text: str) -> str:
    return tokenized_text


def _token_count(text: str) -> int:
    return len(_simple_tokenize(text).split())


def _split_text(text: str, delimiter: str = DEFAULT_DELIMITER) -> list[str]:
    if not text:
        return []

    lines = [line.strip() for line in text.replace("\r\n", "\n").split("\n")]
    sections: list[str] = []
    for line in lines:
        if not line:
            continue
        parts = re.split(f"([{re.escape(delimiter)}])", line)
        sentence = ""
        for part in parts:
            if not part:
                continue
            sentence += part
            if part in delimiter:
                sections.append(sentence.strip())
                sentence = ""
        if sentence.strip():
            sections.append(sentence.strip())
    return sections


def _merge_sections(sections: list[str], chunk_token_num: int) -> list[str]:
    '''
    合并文本片段，使得每个片段的长度不超过chunk_token_num
    '''
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for section in sections:
        section_tokens = _token_count(section)
        if current and current_tokens + section_tokens > chunk_token_num:
            chunks.append("\n".join(current))
            current = [section]
            current_tokens = section_tokens
        else:
            current.append(section)
            current_tokens += section_tokens

    if current:
        chunks.append("\n".join(current))
    return chunks


def _parse_pdf(filename: str, binary: bytes | None, from_page: int, to_page: int) -> list[str]:
    '''
    返回一个列表，列表中的元素是pdf文件中的每一页
    示例：
    [page 1]
    这是第一页的内容
    这是第二行
    这是第三行
    [page 2]
    这是第二页的内容
    这是第二行
    这是第三行
    '''
    source = BytesIO(binary) if binary is not None else filename

    sections: list[str] = []

    with pdfplumber.open(source) as pdf:
        pages = pdf.pages[from_page:to_page]
        for page_number, page in enumerate(pages, start=from_page + 1):
            text = page.extract_text() or ""
            if text.strip():
                sections.append(f"[page {page_number}]\n{text.strip()}")

    return sections


def _parse_docx(filename: str, binary: bytes | None) -> list[str]:
    '''
    返回一个列表，列表中的元素是docx文件中的每一段文本或表格行
    示例：
    [
    string1: 这是第一段文本,
    string2: 这是第二段文本,
    string3: 这是第三段文本,
    string4: 这是第一行表格内容1 | 这是第一行表格内容2,
    string5: 这是第二行表格内容1 | 这是第二行表格内容2,
    ]
    '''
    document = Document(BytesIO(binary)) if binary is not None else Document(filename)
    sections = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]

    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                sections.append(" | ".join(cells))

    return sections


def _parse_markdown(filename: str, binary: bytes | None) -> list[str]:
    text = _read_text(filename, binary)
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^[#>*\-\s]+", "", text, flags=re.MULTILINE)
    return _split_text(text)


def _parse_plain_text(filename: str, binary: bytes | None) -> list[str]:
    return _split_text(_read_text(filename, binary))


def _build_doc(filename: str) -> dict[str, str]:
    name = Path(filename).name
    title = re.sub(r"\.[A-Za-z0-9]+$", "", name)
    title_tokens = _simple_tokenize(title)
    return {
        "docnm_kwd": name,
        "title_tks": title_tokens,
        "title_sm_tks": _fine_grained_tokenize(title_tokens),
    }


def _build_chunk(doc: dict[str, str], content: str) -> dict[str, str]:
    content_tokens = _simple_tokenize(content)
    return {
        **doc,
        "content_with_weight": content,
        "content_ltks": content_tokens,
        "content_sm_ltks": _fine_grained_tokenize(content_tokens),
    }


def chunk(
    filename: str,
    binary: bytes | None = None,
    from_page: int = 0,
    to_page: int = 100000,
    lang: str = "Chinese",
    callback: Callback | None = None,
    **kwargs: Any,
) -> list[dict[str, str]]:
    """Parse a supported file and return text chunks for ES insertion."""

    callback = callback or _noop_callback
    parser_config = kwargs.get("parser_config", {})
    chunk_token_num = int(parser_config.get("chunk_token_num", DEFAULT_CHUNK_TOKEN_NUM))
    suffix = Path(filename).suffix.lower()

    callback(0.1, "Start parsing file.")
    if suffix == ".pdf":
        sections = _parse_pdf(filename, binary, from_page, to_page)
    elif suffix == ".docx":
        sections = _parse_docx(filename, binary)
    elif suffix in {".txt", ".py", ".js", ".java", ".c", ".cpp", ".h", ".php", ".go", ".ts", ".sh", ".cs", ".kt", ".sql"}:
        sections = _parse_plain_text(filename, binary)
    elif suffix in {".md", ".markdown"}:
        sections = _parse_markdown(filename, binary)
    else:
        raise NotImplementedError("Only pdf, docx, txt/code, and markdown files are supported.")
    callback(0.8, "Finish parsing file.")

    # 拼凑sections为chunks，要求每个chunk的token数量不超过chunk_token_num
    # 这里优化可以用滑动窗口，每次只处理一个chunk，然后根据当前chunk的token数量判断是否需要移动滑动窗口的起始位置
    chunks = _merge_sections(sections, chunk_token_num)

    # 构建doc和chunk
    doc = _build_doc(filename)
    return [_build_chunk(doc, item) for item in chunks if item.strip()]
