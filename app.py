"""Application entry point for Chess Improvement Coach."""

from src.config import ConfigurationError, load_settings
from src.cli import TerminalGame
from src.commentary import create_commentary_service
from src.database import Database
from src.engine import EngineError, StockfishEngine
from src.repositories.sqlalchemy_repository import SQLAlchemyGameHistoryRepository
from src.services.history_service import HistoryService


def main() -> None:
    """Start the terminal-based chess coach."""
    try:
        settings = load_settings()
        commentary = create_commentary_service(
            provider=settings.ai_provider,
            api_key=settings.ai_api_key,
            model=settings.ai_model,
        )
        database = Database(settings.database_url) if settings.database_url else None
        history_service = (
            HistoryService(
                SQLAlchemyGameHistoryRepository(database),
                username=settings.coach_username,
            )
            if database is not None
            else None
        )
        try:
            with StockfishEngine.from_settings(settings) as engine:
                TerminalGame(
                    engine,
                    commentary=commentary,
                    history_service=history_service,
                ).run()
        finally:
            if database is not None:
                database.close()
    except ConfigurationError as error:
        raise SystemExit(f"Configuration error: {error}") from error
    except EngineError as error:
        raise SystemExit(f"Stockfish error: {error}") from error
    except KeyboardInterrupt:
        print("\nGame stopped.")


if __name__ == "__main__":
    main()
