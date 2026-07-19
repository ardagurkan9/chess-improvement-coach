"""SQLAlchemy 2 persistence models for coaching history."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from src.models import MistakeTheme, MoveQuality, UserLevel


class PlayerColor(StrEnum):
    """Colors a user can play in a stored game."""

    WHITE = "white"
    BLACK = "black"


class PracticeStatus(StrEnum):
    """Review state of a generated practice position."""

    PENDING = "pending"
    LEARNING = "learning"
    MASTERED = "mastered"


def enum_column(enum_type: type[StrEnum], *, name: str) -> Enum:
    """Store stable enum values portably instead of database-specific enums."""
    return Enum(
        enum_type,
        name=name,
        values_callable=lambda values: [value.value for value in values],
        native_enum=False,
    )


class Base(DeclarativeBase):
    """Declarative base shared by all database records."""


class UserRecord(Base):
    """A coach user whose games and progress are tracked."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    level: Mapped[UserLevel] = mapped_column(
        enum_column(UserLevel, name="user_level"),
        default=UserLevel.BEGINNER,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    games: Mapped[list[GameRecord]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    practice_positions: Mapped[list[PracticePositionRecord]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class GameRecord(Base):
    """One completed game and its PGN representation."""

    __tablename__ = "games"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    player_color: Mapped[PlayerColor] = mapped_column(
        enum_column(PlayerColor, name="player_color")
    )
    result: Mapped[str] = mapped_column(String(16))
    pgn: Mapped[str] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[UserRecord] = relationship(back_populates="games")
    move_analyses: Mapped[list[MoveAnalysisRecord]] = relationship(
        back_populates="game",
        cascade="all, delete-orphan",
        order_by="MoveAnalysisRecord.ply_number",
    )


class MoveAnalysisRecord(Base):
    """Stockfish analysis and coaching output for one user move."""

    __tablename__ = "move_analyses"
    __table_args__ = (
        UniqueConstraint("game_id", "ply_number", name="uq_game_ply_number"),
        CheckConstraint("ply_number > 0", name="ck_positive_ply_number"),
        CheckConstraint(
            "centipawn_loss IS NULL OR centipawn_loss >= 0",
            name="ck_nonnegative_centipawn_loss",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), index=True
    )
    ply_number: Mapped[int] = mapped_column(Integer)
    played_move: Mapped[str] = mapped_column(String(5))
    best_move: Mapped[str] = mapped_column(String(5))
    fen_before: Mapped[str] = mapped_column(Text)
    fen_after: Mapped[str] = mapped_column(Text)
    score_before_cp: Mapped[int | None] = mapped_column(Integer)
    score_after_cp: Mapped[int | None] = mapped_column(Integer)
    mate_before: Mapped[int | None] = mapped_column(Integer)
    mate_after: Mapped[int | None] = mapped_column(Integer)
    centipawn_loss: Mapped[int | None] = mapped_column(Integer)
    quality: Mapped[MoveQuality] = mapped_column(
        enum_column(MoveQuality, name="move_quality"), index=True
    )
    principal_variation: Mapped[list[str]] = mapped_column(JSON, default=list)
    commentary: Mapped[str | None] = mapped_column(Text)
    commentary_source: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    game: Mapped[GameRecord] = relationship(back_populates="move_analyses")
    mistake: Mapped[MistakeRecord | None] = relationship(
        back_populates="move_analysis",
        cascade="all, delete-orphan",
        uselist=False,
    )


class MistakeRecord(Base):
    """A deterministic mistake theme and its supporting evidence."""

    __tablename__ = "mistakes"
    __table_args__ = (
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_mistake_confidence_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    move_analysis_id: Mapped[int] = mapped_column(
        ForeignKey("move_analyses.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    theme: Mapped[MistakeTheme] = mapped_column(
        enum_column(MistakeTheme, name="mistake_theme"), index=True
    )
    evidence: Mapped[list[str]] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    move_analysis: Mapped[MoveAnalysisRecord] = relationship(
        back_populates="mistake"
    )
    practice_positions: Mapped[list[PracticePositionRecord]] = relationship(
        back_populates="source_mistake"
    )


class PracticePositionRecord(Base):
    """A position generated from a past mistake for later review."""

    __tablename__ = "practice_positions"
    __table_args__ = (
        CheckConstraint("attempts >= 0", name="ck_nonnegative_attempts"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    source_mistake_id: Mapped[int] = mapped_column(
        ForeignKey("mistakes.id", ondelete="CASCADE"), index=True
    )
    fen: Mapped[str] = mapped_column(Text)
    solution_moves: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[PracticeStatus] = mapped_column(
        enum_column(PracticeStatus, name="practice_status"),
        default=PracticeStatus.PENDING,
        index=True,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    solved: Mapped[bool] = mapped_column(Boolean, default=False)
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[UserRecord] = relationship(back_populates="practice_positions")
    source_mistake: Mapped[MistakeRecord] = relationship(
        back_populates="practice_positions"
    )
