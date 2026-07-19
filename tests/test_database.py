from sqlalchemy import text

from src.database import Database


def test_database_connection_and_commit() -> None:
    database = Database("sqlite+pysqlite:///:memory:")

    database.check_connection()
    with database.session() as session:
        session.execute(text("CREATE TABLE samples (value INTEGER NOT NULL)"))
        session.execute(text("INSERT INTO samples (value) VALUES (42)"))

    with database.session() as session:
        value = session.scalar(text("SELECT value FROM samples"))

    assert value == 42
    database.close()


def test_database_session_rolls_back_on_failure() -> None:
    database = Database("sqlite+pysqlite:///:memory:")
    with database.session() as session:
        session.execute(text("CREATE TABLE samples (value INTEGER NOT NULL)"))

    try:
        with database.session() as session:
            session.execute(text("INSERT INTO samples (value) VALUES (7)"))
            raise RuntimeError("stop transaction")
    except RuntimeError:
        pass

    with database.session() as session:
        count = session.scalar(text("SELECT COUNT(*) FROM samples"))

    assert count == 0
    database.close()
