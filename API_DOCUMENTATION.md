# Movie Crossword Game — Complete API Specification & UI Integration Guide

This document defines all backend REST API endpoints, exact request schemas, response models, error responses, and how each field maps to the Frontend UI components.

---

## Base URL & General Info
- **Base URL**: `http://localhost:8000/api/v1` (or your configured backend host)
- **Content-Type**: `application/json`
- **Interactive OpenAPI Docs**: `http://localhost:8000/docs`
- **ReDoc API Docs**: `http://localhost:8000/redoc`

---

## Quick Reference Table

| Category | Method | Endpoint | Description | UI Component / Action |
| :--- | :--- | :--- | :--- | :--- |
| **System** | `GET` | `/` | Health check & service status | Connection status / App startup |
| **Users** | `POST` | `/api/v1/users/` | Register new user profile | Sign-up form |
| **Users** | `POST` | `/api/v1/users/login` | Login existing user or auto-register | Player login / guest entry |
| **Users** | `GET` | `/api/v1/users/{user_id}` | Fetch user profile by UUID | User Stats Header / Profile Modal |
| **Users** | `GET` | `/api/v1/users/by-username/{username}` | Fetch user profile by username | Player lookup |
| **Gameplay** | `POST` | `/api/v1/gameplay/generate-level` | Generate personalized 10x10 puzzle level | "Play Next Level" button |
| **Gameplay** | `POST` | `/api/v1/gameplay/request-hint` | Get progressive hint tier for slot | "Lightbulb / Hint" button |
| **Gameplay** | `POST` | `/api/v1/gameplay/submit-telemetry` | Submit completion metrics & update skill rating | Puzzle completion modal |
| **Gameplay** | `GET` | `/api/v1/gameplay/history/{user_id}` | Paginated level play history | History / Statistics Tab |

---

## 1. System & Health Check

### `GET /`
Checks service health and returns system version.

#### Sample Request
```http
GET / HTTP/1.1
Host: localhost:8000
```

#### Sample Response (`200 OK`)
```json
{
  "status": "online",
  "service": "Movie Crossword Game Backend",
  "version": "1.0.0",
  "docs_url": "/docs",
  "test_ui": "/test"
}
```

---

## 2. User Management Endpoints (`/api/v1/users`)

### `POST /api/v1/users/`
Registers a new player profile with initial skill rating (`0.200`) and default premium hint tokens (`5`).

#### Sample Request
```json
{
  "username": "cinephile_99"
}
```

#### Sample Response (`201 Created`)
```json
{
  "user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "username": "cinephile_99",
  "current_skill_level": 0.200,
  "total_games_played": 0,
  "levels_generated": 0,
  "premium_hints_balance": 5
}
```

#### Error Response (`400 Bad Request`)
```json
{
  "detail": "Username 'cinephile_99' is already registered."
}
```

---

### `POST /api/v1/users/login`
Logs in an existing user by username. If the user doesn't exist yet, it automatically creates a new profile.

#### Sample Request
```json
{
  "username": "cinephile_99"
}
```

#### Sample Response (`200 OK`)
```json
{
  "user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "username": "cinephile_99",
  "current_skill_level": 0.245,
  "total_games_played": 4,
  "levels_generated": 4,
  "premium_hints_balance": 4
}
```

---

### `GET /api/v1/users/{user_id}`
Fetches user details by user UUID. Used by the UI header to display hint balance and user profile.

#### Sample Request
```http
GET /api/v1/users/a1b2c3d4-e5f6-7890-abcd-ef1234567890 HTTP/1.1
```

#### Sample Response (`200 OK`)
```json
{
  "user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "username": "cinephile_99",
  "current_skill_level": 0.245,
  "total_games_played": 4,
  "levels_generated": 4,
  "premium_hints_balance": 4
}
```

---

### `GET /api/v1/users/by-username/{username}`
Fetches user details by username string.

#### Sample Response (`200 OK`)
```json
{
  "user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "username": "cinephile_99",
  "current_skill_level": 0.245,
  "total_games_played": 4,
  "levels_generated": 4,
  "premium_hints_balance": 4
}
```

