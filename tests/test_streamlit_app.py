import chess

from src.models import EngineResult, MistakeTheme
from src.repositories.interfaces import MistakeSummary
from src.web.components import (
    board_html,
    evaluation_bar_html,
    move_from_clicks,
    theme_chart_html,
)
from src.web.pages import interactive_board_css
from streamlit_app import main


def test_streamlit_entry_point_exposes_main() -> None:
    assert callable(main)


def test_board_html_renders_all_squares_and_pieces() -> None:
    rendered = board_html(chess.Board())

    assert rendered.count('class="sq ') == 64
    assert rendered.count('class="piece"') == 64
    assert "♔" in rendered
    assert "♚" in rendered
    assert rendered.count('class="file"') == 64


def test_rank_labels_are_attached_to_the_visual_left_edge() -> None:
    normal = board_html(chess.Board())
    flipped = board_html(chess.Board(), flipped=True)

    assert normal.startswith(
        '<div class="chess-board"><div class="sq light"><span class="piece">♜</span>'
        '<span class="file"></span><span class="rank">8</span>'
    )
    assert flipped.startswith(
        '<div class="chess-board"><div class="sq light"><span class="piece">♖</span>'
        '<span class="file"></span><span class="rank">1</span>'
    )


def test_board_clicks_select_a_piece_then_create_a_move() -> None:
    board = chess.Board()

    selected, move = move_from_clicks(board, None, chess.E2, player_color=chess.WHITE)
    assert selected == chess.E2
    assert move is None

    selected, move = move_from_clicks(
        board, selected, chess.E4, player_color=chess.WHITE
    )
    assert selected is None
    assert move == "e2e4"


def test_clicking_another_own_piece_changes_selection() -> None:
    selected, move = move_from_clicks(
        chess.Board(), chess.E2, chess.D2, player_color=chess.WHITE
    )

    assert selected == chess.D2
    assert move is None


def test_promotion_click_uses_selected_piece_type() -> None:
    board = chess.Board("8/P7/8/8/8/8/8/4K2k w - - 0 1")

    selected, move = move_from_clicks(
        board,
        chess.A7,
        chess.A8,
        player_color=chess.WHITE,
        promotion=chess.KNIGHT,
    )

    assert selected is None
    assert move == "a7a8n"


def test_theme_chart_has_labels_counts_and_proportional_bars() -> None:
    rendered = theme_chart_html(
        (
            MistakeSummary(MistakeTheme.KING_SAFETY, 4),
            MistakeSummary(MistakeTheme.MATERIAL_LOSS, 2),
        )
    )

    assert "King Safety" in rendered
    assert "Material Loss" in rendered
    assert "width:100.00%" in rendered
    assert "width:50.00%" in rendered
    assert "<strong>4</strong>" in rendered


def test_evaluation_bar_renders_score_and_white_share() -> None:
    equal = evaluation_bar_html(EngineResult("e2e4", 0, None, ("e2e4",), 8))
    white_better = evaluation_bar_html(EngineResult("e2e4", 400, None, ("e2e4",), 8))

    assert "height:50.00%" in equal
    assert ">+0.00<" in equal
    assert "height:90.91%" in white_better
    assert ">+4.00<" in white_better


def test_evaluation_bar_renders_mate_score() -> None:
    rendered = evaluation_bar_html(EngineResult("h5f7", None, 3, ("h5f7",), 8))

    assert "height:100.00%" in rendered
    assert "M+3" in rendered


def test_interactive_board_css_uses_stable_key_classes() -> None:
    rendered = interactive_board_css(
        selected_square=chess.E2,
        flipped=False,
        key_prefix="practice",
    )

    assert ".st-key-practice_board_e2" in rendered
    assert ".st-key-practice_rank_7" in rendered
    assert "data-testid" not in rendered
    assert ":has(" not in rendered
