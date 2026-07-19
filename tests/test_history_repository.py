import chess

from src.database import Database
from src.db_models import Base
from src.models import (
    AnalyzedMove,
    CommentaryResult,
    EngineResult,
    GameReport,
    MistakeTheme,
    MoveAnalysis,
    MoveClassification,
    MoveQuality,
    ThemeDetection,
    UserLevel,
)
from src.repositories.sqlalchemy_repository import SQLAlchemyGameHistoryRepository


def analyzed_blunder() -> AnalyzedMove:
    board = chess.Board()
    before_fen = board.fen()
    board.push_uci("f2f3")
    return AnalyzedMove(
        analysis=MoveAnalysis(
            played_move="f2f3",
            player_is_white=True,
            fen_before=before_fen,
            fen_after=board.fen(),
            before=EngineResult("e2e4", 30, None, ("e2e4", "e7e5"), 12),
            after=EngineResult("e7e5", -320, None, ("e7e5",), 12),
            centipawn_loss=350,
        ),
        classification=MoveClassification(
            MoveQuality.BLUNDER, "Large evaluation loss.", 350
        ),
        theme_detection=ThemeDetection(
            MistakeTheme.KING_SAFETY,
            ("The move weakens the king.",),
            0.85,
        ),
        commentary=CommentaryResult(
            "Keep the king shelter intact.",
            UserLevel.BEGINNER,
            source="gemini",
        ),
    )


def report() -> GameReport:
    counts = {quality: 0 for quality in MoveQuality}
    counts[MoveQuality.BLUNDER] = 1
    themes = {theme: 0 for theme in MistakeTheme}
    themes[MistakeTheme.KING_SAFETY] = 1
    move = analyzed_blunder()
    return GameReport(
        result="0-1",
        player_is_white=True,
        total_user_moves=1,
        average_centipawn_loss=350.0,
        quality_counts=counts,
        theme_counts=themes,
        missed_mates=0,
        allowed_mates=0,
        biggest_error=move,
        improvement_areas=("Protect the king.",),
        pgn="1. f3 e5 0-1",
    )


def test_repository_saves_history_and_counts_recurring_mistakes() -> None:
    database = Database("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(database.engine)
    repository = SQLAlchemyGameHistoryRepository(database)

    first_id = repository.save_game(
        username="student",
        level=UserLevel.BEGINNER,
        report=report(),
        analyzed_moves=(analyzed_blunder(),),
    )
    second_id = repository.save_game(
        username="student",
        level=UserLevel.INTERMEDIATE,
        report=report(),
        analyzed_moves=(analyzed_blunder(),),
    )
    summaries = repository.recurring_mistakes(username="student")

    assert first_id != second_id
    assert len(summaries) == 1
    assert summaries[0].theme is MistakeTheme.KING_SAFETY
    assert summaries[0].count == 2
    database.close()
