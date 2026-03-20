# Frontend Design System: "Kinetic Lens"

> Inspired by the provided Stitch mockup and DESIGN.md spec. All implementation decisions should reference this document.

---

## 1. Philosophy & Creative North Star

The UI is a **"Kinetic Lens"** — a high-end editorial interface that treats every data point as a critical coaching insight. It avoids the industrial "dashboard" look by using generous white space, atmospheric layering, and typographic authority instead of borders and gridlines.

Key personality traits:
- **Precise but warm** — clinical data presented with editorial grace
- **Layered, not bordered** — depth through background shifts, never lines
- **Coaches first** — density is tamed by hierarchy, not by hiding information

## Language

**The entire frontend is in French.** No multilingual support is planned. All labels, buttons, headings, placeholder text, empty states, and error messages must be written in French from the start. Examples:

| English (don't use) | French (use this) |
|---------------------|-------------------|
| Dashboard | Tableau de bord |
| Skaters | Patineurs |
| Import | Importer |
| Competitions | Compétitions |
| Recent Results | Résultats récents |
| Total Score | Score total |
| Export Season Report | Exporter le rapport de saison |
| Personal Best | Record personnel |
| View All | Voir tout |
| Active Roster | Effectif actif |
| Most Improved | Plus grande progression |
| Elements | Éléments |
| Short Program | Programme court |
| Free Skate | Programme libre |
| Rank | Rang |
| Club | Club |
| Season | Saison |
| Setup | Configuration |
| Save | Enregistrer |

---

## 2. UI Framework: Tailwind CSS (no component library)

**Decision: Tailwind CSS only — no Ant Design, no MUI, no shadcn.**

Rationale:
- The design system is opinionated and custom (no-border rule, tonal layering, specific color tokens). Component libraries would fight it, requiring heavy overrides.
- The Stitch mockup is already written in Tailwind — the translation is direct.
- Recharts (already in the project) integrates cleanly with Tailwind styling.
- Tailwind keeps the bundle lean for a self-hosted club tool.

The existing `tailwind.config.js` must be extended with the full design token set below.

---

## 3. Color Tokens

Add all tokens to `tailwind.config.js` under `theme.extend.colors`:

```js
colors: {
  "background":                "#f7f9fb",
  "surface":                   "#f7f9fb",
  "surface-bright":            "#f7f9fb",
  "surface-dim":               "#d8dadc",
  "surface-container-lowest":  "#ffffff",
  "surface-container-low":     "#f2f4f6",
  "surface-container":         "#eceef0",
  "surface-container-high":    "#e6e8ea",
  "surface-container-highest": "#e0e3e5",
  "surface-variant":           "#e0e3e5",
  "on-surface":                "#191c1e",
  "on-surface-variant":        "#41484d",
  "outline":                   "#71787e",
  "outline-variant":           "#c1c7ce",
  "inverse-surface":           "#2d3133",
  "inverse-on-surface":        "#eff1f3",

  "primary":                   "#2e6385",
  "on-primary":                "#ffffff",
  "primary-container":         "#a5d8ff",
  "on-primary-container":      "#285f80",
  "primary-fixed":             "#c9e6ff",
  "primary-fixed-dim":         "#9accf3",
  "on-primary-fixed":          "#001e2f",
  "on-primary-fixed-variant":  "#0c4b6c",
  "inverse-primary":           "#9accf3",
  "surface-tint":              "#2e6385",

  "secondary":                 "#4d6073",
  "on-secondary":              "#ffffff",
  "secondary-container":       "#cde2f9",
  "on-secondary-container":    "#516578",
  "secondary-fixed":           "#d0e5fb",
  "secondary-fixed-dim":       "#b4c9df",
  "on-secondary-fixed":        "#071d2e",
  "on-secondary-fixed-variant":"#35495b",

  "tertiary":                  "#7d5718",
  "on-tertiary":               "#ffffff",
  "tertiary-container":        "#fdc97f",
  "on-tertiary-container":     "#785313",
  "tertiary-fixed":            "#ffddb2",
  "tertiary-fixed-dim":        "#f1be75",
  "on-tertiary-fixed":         "#291800",
  "on-tertiary-fixed-variant": "#624000",

  "error":                     "#ba1a1a",
  "on-error":                  "#ffffff",
  "error-container":           "#ffdad6",
  "on-error-container":        "#93000a",
}
```

### Semantic usage

| Token | When to use |
|-------|-------------|
| `primary` (#2e6385) | Primary buttons, active nav, chart line, progress bars |
| `primary-container` (#a5d8ff) | Icon backgrounds, badge fills, chip backgrounds, chart fills |
| `tertiary` (#7d5718) | Personal bests, medals, milestones — used sparingly |
| `tertiary-container` (#fdc97f) | Badge for top TSS scores |
| `error` (#ba1a1a) | Declining trends, import failures, critical alerts |
| `surface-container-lowest` | Cards, table rows (active/foreground) |
| `surface-container-low` | Table header background, sidebar, secondary panels |
| `surface-container` | Page sections, alert panels |
| `on-surface` (#191c1e) | All body text — never pure black |

---

## 4. Typography

```js
fontFamily: {
  headline: ["Manrope", "sans-serif"],
  body:     ["Inter", "sans-serif"],
  label:    ["Inter", "sans-serif"],
}
```

Load from Google Fonts in `index.html`:
```html
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700;800&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet"/>
```

### Scale

| Role | Element | Size | Weight | Font |
|------|---------|------|--------|------|
| Display (score hero) | TSS headline | 3.5rem | 800 | Manrope |
| Headline large | Page title | 1.5rem | 700 | Manrope |
| Headline medium | Section title | 1.25rem | 700 | Manrope |
| Headline small | Card title | 1rem | 700 | Manrope |
| Body medium | Notes, descriptions | 0.875rem | 400 | Inter |
| Label small | Table headers | 0.6875rem | 700, uppercase, tracking-widest | Inter |
| Data mono | Numeric scores | 0.875rem | 500, `font-mono` | Inter |

Rule: `h1`–`h4` → `font-headline`. All other text → `font-body` / `font-label`.

---

## 5. Elevation & Depth (The No-Border Rule)

**Borders are prohibited for sectioning content.**

Use surface layering instead:

```
Page background:  bg-surface           (#f7f9fb)
Sidebar/panels:   bg-surface-container-low  (#f2f4f6)
Section panels:   bg-surface-container  (#eceef0)
Cards:            bg-surface-container-lowest  (#ffffff)
```

### Shadows

- **Cards / data panels:** `shadow-sm` — subtle lift
- **Floating elements / modals:** Arctic Shadow: `0px 20px 40px rgba(24, 44, 61, 0.06)`
  - Add as custom Tailwind utility: `shadow-arctic`
- **Ghost border fallback** (accessibility only, e.g. chart axes): `outline-variant` at 15% opacity

### Borders that ARE allowed

- Left accent stripe on alert cards: `border-l-4 border-primary` / `border-error` / `border-tertiary`
- Separator lines: `border-slate-200/50` (at 50% opacity — "felt, not seen")

---

## 6. Border Radius

```js
borderRadius: {
  DEFAULT: "0.125rem",  // 2px — sharp, precise
  lg:      "0.25rem",   // 4px
  xl:      "0.5rem",    // 8px — cards
  full:    "0.75rem",   // 12px — pills, chips
}
```

Use `rounded-xl` for cards, `rounded-full` for chips/badges/avatar, `rounded-lg` for buttons.

---

## 7. Layout

### Shell

```
┌─────────────────────────────────────────────────────┐
│  Sidebar (w-64, fixed, bg-surface-container-low)    │
│  ┌──────────────────────────────────────────────┐   │
│  │ Club logo + name (Manrope, font-black)       │   │
│  │ "Technical Division" label (tiny uppercase)  │   │
│  ├──────────────────────────────────────────────┤   │
│  │ Nav links (uppercase, tracking-wider, 11px)  │   │
│  │  • Tableau de bord                           │   │
│  │  • Patineurs                                 │   │
│  │  • Compétitions (admin)                      │   │
│  │  • Comparaisons (futur)                      │   │
│  ├──────────────────────────────────────────────┤   │
│  │ Aide / Déconnexion (bas)                     │   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
│  Main (ml-64, min-h-screen)                          │
│  ┌──────────────────────────────────────────────┐   │
│  │ TopBar (sticky, backdrop-blur, shadow-sm)    │   │
│  │  [Page title]    [Search]    [Icons][Avatar] │   │
│  ├──────────────────────────────────────────────┤   │
│  │ Content (p-8, max-w-7xl, mx-auto, space-y-8) │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

### Page grid

Use **bento-style grid** on dashboard:
- Hero KPI row: `grid grid-cols-1 md:grid-cols-3 gap-6`
- Main content: `grid grid-cols-1 lg:grid-cols-3 gap-8`
  - Wide panel (chart + table): `lg:col-span-2`
  - Narrow sidebar (alerts + quick actions): `lg:col-span-1`

### Spacing tokens

- Page padding: `p-8` (2rem)
- Section gap: `space-y-8` (2rem)
- Card padding: `p-6` (1.5rem)
- Row padding: `px-6 py-4`

---

## 8. Components

### KPI Cards (Hero Row)

Two variants:

**Standard card:**
```
bg-surface-container-lowest rounded-xl shadow-sm border-l-4 border-primary
hover:bg-primary-container/10 transition-colors
```
- Icon: `bg-primary-container p-2 rounded-lg` with `text-primary` icon
- Value: `text-4xl font-extrabold font-headline text-on-surface`
- Label: `text-sm font-medium text-slate-500`

**Highlight card (accent, e.g. recent competition):**
```
bg-primary text-on-primary rounded-xl shadow-lg relative overflow-hidden
```
- Large background icon at `-right-10 -bottom-10 opacity-10 text-[160px]`

### Alert / Notification Cards

```
bg-surface-container-lowest p-4 rounded-xl shadow-sm border-l-4 border-{color}
```
Colors: `border-primary` (info), `border-error` (alert), `border-tertiary` (milestone)

Category label: `text-[10px] font-black uppercase tracking-widest text-{color}`

### Data Tables

- No dividers (`divide-y-0`)
- Header row: `bg-surface-container-low`
- Header cells: `text-[10px] font-bold text-slate-500 uppercase tracking-widest`
- Row padding: `px-6 py-4`
- Alternating rows: `bg-surface-container-lowest` / `bg-slate-50/50`
- Hover: `hover:bg-slate-50 transition-colors`
- Score badges: `bg-primary-container/30 px-3 py-1 rounded-lg font-bold text-sm`
- Personal best badge: `bg-tertiary-container/30 text-on-tertiary-container px-3 py-1 rounded-lg`
- Numeric values: `font-mono font-medium`

### Navigation Links

Active state:
```
bg-white text-sky-800 shadow-sm rounded-lg mx-2 my-1 px-4 py-3
font-bold flex items-center gap-3
```
Inactive state:
```
text-slate-600 hover:bg-slate-200/50 rounded-lg mx-2 my-1 px-4 py-3
flex items-center gap-3 transition-transform hover:translate-x-1
```
Label: `text-[11px] font-bold uppercase tracking-wider`

### Buttons

| Type | Class |
|------|-------|
| Primary | `bg-primary text-on-primary rounded-lg py-2 px-4 text-xs font-bold active:scale-95 transition-all` |
| Secondary | `bg-surface-container-high text-on-surface rounded-lg py-1.5 px-3 text-[10px] font-bold uppercase` |
| Ghost/outline | `border border-primary text-primary rounded-lg py-1.5 px-3 text-[10px] font-bold uppercase` |
| Text link | `text-primary font-bold text-xs uppercase tracking-wider hover:underline` |

### Chips & Badges

```
flex items-center gap-1.5 text-xs font-bold px-3 py-1.5 rounded-full bg-slate-100
```
Colored dot: `w-2 h-2 rounded-full bg-primary`

### Charts (Recharts)

- Line/area color: `#2e6385` (primary)
- Secondary series: `#a5d8ff` (primary-container)
- Tertiary highlight: `#fdc97f` (tertiary-container)
- Grid lines: `stroke="#e0e3e5"` (outline-variant, very light)
- No axis borders — use `axisLine={false}` and `tickLine={false}`
- Tooltips: white card with Arctic Shadow, `font-body text-xs`

### Icons

Use **Material Symbols Outlined** (loaded from Google Fonts):
```html
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet"/>
```
CSS: `font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;`
Filled variant: `style="font-variation-settings: 'FILL' 1;"`

### Glassmorphism (floating overlays only)

For score overlays or hero metric callouts:
```css
background: rgba(255, 255, 255, 0.70);
backdrop-filter: blur(12px);
```
Tailwind: `bg-white/70 backdrop-blur-md`

### Quick Action Panel ("Generate Report" dark card)

```
bg-slate-900 rounded-xl p-5 text-on-primary relative overflow-hidden group
```
Arrow button: `w-8 h-8 rounded-full bg-white text-slate-900 transition-transform group-hover:scale-110`
Background icon: `absolute -right-4 -bottom-4 text-7xl opacity-5`

---

## 9. Top App Bar

```
sticky top-0 bg-slate-50/70 backdrop-blur-xl z-30 shadow-sm
flex justify-between items-center px-8 py-4
```

- Left: Page title (`text-xl font-bold tracking-tighter text-sky-900 font-headline`) + divider + search input
- Search: `bg-surface-container-highest/50 border-none rounded-full py-1.5 pl-10 pr-4 text-xs focus:ring-1 focus:ring-primary`
- Right: notification bell (with `bg-error` dot badge), settings, avatar

---

## 10. Page-Specific Layout Notes

### Dashboard (`/`) — Tableau de bord

Per plan Phase 1.0:
- Sélecteur de saison: top-right, ghost dropdown
- Rangée KPI (3 cartes): Effectif actif | Progression moyenne | Compétition récente (highlight)
- Grille bento: graphique Progression du club (2/3) + Alertes entraîneur (1/3)
- Tableau Résultats récents sous le graphique
- "Exporter le rapport de saison" → dark quick-action card in sidebar

### Liste des patineurs (`/patineurs`)

- Liste des patineurs du club par défaut: cards ou lignes de tableau (initiale avatar, nom, catégorie, dernier score, nb compétitions)
- Bouton "Afficher tous les clubs" en haut
- Clic → page Analyse patineur

### Skater Analytics (`/skaters/:id/analytics`)

Inspired by the Stitch skater profile mockup. **The mockup is more ambitious than the current plan — use it as a design reference, not a feature list.** Implement only what the plan specifies; the layout language below is the visual target.

#### Hero Header

Full-width banner with a gradient background (`from-primary to-primary-container/30`, subtle linear gradient left-to-right):

```
┌──────────────────────────────────────────────────────────────┐
│  [Avatar photo]  Prénom N.          CLASSEMENT   RECORD SAISON│
│  Catégorie · Club · Age · X ans actif    #14        218.42   │
└──────────────────────────────────────────────────────────────┘
```

- Avatar: `w-20 h-20 rounded-full` with a subtle white ring `ring-2 ring-white/50`
- Skater name: `text-3xl font-extrabold font-headline text-on-primary` (white on gradient)
- Category chip: small `bg-white/20 text-white rounded-full px-3 py-1 text-xs font-bold uppercase`
- Stat boxes (Classement, Record saison): `bg-white/15 backdrop-blur-sm rounded-xl px-4 py-3 text-center` — glassmorphism on the gradient
  - Value: `text-2xl font-extrabold font-headline text-white`
  - Label: `text-[10px] uppercase tracking-widest text-white/70`
- "Télécharger le rapport complet" link: `text-white/80 text-xs font-bold hover:text-white underline`

#### Main Layout

Same bento pattern as dashboard: `grid grid-cols-1 lg:grid-cols-3 gap-8`

**Left/wide panel (2/3): Score chart + Recent competition history**

- `Analyse longitudinale des scores` — Recharts LineChart (TES + PCS lines, 12 months x-axis)
  - Legend chips: TES (primary dot) / PCS (primary-container dot)
  - Chart height: `h-64`
  - Grid: very light (`stroke="#e0e3e5"`)

- `Historique des compétitions récentes` — results table
  - Columns: Compétition | Date | Rang | TES | PCS | Total | Tendance
  - Rang badge: `bg-tertiary-container/30 text-on-tertiary-container` for podium, plain text otherwise
  - Tendance: `+X.X` in `text-primary font-mono` for positive, `text-error` for negative — with a tiny arrow icon

**Right/narrow panel (1/3): Performance KPI cards**

Stack of metric cards (each `bg-surface-container-lowest rounded-xl p-4 shadow-sm`):

```
┌─────────────────────────────────────┐
│  PRÉCISION DE SAUT        ★  92.4%  │
│  ████████████████████░░   progress  │
│  Basé sur les GOE des éléments saut │
└─────────────────────────────────────┘
```

- Metric cards currently planned: available from PDF enrichment data
  - **Précision de saut** — avg positive GOE rate on jump elements
  - **Niveau de spin moyen** — average spin level achieved
  - **Note de pas** — step sequence grade
- Card header: metric name in `label-sm` + icon (Material Symbol) + value in `text-2xl font-extrabold font-headline`
- Progress bar: `h-1.5 rounded-full bg-primary-container` track, `bg-primary` fill
- Gold star icon for milestones/PBs: `text-tertiary` Material Symbol `star` (filled)
- Caption text: `text-xs text-slate-500 mt-1`

> **Implementation note:** These KPI cards require PDF enrichment data (`elements` JSON). Only show them when elements are available; otherwise show an "Enrichir avec les PDF" prompt instead.

### Détail compétition (`/competitions/:id`)

- Regroupé par catégorie + segment
- Tableau de scores selon le modèle data table ci-dessus
- Noms des patineurs = liens → page analyse patineur

### Configuration initiale (`/configuration`)

- Carte centrée sur fond `bg-surface`
- Saisie du nom du club, bouton Enregistrer
- Minimal — sans nav/sidebar

---

## 11. Do's and Don'ts (Summary)

| Do | Don't |
|----|-------|
| Use `on-surface` (#191c1e) for all text | Use pure `#000000` |
| Use `tertiary` for PBs, medals, milestones | Overuse gold/amber |
| Use asymmetric layouts (wide chart + narrow sidebar) | Use equal columns for everything |
| Use `spacing-8` page margins (`p-8`) | Crowd content to the edges |
| Use surface nesting to separate dense data | Add lines or dividers |
| Use `primary` for positive trends | Use green for "success" |
| Use `error` (#ba1a1a) only for critical failures | Use red for general alerts |
| Use `font-mono` for all numeric scores | Use proportional fonts for numbers |

---

## 12. Tailwind Config Changes Required

In `frontend/tailwind.config.js`, extend:
1. Full color token map (Section 3)
2. Font families: `headline`, `body`, `label` (Section 4)
3. Border radius scale (Section 6)
4. Custom shadow: `shadow-arctic: '0px 20px 40px rgba(24, 44, 61, 0.06)'`

In `frontend/index.html`, add Google Fonts links (Manrope + Inter + Material Symbols).

In `frontend/src/index.css`, set base styles:
```css
body { font-family: 'Inter', sans-serif; color: #191c1e; }
h1, h2, h3, h4 { font-family: 'Manrope', sans-serif; }
.material-symbols-outlined {
  font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
  vertical-align: middle;
}
```
