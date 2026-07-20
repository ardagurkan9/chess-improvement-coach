"""Evidence-based mistake-theme detection."""

import chess

from src.models import (
    MistakeTheme,
    MoveAnalysis,
    MoveClassification,
    MoveQuality,
    ThemeDetection,
)

PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}


class MistakeDetector:
    """Detect a conservative primary theme for an analyzed error."""

    def detect(
        self, analysis: MoveAnalysis, classification: MoveClassification
    ) -> ThemeDetection:
        """Return the strongest theme supported by deterministic evidence."""
        if analysis.allowed_forced_mate:
            return ThemeDetection(
                MistakeTheme.ALLOWED_MATE,
                ("The move gives the opponent a forced mate.",),
                1.0,
            )
        if analysis.missed_forced_mate:
            return ThemeDetection(
                MistakeTheme.MISSED_MATE,
                ("A forced mate existed before the move and disappeared after it.",),
                1.0,
            )

        if classification.quality not in {
            MoveQuality.INACCURACY,
            MoveQuality.MISTAKE,
            MoveQuality.BLUNDER,
        }:
            return self._general_error(classification)

        hanging = self._detect_hanging_piece(analysis)
        if hanging is not None:
            return hanging

        material = self._detect_material_loss(analysis)
        if material is not None:
            return material

        king_safety = self._detect_king_safety(analysis)
        if king_safety is not None:
            return king_safety

        return self._general_error(classification)

    @staticmethod
    def _detect_hanging_piece(analysis: MoveAnalysis) -> ThemeDetection | None:
        board = chess.Board(analysis.fen_after)
        if not analysis.after.pv:
            return None
        try:
            reply = chess.Move.from_uci(analysis.after.pv[0])
        except (chess.InvalidMoveError, ValueError):
            return None
        if reply not in board.legal_moves or not board.is_capture(reply):
            return None

        captured_square = (
            reply.to_square
            if not board.is_en_passant(reply)
            else chess.square(
                chess.square_file(reply.to_square), chess.square_rank(reply.from_square)
            )
        )
        captured = board.piece_at(captured_square)
        attacker = board.piece_at(reply.from_square)
        player_color = chess.WHITE if analysis.player_is_white else chess.BLACK
        if captured is None or attacker is None or captured.color != player_color:
            return None
        if captured.piece_type in {chess.PAWN, chess.KING}:
            return None

        after_capture = board.copy(stack=False)
        after_capture.push(reply)
        can_recapture = any(
            move.to_square == reply.to_square and after_capture.is_capture(move)
            for move in after_capture.legal_moves
        )
        captured_value = PIECE_VALUES[captured.piece_type]
        attacker_value = PIECE_VALUES[attacker.piece_type]
        estimated_loss = (
            max(0, captured_value - attacker_value) if can_recapture else captured_value
        )
        if estimated_loss < 200:
            return None

        captured_name = chess.piece_name(captured.piece_type)
        attacker_name = chess.piece_name(attacker.piece_type)
        evidence = (
            f"The {captured_name} on {chess.square_name(captured_square)} can be captured legally by the {attacker_name} on {chess.square_name(reply.from_square)}.",
            f"Stockfish's continuation begins with {reply.uci()}.",
            f"The immediate sequence is estimated to lose at least {estimated_loss} centipawns of material.",
        )
        return ThemeDetection(MistakeTheme.HANGING_PIECE, evidence, 0.95)

    @classmethod
    def _detect_material_loss(cls, analysis: MoveAnalysis) -> ThemeDetection | None:
        board = chess.Board(analysis.fen_after)
        player_color = chess.WHITE if analysis.player_is_white else chess.BLACK
        starting_balance = cls._material_balance(board, player_color)
        applied: list[str] = []
        for move_text in analysis.after.pv[:6]:
            try:
                move = chess.Move.from_uci(move_text)
            except (chess.InvalidMoveError, ValueError):
                break
            if move not in board.legal_moves:
                break
            board.push(move)
            applied.append(move_text)

        if not applied:
            return None
        material_loss = starting_balance - cls._material_balance(board, player_color)
        if material_loss < 100:
            return None
        return ThemeDetection(
            MistakeTheme.MATERIAL_LOSS,
            (
                f"The verified continuation {' '.join(applied)} reduces the player's material by {material_loss} centipawns.",
            ),
            0.9,
        )

    @staticmethod
    def _detect_king_safety(analysis: MoveAnalysis) -> ThemeDetection | None:
        before = chess.Board(analysis.fen_before)
        after = chess.Board(analysis.fen_after)
        player_color = chess.WHITE if analysis.player_is_white else chess.BLACK
        move = chess.Move.from_uci(analysis.played_move)
        moved_piece = before.piece_at(move.from_square)
        king_square = before.king(player_color)

        if (
            moved_piece is not None
            and moved_piece.piece_type == chess.KING
            and before.has_castling_rights(player_color)
            and not before.is_castling(move)
            and not after.has_castling_rights(player_color)
        ):
            return ThemeDetection(
                MistakeTheme.KING_SAFETY,
                ("The king move permanently gives up the remaining castling rights.",),
                0.8,
            )

        if (
            moved_piece is None
            or moved_piece.piece_type != chess.PAWN
            or king_square is None
            or abs(chess.square_file(move.from_square) - chess.square_file(king_square))
            > 1
            or not analysis.after.pv
        ):
            return None
        try:
            reply = chess.Move.from_uci(analysis.after.pv[0])
        except (chess.InvalidMoveError, ValueError):
            return None
        if reply not in after.legal_moves:
            return None
        after.push(reply)
        if not after.is_check():
            return None
        return ThemeDetection(
            MistakeTheme.KING_SAFETY,
            (
                f"The pawn moved from {chess.square_name(move.from_square)}, next to its king.",
                f"Stockfish's reply {reply.uci()} gives check immediately.",
            ),
            0.85,
        )

    @staticmethod
    def _material_for(board: chess.Board, color: chess.Color) -> int:
        return sum(
            len(board.pieces(piece_type, color)) * value
            for piece_type, value in PIECE_VALUES.items()
        )

    @classmethod
    def _material_balance(cls, board: chess.Board, color: chess.Color) -> int:
        return cls._material_for(board, color) - cls._material_for(board, not color)

    @staticmethod
    def _general_error(classification: MoveClassification) -> ThemeDetection:
        loss = classification.centipawn_loss
        evidence = (
            (f"The move lost {loss} centipawns according to Stockfish.",)
            if loss is not None
            else (
                "Stockfish identified an error without enough evidence for a specific theme.",
            )
        )
        return ThemeDetection(MistakeTheme.GENERAL_ERROR, evidence, 1.0)
