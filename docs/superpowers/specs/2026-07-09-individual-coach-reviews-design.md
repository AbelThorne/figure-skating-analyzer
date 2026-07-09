# Retours d'entraînement individuels par entraîneur

**Date** : 2026-07-09
**Statut** : conçu, en attente de validation

## Contexte & objectif

Dans le module de suivi d'entraînement, les retours hebdomadaires (`WeeklyReview`)
et les incidents (`Incident`) portent déjà un `coach_id` (auteur), mais :

- Le nom de l'entraîneur n'est **jamais affiché** au patineur.
- Une contrainte unique `(skater_id, week_start)` + un upsert dans `create_review`
  fait qu'**un seul retour hebdomadaire peut exister par patineur+semaine** :
  si un second entraîneur enregistre, il **écrase** le retour du premier et
  remplace le `coach_id`.

Objectif : permettre à **chaque entraîneur de faire ses retours individuellement**,
et rendre le **nom de l'entraîneur auteur visible du patineur** sur chaque retour
et chaque incident.

## Décisions

1. **Un retour par entraîneur et par semaine** : plusieurs retours peuvent coexister
   pour un même patineur+semaine, un par entraîneur. Le patineur les voit tous,
   chacun attribué à son auteur.
2. **Édition/suppression réservées à l'auteur** (+ admin) pour les retours.
   (Les incidents ont déjà cette règle.)
3. **Nom de l'auteur affiché sur chaque retour ET chaque incident** — cartes,
   modale de détail, et timeline — côté patineur comme côté entraîneur.
4. La demande est étendue aux **incidents** pour cohérence.

## Backend

### Modèle (`models/weekly_review.py`)

La contrainte d'unicité passe de :

```python
UniqueConstraint("skater_id", "week_start", name="uq_review_skater_week")
```

à :

```python
UniqueConstraint("skater_id", "week_start", "coach_id", name="uq_review_skater_week_coach")
```

Le champ `coach_id` existe déjà — aucun ajout de colonne. Les incidents n'ont pas
de contrainte unique, donc aucun changement de modèle côté incidents.

### Migration (`database.py`, `_migrate_drop_constraints`)

SQLite ne supporte pas `ALTER TABLE DROP CONSTRAINT`. On reproduit le pattern déjà
utilisé pour `self_evaluations` : détecter l'ancienne contrainte via
`sqlite_master`, puis rename → create (nouvelle contrainte à 3 colonnes) → copy →
drop de l'ancienne table. Les données existantes sont préservées.

Détection : `SELECT sql FROM sqlite_master WHERE type='table' AND name='weekly_reviews'`,
et si le SQL contient `uq_review_skater_week` **sans** `coach` (l'ancienne
signature), on recrée la table. La nouvelle table reprend toutes les colonnes
actuelles de `WeeklyReview` avec la contrainte `uq_review_skater_week_coach`.

### Routes (`routes/training.py`)

**`create_review`** — l'upsert « par (skater, semaine) » devient un upsert
« par (skater, semaine, coach courant) » :

- On cherche un `WeeklyReview` existant sur `skater_id == data["skater_id"]`
  **ET** `week_start == week_start` **ET** `coach_id == state["user_id"]`.
- S'il existe, on met à jour uniquement **ce** retour (celui de l'entraîneur courant).
- Sinon, on crée un nouveau retour. Les retours des autres entraîneurs ne sont
  jamais touchés.

**`update_review` / `delete_review`** — un `coach` ne peut agir que sur ses propres
retours :

- `update_review` : si `role == "coach"` et `review.coach_id != state["user_id"]`
  → `PermissionDeniedException`. L'`admin` peut éditer tous les retours.
- On **retire** la logique actuelle « any coach can edit any review, coach_id
  updates to current editor » : l'auteur (`coach_id`) reste stable et n'est plus
  réécrit à l'édition.
- `delete_review` a déjà la bonne règle (coach ne supprime que les siens) — on la
  garde.

**Exposition du nom d'auteur** :

- `_review_to_dict` et `_incident_to_dict` ajoutent une clé `coach_name` = le
  `display_name` de l'utilisateur auteur (`coach_id → users.display_name`).
- Pour éviter les N+1 dans les endpoints liste (`list_reviews`, `list_incidents`,
  `get_timeline`), on récupère les `display_name` des coachs concernés en une
  requête et on passe le nom résolu à la fonction `_*_to_dict` (paramètre optionnel
  `coach_name`). Approche : après avoir chargé les lignes, collecter l'ensemble des
  `coach_id`, faire un `select(User.id, User.display_name).where(User.id.in_(ids))`,
  construire un dict `{id: display_name}`, puis mapper.
- Pour les endpoints unitaires (`get_review`, `get_incident`, création,
  mise à jour), on résout le seul `display_name` nécessaire par `session.get(User, coach_id)`.

Les incidents : mêmes ajustements que les retours pour `coach_name`. La règle
d'édition/suppression des incidents est déjà « auteur seulement » — inchangée.

## Frontend

### Types (`api/client.ts`)

- `WeeklyReview` : ajout de `coach_name: string`.
- `TrainingIncident` : ajout de `coach_name: string`.

### Affichage (`pages/SkaterTrainingPage.tsx` et timeline)

- `ReviewCard`, `ReviewDetailModal`, `ReviewRow` : afficher « par {coach_name} »
  (ou équivalent visuel discret) sur chaque retour.
- Les cartes/rows d'incident : afficher de même le nom de l'auteur.
- Entrée timeline (retours et incidents) : le nom d'auteur apparaît aussi.
- **Bouton edit/delete** : n'est rendu que si l'utilisateur courant est l'auteur
  (`review.coach_id === currentUserId`) ou admin. On utilise l'id utilisateur
  courant déjà disponible via le contexte d'auth.

Le style suit le design system existant (surface layering, pas de bordures de
sectionnement, texte en français, ton discret pour l'attribution d'auteur).

## Tests (`backend/tests`)

Tests pytest (SQLite in-memory), suivant les fixtures existantes de `conftest.py` :

1. Deux entraîneurs créent chacun un retour pour le même patineur+même semaine →
   **2 retours coexistent** (plus d'écrasement).
2. Un entraîneur qui ré-enregistre sur sa propre semaine met à jour **son** retour,
   sans affecter celui de l'autre.
3. `update_review` / `delete_review` : un coach ne peut pas éditer/supprimer le
   retour d'un autre coach → 403 ; un admin le peut.
4. `coach_name` présent et correct dans les réponses de `list_reviews`,
   `get_review`, `create_review`, `get_timeline`.
5. Idem incidents : `coach_name` présent dans les réponses.
6. Un patineur lié voit les deux retours (visibles) avec les noms d'auteur.

## Hors scope (YAGNI)

- Pas de notion de « co-signature » ou de fusion de retours entre entraîneurs.
- Pas de changement au mécanisme de notification (chaque retour visible notifie
  comme aujourd'hui).
- Pas de refonte visuelle du module ; seulement l'ajout de l'attribution d'auteur.
