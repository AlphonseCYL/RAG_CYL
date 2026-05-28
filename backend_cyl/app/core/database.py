from collections.abc import Generator
from urllib.parse import quote_plus

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker

from app.core.config import (
    MYSQL_CHARSET,
    MYSQL_COLLATION,
    MYSQL_DATABASE_NAME,
    MYSQL_HOST,
    MYSQL_PASSWORD,
    MYSQL_PORT,
    MYSQL_USER,
)
from app.models import Base


_user = quote_plus(MYSQL_USER)
_password = quote_plus(MYSQL_PASSWORD)
_database = MYSQL_DATABASE_NAME

SERVER_DATABASE_URL = f"mysql+pymysql://{_user}:{_password}@{MYSQL_HOST}:{MYSQL_PORT}/?charset={MYSQL_CHARSET}"
DATABASE_URL = (
    f"mysql+pymysql://{_user}:{_password}@{MYSQL_HOST}:{MYSQL_PORT}/{_database}"
    f"?charset={MYSQL_CHARSET}"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[DbSession, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    server_engine = create_engine(SERVER_DATABASE_URL, pool_pre_ping=True)
    database_name = _database.replace("`", "``")
    with server_engine.begin() as conn:
        conn.execute(
            text(
                f"CREATE DATABASE IF NOT EXISTS `{database_name}` "
                f"CHARACTER SET {MYSQL_CHARSET} COLLATE {MYSQL_COLLATION}"
            )
        )

    Base.metadata.create_all(bind=engine)
    _ensure_messages_schema()


def _column_exists(table_name: str, column_name: str) -> bool:
    with engine.connect() as conn:
        result = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM information_schema.columns
                WHERE table_schema = :database_name
                  AND table_name = :table_name
                  AND column_name = :column_name
                """
            ),
            {
                "database_name": _database,
                "table_name": table_name,
                "column_name": column_name,
            },
        )
        return int(result.scalar() or 0) > 0


def _ensure_messages_schema() -> None:
    message_columns = {
        "user_question": "ADD COLUMN user_question LONGTEXT NULL",
        "model_answer": "ADD COLUMN model_answer LONGTEXT NULL",
        "documents": "ADD COLUMN documents LONGTEXT NULL",
        "recommended_questions": "ADD COLUMN recommended_questions LONGTEXT NULL",
        "think": "ADD COLUMN think LONGTEXT NULL",
        "created_at": "ADD COLUMN created_at VARCHAR(64) NULL",
        "updated_at": "ADD COLUMN updated_at VARCHAR(64) NULL",
    }

    with engine.begin() as conn:
        for column_name, ddl in message_columns.items():
            if not _column_exists("messages", column_name):
                conn.execute(text(f"ALTER TABLE messages {ddl}"))

        conn.execute(text("UPDATE messages SET user_question = '' WHERE user_question IS NULL"))
        conn.execute(text("UPDATE messages SET model_answer = '' WHERE model_answer IS NULL"))
        conn.execute(text("UPDATE messages SET documents = '[]' WHERE documents IS NULL"))
        conn.execute(text("UPDATE messages SET recommended_questions = '[]' WHERE recommended_questions IS NULL"))
        conn.execute(text("UPDATE messages SET think = '' WHERE think IS NULL"))
        conn.execute(text("UPDATE messages SET created_at = NOW() WHERE created_at IS NULL"))
        conn.execute(text("UPDATE messages SET updated_at = NOW() WHERE updated_at IS NULL"))

        conn.execute(text("ALTER TABLE messages MODIFY user_question LONGTEXT NOT NULL"))
        conn.execute(text("ALTER TABLE messages MODIFY model_answer LONGTEXT NOT NULL"))
        conn.execute(text("ALTER TABLE messages MODIFY documents LONGTEXT NOT NULL"))
        conn.execute(text("ALTER TABLE messages MODIFY recommended_questions LONGTEXT NOT NULL"))
        conn.execute(text("ALTER TABLE messages MODIFY think LONGTEXT NOT NULL"))
