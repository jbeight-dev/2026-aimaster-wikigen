from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .database import Base

SEED_USERS = [
    {"user_id": "usr_hong", "name": "홍길동"},
    {"user_id": "usr_jb", "name": "박정병"},
    {"user_id": "usr_yl", "name": "이유리"},
    {"user_id": "usr_gh", "name": "이기훈"},
]

FILE_STATUSES = ["idle", "analyzing", "done", "analysis_failed", "upload_failed", "deleted"]
DOCUMENT_STATUSES = ["pending", "approved", "rejected", "deleted"]
SUPPORTED_FILE_EXTENSIONS = [
    "pdf",
    "txt",
    "md",
    "db",
    "sqlite",
    "sqlite3",
    "csv",
]


class User(Base):
    __tablename__ = "users"

    user_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)


class Space(Base):
    __tablename__ = "spaces"

    space_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    owner_id = Column(String, ForeignKey("users.user_id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    files = relationship("File", back_populates="space", cascade="all, delete-orphan")
    documents = relationship(
        "Document", back_populates="space", cascade="all, delete-orphan"
    )
    chat_messages = relationship(
        "ChatMessage", back_populates="space", cascade="all, delete-orphan"
    )


class File(Base):
    __tablename__ = "files"

    file_id = Column(String, primary_key=True)
    space_id = Column(String, ForeignKey("spaces.space_id"), nullable=False)
    name = Column(String, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    storage_path = Column(String, nullable=True)
    checksum = Column(String, nullable=True)
    status = Column(String, nullable=False, default="idle")
    step_index = Column(Integer, nullable=False, default=0)
    step_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    space = relationship("Space", back_populates="files")
    documents = relationship(
        "Document", back_populates="file", cascade="all, delete-orphan"
    )
    wiki_entries = relationship(
        "WikiMd", back_populates="file", cascade="all, delete-orphan"
    )


class Document(Base):
    __tablename__ = "documents"

    document_id = Column(String, primary_key=True)
    file_id = Column(String, ForeignKey("files.file_id"), nullable=False)
    space_id = Column(String, ForeignKey("spaces.space_id"), nullable=False)
    wiki_doc_id = Column(String, ForeignKey("wikimd.doc_id"), nullable=True)
    title = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")
    version = Column(Integer, nullable=False, default=1)
    reject_reason = Column(String, nullable=True)
    flags = Column(JSON, nullable=False, default=list)
    sections = Column(JSON, nullable=False, default=list)
    related_document_ids = Column(JSON, nullable=False, default=list)
    history = Column(JSON, nullable=False, default=list)

    file = relationship("File", back_populates="documents")
    space = relationship("Space", back_populates="documents")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    message_id = Column(String, primary_key=True)
    space_id = Column(String, ForeignKey("spaces.space_id"), nullable=False)
    role = Column(String, nullable=False)
    text = Column(String, nullable=False)
    source_document_ids = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    space = relationship("Space", back_populates="chat_messages")


class WikiMd(Base):
    __tablename__ = "wikimd"

    doc_id = Column(String, primary_key=True)  # Builder의 WikiFrontmatter.id
    file_id = Column(String, ForeignKey("files.file_id"), nullable=False)
    space_id = Column(String, ForeignKey("spaces.space_id"), nullable=False)

    title = Column(String, nullable=False)
    slug = Column(String, nullable=False)
    doc_type = Column(String, nullable=False, default="generic")
    summary = Column(Text, nullable=False)

    keywords = Column(JSON, nullable=False, default=list)
    concepts = Column(JSON, nullable=False, default=list)
    tags = Column(JSON, nullable=False, default=list)
    entities = Column(JSON, nullable=False, default=list)
    relations = Column(JSON, nullable=False, default=list)
    source = Column(JSON, nullable=False, default=dict)

    review_status = Column(String, nullable=False, default="draft")
    version = Column(Integer, nullable=False, default=1)
    reviewed_by = Column(String, nullable=True)

    builder_created_at = Column(DateTime, nullable=False)
    builder_updated_at = Column(DateTime, nullable=True)

    body = Column(Text, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    synced_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    file = relationship("File", back_populates="wiki_entries")
