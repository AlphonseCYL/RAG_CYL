from datetime import datetime, timezone
import uuid

from app.core.database import get_connection
from pymysql.cursors import DictCursor

# 根据用户id创建会话，返回会话id
def create_session(user_id: int) -> str:
    session_id = uuid.uuid4().hex[:16]
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO sessions (session_id, user_id, name, created_at)
                VALUES (%s, %s, %s, %s)
                """,
                (session_id, user_id, "新对话", now),
            )

    return session_id

# 根据用户id在数据库读取该用户所有会话，返回会话列表list[dict]
def get_sessions(user_id: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(DictCursor) as cursor:
            cursor.execute(
                """
                SELECT session_id, name, created_at
                FROM sessions
                WHERE user_id = %s
                ORDER BY created_at DESC
                """,
                (user_id,),
            )
            return list(cursor.fetchall())

# 根据用户id和会话id删除会话
def delete_session(user_id: int, session_id: str) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM sessions
                WHERE user_id = %s AND session_id = %s
                """,
                (user_id, session_id),
            )
            return cursor.rowcount > 0
