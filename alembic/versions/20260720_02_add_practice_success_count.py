"""Add successful review count to practice positions.

Revision ID: 20260720_02
Revises: 20260719_01
Create Date: 2026-07-20
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260720_02"
down_revision: str | None = "20260719_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "practice_positions",
        sa.Column(
            "successful_attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_check_constraint(
        "ck_valid_successful_attempts",
        "practice_positions",
        "successful_attempts >= 0 AND successful_attempts <= attempts",
    )
    op.alter_column(
        "practice_positions", "successful_attempts", server_default=None
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_valid_successful_attempts",
        "practice_positions",
        type_="check",
    )
    op.drop_column("practice_positions", "successful_attempts")
