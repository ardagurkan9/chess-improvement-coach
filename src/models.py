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
