"""Construction and ownership of long-lived web application resources."""

from dataclasses import dataclass

import streamlit as st

from src.commentary import CommentaryService, create_commentary_service
from src.config import Settings, load_settings
from src.database import Database
from src.engine import StockfishEngine
from src.repositories.sqlalchemy_repository import SQLAlchemyGameHistoryRepository
from src.services.history_service import HistoryService
from src.services.practice_service import PracticeService
from src.services.progress_service import ProgressService


@dataclass(slots=True)
class WebResources:
    """Long-lived external resources shared across Streamlit reruns."""

    settings: Settings
    analysis_engine: StockfishEngine
    opponent_engine: StockfishEngine
    commentary: CommentaryService
    database: Database | None
    repository: SQLAlchemyGameHistoryRepository | None
    history: HistoryService | None
    practice: PracticeService | None
    progress: ProgressService | None


@st.cache_resource
def create_resources(cache_version: str) -> WebResources:
    """Create engines and optional persistence once per Streamlit process."""
    del cache_version
    settings = load_settings()
    analysis_engine = StockfishEngine.from_settings(settings)
    opponent_engine = StockfishEngine.from_settings(settings)
    analysis_engine.start()
    opponent_engine.start()
    commentary = create_commentary_service(
        provider=settings.ai_provider,
        api_key=settings.ai_api_key,
        model=settings.ai_model,
    )
    database = Database(settings.database_url) if settings.database_url else None
    repository = (
        SQLAlchemyGameHistoryRepository(database) if database is not None else None
    )
    return WebResources(
        settings=settings,
        analysis_engine=analysis_engine,
        opponent_engine=opponent_engine,
        commentary=commentary,
        database=database,
        repository=repository,
        history=(
            HistoryService(repository, username=settings.coach_username)
            if repository is not None
            else None
        ),
        practice=(
            PracticeService(
                repository,
                analysis_engine,
                commentary,
                username=settings.coach_username,
            )
            if repository is not None
            else None
        ),
        progress=(
            ProgressService(repository, username=settings.coach_username)
            if repository is not None
            else None
        ),
    )
