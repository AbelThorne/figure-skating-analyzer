from pathlib import Path

from app.services.site_scraper import FSManagerScraper

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_index_finds_events():
    html = (FIXTURES / "index_sample.html").read_text()
    scraper = FSManagerScraper()
    events = scraper.parse_index(html, "http://example.com/results/index.htm")

    assert len(events) == 3  # 2 categories, but R2 Novice has SP + FS = 2 segments + 1 for R1
    # R1 Junior-Senior Femme - Free Skating
    assert events[0].category == "R1 Junior-Senior Femme"
    assert events[0].segment == "Free Skating"
    assert events[0].seg_url == "http://example.com/results/SEG018.htm"
    assert events[0].pdf_url == "http://example.com/results/JUDGES001.pdf"
    # R2 Novice Femme - Short Program
    assert events[1].category == "R2 Novice Femme"
    assert events[1].segment == "Short Program"
    assert events[1].seg_url == "http://example.com/results/SEG005.htm"
    # R2 Novice Femme - Free Skating
    assert events[2].category == "R2 Novice Femme"
    assert events[2].segment == "Free Skating"
    assert events[2].seg_url == "http://example.com/results/SEG006.htm"


def test_parse_index_empty_table():
    html = "<html><body><table></table></body></html>"
    scraper = FSManagerScraper()
    events = scraper.parse_index(html, "http://example.com/index.htm")
    assert events == []


def test_parse_seg_page():
    html = (FIXTURES / "seg_sample.html").read_text()
    scraper = FSManagerScraper()
    results = scraper.parse_seg_page(html, "R1 Junior-Senior Femme", "FS")

    assert len(results) == 2

    r1 = results[0]
    assert r1.name == "Maeva BORIES"
    assert r1.club == "MONTP"
    assert r1.nationality == "FRA"
    assert r1.category == "R1 Junior-Senior Femme"
    assert r1.segment == "FS"
    assert r1.rank == 1
    assert r1.total_score == 28.78
    assert r1.technical_score == 11.91
    assert r1.component_score == 16.87
    assert r1.components == {"CO": 3.42, "PR": 3.25, "SK": 3.25}
    assert r1.deductions == 0.00
    assert r1.starting_number == 8

    r2 = results[1]
    assert r2.name == "Lou Anne BLACHE"
    assert r2.rank == 2
    assert r2.total_score == 27.55
    assert r2.starting_number == 4
