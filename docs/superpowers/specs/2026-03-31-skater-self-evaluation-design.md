# Skater Self-Evaluation Design

**Date**: 2026-03-31
**Status**: Draft

## Overview

Self-evaluation feature for skaters to track their training sessions. Three independent components:

1. **Mood** — quick 1-5 emoji rating per session, always visible to coaches/admins
2. **Self-evaluation** — free-text notes + per-element 1-5 ratings, private by default, shareable
3. **Registered program** — stored SP/FS element sequences, pre-fill evaluations

Coaches/admins see an anonymous weekly mood aggregate across all skaters. Shared evaluations appear in the existing training timeline.

## Data Model

### SkaterProgram

Registered technical program (SP or FS) for a skater.

| Field | Type | Description |
|-------|------|-------------|
| id | int PK | Auto-increment |
| skater_id | int FK → skaters | Owner |
| segment | str | "SP" or "FS" |
| elements | JSON | Ordered list of element names, e.g. `["3Lz", "3F+3T", "CCoSp4"]` |
| created_at | datetime | |
| updated_at | datetime | |

**Unique constraint**: `(skater_id, segment)` — one program per segment per skater.

### TrainingMood

Quick mood rating after a training session. Always visible to coaches/admins.

| Field | Type | Description |
|-------|------|-------------|
| id | int PK | Auto-increment |
| skater_id | int FK → skaters | Owner |
| date | date | Training date |
| rating | int | 1 to 5 |
| created_at | datetime | |

**Unique constraint**: `(skater_id, date)` — one mood per day per skater.

### SelfEvaluation

Detailed self-evaluation of a training session. Private by default.

| Field | Type | Description |
|-------|------|-------------|
| id | int PK | Auto-increment |
| skater_id | int FK → skaters | Owner |
| mood_id | int FK → training_moods, nullable | Optional link to same-day mood |
| date | date | Training date |
| notes | text, nullable | Free-text notes |
| element_ratings | JSON, nullable | `[{"name": "3Lz", "rating": 4}, {"name": "CCoSp4", "rating": 3}]` |
| shared | bool, default=False | Visible to coaches/admins |
| created_at | datetime | |
| updated_at | datetime | |

**Unique constraint**: `(skater_id, date)` — one evaluation per day per skater.

The `element_ratings` field is JSON (consistent with the existing `elements` field in Score). Elements are pre-filled from `SkaterProgram` but modifications in the evaluation form do not affect the registered program.

## API Routes

All routes under `/api/training/` in the existing `training.py` route file.

### Programs (`/api/training/programs`)

| Method | Route | Access | Description |
|--------|-------|--------|-------------|
| GET | `/programs?skater_id=` | skater (own), coach, admin | List skater's programs |
| PUT | `/programs` | skater (own), coach, admin | Upsert program (by skater_id + segment) |
| DELETE | `/programs/{id}` | skater (own), coach, admin | Delete program |

### Moods (`/api/training/moods`)

| Method | Route | Access | Description |
|--------|-------|--------|-------------|
| GET | `/moods?skater_id=&from=&to=` | skater (own), coach, admin | List moods, filterable by period |
| POST | `/moods` | skater (own) | Create today's mood |
| PUT | `/moods/{id}` | skater (own) | Update mood (same day) |
| GET | `/moods/weekly-summary?from=&to=` | coach, admin | Anonymous weekly aggregate |

**Weekly summary response**:
```json
{
  "average": 3.8,
  "count": 12,
  "distribution": [0, 1, 2, 5, 4]
}
```
`distribution[i]` = number of moods with rating `i+1`.

### Self-evaluations (`/api/training/self-evaluations`)

| Method | Route | Access | Description |
|--------|-------|--------|-------------|
| GET | `/self-evaluations?skater_id=&from=&to=` | skater (own), coach/admin (shared only) | List evaluations |
| POST | `/self-evaluations` | skater (own) | Create evaluation |
| PUT | `/self-evaluations/{id}` | skater (own) | Update (text, ratings, sharing) |
| DELETE | `/self-evaluations/{id}` | skater (own) | Delete evaluation |

