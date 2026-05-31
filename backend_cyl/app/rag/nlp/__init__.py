from __future__ import annotations

import re
from typing import Iterable


DEFAULT_CHUNK_TOKEN_NUM = 128
DEFAULT_DELIMITER = "\n!?;。；！？"


class SimpleTokenizer:
    """Small tokenizer used by backend_cyl's lightweight RAG path."""

    @staticmethod
    def tokenize(text: str) -> str:
        return " ".join(re.findall(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+|[^\s]", text or ""))

    @staticmethod
    def fine_grained_tokenize(tokenized_text: str) -> str:
        return tokenized_text or ""

    @staticmethod
    def strQ2B(text: str) -> str:
        return text

    @staticmethod
    def tradi2simp(text: str) -> str:
        return text

    @staticmethod
    def tag(token: str) -> str:
        return "n"

    @staticmethod
    def freq(token: str) -> int:
        return 1


rag_tokenizer = SimpleTokenizer()


def is_english(texts: Iterable[str]) -> bool:
    items = [item.strip() for item in texts if item and item.strip()]
    if not items:
        return False

    english_count = sum(1 for item in items if re.match(r"[A-Za-z0-9 ,.;:'\"!?()/-]", item))
    return english_count / len(items) > 0.8


def num_tokens_from_string(text: str) -> int:
    return len(rag_tokenizer.tokenize(text).split())


def find_codec(blob: bytes) -> str:
    for encoding in ("utf-8", "gb18030", "gbk"):
        try:
            blob.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    return "utf-8"


def _section_text(section: str | tuple[str, object]) -> str:
    return section if isinstance(section, str) else section[0]


def naive_merge(
    sections: list[str] | list[tuple[str, object]],
    chunk_token_num: int = DEFAULT_CHUNK_TOKEN_NUM,
    delimiter: str = DEFAULT_DELIMITER,
) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for section in sections:
        text = _section_text(section).strip()
        if not text:
            continue

        token_count = num_tokens_from_string(text)
        if current and current_tokens + token_count > chunk_token_num:
            chunks.append("\n".join(current))
            current = [text]
            current_tokens = token_count
        else:
            current.append(text)
            current_tokens += token_count

    if current:
        chunks.append("\n".join(current))
    return chunks


def naive_merge_docx(
    sections: list[tuple[str, object]],
    chunk_token_num: int = DEFAULT_CHUNK_TOKEN_NUM,
    delimiter: str = DEFAULT_DELIMITER,
) -> tuple[list[str], list[None]]:
    chunks = naive_merge(sections, chunk_token_num, delimiter)
    return chunks, [None for _ in chunks]


def tokenize(doc: dict, text: str, eng: bool = False) -> None:
    content_tokens = rag_tokenizer.tokenize(text)
    doc["content_with_weight"] = text
    doc["content_ltks"] = content_tokens
    doc["content_sm_ltks"] = rag_tokenizer.fine_grained_tokenize(content_tokens)


def _build_tokenized_doc(base_doc: dict, content: str) -> dict:
    item = dict(base_doc)
    tokenize(item, content)
    return item


def tokenize_chunks(chunks: list[str], doc: dict, eng: bool = False, pdf_parser=None) -> list[dict]:
    return [_build_tokenized_doc(doc, chunk) for chunk in chunks if chunk.strip()]


def tokenize_chunks_docx(chunks: list[str], doc: dict, eng: bool = False, images=None) -> list[dict]:
    return tokenize_chunks(chunks, doc, eng)


def tokenize_table(tbls, doc: dict, eng: bool = False, batch_size: int = 10) -> list[dict]:
    rows: list[dict] = []
    for table, _position in tbls or []:
        _image, content = table
        if isinstance(content, str) and content.strip():
            rows.append(_build_tokenized_doc(doc, content.strip()))
    return rows


def concat_img(img1, img2):
    return img1 or img2
