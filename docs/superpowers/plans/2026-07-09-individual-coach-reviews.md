# Retours d'entraînement individuels par entraîneur — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permettre à chaque entraîneur de rédiger ses retours hebdomadaires individuellement pour un même patineur, et rendre le nom de l'entraîneur auteur visible du patineur sur chaque retour et chaque incident.

**Architecture:** Le modèle `WeeklyReview` porte déjà un `coach_id`. On élargit sa contrainte d'unicité de `(skater_id, week_start)` à `(skater_id, week_start, coach_id)` (via une migration SQLite qui recrée la table, comme déjà fait pour `self_evaluations`), on change l'upsert de `create_review` pour qu'il ne touche que le retour de l'entraîneur courant, on restreint l'édition/suppression à l'auteur (+ admin), et on expose `coach_name` (le `display_name` de l'auteur) dans les réponses retours ET incidents. Côté frontend, les types gagnent `coach_name`, l'attribution d'auteur s'affiche sur chaque retour/incident (page coach + page patineur + timeline), et les boutons edit/delete ne s'affichent que pour l'auteur ou l'admin.

**Tech Stack:** Backend Litestar + SQLAlchemy async + SQLite ; tests pytest-asyncio (SQLite in-memory). Frontend React + TypeScript + Vite + Tailwind, TanStack Query.

## Global Constraints

- Tout le texte d'UI est en **français**.
- Design system « Kinetic Lens » : pas de bordures pour le sectionnement (surface layering), scores numériques en `font-mono`, icônes Material Symbols Outlined.
- La DB SQLite vit dans le conteneur backend ; les commandes de test s'exécutent via `uv`. `npm`/`uv` ne sont pas sur le PATH par défaut — préfixer avec `PATH="/opt/homebrew/bin:$PATH"`.
- SQLite ne supporte pas `ALTER TABLE DROP CONSTRAINT` : toute suppression de contrainte passe par recréation de table.
- Commandes de test backend : `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest <chemin> -v`.

---

### Task 1: Élargir la contrainte d'unicité du modèle WeeklyReview + migration

Deux entraîneurs doivent pouvoir avoir chacun leur retour pour un même patineur+semaine. On change la contrainte d'unicité et on migre les bases existantes.

**Files:**
- Modify: `backend/app/models/weekly_review.py:15-17`
- Modify: `backend/app/database.py` (fonction `_migrate_drop_constraints`, après le bloc `self_evaluations` qui finit vers la ligne 118)
- Test: `backend/tests/test_training_reviews.py`

**Interfaces:**
- Consumes: rien (première tâche).
- Produces: la contrainte `uq_review_skater_week_coach` sur `(skater_id, week_start, coach_id)`. Les tâches suivantes s'appuient sur le fait que plusieurs `WeeklyReview` peuvent coexister pour un même `(skater_id, week_start)` avec des `coach_id` différents.

- [ ] **Step 1: Écrire le test qui échoue**

Ajouter en haut de `backend/tests/test_training_reviews.py` un fixture pour un **second** coach (après le fixture `coach_and_skater`, avant `skater_parent`) :

```python
@pytest.fixture
async def second_coach(db_session, coach_and_skater):
    _, _, skater = coach_and_skater
    coach2 = User(
        email="coach2@test.com",
        password_hash=hash_password("coach2pass1"),
        display_name="Second Coach",
        role="coach",
    )
    db_session.add(coach2)
    await db_session.commit()
    await db_session.refresh(coach2)
    token = create_access_token(user_id=coach2.id, role=coach2.role)
    return coach2, token, skater
```

Puis ajouter le test à la fin du fichier :

```python
async def test_two_coaches_coexist_same_week(client, coach_and_skater, second_coach):
    _, token1, skater = coach_and_skater
    _, token2, _ = second_coach
    body = {
        "skater_id": skater.id,
        "week_start": "2026-03-23",
        "attendance": "3/4",
        "engagement": 4,
        "progression": 3,
        "attitude": 5,
        "strengths": "Bon",
        "improvements": "Mieux",
        "visible_to_skater": True,
    }
    r1 = await client.post("/api/training/reviews", json=body,
                           headers={"Authorization": f"Bearer {token1}"})
    r2 = await client.post("/api/training/reviews", json=body,
                           headers={"Authorization": f"Bearer {token2}"})
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] != r2.json()["id"]

    listing = await client.get(f"/api/training/reviews?skater_id={skater.id}",
                               headers={"Authorization": f"Bearer {token1}"})
    assert listing.status_code == 200
    assert len(listing.json()) == 2
```

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_training_reviews.py::test_two_coaches_coexist_same_week -v`
Expected: FAIL — le second POST déclenche l'upsert (écrasement), donc `listing` contient 1 retour, pas 2 (l'assert `== 2` échoue), et/ou les deux ids sont égaux.

- [ ] **Step 3: Changer la contrainte du modèle**

Dans `backend/app/models/weekly_review.py`, remplacer :

```python
    __table_args__ = (
        UniqueConstraint("skater_id", "week_start", name="uq_review_skater_week"),
    )
```

par :

```python
    __table_args__ = (
        UniqueConstraint("skater_id", "week_start", "coach_id", name="uq_review_skater_week_coach"),
    )
```

- [ ] **Step 4: Ajouter la migration**

Dans `backend/app/database.py`, à la fin de la fonction `_migrate_drop_constraints` (juste avant le `return` implicite / après le bloc `try/except` de `self_evaluations`), ajouter un second bloc, en suivant exactement le pattern existant :

```python
    # Widen weekly_reviews unique constraint to include coach_id
    try:
        result = await conn.execute(
            text("SELECT sql FROM sqlite_master WHERE type='table' AND name='weekly_reviews'")
        )
        row = result.fetchone()
        sql = row[0] or "" if row else ""
        if "uq_review_skater_week" in sql and "uq_review_skater_week_coach" not in sql:
            logger.info("Recreating weekly_reviews table to widen unique constraint with coach_id")
            await conn.execute(text("ALTER TABLE weekly_reviews RENAME TO _weekly_reviews_old"))
            await conn.execute(text("""
                CREATE TABLE weekly_reviews (
                    id INTEGER NOT NULL PRIMARY KEY,
                    skater_id INTEGER NOT NULL,
                    coach_id VARCHAR(36) NOT NULL,
                    week_start DATE NOT NULL,
                    attendance VARCHAR(20) NOT NULL,
                    engagement INTEGER NOT NULL,
                    progression INTEGER NOT NULL,
                    attitude INTEGER NOT NULL,
                    strengths TEXT NOT NULL,
                    improvements TEXT NOT NULL,
                    visible_to_skater BOOLEAN NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    CONSTRAINT uq_review_skater_week_coach UNIQUE (skater_id, week_start, coach_id),
                    FOREIGN KEY(skater_id) REFERENCES skaters (id) ON DELETE CASCADE,
                    FOREIGN KEY(coach_id) REFERENCES users (id) ON DELETE CASCADE
                )
            """))
            await conn.execute(text("""
                INSERT INTO weekly_reviews
                SELECT * FROM _weekly_reviews_old
            """))
            await conn.execute(text("DROP TABLE _weekly_reviews_old"))
            logger.info("Widened unique constraint to uq_review_skater_week_coach")
    except Exception:
        logger.exception("Failed to widen unique constraint on weekly_reviews")
```

Note : la détection `"uq_review_skater_week" in sql and "uq_review_skater_week_coach" not in sql` évite de re-migrer une base déjà à jour (le nouveau nom contient l'ancien comme sous-chaîne, d'où la seconde condition).

- [ ] **Step 5: Lancer le test — toujours en échec, mais pour la bonne raison**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_training_reviews.py::test_two_coaches_coexist_same_week -v`
Expected: encore FAIL — la contrainte autorise maintenant deux lignes, mais l'upsert de `create_review` (Task 2) écrase toujours le retour du premier coach. Le fix complet arrive en Task 2. (Si l'erreur devient un `IntegrityError` disparu et que le test passe déjà parce que l'upsert ne matche plus, tant mieux — mais on ne compte pas dessus ici.)

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/weekly_review.py backend/app/database.py backend/tests/test_training_reviews.py
git commit -m "feat: widen weekly review unique constraint to include coach"
```

---

### Task 2: Upsert par entraîneur + édition/suppression réservées à l'auteur

`create_review` ne doit mettre à jour que le retour de l'entraîneur courant ; `update_review`/`delete_review` interdisent à un coach de toucher le retour d'un autre coach.

**Files:**
- Modify: `backend/app/routes/training.py:129-204` (`create_review`, `update_review`, `delete_review`)
- Test: `backend/tests/test_training_reviews.py`

**Interfaces:**
- Consumes: la contrainte `uq_review_skater_week_coach` (Task 1) ; les fixtures `coach_and_skater`, `second_coach` (Task 1).
- Produces: `create_review` fait un upsert filtré par `coach_id == state["user_id"]` ; `update_review`/`delete_review` lèvent `PermissionDeniedException` si `role == "coach"` et `review.coach_id != state["user_id"]`. `update_review` ne réécrit plus `coach_id`.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à la fin de `backend/tests/test_training_reviews.py` :

```python
async def test_coach_reupsert_only_own_review(client, coach_and_skater, second_coach):
    _, token1, skater = coach_and_skater
    _, token2, _ = second_coach
    body = {
        "skater_id": skater.id, "week_start": "2026-03-23", "attendance": "3/4",
        "engagement": 4, "progression": 3, "attitude": 5,
        "strengths": "Coach1", "improvements": "", "visible_to_skater": True,
    }
    await client.post("/api/training/reviews", json=body,
                      headers={"Authorization": f"Bearer {token1}"})
    await client.post("/api/training/reviews", json={**body, "strengths": "Coach2"},
                      headers={"Authorization": f"Bearer {token2}"})
    # Coach1 re-enregistre -> met à jour SON retour, sans toucher celui de Coach2
    await client.post("/api/training/reviews", json={**body, "engagement": 2},
                      headers={"Authorization": f"Bearer {token1}"})
    listing = (await client.get(f"/api/training/reviews?skater_id={skater.id}",
               headers={"Authorization": f"Bearer {token1}"})).json()
    assert len(listing) == 2
    by_text = {r["strengths"]: r for r in listing}
    assert by_text["Coach1"]["engagement"] == 2
    assert by_text["Coach2"]["engagement"] == 4


async def test_coach_cannot_edit_other_coach_review(client, coach_and_skater, second_coach):
    _, token1, skater = coach_and_skater
    _, token2, _ = second_coach
    created = (await client.post("/api/training/reviews", json={
        "skater_id": skater.id, "week_start": "2026-03-23", "attendance": "3/4",
        "engagement": 4, "progression": 3, "attitude": 5,
        "strengths": "Bon", "improvements": "", "visible_to_skater": True,
    }, headers={"Authorization": f"Bearer {token1}"})).json()
    resp = await client.put(f"/api/training/reviews/{created['id']}",
        json={"engagement": 1},
        headers={"Authorization": f"Bearer {token2}"})
    assert resp.status_code == 403


async def test_coach_cannot_delete_other_coach_review(client, coach_and_skater, second_coach):
    _, token1, skater = coach_and_skater
    _, token2, _ = second_coach
    created = (await client.post("/api/training/reviews", json={
        "skater_id": skater.id, "week_start": "2026-03-23", "attendance": "3/4",
        "engagement": 4, "progression": 3, "attitude": 5,
        "strengths": "Bon", "improvements": "", "visible_to_skater": True,
    }, headers={"Authorization": f"Bearer {token1}"})).json()
    resp = await client.delete(f"/api/training/reviews/{created['id']}",
        headers={"Authorization": f"Bearer {token2}"})
    assert resp.status_code == 403


async def test_admin_can_edit_any_review(client, coach_and_skater, admin_token):
    _, token1, skater = coach_and_skater
    created = (await client.post("/api/training/reviews", json={
        "skater_id": skater.id, "week_start": "2026-03-23", "attendance": "3/4",
        "engagement": 4, "progression": 3, "attitude": 5,
        "strengths": "Bon", "improvements": "", "visible_to_skater": True,
    }, headers={"Authorization": f"Bearer {token1}"})).json()
    resp = await client.put(f"/api/training/reviews/{created['id']}",
        json={"engagement": 1},
        headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert resp.json()["engagement"] == 1
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_training_reviews.py -k "reupsert or cannot_edit or cannot_delete or admin_can_edit" -v`
Expected: FAIL — `test_coach_reupsert_only_own_review` échoue (l'upsert écrase le retour de Coach2) ; `test_coach_cannot_edit/delete...` échouent (200/204 au lieu de 403, car « any coach can edit »).

- [ ] **Step 3: Corriger `create_review` (upsert par coach)**

Dans `backend/app/routes/training.py`, remplacer le bloc de recherche `existing` de `create_review` (lignes ~137-142) :

```python
    # Upsert: if a review already exists for this skater+week, update it
    existing = (await session.execute(
        select(WeeklyReview).where(
            WeeklyReview.skater_id == data["skater_id"],
            WeeklyReview.week_start == week_start,
        )
    )).scalar_one_or_none()
```

par (filtrer aussi sur le coach courant) :

```python
    # Upsert per coach: only the current coach's own review for this skater+week
    existing = (await session.execute(
        select(WeeklyReview).where(
            WeeklyReview.skater_id == data["skater_id"],
            WeeklyReview.week_start == week_start,
            WeeklyReview.coach_id == state["user_id"],
        )
    )).scalar_one_or_none()
```

Dans la branche `if existing:` juste en dessous, **supprimer** la ligne qui réécrit le coach (elle vaut déjà `state["user_id"]` par construction) :

```python
        existing.coach_id = state["user_id"]
```

- [ ] **Step 4: Corriger `update_review` (auteur seulement, ne pas réécrire coach_id)**

Dans `update_review`, après le chargement du review et avant la boucle `for field in (...)`, ajouter le contrôle d'accès :

```python
    if role == "coach" and review.coach_id != state["user_id"]:
        raise PermissionDeniedException("You can only edit your own reviews")
```

Puis **supprimer** les deux lignes qui réécrivent le coach :

```python
    # Per spec: any coach can edit any review, coach_id updates to current editor
    review.coach_id = state["user_id"]
```

- [ ] **Step 5: Confirmer `delete_review`**

`delete_review` a déjà la règle correcte (lignes ~219-220 : `if role == "coach" and review.coach_id != state["user_id"]: raise PermissionDeniedException(...)`). Aucun changement nécessaire — vérifier visuellement que ce bloc est présent.

- [ ] **Step 6: Lancer les tests — doivent passer**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_training_reviews.py -v`
Expected: PASS pour tous, y compris `test_two_coaches_coexist_same_week` (Task 1) et les tests existants.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routes/training.py backend/tests/test_training_reviews.py
git commit -m "feat: per-coach review upsert, author-only edit/delete"
```

---

### Task 3: Exposer coach_name dans les retours et incidents

Le patineur doit voir le nom de l'auteur. On ajoute `coach_name` (le `display_name` de l'auteur) aux dicts retours et incidents, en évitant les N+1 sur les endpoints liste/timeline.

**Files:**
- Modify: `backend/app/routes/training.py` (`_review_to_dict`, `_incident_to_dict`, `list_reviews`, `get_review`, `create_review`, `update_review`, `list_incidents`, `get_incident`, `create_incident`, `update_incident`, `get_timeline`)
- Test: `backend/tests/test_training_reviews.py`, `backend/tests/test_training_incidents.py`

**Interfaces:**
- Consumes: le modèle `User` (`app.models.user.User`) avec le champ `display_name`.
- Produces: `_review_to_dict(r, coach_name=None)` et `_incident_to_dict(i, coach_name=None)` incluent la clé `"coach_name"` (str ou None). Un helper `_coach_names(session, ids) -> dict[str, str]` mappe `coach_id -> display_name`.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à la fin de `backend/tests/test_training_reviews.py` :

```python
async def test_review_includes_coach_name(client, coach_and_skater):
    coach, token, skater = coach_and_skater
    created = (await client.post("/api/training/reviews", json={
        "skater_id": skater.id, "week_start": "2026-03-23", "attendance": "3/4",
        "engagement": 4, "progression": 3, "attitude": 5,
        "strengths": "Bon", "improvements": "", "visible_to_skater": True,
    }, headers={"Authorization": f"Bearer {token}"})).json()
    assert created["coach_name"] == coach.display_name

    listing = (await client.get(f"/api/training/reviews?skater_id={skater.id}",
               headers={"Authorization": f"Bearer {token}"})).json()
    assert listing[0]["coach_name"] == coach.display_name

    one = (await client.get(f"/api/training/reviews/{created['id']}",
           headers={"Authorization": f"Bearer {token}"})).json()
    assert one["coach_name"] == coach.display_name
```

Ajouter à la fin de `backend/tests/test_training_incidents.py` (importer ce qu'il faut si absent — voir le haut du fichier existant qui définit déjà un fixture coach/skater ; réutiliser le fixture existant de ce fichier) :

```python
async def test_incident_includes_coach_name(client, coach_and_skater):
    coach, token, skater = coach_and_skater
    created = (await client.post("/api/training/incidents", json={
        "skater_id": skater.id, "date": "2026-03-23",
        "incident_type": "behavior", "description": "Retard",
        "visible_to_skater": True,
    }, headers={"Authorization": f"Bearer {token}"})).json()
    assert created["coach_name"] == coach.display_name

    listing = (await client.get(f"/api/training/incidents?skater_id={skater.id}",
               headers={"Authorization": f"Bearer {token}"})).json()
    assert listing[0]["coach_name"] == coach.display_name
```

Note : `test_training_incidents.py` définit déjà un fixture nommé `coach_and_skater` (identique en forme à celui de `test_training_reviews.py`) — le test ci-dessus l'utilise directement, aucune adaptation nécessaire.

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_training_reviews.py::test_review_includes_coach_name tests/test_training_incidents.py::test_incident_includes_coach_name -v`
Expected: FAIL avec `KeyError: 'coach_name'`.

- [ ] **Step 3: Ajouter l'import User et le helper `_coach_names`**

En haut de `backend/app/routes/training.py`, ajouter l'import (à côté des autres imports de modèles) :

```python
from app.models.user import User
```

Ajouter le helper juste après les imports (avant `_snap_to_monday`) :

```python
async def _coach_names(session: AsyncSession, coach_ids: set[str]) -> dict[str, str]:
    """Map coach_id -> display_name for a set of ids, in one query."""
    if not coach_ids:
        return {}
    rows = (await session.execute(
        select(User.id, User.display_name).where(User.id.in_(coach_ids))
    )).all()
    return {row[0]: row[1] for row in rows}
```

- [ ] **Step 4: Ajouter `coach_name` aux fonctions `_to_dict`**

Modifier la signature et le corps de `_review_to_dict` :

```python
def _review_to_dict(r: WeeklyReview, coach_name: str | None = None) -> dict:
    return {
        "id": r.id,
        "skater_id": r.skater_id,
        "coach_id": r.coach_id,
        "coach_name": coach_name,
        "week_start": r.week_start.isoformat(),
        "attendance": r.attendance,
        "engagement": r.engagement,
        "progression": r.progression,
        "attitude": r.attitude,
        "strengths": r.strengths,
        "improvements": r.improvements,
        "visible_to_skater": r.visible_to_skater,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }
```

Modifier de même `_incident_to_dict` :

```python
def _incident_to_dict(i: Incident, coach_name: str | None = None) -> dict:
    return {
        "id": i.id,
        "skater_id": i.skater_id,
        "coach_id": i.coach_id,
        "coach_name": coach_name,
        "date": i.date.isoformat(),
        "incident_type": i.incident_type,
        "description": i.description,
        "visible_to_skater": i.visible_to_skater,
        "created_at": i.created_at.isoformat() if i.created_at else None,
        "updated_at": i.updated_at.isoformat() if i.updated_at else None,
    }
```

- [ ] **Step 5: Renseigner `coach_name` dans les endpoints liste (batch)**

Dans `list_reviews`, remplacer la ligne finale :

```python
    result = await session.execute(stmt)
    return [_review_to_dict(r) for r in result.scalars().all()]
```

par :

```python
    rows = (await session.execute(stmt)).scalars().all()
    names = await _coach_names(session, {r.coach_id for r in rows})
    return [_review_to_dict(r, names.get(r.coach_id)) for r in rows]
```

Dans `list_incidents`, remplacer de même :

```python
    result = await session.execute(stmt)
    return [_incident_to_dict(i) for i in result.scalars().all()]
```

par :

```python
    rows = (await session.execute(stmt)).scalars().all()
    names = await _coach_names(session, {i.coach_id for i in rows})
    return [_incident_to_dict(i, names.get(i.coach_id)) for i in rows]
```

- [ ] **Step 6: Renseigner `coach_name` dans les endpoints unitaires**

Pour `get_review`, `create_review` (les deux `return` : branche `existing` et création), et `update_review` : remplacer chaque `return _review_to_dict(<var>)` par une résolution du nom via `session.get(User, ...)`. Exemple pour `get_review` :

```python
    coach = await session.get(User, review.coach_id)
    return _review_to_dict(review, coach.display_name if coach else None)
```

Appliquer le même motif dans `create_review` (remplacer `return _review_to_dict(existing)` et `return _review_to_dict(review)`) et dans `update_review` (`return _review_to_dict(review)`), en utilisant la variable locale correspondante (`existing` ou `review`).

Pour les incidents, appliquer le même motif dans `get_incident`, `create_incident`, `update_incident` — remplacer `return _incident_to_dict(<var>)` par :

```python
    coach = await session.get(User, <var>.coach_id)
    return _incident_to_dict(<var>, coach.display_name if coach else None)
```

- [ ] **Step 7: Renseigner `coach_name` dans le timeline**

Dans `get_timeline`, après avoir chargé `reviews` et `incidents` (avant la boucle `timeline = []`), résoudre les noms en un batch :

```python
    coach_ids = {r.coach_id for r in reviews} | {i.coach_id for i in incidents}
    names = await _coach_names(session, coach_ids)
```

Puis dans les deux boucles de construction, passer le nom :

```python
    for r in reviews:
        entry = _review_to_dict(r, names.get(r.coach_id))
        entry["type"] = "review"
        entry["sort_date"] = r.week_start.isoformat()
        timeline.append(entry)
    for i in incidents:
        entry = _incident_to_dict(i, names.get(i.coach_id))
        entry["type"] = "incident"
        entry["sort_date"] = i.date.isoformat()
        timeline.append(entry)
```

- [ ] **Step 8: Lancer les tests — doivent passer**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest tests/test_training_reviews.py tests/test_training_incidents.py tests/test_training_timeline.py -v`
Expected: PASS pour tous.

- [ ] **Step 9: Lancer toute la suite backend**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest -v`
Expected: PASS (aucune régression).

- [ ] **Step 10: Commit**

```bash
git add backend/app/routes/training.py backend/tests/test_training_reviews.py backend/tests/test_training_incidents.py
git commit -m "feat: expose coach_name on reviews and incidents"
```

---

### Task 4: Types frontend + attribution d'auteur (page coach) + gating edit/delete

Ajouter `coach_name` aux types, l'afficher sur chaque retour/incident de la page coach, et n'afficher edit/delete que pour l'auteur ou l'admin.

**Files:**
- Modify: `frontend/src/api/client.ts:479-539` (interfaces `WeeklyReview`, `TrainingIncident`)
- Modify: `frontend/src/pages/SkaterTrainingPage.tsx` (`ReviewCard`, `ReviewDetailModal`, `ReviewRow`, `IncidentDetailModal`, câblage `onEdit` dans le composant page + timeline)

**Interfaces:**
- Consumes: le champ `coach_name` renvoyé par le backend (Task 3) ; `AuthUser` (`{ id, role, ... }`) via `useAuth()` de `../auth/AuthContext`.
- Produces: attribution d'auteur affichée ; boutons edit passés conditionnellement (`onEdit` undefined si le viewer n'est ni l'auteur ni admin).

- [ ] **Step 1: Ajouter `coach_name` aux types**

Dans `frontend/src/api/client.ts`, interface `WeeklyReview` (après `coach_id: string;`) ajouter :

```typescript
  coach_name: string | null;
```

Interface `TrainingIncident` (après `coach_id: string;`) ajouter de même :

```typescript
  coach_name: string | null;
```

- [ ] **Step 2: Afficher l'auteur sur `ReviewCard`**

Dans `SkaterTrainingPage.tsx`, dans `ReviewCard`, sous le `<h4>` « Semaine du … », ajouter une ligne d'attribution. Remplacer le `<h4>` :

```tsx
        <h4 className="font-headline font-bold text-on-surface text-sm">
          Semaine du {weekDate}
        </h4>
```

par un bloc titre + auteur :

```tsx
        <div>
          <h4 className="font-headline font-bold text-on-surface text-sm">
            Semaine du {weekDate}
          </h4>
          {review.coach_name && (
            <p className="text-[11px] text-on-surface-variant">par {review.coach_name}</p>
          )}
        </div>
```

- [ ] **Step 3: Afficher l'auteur sur `ReviewDetailModal`**

Dans `ReviewDetailModal`, remplacer le `<h3>` « Semaine du … » par titre + auteur :

```tsx
          <div>
            <h3 className="font-headline font-bold text-on-surface text-lg">
              Semaine du {weekDate}
            </h3>
            {review.coach_name && (
              <p className="text-xs text-on-surface-variant">par {review.coach_name}</p>
            )}
          </div>
```

- [ ] **Step 4: Afficher l'auteur sur `ReviewRow`**

Dans `ReviewRow`, après le `<span>` de la date (`{weekDate}`) et avant le bloc des dots, ajouter le nom (tronqué, discret). Insérer juste après :

```tsx
      <span className="text-xs text-on-surface-variant w-16 shrink-0">{weekDate}</span>
```

la ligne :

```tsx
      {review.coach_name && (
        <span className="text-[11px] text-on-surface-variant truncate max-w-[6rem] shrink-0">{review.coach_name}</span>
      )}
```

- [ ] **Step 5: Afficher l'auteur sur `IncidentDetailModal`**

Dans `IncidentDetailModal`, sous le `<p>` de date (`{dateStr}`), ajouter l'auteur. Remplacer :

```tsx
        <p className="text-xs text-on-surface-variant">{dateStr}</p>
```

par :

```tsx
        <p className="text-xs text-on-surface-variant">
          {dateStr}
          {incident.coach_name && <> · par {incident.coach_name}</>}
        </p>
```

- [ ] **Step 6: Gating edit/delete par auteur (page coach)**

En haut de `SkaterTrainingPage()` (le composant par défaut), importer et lire l'utilisateur courant. Ajouter en tête du fichier l'import :

```tsx
import { useAuth } from "../auth/AuthContext";
```

Dans le corps de `SkaterTrainingPage`, après `const skaterId = Number(id);`, ajouter :

```tsx
  const { user } = useAuth();
  const canEditReview = (r: WeeklyReview) => user?.role === "admin" || user?.id === r.coach_id;
  const canEditIncident = (i: TrainingIncident) => user?.role === "admin" || user?.id === i.coach_id;
```

Puis rendre les `onEdit` conditionnels. Pour la `ReviewCard` du dernier retour (ligne ~863) :

```tsx
            <ReviewCard review={latestReview} onEdit={canEditReview(latestReview) ? () => { setEditingReview(latestReview); setShowReviewForm(true); } : undefined} />
```

Pour le `ReviewDetailModal` (bloc `{viewingReview && ...}`), passer `onEdit` seulement si autorisé :

```tsx
          onEdit={canEditReview(viewingReview) ? () => {
            setViewingReview(undefined);
            setEditingReview(viewingReview);
            setShowReviewForm(true);
          } : undefined}
```

Pour le `IncidentDetailModal` (bloc `{viewingIncident && ...}`) :

```tsx
          onEdit={canEditIncident(viewingIncident) ? () => {
            setViewingIncident(undefined);
            setEditingIncident(viewingIncident);
            setShowIncidentForm(true);
          } : undefined}
```

(Le composant `ReviewDetailModal`/`IncidentDetailModal` masque déjà le bouton edit quand `onEdit` est `undefined` — cf. `{onEdit && (...)}`.)

- [ ] **Step 7: Vérifier le build TypeScript**

Run: `cd frontend && PATH="/opt/homebrew/bin:$PATH" npm run build`
Expected: build OK, pas d'erreur TS (notamment sur `coach_name` maintenant requis dans les types).

- [ ] **Step 8: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/pages/SkaterTrainingPage.tsx
git commit -m "feat: show review/incident author and gate edit to author (coach page)"
```

---

### Task 5: Attribution d'auteur sur la page patineur (SkaterAnalyticsPage)

Le patineur consulte ses retours via `SkaterAnalyticsPage`, qui a sa **propre** modale de détail inline (elle ne réutilise PAS `ReviewDetailModal`). Afficher le nom de l'auteur sur la liste des retours et dans cette modale locale.

**Files:**
- Modify: `frontend/src/pages/SkaterAnalyticsPage.tsx` (liste des retours du sous-onglet « reviews », ~lignes 1515-1546 ; modale inline `{viewingReview && ...}`, ~lignes 1674-1679)

**Interfaces:**
- Consumes: `coach_name` sur `WeeklyReview` (Task 4, déjà dans le type).
- Produces: attribution d'auteur visible côté patineur (liste + modale locale).

- [ ] **Step 1: Afficher l'auteur dans la modale de détail locale**

Dans le bloc `{viewingReview && (...)}` (~ligne 1674), remplacer le `<h3>` titre :

```tsx
                  <h3 className="font-headline font-bold text-on-surface text-lg">
                    Semaine du {new Date(viewingReview.week_start).toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" })}
                  </h3>
```

par titre + auteur :

```tsx
                  <div>
                    <h3 className="font-headline font-bold text-on-surface text-lg">
                      Semaine du {new Date(viewingReview.week_start).toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" })}
                    </h3>
                    {viewingReview.coach_name && (
                      <p className="text-xs text-on-surface-variant">par {viewingReview.coach_name}</p>
                    )}
                  </div>
```

- [ ] **Step 2: Afficher l'auteur dans la liste des retours**

Dans le rendu du sous-onglet `reviews` (le `.map((r) => { ... })` vers la ligne 1516), ajouter le nom d'auteur. Après le `<span>` de la date :

```tsx
                        <span className="text-xs text-on-surface-variant w-16 shrink-0">{weekDate}</span>
```

insérer :

```tsx
                        {r.coach_name && (
                          <span className="text-[11px] text-on-surface-variant truncate max-w-[6rem] shrink-0">{r.coach_name}</span>
                        )}
```

- [ ] **Step 3: Vérifier le build TypeScript**

Run: `cd frontend && PATH="/opt/homebrew/bin:$PATH" npm run build`
Expected: build OK.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/SkaterAnalyticsPage.tsx
git commit -m "feat: show review author on skater-facing page"
```

---

### Task 6: Vérification end-to-end

Confirmer le comportement complet en conditions réelles (pas seulement les tests unitaires).

**Files:** aucun (vérification).

- [ ] **Step 1: Lancer toute la suite backend**

Run: `cd backend && PATH="/opt/homebrew/bin:$PATH" uv run pytest -v`
Expected: PASS, aucune régression.

- [ ] **Step 2: Vérifier le build frontend**

Run: `cd frontend && PATH="/opt/homebrew/bin:$PATH" npm run build`
Expected: build OK.

- [ ] **Step 3: Vérification fonctionnelle via l'app (skill `verify`)**

Invoquer la skill `verify` pour piloter le flux : avec deux comptes entraîneur, créer chacun un retour pour le même patineur+semaine → les deux coexistent ; le nom de chaque entraîneur apparaît sur son retour côté patineur ; un entraîneur ne voit pas de bouton d'édition sur le retour de l'autre. Observer le comportement réel, pas seulement les tests.

- [ ] **Step 4: Commit final (si des ajustements ont été nécessaires)**

```bash
git add -A
git commit -m "chore: end-to-end verification for per-coach reviews"
```

---

## Notes d'implémentation

- Le fixture `coach_and_skater` (dans `test_training_reviews.py`) crée un coach `coach@test.com` ; le fixture `second_coach` (Task 1) crée `coach2@test.com`. Ne pas confondre avec le fixture session-level `coach_user`/`coach_token` de `conftest.py` (même email `coach@test.com`) — utiliser ceux du fichier de test pour ces scénarios.
- La migration de contrainte est idempotente grâce à la double condition de détection ; elle ne s'exécute qu'une fois par base.
- `coach_name` est nullable (str | None) : si l'utilisateur auteur a été supprimé (le `ON DELETE CASCADE` supprime en fait le retour, donc ce cas est théorique), l'UI masque simplement l'attribution via `{coach_name && ...}`.
