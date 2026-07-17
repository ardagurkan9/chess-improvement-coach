from unittest.mock import MagicMock

import chess
import pytest

from src.analysis import AnalysisError, MoveAnalyzer
from src.models import EngineResult


def result(
    score_cp: int | None,
    *,
    mate: int | None = None,
    best_move: str = "e2e4",
) -> EngineResult:
    return EngineResult(
        best_move=best_move,
        score_cp=score_cp,
        mate=mate,
        pv=(best_move,),
        depth=12,
    )


def analyzer_with(*results: EngineResult) -> tuple[MoveAnalyzer, MagicMock]:
    engine = MagicMock()
    engine.analyze.side_effect = results
    return MoveAnalyzer(engine), engine


def test_white_centipawn_loss_uses_white_perspective() -> None:
    analyzer, engine = analyzer_with(result(50), result(-100))
    board = chess.Board()

    analysis = analyzer.analyze_move(board, "e2e4")

    assert analysis.player_is_white
    assert analysis.centipawn_loss == 150
    assert analysis.best_move == "e2e4"
    assert analysis.played_move == "e2e4"
    assert board.fen() == chess.STARTING_FEN
    assert engine.analyze.call_count == 2


def test_black_centipawn_loss_reverses_white_score_difference() -> None:
    analyzer, _ = analyzer_with(result(50, best_move="e7e5"), result(120))
    board = chess.Board()
    board.push_uci("e2e4")

    analysis = analyzer.analyze_move(board, "e7e5")

    assert not analysis.player_is_white
    assert analysis.centipawn_loss == 70


@pytest.mark.parametrize(
    ("before_score", "after_score", "player_move"),
    [(0, 80, "e2e4"), (80, 0, "e7e5")],
)
def test_better_move_never_produces_negative_loss(
    before_score: int, after_score: int, player_move: str
) -> None:
    analyzer, _ = analyzer_with(result(before_score), result(after_score))
    board = chess.Board()
    if player_move == "e7e5":
        board.push_uci("e2e4")

    analysis = analyzer.analyze_move(board, player_move)

    assert analysis.centipawn_loss == 0


def test_white_missed_forced_mate_is_kept_separate_from_cp() -> None:
    analyzer, _ = analyzer_with(result(None, mate=3), result(100))

    analysis = analyzer.analyze_move(chess.Board(), "e2e4")

    assert analysis.centipawn_loss is None
    assert analysis.contains_mate_score
    assert analysis.missed_forced_mate
    assert not analysis.allowed_forced_mate


def test_black_allowing_white_mate_is_reported() -> None:
    analyzer, _ = analyzer_with(result(-20, best_move="e7e5"), result(None, mate=2))
    board = chess.Board()
    board.push_uci("e2e4")

    analysis = analyzer.analyze_move(board, "e7e5")

    assert analysis.centipawn_loss is None
    assert not analysis.missed_forced_mate
    assert analysis.allowed_forced_mate


def test_illegal_move_is_rejected_before_engine_call() -> None:
    analyzer, engine = analyzer_with()

    with pytest.raises(AnalysisError, match="illegal"):
        analyzer.analyze_move(chess.Board(), "e2e5")

    engine.analyze.assert_not_called()


def test_invalid_move_text_is_rejected() -> None:
    analyzer, _ = analyzer_with()

    with pytest.raises(AnalysisError, match="Invalid UCI"):
        analyzer.analyze_move(chess.Board(), "pawn to e4")


def test_game_over_position_is_rejected() -> None:
    analyzer, _ = analyzer_with()
    board = chess.Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")

    with pytest.raises(AnalysisError, match="game is over"):
        analyzer.analyze_move(board, "h8g8")
