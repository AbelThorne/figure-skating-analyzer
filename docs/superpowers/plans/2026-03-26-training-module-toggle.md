# Module Entraînement activable — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendre le module de suivi d'entraînement activable/désactivable depuis les paramètres admin. Quand désactivé, tous les éléments UI liés à l'entraînement sont masqués.

**Architecture:** Ajouter un champ `training_enabled` (booléen, default `false`) sur `AppSettings`. L'exposer via l'endpoint `/api/config` (public). Le frontend lit ce flag depuis le query `["config"]` déjà en cache (TanStack Query, `staleTime: Infinity`) et conditionne l'affichage de : la nav "Entraînement", les routes `/entrainement/*`, l'onglet "Entraînement" dans les paramètres, l'onglet "Entraînement" dans la page patineur, et le bouton "Suivre" sur la fiche patineur.

**Tech Stack:** Python/Litestar/SQLAlchemy (backend), React/TypeScript/TanStack Query (frontend)

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/app/models/app_settings.py` | Modify | Add `training_enabled` boolean column |
| `backend/app/database.py` | Modify | Add migration for `training_enabled` column |
| `backend/app/routes/club_config.py` | Modify | Expose `training_enabled` in GET, accept it in PATCH |
| `frontend/src/api/client.ts` | Modify | Add `training_enabled` to `ConfigResponse` and `config.update` |
| `frontend/src/App.tsx` | Modify | Conditionally hide nav link + routes based on `training_enabled` |
| `frontend/src/pages/SkaterAnalyticsPage.tsx` | Modify | Hide training tab + toggle button when module disabled |
| `frontend/src/pages/SettingsPage.tsx` | Modify | Hide "Entraînement" tab when module disabled; add toggle in "Général" |
| `backend/tests/test_training_toggle.py` | Create | Tests for the feature |

---

### Task 1: Backend — Ajouter `training_enabled` au modèle et à la migration

**Files:**
- Modify: `backend/app/models/app_settings.py`
- Modify: `backend/app/database.py:41-54` (migration list)

- [ ] **Step 1: Add `training_enabled` column to AppSettings model**

In `backend/app/models/app_settings.py`, add after line 17 (`current_season`):

```python
training_enabled: Mapped[bool] = mapped_column(
    Integer, nullable=False, default=0, server_default="0"
)
```

Note: SQLite stores booleans as integers, so we use `Integer` with `default=0`. Also add `Integer` to the existing import from `sqlalchemy` (already imported on line 3).

- [ ] **Step 2: Add migration entry in `database.py`**

In `backend/app/database.py`, add to the `_MIGRATIONS` list (after the last entry at line 53):

```python
("app_settings", "training_enabled", "INTEGER DEFAULT 0"),
```

- [ ] **Step 3: Run tests to verify no regressions**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest -v --tb=short 2>&1 | tail -20`
Expected: all existing tests pass

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/app_settings.py backend/app/database.py
git commit -m "feat: add training_enabled column to AppSettings model"
```

---

### Task 2: Backend — Exposer `training_enabled` dans l'API config

**Files:**
- Modify: `backend/app/routes/club_config.py:18-69`

- [ ] **Step 1: Expose `training_enabled` in GET `/api/config`**

In `get_config`, add `"training_enabled": False` to the `setup_required: True` response dict (line 26), and add `"training_enabled": bool(settings.training_enabled)` to the normal response dict (after line 35):

The `setup_required: True` block becomes:
```python
    if not settings:
        return {
            "setup_required": True,
            "google_client_id": GOOGLE_CLIENT_ID or None,
            "training_enabled": False,
        }
```

The normal response block becomes:
```python
    return {
        "setup_required": False,
        "club_name": settings.club_name,
        "club_short": settings.club_short,
        "logo_url": f"/api/logos/{settings.logo_path}" if settings.logo_path else "",
        "current_season": settings.current_season,
        "google_client_id": GOOGLE_CLIENT_ID or None,
        "training_enabled": bool(settings.training_enabled),
    }
```

- [ ] **Step 2: Accept `training_enabled` in PATCH `/api/config`**

In `update_config`, add after line 56 (`current_season` handling):

```python
    if "training_enabled" in data:
        settings.training_enabled = bool(data["training_enabled"])
```

And add `"training_enabled": bool(settings.training_enabled)` to the PATCH response dict (line 61-68):

```python
    return Response(
        content={
            "club_name": settings.club_name,
            "club_short": settings.club_short,
            "logo_url": f"/api/logos/{settings.logo_path}" if settings.logo_path else "",
            "current_season": settings.current_season,
            "training_enabled": bool(settings.training_enabled),
        },
        status_code=200,
    )
