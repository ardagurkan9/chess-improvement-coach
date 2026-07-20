"""Stable Streamlit entry point; implementation lives in ``src.web``."""

from src.web.pages import (
    board_html,
    evaluation_bar_html,
    main,
    move_from_clicks,
    theme_chart_html,
)

__all__ = [
    "board_html",
    "evaluation_bar_html",
    "main",
    "move_from_clicks",
    "theme_chart_html",
]


if __name__ == "__main__":
    main()
