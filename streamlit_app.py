"""Streamlit interface for Chess Improvement Coach."""

from __future__ import annotations

from dataclasses import dataclass
import math
import time

import chess
import streamlit as st

from src.analysis import AnalysisError, MoveAnalyzer
from src.commentary import CommentaryService, create_commentary_service
from src.config import ConfigurationError, Settings, load_settings
from src.database import Database
from src.engine import EngineError, StockfishEngine
from src.game import ChessGame, MoveError
from src.mistake_detector import MistakeDetector
from src.models import AnalyzedMove, EngineResult, MoveQuality, UserLevel
from src.move_classifier import MoveClassifier
from src.report import GameReportBuilder
from src.repositories.sqlalchemy_repository import SQLAlchemyGameHistoryRepository
from src.repositories.interfaces import MistakeSummary
from src.services.history_service import HistoryService
from src.services.practice_service import PracticeMoveError, PracticeService
from src.services.progress_service import ProgressService


UI_STATE_VERSION = "move-context-coach-v1"


@dataclass(slots=True)
class WebResources:
    """Long-lived external resources shared across Streamlit reruns."""

    settings: Settings
    analysis_engine: StockfishEngine
    opponent_engine: StockfishEngine
    commentary: CommentaryService
    database: Database | None
    repository: SQLAlchemyGameHistoryRepository | None
    history: HistoryService | None
    practice: PracticeService | None
    progress: ProgressService | None


@st.cache_resource
def create_resources(cache_version: str = UI_STATE_VERSION) -> WebResources:
    """Create engines and optional persistence once per Streamlit process."""
    del cache_version  # Included in the cache key to invalidate long-lived services.
    settings = load_settings()
    analysis_engine = StockfishEngine.from_settings(settings)
    opponent_engine = StockfishEngine.from_settings(settings)
    analysis_engine.start()
    opponent_engine.start()
    commentary = create_commentary_service(
        provider=settings.ai_provider,
        api_key=settings.ai_api_key,
        model=settings.ai_model,
    )
    database = Database(settings.database_url) if settings.database_url else None
    repository = (
        SQLAlchemyGameHistoryRepository(database) if database is not None else None
    )
    return WebResources(
        settings=settings,
        analysis_engine=analysis_engine,
        opponent_engine=opponent_engine,
        commentary=commentary,
        database=database,
        repository=repository,
        history=(
            HistoryService(repository, username=settings.coach_username)
            if repository is not None
            else None
        ),
        practice=(
            PracticeService(
                repository,
                analysis_engine,
                commentary,
                username=settings.coach_username,
            )
            if repository is not None
            else None
        ),
        progress=(
            ProgressService(repository, username=settings.coach_username)
            if repository is not None
            else None
        ),
    )


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
            file_label = chess.FILE_NAMES[file_index] if rank == (7 if flipped else 0) else ""
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
            f'<div class="theme-meta"><span>{label}</span><strong>{item.count}</strong></div>'
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
        '<div class="eval-wrap">'
        '<div class="eval-bar">'
        f'<div class="eval-white" style="height:{white_percent:.2f}%"></div>'
        f'<div class="eval-score">{label}</div>'
        '<div class="eval-side eval-black-label">Black</div>'
        '<div class="eval-side eval-white-label">White</div>'
        "</div></div>"
    )


