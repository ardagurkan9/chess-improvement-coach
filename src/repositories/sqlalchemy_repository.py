"""SQLAlchemy repository for games, mistakes, and practice positions."""

import chess
from sqlalchemy import func, select

from src.database import Database
from src.db_models import (
    GameRecord,
    MistakeRecord,
    MoveAnalysisRecord,
    PlayerColor,
    PracticePositionRecord,
    UserRecord,
)
from src.models import AnalyzedMove, GameReport, UserLevel
from src.repositories.interfaces import MistakeSummary


class SQLAlchemyGameHistoryRepository:
    """Persist coaching history through a shared ``Database`` instance."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def save_game(
        self,
        *,
        username: str,
        level: UserLevel,
        report: GameReport,
        analyzed_moves: tuple[AnalyzedMove, ...],
    ) -> int:
        """Save a completed game, its analyses, mistakes, and review positions."""
        clean_username = username.strip()
        if not clean_username:
            raise ValueError("Username cannot be empty.")

        with self.database.session() as session:
            user = session.scalar(
                select(UserRecord).where(UserRecord.username == clean_username)
            )
            if user is None:
                user = UserRecord(username=clean_username, level=level)
                session.add(user)
            else:
                user.level = level

            game = GameRecord(
                user=user,
                player_color=(
                    PlayerColor.WHITE if report.player_is_white else PlayerColor.BLACK
                ),
                result=report.result,
                pgn=report.pgn,
            )
            session.add(game)

            for analyzed in analyzed_moves:
                analysis = analyzed.analysis
                move_record = MoveAnalysisRecord(
                    game=game,
                    ply_number=chess.Board(analysis.fen_before).ply() + 1,
                    played_move=analysis.played_move,
                    best_move=analysis.best_move,
                    fen_before=analysis.fen_before,
                    fen_after=analysis.fen_after,
                    score_before_cp=analysis.before.score_cp,
                    score_after_cp=analysis.after.score_cp,
                    mate_before=analysis.before.mate,
                    mate_after=analysis.after.mate,
                    centipawn_loss=analyzed.classification.centipawn_loss,
                    quality=analyzed.classification.quality,
                    principal_variation=list(analysis.before.pv),
                    commentary=(
                        analyzed.commentary.text if analyzed.commentary is not None else None
                    ),
                    commentary_source=(
                        analyzed.commentary.source
                        if analyzed.commentary is not None
                        else None
                    ),
                )
                session.add(move_record)

                detection = analyzed.theme_detection
                if detection is None:
                    continue
                mistake = MistakeRecord(
                    move_analysis=move_record,
                    theme=detection.theme,
                    evidence=list(detection.evidence),
                    confidence=detection.confidence,
                )
                session.add(
                    PracticePositionRecord(
                        user=user,
                        source_mistake=mistake,
                        fen=analysis.fen_before,
                        solution_moves=list(analysis.before.pv),
                    )
                )

            session.flush()
            game_id = game.id

        return game_id

    def recurring_mistakes(self, *, username: str) -> tuple[MistakeSummary, ...]:
        """Count mistake themes across every game belonging to a user."""
        statement = (
            select(MistakeRecord.theme, func.count(MistakeRecord.id))
            .join(MistakeRecord.move_analysis)
            .join(MoveAnalysisRecord.game)
            .join(GameRecord.user)
            .where(UserRecord.username == username.strip())
            .group_by(MistakeRecord.theme)
            .order_by(func.count(MistakeRecord.id).desc(), MistakeRecord.theme)
        )
        with self.database.session() as session:
            rows = session.execute(statement).all()
        return tuple(MistakeSummary(theme=theme, count=count) for theme, count in rows)
