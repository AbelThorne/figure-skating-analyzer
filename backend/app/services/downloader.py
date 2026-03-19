"""
Downloader service: crawls a competition result website and downloads PDF score sheets.

Since competition result sites vary in structure, this module uses an extensible
adapter pattern. New site-specific adapters can be registered via `register_adapter`.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx

from app.config import PDF_DIR


class BaseAdapter:
    """Base class for site-specific download adapters."""

    def can_handle(self, url: str) -> bool:
        raise NotImplementedError

    async def discover_pdfs(self, url: str, client: httpx.AsyncClient) -> list[str]:
        """Return a list of absolute PDF URLs found at the given competition URL."""
        raise NotImplementedError


class GenericHTMLAdapter(BaseAdapter):
    """
    Generic adapter that scans an HTML page for links ending in .pdf.
    Works for most statically generated competition result sites.
    """

    def can_handle(self, url: str) -> bool:
        return True  # fallback adapter

    async def discover_pdfs(self, url: str, client: httpx.AsyncClient) -> list[str]:
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()
        html = response.text
        base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        # Find all href values ending in .pdf (case-insensitive)
        hrefs = re.findall(r'href=["\']([^"\']*\.pdf[^"\']*)["\']', html, re.IGNORECASE)
        pdf_urls = []
        for href in hrefs:
            absolute = href if href.startswith("http") else urljoin(url, href)
            pdf_urls.append(absolute)
        return list(dict.fromkeys(pdf_urls))  # deduplicate, preserve order


_adapters: list[BaseAdapter] = [GenericHTMLAdapter()]


def register_adapter(adapter: BaseAdapter, priority: bool = True) -> None:
    """Register a new site adapter. Set priority=True to check it before others."""
    if priority:
        _adapters.insert(0, adapter)
    else:
        _adapters.append(adapter)


def _get_adapter(url: str) -> BaseAdapter:
    for adapter in _adapters:
        if adapter.can_handle(url):
            return adapter
    return GenericHTMLAdapter()


async def download_competition_pdfs(url: str) -> list[Path]:
    """
    Crawl a competition result website and download all PDF score sheets.

    Returns a list of local file paths where PDFs were saved.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        adapter = _get_adapter(url)
        pdf_urls = await adapter.discover_pdfs(url, client)

        downloaded: list[Path] = []
        competition_slug = _url_to_slug(url)
        dest_dir = PDF_DIR / competition_slug
        dest_dir.mkdir(parents=True, exist_ok=True)

        for pdf_url in pdf_urls:
            filename = _pdf_filename(pdf_url)
            dest = dest_dir / filename
            if dest.exists():
                downloaded.append(dest)
                continue
            resp = await client.get(pdf_url, follow_redirects=True)
            resp.raise_for_status()
            dest.write_bytes(resp.content)
            downloaded.append(dest)

    return downloaded


def _url_to_slug(url: str) -> str:
    parsed = urlparse(url)
    slug = f"{parsed.netloc}{parsed.path}".replace("/", "_").strip("_")
    return re.sub(r"[^a-zA-Z0-9_\-]", "", slug)[:100]


def _pdf_filename(pdf_url: str) -> str:
    path = urlparse(pdf_url).path
    name = path.rstrip("/").split("/")[-1]
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name
