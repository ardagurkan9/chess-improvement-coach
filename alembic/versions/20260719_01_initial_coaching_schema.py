"""Create the initial coaching history schema.

Revision ID: 20260719_01
Revises: None
Create Date: 2026-07-19
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260719_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("level", sa.String(length=12), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    op.create_table(
        "games",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("player_color", sa.String(length=5), nullable=False),
        sa.Column("result", sa.String(length=16), nullable=False),
        sa.Column("pgn", sa.Text(), nullable=False),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "completed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_games_user_id"), "games", ["user_id"], unique=False)

    op.create_table(
        "move_analyses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("ply_number", sa.Integer(), nullable=False),
        sa.Column("played_move", sa.String(length=5), nullable=False),
        sa.Column("best_move", sa.String(length=5), nullable=False),
        sa.Column("fen_before", sa.Text(), nullable=False),
        sa.Column("fen_after", sa.Text(), nullable=False),
        sa.Column("score_before_cp", sa.Integer(), nullable=True),
        sa.Column("score_after_cp", sa.Integer(), nullable=True),
        sa.Column("mate_before", sa.Integer(), nullable=True),
        sa.Column("mate_after", sa.Integer(), nullable=True),
        sa.Column("centipawn_loss", sa.Integer(), nullable=True),
        sa.Column("quality", sa.String(length=10), nullable=False),
        sa.Column("principal_variation", sa.JSON(), nullable=False),
        sa.Column("commentary", sa.Text(), nullable=True),
        sa.Column("commentary_source", sa.String(length=32), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "centipawn_loss IS NULL OR centipawn_loss >= 0",
            name="ck_nonnegative_centipawn_loss",
        ),
        sa.CheckConstraint("ply_number > 0", name="ck_positive_ply_number"),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("game_id", "ply_number", name="uq_game_ply_number"),
    )
    op.create_index(
        op.f("ix_move_analyses_game_id"), "move_analyses", ["game_id"], unique=False
    )
    op.create_index(
        op.f("ix_move_analyses_quality"), "move_analyses", ["quality"], unique=False
    )

    op.create_table(
        "mistakes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("move_analysis_id", sa.Integer(), nullable=False),
        sa.Column("theme", sa.String(length=13), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_mistake_confidence_range"
        ),
        sa.ForeignKeyConstraint(
            ["move_analysis_id"], ["move_analyses.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_mistakes_move_analysis_id"),
        "mistakes",
        ["move_analysis_id"],
        unique=True,
    )
    op.create_index(op.f("ix_mistakes_theme"), "mistakes", ["theme"], unique=False)

    op.create_table(
        "practice_positions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("source_mistake_id", sa.Integer(), nullable=False),
        sa.Column("fen", sa.Text(), nullable=False),
        sa.Column("solution_moves", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=8), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("solved", sa.Boolean(), nullable=False),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_nonnegative_attempts"),
        sa.ForeignKeyConstraint(
            ["source_mistake_id"], ["mistakes.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_practice_positions_source_mistake_id"),
        "practice_positions",
        ["source_mistake_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_practice_positions_status"),
        "practice_positions",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_practice_positions_user_id"),
        "practice_positions",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_practice_positions_user_id"), table_name="practice_positions")
    op.drop_index(op.f("ix_practice_positions_status"), table_name="practice_positions")
    op.drop_index(
        op.f("ix_practice_positions_source_mistake_id"), table_name="practice_positions"
    )
    op.drop_table("practice_positions")
    op.drop_index(op.f("ix_mistakes_theme"), table_name="mistakes")
    op.drop_index(op.f("ix_mistakes_move_analysis_id"), table_name="mistakes")
    op.drop_table("mistakes")
    op.drop_index(op.f("ix_move_analyses_quality"), table_name="move_analyses")
    op.drop_index(op.f("ix_move_analyses_game_id"), table_name="move_analyses")
    op.drop_table("move_analyses")
    op.drop_index(op.f("ix_games_user_id"), table_name="games")
    op.drop_table("games")
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_table("users")
