import pytest

from src.models import EngineResult, MoveAnalysis, MoveQuality
from src.move_classifier import (
    ClassificationError,
    ClassificationThresholds,
    MoveClassifier,
)


def engine_result(
    *, best_move: str = "e2e4", score_cp: int | None = 0, mate: int | None = None
) -> EngineResult:
    return EngineResult(
        best_move=best_move,
        score_cp=score_cp,
        mate=mate,
        pv=(best_move,),
        depth=12,
    )


def analysis(
    loss: int | None,
    *,
    played_move: str = "d2d4",
    best_move: str = "e2e4",
    before_mate: int | None = None,
    after_mate: int | None = None,
    missed_mate: bool = False,
    allowed_mate: bool = False,
) -> MoveAnalysis:
    return MoveAnalysis(
        played_move=played_move,
        player_is_white=True,
        fen_before="before",
        fen_after="after",
        before=engine_result(
            best_move=best_move,
            score_cp=None if before_mate is not None else 0,
            mate=before_mate,
        ),
        after=engine_result(
            score_cp=None if after_mate is not None else 0,
            mate=after_mate,
        ),
        centipawn_loss=loss,
        missed_forced_mate=missed_mate,
        allowed_forced_mate=allowed_mate,
    )


@pytest.mark.parametrize(
    ("loss", "expected"),
    [
        (0, MoveQuality.BEST),
        (15, MoveQuality.BEST),
        (16, MoveQuality.EXCELLENT),
        (40, MoveQuality.EXCELLENT),
        (41, MoveQuality.GOOD),
        (80, MoveQuality.GOOD),
        (81, MoveQuality.INACCURACY),
        (150, MoveQuality.INACCURACY),
        (151, MoveQuality.MISTAKE),
        (300, MoveQuality.MISTAKE),
        (301, MoveQuality.BLUNDER),
    ],
)
def test_centipawn_boundaries(loss: int, expected: MoveQuality) -> None:
    classification = MoveClassifier().classify(analysis(loss))

    assert classification.quality is expected
    assert classification.centipawn_loss == loss
    if expected is not MoveQuality.BEST:
        assert str(loss) in classification.reason


def test_stockfish_first_choice_is_best_despite_small_analysis_noise() -> None:
    classification = MoveClassifier().classify(
        analysis(20, played_move="e2e4", best_move="e2e4")
    )

    assert classification.quality is MoveQuality.BEST
    assert "first choice" in classification.reason


@pytest.mark.parametrize(
    ("missed_mate", "allowed_mate", "reason"),
    [(True, False, "misses"), (False, True, "opponent")],
)
def test_mate_blunders_override_centipawn_and_best_move(
    missed_mate: bool, allowed_mate: bool, reason: str
) -> None:
    classification = MoveClassifier().classify(
        analysis(
            None,
            played_move="e2e4",
            best_move="e2e4",
            before_mate=3 if missed_mate else None,
            after_mate=-2 if allowed_mate else None,
            missed_mate=missed_mate,
            allowed_mate=allowed_mate,
        )
    )

    assert classification.quality is MoveQuality.BLUNDER
    assert reason in classification.reason


def test_other_mate_transition_is_classified_without_fake_cp_value() -> None:
    classification = MoveClassifier().classify(
        analysis(None, before_mate=3, after_mate=2)
    )

    assert classification.quality is MoveQuality.GOOD
    assert classification.centipawn_loss is None


def test_incomplete_analysis_is_rejected() -> None:
    with pytest.raises(ClassificationError, match="neither"):
        MoveClassifier().classify(analysis(None))


def test_negative_centipawn_loss_is_rejected() -> None:
    with pytest.raises(ClassificationError, match="negative"):
        MoveClassifier().classify(analysis(-1))


@pytest.mark.parametrize(
    "values",
    [
        {"best": -1},
        {"best": 40, "excellent": 40},
        {"good": 301, "inaccuracy": 150},
    ],
)
def test_invalid_thresholds_are_rejected(values: dict[str, int]) -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        ClassificationThresholds(**values)
