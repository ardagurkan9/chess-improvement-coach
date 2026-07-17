import chess


def test_python_chess_is_available() -> None:
    board = chess.Board()

    assert board.is_valid()
    assert board.fullmove_number == 1
