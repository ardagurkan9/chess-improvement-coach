"""PostgreSQL migration and transaction integration tests."""

import os
from uuid import uuid4

import pytest
from sqlalchemy import inspect, select, text

from alembic import command
from alembic.config import Config
from src.database import Database
from src.db_models import UserRecord

pytestmark = pytest.mark.postgres


@pytest.fixture(scope="module")
def postgres_database() -> Database:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not configured")
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    database = Database(url)
    yield database
    database.close()


def test_alembic_creates_the_coaching_schema(postgres_database: Database) -> None:
    assert postgres_database.engine.dialect.name == "postgresql"
    tables = set(inspect(postgres_database.engine).get_table_names())
    assert {
        "alembic_version",
        "users",
        "games",
        "move_analyses",
        "mistakes",
        "practice_positions",
        "practice_attempts",
    } <= tables


def test_postgresql_commit_and_rollback(postgres_database: Database) -> None:
    committed_name = f"integration-{uuid4()}"
    with postgres_database.session() as session:
        session.add(UserRecord(username=committed_name))

    with postgres_database.session() as session:
        stored = session.scalar(
            select(UserRecord).where(UserRecord.username == committed_name)
        )
        assert stored is not None

    rolled_back_name = f"rollback-{uuid4()}"
    with pytest.raises(RuntimeError):
        with postgres_database.session() as session:
            session.add(UserRecord(username=rolled_back_name))
            session.flush()
            raise RuntimeError("force rollback")

    with postgres_database.engine.connect() as connection:
        count = connection.scalar(
            text("SELECT count(*) FROM users WHERE username = :username"),
            {"username": rolled_back_name},
        )
    assert count == 0