## Permissions & Privacy

| Data | Skater (own) | Coach/Admin | Reader |
|------|-------------|-------------|--------|
| Program (SP/FS) | CRUD | Read | None |
| Mood | CRUD | Read (always) | None |
| Self-evaluation | CRUD | Read if `shared=True` | None |
| Weekly mood aggregate | None | Read (anonymous) | None |

Key rules:
- **Mood is always shared** — the UI clearly indicates "Visible par vos coachs" next to the mood input.
- **Self-evaluation is private by default**. The "Partager" toggle is clearly labeled. A shared evaluation can be re-privatized (skater keeps control).
- **Weekly mood aggregate is anonymous** — no per-skater breakdown. Coach sees "average 3.8 across 12 sessions this week", not "Léa rated 2 on Tuesday".
- **Exception**: if a self-evaluation is shared, the coach sees the associated mood in that evaluation's context (mood is public anyway).
- **Readers** have no access to any training data.

## Frontend

### Mood Input (quick access)

`MoodInput` component displayed at the top of the skater analytics page — 5 clickable emojis in a row:

`😞 😕 😐 🙂 😄`

Single tap to save. If already set for today, the active emoji is highlighted and can be changed. No form, no validation — just a click. Label: "Visible par vos coachs".

### Self-Evaluation Form

Accessible from analytics page via "Évaluer ma séance" button. Opens a form (modal or expandable section):

1. **Date** — pre-filled with today, editable
2. **Mood** — `MoodInput` component, pre-filled if already set
3. **Free-text notes** — textarea
4. **Technical elements** — list pre-filled from registered program (SP, FS, or both):
   - Each element: name + 5 clickable stars/circles (1-5)
   - "Ajouter un élément" button (free-text input)
   - Delete button (×) per element
   - Modifications only affect this evaluation, not the registered program
5. **Share toggle** — "Partager avec les coachs", off by default
6. **Save button**

### Program Management

"Mon programme" section in analytics page — two sub-sections SP and FS. Editable element list with add/remove. Saved via PUT upsert.

### History / Journal

New section "Journal" in analytics page:
- Mood timeline (emojis on a chronological strip)
- Past evaluations list (date, text excerpt, element ratings, "shared" badge)
- Element rating evolution chart over time (Recharts)

### Coach View — Mood Aggregate Widget

In `TrainingPage`, a "Humeur du groupe" widget:
- Current week average (emoji + number)
- Mini bar chart of distribution (count per rating)
- Trend vs previous week (up/down arrow)

Shared self-evaluations appear in `SkaterTrainingPage` training timeline alongside WeeklyReviews and incidents.

## Testing

### Backend (pytest, async, in-memory SQLite)

**Model tests**:
- CRUD for `SkaterProgram`, `TrainingMood`, `SelfEvaluation`
- Uniqueness constraints (one program per segment, one mood per day, one evaluation per day)
- Validation: mood rating 1-5, element_ratings ratings 1-5

**Route tests — permissions**:
- Skater can only access own data (via `require_skater_access`)
- Coach/admin sees all moods but only shared evaluations
- Reader gets 403 on all self-eval/mood/program routes
- Skater cannot access `moods/weekly-summary`

**Route tests — business logic**:
- POST mood creates; second POST same day returns 409
- PUT mood updates
- POST self-evaluation with registered program: verify GET program returns elements for pre-fill
- PUT self-evaluation toggle shared: verify coach visibility changes
- GET weekly-summary: verify correct aggregation (average, distribution, count)
- GET weekly-summary with no data: clean empty response

**Fixtures**: reuse existing (`skater_user_with_skater`, `admin_user`, etc.) + add `coach_user` fixture.

### Frontend
No frontend unit tests (consistent with existing project pattern).
