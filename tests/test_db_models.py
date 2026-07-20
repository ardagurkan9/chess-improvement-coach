from sqlalchemy import select

from src.database import Database
from src.db_models import (
    Base,
    GameRecord,
    MistakeRecord,
    MoveAnalysisRecord,
    PlayerColor,
    PracticePositionRecord,
    PracticeStatus,
    UserRecord,
)
from src.models import MistakeTheme, MoveQuality, UserLevel


def test_metadata_contains_the_initial_coaching_tables() -> None:
    assert set(Base.metadata.tables) == {
        "users",
        "games",
        "move_analyses",
        "mistakes",
        "practice_positions",
        "practice_attempts",
    }


def test_complete_coaching_history_can_be_persisted() -> None:
    database = Database("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(database.engine)

    user = UserRecord(username="student", level=UserLevel.INTERMEDIATE)
    game = GameRecord(
        user=user,
        player_color=PlayerColor.WHITE,
        result="0-1",
        pgn="1. f3 e5 2. g4 Qh4# 0-1",
    )
    move = MoveAnalysisRecord(
        game=game,
        ply_number=3,
        played_move="g2g4",
        best_move="g2g3",
        fen_before="before",
        fen_after="after",
        score_before_cp=0,
        score_after_cp=None,
        mate_before=None,
        mate_after=-1,
        centipawn_loss=None,
        quality=MoveQuality.BLUNDER,
        principal_variation=["g2g3", "d8h4"],
        commentary="This allows mate.",
        commentary_source="gemini",
    )
    mistake = MistakeRecord(
        move_analysis=move,
        theme=MistakeTheme.ALLOWED_MATE,
        evidence=["The opponent has a forced mate."],
        confidence=1.0,
    )
    practice = PracticePositionRecord(
        user=user,
        source_mistake=mistake,
        fen="before",
        solution_moves=["g2g3"],
    )

    with database.session() as session:
        session.add(practice)

    with database.session() as session:
        stored_user = session.scalar(select(UserRecord))
        stored_practice = session.scalar(select(PracticePositionRecord))
        assert stored_user is not None
        assert stored_practice is not None
        assert stored_user.games[0].move_analyses[0].mistake is not None
        assert stored_user.games[0].move_analyses[0].mistake.theme is MistakeTheme.ALLOWED_MATE
        assert stored_practice.status is PracticeStatus.PENDING
        assert stored_practice.solution_moves == ["g2g3"]

    database.close()
