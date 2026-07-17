"""Chess game state and legal move management."""

from dataclasses import dataclass, field

import chess


class MoveError(ValueError):
    """Base exception for moves that cannot be played."""


class InvalidMoveFormatError(MoveError):
    """Raised when a move is not valid UCI notation."""


class IllegalMoveError(MoveError):
    """Raised when a validly formatted move is illegal in the position."""


class GameOverError(MoveError):
    """Raised when a move is attempted after the game has ended."""


@dataclass(slots=True)
class ChessGame:
    """Manage a chess position, legal moves, and move history.

    Args:
        fen: Optional starting position in Forsyth-Edwards Notation. A new game
            starts from the standard initial position when omitted.
    """

    fen: str | None = None
    _board: chess.Board = field(init=False, repr=False)
    _starting_fen: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        try:
            self._board = chess.Board(self.fen) if self.fen else chess.Board()
        except ValueError as error:
            raise ValueError(f"Invalid starting FEN: {self.fen}") from error

        if not self._board.is_valid():
            raise ValueError(f"Invalid starting position: {self.fen}")

        self._starting_fen = self._board.fen()

    @property
    def board(self) -> chess.Board:
        """Return a defensive copy of the current board."""
        return self._board.copy(stack=True)

    @property
    def current_fen(self) -> str:
        """Return the current position as FEN."""
        return self._board.fen()

    @property
    def turn(self) -> chess.Color:
        """Return the side to move (``chess.WHITE`` or ``chess.BLACK``)."""
        return self._board.turn

    @property
    def move_history(self) -> tuple[chess.Move, ...]:
        """Return played moves in chronological order."""
        return tuple(self._board.move_stack)

    @property
    def uci_history(self) -> tuple[str, ...]:
        """Return played moves in UCI notation."""
        return tuple(move.uci() for move in self._board.move_stack)

    @property
    def legal_moves(self) -> tuple[str, ...]:
        """Return all legal moves in UCI notation."""
        return tuple(move.uci() for move in self._board.legal_moves)

    @property
    def is_check(self) -> bool:
        """Return whether the side to move is in check."""
        return self._board.is_check()

    @property
    def is_checkmate(self) -> bool:
        """Return whether the current position is checkmate."""
        return self._board.is_checkmate()

    @property
    def is_stalemate(self) -> bool:
        """Return whether the current position is stalemate."""
        return self._board.is_stalemate()

    @property
    def is_game_over(self) -> bool:
        """Return whether the game has ended under standard rules."""
        return self._board.is_game_over(claim_draw=True)

    @property
    def result(self) -> str | None:
        """Return the game result, or ``None`` while play can continue."""
        if not self.is_game_over:
            return None
        return self._board.result(claim_draw=True)

    def play_uci(self, move_text: str) -> chess.Move:
        """Validate and play a move written in UCI notation.

        Promotion moves must include the promoted piece, for example ``e7e8q``.
        The returned move is also appended to the game history.
        """
        if self.is_game_over:
            raise GameOverError(f"The game is over ({self.result}); no more moves can be played.")

        normalized_move = move_text.strip().lower()
        try:
            move = chess.Move.from_uci(normalized_move)
        except (chess.InvalidMoveError, ValueError) as error:
            raise InvalidMoveFormatError(
                f"'{move_text}' is not valid UCI notation. Use a move such as e2e4."
            ) from error

        if move not in self._board.legal_moves:
            raise IllegalMoveError(
                f"Move {normalized_move} is illegal in the current position."
            )

        self._board.push(move)
        return move

    def undo(self) -> chess.Move:
        """Undo and return the last move.

        Raises:
            MoveError: If no move has been played.
        """
        if not self._board.move_stack:
            raise MoveError("There is no move to undo.")
        return self._board.pop()

    def reset(self) -> None:
        """Restore the position used when this game instance was created."""
        self._board = chess.Board(self._starting_fen)
