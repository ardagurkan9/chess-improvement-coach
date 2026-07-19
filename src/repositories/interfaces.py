"""Repository contracts used by application services."""

from dataclasses import dataclass
from typing import Protocol

from src.models import AnalyzedMove, GameReport, MistakeTheme, UserLevel


@dataclass(frozen=True, slots=True)
class MistakeSummary:
    """Number of persisted mistakes belonging to one theme."""

    theme: MistakeTheme
    count: int


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
