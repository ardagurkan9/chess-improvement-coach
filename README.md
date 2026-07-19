# Chess Improvement Coach

Chess Improvement Coach is a terminal-based Python application that lets a user play against Stockfish while receiving evidence-grounded feedback on each move. The engineering focus is reliability: Stockfish evaluates positions, deterministic application code calculates move quality and conservative mistake themes, and Google Gemini—when configured—only turns verified evidence into readable coaching language. The codebase separates chess rules, engine integration, explanation generation, reporting, and persistence so each boundary can be tested independently.

## Current Project Status

The repository contains a working terminal MVP with legal chess play, Stockfish analysis, move classification, deterministic mistake detection, template/Gemini commentary, end-of-game reports, PGN generation, and optional game-history persistence. A PostgreSQL schema, Docker Compose service, SQLAlchemy repository, and initial Alembic migration are present. The browser UI and interactive practice workflow are not implemented.

| Area                  | Status      |
| --------------------- | ----------- |
| Chess game logic      | Implemented |
| Stockfish integration | Implemented |
| Move analysis         | Implemented |
| Mistake detection     | Implemented |
| AI explanations       | Implemented |
| Persistence           | Implemented |
| User interface        | In Progress |
| Testing and CI        | In Progress |

`User interface` is marked in progress because the terminal interface works, but the planned Streamlit interface does not exist yet. `Testing and CI` is in progress because the pytest suite is implemented and currently passes locally, while no GitHub Actions workflow is present.

## Core Concept and Responsibility Boundaries

The application deliberately separates evaluation, classification, and explanation:

```text
User move
   |
   v
python-chess validates the position and move
   |
   v
Stockfish evaluates the position before and after the move
   |
   v
Deterministic Python logic calculates centipawn loss, mate transitions,
move quality, and any evidence-supported mistake theme
   |
   v
Template commentary or Gemini explains only the supplied evidence
```

- **Stockfish performs chess evaluation.** It supplies the best move, White-perspective score or mate score, principal variation, and search depth.
- **Application code interprets the engine output.** It calculates player-perspective centipawn loss, handles mate transitions separately, classifies moves, and applies conservative theme detectors.
- **The language model does not evaluate the board.** Gemini receives a constrained payload containing verified moves, scores, classifications, mate flags, and optional theme evidence. It is not allowed to choose another best move or invent a tactical theme.
- **Persistence is isolated from chess logic.** The CLI calls an application service, which depends on a repository contract. SQLAlchemy and PostgreSQL details remain outside the game and analysis modules.

## Implemented Features

### Chess game and terminal play

- Standard starting position or validated custom FEN input through `ChessGame`.
- Legal move generation and UCI move input such as `e2e4` and `a7a8q`.
- Separate errors for invalid UCI notation, illegal moves, and moves attempted after game end.
- Check, checkmate, stalemate, claimable game-over state, and result reporting.
- Castling, en passant, and promotion through `python-chess` legality rules.
- Move history in `chess.Move` and UCI forms.
- Programmatic undo and reset behavior in the game layer.
- Choice of White or Black and Beginner, Intermediate, or Advanced explanation detail.
- Coordinate-labelled terminal board and retry behavior for invalid input.

Undo and reset are implemented in the game API, but the current terminal loop does not expose commands for them.

### Stockfish integration and move analysis

- Managed Stockfish UCI process with lazy startup, context-manager cleanup, and error translation.
- Analysis from a `chess.Board` or FEN string using depth and/or time limits.
- Normalized `EngineResult` containing best move, principal variation, depth, centipawn score, or mate score.
- Engine scores normalized to White's perspective.
- Before/after analysis without mutating the caller's board.
- Player-perspective, non-negative centipawn-loss calculation.
- Separate detection of missed forced mate and newly allowed forced mate; mate scores are not converted into artificial centipawn values.

### Move-quality classification

The default deterministic thresholds are:

| Centipawn loss | Classification |
| --------------- | -------------- |
| 0–15            | Best           |
| 16–40           | Excellent      |
| 41–80           | Good           |
| 81–150          | Inaccuracy     |
| 151–300         | Mistake        |
| 301+            | Blunder        |

Stockfish's first-choice move is classified as `Best` despite small analysis noise. Missed or allowed forced mates take priority and are classified as `Blunder`.

