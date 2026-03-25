# Guide de deploiement — Figure Skating Analyzer

Ce guide vous accompagne pour mettre en ligne votre propre instance de l'application d'analyse de patinage artistique. Trois options sont proposees, de la plus simple a la plus avancee.

## Quelle option choisir ?

| | Render | Railway | VPS + Docker |
|---|---|---|---|
| **Difficulte** | Facile | Facile | Avancee |
| **Cout** | Gratuit | ~5 $/mois | ~5 EUR/mois |
| **Temps de mise en place** | ~15 min | ~10 min | ~30 min |
| **Performances** | Pause apres 15 min d'inactivite (free tier) | Toujours actif | Toujours actif |
| **Domaine personnalise** | Oui (gratuit) | Oui (inclus) | Oui (avec Caddy) |
| **Carte bancaire requise** | Non (free tier) | Oui | Oui |

> **Vous ne savez pas quoi choisir ?** Commencez par **Render** — c'est gratuit et ca prend 15 minutes.

---

## Prerequis communs

Avant de commencer, vous aurez besoin de :

1. **Un compte GitHub** — Creez-en un sur [github.com](https://github.com) si ce n'est pas deja fait
2. **Le code de l'application** — Faites un "Fork" du depot sur votre compte GitHub (bouton "Fork" en haut a droite du depot)
3. **(Optionnel) Un Google Client ID** — Necessaire uniquement si vous souhaitez que vos utilisateurs puissent se connecter via Google. Sans cela, seule la connexion par email/mot de passe est disponible.

---

## Option 1 : Render (recommandee)

Render est une plateforme cloud qui permet de deployer des applications web gratuitement. L'application s'endort apres 15 minutes d'inactivite (le premier chargement prend alors ~30 secondes), mais c'est amplement suffisant pour un usage club.

### Comment ca marche

Sur Render, l'application est separee en deux services :

- **Backend** (Web Service) — le serveur Python qui gere les donnees, heberge via Docker
- **Frontend** (Static Site) — l'interface web, servie comme un simple site statique

Le frontend communique avec le backend via la variable `VITE_API_URL`, qui doit pointer vers l'URL du backend sur Render (ex: `https://skating-backend.onrender.com/api`).

### Methode rapide : Blueprint (recommande)

Le depot contient un fichier `render.yaml` qui configure tout automatiquement.

1. Connectez-vous sur [render.com](https://render.com) avec votre compte GitHub
2. Cliquez sur **New** > **Blueprint**
3. Selectionnez votre fork du depot
4. Render detecte le fichier `render.yaml` et affiche les services a creer
5. Remplissez les variables demandees :
   - `ADMIN_EMAIL` — votre adresse email (sera le compte administrateur)
   - `ADMIN_PASSWORD` — un mot de passe solide (min. 8 caracteres)
   - `CLUB_NAME` — le nom complet de votre club
   - `CLUB_SHORT` — l'abreviation (ex: CSG)
   - `GOOGLE_CLIENT_ID` — laissez vide si vous n'utilisez pas Google OAuth
   - `VITE_GOOGLE_CLIENT_ID` — meme valeur que `GOOGLE_CLIENT_ID` (ou vide)
   - `ALLOWED_ORIGINS` — l'URL de votre frontend Render (ex: `https://skating-frontend.onrender.com`)
   - `VITE_API_URL` — l'URL de votre backend Render suivie de `/api` (ex: `https://skating-backend.onrender.com/api`)
6. Cliquez sur **Apply**
7. Attendez que les deux services soient en ligne (icone verte)
8. Cliquez sur l'URL de votre frontend — votre application est en ligne !

> **Note :** Les URLs exactes de vos services ne sont connues qu'apres creation. Vous devrez peut-etre revenir dans les parametres pour completer `ALLOWED_ORIGINS` et `VITE_API_URL` une fois les services crees.

### Methode manuelle

Si le Blueprint ne fonctionne pas, creez les services manuellement :

#### Backend

1. **New** > **Web Service**
2. Connectez votre depot GitHub
3. Parametres :
   - **Name** : `skating-backend`
   - **Runtime** : Docker
   - **Dockerfile Path** : `./Dockerfile.backend`
   - **Plan** : Free
4. Dans **Disks**, ajoutez un disque :
   - **Mount Path** : `/data`
   - **Size** : 1 GB
5. Dans **Environment**, ajoutez les variables :
   - `SECRET_KEY` — cliquez "Generate" pour creer une valeur aleatoire
   - `DATABASE_URL` = `sqlite+aiosqlite:////data/skating.db`
   - `PDF_DIR` = `/data/pdfs`
   - `LOGOS_DIR` = `/data/logos`
   - `ADMIN_EMAIL` = votre email
   - `ADMIN_PASSWORD` = votre mot de passe
   - `CLUB_NAME` = nom du club
   - `CLUB_SHORT` = abreviation
   - `ALLOWED_ORIGINS` = l'URL de votre frontend (a completer apres creation)
   - `SECURE_COOKIES` = `true`
6. Cliquez **Create Web Service**

#### Frontend

1. **New** > **Static Site**
2. Connectez le meme depot GitHub
3. Parametres :
   - **Name** : `skating-frontend`
   - **Build Command** : `cd frontend && npm ci && npm run build`
   - **Publish Directory** : `frontend/dist`
4. Dans **Environment**, ajoutez :
   - `VITE_API_URL` = l'URL de votre backend suivie de `/api` (ex: `https://skating-backend.onrender.com/api`)
   - `VITE_GOOGLE_CLIENT_ID` = votre Google Client ID (ou laissez vide)
5. Dans **Redirects/Rewrites**, ajoutez :
   - **Source** : `/*`, **Destination** : `/index.html`, **Action** : Rewrite
6. Cliquez **Create Static Site**

> **Important :** Apres creation des deux services, mettez a jour `ALLOWED_ORIGINS` dans le backend avec l'URL exacte du frontend (ex: `https://skating-frontend.onrender.com`).

---

## Option 2 : Railway

Railway est une plateforme cloud avec une interface tres visuelle. Pas de free tier permanent, mais le service reste toujours actif (pas de mise en veille).

### Etapes

1. Connectez-vous sur [railway.app](https://railway.app) avec votre compte GitHub
2. Cliquez sur **New Project** > **Deploy from GitHub Repo**
3. Selectionnez votre fork du depot

Railway cree un premier service. Vous devez configurer les deux services (backend et frontend) separement :

#### Backend

4. Cliquez sur le service cree, puis dans **Settings** :
   - **Builder** : Dockerfile
   - **Dockerfile Path** : `Dockerfile.backend`
5. Dans **Variables**, ajoutez :
   - `SECRET_KEY` — une chaine aleatoire (generez-la avec `openssl rand -hex 32` ou sur un site comme randomkeygen.com)
   - `ADMIN_EMAIL` — votre email
   - `ADMIN_PASSWORD` — votre mot de passe
   - `CLUB_NAME` — nom du club
   - `CLUB_SHORT` — abreviation
   - `ALLOWED_ORIGINS` — l'URL du frontend (a completer apres)
   - `SECURE_COOKIES` = `true`
6. Dans **Settings** > **Volumes**, ajoutez un volume :
   - **Mount Path** : `/data`
7. Dans **Settings** > **Networking**, cliquez **Generate Domain** pour obtenir une URL publique

#### Frontend

8. Dans le meme projet, cliquez **New** > **GitHub Repo** et selectionnez a nouveau votre depot
9. Dans **Settings** :
   - **Builder** : Dockerfile
   - **Dockerfile Path** : `Dockerfile.frontend`
10. Dans **Variables**, ajoutez :
    - `VITE_GOOGLE_CLIENT_ID` = votre Google Client ID (ou vide)
11. Dans **Settings** > **Networking**, cliquez **Generate Domain**

#### Connexion des services

12. Notez l'URL interne du backend (visible dans les settings du service backend)
13. Dans les variables du frontend, ajoutez : `VITE_API_URL` = URL du backend + `/api`
14. Dans les variables du backend, mettez a jour `ALLOWED_ORIGINS` avec l'URL du frontend
15. Cliquez **Deploy** sur les deux services

### Cout

Railway offre 5 $ de credits a l'inscription. Ensuite, l'usage typique pour un club (faible trafic) revient a environ 5 $/mois.

---

## Option 3 : VPS + Docker Compose

Cette option est pour les utilisateurs a l'aise avec un terminal. Elle offre le plus de controle et les meilleures performances pour le prix.

### Fournisseurs VPS recommandes

| Fournisseur | Prix minimum | Localisation |
|---|---|---|
| OVH | ~3.50 EUR/mois (VPS Starter) | France |
| Hetzner | ~4.50 EUR/mois (CX22) | Allemagne/Finlande |
| DigitalOcean | ~6 $/mois (Basic) | Europe |

Un VPS avec 1 vCPU et 2 Go de RAM suffit largement.

### Installation rapide

Connectez-vous a votre VPS en SSH, puis lancez :

```bash
sudo apt-get update && sudo apt-get install -y git
git clone https://github.com/VOTRE_UTILISATEUR/figure-skating-analyzer.git /opt/skating-analyzer
cd /opt/skating-analyzer
sudo bash deploy.sh
```

Le script `deploy.sh` :
- Installe Docker si necessaire
- Vous demande les informations de votre club
- Genere une cle secrete aleatoire
- Lance l'application

Votre application est ensuite accessible sur `http://ADRESSE_IP_DU_VPS`.

### Securisation du VPS

Avant de rendre l'application publique, securisez votre serveur :

```bash
# Activer le pare-feu — autoriser uniquement SSH, HTTP et HTTPS
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

> **Important :** Ne laissez pas le port 8000 ouvert directement. Quand vous utilisez Caddy (voir ci-dessous), le backend n'est accessible que via le reverse proxy.

### HTTPS avec Caddy (recommande)

Pour securiser l'acces avec HTTPS et un certificat Let's Encrypt gratuit, ajoutez Caddy comme reverse proxy.

#### 1. Creez un fichier `Caddyfile` a la racine du projet :

```
votre-domaine.fr {
    handle /api/* {
        reverse_proxy backend:8000
    }
    handle {
        reverse_proxy frontend:80
    }
}
```

#### 2. Creez un fichier `docker-compose.prod.yml` :

```yaml
services:
  caddy:
    image: caddy:2-alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy-data:/data
      - caddy-config:/config
    depends_on:
      - frontend
      - backend

  # Retirer le port public du frontend — Caddy s'en charge
  frontend:
    ports: !reset []

  # Retirer le port public du backend — Caddy s'en charge
  backend:
    ports: !reset []

volumes:
  caddy-data:
  caddy-config:
```

#### 3. Lancez avec le fichier de production :

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Caddy obtient automatiquement un certificat SSL pour votre domaine. Assurez-vous que :
- Votre domaine pointe vers l'IP du VPS (enregistrement DNS de type A)
- Les ports 80 et 443 sont ouverts sur le VPS (voir section securisation ci-dessus)

### Maintenance

#### Sauvegarder la base de donnees

```bash
cd /opt/skating-analyzer
docker compose exec backend sqlite3 /data/skating.db ".backup '/data/backup.db'"
cp "$(docker compose exec backend cat /data/backup.db)" ./backup_$(date +%Y%m%d).db
```

Methode alternative avec un dump SQL :

```bash
docker compose exec backend sqlite3 /data/skating.db .dump > backup_$(date +%Y%m%d).sql
```

Planifiez une sauvegarde automatique avec cron :

```bash
# Sauvegarder tous les jours a 3h du matin
sudo mkdir -p /opt/backups
echo "0 3 * * * cd /opt/skating-analyzer && docker compose exec -T backend sqlite3 /data/skating.db .dump > /opt/backups/skating_\$(date +\%Y\%m\%d).sql" | sudo crontab -
```

#### Mettre a jour l'application

```bash
cd /opt/skating-analyzer
git pull
docker compose up -d --build
```

#### Consulter les logs

```bash
docker compose logs -f           # Tous les services
docker compose logs -f backend   # Backend uniquement
```

#### Redemarrer

```bash
docker compose restart
```

---

## Reference des variables d'environnement

### Variables backend

| Variable | Obligatoire | Description |
|---|---|---|
| `SECRET_KEY` | **Oui** | Chaine aleatoire utilisee pour securiser les sessions. Ne la partagez jamais. Generez-la avec `openssl rand -hex 32`. |
| `ADMIN_EMAIL` | Non | Email du compte administrateur cree au premier lancement. Si non defini, utilisez la page `/setup`. |
| `ADMIN_PASSWORD` | Non | Mot de passe du compte administrateur (min. 8 caracteres). |
| `CLUB_NAME` | Non | Nom complet de votre club (ex: "Club des Sports de Grenoble"). |
| `CLUB_SHORT` | Non | Abreviation du club (ex: "CSG"). |
| `DATABASE_URL` | Non | URL de la base de donnees. Par defaut : SQLite dans `/data/skating.db`. |
| `GOOGLE_CLIENT_ID` | Non | Identifiant Google OAuth. Si non defini, le bouton "Connexion Google" est masque. |
| `ALLOWED_ORIGINS` | Non | URLs autorisees pour les requetes (CORS). Indiquez l'URL de votre frontend. |
| `SECURE_COOKIES` | Non | `true` par defaut. Mettez `false` uniquement en developpement local sans HTTPS. |
| `PDF_DIR` | Non | Dossier de stockage des PDFs. Par defaut : `/data/pdfs`. |
| `LOGOS_DIR` | Non | Dossier de stockage des logos. Par defaut : `/data/logos`. |

### Variables frontend (build-time)

Ces variables sont injectees a la construction du frontend. Elles commencent par `VITE_` et doivent etre definies **avant** le build (ou dans les parametres de la plateforme).

| Variable | Obligatoire | Description |
|---|---|---|
| `VITE_API_URL` | Selon plateforme | URL de l'API backend. Requis sur Render/Railway (ex: `https://skating-backend.onrender.com/api`). Pas necessaire sur VPS (le proxy Nginx/Caddy s'en charge). |
| `VITE_GOOGLE_CLIENT_ID` | Non | Meme valeur que `GOOGLE_CLIENT_ID`. Necessaire pour afficher le bouton Google dans l'interface. |

---

## Aller plus loin : domaine personnalise

Au lieu d'utiliser l'URL generee par Render ou Railway (ex: `skating-frontend.onrender.com`), vous pouvez utiliser votre propre domaine (ex: `resultats.monclub.fr`).

### 1. Acheter un domaine

Si votre club n'a pas encore de nom de domaine, vous pouvez en acheter un chez :
- **OVH** (~7 EUR/an pour un .fr)
- **Gandi** (~15 EUR/an)

Si votre club a deja un domaine (ex: `monclub.fr`), vous pouvez creer un sous-domaine (ex: `resultats.monclub.fr`) sans frais supplementaires.

### 2. Configurer le DNS

Creez un enregistrement DNS de type **CNAME** (pour Render/Railway) ou **A** (pour VPS) :

**Pour Render :**
- Type : CNAME
- Nom : `resultats` (ou ce que vous voulez)
- Valeur : l'URL de votre service Render (ex: `skating-frontend.onrender.com`)

**Pour Railway :**
- Type : CNAME
- Nom : `resultats`
- Valeur : l'URL fournie par Railway dans les settings du domaine personnalise

**Pour VPS :**
- Type : A
- Nom : `resultats`
- Valeur : l'adresse IP de votre VPS

### 3. Activer dans la plateforme

**Render :** Service > Settings > Custom Domains > Add Custom Domain

**Railway :** Service > Settings > Domains > Add Custom Domain

**VPS :** Modifiez le `Caddyfile` avec votre domaine (Caddy genere le certificat automatiquement).

---

## Migrer entre plateformes

Si vous commencez sur Render et souhaitez migrer vers un VPS (ou inversement), vos donnees sont portables :

### Exporter les donnees

**Depuis Render :** Accedez au shell du service backend (onglet "Shell"), puis :
```bash
sqlite3 /data/skating.db .dump
```
Copiez la sortie dans un fichier `backup.sql` sur votre machine.

**Depuis un VPS :**
```bash
docker compose exec backend sqlite3 /data/skating.db .dump > backup.sql
```

### Importer sur la nouvelle plateforme

```bash
# Copier le backup sur le nouveau serveur, puis :
docker compose exec -T backend sqlite3 /data/skating.db < backup.sql
```

---

## Depannage

### Le service backend ne demarre pas

**Verifiez les logs :**
- Render : onglet "Logs" du service
- Railway : onglet "Logs"
- VPS : `docker compose logs backend`

**Causes frequentes :**
- `SECRET_KEY` non defini — ajoutez-le dans les variables d'environnement. **Attention :** si `SECRET_KEY` n'est pas defini, l'application utilise une cle par defaut non securisee. Definissez toujours une cle aleatoire en production.
- Disque non monte — verifiez que `/data` est bien un volume persistant

### "Erreur de connexion" ou "Network Error" sur la page de login

- Verifiez que `VITE_API_URL` est bien defini dans le frontend et pointe vers le backend (avec `/api` a la fin)
- Verifiez que `ALLOWED_ORIGINS` dans le backend contient l'URL exacte de votre frontend (avec `https://`)
- Verifiez que le backend est en ligne et accessible

### La base de donnees est vide apres un redemarrage

Le volume persistant n'est probablement pas configure. La base SQLite doit etre stockee dans un volume Docker (`/data`), sinon elle est perdue a chaque redemarrage du conteneur.

### Le bouton "Google" n'apparait pas

C'est normal si `GOOGLE_CLIENT_ID` et `VITE_GOOGLE_CLIENT_ID` ne sont pas definis. Les deux variables sont necessaires : l'une pour le backend (verification du token), l'autre pour le frontend (affichage du bouton). La connexion par email/mot de passe fonctionne sans.

### Comment reinitialiser le mot de passe admin ?

Arretez l'application, modifiez `ADMIN_PASSWORD` dans les variables d'environnement, puis relancez. Le mot de passe sera mis a jour au prochain demarrage.

### L'application est lente au premier chargement (Render)

Sur le plan gratuit de Render, le service s'endort apres 15 minutes d'inactivite. Le premier acces apres une periode d'inactivite prend ~30 secondes. C'est normal. Pour eviter cela, passez au plan Starter (7 $/mois).
