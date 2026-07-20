"""Repository contracts used by application services."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from src.models import (
    AnalyzedMove,
    GameReport,
    MistakeTheme,
    MoveQuality,
    UserLevel,
)


@dataclass(frozen=True, slots=True)
class MistakeSummary:
    """Number of persisted mistakes belonging to one theme."""

    theme: MistakeTheme
    count: int


@dataclass(frozen=True, slots=True)
class PracticePosition:
    """A due mistake position that can be presented without exposing ORM models."""

    id: int
    fen: str
    theme: MistakeTheme
    evidence: tuple[str, ...]
    solution_moves: tuple[str, ...]
    status: str
    attempts: int
    successful_attempts: int
    next_review_at: datetime | None


class GameHistoryRepository(Protocol):
    """Persistence operations required by the coaching history service."""

    def save_game(
        self,
        *,
        username: str,
        level: UserLevel,
        report: GameReport,
        analyzed_moves: tuple[AnalyzedMove, ...],
    ) -> int:
        """Persist one completed game and return its identifier."""

    def recurring_mistakes(self, *, username: str) -> tuple[MistakeSummary, ...]:
        """Return persisted mistake counts ordered from most common to least."""

    def due_practice_position(
        self, *, username: str, as_of: datetime
    ) -> PracticePosition | None:
        """Return the next practice position due for a user."""

    def record_practice_attempt(
        self,
        *,
        username: str,
        position_id: int,
        attempted_move: str,
        correct: bool,
        quality: MoveQuality | None,
        detected_theme: MistakeTheme | None,
        commentary: str | None,
        commentary_source: str | None,
        status: str,
        solved: bool,
        next_review_at: datetime,
    ) -> PracticePosition:
        """Record one answer and return the updated position."""
