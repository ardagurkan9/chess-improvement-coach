"""Pure web presentation helpers with no Streamlit runtime dependency."""

import math

import chess

from src.models import EngineResult
from src.repositories.interfaces import MistakeSummary

PIECES = {
    "K": "♔",
    "Q": "♕",
    "R": "♖",
    "B": "♗",
    "N": "♘",
    "P": "♙",
    "k": "♚",
    "q": "♛",
    "r": "♜",
    "b": "♝",
    "n": "♞",
    "p": "♟",
}


def board_html(board: chess.Board, *, flipped: bool = False) -> str:
    """Render a coordinate-labelled chess board without a frontend dependency."""
    ranks = range(8) if flipped else range(7, -1, -1)
    files = range(7, -1, -1) if flipped else range(8)
    cells: list[str] = []
    for rank in ranks:
        for file_index in files:
            square = chess.square(file_index, rank)
            piece = board.piece_at(square)
            symbol = PIECES.get(piece.symbol(), "") if piece else ""
            color = "light" if (rank + file_index) % 2 else "dark"
            file_label = (
                chess.FILE_NAMES[file_index] if rank == (7 if flipped else 0) else ""
            )
            rank_label = str(rank + 1) if file_index == (7 if flipped else 0) else ""
            cells.append(
                f'<div class="sq {color}"><span class="piece">{symbol}</span>'
                f'<span class="file">{file_label}</span>'
                f'<span class="rank">{rank_label}</span></div>'
            )
    return '<div class="chess-board">' + "".join(cells) + "</div>"


def theme_chart_html(items: tuple[MistakeSummary, ...]) -> str:
    """Render mistake counts as labelled proportional bars."""
    if not items:
        return ""
    maximum = max(item.count for item in items)
    rows = []
    for item in items:
        label = item.theme.value.replace("_", " ").title()
        width = item.count / maximum * 100
        rows.append(
            '<div class="theme-row">'
            f'<div class="theme-meta"><span>{label}</span>'
            f"<strong>{item.count}</strong></div>"
            '<div class="theme-track">'
            f'<div class="theme-fill" style="width:{width:.2f}%"></div>'
            "</div></div>"
        )
    return '<div class="theme-chart">' + "".join(rows) + "</div>"


def evaluation_bar_html(result: EngineResult | None) -> str:
    """Render a White-perspective vertical evaluation bar."""
    if result is None:
        white_percent = 50.0
        label = "0.00"
    elif result.mate is not None:
        white_percent = 100.0 if result.mate > 0 else 0.0
        label = f"M{result.mate:+d}"
    elif result.score_cp is not None:
        white_percent = 100 / (1 + math.pow(10, -result.score_cp / 400))
        label = f"{result.score_cp / 100:+.2f}"
    else:
        white_percent = 50.0
        label = "?"
    return (
        '<div class="eval-wrap"><div class="eval-bar">'
        f'<div class="eval-white" style="height:{white_percent:.2f}%"></div>'
        f'<div class="eval-score">{label}</div>'
        '<div class="eval-side eval-black-label">Black</div>'
        '<div class="eval-side eval-white-label">White</div></div></div>'
    )


def move_from_clicks(
    board: chess.Board,
    selected_square: chess.Square | None,
    clicked_square: chess.Square,
    *,
    player_color: chess.Color,
    promotion: chess.PieceType = chess.QUEEN,
) -> tuple[chess.Square | None, str | None]:
    """Turn source/target clicks into a legal-attempt UCI move."""
    clicked_piece = board.piece_at(clicked_square)
    if selected_square is None:
        if clicked_piece is not None and clicked_piece.color == player_color:
            return clicked_square, None
        return None, None
    if clicked_square == selected_square:
        return None, None
    if clicked_piece is not None and clicked_piece.color == player_color:
        return clicked_square, None

    selected_piece = board.piece_at(selected_square)
    promotion_piece = None
    if (
        selected_piece is not None
        and selected_piece.piece_type == chess.PAWN
        and chess.square_rank(clicked_square) in {0, 7}
    ):
        promotion_piece = promotion
    move = chess.Move(selected_square, clicked_square, promotion=promotion_piece)
    return None, move.uci()
