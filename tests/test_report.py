import chess
import pytest

from src.game import ChessGame
from src.models import (
    AnalyzedMove,
    EngineResult,
    MoveAnalysis,
    MoveClassification,
    MoveQuality,
    MistakeTheme,
    ThemeDetection,
)
from src.report import GameReportBuilder, ReportError


def analyzed_move(
    move: str,
    quality: MoveQuality,
    loss: int | None,
    *,
    missed_mate: bool = False,
    allowed_mate: bool = False,
    theme: MistakeTheme | None = None,
) -> AnalyzedMove:
    engine_result = EngineResult("e2e4", 0, None, ("e2e4",), 10)
    analysis = MoveAnalysis(
        played_move=move,
        player_is_white=True,
        fen_before="before",
        fen_after="after",
        before=engine_result,
        after=engine_result,
        centipawn_loss=loss,
        missed_forced_mate=missed_mate,
        allowed_forced_mate=allowed_mate,
    )
    classification = MoveClassification(quality, "reason", loss)
    detection = ThemeDetection(theme, ("evidence",), 0.9) if theme else None
    return AnalyzedMove(analysis, classification, detection)


def completed_fools_mate() -> ChessGame:
    game = ChessGame()
    for move in ("f2f3", "e7e5", "g2g4", "d8h4"):
        game.play_uci(move)
    return game


def test_report_aggregates_quality_and_centipawn_statistics() -> None:
    moves = [
        analyzed_move("f2f3", MoveQuality.INACCURACY, 100),
        analyzed_move("g2g4", MoveQuality.BLUNDER, 300),
    ]

    report = GameReportBuilder().build(
        completed_fools_mate(), moves, player_color=chess.WHITE
    )

    assert report.result == "0-1"
    assert report.player_is_white
    assert report.total_user_moves == 2
    assert report.average_centipawn_loss == 200.0
    assert report.quality_counts[MoveQuality.INACCURACY] == 1
    assert report.quality_counts[MoveQuality.BLUNDER] == 1
    assert report.quality_counts[MoveQuality.BEST] == 0
    assert report.biggest_error == moves[1]
    assert len(report.improvement_areas) == 2


def test_mate_error_is_biggest_and_excluded_from_cp_average() -> None:
    cp_error = analyzed_move("a2a3", MoveQuality.BLUNDER, 500)
    mate_error = analyzed_move(
        "g2g4", MoveQuality.BLUNDER, None, allowed_mate=True
    )

    report = GameReportBuilder().build(
        completed_fools_mate(), [cp_error, mate_error], player_color=chess.WHITE
    )

    assert report.average_centipawn_loss == 500.0
    assert report.allowed_mates == 1
    assert report.missed_mates == 0
    assert report.biggest_error == mate_error
    assert any("mating threats" in area for area in report.improvement_areas)


def test_report_generates_standard_pgn_with_players_and_result() -> None:
    report = GameReportBuilder().build(
        completed_fools_mate(), [], player_color=chess.WHITE
    )

    assert '[Event "Explainable Chess Coach"]' in report.pgn
    assert '[White "User"]' in report.pgn
    assert '[Black "Stockfish"]' in report.pgn
    assert '[Result "0-1"]' in report.pgn
    assert "1. f3 e5 2. g4 Qh4# 0-1" in report.pgn


def test_report_handles_game_without_numeric_user_analyses() -> None:
    report = GameReportBuilder().build(
        completed_fools_mate(), [], player_color=chess.BLACK
    )

    assert not report.player_is_white
    assert report.average_centipawn_loss is None
    assert report.biggest_error is None
    assert report.improvement_areas
    assert '[White "Stockfish"]' in report.pgn
    assert '[Black "User"]' in report.pgn


def test_report_rejects_unfinished_game() -> None:
    with pytest.raises(ReportError, match="after the game is over"):
        GameReportBuilder().build(ChessGame(), [], player_color=chess.WHITE)


def test_report_counts_themes_and_produces_theme_based_advice() -> None:
    moves = [
        analyzed_move(
            "g2g4",
            MoveQuality.BLUNDER,
            350,
            theme=MistakeTheme.HANGING_PIECE,
        ),
        analyzed_move(
            "f2f3",
            MoveQuality.MISTAKE,
            200,
            theme=MistakeTheme.KING_SAFETY,
        ),
    ]

    report = GameReportBuilder().build(
        completed_fools_mate(), moves, player_color=chess.WHITE
    )

    assert report.theme_counts[MistakeTheme.HANGING_PIECE] == 1
    assert report.theme_counts[MistakeTheme.KING_SAFETY] == 1
    assert any("valuable piece" in area for area in report.improvement_areas)
    assert any("king shelter" in area for area in report.improvement_areas)
