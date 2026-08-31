# Demande de création de compte (parents & patineurs)

**Date** : 2026-08-30
**Statut** : design validé, à implémenter

## Problème

SkateLab n'a aucun mécanisme de demande de compte. Aujourd'hui trois chemins
existent seulement :

1. `POST /api/auth/setup` — premier admin, bloqué dès qu'un utilisateur existe.
2. `POST /api/users/` — création par un admin (`require_admin`).
3. `POST /api/auth/google` — auto-provisioning OAuth en rôle `reader`, si le
   domaine de l'email est dans `allowed_domains`.

Un parent ou un patineur sans compte n'a donc aucun recours en self-service : il
doit contacter un admin hors application. On veut lui permettre de demander un
compte en fournissant le numéro de licence des patineurs à rattacher, vérifié
contre le **French Ranking** (classement national FFSG, export CSV public d'un
Google Sheet). Si le patineur appartient bien au club de l'instance, le compte
est créé automatiquement en rôle `skater`, avec un mot de passe temporaire
envoyé par email et à changer à la première connexion.

## Décisions d'architecture

### Accès au French Ranking : portage local (option A)

Le projet voisin `../ligue-app-competitions` sait déjà lire le French Ranking
(`backend/app/licence/`). Trois options ont été examinées :

- **A. Portage local** dans SkateLab — retenue.
- B. SkateLab appelle l'API de l'app ligue au runtime.
- C. Extraction d'un paquet Python partagé.

**A est retenue** parce que SkateLab est conçu comme une instance autonome par
club (setup first-run, SQLite embarquée, configuration en base). Le faire
dépendre au runtime d'une autre application déployée séparément casserait cette
propriété. La duplication (~200 lignes) est petite et stable : le format CSV ne
dérive que d'une saison à l'autre, ce que le parsing par alias d'en-tête absorbe
déjà. C n'est pas justifiable sans registre privé pour si peu de code.

### Clé de jointure : `licence_number` sur `skaters`

Le `Skater` de SkateLab est identifié par `(first_name, last_name)` (contrainte
d'unicité) et alimenté par l'import des feuilles de compétition. Le French
Ranking est indexé par licence. **Aucune clé commune n'existe** : la seule
jointure possible au premier rattachement est le nom.

On ajoute donc `skaters.licence_number` (nullable, unique), renseignée au
premier rattachement réussi. Les demandes suivantes pour le même patineur
matchent directement sur la licence, sans repasser par le nom.

### Rôle : pas de rôle `parent`

Le rôle `skater` existe et donne accès aux patineurs liés via `user_skaters`
(many-to-many). Un parent de trois enfants = un compte `skater` + trois liens.
Un rôle `parent` distinct aurait exactement les mêmes droits — il n'est pas
créé. Le formulaire ne demande pas « parent ou patineur ? » : la réponse ne
changerait rien au résultat.

### Preuve d'appartenance : licence + date de naissance

Le numéro de licence **seul ne prouve rien** : il figure sur les listes de
départ, les feuilles de résultats publiées et le French Ranking lui-même, qui
est un Google Sheet public. Le formulaire exige donc aussi la **date de
naissance**, vérifiée contre `birth_date` du French Ranking.

C'est une barrière faible assumée (la date de naissance est elle aussi dans le
French Ranking public) : elle élimine le curieux opportuniste sans friction pour
un parent légitime. Le vrai filet est la **notification admin systématique** à
chaque compte créé, qui rend tout rattachement anormal visible et révocable.

L'adresse email saisie n'est vérifiée par rien (pas de lien de confirmation —
cf. YAGNI) ; la notification admin couvre ce risque.

## Modèle de données

### `skaters` — nouvelle colonne

| Colonne | Type | Notes |
|---|---|---|
| `licence_number` | `str \| None`, unique | Clé French Ranking, posée au rattachement |

`database.py` fait déjà de l'auto-migration par `ALTER TABLE` pour les nouvelles
colonnes : l'ajout suit ce mécanisme.

### `app_settings` — nouvelles colonnes

| Colonne | Type | Défaut | Notes |
|---|---|---|---|
| `french_ranking_url` | `str \| None` | `NULL` | URL collée par l'admin (lien de partage Google Sheets) |
| `account_requests_enabled` | `bool` | `False` | Opt-in : sans URL configurée, pas de formulaire |
| `french_ranking_club_names` | `JSON \| None` | `NULL` | Graphies nationales acceptées du nom de club |

