import json

import redis
from fastapi import HTTPException

from app.core.config import QUICK_PARSE_EXPIRE_SECONDS, REDIS_DB, REDIS_HOST, REDIS_PORT


redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    decode_responses=True,
)




# 输入：会话id和要存储的文档内容（以字典形式）。
# 功能：将文档内容存储在Redis中，并设置过期时间。
# 返回：无。如果存储过程中发生Redis错误，会抛出HTTPException异常，状态码为503
def store_quick_parsed_document_to_redis(session_id: str, payload: dict) -> None:
    try:
        redis_client.setex(
            f"quick_parse:{session_id}",
            QUICK_PARSE_EXPIRE_SECONDS,
            json.dumps(payload, ensure_ascii=False),
        )
    except redis.RedisError as exc:
        raise HTTPException(status_code=503, detail=f"Redis store failed: {exc}") from exc

# 输入：会话id。
# 功能：从Redis中获取与会话id绑定的已解析文档内容
# 返回：文档内容；如果获取过程中发生Redis错误，会抛出HTTPException异常，状态码为503；
def load_quick_parsed_document_from_redis(session_id: str) -> dict:
    try:
        raw_value = redis_client.get(f"quick_parse:{session_id}")
    except redis.RedisError as exc:
        raise HTTPException(status_code=503, detail=f"Redis read failed: {exc}") from exc

    if not raw_value:
        return {}

    try:
        return json.loads(raw_value)
    except json.JSONDecodeError:
        return {
            "session_id": session_id,
            "filename": "current session document",
            "file_type": "unknown",
            "content": raw_value,
            "content_length": len(raw_value),
        }

# 输入：会话id。
# 功能：获得与会话id相关的文档在Redis中的剩余TTL（以秒为单位）。
# 返回：剩余TTL；如果获取过程中发生Redis错误，会返回-1。
def get_quick_parsed_doc_ttl(session_id: str):
    try:
        return redis_client.ttl(f"quick_parse:{session_id}")
    except redis.RedisError:
        return -1
