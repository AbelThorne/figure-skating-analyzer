# Rôle `skater` — Accès restreint par patineur

## Contexte

L'application dispose de deux rôles : `admin` (gestion complète) et `reader` (consultation de toutes les données). Un nouveau besoin émerge : permettre à des utilisateurs (typiquement des parents) de consulter uniquement les données de leur(s) patineur(s), sans accès au reste de l'application.

## Objectif

Ajouter un troisième rôle `skater` qui restreint l'accès à la page détail d'un ou plusieurs patineurs spécifiques (gestion des fratries). Tout le reste de l'application est masqué.

---

## Modèle de données

### Enum `user_role`

Ajout de `"skater"` aux valeurs possibles :

```
admin | reader | skater
```

Migration Alembic nécessaire pour étendre l'enum SQLite.

### Table `user_skaters`

Nouvelle table de liaison many-to-many :

| Colonne    | Type   | Contraintes                        |
|------------|--------|------------------------------------|
| user_id    | String | FK → users.id, ON DELETE CASCADE   |
| skater_id  | String | FK → skaters.id, ON DELETE CASCADE |

- Contrainte d'unicité sur `(user_id, skater_id)`
- Seuls les utilisateurs de rôle `skater` utilisent cette table

---

## Backend

### Guards

**Nouveau guard : `require_skater_access(request, skater_id)`**

- Rôles `admin` et `reader` : accès autorisé (pass-through)
- Rôle `skater` : vérifie que `skater_id` figure dans les `user_skaters` de l'utilisateur connecté. Sinon, 403.

### Endpoints patineurs

Les endpoints suivants ajoutent le guard `require_skater_access` :

- `GET /api/skaters/{id}`
- `GET /api/skaters/{id}/seasons`
- `GET /api/skaters/{id}/scores`
- `GET /api/skaters/{id}/elements`
- `GET /api/skaters/{id}/category-results`
- `GET /api/reports/skater/{id}/pdf`

### Nouvel endpoint

**`GET /api/me/skaters`**

- Retourne la liste des patineurs liés à l'utilisateur connecté
- Réponse : `Array<{ id: string, first_name: string, last_name: string, club: string }>`
- Utilisé par le frontend pour la navigation et la page de sélection fratrie

### Endpoints restreints pour le rôle `skater`

Les endpoints suivants retournent 403 pour un utilisateur `skater` :

- `GET /api/dashboard/*` (statistiques globales)
- `GET /api/competitions/*` (liste et détail des compétitions)
- `GET /api/skaters` (liste de tous les patineurs)
- `GET /api/club/*` (statistiques club)
- `GET /api/reports/club/*` (rapport club)
- Tous les endpoints admin (déjà protégés par `require_admin`)

**Implémentation** : nouveau guard `reject_skater_role(request)` appelé sur ces routes, qui retourne 403 si `user_role == "skater"`.

### JWT

Le claim `role` du token d'accès inclut désormais `"skater"` comme valeur possible. Aucun changement de structure.

---

## Frontend

### Routing (rôle `skater`)

**Cas 1 patineur lié :**
- Redirection automatique vers `/patineurs/:id/analyse`
- Toute navigation vers une autre route redirige vers cette page

**Cas plusieurs patineurs (fratrie) :**
- Page de sélection à `/mes-patineurs` : liste simple de cartes cliquables (nom, prénom, club)
- Clic → `/patineurs/:id/analyse`
- Toute navigation vers une route non autorisée redirige vers `/mes-patineurs`

