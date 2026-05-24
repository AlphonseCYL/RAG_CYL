import os

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

if load_dotenv:
    load_dotenv()


JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-only-secret-change-me")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

MYSQL_DATABASE_NAME = os.getenv("MYSQL_DATABASE_NAME", "RAG_system")
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "0000")
MYSQL_CHARSET = os.getenv("MYSQL_CHARSET", "utf8mb4")
MYSQL_COLLATION = os.getenv("MYSQL_COLLATION", "utf8mb4_unicode_ci")
