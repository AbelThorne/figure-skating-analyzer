# Competitions Import Improvements

## Overview

Three improvements to the competition import system:
1. **Ligue field** with auto-detection and filtering
2. **Auto-polling** for competition updates (hourly, with toggle)
3. **Status labels** ("Prochainement" / "En cours") based on competition dates

---

## 1. Data Model Changes

### New columns on `Competition`

| Column | Type | Default | Purpose |
|--------|------|---------|---------|
| `ligue` | `String(50)` | `None` | Regional league / federation |
| `date_end` | `Date` | `None` | Last day of competition |
| `polling_enabled` | `Boolean` | `False` | Whether auto-polling is active |
| `polling_activated_at` | `DateTime` | `None` | When polling was last enabled (for auto-disable logic) |

### Migration

Add to `_MIGRATIONS` in `database.py`:
- `("competitions", "ligue", "VARCHAR(50)")`
- `("competitions", "date_end", "DATE")`
- `("competitions", "polling_enabled", "BOOLEAN DEFAULT 0")`
- `("competitions", "polling_activated_at", "DATETIME")`

---

## 2. Ligue Detection

### Values

Fixed list: `ISU`, `FFSG`, `Occitanie`, `Aquitaine`, `Ile-de-France`, `AURA`, `Grand Est`, `Pays de Loire`, `Bretagne`, `Bourgogne Franche-Comte`, `Centre Val de Loire`, `Hauts de France`, `Normandie`, `Autres`.

### Detection logic (in `competition_metadata.py`)

New function `detect_ligue(url: str, html: str) -> str`:

1. **CSNPA in URL path or HTML body** (case-insensitive) -> `FFSG`
2. **ISU domains** (`results.isu.org`, `isuresults.com`) -> `ISU`
3. **Domain mapping:**
   - `ligue-des-alpes-patinage.org` -> `AURA`
   - `ligue-occitanie-sg.com` -> `Occitanie`
   - (extensible as new domains are discovered)
4. **Fallback** -> `Autres`

### Integration points

- Called during import (in `import_service.py` after scraping)
- Called during `backfill-metadata` endpoint
- Admin can override via the edit form (add `ligue` to updatable fields in `PATCH /api/competitions/{id}`)

---

## 3. Date End Extraction

### Scraper changes

In `ScrapedCompetitionInfo`, add `date_end: str | None = None`.

In `FSManagerScraper.parse_competition_info()`, the banner typically shows a date range like "20.03.2026 - 22.03.2026". Extract both dates:
- First `DD.MM.YYYY` -> `date` (already done)
- Second `DD.MM.YYYY` -> `date_end`
- If only one date found, `date_end` = `date`

### Storage

`import_service.py` stores `date_end` on the Competition model after scraping, alongside existing `date` storage.

---

## 4. Auto-Polling

### Backend polling loop

A new `_polling_loop()` coroutine in `main.py` lifespan:

```
async def _polling_loop():
    while True:
        await asyncio.sleep(3600)  # 1 hour
        async with async_session_factory() as session:
            comps = query competitions where polling_enabled = True
            today = date.today()
            for comp in comps:
                # Auto-disable if date_end + 7 days < today
                if comp.date_end and (comp.date_end + timedelta(days=7)) < today:
                    comp.polling_enabled = False
                    continue
                # Submit import + enrich jobs
                job_queue.create_job("import", comp.id)
                job_queue.create_job("enrich", comp.id)
            await session.commit()
```

Started as an `asyncio.create_task()` in lifespan, cancelled on shutdown.

### API

- `POST /api/competitions/{id}/polling` — body: `{"enabled": true/false}` (admin only)
  - When enabling: sets `polling_enabled = True`, `polling_activated_at = now()`
  - When disabling: sets `polling_enabled = False`
  - Returns updated competition dict

### Frontend

- Icon button on each competition row (admin only): `sync` material icon
  - Primary color when polling is enabled, surface-variant when disabled
  - Tooltip: "Suivi automatique actif" / "Activer le suivi automatique"
  - Clicking toggles the state via the API
- New filter: "Suivi auto" checkbox in the filter bar to show only polled competitions

---

## 5. Competition Status Labels

### Logic (client-side)

Computed from `date` and `date_end`:

| Condition | Label | Style |
|-----------|-------|-------|
| `date` is in the future | "Prochainement" | `bg-surface-container text-on-surface-variant` (subtle) |
| `date <= today <= date_end` | "En cours" | `bg-primary/10 text-primary` (prominent) |
| `date_end < today` or no dates | No label | — |

### Where displayed

1. **CompetitionsPage** — badge next to the competition name, alongside existing badges ("A verifier", competition type)
2. **Competition detail page** — in the header/banner area

---

## 6. Frontend API & Types

### Competition interface

Add to `Competition` type:
- `ligue: string | null`
- `date_end: string | null`
- `polling_enabled: boolean`
- `polling_activated_at: string | null`

### New constants

```typescript
export const LIGUES: Record<string, string> = {
  ISU: "ISU",
  FFSG: "FFSG",
  Occitanie: "Occitanie",
  Aquitaine: "Aquitaine",
  "Ile-de-France": "Ile-de-France",
  AURA: "AURA",
  "Grand Est": "Grand Est",
  "Pays de Loire": "Pays de Loire",
  Bretagne: "Bretagne",
  "Bourgogne Franche-Comte": "Bourgogne Franche-Comte",
  "Centre Val de Loire": "Centre Val de Loire",
  "Hauts de France": "Hauts de France",
  Normandie: "Normandie",
  Autres: "Autres",
};
```

### New API function

```typescript
togglePolling: (id: number, enabled: boolean) =>
  request<Competition>(`/competitions/${id}/polling`, {
    method: "POST",
    body: JSON.stringify({ enabled }),
  }),
```

### Filter additions

- Ligue dropdown filter (similar to existing Season and Type filters)
- "Suivi auto" checkbox filter

---

## 7. Backend DTO & Route Changes

### `competition_to_dict()`

Add `ligue`, `date_end`, `polling_enabled`, `polling_activated_at` to the returned dict.

### `PATCH /api/competitions/{id}`

Add `ligue` to the list of updatable fields.

### `list_competitions`

Add optional `ligue` query parameter for server-side filtering.

---

## 8. Files to Modify

### Backend
- `app/models/competition.py` — new columns
- `app/database.py` — migration entries
- `app/services/site_scraper.py` — `date_end` in `ScrapedCompetitionInfo` + extraction
- `app/services/competition_metadata.py` — `detect_ligue()` function
- `app/services/import_service.py` — store `ligue` and `date_end`
- `app/routes/competitions.py` — DTO, polling endpoint, ligue filter, edit support
- `app/main.py` — polling loop in lifespan

### Frontend
- `src/api/client.ts` — types, constants, API function
- `src/pages/CompetitionsPage.tsx` — ligue filter, polling toggle, status labels
- Competition detail page — status label in banner

### Tests
- Test ligue detection logic
- Test date_end extraction from scraper
- Test polling auto-disable logic
