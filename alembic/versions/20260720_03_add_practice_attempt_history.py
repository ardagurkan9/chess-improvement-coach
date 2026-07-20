"""Add immutable practice attempt history.

Revision ID: 20260720_03
Revises: 20260720_02
Create Date: 2026-07-20
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260720_03"
down_revision: str | None = "20260720_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "practice_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("practice_position_id", sa.Integer(), nullable=False),
        sa.Column("attempted_move", sa.String(length=5), nullable=False),
        sa.Column("correct", sa.Boolean(), nullable=False),
        sa.Column("quality", sa.String(length=10), nullable=True),
        sa.Column("detected_theme", sa.String(length=13), nullable=True),
        sa.Column("commentary", sa.Text(), nullable=True),
        sa.Column("commentary_source", sa.String(length=32), nullable=True),
        sa.Column("scheduled_review_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "attempted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["practice_position_id"],
            ["practice_positions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_practice_attempts_practice_position_id"),
        "practice_attempts",
        ["practice_position_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_practice_attempts_correct"),
        "practice_attempts",
        ["correct"],
        unique=False,
    )
    op.create_index(
        op.f("ix_practice_attempts_attempted_at"),
        "practice_attempts",
        ["attempted_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_practice_attempts_attempted_at"),
        table_name="practice_attempts",
    )
    op.drop_index(
        op.f("ix_practice_attempts_correct"),
        table_name="practice_attempts",
    )
    op.drop_index(
        op.f("ix_practice_attempts_practice_position_id"),
        table_name="practice_attempts",
    )
    op.drop_table("practice_attempts")
