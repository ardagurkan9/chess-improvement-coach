"""Shared application data models."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EngineResult:
    """A normalized Stockfish position analysis.

    Scores always use White's perspective: positive values favor White and
    negative values favor Black. Exactly one of ``score_cp`` and ``mate`` is
    populated.
    """

    best_move: str
    score_cp: int | None
    mate: int | None
    pv: tuple[str, ...]
    depth: int | None = None

    @property
    def is_mate(self) -> bool:
        """Return whether Stockfish reported a forced mate."""
        return self.mate is not None


@dataclass(frozen=True, slots=True)
class MoveAnalysis:
    """Comparison of a position before and after a player's move."""

    played_move: str
    player_is_white: bool
    fen_before: str
    fen_after: str
    before: EngineResult
    after: EngineResult
    centipawn_loss: int | None
    missed_forced_mate: bool = False
    allowed_forced_mate: bool = False

    @property
    def best_move(self) -> str:
        """Return Stockfish's best move in the position before the move."""
        return self.before.best_move

    @property
    def contains_mate_score(self) -> bool:
        """Return whether either position contains a forced-mate score."""
        return self.before.is_mate or self.after.is_mate
