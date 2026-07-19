"""SQLAlchemy engine, session factory, and transaction management."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker


class Database:
    """Own the SQLAlchemy engine and provide transactional sessions."""

    def __init__(self, url: str, *, echo: bool = False) -> None:
        if not url.strip():
            raise ValueError("Database URL cannot be empty.")

        self.engine: Engine = create_engine(
            url.strip(),
            echo=echo,
            pool_pre_ping=True,
        )
        self.session_factory = sessionmaker(
            bind=self.engine,
            class_=Session,
            expire_on_commit=False,
        )

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Commit successful work and roll back the transaction on failure."""
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def check_connection(self) -> None:
        """Execute a minimal query, raising when the database is unavailable."""
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    def close(self) -> None:
        """Release pooled database connections."""
        self.engine.dispose()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
