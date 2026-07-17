"""Application entry point for Explainable Chess Coach."""

from src.config import ConfigurationError, load_settings


def main() -> None:
    """Validate the local configuration while the UI is being developed."""
    try:
        settings = load_settings()
    except ConfigurationError as error:
        raise SystemExit(f"Configuration error: {error}") from error

    print("Explainable Chess Coach")
    print(f"Stockfish: {settings.stockfish_path}")


if __name__ == "__main__":
    main()

