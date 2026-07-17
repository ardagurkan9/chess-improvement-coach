"""End-of-game statistics and PGN generation."""

from collections import Counter

import chess
import chess.pgn

from src.game import ChessGame
from src.models import AnalyzedMove, GameReport, MistakeTheme, MoveQuality


class ReportError(ValueError):
    """Raised when a game report cannot be generated."""


class GameReportBuilder:
    """Aggregate user analyses and export a completed game as PGN."""

    def build(
        self,
        game: ChessGame,
        analyzed_moves: list[AnalyzedMove] | tuple[AnalyzedMove, ...],
        *,
        player_color: chess.Color,
    ) -> GameReport:
        """Build a report for a completed game."""
        if not game.is_game_over or game.result is None:
            raise ReportError("A report can only be built after the game is over.")

        moves = tuple(analyzed_moves)
        cp_losses = [
            record.classification.centipawn_loss
            for record in moves
            if record.classification.centipawn_loss is not None
        ]
        average_loss = (
            round(sum(cp_losses) / len(cp_losses), 2) if cp_losses else None
        )

        counted = Counter(record.classification.quality for record in moves)
        quality_counts = {quality: counted.get(quality, 0) for quality in MoveQuality}
        counted_themes = Counter(
            record.theme_detection.theme
            for record in moves
            if record.theme_detection is not None
        )
        theme_counts = {
            theme: counted_themes.get(theme, 0) for theme in MistakeTheme
        }

        return GameReport(
            result=game.result,
            player_is_white=player_color == chess.WHITE,
            total_user_moves=len(moves),
            average_centipawn_loss=average_loss,
            quality_counts=quality_counts,
            theme_counts=theme_counts,
            missed_mates=sum(
                record.analysis.missed_forced_mate for record in moves
            ),
            allowed_mates=sum(
                record.analysis.allowed_forced_mate for record in moves
            ),
            biggest_error=max(moves, key=self._error_weight, default=None),
            improvement_areas=self._improvement_areas(
                quality_counts, theme_counts, moves
            ),
            pgn=self._create_pgn(game, player_color=player_color),
        )

    @staticmethod
    def _error_weight(record: AnalyzedMove) -> tuple[int, int]:
        mate_blunder = int(
            record.analysis.missed_forced_mate
            or record.analysis.allowed_forced_mate
        )
        loss = record.classification.centipawn_loss or 0
        return mate_blunder, loss

    @staticmethod
    def _improvement_areas(
        counts: dict[MoveQuality, int],
        theme_counts: dict[MistakeTheme, int],
        moves: tuple[AnalyzedMove, ...],
    ) -> tuple[str, ...]:
        areas: list[str] = []
        if (
            theme_counts[MistakeTheme.MISSED_MATE]
            or theme_counts[MistakeTheme.ALLOWED_MATE]
            or any(
                record.analysis.missed_forced_mate
                or record.analysis.allowed_forced_mate
                for record in moves
            )
        ):
            areas.append("Practice checking all forcing checks and mating threats.")
        if theme_counts[MistakeTheme.HANGING_PIECE]:
            areas.append("Before moving, check whether every valuable piece is defended.")
        if theme_counts[MistakeTheme.MATERIAL_LOSS]:
            areas.append("Calculate forcing capture sequences before committing.")
        if theme_counts[MistakeTheme.KING_SAFETY]:
            areas.append(
                "Preserve king shelter and review checks before moving pawns or the king."
            )
        if counts[MoveQuality.BLUNDER]:
            areas.append("Before moving, check whether the move loses material or the game.")
        if counts[MoveQuality.MISTAKE]:
            areas.append("Compare multiple candidate moves before committing.")
        if counts[MoveQuality.INACCURACY]:
            areas.append("Review small evaluation drops to improve consistency.")
        if not areas:
            areas.append("Keep reviewing the engine's alternatives after each game.")
        return tuple(areas)

    @staticmethod
    def _create_pgn(game: ChessGame, *, player_color: chess.Color) -> str:
        pgn_game = chess.pgn.Game.from_board(game.board)
        pgn_game.headers["Event"] = "Explainable Chess Coach"
        pgn_game.headers["White"] = (
            "User" if player_color == chess.WHITE else "Stockfish"
        )
        pgn_game.headers["Black"] = (
            "Stockfish" if player_color == chess.WHITE else "User"
        )
        pgn_game.headers["Result"] = game.result or "*"
        return str(pgn_game)
