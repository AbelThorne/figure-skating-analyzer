from abc import ABC, abstractmethod

from app.services.site_scraper import ScrapedCategory, ScrapedCompetitionInfo, ScrapedEvent, ScrapedResult, ScrapedCategoryResult


class BaseScraper(ABC):
    @abstractmethod
    def parse_competition_info(self, html: str) -> ScrapedCompetitionInfo: ...

    @abstractmethod
    def parse_index(self, html: str, base_url: str) -> tuple[list[ScrapedEvent], list[ScrapedCategory]]: ...

    @abstractmethod
    def parse_seg_page(self, html: str, category: str, segment: str) -> list[ScrapedResult]: ...

    @abstractmethod
    async def scrape(self, url: str) -> tuple[list[ScrapedEvent], list[ScrapedResult], list[ScrapedCategoryResult], ScrapedCompetitionInfo]: ...