`french_ranking_club_names` existe parce que `club_name_raw` du French Ranking
est une chaîne libre nationale (« TOULOUSE CLUB PATINAGE ») alors que SkateLab a
`club_name` / `club_short` saisis au setup (« TCP »). Sans ce réglage, une
instance dont les deux graphies divergent rejetterait toutes les demandes
légitimes.

### `french_ranking_entries` — nouvelle table

Cache local, portage de la table du projet ligue **moins la dimension saison**
(SkateLab a une seule saison courante dans `app_settings.current_season`) :

`id`, `licence_number`, `last_name`, `first_name`, `sex`, `birth_date`,
`club_name_raw`, `has_competition_licence`, `filiere`, `ligue_code`,
`fetched_at`.

Remplacée **en bloc** à chaque rafraîchissement (pas de diff/hash). TTL 1h.
Index sur `licence_number`.

### `account_requests` — nouvelle table

Trace de chaque demande, pour l'audit et la notification admin :

`id`, `email`, `display_name`, `licence_numbers` (JSON), `status`
(`created` / `pending_admin` / `rejected` / `expired`), `reject_reason`,
`created_at`, `resolved_at`, `user_id` (nullable, rempli si compte créé).

## Modules backend

### `app/services/french_ranking/` — portage

Trois fichiers à responsabilité unique :

- **`parser.py`** — `split_csv_line`, `normalize_birth`, `parse_french_ranking`.
  Résolution des colonnes par **alias d'en-tête** : la graphie dérive d'une
  saison à l'autre (« Filière » en 2026-2027, « Catégorie » en 2025-2026).
  Nom/Prénom/Licence obligatoires. Code pur, sans I/O ni DB.
- **`url.py`** — `normalize_french_ranking_url` : réécrit `.../pubhtml[?...]` en
  `.../pub?output=csv[&gid=N]`. Le `gid` doit être préservé : sans lui, l'export
  ne renvoie **silencieusement que le premier onglet** du classeur.
- **`cache.py`** — `ensure_fresh_cache(session, url, now)` : TTL 1h,
  remplacement en bloc. **Ne lève jamais** — toute erreur réseau ou de parsing
  sert le cache existant tel quel, même périmé ; pas de cache → liste vide.

### `app/services/account_request.py` — logique métier

Isolée des routes pour être testable sans HTTP :

- `verify_licence(entries, licence, birth_date)` → entrée French Ranking ou
  motif de rejet.
- `is_club_member(entry, settings)` → comparaison **foldée** (minuscules,
  diacritiques et ponctuation supprimés) de `club_name_raw` contre `club_name`,
  `club_short` et `french_ranking_club_names`.
- `resolve_skater(session, entry)` → `(skater, mode)` avec `mode` ∈ :
  - `exact` — match sur `licence_number`, ou sur nom exact (après folding et
    consultation de `skater_aliases`) → on lie.
  - `ambiguous` — match approchant mais non exact → **validation admin**, pour ne
    pas fabriquer un doublon en silence. `SettingsPage` a déjà une fusion de
    patineurs comme outil de rattrapage.
  - `absent` — aucun patineur correspondant → **création automatique** du
    `Skater` depuis les données French Ranking (`manual_create=True`, nom, club,
    année de naissance, licence). Refuser un licencié du club parce que ses
    compétitions ne sont pas encore importées serait incompréhensible ; une
    fiche vide est un état normal en début de saison.
- `process_request(session, payload)` → orchestration.

## Flux de la demande

Pour une demande portant sur N licences :

1. **Rate-limit** (IP + email), via `auth/rate_limit.py` déjà utilisé au login →
   sinon `429`.
2. `ensure_fresh_cache` → entrées du French Ranking.
3. Pour chaque licence : vérification licence + date de naissance, puis
   appartenance au club.
4. **Aucune licence valide** → `account_requests` en `rejected`, email
   d'explication au demandeur, réponse neutre.
5. **Au moins une valide, aucune ambiguë** → création du compte `skater`, mot de
   passe temporaire (`must_change_password=True`), liens `user_skaters`,
   `licence_number` posé sur chaque `Skater`.
