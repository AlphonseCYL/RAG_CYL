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
