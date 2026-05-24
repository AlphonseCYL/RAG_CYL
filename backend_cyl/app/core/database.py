from collections.abc import Iterator
from contextlib import contextmanager

from pymysql.connections import Connection

from app.core.mysql_db import create_mysql_connection, ensure_mysql_database


@contextmanager
def get_connection() -> Iterator[Connection]:
    conn = create_mysql_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    ensure_mysql_database()

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    username VARCHAR(50) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    created_at VARCHAR(64) NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id VARCHAR(32) PRIMARY KEY,
                    user_id INT NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    created_at VARCHAR(64) NOT NULL,
                    CONSTRAINT fk_sessions_user
                        FOREIGN KEY (user_id) REFERENCES users (id)
                        ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