```

- [ ] **Step 3: Run tests**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest -v --tb=short 2>&1 | tail -20`
Expected: all tests pass

- [ ] **Step 4: Commit**

```bash
git add backend/app/routes/club_config.py
git commit -m "feat: expose training_enabled in config API"
```

---

### Task 3: Backend — Tests

**Files:**
- Create: `backend/tests/test_training_toggle.py`

- [ ] **Step 1: Write tests for the training toggle feature**

Create `backend/tests/test_training_toggle.py`:

```python
"""Tests for training_enabled toggle in AppSettings / config API."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_config_returns_training_enabled_default_false(client: AsyncClient):
    """GET /api/config should return training_enabled=False by default."""
    res = await client.get("/api/config/")
    assert res.status_code == 200
    data = res.json()
    assert "training_enabled" in data
    assert data["training_enabled"] is False


@pytest.mark.asyncio
async def test_admin_can_enable_training(client: AsyncClient, admin_token: str):
    """PATCH /api/config with training_enabled=true should persist."""
    res = await client.patch(
        "/api/config/",
        json={"training_enabled": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    assert res.json()["training_enabled"] is True

    # Verify GET returns updated value
    res = await client.get("/api/config/")
    assert res.json()["training_enabled"] is True


@pytest.mark.asyncio
async def test_admin_can_disable_training(client: AsyncClient, admin_token: str):
    """Enable then disable training module."""
    await client.patch(
        "/api/config/",
        json={"training_enabled": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    res = await client.patch(
        "/api/config/",
        json={"training_enabled": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    assert res.json()["training_enabled"] is False


@pytest.mark.asyncio
async def test_reader_cannot_toggle_training(client: AsyncClient, reader_token: str):
    """Non-admin should be rejected."""
    res = await client.patch(
        "/api/config/",
        json={"training_enabled": True},
        headers={"Authorization": f"Bearer {reader_token}"},
    )
    assert res.status_code == 403
```

- [ ] **Step 2: Run the new tests**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_training_toggle.py -v`
Expected: all 4 tests pass

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_training_toggle.py
git commit -m "test: add tests for training_enabled toggle"
```

---

### Task 4: Frontend — Ajouter `training_enabled` au type et à l'API client

**Files:**
- Modify: `frontend/src/api/client.ts:346-352` (ConfigResponse type)
- Modify: `frontend/src/api/client.ts:585-589` (config.update params)

- [ ] **Step 1: Add `training_enabled` to ConfigResponse**

In `frontend/src/api/client.ts`, add to the `ConfigResponse` interface (after `current_season`):

```typescript
export interface ConfigResponse {
  setup_required: boolean;
  club_name?: string;
  club_short?: string;
  logo_url?: string;
  current_season?: string;
  google_client_id?: string;
  training_enabled?: boolean;
}
```

- [ ] **Step 2: Add `training_enabled` to config.update params**

Change the `update` method signature to include `training_enabled`:

```typescript
    update: (data: { club_name?: string; club_short?: string; current_season?: string; training_enabled?: boolean }) =>
      request<ConfigResponse>("/config/", {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat: add training_enabled to frontend config types"
```

---

### Task 5: Frontend — Masquer la navigation et les routes Entraînement

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Filter navLinks based on `training_enabled`**

In `AuthenticatedLayout`, the config is already fetched at line 109. Use it to filter the nav.

Replace the `navLinks` constant (line 24-30) to remove the training entry from the static array:

```typescript
const navLinksBase = [
  { to: "/", label: "TABLEAU DE BORD", icon: "dashboard", end: true },
  { to: "/patineurs", label: "PATINEURS", icon: "people", end: false },
  { to: "/competitions", label: "COMPÉTITIONS", icon: "emoji_events", end: false },
  { to: "/club", label: "CLUB", icon: "bar_chart", end: false },
];

const trainingNavLink = { to: "/entrainement", label: "ENTRAÎNEMENT", icon: "fitness_center", end: false };
```

- [ ] **Step 2: Conditionally include training nav link for admin/reader roles**

In `AuthenticatedLayout`, build the nav links dynamically using the already-fetched `config`:

Replace the admin/reader nav block (lines 177-194) that maps over `navLinks`:

