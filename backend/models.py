"""
SQLAlchemy ORM models for the Phase 1 ingestion schema.

Tables (named to match docs/architecture.md):
  * ``papers`` — metadata + storage reference for an ingested PDF
  * ``chunks``  — deterministic text chunks tied to a paper and a page

Created only via scripts/init_db.py (or ``Base.metadata.create_all`` in the
integration tests). Importing this module never connects to the database.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Paper(Base):
    __tablename__ = "papers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    authors: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    doi: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    extracted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    chunks: Mapped[List["Chunk"]] = relationship(
        back_populates="paper",
        cascade="all, delete-orphan",
        order_by="Chunk.chunk_index",
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[int] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    section: Mapped[str] = mapped_column(String(128), nullable=False, default="Unknown")
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    paper: Mapped[Paper] = relationship(back_populates="chunks")
