from abc import ABC, abstractmethod

from app.services.site_scraper import ScrapedEvent, ScrapedResult


class BaseScraper(ABC):
    @abstractmethod
    def parse_index(self, html: str, base_url: str) -> list[ScrapedEvent]: ...

    @abstractmethod
    def parse_seg_page(self, html: str, category: str, segment: str) -> list[ScrapedResult]: ...

    @abstractmethod
    async def scrape(self, url: str) -> tuple[list[ScrapedEvent], list[ScrapedResult]]: ...
