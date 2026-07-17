"""Deterministic, Stockfish-grounded move explanations."""

from src.models import (
    CommentaryResult,
    MoveAnalysis,
    MoveClassification,
    MoveQuality,
    UserLevel,
)


QUALITY_OPENINGS: dict[MoveQuality, str] = {
    MoveQuality.BEST: "This was the best move.",
    MoveQuality.EXCELLENT: "This was an excellent move.",
    MoveQuality.GOOD: "This was a good move.",
    MoveQuality.INACCURACY: "This move was an inaccuracy.",
    MoveQuality.MISTAKE: "This move was a mistake.",
    MoveQuality.BLUNDER: "This move was a blunder.",
}


class TemplateCommentary:
    """Generate explanations without an external language model."""

    def generate(
        self,
        analysis: MoveAnalysis,
        classification: MoveClassification,
        *,
        level: UserLevel = UserLevel.BEGINNER,
    ) -> CommentaryResult:
        """Build an explanation using only supplied engine analysis."""
        if analysis.allowed_forced_mate:
            core = (
                f"{analysis.played_move} gives your opponent a forced mate. "
                f"Stockfish preferred {analysis.best_move}."
            )
        elif analysis.missed_forced_mate:
            core = (
                f"{analysis.played_move} misses a forced mate. "
                f"Stockfish preferred {analysis.best_move}."
            )
        else:
            core = self._standard_explanation(analysis, classification)

        detail = self._level_detail(analysis, level)
        text = f"{QUALITY_OPENINGS[classification.quality]} {core}"
        if detail:
            text = f"{text} {detail}"
        return CommentaryResult(text=text, level=level)

    @staticmethod
    def _standard_explanation(
        analysis: MoveAnalysis, classification: MoveClassification
    ) -> str:
        if analysis.played_move == analysis.best_move:
            return (
                f"{analysis.played_move} matches Stockfish's first choice and "
                "preserves the engine's preferred continuation."
            )

        loss = classification.centipawn_loss
        loss_text = (
            f" It loses {loss} centipawns."
            if loss is not None
            else " The position contains a forced-mate evaluation."
        )
        return (
            f"You played {analysis.played_move}; Stockfish preferred "
            f"{analysis.best_move}.{loss_text}"
        )

    def _level_detail(self, analysis: MoveAnalysis, level: UserLevel) -> str:
        if level is UserLevel.BEGINNER:
            return "Compare your move with the suggested move before continuing."

        evaluation = (
            f"The evaluation changed from {self._format_score(analysis.before)} "
            f"to {self._format_score(analysis.after)}."
        )
        if level is UserLevel.INTERMEDIATE:
            return evaluation

        pv = " ".join(analysis.before.pv)
        depth = analysis.before.depth
        depth_text = f" at depth {depth}" if depth is not None else ""
        line_text = f" Stockfish's line{depth_text}: {pv}." if pv else ""
        return f"{evaluation}{line_text}"

    @staticmethod
    def _format_score(result: object) -> str:
        mate = getattr(result, "mate", None)
        if mate is not None:
            return f"mate {mate:+d}"
        score_cp = getattr(result, "score_cp", None)
        if score_cp is None:
            return "an unknown score"
        return f"{score_cp / 100:+.2f}"
