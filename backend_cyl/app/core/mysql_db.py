import pymysql
import re
from pymysql.connections import Connection
from pymysql.cursors import DictCursor

from app.core.config import (
    MYSQL_CHARSET,
    MYSQL_COLLATION,
    MYSQL_HOST,
    MYSQL_PASSWORD,
    MYSQL_PORT,
    MYSQL_USER,
    MYSQL_DATABASE_NAME,
)

# 建立与 MySQL 数据库的连接，连接到指定的数据库
# 返回一个 pymysql 的 Connection 对象，用于执行 SQL 查询和操作数据库
def create_mysql_connection() -> Connection:
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE_NAME,
        charset=MYSQL_CHARSET,
        cursorclass=DictCursor,
        autocommit=False,
    )


# MySQL 标识符必须由字母、数字、下划线或美元符号组成，且不能包含其他特殊字符
def _quote_identifier(identifier: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_$]+", identifier):
        raise ValueError(f"Invalid MySQL identifier: {identifier}")
    return f"`{identifier}`"

# 建立与 MySQL 数据库服务器的连接，不指定数据库
def create_mysql_server_connection() -> Connection:
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        charset=MYSQL_CHARSET,
        cursorclass=DictCursor,
        autocommit=True,
    )

# 确保 MySQL 数据库存在，如果不存在则创建它
def ensure_mysql_database() -> None:
    database_name = _quote_identifier(MYSQL_DATABASE_NAME)
    with create_mysql_server_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS {database_name} "
                f"DEFAULT CHARACTER SET {MYSQL_CHARSET} "
                f"COLLATE {MYSQL_COLLATION}"
            )