**Routes autorisées pour le rôle `skater` :**
- `/patineurs/:id/analyse` (avec vérification que l'ID est dans la liste autorisée)
- `/mes-patineurs` (sélection fratrie)
- `/profil`
- `/login`

**Toutes les autres routes** redirigent vers `/mes-patineurs` (ou directement vers la page patineur si un seul lié).

### Sidebar (rôle `skater`)

La sidebar affiche uniquement :

- **Haut** : logo du club (identique aux autres rôles)
- **Navigation** :
  - 1 patineur : lien "Mon patineur" vers `/patineurs/:id/analyse`
  - Plusieurs patineurs : lien "Mes patineurs" vers `/mes-patineurs`
- **Bas** : profil utilisateur + bouton déconnexion (identique aux autres rôles)

Les liens Dashboard, Patineurs, Compétitions, Club et Settings sont masqués.

### Page détail patineur

Identique à la version actuelle avec une seule modification :

- Les noms de compétitions dans le tableau d'historique sont affichés en **texte simple** (plus de liens cliquables vers `/competitions/:id`) pour le rôle `skater`
- Les rôles `admin` et `reader` conservent les liens cliquables

### Nouvelle page : sélection fratrie (`/mes-patineurs`)

Page minimaliste affichant les patineurs liés :

- Titre : "Mes patineurs"
- Liste de cartes avec nom et prénom de chaque patineur
- Clic sur une carte → navigation vers `/patineurs/:id/analyse`
- Accessible uniquement au rôle `skater`

---

## Admin — Gestion des comptes `skater`

### Formulaire de création/édition d'utilisateur

Modification du formulaire existant dans la page Settings :

- Quand le rôle `skater` est sélectionné dans le sélecteur de rôle, un nouveau champ apparaît : **"Patineurs associés"**
- Ce champ est un autocomplete multi-sélection qui recherche parmi les patineurs existants (par nom/prénom)
- Pour les rôles `admin` et `reader`, ce champ est masqué

### Endpoints utilisateurs

Modification des endpoints `POST /api/users` et `PATCH /api/users/{id}` :

- Acceptent un champ optionnel `skater_ids: string[]`
- Si le rôle est `skater` : crée/met à jour les entrées dans `user_skaters`
- Si le rôle n'est pas `skater` : le champ `skater_ids` est ignoré
- Si le rôle change de `skater` vers autre chose : les entrées `user_skaters` sont supprimées

### Endpoint `GET /api/users`

La réponse pour chaque utilisateur inclut un champ `skater_ids: string[]` (vide pour les non-skaters) afin que le formulaire d'édition puisse pré-remplir la sélection.

---

## Cas limites

- **Utilisateur `skater` sans patineur lié** : affiche un message "Aucun patineur associé à votre compte. Contactez l'administrateur." avec uniquement le bouton déconnexion.
- **Patineur supprimé** (cascade) : l'entrée `user_skaters` est supprimée automatiquement (ON DELETE CASCADE). Si plus aucun patineur lié, l'utilisateur tombe dans le cas ci-dessus.
- **Changement de rôle** : passer de `skater` à `reader`/`admin` supprime les liaisons `user_skaters`. Passer à `skater` nécessite d'assigner des patineurs.

---

## Fichiers impactés

### Backend
| Fichier | Modification |
|---------|-------------|
| `backend/app/models/user.py` | Enum `skater`, relation `skaters` |
| `backend/app/models/` (nouveau) | Table `user_skaters` |
| `backend/app/auth/guards.py` | `require_skater_access()`, `reject_skater_role()` |
| `backend/app/routes/skaters.py` | Ajout guard sur endpoints patineur |
| `backend/app/routes/users.py` | Gestion `skater_ids` en création/édition |
| `backend/app/routes/` (nouveau ou existant) | Endpoint `GET /api/me/skaters` |
| `backend/app/routes/competitions.py` | Ajout `reject_skater_role` sur GET |
| `backend/app/routes/dashboard.py` | Ajout `reject_skater_role` |
| `backend/app/routes/club_config.py` | Ajout `reject_skater_role` sur GET stats |
| Migration Alembic | Enum + table `user_skaters` |

### Frontend
| Fichier | Modification |
|---------|-------------|
| `frontend/src/api/client.ts` | Type `AuthUser.role` + endpoint `/api/me/skaters` + type `skater_ids` |
| `frontend/src/App.tsx` | Routing conditionnel, sidebar conditionnelle |
| `frontend/src/pages/SkaterAnalyticsPage.tsx` | Liens compétitions conditionnels |
| `frontend/src/pages/` (nouveau) | `MySkaters.tsx` (page sélection fratrie) |
| `frontend/src/auth/ProtectedRoute.tsx` | Logique de redirection rôle `skater` |
| `frontend/src/pages/SettingsPage.tsx` (ou sous-composant) | Champ autocomplete patineurs |
