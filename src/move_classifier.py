"""Classify analyzed moves by centipawn loss and mate transitions."""

from dataclasses import dataclass

from src.models import MoveAnalysis, MoveClassification, MoveQuality


class ClassificationError(ValueError):
    """Raised when an analysis does not contain enough classification data."""


@dataclass(frozen=True, slots=True)
class ClassificationThresholds:
    """Inclusive upper centipawn-loss bounds for non-blunder labels."""

    best: int = 15
    excellent: int = 40
    good: int = 80
    inaccuracy: int = 150
    mistake: int = 300

    def __post_init__(self) -> None:
        values = (
            self.best,
            self.excellent,
            self.good,
            self.inaccuracy,
            self.mistake,
        )
        if values[0] < 0 or any(
            left >= right for left, right in zip(values, values[1:])
        ):
            raise ValueError(
                "Classification thresholds must be non-negative and strictly increasing."
            )


class MoveClassifier:
    """Convert a ``MoveAnalysis`` into a stable quality label."""

    def __init__(self, thresholds: ClassificationThresholds | None = None) -> None:
        self.thresholds = thresholds or ClassificationThresholds()

    def classify(self, analysis: MoveAnalysis) -> MoveClassification:
        """Classify a move, giving mate events priority over numeric scores."""
        if analysis.allowed_forced_mate:
            return self._result(
                MoveQuality.BLUNDER,
                analysis,
                "The move gives the opponent a forced mate.",
            )
        if analysis.missed_forced_mate:
            return self._result(
                MoveQuality.BLUNDER,
                analysis,
                "The move misses a forced mate.",
            )

        if analysis.played_move == analysis.best_move:
            return self._result(
                MoveQuality.BEST,
                analysis,
                "The move matches Stockfish's first choice.",
            )

        if analysis.centipawn_loss is not None:
            return self._classify_centipawn_loss(analysis)

        if analysis.contains_mate_score:
            return self._result(
                MoveQuality.GOOD,
                analysis,
                "The position contains a mate score without a newly missed or allowed mate.",
            )

        raise ClassificationError(
            "The move analysis has neither centipawn loss nor mate information."
        )

    def _classify_centipawn_loss(self, analysis: MoveAnalysis) -> MoveClassification:
        loss = analysis.centipawn_loss
        assert loss is not None
        if loss < 0:
            raise ClassificationError("Centipawn loss cannot be negative.")

        bounds = self.thresholds
        if loss <= bounds.best:
            quality = MoveQuality.BEST
        elif loss <= bounds.excellent:
            quality = MoveQuality.EXCELLENT
        elif loss <= bounds.good:
            quality = MoveQuality.GOOD
        elif loss <= bounds.inaccuracy:
            quality = MoveQuality.INACCURACY
        elif loss <= bounds.mistake:
            quality = MoveQuality.MISTAKE
        else:
            quality = MoveQuality.BLUNDER

        if loss == 0:
            reason = "The move matches Stockfish's top evaluation."
        elif quality is MoveQuality.BEST:
            reason = "The move is effectively tied with Stockfish's first choice."
        else:
            reason = f"The move loses {loss} centipawns."

        return self._result(quality, analysis, reason)

    @staticmethod
    def _result(
        quality: MoveQuality, analysis: MoveAnalysis, reason: str
    ) -> MoveClassification:
        return MoveClassification(
            quality=quality,
            reason=reason,
            centipawn_loss=analysis.centipawn_loss,
        )
