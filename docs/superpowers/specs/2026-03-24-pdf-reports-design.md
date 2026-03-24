# Phase 4 — PDF Reports Design Spec

## Overview

Add PDF report generation for individual skaters and for the club as a whole, both scoped to a season. Reports are text and tables only (no embedded charts), generated on-demand via WeasyPrint (HTML to PDF), and streamed directly to the client.

## Dependencies

Add to `backend/pyproject.toml`:
- `weasyprint>=62.0` — HTML/CSS to PDF rendering
- `jinja2>=3.1` — HTML templating (may already be available transitively)

## File Structure

```
backend/
  app/
    routes/reports.py          # Report endpoints
    services/report_data.py    # Data aggregation for reports
    templates/
      reports/
        base.html              # Shared layout (header, footer, fonts, styles)
        skater_season.html     # Skater season report template
        club_season.html       # Club season report template
```

## Endpoints

### Skater Season Report

```
GET /api/reports/skater/{skater_id}/pdf?season=2025-2026
```

- Auth: `auth_guard` (any authenticated user)
- Response: `application/pdf`, streamed, with `Content-Disposition: attachment; filename="rapport-{skater_name}-{season}.pdf"`
- Errors: 404 if skater not found, 404 if no data for the given season

### Club Season Report

```
GET /api/reports/club/pdf?season=2025-2026
```

- Auth: `auth_guard`
- Response: `application/pdf`, streamed, with `Content-Disposition: attachment; filename="rapport-club-{season}.pdf"`
- Errors: 404 if no data for the given season

## Data Aggregation — `report_data.py`

### `get_skater_report_data(skater_id, season, db_session) -> SkaterReportData`

Returns a dataclass with:

- **skater**: name, club, birth_year, nationality
- **season**: the season string
- **personal_bests**: dict keyed by segment (SP/FS), each containing best TSS, TES, PCS with competition name and date
- **results**: list of all competition results for the season, sorted by date:
  - competition_name, competition_date, category, segment, rank, tss, tes, pcs, deductions
- **element_summary** (optional, None if no enriched data):
  - most_attempted: top 5 elements by frequency, with average GOE
  - best_goe: top 5 elements by average GOE (min 2 attempts)
  - total_elements_tracked: count

Logic:
1. Query `Score` joined with `Competition` filtered by `skater_id` and `Competition.season == season`
2. Compute personal bests by grouping scores by segment and taking max TSS/TES/PCS
3. Query `CategoryResult` for rank data
4. If any score has non-null `elements`, compute element summary by aggregating across all elements

### `get_club_report_data(season, db_session) -> ClubReportData`

Returns a dataclass with:

- **club_name**: from AppSettings
- **club_logo_path**: filesystem path to logo (for embedding in PDF), or None
- **season**: the season string
- **stats**: active_skaters, competitions_tracked, total_programs, total_podiums
- **skaters_summary**: list sorted by name:
  - name, category (most recent), competitions_entered, best_tss, best_tes, best_pcs
- **medals**: list sorted by competition date:
  - skater_name, competition_name, competition_date, category, rank (1/2/3 only)
- **most_improved**: up to 3 skaters with biggest TSS gain (first vs last result in season):
  - skater_name, category, first_tss, last_tss, delta

Logic:
1. Get club_name from AppSettings
2. Query all skaters belonging to the club (`Skater.club == club_name`)
3. Query `Score` and `CategoryResult` joined with `Competition` filtered by club skater IDs and season
4. Aggregate stats, compute personal bests per skater, find medals (rank <= 3), compute improvement deltas
5. Reuses similar logic to `dashboard.py` but returns full detail rather than summary counts

## HTML Templates

### `base.html`

Shared Jinja2 base template with:
- `@page` CSS for A4 portrait, margins
- Embedded fonts: Inter (body), Manrope (headlines) — loaded as base64 `@font-face` or system fallback
- Color tokens from Kinetic Lens: `#191c1e` (text), `#2e6385` (primary/headers), `#ba1a1a` (error)
- Table styles: clean, no heavy borders, zebra striping with surface colors
- Header block: club logo (if available) + report title + season + generation date
- Footer block: page number, generation timestamp
- `{% block content %}{% endblock %}` for report-specific content

