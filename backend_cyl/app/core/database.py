from collections.abc import Generator
from datetime import datetime, timezone
import os
from urllib.parse import quote_plus
import uuid

from sqlalchemy import create_engine, func, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker

from app.db_models import Base
from app.db_models.knowledgebase import KnowledgeBase, KnowledgeBaseFile

from dotenv import load_dotenv

load_dotenv()  # 加载 .env 文件中的环境变量

MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "0000")
MYSQL_DATABASE_NAME = os.getenv("MYSQL_DATABASE_NAME", "cyl_db")
MYSQL_CHARSET = os.getenv("MYSQL_CHARSET", "utf8mb4")
MYSQL_COLLATION = os.getenv("MYSQL_COLLATION", "utf8mb4_general_ci")

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
    _ensure_knowledgebase_schema()


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


def _ensure_knowledgebase_schema() -> None:
    knowledgebase_columns = {
        "knowledge_id": "ADD COLUMN knowledge_id VARCHAR(32) NULL",
        "knowledgebase_name": "ADD COLUMN knowledgebase_name VARCHAR(255) NULL",
        "knowledgebase_dir": "ADD COLUMN knowledgebase_dir VARCHAR(1024) NULL",
        "session_id": "ADD COLUMN session_id VARCHAR(32) NULL",
        "file_name": "ADD COLUMN file_name VARCHAR(1024) NULL",
        "file_path": "ADD COLUMN file_path VARCHAR(1024) NULL",
        "created_at": "ADD COLUMN created_at VARCHAR(64) NULL",
        "updated_at": "ADD COLUMN updated_at VARCHAR(64) NULL",
    }

    with engine.begin() as conn:
        for column_name, ddl in knowledgebase_columns.items():
            if not _column_exists("knowledgebases", column_name):
                conn.execute(text(f"ALTER TABLE knowledgebases {ddl}"))

        conn.execute(text("ALTER TABLE knowledgebases MODIFY session_id VARCHAR(32) NULL"))
        conn.execute(text("ALTER TABLE knowledgebases MODIFY file_name VARCHAR(1024) NULL"))
        conn.execute(text("ALTER TABLE knowledgebases MODIFY file_path VARCHAR(1024) NULL"))

        conn.execute(
            text(
                """
                UPDATE knowledgebases
                SET knowledge_id = CONCAT('kb_', LPAD(id, 12, '0'))
                WHERE knowledge_id IS NULL OR knowledge_id = ''
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE knowledgebases
                SET knowledgebase_name = COALESCE(file_name, CONCAT('知识库-', id))
                WHERE knowledgebase_name IS NULL OR knowledgebase_name = ''
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE knowledgebases
                SET knowledgebase_dir = CONCAT('storage/', user_id, '/', knowledge_id)
                WHERE knowledgebase_dir IS NULL OR knowledgebase_dir = ''
                """
            )
        )
        conn.execute(text("UPDATE knowledgebases SET created_at = NOW() WHERE created_at IS NULL"))
        conn.execute(text("UPDATE knowledgebases SET updated_at = NOW() WHERE updated_at IS NULL"))
        conn.execute(text("ALTER TABLE knowledgebases MODIFY knowledge_id VARCHAR(32) NOT NULL"))
        conn.execute(text("ALTER TABLE knowledgebases MODIFY knowledgebase_name VARCHAR(255) NOT NULL"))
        conn.execute(text("ALTER TABLE knowledgebases MODIFY knowledgebase_dir VARCHAR(1024) NOT NULL"))
        conn.execute(text("ALTER TABLE knowledgebases MODIFY created_at VARCHAR(64) NOT NULL"))
        conn.execute(text("ALTER TABLE knowledgebases MODIFY updated_at VARCHAR(64) NOT NULL"))

        if not _index_exists("knowledgebases", "ux_knowledgebases_knowledge_id"):
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX ux_knowledgebases_knowledge_id "
                    "ON knowledgebases (knowledge_id)"
                )
            )


