#!/usr/bin/env bash
# deploy.sh — Script d'installation pour Figure Skating Analyzer
# Usage: curl -sSL <url>/deploy.sh | bash
#   ou : bash deploy.sh

set -euo pipefail

# --- Couleurs ---
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
error() { echo -e "${RED}[ERREUR]${NC} $*" >&2; }

# --- Vérification OS ---
check_os() {
    if [[ ! -f /etc/os-release ]]; then
        error "Ce script supporte uniquement Debian/Ubuntu."
        error "Sur un autre OS, installez Docker manuellement puis lancez :"
        error "  docker compose up -d --build"
        exit 1
    fi
    # shellcheck source=/dev/null
    . /etc/os-release
    if [[ "$ID" != "debian" && "$ID" != "ubuntu" ]]; then
        error "Ce script supporte Debian et Ubuntu. OS detecte : $ID"
        error "Installez Docker manuellement, puis lancez : docker compose up -d --build"
        exit 1
    fi
    ok "Systeme detecte : $PRETTY_NAME"
}

# --- Installation Docker ---
install_docker() {
    if command -v docker &>/dev/null; then
        ok "Docker est deja installe ($(docker --version))"
        return
    fi

    info "Installation de Docker..."
    apt-get update -qq
    apt-get install -y -qq ca-certificates curl gnupg >/dev/null

    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL "https://download.docker.com/linux/$ID/gpg" | \
        gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    # shellcheck source=/dev/null
    . /etc/os-release
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
      https://download.docker.com/linux/$ID $VERSION_CODENAME stable" \
      > /etc/apt/sources.list.d/docker.list

    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin >/dev/null
    ok "Docker installe avec succes"
}

# --- Cloner le repo ---
clone_repo() {
    local repo_url="https://github.com/VOTRE_UTILISATEUR/figure-skating-analyzer.git"
    local install_dir="/opt/skating-analyzer"

    if [[ -d "$install_dir" ]]; then
        info "Le repertoire $install_dir existe deja."
        read -rp "Mettre a jour ? (o/N) " update
        if [[ "$update" =~ ^[oOyY]$ ]]; then
            cd "$install_dir"
            git pull
            ok "Mis a jour"
        fi
    else
        info "Clonage du depot..."
        read -rp "URL du depot GitHub (Entree pour utiliser le depot par defaut) : " custom_url
        if [[ -n "$custom_url" ]]; then
            repo_url="$custom_url"
        fi
        git clone "$repo_url" "$install_dir"
        ok "Depot clone dans $install_dir"
    fi

    cd "$install_dir"
}

# --- Générer la configuration ---
generate_env() {
    if [[ -f .env ]]; then
        info "Le fichier .env existe deja."
        read -rp "Le recreer ? (o/N) " recreate
        if [[ ! "$recreate" =~ ^[oOyY]$ ]]; then
            ok "Conservation du .env existant"
            return
        fi
    fi

    echo ""
    echo -e "${BOLD}=== Configuration de votre club ===${NC}"
    echo ""

    # Clé secrète
    local secret_key
    secret_key=$(openssl rand -hex 32 2>/dev/null || head -c 64 /dev/urandom | od -An -tx1 | tr -d ' \n')

    # Infos club
    read -rp "Nom du club : " club_name
    read -rp "Abreviation du club (ex: CSG) : " club_short

    # Compte admin
    echo ""
    echo -e "${BOLD}Compte administrateur${NC}"
    read -rp "Email admin : " admin_email
    while true; do
        read -rsp "Mot de passe admin (min. 8 caracteres) : " admin_password
        echo ""
        if [[ ${#admin_password} -ge 8 ]]; then
            break
        fi
        error "Le mot de passe doit contenir au moins 8 caracteres."
    done

    # Google OAuth (optionnel)
    echo ""
    read -rp "Google Client ID (Entree pour ignorer) : " google_client_id

    # Écrire .env
    cat > .env <<EOF
SECRET_KEY=${secret_key}
CLUB_NAME=${club_name}
CLUB_SHORT=${club_short}
ADMIN_EMAIL=${admin_email}
ADMIN_PASSWORD=${admin_password}
GOOGLE_CLIENT_ID=${google_client_id}
SECURE_COOKIES=true
EOF

    ok "Fichier .env genere"
}

# --- Lancer l'application ---
start_app() {
    info "Construction et demarrage de l'application..."
    docker compose up -d --build

    echo ""
    echo -e "${GREEN}${BOLD}=== Installation terminee ===${NC}"
    echo ""
    echo -e "L'application est accessible sur : ${BOLD}http://$(hostname -I | awk '{print $1}')${NC}"
    echo ""
    echo -e "Commandes utiles :"
    echo -e "  ${BLUE}cd /opt/skating-analyzer${NC}"
    echo -e "  ${BLUE}docker compose logs -f${NC}          — voir les logs"
    echo -e "  ${BLUE}docker compose restart${NC}           — redemarrer"
    echo -e "  ${BLUE}docker compose down${NC}              — arreter"
    echo -e "  ${BLUE}git pull && docker compose up -d --build${NC} — mettre a jour"
    echo ""
}

# --- Script principal ---
main() {
    echo ""
    echo -e "${BOLD}=== Figure Skating Analyzer — Installation ===${NC}"
    echo ""

    # Vérifier les droits root
    if [[ $EUID -ne 0 ]]; then
        error "Ce script doit etre lance en tant que root (sudo)."
        error "Relancez avec : sudo bash deploy.sh"
        exit 1
    fi

    check_os
    install_docker
    clone_repo
    generate_env
    start_app
}

main "$@"
