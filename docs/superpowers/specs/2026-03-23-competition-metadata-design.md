# Competition Metadata: Type, City, Country, Filtering & Sorting

**Date:** 2026-03-23
**Status:** Approved

## Goal

Automatically extract competition metadata (type, city, country, season) during import, let admins review/correct via inline editing, and enable filtering and sorting on the Competitions page.

## Competition Types

| Code | Label | URL/HTML patterns |
|------|-------|-------------------|
| `cr` | Compétition Régionale | `/CR-/`, local league events (CoupeCostieres, MMMP, CFL-BPG, NPL) |
| `tf` | Trophée Fédéral | `/TF-/`, title contains "Trophée Fédéral" |
| `tdf` | Tournoi de France | `/TDF_/`, `/TDF[_-]/`, title contains "Tournoi de France" |
| `masters` | Masters | `/MASTERS/`, title contains "Masters" |
| `nationales_autres` | Nationales Autres | Ouverture, TMNCA, and other CSNPA national events not in other categories |
| `championnats_france` | Championnats de France | `/FFSG_ELITES/`, `/FRANCE_JUNIOR/`, `/FRANCE_NOVICE/`, `/france_minime/`, `/France_3_/`, `/cdf_adultes/`, title contains "Championnat" |
| `france_clubs` | France Clubs | `/SFC_/`, `/Sel_Fr_Clubs/`, `/FC_/`, `/franceclubs_/`, title contains "France Club" |
| `grand_prix` | Grand Prix | `/gpfra/`, `/gpf\d/`, title contains "Grand Prix" |
| `championnats_europe` | Championnats d'Europe | `/ec\d{4}/`, title contains "European" |
| `championnats_monde` | Championnats du Monde | `/wc\d{4}/`, title contains "World Championships" (not Junior) |
| `championnats_monde_junior` | Championnats du Monde Junior | `/wjc\d{4}/`, title contains "World Junior" |
| `jeux_olympiques` | Jeux Olympiques | `/owg\d{4}/`, title contains "Olympic" |
| `autre` | Autre | Fallback when no pattern matches |

## Data Model Changes

New columns on `Competition`:

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| `city` | `String(100)`, nullable | `None` | City name |
| `country` | `String(100)`, nullable | `"France"` | Country, defaults to France |
| `competition_type` | `String(50)`, nullable | `None` | Type code from table above |
| `metadata_confirmed` | `Boolean` | `False` | True once admin has validated |

## Backend: Metadata Detection Service

New module: `backend/app/services/competition_metadata.py`

### `detect_metadata(url: str, html: str) -> dict`

Returns `{competition_type, city, country, season}`.

**Detection in 3 passes:**

1. **URL patterns** — regex on URL path for type detection and season extraction (`Saison20252026` → `2025-2026`, `season2526` → `2025-2026`, `2024-2025` in path)
2. **HTML content** — parse `<title>` and visible text to confirm/refine type, extract city (often in title or address line), extract country (default France, except ISU events where it's in the page)
3. **Fallbacks** — city from URL path segments (`TDF_Colmar_2025` → "Colmar", `CR-Castres` → "Castres"), season from competition date (cutover July: before July → season (year-1)/year, July onwards → season year/(year+1))

### Integration with Import

At the end of `run_import`, after scraping, call `detect_metadata(comp.url, index_html)`. Fill empty fields only, set `metadata_confirmed=False`. The index HTML is already fetched during scraping — pass it through rather than re-fetching.

## API Changes

### Modified: `GET /api/competitions/`

New optional query params:
- `season` — filter by season (e.g. `2025-2026`)
- `type` — filter by competition_type code
- `sort` — `date` (default), `city`, `country`
- `order` — `desc` (default), `asc`

### Modified: `competition_to_dict`

Add `city`, `country`, `competition_type`, `metadata_confirmed` to response.

### New: `PATCH /api/competitions/{id}`

Admin-only. Accepts partial update of `city`, `country`, `competition_type`, `season`. Automatically sets `metadata_confirmed=True` on save.

### New: `POST /api/competitions/{id}/confirm-metadata`

Admin-only. Sets `metadata_confirmed=True` without changing any fields (the "Valider" button).

## Frontend Changes

### Competition Type

Add to `client.ts`:
- New fields on `Competition` interface: `city`, `country`, `competition_type`, `metadata_confirmed`
- `api.competitions.update(id, data)` — PATCH endpoint
- `api.competitions.confirmMetadata(id)` — POST confirm endpoint
- `COMPETITION_TYPES` constant mapping codes to French labels

### CompetitionsPage

**Filter bar** (above competition list):
- Season dropdown (populated from distinct seasons in data)
- Type dropdown (all competition types)
- Sort dropdown: Date ↓, Date ↑, Ville A→Z, Ville Z→A, Pays A→Z
- Checkbox: "À vérifier uniquement" (filters `metadata_confirmed === false`)

**Competition cards** (modified):
- Type badge (grey pill) next to name
- "À vérifier" badge (red pill) when `metadata_confirmed === false`
- Subtitle line: city + country, date (formatted in French), season
- Admin buttons: "Valider" (confirm without edit) + "Modifier" (expand inline editor)
- Existing import/reimport/enrich/delete buttons unchanged

**Inline editor** (expands on "Modifier"):
- Type dropdown, city input, country input, season input
- "Enregistrer" saves + confirms, "Annuler" collapses

Filtering and sorting are done client-side (dataset is small enough). Server-side params exist as fallback but frontend handles it.

## Migration

Alembic migration adding the 4 new columns. Existing competitions get `metadata_confirmed=False`, `country="France"`, others `NULL`. A one-time backfill can run `detect_metadata` on existing competitions during migration or as a management command.
