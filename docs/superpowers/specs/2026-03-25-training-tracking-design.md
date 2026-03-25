# Suivi d'entraînement — Design Spec

## Contexte

L'application figure-skating-analyzer permet aujourd'hui d'analyser les résultats de compétitions. Cette feature étend la portée avec un suivi quotidien des patineurs par les coachs : retours hebdomadaires structurés, signalement d'incidents, et vue longitudinale de la progression.

## Décisions de design

| Question | Décision |
|----------|----------|
| Utilisateurs | Nouveau rôle `coach` dédié |
| Relation coach-patineurs | Un coach voit tous les patineurs du club |
| Format retour | Mixte : notes rapides (1-5) par critère + commentaires séparés |
| Critères | Assiduité (fractionnaire), engagement (1-5), progression (1-5), attitude (1-5) |
| Commentaires | Deux champs : "points forts" et "axes d'amélioration" |
| Incidents | Simple : type + date + description |
| Visibilité parents | Configurable par le coach à chaque saisie |
| Granularité temporelle | Semaine calendaire (lundi-dimanche), auto-proposée |
| Notifications | Email (désactivable dans les préférences utilisateur) |
| Architecture données | Modèles séparés (WeeklyReview + Incident) |

## 1. Modèle de données

### Rôle `coach`

Ajout de `"coach"` à l'enum `user_role` dans `User.role`. Permissions :
- Voit tous les patineurs du club (pas de lien explicite)
- Crée/modifie/supprime des retours hebdomadaires et incidents
- Accès lecture seule aux compétitions et scores
- Pas d'accès à la gestion utilisateurs, imports, ou configuration

### Table `WeeklyReview`

| Colonne | Type | Description |
|---------|------|-------------|
| `id` | Integer PK | Auto-increment |
| `skater_id` | FK → skaters.id (CASCADE) | Patineur concerné |
| `coach_id` | FK → users.id (CASCADE) | Coach auteur |
| `week_start` | Date | Lundi de la semaine (calculé automatiquement) |
| `attendance` | String(20) | Assiduité, format libre ex: "3/4" |
| `engagement` | Integer | Note 1-5 |
| `progression` | Integer | Note 1-5 |
| `attitude` | Integer | Note 1-5 |
| `strengths` | Text | Points forts de la semaine |
| `improvements` | Text | Axes d'amélioration |
| `visible_to_skater` | Boolean | Visible par le parent/patineur (default: true) |
| `created_at` | DateTime | |
| `updated_at` | DateTime | |

Contrainte unique : `(skater_id, week_start)` — un seul retour par patineur par semaine.

### Table `Incident`

| Colonne | Type | Description |
|---------|------|-------------|
| `id` | Integer PK | Auto-increment |
| `skater_id` | FK → skaters.id (CASCADE) | Patineur concerné |
| `coach_id` | FK → users.id (CASCADE) | Coach auteur |
| `date` | Date | Date de l'incident |
| `incident_type` | Enum: `injury`, `behavior`, `other` | Type d'incident |
| `description` | Text | Description libre |
| `visible_to_skater` | Boolean | Visible par le parent/patineur (default: false) |
| `created_at` | DateTime | |
| `updated_at` | DateTime | |

### Modification du modèle `User`

Ajout d'une colonne `email_notifications` (Boolean, default: true) pour permettre la désactivation des notifications email.

## 2. API Backend

### Routes retours hebdomadaires — `/api/training/reviews`

| Méthode | Route | Accès | Description |
|---------|-------|-------|-------------|
| `GET` | `/api/training/reviews?skater_id=&from=&to=` | coach, admin | Liste des retours (filtrable par patineur et période) |
| `GET` | `/api/training/reviews/{id}` | coach, admin, skater (si visible) | Détail d'un retour |
| `POST` | `/api/training/reviews` | coach, admin | Créer un retour |
| `PUT` | `/api/training/reviews/{id}` | coach (auteur), admin | Modifier un retour |
| `DELETE` | `/api/training/reviews/{id}` | coach (auteur), admin | Supprimer un retour |

### Routes incidents — `/api/training/incidents`

| Méthode | Route | Accès | Description |
|---------|-------|-------|-------------|
| `GET` | `/api/training/incidents?skater_id=&from=&to=` | coach, admin | Liste des incidents |
| `GET` | `/api/training/incidents/{id}` | coach, admin, skater (si visible) | Détail |
| `POST` | `/api/training/incidents` | coach, admin | Créer un incident |
| `PUT` | `/api/training/incidents/{id}` | coach (auteur), admin | Modifier |
| `DELETE` | `/api/training/incidents/{id}` | coach (auteur), admin | Supprimer |

### Route timeline — `/api/training/timeline`

| Méthode | Route | Accès | Description |
|---------|-------|-------|-------------|
| `GET` | `/api/training/timeline?skater_id=&from=&to=` | coach, admin, skater | Timeline fusionnée reviews + incidents, triée par date décroissante |

