"""
Downloader service: downloads PDF score sheets from competition result websites.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.config import PDF_DIR

logger = logging.getLogger(__name__)


async def download_pdfs(pdf_urls: list[str], competition_slug: str) -> list[Path]:
    """Download a list of PDF URLs to local storage. Returns paths of downloaded files."""
    dest_dir = PDF_DIR / competition_slug
    dest_dir.mkdir(parents=True, exist_ok=True)

    downloaded: list[Path] = []
    async with httpx.AsyncClient(
        timeout=30.0,
        headers={"User-Agent": "Mozilla/5.0 (compatible; skating-analyzer/1.0)"},
    ) as client:
        for pdf_url in pdf_urls:
            filename = _pdf_filename(pdf_url)
            dest = dest_dir / filename
            if dest.exists():
                downloaded.append(dest)
                continue
            try:
                resp = await client.get(pdf_url, follow_redirects=True)
                resp.raise_for_status()
                dest.write_bytes(resp.content)
                downloaded.append(dest)
            except (httpx.HTTPError, OSError) as exc:
                logger.warning("Failed to download %s: %s", pdf_url, exc)

    return downloaded


def url_to_slug(url: str) -> str:
    parsed = urlparse(url)
    slug = f"{parsed.netloc}{parsed.path}".replace("/", "_").strip("_")
    return re.sub(r"[^a-zA-Z0-9_\-]", "", slug)[:100]


def _pdf_filename(pdf_url: str) -> str:
    path = urlparse(pdf_url).path
    name = path.rstrip("/").split("/")[-1]
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name
