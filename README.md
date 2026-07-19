# Chess Improvement Coach

Chess Improvement Coach is a working terminal MVP for playing against Stockfish and receiving evidence-grounded feedback after each move. Stockfish evaluates the chess position; deterministic Python code calculates centipawn loss, move quality, mate transitions, and conservative mistake themes; Google Gemini is optional and may only explain evidence supplied by the engine and application. The design keeps chess rules, engine integration, commentary, reporting, and persistence independently testable.

## Table of Contents

- [Current Status](#current-status)
- [How It Works](#how-it-works)
- [Implemented Features](#implemented-features)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Technology Stack](#technology-stack)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [Testing](#testing)
- [Known Limitations](#known-limitations)
- [Roadmap](#roadmap)

## Current Status

| Area                       | Status      |
| -------------------------- | ----------- |
| Terminal interface         | Implemented |
| Browser interface          | Planned     |
| Chess game logic           | Implemented |
| Stockfish integration      | Implemented |
| Move analysis              | Implemented |
| Mistake detection          | Implemented |
| AI-assisted explanations   | Implemented |
| Persistence layer          | Implemented |
| Live PostgreSQL validation | In Progress |
| Practice-position storage  | Implemented |
| Interactive practice flow  | Planned     |
| Automated tests            | Implemented |
| GitHub Actions CI          | Planned     |

The current application can complete and analyze terminal games, generate reports and PGN, and optionally persist coaching history. PostgreSQL models, Docker Compose configuration, repository code, and an initial Alembic migration exist; automated repository tests currently use SQLite rather than a live PostgreSQL service.

## How It Works

```text
User move -> legal-move validation -> before/after Stockfish analysis
          -> deterministic classification and theme detection
          -> template/Gemini explanation -> report and optional persistence
```

The responsibility boundaries are deliberate:

- **Stockfish evaluates chess.** It supplies the best move, White-perspective centipawn or mate score, principal variation, and search depth.
- **Deterministic application code interprets the result.** It calculates player-perspective centipawn loss, classifies the move, and detects only themes supported by board and principal-variation evidence.
- **Gemini explains; it does not evaluate.** It receives a constrained payload and cannot replace Stockfish's best move or select an unsupported mistake theme.
- **Persistence is separate from gameplay.** The CLI uses a history service and repository contract; SQLAlchemy details do not enter the game or analysis modules.

## Implemented Features

### Chess game logic and terminal play

- Standard or validated custom-FEN positions, legal UCI input, and move history.
- Separate handling for invalid notation, illegal moves, and moves after game end.
- Check, checkmate, stalemate, castling, en passant, promotion, and results through `python-chess`.
- Legal-move access, defensive board copies, undo, and reset APIs.
- Choice of White or Black and three explanation detail levels.
- Coordinate-labelled terminal board with retry behavior for invalid input.

Undo and reset exist in the game layer but are not exposed as terminal commands.

### Stockfish analysis

- Managed UCI process with lazy startup, error translation, and safe cleanup.
- Board/FEN analysis using depth and/or time limits.
- Normalized best move, principal variation, depth, centipawn score, or mate score.
- Non-mutating before/after analysis and non-negative player-perspective centipawn loss.
- Missed and newly allowed forced mates kept separate from numeric scores.

### Move classification

| Centipawn loss | Classification |
| --------------- | -------------- |
| 0–15            | Best           |
| 16–40           | Excellent      |
| 41–80           | Good           |
| 81–150          | Inaccuracy     |
| 151–300         | Mistake        |
| 301+            | Blunder        |

Stockfish's first-choice move remains `Best` despite small search noise. Missed or allowed forced mates take priority and are classified as `Blunder`.

### Evidence-based mistake themes

Theme detection runs for `Inaccuracy`, `Mistake`, and `Blunder` moves:

- `HANGING_PIECE`: Stockfish's verified continuation begins with a legal capture producing a conservative material loss.
- `MISSED_MATE`: a forced mate existed before the move and disappeared afterward.
- `ALLOWED_MATE`: the move newly gives the opponent a forced mate.
- `MATERIAL_LOSS`: a legal prefix of the principal variation produces measurable material loss.
- `KING_SAFETY`: selected concrete signals such as surrendering castling rights or allowing an immediate check after a nearby pawn move.
- `GENERAL_ERROR`: fallback when the evaluation loss is known but no specific supported theme is proven.

Each result includes evidence and a confidence value. This is intentionally a limited heuristic system, not a complete tactical motif recognizer.

### Coaching explanations

- Deterministic English templates for all move qualities and user levels.
- Optional Gemini commentary for `Inaccuracy`, `Mistake`, and `Blunder` only.
- Structured prompts limited to verified moves, scores, classifications, mate flags, and theme evidence.
- Validation for empty, oversized, or move-omitting responses.
- Automatic template fallback when Gemini is missing, unavailable, or returns an invalid response.

### Reports and persistence

Completed games produce result and centipawn statistics, quality/theme counts, mate errors, the largest error, improvement suggestions, and standard PGN text.

Optional persistence provides:

- Transactional SQLAlchemy sessions and ORM records for users, games, analyses, mistakes, and practice positions.
- PGN, FEN, engine scores, commentary, evidence, confidence, and generated practice records.
- Recurring theme counts for the configured user.
- PostgreSQL 17 through Docker Compose and initial Alembic revision `20260719_01`.
- Graceful save failure without invalidating a completed game.

## Architecture

```text
app.py
  +-- config.py
  +-- engine.py ---------------- Stockfish process and normalized results
  +-- cli.py ------------------- terminal orchestration
        +-- game.py ------------ legal state and move history
        +-- analysis.py -------- before/after comparison
        +-- move_classifier.py - deterministic quality labels
        +-- mistake_detector.py  evidence-based themes
        +-- commentary.py ------ templates and constrained Gemini calls
        +-- report.py ---------- aggregate report and PGN
        +-- HistoryService
              +-- repository protocol
              +-- SQLAlchemy repository
                    +-- database.py
                    +-- db_models.py
                    +-- PostgreSQL / Alembic
```

Immutable domain records live in `src/models.py`; SQLAlchemy records remain separate in `src/db_models.py`. Engine, commentary, and repository protocols allow tests to replace external systems with deterministic doubles.

## Project Structure

```text
chess-improvement-coach/
├── app.py
├── run.bat
├── requirements.txt
├── requirements-dev.txt
├── docker-compose.yml
├── alembic.ini
├── .env.example
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 20260719_01_initial_coaching_schema.py
├── src/
│   ├── analysis.py
│   ├── cli.py
│   ├── commentary.py
│   ├── config.py
│   ├── database.py
│   ├── db_models.py
│   ├── engine.py
│   ├── game.py
│   ├── mistake_detector.py
│   ├── models.py
│   ├── move_classifier.py
│   ├── report.py
│   ├── repositories/
│   │   ├── interfaces.py
│   │   └── sqlalchemy_repository.py
│   └── services/
│       └── history_service.py
└── tests/                   # pytest modules mirroring the application layers
```

## Technology Stack

- Python 3.11+
- `python-chess` for rules, board state, PGN, and UCI integration
- Stockfish as evaluator and opponent
- `google-genai` for optional Gemini explanations
- `python-dotenv` for local configuration
- SQLAlchemy 2, Alembic, PostgreSQL 17, and `psycopg` 3 for persistence
- Docker Compose for the local PostgreSQL service
- pytest and pytest-cov for tests

## Installation

Requirements:

- Python 3.11 or newer (`enum.StrEnum` is used).
- A Stockfish executable for the host operating system.
- Optional Gemini API key.
- Optional Docker Desktop or another PostgreSQL instance for persistence.

```bash
git clone https://github.com/ardagurkan9/chess-improvement-coach.git
cd chess-improvement-coach
python -m venv .venv
```

Activate it with `.\.venv\Scripts\Activate.ps1` (PowerShell),
`.venv\Scripts\activate.bat` (Command Prompt), or
`source .venv/bin/activate` (macOS/Linux).

Install runtime dependencies:

```bash
python -m pip install -r requirements.txt
```

For development and testing:

```bash
python -m pip install -r requirements-dev.txt
```

Copy `.env.example` to `.env` and configure at least `STOCKFISH_PATH`. `.env` is ignored by Git.

## Configuration

| Variable         | Required | Purpose |
| ---------------- | -------- | ------- |
| `STOCKFISH_PATH` | Yes      | Absolute path validated at startup. |
| `AI_PROVIDER`    | No       | Must be `gemini` to enable the current AI provider. |
| `AI_API_KEY`     | No       | Missing values select template commentary. |
| `AI_MODEL`       | No       | Gemini model identifier passed to `google-genai`. |
| `DATABASE_URL`   | No       | SQLAlchemy URL; leave empty to disable persistence. |
| `COACH_USERNAME` | No       | History label; defaults to `local-player`. |

The application loads `.env` with `python-dotenv`. Alembic reads a shell `DATABASE_URL` when present; otherwise it uses the development URL in `alembic.ini`.

### Optional database setup

With Docker Desktop running:

```bash
docker compose up -d
python -m alembic upgrade head
docker compose ps
```

The Compose credentials are development defaults. Set `DATABASE_URL=` to run without persistence.

## Running the Application

From an activated environment:

```bash
python app.py
```

Windows launchers:

```powershell
# PowerShell
.\run
```

```cmd
:: Command Prompt
run
```

Moves use UCI notation: `e2e4`, `g1f3`, or `a7a8q`. Enter `quit`, `exit`, or `q` on the user's turn to stop without a report or persistence write. Each accepted move shows its classification, Stockfish choice, evaluation, suggested line, optional verified theme, and template/Gemini commentary. Engine moves and scores vary by Stockfish version and search result.

## Testing

```bash
python -m pytest
```

Optional coverage report:

```bash
python -m pytest --cov=src
```

The local suite covers game rules, engine process behavior, score normalization, move analysis, classification thresholds, mistake detection, commentary fallback, terminal flow, reporting, configuration, transactions, ORM relationships, and repository aggregation. No CI workflow, coverage threshold, or published coverage percentage exists.

## Design and Reliability Decisions

- Board access uses defensive copies, and illegal moves are rejected before engine analysis.
- Engine lifecycle and cleanup are explicit and idempotent.
- Mate scores remain separate from centipawn values.
- Specific mistake themes require deterministic evidence; uncertain cases use `GENERAL_ERROR`.
- Gemini is never the source of evaluation, best move, or theme, and templates remain available offline.
- Database writes are transactional and isolated behind service/repository boundaries.
- Gameplay can finish when AI or persistence services are unavailable.

## Known Limitations

- The interface is terminal-only and accepts UCI rather than SAN or board clicks.
- Undo/reset are not exposed in the terminal.
- Practice records are created but cannot yet be listed, solved, scored, or rescheduled.
- Mistake detection covers six conservative categories, not all tactical or positional motifs.
- Stockfish depth is fixed at 12 in the terminal; strength controls and MultiPV are absent.
- PGN is printed and optionally stored, but no `.pgn` file export exists.
- Only completed games are reported and persisted.
- Template score wording uses White-normalized values and can be misleading for Black even though centipawn-loss calculation correctly reverses perspective.
- Gemini response checks cannot prove that every generated sentence is semantically correct.
- Repository tests use SQLite; no automated live-PostgreSQL integration test exists.
- There is no authentication, GitHub Actions workflow, hosted demo, or license file.

## Roadmap

1. Validate Docker Compose and Alembic in automated live-PostgreSQL integration tests.
2. Implement practice retrieval, move submission, attempt tracking, status transitions, and review scheduling.
3. Add progress summaries over persisted games and recurring themes.
4. Build a Streamlit browser interface on the existing service boundaries.
5. Add configurable Stockfish strength and MultiPV comparison.
6. Add PGN file export and report/practice downloads.
7. Add GitHub Actions for tests and migration checks.
8. Add a short terminal demo GIF once a stable presentation flow exists.