def interactive_board_css(
    *,
    selected_square: chess.Square | None,
    flipped: bool,
    last_move: chess.Move | None = None,
    key_prefix: str = "web",
) -> str:
    """Return square-specific styles for the native Streamlit button board."""
    rules = []
    for square in chess.SQUARES:
        rank = chess.square_rank(square)
        file_index = chess.square_file(square)
        background = "#e9edcc" if (rank + file_index) % 2 else "#779556"
        name = chess.square_name(square)
        square_key = f"{key_prefix}_board_{name}"
        rank_label = (
            str(rank + 1)
            if file_index == (7 if flipped else 0)
            else ""
        )
        file_label = (
            chess.FILE_NAMES[file_index]
            if rank == (7 if flipped else 0)
            else ""
        )
        outline = (
            "box-shadow: inset 0 0 0 5px #f2c94c !important;"
            if square == selected_square
            else (
                "box-shadow: inset 0 0 0 5px rgba(242,201,76,.85) !important;"
                if last_move is not None
                and square in {last_move.from_square, last_move.to_square}
                else ""
            )
        )
        rules.append(
            f".st-key-{square_key} button {{ background:{background} !important; "
            f"border:0 !important; border-radius:0 !important; aspect-ratio:1/1; "
            f"padding:0 !important; font-size:clamp(24px,5vw,52px) !important; "
            f"line-height:1 !important; color:#20252f !important; position:relative; "
            f"{outline} }}"
            f".st-key-{square_key} button::before {{ content:'{rank_label}'; "
            f"position:absolute; left:4px; top:2px; font:700 10px ui-monospace; opacity:.7; }}"
            f".st-key-{square_key} button::after {{ content:'{file_label}'; "
            f"position:absolute; right:4px; bottom:2px; font:700 10px ui-monospace; opacity:.7; }}"
        )
    non_first_ranks = range(1, 8) if flipped else range(6, -1, -1)
    container_selector = f".st-key-{key_prefix}_interactive_chess_board"
    row_selectors = ",".join(
        f'{container_selector} [data-testid="stHorizontalBlock"]:'
        f'has(.st-key-{key_prefix}_board_a{rank + 1})'
        for rank in non_first_ranks
    )
    layout = f"""
        {container_selector} {{ max-width:620px; overflow:hidden; border-radius:12px; }}
        {container_selector} [data-testid="stVerticalBlock"],
        {container_selector} [data-testid="stHorizontalBlock"] {{
            gap:0 !important;
        }}
        {container_selector} [data-testid="stElementContainer"],
        {container_selector} [data-testid="stButton"],
        {container_selector} button {{
            margin:0 !important;
        }}
        {container_selector} button p {{
            font-size:clamp(32px, 6vw, 60px) !important;
            line-height:1 !important;
        }}
    """ + row_selectors + """ {
            margin-top:-1rem !important;
        }
    """
    return "<style>" + layout + "".join(rules) + "</style>"


