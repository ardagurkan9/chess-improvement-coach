"""Stockfish process management and position analysis."""

from pathlib import Path
from types import TracebackType
from typing import Self

import chess
import chess.engine

from src.config import Settings
from src.models import EngineResult


class EngineError(RuntimeError):
    """Base exception for Stockfish integration failures."""


class EngineConnectionError(EngineError):
    """Raised when Stockfish cannot be started or contacted."""


class EngineAnalysisError(EngineError):
    """Raised when a position cannot be analyzed."""


class StockfishEngine:
    """Own a Stockfish process and expose normalized analysis results."""

    def __init__(self, executable_path: str | Path) -> None:
        self.executable_path = Path(executable_path)
        self._engine: chess.engine.SimpleEngine | None = None

    @classmethod
    def from_settings(cls, settings: Settings) -> Self:
        """Create an engine client from validated application settings."""
        return cls(settings.stockfish_path)

    @property
    def is_running(self) -> bool:
        """Return whether this client currently owns an engine process."""
        return self._engine is not None

    def start(self) -> None:
        """Start Stockfish and complete its UCI initialization."""
        if self.is_running:
            return

        if not self.executable_path.is_file():
            raise EngineConnectionError(
                f"Stockfish executable does not exist: {self.executable_path}"
            )

        try:
            self._engine = chess.engine.SimpleEngine.popen_uci(
                str(self.executable_path)
            )
        except (OSError, chess.engine.EngineError) as error:
            raise EngineConnectionError(
                f"Could not start Stockfish at {self.executable_path}: {error}"
            ) from error

    def analyze(
        self,
        position: chess.Board | str,
        *,
        depth: int | None = 12,
        time_limit: float | None = None,
    ) -> EngineResult:
        """Analyze a board or FEN and return a normalized result.

        Args:
            position: A python-chess board or a FEN string.
            depth: Maximum search depth. Set to ``None`` when using only time.
            time_limit: Optional analysis time in seconds.
        """
        board = self._to_board(position)
        limit = self._create_limit(depth=depth, time_limit=time_limit)
        self.start()
        assert self._engine is not None

        try:
            info = self._engine.analyse(board, limit)
        except (chess.engine.EngineError, chess.engine.EngineTerminatedError) as error:
            self._engine = None
            raise EngineAnalysisError(f"Stockfish analysis failed: {error}") from error

        return self._normalize_result(info)

    def elo_range(self) -> tuple[int, int]:
        """Return the Elo limits advertised by the running Stockfish binary."""
        self.start()
        assert self._engine is not None
        elo_option = self._engine.options.get("UCI_Elo")
        limit_option = self._engine.options.get("UCI_LimitStrength")
        if elo_option is None or limit_option is None:
            raise EngineConnectionError(
                "This Stockfish binary does not support UCI Elo limiting."
            )
        if not isinstance(elo_option.min, int) or not isinstance(elo_option.max, int):
            raise EngineConnectionError("Stockfish returned invalid UCI Elo limits.")
        return elo_option.min, elo_option.max

    def configure_strength(self, elo: int) -> None:
        """Limit this engine process to a supported target Elo."""
        minimum, maximum = self.elo_range()
        if not minimum <= elo <= maximum:
            raise ValueError(f"Elo must be between {minimum} and {maximum}.")
        assert self._engine is not None
        try:
            self._engine.configure(
                {"UCI_LimitStrength": True, "UCI_Elo": elo}
            )
        except (chess.engine.EngineError, chess.engine.EngineTerminatedError) as error:
            raise EngineConnectionError(
                f"Stockfish strength could not be configured: {error}"
            ) from error

    def close(self) -> None:
        """Stop Stockfish safely. Calling this repeatedly is allowed."""
        engine, self._engine = self._engine, None
        if engine is None:
            return
        try:
            engine.quit()
        except (OSError, chess.engine.EngineError):
            engine.close()

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    @staticmethod
    def _to_board(position: chess.Board | str) -> chess.Board:
        if isinstance(position, chess.Board):
            if not position.is_valid():
                raise EngineAnalysisError("The supplied board position is invalid.")
            return position.copy(stack=False)

        try:
            board = chess.Board(position)
        except ValueError as error:
            raise EngineAnalysisError(f"Invalid FEN: {position}") from error
        if not board.is_valid():
            raise EngineAnalysisError(f"Invalid position in FEN: {position}")
        return board

    @staticmethod
    def _create_limit(
        *, depth: int | None, time_limit: float | None
    ) -> chess.engine.Limit:
        if depth is None and time_limit is None:
            raise ValueError("Set at least one of depth or time_limit.")
        if depth is not None and depth < 1:
            raise ValueError("depth must be at least 1.")
        if time_limit is not None and time_limit <= 0:
            raise ValueError("time_limit must be greater than 0.")
        return chess.engine.Limit(depth=depth, time=time_limit)

    @staticmethod
    def _normalize_result(info: dict[str, object]) -> EngineResult:
        score = info.get("score")
        pv = info.get("pv")
        if not isinstance(score, chess.engine.PovScore):
            raise EngineAnalysisError("Stockfish returned no position score.")
        if not isinstance(pv, list) or not pv:
            raise EngineAnalysisError("Stockfish returned no principal variation.")

        white_score = score.white()
        mate = white_score.mate()
        score_cp = None if mate is not None else white_score.score()
        moves = tuple(move.uci() for move in pv if isinstance(move, chess.Move))
        if not moves:
            raise EngineAnalysisError("Stockfish returned an invalid principal variation.")

        depth_value = info.get("depth")
        return EngineResult(
            best_move=moves[0],
            score_cp=score_cp,
            mate=mate,
            pv=moves,
            depth=depth_value if isinstance(depth_value, int) else None,
        )
