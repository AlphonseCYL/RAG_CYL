from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db_models.base import Base


class KnowledgeBase(Base):
    __tablename__ = "knowledgebases"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    knowledge_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    knowledgebase_name: Mapped[str] = mapped_column(String(255), nullable=False)
    knowledgebase_dir: Mapped[str] = mapped_column(String(1024), nullable=False)
    session_id: Mapped[str] = mapped_column(String(32), nullable=True, index=True)
    file_name: Mapped[str] = mapped_column(String(1024), nullable=True)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False)


class KnowledgeBaseFile(Base):
    __tablename__ = "knowledgebase_files"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    knowledge_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(32), nullable=True, index=True)
    file_name: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
