"""Compare Stockfish evaluations before and after a move."""

from typing import Protocol

import chess

from src.models import EngineResult, MoveAnalysis


class AnalysisError(RuntimeError):
    """Raised when a requested move cannot be analyzed."""


class PositionAnalyzer(Protocol):
    """Minimal engine interface required by ``MoveAnalyzer``."""

    def analyze(
        self,
        position: chess.Board | str,
        *,
        depth: int | None = 12,
        time_limit: float | None = None,
    ) -> EngineResult: ...


class MoveAnalyzer:
    """Analyze the quality impact of one legal move."""

    def __init__(self, engine: PositionAnalyzer) -> None:
        self.engine = engine

    def analyze_move(
        self,
        board: chess.Board,
        move: chess.Move | str,
        *,
        depth: int | None = 12,
        time_limit: float | None = None,
    ) -> MoveAnalysis:
        """Analyze a move without modifying the supplied board.

        Centipawn loss is calculated from the moving player's perspective and
        is never negative. If either position has a mate score, centipawn loss
        is left as ``None`` and mate transitions are reported separately.
        """
        if not board.is_valid():
            raise AnalysisError("The supplied board position is invalid.")
        if board.is_game_over(claim_draw=True):
            raise AnalysisError("A move cannot be analyzed after the game is over.")

        parsed_move = self._parse_move(move)
        if parsed_move not in board.legal_moves:
            raise AnalysisError(
                f"Move {parsed_move.uci()} is illegal in the supplied position."
            )

        working_board = board.copy(stack=True)
        player_is_white = working_board.turn == chess.WHITE
        fen_before = working_board.fen()
        before = self.engine.analyze(working_board, depth=depth, time_limit=time_limit)

        working_board.push(parsed_move)
        fen_after = working_board.fen()
        after = self.engine.analyze(working_board, depth=depth, time_limit=time_limit)

        return MoveAnalysis(
            played_move=parsed_move.uci(),
            player_is_white=player_is_white,
            fen_before=fen_before,
            fen_after=fen_after,
            before=before,
            after=after,
            centipawn_loss=self._centipawn_loss(
                before, after, player_is_white=player_is_white
            ),
            missed_forced_mate=self._missed_forced_mate(
                before, after, player_is_white=player_is_white
            ),
            allowed_forced_mate=self._allowed_forced_mate(
                before, after, player_is_white=player_is_white
            ),
        )

    @staticmethod
    def _parse_move(move: chess.Move | str) -> chess.Move:
        if isinstance(move, chess.Move):
            return move
        try:
            return chess.Move.from_uci(move.strip().lower())
        except (chess.InvalidMoveError, ValueError) as error:
            raise AnalysisError(f"Invalid UCI move: {move}") from error

    @staticmethod
    def _centipawn_loss(
        before: EngineResult, after: EngineResult, *, player_is_white: bool
    ) -> int | None:
        if before.is_mate or after.is_mate:
            return None
        if before.score_cp is None or after.score_cp is None:
            raise AnalysisError("A non-mate engine result is missing its score.")

        raw_loss = (
            before.score_cp - after.score_cp
            if player_is_white
            else after.score_cp - before.score_cp
        )
        return max(0, raw_loss)

    @staticmethod
    def _mate_favors_player(result: EngineResult, *, player_is_white: bool) -> bool:
        if result.mate is None:
            return False
        return result.mate > 0 if player_is_white else result.mate < 0

    @classmethod
    def _missed_forced_mate(
        cls,
        before: EngineResult,
        after: EngineResult,
        *,
        player_is_white: bool,
    ) -> bool:
        had_mate = cls._mate_favors_player(before, player_is_white=player_is_white)
        keeps_mate = cls._mate_favors_player(after, player_is_white=player_is_white)
        return had_mate and not keeps_mate

    @classmethod
    def _allowed_forced_mate(
        cls,
        before: EngineResult,
        after: EngineResult,
        *,
        player_is_white: bool,
    ) -> bool:
        opponent_had_mate = before.is_mate and not cls._mate_favors_player(
            before, player_is_white=player_is_white
        )
        opponent_has_mate = after.is_mate and not cls._mate_favors_player(
            after, player_is_white=player_is_white
        )
        return opponent_has_mate and not opponent_had_mate