6. **Au moins une ambiguë** → `pending_admin`, aucun compte créé, notification
   admin.
7. Dans tous les cas : **notification admin** + **réponse HTTP neutre
   identique**.

### Demande partiellement valide

Deux enfants, une licence bonne et une erronée (faute de frappe) : le compte est
créé avec les licences valides, et l'email **liste explicitement** celles qui ont
échoué et pourquoi, en invitant à refaire une demande pour celles-ci. L'admin
voit le détail dans `account_requests`. Créer le compte en silence laisserait le
parent croire que tout a marché ; tout rejeter serait frustrant.

### Cas limites

- **Mot de passe temporaire** : valable **7 jours**. L'expiration est évaluée
  **à la connexion** (pas de tâche planifiée) : si le compte a encore
  `must_change_password=True` et que la demande liée date de plus de 7 jours, le
  login est refusé, la demande passe `expired` et il faut en refaire une. Un
  compte déjà activé n'est jamais affecté.
- **Email déjà utilisé** : pas de doublon, et **on ne révèle pas** l'existence du
  compte. Réponse neutre habituelle ; un email part au demandeur indiquant qu'un
  compte existe déjà, avec les liens éventuellement ajoutés si les licences sont
  valides. Le endpoint ne doit pas devenir un oracle d'existence de comptes.
- **Réponse toujours neutre** : licence valide, mauvais club ou inexistante — la
  réponse HTTP est identique (`202`). Le détail part par email au demandeur et
  reste visible pour l'admin. Sinon le endpoint permettrait d'énumérer les
  licences du club.

## API

| Méthode | Chemin | Accès | Rôle |
|---|---|---|---|
| `POST` | `/api/auth/request-account` | public | Demande. Payload : `email`, `display_name`, `licences: [{licence_number, birth_date}]`. Réponse `202` neutre. |
| `GET` | `/api/admin/account-requests` | admin | Liste, avec détail des rejets et cas ambigus |
| `POST` | `/api/admin/account-requests/{id}/approve` | admin | Résout un `pending_admin` : choix du `Skater` à lier ou création, puis compte + email |
| `GET` | `/api/club-config/account-requests-enabled` | public | Dit au front s'il doit afficher le lien |

`/api/auth/*` est déjà exempté de `auth_guard` : le endpoint public s'y insère
naturellement.

## Frontend

- **`RequestAccountPage.tsx`** — accessible par un lien depuis `LoginPage`
  (affiché seulement si `account-requests-enabled`). Champ email, champ nom, et
  liste dynamique de licences (numéro + date de naissance, bouton « ajouter un
  patineur »). Après envoi : message neutre, aucun retour sur la validité.
- **`SettingsPage`** — un onglet listant les demandes en attente avec l'action
  d'approbation ; dans les paramètres, les champs URL French Ranking, activation
  du formulaire et graphies de club.

Tout le texte en **français**, Tailwind seul, conformément au design system
Kinetic Lens.

## Emails

Trois templates Jinja2 dans `templates/emails/` :

1. **Compte créé** — mot de passe temporaire, patineurs liés, et le cas échéant
   les licences en échec avec leur motif.
2. **Demande rejetée** — motif générique, sans révéler quelles licences existent.
3. **Email déjà utilisé** — cf. cas limites.

La notification admin passe par le `notification_service` existant.

## Tests

TDD : tests avant implémentation.

- **`parser.py` / `url.py`** — code pur, tests directs. Inclure les variantes
  d'en-tête (`Filière` / `Catégorie`) qui ont déjà mordu le projet ligue, et la
  préservation du `gid`.
- **`cache.py`** — TTL respecté ; surtout le comportement en panne réseau : sert
  le cache périmé, ne lève pas.
- **`account_request.py`** — les trois modes de `resolve_skater`, la comparaison
  de club foldée, la demande partiellement valide, la date de naissance qui ne
  correspond pas.
- **Routes** — réponse neutre identique dans tous les cas de figure,
  rate-limiting, email existant ne créant pas de doublon.

## Hors périmètre (YAGNI)

- Vérification d'email par lien de confirmation.
- Rôle `parent` distinct.
- Auto-approbation des cas ambigus.
- Interface de gestion des graphies de club au-delà d'un champ texte.