### Evidence-based mistake detection

The CLI runs theme detection only for `Inaccuracy`, `Mistake`, and `Blunder` moves. The detector currently supports:

- `HANGING_PIECE`: a verified legal capture at the start of Stockfish's continuation, with a conservative material-loss estimate.
- `MISSED_MATE`: a forced mate existed before the move and was lost afterward.
- `ALLOWED_MATE`: the move newly gives the opponent a forced mate.
- `MATERIAL_LOSS`: a legal prefix of Stockfish's continuation produces a measurable material loss.
- `KING_SAFETY`: selected concrete signals, including giving up castling rights with a king move or allowing an immediate checking reply after a nearby pawn move.
- `GENERAL_ERROR`: fallback when the evaluation loss is verified but no specific supported theme is proven.

Each detection includes evidence and a confidence value. These are deterministic heuristics, not a complete tactical motif system.

### Explanations

- Deterministic English templates for every move-quality category.
- Three explanation detail levels.
- Optional Google Gemini integration through `google-genai`.
- Gemini is called only for `Inaccuracy`, `Mistake`, and `Blunder`; stronger moves use templates.
- Structured, constrained Gemini payloads containing only verified analysis data.
- Response validation requires a non-empty, bounded response that mentions both the played move and Stockfish's best move.
- Automatic template fallback for missing configuration, client creation failures, timeouts/API failures, invalid responses, or empty AI output.

### Reports and PGN

Completed games produce a terminal report containing:

- Result and number of analyzed user moves.
- Average centipawn loss for moves with numeric evaluations.
- Move-quality distribution.
- Mistake-theme counts.
- Missed- and allowed-mate counts.
- Largest recorded error.
- Deterministic improvement suggestions.
- Standard PGN text with user/Stockfish headers and the game result.

PGN is printed to the terminal and can be persisted with the game record; no standalone `.pgn` file is written.

### Persistence

- Optional SQLAlchemy 2 engine and transactional session management.
- Commit on success, rollback on failure, connection health check, and pooled connection disposal.
- ORM records for `users`, `games`, `move_analyses`, `mistakes`, and `practice_positions`.
- Database constraints for unique game ply numbers, non-negative centipawn loss and attempt counts, and confidence values between 0 and 1.
- Repository contract and SQLAlchemy implementation.
- Completed-game persistence including PGN, FEN values, engine results, move quality, commentary source/text, mistake evidence, and generated practice-position records.
- Recurring mistake counts grouped by theme for the configured user.
- Initial Alembic migration: `20260719_01_initial_coaching_schema.py`.
- PostgreSQL 17 development service through Docker Compose.
- Graceful CLI behavior when persistence fails: gameplay completes and a save error is reported without crashing the chess session.

## In Progress

- End-to-end validation of the PostgreSQL/Docker setup across development environments.
- Turning stored `practice_positions` into an interactive review flow. Records are created, but the application cannot yet list, solve, score, or reschedule them.
- A richer user interface. The terminal UI is implemented; no Streamlit application or page modules exist.
- Continuous integration. Local pytest coverage is broad, but no `.github/workflows` configuration exists.

## Planned Features

- Streamlit-based play, analysis, report, practice, and progress views.
- Practice attempts, solved/mastered state transitions, and `next_review_at` scheduling.
- Spaced-repetition logic for recurring mistakes.
- Progress summaries over stored games and themes.
- Configurable Stockfish strength from the user interface.
- MultiPV comparison of multiple candidate moves.
- PGN file export/download rather than terminal output only.
- GitHub Actions for automated test execution.

## Current Architecture

```text
app.py
  |
  +-- configuration ------------------------------ src/config.py
  +-- Stockfish lifecycle ------------------------ src/engine.py
  +-- terminal orchestration --------------------- src/cli.py
        |
        +-- legal game state --------------------- src/game.py
        +-- before/after analysis ---------------- src/analysis.py
        +-- move classification ------------------ src/move_classifier.py
        +-- mistake-theme evidence --------------- src/mistake_detector.py
        +-- template/Gemini explanation ---------- src/commentary.py
        +-- report and PGN ------------------------ src/report.py
        +-- history service ---------------------- src/services/history_service.py
              |
              +-- repository contract ------------ src/repositories/interfaces.py
              +-- SQLAlchemy repository ---------- src/repositories/sqlalchemy_repository.py
                    |
                    +-- sessions ----------------- src/database.py
                    +-- ORM schema ---------------- src/db_models.py
                    +-- PostgreSQL / Alembic
```

