"""
Script de diagnostic: analyse la structure d'un site de résultats de patinage.
Usage: python scripts/analyze_site.py <url>
"""

import re
import sys
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup


def analyze(url: str):
    headers = {"User-Agent": "Mozilla/5.0 (compatible; skating-analyzer/1.0)"}
    with httpx.Client(headers=headers, follow_redirects=True, timeout=15) as client:
        print(f"\n=== Fetching {url} ===\n")
        r = client.get(url)
        print(f"Status: {r.status_code}")
        print(f"Content-Type: {r.headers.get('content-type')}")
        print(f"Content-Length: {len(r.content)} bytes\n")

        soup = BeautifulSoup(r.text, "html.parser")

        # All links
        all_links = [(a.get("href", ""), a.get_text(strip=True)) for a in soup.find_all("a", href=True)]

        # PDFs
        pdf_links = [(href, text) for href, text in all_links if ".pdf" in href.lower()]

        # Sub-pages (same domain .htm/.html)
        parsed = urlparse(url)
        base_domain = f"{parsed.scheme}://{parsed.netloc}"
        htm_links = [(href, text) for href, text in all_links
                     if re.search(r"\.html?", href, re.IGNORECASE) and "http" not in href]

        print("=== PDF links found ===")
        if pdf_links:
            for href, text in pdf_links:
                abs_url = href if href.startswith("http") else urljoin(url, href)
                print(f"  [{text}] {abs_url}")
        else:
            print("  (none)")

        print("\n=== Sub-page links (.htm/.html) ===")
        if htm_links:
            for href, text in htm_links:
                abs_url = urljoin(url, href)
                print(f"  [{text}] {abs_url}")
        else:
            print("  (none)")

        print("\n=== All other links ===")
        other = [(h, t) for h, t in all_links if (h, t) not in pdf_links and (h, t) not in htm_links]
        for href, text in other[:20]:
            print(f"  [{text}] {href}")

        print("\n=== Page title ===")
        print(f"  {soup.title.string if soup.title else '(none)'}")

        print("\n=== Raw HTML (first 3000 chars) ===")
        print(r.text[:3000])


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/analyze_site.py <url>")
        sys.exit(1)
    analyze(sys.argv[1])