---

## 3. Gameplay Endpoints (`/api/v1/gameplay`)

### `POST /api/v1/gameplay/generate-level`
Generates a personalized, 10x10 crossword level containing 6 movie title clues. Applies skill-based clue adaptation and excludes previously played IMDb IDs.

> **Rule**: Enforces sequential level progression. If a user already has an active, uncompleted level, a `400 Bad Request` is returned until that level is submitted.

#### Sample Request
```json
{
  "user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "requested_difficulty": 0.35,
  "exclude_imdb_ids": ["tt0114709", "tt0120338"]
}
```

#### Sample Response (`200 OK`)
```json
{
  "level_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "level_number": 1,
  "target_difficulty": 0.35,
  "free_hints_remaining": 2,
  "premium_hints_remaining": 5,
  "grid": [
    ["T", "H", "E", "B", "A", "T", "M", "A", "N", ""],
    ["", "", "", "", "", "", "", "", "", ""],
    ["", "", "", "", "", "", "", "", "", ""],
    ["", "", "", "", "", "", "", "", "", ""],
    ["", "", "", "", "", "", "", "", "", ""],
    ["", "", "", "", "", "", "", "", "", ""],
    ["", "", "", "", "", "", "", "", "", ""],
    ["", "", "", "", "", "", "", "", "", ""],
    ["", "", "", "", "", "", "", "", "", ""],
    ["", "", "", "", "", "", "", "", "", ""]
  ],
  "clues": [
    {
      "slot_id": "S1",
      "number": 1,
      "direction": "ACROSS",
      "row": 0,
      "col": 0,
      "length": 9,
      "word_lengths": [3, 6],
      "word_pattern": "(3,6)",
      "imdb_id": "tt1877830",
      "display_title": "The Batman",
      "difficulty": 0.385,
      "hint": "Gotham's vigilante hero investigates corrupt elites.",
      "hint_tier": 1,
      "hint_type": "PLOT",
      "hints_available": 3,
      "post_solve_trivia": "I am Vengeance."
    },
    {
      "slot_id": "S2",
      "number": 2,
      "direction": "DOWN",
      "row": 0,
      "col": 0,
      "length": 7,
      "word_lengths": [7],
      "word_pattern": "(7)",
      "imdb_id": "tt0111161",
      "display_title": "Titanic",
      "difficulty": 0.250,
      "hint": "Epic romance and disaster movie set on a tragic maiden voyage.",
      "hint_tier": 1,
      "hint_type": "PLOT",
      "hints_available": 3,
      "post_solve_trivia": "I'm the king of the world!"
    }
  ]
}
```

#### UI Mapping (`CrosswordGrid.jsx` & `ClueList.jsx`)
- `grid`: Rendered as the 10x10 interactive crossword board (`CrosswordGrid.jsx`).
- `clues[i].number`: Rendered in slot number badge on top-left of starting grid cell.
- `clues[i].word_lengths`: Rendered next to clue title, e.g. `1. [3,6] Gotham's vigilante hero...` (`ClueList.jsx` via `formatWordPattern`).
- `clues[i].word_pattern`: Formatted pattern string `(3,6)`.
- `free_hints_remaining` & `premium_hints_remaining`: Rendered in the Hint Header Badges.

#### Error Response (`400 Bad Request` - Progression Lock)
```json
{
  "detail": "You must complete level 1 before generating a new level."
}
```

---

### `POST /api/v1/gameplay/request-hint`
Requests the next progressive hint tier for a specific clue slot. Each clue has multiple progressive hint tiers (Plot -> Character -> Trivia -> Dialogue/Props).

> **Hint Economy**: Each level includes **2 Free Hints**. Once the level's free hint budget is exhausted, subsequent hints charge **1 Premium Hint Token** from the user's balance.

#### Sample Request
```json
{
  "user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "level_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "slot_id": "S1"
}
```

