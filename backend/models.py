from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    type: Mapped[str] = mapped_column(Text, nullable=False, default="arxiv")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    schedule_frequency: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    schedule_time: Mapped[str] = mapped_column(Text, nullable=False, default="00:00")  # UTC HH:MM
    email_to: Mapped[str] = mapped_column(Text, nullable=False)
    max_results: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    period: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    google_drive_folder_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    interests: Mapped[list["SourceInterest"]] = relationship(
        "SourceInterest", back_populates="source", cascade="all, delete-orphan"
    )


class SourceInterest(Base):
    __tablename__ = "source_interests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_id: Mapped[int] = mapped_column(Integer, ForeignKey("sources.id"), nullable=False)
    arxiv_categories: Mapped[str] = mapped_column(Text, nullable=False, default="")
    keywords: Mapped[str] = mapped_column(Text, nullable=False, default="")

    source: Mapped["Source"] = relationship("Source", back_populates="interests")


class GoogleToken(Base):
    __tablename__ = "google_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    token_expiry: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
