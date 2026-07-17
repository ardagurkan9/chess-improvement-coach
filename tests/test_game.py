import chess
import pytest

from src.game import (
    ChessGame,
    GameOverError,
    IllegalMoveError,
    InvalidMoveFormatError,
    MoveError,
)


def play_moves(game: ChessGame, *moves: str) -> None:
    for move in moves:
        game.play_uci(move)


def test_new_game_starts_from_initial_position() -> None:
    game = ChessGame()

    assert game.current_fen == chess.STARTING_FEN
    assert game.turn == chess.WHITE
    assert len(game.legal_moves) == 20
    assert game.move_history == ()
    assert game.result is None


def test_legal_move_is_played_and_recorded() -> None:
    game = ChessGame()

    move = game.play_uci(" E2E4 ")

    assert move == chess.Move.from_uci("e2e4")
    assert game.uci_history == ("e2e4",)
    assert game.turn == chess.BLACK
    assert game.board.piece_at(chess.E4) == chess.Piece(chess.PAWN, chess.WHITE)


@pytest.mark.parametrize("move", ["e9e4", "pawn to e4", "", "e2e4queen"])
def test_invalid_uci_format_is_rejected(move: str) -> None:
    with pytest.raises(InvalidMoveFormatError, match="valid UCI notation"):
        ChessGame().play_uci(move)


def test_illegal_move_is_rejected_without_changing_position() -> None:
    game = ChessGame()
    starting_fen = game.current_fen

    with pytest.raises(IllegalMoveError, match="illegal"):
        game.play_uci("e2e5")

    assert game.current_fen == starting_fen
    assert game.move_history == ()


def test_castling_moves_the_king_and_rook() -> None:
    game = ChessGame()
    play_moves(game, "e2e4", "e7e5", "g1f3", "b8c6", "f1e2", "g8f6")

    game.play_uci("e1g1")

    board = game.board
    assert board.king(chess.WHITE) == chess.G1
    assert board.piece_at(chess.F1) == chess.Piece(chess.ROOK, chess.WHITE)


def test_en_passant_capture_removes_the_captured_pawn() -> None:
    game = ChessGame()
    play_moves(game, "e2e4", "a7a6", "e4e5", "d7d5", "e5d6")

    board = game.board
    assert board.piece_at(chess.D6) == chess.Piece(chess.PAWN, chess.WHITE)
    assert board.piece_at(chess.D5) is None


def test_pawn_promotion_requires_and_uses_promotion_piece() -> None:
    game = ChessGame("8/P7/8/8/8/8/7p/4K2k w - - 0 1")

    with pytest.raises(IllegalMoveError):
        game.play_uci("a7a8")

    game.play_uci("a7a8q")

    assert game.board.piece_at(chess.A8) == chess.Piece(chess.QUEEN, chess.WHITE)


def test_fools_mate_is_reported_as_checkmate() -> None:
    game = ChessGame()
    play_moves(game, "f2f3", "e7e5", "g2g4", "d8h4")

    assert game.is_check
    assert game.is_checkmate
    assert game.is_game_over
    assert game.result == "0-1"

    with pytest.raises(GameOverError, match="0-1"):
        game.play_uci("e2e4")


def test_stalemate_is_reported_as_draw() -> None:
    game = ChessGame("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")

    assert game.is_stalemate
    assert game.is_game_over
    assert game.result == "1/2-1/2"


def test_undo_and_reset_restore_previous_positions() -> None:
    game = ChessGame()
    play_moves(game, "e2e4", "e7e5")

    assert game.undo().uci() == "e7e5"
    assert game.uci_history == ("e2e4",)

    game.reset()
    assert game.current_fen == chess.STARTING_FEN
    assert game.move_history == ()


def test_undo_rejects_empty_history() -> None:
    with pytest.raises(MoveError, match="no move"):
        ChessGame().undo()


def test_invalid_starting_fen_is_rejected() -> None:
    with pytest.raises(ValueError, match="Invalid starting FEN"):
        ChessGame("not-a-fen")


def test_structurally_invalid_starting_position_is_rejected() -> None:
    with pytest.raises(ValueError, match="Invalid starting position"):
        ChessGame("8/8/8/8/8/8/8/8 w - - 0 1")
