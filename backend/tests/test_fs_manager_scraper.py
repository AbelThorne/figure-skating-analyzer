from pathlib import Path

from app.services.site_scraper import FSManagerScraper

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_index_finds_events():
    html = (FIXTURES / "index_sample.html").read_text()
    scraper = FSManagerScraper()
    events, categories = scraper.parse_index(html, "http://example.com/results/index.htm")

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

    # Categories
    assert len(categories) == 2
    assert categories[0].category == "R1 Junior-Senior Femme"
    assert categories[0].cat_url == "http://example.com/results/CAT001RS.htm"
    assert categories[0].segments == ["Free Skating"]
    assert categories[1].category == "R2 Novice Femme"
    assert categories[1].cat_url == "http://example.com/results/CAT002RS.htm"
    assert categories[1].segments == ["Short Program", "Free Skating"]


def test_parse_index_empty_table():
    html = "<html><body><table></table></body></html>"
    scraper = FSManagerScraper()
    events, categories = scraper.parse_index(html, "http://example.com/index.htm")
    assert events == []
    assert categories == []


def test_parse_cat_page_two_segments():
    html = (FIXTURES / "cat_result_two_segments.html").read_text()
    scraper = FSManagerScraper()
    results = scraper.parse_cat_page(html, "National Novice Femme", segment_count=2)

    assert len(results) == 3  # WD row is skipped
    r1 = results[0]
    assert r1.name == "Elina MONTAGARD"
    assert r1.club == "LGP"
    assert r1.nationality == "FRA"
    assert r1.category == "National Novice Femme"
    assert r1.overall_rank == 1
    assert r1.combined_total == 91.51
    assert r1.sp_rank == 1
    assert r1.fs_rank == 1
    assert r1.segment_count == 2

    r2 = results[1]
    assert r2.name == "Jade BELLOUATI"
    assert r2.overall_rank == 2
    assert r2.combined_total == 89.72
    assert r2.sp_rank == 3
    assert r2.fs_rank == 2

    r3 = results[2]
    assert r3.name == "Emma VOIROL-CABRIT"
    assert r3.overall_rank == 3
    assert r3.sp_rank == 6
    assert r3.fs_rank == 5


def test_parse_cat_page_one_segment():
    html = (FIXTURES / "cat_result_one_segment.html").read_text()
    scraper = FSManagerScraper()
    results = scraper.parse_cat_page(html, "National Minime Femme", segment_count=1)

    assert len(results) == 2
    r1 = results[0]
    assert r1.name == "Anna REBOULLET"
    assert r1.overall_rank == 1
    assert r1.combined_total == 47.75
    assert r1.sp_rank is None  # No SP column
    assert r1.fs_rank == 1
    assert r1.segment_count == 1


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