#### Sample Response (`200 OK`)
```json
{
  "level_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "slot_id": "S1",
  "hint_text": "Stars Robert Pattinson as Bruce Wayne.",
  "tier": 2,
  "type": "CHARACTER",
  "cost_charged": 0,
  "free_hints_remaining": 1,
  "premium_hints_remaining": 5,
  "hints_left_for_slot": 2
}
```

#### UI Mapping (`ClueList.jsx` & Active Clue Banner)
- `hint_text`: Updates the active hint display text for the selected clue.
- `cost_charged`: Shows a notification (`+0 Free Hint Used` or `1 Premium Token Used`).
- `free_hints_remaining` / `premium_hints_remaining`: Updates header badge counter.

#### Error Response (`402 Payment Required` - Insufficient Balance)
```json
{
  "detail": "Insufficient premium hint balance."
}
```

---

### `POST /api/v1/gameplay/submit-telemetry`
Submits game session telemetry upon puzzle completion or exit. Updates the player's skill rating (Elo dynamic adaptation) and updates their 1024-dimensional movie taste vector. Unlocks level generation for subsequent levels.

#### Sample Request
```json
{
  "user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "session_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "level_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "level_number": 1,
  "imdb_ids": ["tt1877830", "tt0111161"],
  "time_taken_seconds": 94,
  "free_hints_used": 1,
  "premium_hints_used": 0,
  "cell_error_count": 1,
  "is_completed": true,
  "hint_usage": [
    {
      "imdb_id": "tt1877830",
      "hints_revealed": 1,
      "deepest_tier": 2
    }
  ]
}
```

#### Sample Response (`200 OK`)
```json
{
  "user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "session_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "previous_skill_level": 0.200,
  "new_skill_level": 0.235,
  "skill_delta": 0.035
}
```

#### UI Mapping (Level Complete Modal)
- `new_skill_level`: Displayed as the player's updated skill rating (e.g. `0.235`).
- `skill_delta`: Displayed as rating gain/loss animation (e.g. `+0.035 Skill Up!`).

#### Error Response (`409 Conflict` - Duplicate Submission)
```json
{
  "detail": "Telemetry already submitted for this level."
}
```

---

### `GET /api/v1/gameplay/history/{user_id}`
Retrieves paginated level completion history for a player profile.

#### Query Parameters
- `limit` (int, default `20`, max `100`): Maximum entries to return.
- `offset` (int, default `0`): Pagination offset.

#### Sample Request
```http
GET /api/v1/gameplay/history/a1b2c3d4-e5f6-7890-abcd-ef1234567890?limit=5&offset=0 HTTP/1.1
```

#### Sample Response (`200 OK`)
```json
[
  {
    "session_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "level_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "level_number": 1,
    "user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "status": "completed",
    "time_taken_seconds": 94,
    "free_hints_used": 1,
    "premium_hints_used": 0,
    "cell_error_count": 1,
    "created_at": "2026-09-14T10:30:00.000Z"
  }
]
```

---

## 4. UI Alignment & Component Mapping

| UI Feature / Component | Backend Data Field | Source Endpoint |
| :--- | :--- | :--- |
| **Grid Cell Letter** | `grid[row][col]` | `POST /api/v1/gameplay/generate-level` |
| **Word Length Badge `[3, 6]`** | `clue.word_lengths` | `POST /api/v1/gameplay/generate-level` |
| **Word Pattern `(3,6)`** | `clue.word_pattern` | `POST /api/v1/gameplay/generate-level` |
| **Active Clue Hint Text** | `clue.hint` / `hint_response.hint_text` | `POST /generate-level` / `POST /request-hint` |
| **Free Hints Counter** | `free_hints_remaining` | `POST /generate-level` & `POST /request-hint` |
| **Premium Token Balance** | `premium_hints_remaining` | `POST /users/login`, `/request-hint`, etc. |
| **Post-Solve Trivia Banner** | `clue.post_solve_trivia` | `POST /api/v1/gameplay/generate-level` |
| **Player Skill Rating** | `current_skill_level` / `new_skill_level` | `GET /users/{id}` & `POST /submit-telemetry` |
