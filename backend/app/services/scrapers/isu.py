from app.services.scrapers.base import BaseScraper
from app.services.site_scraper import ScrapedEvent, ScrapedResult


class ISUScraper(BaseScraper):
    """Stub — not yet implemented."""

    def parse_index(self, html: str, base_url: str) -> list[ScrapedEvent]:
        raise NotImplementedError("ISU scraper not yet implemented")

    def parse_seg_page(self, html: str, category: str, segment: str) -> list[ScrapedResult]:
        raise NotImplementedError

    async def scrape(self, url: str) -> tuple[list[ScrapedEvent], list[ScrapedResult]]:
        raise NotImplementedError
