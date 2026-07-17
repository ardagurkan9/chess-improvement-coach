import pytest

from src.mistake_detector import MistakeDetector
from src.models import (
    EngineResult,
    MistakeTheme,
    MoveAnalysis,
    MoveClassification,
    MoveQuality,
    ThemeDetection,
)


def analysis(
    *,
    played_move: str = "e2e4",
    fen_before: str = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    fen_after: str = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
    after_pv: tuple[str, ...] = ("e7e5",),
    missed_mate: bool = False,
    allowed_mate: bool = False,
) -> MoveAnalysis:
    before = EngineResult("e2e4", 0, None, ("e2e4",), 12)
    after = EngineResult(after_pv[0] if after_pv else "e7e5", -200, None, after_pv, 12)
    return MoveAnalysis(
        played_move=played_move,
        player_is_white=True,
        fen_before=fen_before,
        fen_after=fen_after,
        before=before,
        after=after,
        centipawn_loss=None if missed_mate or allowed_mate else 200,
        missed_forced_mate=missed_mate,
        allowed_forced_mate=allowed_mate,
    )


def classification(
    quality: MoveQuality = MoveQuality.MISTAKE, loss: int | None = 200
) -> MoveClassification:
    return MoveClassification(quality, "reason", loss)


@pytest.mark.parametrize(
    ("missed", "allowed", "theme"),
    [
        (True, False, MistakeTheme.MISSED_MATE),
        (False, True, MistakeTheme.ALLOWED_MATE),
    ],
)
def test_mate_themes_have_highest_priority(
    missed: bool, allowed: bool, theme: MistakeTheme
) -> None:
    detection = MistakeDetector().detect(
        analysis(missed_mate=missed, allowed_mate=allowed),
        classification(MoveQuality.BLUNDER, None),
    )

    assert detection.theme is theme
    assert detection.confidence == 1.0
    assert detection.evidence


def test_stockfish_capture_of_more_valuable_piece_detects_hanging_piece() -> None:
    position = "7k/8/3p4/4N3/8/8/8/4K3 b - - 0 1"

    detection = MistakeDetector().detect(
        analysis(
            played_move="f3e5",
            fen_before=position,
            fen_after=position,
            after_pv=("d6e5",),
        ),
        classification(),
    )

    assert detection.theme is MistakeTheme.HANGING_PIECE
    assert detection.confidence == 0.95
    assert "knight on e5" in detection.evidence[0]
    assert "d6e5" in detection.evidence[1]


def test_pawn_capture_in_verified_line_detects_material_loss() -> None:
    position = "7k/8/3p4/4P3/8/8/8/4K3 b - - 0 1"

    detection = MistakeDetector().detect(
        analysis(
            played_move="e4e5",
            fen_before=position,
            fen_after=position,
            after_pv=("d6e5",),
        ),
        classification(),
    )

    assert detection.theme is MistakeTheme.MATERIAL_LOSS
    assert "100 centipawns" in detection.evidence[0]


def test_giving_up_castling_rights_with_king_move_detects_king_safety() -> None:
    before = "4k3/8/8/8/8/8/8/4K2R w K - 0 1"
    after = "4k3/8/8/8/8/8/4K3/7R b - - 1 1"

    detection = MistakeDetector().detect(
        analysis(
            played_move="e1e2",
            fen_before=before,
            fen_after=after,
            after_pv=("e8e7",),
        ),
        classification(),
    )

    assert detection.theme is MistakeTheme.KING_SAFETY
    assert "castling rights" in detection.evidence[0]


def test_unproven_specific_theme_falls_back_to_general_error() -> None:
    detection = MistakeDetector().detect(analysis(), classification())

    assert detection.theme is MistakeTheme.GENERAL_ERROR
    assert detection.confidence == 1.0
    assert "200 centipawns" in detection.evidence[0]


def test_good_move_is_not_assigned_a_speculative_theme() -> None:
    detection = MistakeDetector().detect(
        analysis(), classification(MoveQuality.GOOD, 50)
    )

    assert detection.theme is MistakeTheme.GENERAL_ERROR


def test_theme_confidence_is_validated() -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        ThemeDetection(MistakeTheme.GENERAL_ERROR, (), 1.1)