Pour le rôle `skater`, le backend filtre automatiquement par `visible_to_skater=true` et par les patineurs liés dans `UserSkater`.

### Permissions

- Nouveau guard `require_coach_or_admin` — autorise les rôles `coach` et `admin`
- Modification/suppression : un coach ne peut modifier/supprimer que ses propres entrées, un admin peut tout modifier
- Le rôle `reader` n'a pas accès aux données d'entraînement
- Le rôle `skater` accède en lecture seule aux entrées marquées visibles pour ses patineurs liés

## 3. Notifications email

### Déclenchement

Un email est envoyé quand :
- Un retour hebdomadaire est créé avec `visible_to_skater=true`
- Un incident est créé avec `visible_to_skater=true`
- Un retour/incident existant est modifié pour devenir `visible_to_skater=true`

### Destinataires

Utilisateurs de rôle `skater` liés au patineur concerné via `UserSkater`, qui ont `email_notifications=true`.

### Contenu

- **Sujet** : "Nouveau retour d'entraînement pour [Prénom NOM]" ou "Nouvel incident signalé pour [Prénom NOM]"
- **Corps** : email HTML avec résumé (notes pour un retour, type + description pour un incident) et lien vers l'app
- **Templates** : Jinja2, même approche que les templates de rapports PDF existants

### Envoi

- Via la job queue existante (`services/job_queue.py`) — non bloquant pour le coach
- Nouveau service `services/email.py` avec fonction `send_notification_email(to, subject, html_body)`
- Configuration SMTP via variables d'env : `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`

### Préférence utilisateur

- Colonne `email_notifications` sur `User` (default: true)
- Endpoint `PUT /api/me/preferences` pour basculer le réglage
- Accessible dans la page profil/paramètres du skater

## 4. Frontend

### Nouvelles pages

**Page "Suivi entraînement"** — `/training` (coach, admin)
- Liste des patineurs du club en cards
- Pour chaque patineur : dernier retour, nombre d'incidents récents
- Clic → page détail

**Page détail patineur entraînement** — `/training/skaters/:id` (coach, admin)
- En-tête : nom du patineur, moyennes sur les 4 dernières semaines
- Onglet "Retours" : liste des retours hebdomadaires + bouton "Nouveau retour"
- Onglet "Incidents" : liste des incidents + bouton "Nouvel incident"
- Onglet "Évolution" : graphiques longitudinaux

**Formulaire retour hebdomadaire** — modal ou page (coach, admin)
- Sélecteur de semaine (pré-rempli semaine courante, sélection de semaines passées possible)
- Assiduité (texte), engagement/progression/attitude (sélecteur 1-5)
- Points forts (textarea), axes d'amélioration (textarea)
- Toggle "Visible par le patineur/parent"
- Alerte si un retour existe déjà pour cette semaine

**Formulaire incident** — modal (coach, admin)
- Date (pré-remplie aujourd'hui), type (select: blessure/comportement/autre)
- Description (textarea)
- Toggle "Visible par le patineur/parent" (default: non coché)

**Vue skater** — onglet "Entraînement" dans la fiche patineur existante (rôle `skater`)
- Timeline des retours et incidents visibles
- Graphique d'évolution des notes

### Navigation

- Rôle `coach` : nav principale = "Patineurs" (suivi entraînement) + "Compétitions" (lecture seule)
- Rôle `skater` : onglet "Entraînement" ajouté sur la fiche de chaque patineur lié

## 5. Vue longitudinale

### Graphique d'évolution des notes

- Type : Line chart (Recharts)
- Axe X : semaines (`week_start`)
- Axe Y : notes 1-5
- 3 séries : engagement, progression, attitude (couleurs distinctes)
- Période par défaut : 12 dernières semaines, sélecteur pour élargir
- Tooltip au survol avec détail de la semaine

### Indicateur d'assiduité

- Affiché sous le graphique principal sous forme de barres ou pastilles par semaine (ex: "3/4", "4/4")
- Format texte libre, pas de courbe

### Marqueurs d'incidents

- Affichés comme marqueurs sur l'axe X du graphique principal à la date correspondante
- Couleur par type : rouge (blessure), orange (comportement), gris (autre)
- Tooltip au clic avec résumé de l'incident

### Filtrage par rôle

- Coach/admin : voit tous les retours et incidents
- Skater : ne voit que les entrées marquées `visible_to_skater=true`

## 6. Design system

Toutes les nouvelles pages suivent le design system Kinetic Lens :
- Tailwind CSS, pas de component libraries
- Textes en français
- Surface color layering (pas de bordures)
- Fonts : Manrope (titres), Inter (body), Material Symbols Outlined (icônes)
- Notes numériques en `font-mono`
- Couleurs : `on-surface` (#191c1e), `primary` (#2e6385), `error` (#ba1a1a)
