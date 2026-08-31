# Code Quality & Project Rules for Movie Crossword Game Backend

These rules apply to all AI code generations, refactoring, and implementations in this repository.



NEVER START WRITING CODE IMMEDIATELY, FIRST TELL THE APPROACH AND THEN THE REASONING BEHIND IT  AND THEN IF USER TELLS TO PROCEED, START WRITING THE CODE.

## 1. Code Cleanliness & Naming Conventions
- **Keep Code Minimal & Concise:** Avoid over-engineering, redundant abstractions, or unused functions. Write clean, readable Python code.
- **Naming Conventions:** Use camelCase for function and method names (e.g. `calculateBaseDifficulty`, `updateUserSkill`, `solveGrid`). Use PascalCase for classes (e.g. `CrosswordCSPSolver`).
- **Explicit Typing:** Use Python type hints (`int`, `float`, `List[str]`, `Optional[Dict]`) on all function signatures.

## 2. Clear Separation of Concerns
- **Single Responsibility Principle:** Keep each module strictly focused on a single responsibility:
  - `app/engine/difficulty.py` -> Pure difficulty & performance math algorithms.
  - `app/engine/csp_solver.py` -> Pure grid constraint satisfaction solver (Google OR-Tools).
  - `app/engine/recommender.py` -> Vector similarity & candidate movie selection.
  - `app/db/models/` -> SQLAlchemy ORM database definitions.
  - `app/api/v1/endpoints/` -> FastAPI HTTP route handlers.

## 3. Interactive & Incremental Development
- **Step-by-Step Workflow:** Explain changes line-by-line before writing large blocks of code. Take it slow and ensure complete understanding.
- **No Unrequested Features:** Implement only what is explicitly requested or agreed upon in the implementation plan.
- **Clean Documentation:** Include concise docstrings on public classes and functions explaining inputs, math formulas, and outputs.

## 4. High Performance & Tech Stack Rules
- **Fast Execution:** Use Google OR-Tools (C++) for grid constraints to guarantee sub-20ms layout generation.
- **Async Database Handling:** Use SQLAlchemy 2.0 async sessions with `asyncpg` for all PostgreSQL operations.
- **Vector Search Integrity:** Maintain 1024-dimensional normalized embeddings for `pgvector` similarity queries.
