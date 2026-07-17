import pytest

from src.commentary import TemplateCommentary
from src.models import (
    EngineResult,
    MoveAnalysis,
    MoveClassification,
    MoveQuality,
    UserLevel,
)


def move_analysis(
    *,
    played_move: str = "f2f3",
    best_move: str = "e2e4",
    loss: int | None = 153,
    missed_mate: bool = False,
    allowed_mate: bool = False,
) -> MoveAnalysis:
    before = EngineResult(best_move, 69, None, (best_move, "e7e5"), 12)
    after = EngineResult("e7e5", -84, None, ("e7e5",), 12)
    return MoveAnalysis(
        played_move=played_move,
        player_is_white=True,
        fen_before="before",
        fen_after="after",
        before=before,
        after=after,
        centipawn_loss=loss,
        missed_forced_mate=missed_mate,
        allowed_forced_mate=allowed_mate,
    )


def classification(
    quality: MoveQuality = MoveQuality.MISTAKE, loss: int | None = 153
) -> MoveClassification:
    return MoveClassification(quality, "test reason", loss)


@pytest.mark.parametrize("level", list(UserLevel))
def test_explanation_is_grounded_in_analysis_for_every_level(
    level: UserLevel,
) -> None:
    result = TemplateCommentary().generate(
        move_analysis(), classification(), level=level
    )

    assert result.source == "template"
    assert result.level is level
    assert "f2f3" in result.text
    assert "e2e4" in result.text
    assert "153 centipawns" in result.text


def test_intermediate_explanation_includes_evaluation_change() -> None:
    result = TemplateCommentary().generate(
        move_analysis(), classification(), level=UserLevel.INTERMEDIATE
    )

    assert "+0.69" in result.text
    assert "-0.84" in result.text


def test_advanced_explanation_includes_depth_and_pv() -> None:
    result = TemplateCommentary().generate(
        move_analysis(), classification(), level=UserLevel.ADVANCED
    )

    assert "depth 12" in result.text
    assert "e2e4 e7e5" in result.text


def test_best_move_explanation_mentions_stockfish_match() -> None:
    result = TemplateCommentary().generate(
        move_analysis(played_move="e2e4", best_move="e2e4", loss=0),
        classification(MoveQuality.BEST, 0),
    )

    assert "best move" in result.text
    assert "matches Stockfish's first choice" in result.text


@pytest.mark.parametrize(
    ("missed", "allowed", "expected"),
    [(True, False, "misses a forced mate"), (False, True, "opponent a forced mate")],
)
def test_mate_templates_take_priority(
    missed: bool, allowed: bool, expected: str
) -> None:
    result = TemplateCommentary().generate(
        move_analysis(loss=None, missed_mate=missed, allowed_mate=allowed),
        classification(MoveQuality.BLUNDER, None),
    )

    assert expected in result.text