```tsx
        ) : (
          <nav className="flex-1 py-2">
            {[...navLinksBase, ...(config?.training_enabled ? [trainingNavLink] : [])].map(({ to, label, icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                onClick={closeSidebar}
                className={({ isActive }) =>
                  isActive
                    ? "bg-white text-primary shadow-sm rounded-xl mx-2 my-0.5 px-4 py-3 font-bold flex items-center gap-3"
                    : "text-on-surface-variant hover:bg-surface-container rounded-xl mx-2 my-0.5 px-4 py-3 flex items-center gap-3 transition-colors"
                }
              >
                <span className="material-symbols-outlined text-xl">{icon}</span>
                <span className="text-[11px] font-bold uppercase tracking-wider">{label}</span>
              </NavLink>
            ))}
          </nav>
        )}
```

- [ ] **Step 3: Conditionally include training nav for coach role**

Replace the coach nav block (lines 154-175) to filter based on `config?.training_enabled`:

```tsx
        ) : user?.role === "coach" ? (
          <nav className="flex-1 py-2">
            {[
              ...(config?.training_enabled ? [{ to: "/entrainement", label: "ENTRAÎNEMENT", icon: "fitness_center", end: true }] : []),
              { to: "/patineurs", label: "PATINEURS", icon: "people", end: false },
              { to: "/competitions", label: "COMPÉTITIONS", icon: "emoji_events", end: false },
            ].map(({ to, label, icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                onClick={closeSidebar}
                className={({ isActive }) =>
                  isActive
                    ? "bg-white text-primary shadow-sm rounded-xl mx-2 my-0.5 px-4 py-3 font-bold flex items-center gap-3"
                    : "text-on-surface-variant hover:bg-surface-container rounded-xl mx-2 my-0.5 px-4 py-3 flex items-center gap-3 transition-colors"
                }
              >
                <span className="material-symbols-outlined text-xl">{icon}</span>
                <span className="text-[11px] font-bold uppercase tracking-wider">{label}</span>
              </NavLink>
            ))}
          </nav>
        ) : (
```

- [ ] **Step 4: Conditionally register training routes**

For the coach routes block (lines 261-269), wrap the training routes:

```tsx
            ) : user?.role === "coach" ? (
              <>
                {config?.training_enabled && (
                  <>
                    <Route path="/entrainement" element={<TrainingPage />} />
                    <Route path="/entrainement/patineurs/:id" element={<SkaterTrainingPage />} />
                  </>
                )}
                <Route path="/patineurs" element={<SkaterBrowserPage />} />
                <Route path="/patineurs/:id/analyse" element={<SkaterAnalyticsPage />} />
                <Route path="/competitions" element={<CompetitionsPage />} />
                <Route path="/competitions/:id" element={<CompetitionPage />} />
                <Route path="/profil" element={<ProfilePage />} />
                <Route path="*" element={<Navigate to={config?.training_enabled ? "/entrainement" : "/patineurs"} replace />} />
              </>
```

For the admin/reader routes block (lines 271-293), wrap similarly:

```tsx
              <>
                <Route path="/" element={<HomePage />} />
                <Route path="/competitions/:id" element={<CompetitionPage />} />
                <Route path="/competitions" element={<CompetitionsPage />} />
                <Route path="/patineurs" element={<SkaterBrowserPage />} />
                <Route path="/patineurs/:id/analyse" element={<SkaterAnalyticsPage />} />
                <Route path="/club/saison" element={<StatsPage />} />
                <Route path="/club/competition" element={<ClubCompetitionPage />} />
                <Route path="/club" element={<Navigate to="/club/saison" replace />} />
                <Route path="/stats" element={<Navigate to="/club/saison" replace />} />
                {config?.training_enabled && (
                  <>
                    <Route path="/entrainement" element={<TrainingPage />} />
                    <Route path="/entrainement/patineurs/:id" element={<SkaterTrainingPage />} />
                  </>
                )}
                <Route
                  path="/settings"
                  element={
                    <ProtectedRoute requiredRole="admin">
                      <SettingsPage />
                    </ProtectedRoute>
                  }
                />
                <Route path="/profil" element={<ProfilePage />} />
              </>
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat: hide training nav and routes when module disabled"
```

---

### Task 6: Frontend — Masquer l'onglet Entraînement dans la page patineur

**Files:**
- Modify: `frontend/src/pages/SkaterAnalyticsPage.tsx`

- [ ] **Step 1: Read `training_enabled` from config query**

Add a config query at the top of the component (near the other queries):

```typescript
const { data: config } = useQuery({
  queryKey: ["config"],
  queryFn: api.config.get,
  staleTime: Infinity,
});
```

- [ ] **Step 2: Gate `showTrainingTab` on `config.training_enabled`**

Change the `showTrainingTab` logic (line 173-175) from:

```typescript
const showTrainingTab = user?.role === "skater" || (
  (user?.role === "admin" || user?.role === "coach") && skater?.training_tracked
);
```

to:

```typescript
const showTrainingTab = config?.training_enabled && (
  user?.role === "skater" || (
    (user?.role === "admin" || user?.role === "coach") && skater?.training_tracked
  )
);
```

- [ ] **Step 3: Hide the "Suivre" toggle button when module disabled**

Find the toggle button (around line 565) that calls `toggleTrainingTracked.mutate()`. Wrap it with a condition on `config?.training_enabled`. The button already checks `skater?.training_tracked` for styling, but the entire button should be hidden when the module is off:

Find:
```tsx
              <button
                onClick={() => toggleTrainingTracked.mutate()}
                disabled={toggleTrainingTracked.isPending}
```

Wrap the button in: `{config?.training_enabled && ( ... )}` so the entire `<button>` element is conditionally rendered.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/SkaterAnalyticsPage.tsx
git commit -m "feat: hide training tab in skater page when module disabled"
```

---

### Task 7: Frontend — Toggle dans les paramètres + masquer l'onglet Entraînement

**Files:**
- Modify: `frontend/src/pages/SettingsPage.tsx`

- [ ] **Step 1: Read `training_enabled` from config**

The SettingsPage already uses `useQueryClient`. Add a config query:

```typescript
const { data: config } = useQuery({
  queryKey: ["config"],
  queryFn: api.config.get,
  staleTime: Infinity,
});
```

- [ ] **Step 2: Add toggle mutation**

```typescript
const toggleTrainingModule = useMutation({
  mutationFn: (enabled: boolean) => api.config.update({ training_enabled: enabled }),
  onSuccess: () => {
    qc.invalidateQueries({ queryKey: ["config"] });
  },
});
```

- [ ] **Step 3: Hide the "Entraînement" tab when module disabled**

Find the tab button for "Entraînement" (around line 410-419). Wrap it:

```tsx
{config?.training_enabled && (
  <button
    onClick={() => setActiveTab("training")}
    className={`px-5 py-2 text-sm font-semibold transition-colors border-b-2 ${
      activeTab === "training"
        ? "text-primary border-primary"
        : "text-on-surface-variant border-transparent hover:text-on-surface"
    }`}
  >
    Entraînement
  </button>
)}
```

Also, if the active tab is "training" but the module gets disabled, reset to "general". Add an effect:

```typescript
useEffect(() => {
  if (activeTab === "training" && !config?.training_enabled) {
    setActiveTab("general");
  }
}, [config?.training_enabled, activeTab]);
```

- [ ] **Step 4: Add toggle switch in the "Général" tab**

In the "Général" tab content (inside `{activeTab === "general" && ( ... )}`), add a new section at the end (before the closing `</div>` of the general tab), after the last `<section>`:

```tsx
        {/* Module entraînement toggle */}
        <section className="bg-surface-container-lowest rounded-2xl p-6 shadow-arctic">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="font-headline font-bold text-on-surface text-base">
                Module entraînement
              </h2>
              <p className="text-sm text-on-surface-variant mt-1">
                Active le suivi d'entraînement des patineurs (retours hebdomadaires, défis, incidents)
              </p>
            </div>
            <button
              onClick={() => toggleTrainingModule.mutate(!config?.training_enabled)}
              disabled={toggleTrainingModule.isPending}
              className={`relative inline-flex h-7 w-12 items-center rounded-full transition-colors ${
                config?.training_enabled ? "bg-primary" : "bg-on-surface/20"
              }`}
            >
              <span
                className={`inline-block h-5 w-5 rounded-full bg-white shadow-sm transition-transform ${
                  config?.training_enabled ? "translate-x-6" : "translate-x-1"
                }`}
              />
            </button>
          </div>
        </section>
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/SettingsPage.tsx
git commit -m "feat: add training module toggle in settings"
```

---

### Task 8: Vérification end-to-end

- [ ] **Step 1: Run backend tests**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest -v --tb=short 2>&1 | tail -30`
Expected: all tests pass (including the new `test_training_toggle.py`)

- [ ] **Step 2: Start dev servers and verify manually**

Run: `cd frontend && PATH="/opt/homebrew/bin:$PATH" npm run dev` and `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`

Verify:
1. Login as admin → Paramètres → "Module entraînement" toggle is visible in "Général" tab → defaults to OFF
2. Nav does NOT show "ENTRAÎNEMENT" link
3. Open a skater → no "Entraînement" tab, no "Suivre" button
4. Settings → no "Entraînement" tab
5. Toggle ON → "ENTRAÎNEMENT" appears in nav
6. Settings → "Entraînement" tab now visible
7. Open a skater → "Suivre" button reappears
8. Refresh the page → state persists

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat: training module is now an opt-in setting in admin"
```
