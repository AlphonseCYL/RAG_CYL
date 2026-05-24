from datetime import datetime, timezone
import uuid

from app.core.database import get_connection


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
