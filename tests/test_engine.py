from pathlib import Path
from unittest.mock import MagicMock, patch

import chess
import chess.engine
import pytest

from src.engine import (
    EngineAnalysisError,
    EngineConnectionError,
    StockfishEngine,
)


def engine_info(*, score: chess.engine.Score | None = None) -> dict[str, object]:
    return {
        "score": chess.engine.PovScore(score or chess.engine.Cp(24), chess.WHITE),
        "pv": [chess.Move.from_uci("e2e4"), chess.Move.from_uci("e7e5")],
        "depth": 12,
    }


def test_start_rejects_missing_executable(tmp_path: Path) -> None:
    client = StockfishEngine(tmp_path / "missing-stockfish.exe")

    with pytest.raises(EngineConnectionError, match="does not exist"):
        client.start()


def test_analyze_returns_normalized_white_perspective_result(tmp_path: Path) -> None:
    executable = tmp_path / "stockfish.exe"
    executable.touch()
    process = MagicMock()
    process.analyse.return_value = engine_info()

    with patch("src.engine.chess.engine.SimpleEngine.popen_uci", return_value=process):
        with StockfishEngine(executable) as client:
            result = client.analyze(chess.Board())
            assert client.is_running

    assert result.best_move == "e2e4"
    assert result.score_cp == 24
    assert result.mate is None
    assert result.pv == ("e2e4", "e7e5")
    assert result.depth == 12
    process.quit.assert_called_once()
    assert not client.is_running


def test_analyze_preserves_mate_score(tmp_path: Path) -> None:
    executable = tmp_path / "stockfish.exe"
    executable.touch()
    process = MagicMock()
    process.analyse.return_value = engine_info(score=chess.engine.Mate(3))

    with patch("src.engine.chess.engine.SimpleEngine.popen_uci", return_value=process):
        result = StockfishEngine(executable).analyze(chess.STARTING_FEN)

    assert result.is_mate
    assert result.mate == 3
    assert result.score_cp is None


@pytest.mark.parametrize(
    ("depth", "time_limit", "message"),
    [(None, None, "at least one"), (0, None, "depth"), (None, 0, "time_limit")],
)
def test_analyze_rejects_invalid_limits(
    depth: int | None, time_limit: float | None, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        StockfishEngine("unused").analyze(
            chess.Board(), depth=depth, time_limit=time_limit
        )


def test_analyze_rejects_invalid_fen() -> None:
    with pytest.raises(EngineAnalysisError, match="Invalid FEN"):
        StockfishEngine("unused").analyze("not-a-fen")


def test_close_is_safe_before_start() -> None:
    client = StockfishEngine("unused")

    client.close()
    client.close()

    assert not client.is_running
