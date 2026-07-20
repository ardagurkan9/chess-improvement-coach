"""SQLAlchemy repository for games, mistakes, and practice positions."""

import chess
from datetime import datetime

from sqlalchemy import case, func, or_, select

from src.database import Database
from src.db_models import (
    GameRecord,
    MistakeRecord,
    MoveAnalysisRecord,
    PlayerColor,
    PracticeAttemptRecord,
    PracticePositionRecord,
    PracticeStatus,
    UserRecord,
)
from src.models import AnalyzedMove, GameReport, MistakeTheme, MoveQuality, UserLevel
from src.repositories.interfaces import MistakeSummary, PracticePosition


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

    def due_practice_position(
        self, *, username: str, as_of: datetime
    ) -> PracticePosition | None:
        """Return the oldest due position for the requested user."""
        statement = (
            select(PracticePositionRecord, MistakeRecord)
            .join(PracticePositionRecord.user)
            .join(PracticePositionRecord.source_mistake)
            .where(
                UserRecord.username == username.strip(),
                or_(
                    PracticePositionRecord.next_review_at.is_(None),
                    PracticePositionRecord.next_review_at <= as_of,
                ),
            )
            .order_by(
                case(
                    (PracticePositionRecord.next_review_at.is_(None), 0),
                    else_=1,
                ),
                PracticePositionRecord.next_review_at,
                PracticePositionRecord.created_at,
            )
            .limit(1)
        )
        with self.database.session() as session:
            row = session.execute(statement).first()
            if row is None:
                return None
            position, mistake = row
            return self._practice_position(position, mistake)

    def record_practice_attempt(
        self,
        *,
        username: str,
        position_id: int,
        attempted_move: str,
        correct: bool,
        quality: MoveQuality | None,
        detected_theme: MistakeTheme | None,
        commentary: str | None,
        commentary_source: str | None,
        status: str,
        solved: bool,
        next_review_at: datetime,
    ) -> PracticePosition:
        """Update review counters and scheduling for one owned position."""
        statement = (
            select(PracticePositionRecord, MistakeRecord)
            .join(PracticePositionRecord.user)
            .join(PracticePositionRecord.source_mistake)
            .where(
                PracticePositionRecord.id == position_id,
                UserRecord.username == username.strip(),
            )
        )
        with self.database.session() as session:
            row = session.execute(statement).first()
            if row is None:
                raise LookupError("Practice position was not found for this user.")
            position, mistake = row
            position.attempts += 1
            if correct:
                position.successful_attempts += 1
            position.status = PracticeStatus(status)
            position.solved = solved
            position.next_review_at = next_review_at
            session.add(
                PracticeAttemptRecord(
                    practice_position=position,
                    attempted_move=attempted_move,
                    correct=correct,
                    quality=quality,
                    detected_theme=detected_theme,
                    commentary=commentary,
                    commentary_source=commentary_source,
                    scheduled_review_at=next_review_at,
                )
            )
            session.flush()
            return self._practice_position(position, mistake)

    @staticmethod
    def _practice_position(
        position: PracticePositionRecord, mistake: MistakeRecord
    ) -> PracticePosition:
        return PracticePosition(
            id=position.id,
            fen=position.fen,
            theme=mistake.theme,
            evidence=tuple(mistake.evidence),
            solution_moves=tuple(position.solution_moves),
            status=position.status.value,
            attempts=position.attempts,
            successful_attempts=position.successful_attempts,
            next_review_at=position.next_review_at,
        )
