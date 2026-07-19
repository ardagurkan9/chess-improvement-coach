"""Application service for persistent personal coaching history."""

from src.models import AnalyzedMove, GameReport, UserLevel
from src.repositories.interfaces import GameHistoryRepository, MistakeSummary


class HistoryService:
    """Coordinate game-history persistence without exposing SQLAlchemy to the CLI."""

    def __init__(self, repository: GameHistoryRepository, *, username: str) -> None:
        clean_username = username.strip()
        if not clean_username:
            raise ValueError("Username cannot be empty.")
        self.repository = repository
        self.username = clean_username

    def save_completed_game(
        self,
        report: GameReport,
        analyzed_moves: list[AnalyzedMove] | tuple[AnalyzedMove, ...],
        *,
        level: UserLevel,
    ) -> int:
        """Persist a completed game and return its database identifier."""
        return self.repository.save_game(
            username=self.username,
            level=level,
            report=report,
            analyzed_moves=tuple(analyzed_moves),
        )

    def recurring_mistakes(self) -> tuple[MistakeSummary, ...]:
        """Return the current user's recurring mistake themes."""
        return self.repository.recurring_mistakes(username=self.username)