def _index_exists(table_name: str, index_name: str) -> bool:
    with engine.connect() as conn:
        result = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM information_schema.statistics
                WHERE table_schema = :database_name
                  AND table_name = :table_name
                  AND index_name = :index_name
                """
            ),
            {
                "database_name": _database,
                "table_name": table_name,
                "index_name": index_name,
            },
        )
        return int(result.scalar() or 0) > 0


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def create_knowledgebase_record(
    user_id: int,
    knowledgebase_name: str,
    knowledgebase_dir: str,
) -> KnowledgeBase:
    _ensure_knowledgebase_schema()
    db = SessionLocal()
    try:
        knowledgebase = KnowledgeBase(
            user_id=user_id,
            knowledge_id=uuid.uuid4().hex[:16],
            knowledgebase_name=knowledgebase_name,
            knowledgebase_dir=knowledgebase_dir,
            created_at=_utc_now(),
            updated_at=_utc_now(),
        )
        knowledgebase.knowledgebase_dir = os.path.join(
            knowledgebase_dir,
            str(user_id),
            knowledgebase.knowledge_id,
        )
        db.add(knowledgebase)
        db.commit()
        db.refresh(knowledgebase)
        return knowledgebase
    except SQLAlchemyError as e:
        db.rollback()
        raise RuntimeError(f"创建知识库失败:{str(e)}") from e
    finally:
        db.close()


def list_user_knowledgebases(user_id: int) -> list[dict]:
    db = SessionLocal()
    try:
        knowledgebases = (
            db.query(KnowledgeBase)
            .filter(KnowledgeBase.user_id == user_id)
            .order_by(KnowledgeBase.created_at.desc(), KnowledgeBase.id.desc())
            .all()
        )
        file_counts = {
            row.knowledge_id: row.file_count
            for row in db.query(
                KnowledgeBaseFile.knowledge_id,
                func.count(KnowledgeBaseFile.id).label("file_count"),
            )
            .filter(KnowledgeBaseFile.user_id == user_id)
            .group_by(KnowledgeBaseFile.knowledge_id)
            .all()
        }
        return [
            {
                "knowledge_id": item.knowledge_id,
                "user_id": str(item.user_id),
                "knowledgebase_name": item.knowledgebase_name,
                "knowledgebase_dir": item.knowledgebase_dir,
                "file_count": int(file_counts.get(item.knowledge_id, 0) or 0),
                "created_at": item.created_at,
                "updated_at": item.updated_at,
            }
            for item in knowledgebases
        ]
    finally:
        db.close()


def get_user_knowledgebase(user_id: int, knowledge_id: str) -> KnowledgeBase | None:
    db = SessionLocal()
    try:
        return (
            db.query(KnowledgeBase)
            .filter(KnowledgeBase.user_id == user_id, KnowledgeBase.knowledge_id == knowledge_id)
            .first()
        )
    finally:
        db.close()


def insert_knowledgebase_file(
    user_id: int,
    knowledge_id: str,
    session_id: str | None,
    file_name: str,
    file_path: str,
) -> None:
    db = SessionLocal()
    try:
        db.add(
            KnowledgeBaseFile(
                user_id=user_id,
                knowledge_id=knowledge_id,
                session_id=session_id,
                file_name=file_name,
                file_path=file_path,
                created_at=_utc_now(),
            )
        )
        knowledgebase = (
            db.query(KnowledgeBase)
            .filter(KnowledgeBase.user_id == user_id, KnowledgeBase.knowledge_id == knowledge_id)
            .first()
        )
        if knowledgebase is not None:
            knowledgebase.session_id = session_id
            knowledgebase.file_name = file_name
            knowledgebase.file_path = file_path
            knowledgebase.updated_at = _utc_now()
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        raise RuntimeError(f"插入MySQL数据库表knowledgebase_files失败:{str(e)}") from e
    finally:
        db.close()


def knowledgebase_file_exists(user_id: int, knowledge_id: str, file_name: str) -> bool:
    db = SessionLocal()
    try:
        return (
            db.query(KnowledgeBaseFile)
            .filter(
                KnowledgeBaseFile.user_id == user_id,
                KnowledgeBaseFile.knowledge_id == knowledge_id,
                KnowledgeBaseFile.file_name == file_name,
            )
            .first()
            is not None
        )
    finally:
        db.close()
