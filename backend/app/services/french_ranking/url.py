"""Normalisation d'URL French Ranking.

Un admin colle le lien de partage Google Sheets (« pubhtml »), qui ne renvoie
qu'une coquille JS sans données. L'export exploitable est `pub?output=csv`.

Le `gid` doit être préservé : sans lui, l'export ne renvoie silencieusement que
le PREMIER onglet du classeur (un classeur French Ranking a un onglet par
catégorie/sexe).
"""

from __future__ import annotations

import re

_GID_RE = re.compile(r"[?&#]gid=(-?\d+)")


def normalize_french_ranking_url(raw_url: str) -> str:
    """Réécrit `.../pubhtml[?...]` en `.../pub?output=csv[&gid=N]`.

    Laisse inchangée toute autre URL (déjà au format export, ou source non-Google).
    """
    url = raw_url.strip()
    if "/pubhtml" in url:
        base = url.split("/pubhtml", 1)[0]
        match = _GID_RE.search(url)
        if match:
            return f"{base}/pub?output=csv&gid={match.group(1)}"
        return f"{base}/pub?output=csv"
    return url
