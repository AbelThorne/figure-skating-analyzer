from app.services.scrapers.fs_manager import FSManagerScraper
from app.services.scrapers.base import BaseScraper


def get_scraper(url: str) -> BaseScraper:
    """Return the appropriate scraper based on URL pattern.

    Currently all supported competitions use the FS Manager HTML format.
    Future: add Swiss Timing / ISU pattern detection here.
    """
    return FSManagerScraper()