Shared immutable domain records and enums live in `src/models.py`. SQLAlchemy records are kept separately in `src/db_models.py`.

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
├── .gitignore
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   ├── README.md
│   └── versions/
│       └── 20260719_01_initial_coaching_schema.py
├── src/
│   ├── __init__.py
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
│   │   ├── __init__.py
│   │   ├── interfaces.py
│   │   └── sqlalchemy_repository.py
│   └── services/
│       ├── __init__.py
│       └── history_service.py
└── tests/
    ├── __init__.py
    ├── test_analysis.py
    ├── test_cli.py
    ├── test_commentary.py
    ├── test_config.py
    ├── test_database.py
    ├── test_db_models.py
    ├── test_engine.py
    ├── test_game.py
    ├── test_history_repository.py
    ├── test_mistake_detector.py
    ├── test_move_classifier.py
    ├── test_project.py
    └── test_report.py
```

## Technology Stack

- Python 3.11+
- `python-chess` for board state, move legality, PGN, and UCI engine integration
- Stockfish executable as the chess evaluator and opponent
- `google-genai` for optional Gemini explanations
- `python-dotenv` for local environment configuration
- SQLAlchemy 2 for ORM and transaction management
- Alembic for schema migrations
- PostgreSQL 17 for persistent development storage
- `psycopg` 3 with binary dependencies for PostgreSQL connectivity
- Docker Compose for the local PostgreSQL service
- pytest and pytest-cov for automated tests
- Streamlit is installed as a dependency for the planned UI, but is not used by current application code

## Requirements

- Python 3.11 or newer. The code uses `enum.StrEnum`, introduced in Python 3.11.
- A Stockfish executable compatible with the host operating system.
- Optional: a Google Gemini API key for AI-assisted explanations.
- Optional: Docker Desktop or another reachable PostgreSQL instance for persistence.

## Installation

Clone the repository and create a virtual environment:

```bash
git clone https://github.com/ardagurkan9/chess-improvement-coach.git
cd chess-improvement-coach
python -m venv .venv
```

Activate it:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```cmd
:: Windows Command Prompt
.venv\Scripts\activate.bat
```

```bash
# macOS/Linux
source .venv/bin/activate
```

Install runtime dependencies:

```bash
python -m pip install -r requirements.txt
```

For development and tests:

```bash
python -m pip install -r requirements-dev.txt
```

Copy `.env.example` to `.env`, then set at least `STOCKFISH_PATH`. The real `.env` is ignored by Git.

## Environment Variables

```env
STOCKFISH_PATH=/absolute/path/to/stockfish

AI_PROVIDER=gemini
AI_API_KEY=
AI_MODEL=gemini-3.1-flash-lite

DATABASE_URL=postgresql+psycopg://chess_coach:chess_coach@localhost:5432/chess_coach
COACH_USERNAME=local-player
```

| Variable         | Required | Purpose |
| ---------------- | -------- | ------- |
| `STOCKFISH_PATH` | Yes      | Absolute path to the Stockfish executable; validated at startup. |
| `AI_PROVIDER`    | No       | Must be `gemini` to enable the current AI provider. |
| `AI_API_KEY`     | No       | Gemini API key. Missing values select template commentary. |
| `AI_MODEL`       | No       | Gemini model identifier passed to `google-genai`. |
| `DATABASE_URL`   | No       | SQLAlchemy connection URL. Leave empty to disable persistence. |
| `COACH_USERNAME` | No       | Logical username for stored history; defaults to `local-player`. |

The application loads `.env` through `python-dotenv`. Alembic does not load `.env` itself: it uses the shell's `DATABASE_URL` when set, otherwise the development URL in `alembic.ini`.

## Database Setup

With Docker Desktop running, start PostgreSQL:

```bash
docker compose up -d
```

Apply the schema migration from the activated virtual environment:

```bash
python -m alembic upgrade head
```

Check the container:

```bash
docker compose ps
```

The Compose credentials are development defaults and should not be reused for a deployed environment. To run without persistence, set `DATABASE_URL=` in `.env`; the chess, analysis, commentary, and reporting flows remain available.

## Running the Application

From an activated virtual environment:

```bash
python app.py
```

On Windows, `run.bat` uses the repository's `.venv` directly, so PowerShell can run:

```powershell
.\run
```

Command Prompt can run:

```cmd
run
```

Moves must use UCI notation. Examples: `e2e4`, `g1f3`, or `a7a8q`. Enter `quit`, `exit`, or `q` on the user's turn to stop without an end-of-game report or persistence write.

## Running Tests

```bash
python -m pytest
```

Optional local coverage output:

```bash
python -m pytest --cov=src
```

The current repository contains 102 passing pytest cases. There is no CI workflow, coverage threshold, or published coverage percentage.

## Example Usage

The exact Stockfish move and evaluation depend on the engine version and search result, but the terminal flow is:

```text
Chess Improvement Coach
Enter moves in UCI notation, for example: e2e4
Choose your color [w/b]: w
Choose explanation level [1=Beginner, 2=Intermediate, 3=Advanced]: 2

  a b c d e f g h