### `skater_season.html`

Extends `base.html`. Sections:

1. **Report header**: Skater name, club, category, season
2. **Personal bests**: 2-column table (SP | FS) with best TSS, TES, PCS and where achieved
3. **Competition results**: Full-width table with columns: Date, Competition, Category, Segment, Rang, TSS, TES, PCS, Ded.
4. **Element analysis** (conditional `{% if element_summary %}`):
   - "Elements les plus travailles" — table: Element, Tentatives, GOE moyen
   - "Meilleurs GOE" — table: Element, GOE moyen, Tentatives

### `club_season.html`

Extends `base.html`. Sections:

1. **Cover area**: Club name (large), logo, season, generation date
2. **Statistiques de la saison**: 4 KPI blocks in a row — Patineurs actifs, Competitions, Programmes, Podiums
3. **Tableau des patineurs**: Full-width table: Nom, Categorie, Competitions, Meilleur TSS, Meilleur TES, Meilleur PCS
4. **Podiums et medailles**: Table: Patineur, Competition, Date, Categorie, Rang (with medal emoji or icon)
5. **Progression**: Table or cards: Patineur, Categorie, Premier TSS, Dernier TSS, Progression (+X.XX)

## Route Implementation — `reports.py`

```python
from litestar import Router, get
from litestar.response import Response

@get("/skater/{skater_id:int}/pdf")
async def skater_report_pdf(
    skater_id: int,
    season: str,  # query param
    db_session: AsyncSession,
) -> Response:
    data = await get_skater_report_data(skater_id, season, db_session)
    if not data.results:
        raise NotFoundException("Aucun resultat pour cette saison")
    html = render_template("reports/skater_season.html", data=data)
    pdf_bytes = weasyprint.HTML(string=html).write_pdf()
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="rapport-{data.skater.name}-{season}.pdf"'
        },
    )

@get("/club/pdf")
async def club_report_pdf(
    season: str,
    db_session: AsyncSession,
) -> Response:
    data = await get_club_report_data(season, db_session)
    if not data.skaters_summary:
        raise NotFoundException("Aucun resultat pour cette saison")
    html = render_template("reports/club_season.html", data=data)
    pdf_bytes = weasyprint.HTML(string=html).write_pdf()
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="rapport-club-{season}.pdf"'
        },
    )
```

Router mounted at `/api/reports` in `main.py`.

## Frontend Changes

### `HomePage.tsx`

Add a "Rapport de saison" button near the season selector:
```tsx
<a
  href={`/api/reports/club/pdf?season=${season}`}
  className="px-4 py-2 bg-primary text-on-primary rounded-xl text-sm font-bold"
>
  <span className="material-symbols-outlined text-sm">picture_as_pdf</span>
  Rapport de saison
</a>
```

### `SkaterAnalyticsPage.tsx`

Add an "Exporter le bilan" button near the season selector:
```tsx
<a
  href={`/api/reports/skater/${skaterId}/pdf?season=${season}`}
  className="px-4 py-2 bg-primary text-on-primary rounded-xl text-sm font-bold"
>
  <span className="material-symbols-outlined text-sm">picture_as_pdf</span>
  Exporter le bilan
</a>
```

## Docker Considerations

WeasyPrint requires system libraries (cairo, pango, gdk-pixbuf). Update `Dockerfile.backend`:
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 \
    && rm -rf /var/lib/apt/lists/*
```

## Verification

1. Import 3+ competitions for a season with PDF enrichment on at least one
2. `GET /api/reports/skater/{id}/pdf?season=2025-2026` — downloads a PDF with personal bests, results table, and element summary
3. `GET /api/reports/club/pdf?season=2025-2026` — downloads a multi-section club PDF
4. Reports render correctly in a PDF viewer (A4, readable tables, proper French text)
5. Auth required — unauthenticated requests return 401
6. Missing data returns 404 with clear message
7. Docker build succeeds with WeasyPrint system deps