def render_interactive_board(
    board: chess.Board, *, flipped: bool = False, key_prefix: str = "web"
) -> chess.Square | None:
    """Render an 8x8 button board and return the clicked square."""
    selected = st.session_state.get(f"{key_prefix}_selected_square")
    last_move_text = st.session_state.get(f"{key_prefix}_engine_move")
    last_move = (
        chess.Move.from_uci(last_move_text) if last_move_text is not None else None
    )
    st.html(
        interactive_board_css(
            selected_square=selected,
            flipped=flipped,
            last_move=last_move,
            key_prefix=key_prefix,
        )
    )
    ranks = list(range(8) if flipped else range(7, -1, -1))
    files = list(range(7, -1, -1) if flipped else range(8))
    clicked = None
    with st.container(key=f"{key_prefix}_interactive_chess_board"):
        for rank in ranks:
            columns = st.columns(8, gap=None)
            for column, file_index in zip(columns, files, strict=True):
                square = chess.square(file_index, rank)
                piece = board.piece_at(square)
                label = PIECES.get(piece.symbol(), " ") if piece else " "
                with column:
                    if st.button(
                        label,
                        key=f"{key_prefix}_board_{chess.square_name(square)}",
                        use_container_width=True,
                        help=chess.square_name(square),
                    ):
                        clicked = square
    return clicked


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


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp { background: #f5f7f3; }
        .block-container { max-width: 1180px; padding-top: 2rem; }
        .chess-board {
            display:grid;
            grid-template-columns:repeat(8, minmax(0, 1fr));
            width:min(100%, 620px); border-radius:12px;
            overflow:hidden; box-shadow:0 16px 40px rgba(35,48,38,.18);
            border:1px solid rgba(35,48,38,.15);
        }
        .sq {
            position:relative; display:flex; align-items:center; justify-content:center;
            width:100%; aspect-ratio:1 / 1; min-width:0; overflow:hidden;
        }
        .sq.light { background:#e9edcc; }
        .sq.dark { background:#779556; }
        .piece {
            position:absolute; inset:0; display:flex; align-items:center; justify-content:center;
            font-size:clamp(24px, 5.2vw, 54px); line-height:1;
            text-shadow:0 1px 1px rgba(0,0,0,.18);
        }
        .file,.rank { position:absolute; font:bold 11px ui-monospace,monospace; opacity:.72; }
        .file { right:4px; bottom:1px; } .rank { left:4px; top:1px; }
        [data-testid="stMetric"] { background:white; padding:14px; border-radius:12px; border:1px solid #e2e8df; }
        .coach-card { background:white; border-left:5px solid #779556; padding:16px 18px; border-radius:10px; margin-top:12px; }
        .theme-chart { display:flex; flex-direction:column; gap:14px; padding:16px; background:white; border:1px solid #e2e8df; border-radius:12px; }
        .theme-row { display:flex; flex-direction:column; gap:6px; }
        .theme-meta { display:flex; justify-content:space-between; gap:12px; color:#263127; font-size:14px; }
        .theme-track { width:100%; height:12px; background:#e9edcc; border-radius:999px; overflow:hidden; }
        .theme-fill { height:100%; min-width:8px; background:#779556; border-radius:999px; }
        .play-top-spacer { height:3.5rem; }
        .st-key-game_board_with_evaluation { container-type:inline-size; }
        .st-key-game_board_with_evaluation [data-testid="stHorizontalBlock"] { align-items:flex-start; }
        .eval-wrap {
            height:min(48vw,620px);
            height:min(620px, calc((100cqw - 1rem) * 1.2 / 1.32));
            display:flex; justify-content:center;
        }
        .eval-bar { position:relative; width:44px; height:100%; background:#252a25; border-radius:10px; overflow:hidden; border:1px solid #cfd6ca; box-shadow:0 8px 24px rgba(35,48,38,.14); }
        .eval-white { position:absolute; left:0; right:0; bottom:0; background:#f4f5ec; transition:height .35s ease; }
        .eval-score { position:absolute; z-index:2; top:50%; left:50%; transform:translate(-50%,-50%) rotate(-90deg); background:#f4f5ec; color:#252a25; border:1px solid #cfd6ca; font:bold 12px ui-monospace,monospace; padding:4px 7px; border-radius:999px; white-space:nowrap; }
        .eval-side { position:absolute; z-index:2; left:50%; transform:translateX(-50%) rotate(-90deg); font:bold 9px ui-monospace,monospace; letter-spacing:.08em; text-transform:uppercase; }
        .eval-black-label { top:29px; color:#f4f5ec; }
        .eval-white-label { bottom:29px; color:#252a25; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def clear_practice_answer() -> None:
    """Clear position-specific state when the selected game changes."""
    for key in (
        "practice_position",
        "practice_position_id",
        "practice_result",
        "practice_selected_square",
    ):
        st.session_state.pop(key, None)


def render_dashboard(resources: WebResources) -> None:
    st.header("Personal progress")
    st.caption("A live summary calculated from your PostgreSQL coaching history.")
    if resources.progress is None:
        st.warning("Set DATABASE_URL to enable progress tracking.")
        return
    try:
        summary = resources.progress.summary()
    except Exception as error:
        st.error(f"Progress could not be loaded: {type(error).__name__}")
        return

    first = st.columns(4)
    first[0].metric("Completed games", summary.total_games)
    first[1].metric("Analyzed moves", summary.total_analyzed_moves)
    first[2].metric("Detected mistakes", summary.total_mistakes)
    first[3].metric("Due reviews", summary.due_positions)
    second = st.columns(4)
    rate = f"{summary.success_rate:.1%}" if summary.success_rate is not None else "N/A"
    second[0].metric("Practice attempts", summary.total_practice_attempts)
    second[1].metric("Correct answers", summary.correct_practice_attempts)
    second[2].metric("Success rate", rate)
    second[3].metric("Mastered", summary.mastered_positions)

    left, right = st.columns([1.15, 1])
    with left:
        st.subheader("Mistake themes")
        if summary.mistake_counts:
            st.markdown(
                theme_chart_html(summary.mistake_counts),
                unsafe_allow_html=True,
            )
        else:
            st.info("Complete an analyzed game to build your mistake profile.")
    with right:
        st.subheader("Review status")
        st.write(f"Pending: **{summary.pending_positions}**")
        st.write(f"Learning: **{summary.learning_positions}**")
        st.write(f"Mastered: **{summary.mastered_positions}**")
        if summary.due_positions:
            st.success(f"{summary.due_positions} position(s) are ready now.")
        elif summary.next_review_at is not None:
            st.info(f"Next review: {summary.next_review_at:%Y-%m-%d %H:%M UTC}")
        else:
            st.info("No review is scheduled yet.")

    st.subheader("Recent practice trend")
    if summary.success_rate_change is None:
        st.caption("20 attempts are required to compare the latest 10 with the previous 10.")
    else:
        st.metric(
            "Change in success rate",
            f"{summary.recent_success_rate:.1%}",
            f"{summary.success_rate_change * 100:+.1f} percentage points",
        )


def render_practice(resources: WebResources) -> None:
    st.header("Review past mistakes")
    st.caption("Select a piece and its destination. Incorrect legal moves receive fresh coaching feedback.")
    if resources.practice is None:
        st.warning("Set DATABASE_URL to enable saved mistake practice.")
        return

    level = UserLevel.INTERMEDIATE
    result = st.session_state.get("practice_result")
    try:
        games = resources.practice.games()
    except Exception as error:
        st.error(f"Saved games could not be loaded: {type(error).__name__}")
        return
    if not games:
        st.info("No completed games with saved mistakes were found.")
        return

    game_by_id = {game.id: game for game in games}
    game_id = st.selectbox(
        "Choose a game",
        list(game_by_id),
        format_func=lambda value: (
            f"Game #{value} · "
            f"{game_by_id[value].completed_at:%Y-%m-%d %H:%M} · "
            f"{game_by_id[value].result} · "
            f"{game_by_id[value].mistake_count} mistake(s) · "
            f"{game_by_id[value].due_count} due"
        ),
        key="practice_game_id",
        on_change=clear_practice_answer,
    )

    if result is not None and "practice_position" in st.session_state:
        position = st.session_state.practice_position
    else:
        try:
            positions = resources.practice.positions_for_game(game_id)
        except Exception as error:
            st.error(f"Game mistakes could not be loaded: {type(error).__name__}")
            return
        if not positions:
            st.info("This game has no mistake positions due right now.")
            return
        position_by_id = {position.id: position for position in positions}
        position_id = st.selectbox(
            "Choose a mistake",
            list(position_by_id),
            format_func=lambda value: (
                f"Move {position_by_id[value].ply_number or '?'} · "
                f"played {position_by_id[value].played_move or '?'} · "
                f"{position_by_id[value].theme.value.replace('_', ' ').title()}"
            ),
            key="practice_position_id",
            on_change=lambda: st.session_state.pop("practice_selected_square", None),
        )
        position = position_by_id[position_id]
        st.session_state.practice_position = position

    board = chess.Board(position.fen)
    left, right = st.columns([1.35, 1])
    with left:
        clicked_square = None
        if result is None:
            clicked_square = render_interactive_board(
                board,
                flipped=board.turn == chess.BLACK,
                key_prefix="practice",
            )
            st.caption("Select a piece, then select its destination square.")
        else:
            st.markdown(
                board_html(board, flipped=board.turn == chess.BLACK),
                unsafe_allow_html=True,
            )
    with right:
        st.subheader(position.theme.value.replace("_", " ").title())
        st.write(f"Previous attempts: **{position.attempts}**")
        st.write(f"Successful reviews: **{position.successful_attempts}**")
        promotion_names = {
            "Queen": chess.QUEEN,
            "Rook": chess.ROOK,
            "Bishop": chess.BISHOP,
            "Knight": chess.KNIGHT,
        }
        promotion_name = st.radio(
            "Promotion piece",
            list(promotion_names),
            key="practice_promotion",
            horizontal=True,
            disabled=result is not None,
        )
        selected = st.session_state.get("practice_selected_square")
        st.write(
            "Selected square: **"
            + (chess.square_name(selected) if selected is not None else "None")
            + "**"
        )
        if clicked_square is not None and result is None:
            new_selection, move = move_from_clicks(
                board,
                selected,
                clicked_square,
                player_color=board.turn,
                promotion=promotion_names[promotion_name],
            )
            st.session_state.practice_selected_square = new_selection
            if move is None:
                st.rerun()
            try:
                result = resources.practice.submit(position, move, level=level)
            except PracticeMoveError as error:
                st.error(str(error))
            except Exception as error:
                st.error(f"Practice answer failed: {type(error).__name__}")
            else:
                st.session_state.practice_result = result
                st.session_state.practice_selected_square = None
                st.rerun()

        if result is not None:
            if result.correct:
                st.success(f"Correct — {result.best_move} was the stored best move.")
            else:
                st.error(f"The stored best move was {result.best_move}.")
                if result.classification is not None:
                    st.write(f"Move quality: **{result.classification.quality.value}**")
                if result.commentary is not None:
                    st.markdown(
                        f'<div class="coach-card"><b>Coach</b><br>{result.commentary.text}</div>',
                        unsafe_allow_html=True,
                    )
            st.caption(f"Next review: {result.updated_position.next_review_at:%Y-%m-%d %H:%M UTC}")
            if st.button("Choose another mistake", use_container_width=True):
                for key in (
                    "practice_result",
                    "practice_selected_square",
                    "practice_position",
                    "practice_position_id",
                ):
                    st.session_state.pop(key, None)
                st.rerun()


def initialize_game(resources: WebResources, color: chess.Color, elo: int) -> None:
    resources.opponent_engine.configure_strength(elo)
    st.session_state.web_game = ChessGame()
    st.session_state.web_color = color
    st.session_state.web_level = UserLevel.INTERMEDIATE
    st.session_state.web_elo = elo
    st.session_state.web_analysis = []
    st.session_state.web_feedback = None
    st.session_state.web_saved = False
    st.session_state.web_selected_square = None
    if color == chess.BLACK:
        play_engine_move(resources)
    update_position_evaluation(resources)


def play_engine_move(resources: WebResources) -> None:
    game: ChessGame = st.session_state.web_game
    if not game.is_game_over:
        started_at = time.monotonic()
        with st.spinner("Stockfish is thinking..."):
            result = resources.opponent_engine.analyze(game.board, depth=12)
            remaining_delay = 1.0 - (time.monotonic() - started_at)
            if remaining_delay > 0:
                time.sleep(remaining_delay)
        move = chess.Move.from_uci(result.best_move)
        st.session_state.web_engine_move_san = game.board.san(move)
        game.play_uci(result.best_move)
        st.session_state.web_engine_move = result.best_move


def update_position_evaluation(resources: WebResources) -> None:
    """Refresh the lightweight visual evaluation for the current board."""
    game: ChessGame = st.session_state.web_game
    if game.is_game_over:
        return
    with st.spinner("Updating evaluation..."):
        st.session_state.web_position_evaluation = (
            resources.analysis_engine.analyze(game.board, depth=8)
        )


def finish_game(resources: WebResources) -> None:
    game: ChessGame = st.session_state.web_game
    if not game.is_game_over or st.session_state.web_saved:
        return
    report = GameReportBuilder().build(
        game,
        st.session_state.web_analysis,
        player_color=st.session_state.web_color,
    )
    st.session_state.web_report = report
    if resources.history is not None:
        try:
            resources.history.save_completed_game(
                report,
                st.session_state.web_analysis,
                level=st.session_state.web_level,
            )
        except Exception as error:
            st.session_state.web_save_error = type(error).__name__
    st.session_state.web_saved = True


def submit_web_move(resources: WebResources, move_text: str) -> None:
    game: ChessGame = st.session_state.web_game
    try:
        move = chess.Move.from_uci(move_text.strip().lower())
        analysis = MoveAnalyzer(resources.analysis_engine).analyze_move(game.board, move, depth=12)
        game.play_uci(move.uci())
    except (AnalysisError, MoveError, chess.InvalidMoveError, ValueError) as error:
        raise MoveError(str(error)) from error
    classification = MoveClassifier().classify(analysis)
    detection = (
        MistakeDetector().detect(analysis, classification)
        if classification.quality in {MoveQuality.INACCURACY, MoveQuality.MISTAKE, MoveQuality.BLUNDER}
        else None
    )
    commentary = resources.commentary.generate(
        analysis,
        classification,
        level=st.session_state.web_level,
        theme_detection=detection,
    )
    st.session_state.web_analysis.append(
        AnalyzedMove(analysis, classification, detection, commentary)
    )
    st.session_state.web_feedback = st.session_state.web_analysis[-1]
    if not game.is_game_over:
        play_engine_move(resources)
    update_position_evaluation(resources)
    finish_game(resources)


def render_play(resources: WebResources) -> None:
    st.markdown('<div class="play-top-spacer"></div>', unsafe_allow_html=True)
    if "web_game" not in st.session_state:
        minimum, maximum = resources.opponent_engine.elo_range()
        with st.form("new_game"):
            color_name = st.radio("Your color", ["White", "Black"], horizontal=True)
            elo = st.slider("Opponent Elo", minimum, maximum, min(1600, maximum), step=10)
            if st.form_submit_button("Start game", use_container_width=True):
                initialize_game(
                    resources,
                    chess.WHITE if color_name == "White" else chess.BLACK,
                    elo,
                )
                st.rerun()
        return

    game: ChessGame = st.session_state.web_game
    board_area, right = st.columns([1.35, 1])
    with board_area:
        with st.container(key="game_board_with_evaluation"):
            evaluation_column, left = st.columns([0.12, 1.2])
            with evaluation_column:
                st.markdown(
                    evaluation_bar_html(
                        st.session_state.get("web_position_evaluation")
                    ),
                    unsafe_allow_html=True,
                )
            with left:
                clicked_square = render_interactive_board(
                    game.board,
                    flipped=st.session_state.web_color == chess.BLACK,
                )
        st.caption("Select one of your pieces, then select its destination square.")
    with right:
        st.write(f"Opponent: **{st.session_state.web_elo} Elo**")
        turn = "White" if game.turn == chess.WHITE else "Black"
        st.write(f"Turn: **{turn}**")
        engine_move = st.session_state.get("web_engine_move")
        if engine_move is not None:
            engine_san = st.session_state.get("web_engine_move_san", engine_move)
            st.info(f"Stockfish played **{engine_san}** (`{engine_move}`)")
        if game.is_game_over:
            st.success(f"Game over: {game.result}")
            if st.session_state.get("web_save_error"):
                st.warning(
                    "The game finished, but history could not be saved "
                    f"({st.session_state.web_save_error})."
                )
        else:
            promotion_names = {
                "Queen": chess.QUEEN,
                "Rook": chess.ROOK,
                "Bishop": chess.BISHOP,
                "Knight": chess.KNIGHT,
            }
            promotion_name = st.radio(
                "Promotion piece",
                list(promotion_names),
                horizontal=True,
                help="Used only when a pawn reaches the final rank.",
            )
            selected = st.session_state.get("web_selected_square")
            st.write(
                "Selected square: **"
                + (chess.square_name(selected) if selected is not None else "None")
                + "**"
            )
            if clicked_square is not None:
                new_selection, move = move_from_clicks(
                    game.board,
                    selected,
                    clicked_square,
                    player_color=st.session_state.web_color,
                    promotion=promotion_names[promotion_name],
                )
                st.session_state.web_selected_square = new_selection
                if move is None:
                    st.rerun()
                try:
                    submit_web_move(resources, move)
                except MoveError as error:
                    st.error(str(error))
                else:
                    st.rerun()

        feedback = st.session_state.get("web_feedback")
        if feedback is not None:
            st.subheader(feedback.classification.quality.value)
            st.write(f"Stockfish preferred **{feedback.analysis.best_move}**")
            st.markdown(
                f'<div class="coach-card"><b>Coach</b><br>{feedback.commentary.text}</div>',
                unsafe_allow_html=True,
            )
        if st.button("New game", use_container_width=True):
            for key in [
                "web_game", "web_color", "web_level", "web_elo", "web_analysis",
                "web_feedback", "web_saved", "web_report", "web_engine_move",
                "web_engine_move_san", "web_save_error",
                "web_selected_square",
                "web_position_evaluation",
            ]:
                st.session_state.pop(key, None)
            st.rerun()


def main() -> None:
    st.set_page_config(
        page_title="Chess Improvement Coach",
        page_icon="♞",
        layout="wide",
    )
    inject_styles()
    if st.session_state.get("ui_state_version") != UI_STATE_VERSION:
        st.session_state.pop("web_feedback", None)
        st.session_state.pop("practice_result", None)
        st.session_state.ui_state_version = UI_STATE_VERSION
    try:
        resources = create_resources(UI_STATE_VERSION)
    except (ConfigurationError, EngineError) as error:
        st.error(str(error))
        st.stop()

    with st.sidebar:
        st.title("♞ Chess Coach")
        st.caption("Evidence-grounded improvement")
        page = st.radio("Navigate", ["Dashboard", "Practice", "Play"])
        st.divider()
        st.caption(f"User: {resources.settings.coach_username}")
        st.caption("Analysis: full-strength Stockfish")

    if page == "Dashboard":
        render_dashboard(resources)
    elif page == "Practice":
        render_practice(resources)
    else:
        render_play(resources)


if __name__ == "__main__":
    main()