8 r n b q k b n r 8
7 p p p p p p p p 7
...
1 R N B Q K B N R 1
  a b c d e f g h
Turn: White
Your move (UCI, or 'quit'): e2e4
Analysis: Best - The move matches Stockfish's first choice.
Stockfish's choice: e2e4
Evaluation: +0.47 -> +0.42
Coach [Template]: Nice move! ...
Stockfish plays: e7e6
```

For significant errors, the output can also include a verified theme and `Coach [Gemini]` when Gemini is configured. Otherwise it shows `Coach [Template]`.

## Design and Reliability Decisions

- `ChessGame.board` returns a defensive copy so callers cannot silently mutate internal state.
- Illegal moves are rejected before Stockfish is called.
- Engine process ownership is explicit and cleanup is idempotent.
- Normal numeric scores and mate scores remain separate throughout analysis and persistence.
- Centipawn loss is calculated from the moving player's perspective and clamped at zero to tolerate search noise.
- Classification thresholds are deterministic and validated.
- Specific mistake themes require concrete board/PV evidence; unsupported cases fall back to `GENERAL_ERROR`.
- Gemini receives a restricted payload and never becomes the source of the best move, evaluation, or theme.
- Template commentary is always available as a deterministic fallback.
- Database writes are transactional and isolated behind a repository protocol.
- A database failure does not invalidate an otherwise completed game.
- Engine, commentary, and repository boundaries are replaceable with test doubles, allowing tests to run without a live Stockfish process, Gemini API, or PostgreSQL server.

## Known Limitations

- The only current user interface is the terminal; no Streamlit files or browser interface exist.
- Moves are entered in UCI notation rather than by clicking a board or using SAN.
- The terminal does not expose the implemented undo/reset methods.
- Stockfish depth defaults to 12 in the terminal and is not user-configurable there; engine Elo/skill options and MultiPV are not configured.
- Mistake detection covers six conservative categories and does not recognize the full range of tactical or positional motifs.
- The application creates practice-position records but provides no review, attempt, solved-state, or scheduling workflow.
- PGN is printed and optionally stored in PostgreSQL, not exported as a file.
- Only completed games are reported and persisted; quitting early returns without a report.
- Template evaluation text uses normalized White-perspective engine scores. For a Black user, wording that says “your perspective” can be misleading even though centipawn-loss calculation itself correctly reverses perspective.
- Gemini response validation checks structure, length, and required move references, but cannot prove that every generated sentence is semantically correct.
- `COACH_USERNAME` is a configuration label, not an authentication or account system.
- PostgreSQL integration requires the migration to be applied; repository tests use SQLite and no automated live-PostgreSQL test is present.
- No GitHub Actions workflow, deployment configuration, screenshots, hosted demo, or license file is currently included.

## Roadmap

1. Validate Docker Compose and Alembic against a live PostgreSQL instance in automated integration tests.
2. Implement practice-position retrieval, move submission, attempt tracking, status updates, and review scheduling.
3. Add personal progress queries and summaries over persisted games and themes.
4. Build the Streamlit interface on top of the existing services and repository boundaries.
5. Add configurable Stockfish strength and MultiPV candidate comparison.
6. Add PGN file export and practice/report downloads.
7. Add GitHub Actions for tests and migration checks.
