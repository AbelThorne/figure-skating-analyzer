from typing import Set
import requests
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup, ResultSet
import colorama
from pathlib import Path
import pandas as pd
import json
from datetime import datetime, date
from pprint import pprint
import re

# init the colorama module
colorama.init()
GREEN = colorama.Fore.GREEN
GRAY = colorama.Fore.LIGHTBLACK_EX
RESET = colorama.Fore.RESET
YELLOW = colorama.Fore.YELLOW

# initialize the set of links (unique links)
internal_urls = set()
external_urls = set()


def is_valid(url):
    """
    Checks whether `url` is a valid URL.
    """
    parsed = urlparse(url)
    return bool(parsed.netloc) and bool(parsed.scheme)


def is_pdf(url):
    """
    Checks whether `url` is link to a PDF file.
    """
    parsed = urlparse(url)
    return Path(parsed.path).suffix == ".pdf"


def load_competition_url(url: str) -> BeautifulSoup:
    if not is_valid(url):
        print(f"Not a valid URL: {url}")
        return None
    resp = requests.get(url)
    if resp.ok:
        return BeautifulSoup(resp.content, "html.parser")
    else:
        print(f"Error {resp.status_code} when trying to crawl {url}")
        return None


def download_file(url: str, dest_dir: str) -> bool:
    """Download the file at `url` and save it in `dest_dir`

    Args:
        url (str): URL to the file
        dest_dir (str): Destination directory
    Returns bool: True is the file was correctly saved
    """
    dest_path = Path(dest_dir)
    file_name = Path(urlparse(url).path).name
    if not dest_path.exists():
        print(f"{dest_dir}: Destination directory does not exist")
        return False
    r = requests.get(url, allow_redirects=True)
    if not r.ok:
        print(f"{file_name}: File not found")
        return False
    return open(dest_path.joinpath(file_name), "wb").write(r.content) > 0


def _parse_dates(line):
    start = None
    end = None
    match line.split(" "):
        case [date1, "-", date2]:
            try:
                start = datetime.strptime(date1, "%d/%m/%Y")
                end = datetime.strptime(date2, "%d/%m/%Y")
            except Exception:
                start = datetime.strptime(date1, "%d.%m.%Y")
                end = datetime.strptime(date2, "%d.%m.%Y")
        case ["-", date1] | [date1, "-"] | [date1]:
            try:
                start = datetime.strptime(date1, "%d/%m/%Y")
            except Exception:
                start = datetime.strptime(date1, "%d.%m.%Y")
            end = start
        case _:
            pass
    return start, end


def _competition_type(line):
    patterns = [
        r"(?P<TF>TF | TF | TF)",
        r"(?P<TdF>TDF | TDF | TDF)",
        r"(?P<Challenge>CHALLENGE)",
        r"(?P<SFC>SELECTION FRANCE CLUB|SFC)",
        r"(?P<Criterium>CRITERIUM|CRIT )",
        r"(?P<CdF>Coupe de France)",
        r"(?P<Masters>Masters)",
        r"(?P<GP>Grand Prix)",
        r"(?P<Ouverture>Coupe de l ouverture)",
    ]
    pattern = "|".join(patterns)
    match = re.search(pattern, line, flags=re.IGNORECASE)
    if match is not None:
        type = dict(filter(lambda elem: elem[1] is not None, match.groupdict().items()))
        if len(type) == 1:
            return type.popitem()[0]
        else:
            return None  # Should not happen...
    else:
        return None


def _find_table_from_header(tables: ResultSet, header: str):
    header = "\n\n" + header
    for t in tables:
        if t.text.startswith(header):
            return t


def _master_table(soup, url):
    results = {}
    table = _find_table_from_header(soup.find_all("table"), "Category")
    rows = table.find_all("tr")
    rows = rows[1:]  # removing headers
    index = 0
    category = None
    segment = None
    while index < len(rows):
        cells = rows[index].find_all("td")
        if cells[0].text != "":
            if category is not None:
                results[category["name"]] = category
            category = {}  # new category
            category["segments"] = []
            category["name"] = cells[0].text
            category["entries_link"] = urljoin(
                url, cells[2].find("a").attrs.get("href")
            )
            category["results_link"] = urljoin(
                url, cells[3].find("a").attrs.get("href")
            )
        else:  # Going through the category segments
            segment = {}  # New segment
            segment["name"] = cells[1].text
            segment["officials_link"] = urljoin(
                url, cells[2].find("a").attrs.get("href")
            )
            segment["details_link"] = urljoin(url, cells[3].find("a").attrs.get("href"))
            if (
                len(cells) >= 5
            ):  # Sometimes there are no score cards (for some challenges)
                try:
                    segment["scores_link"] = urljoin(
                        url, cells[4].find("a").attrs.get("href")
                    )
                except:  # Link can be omitted if the category is empty or if all skaters were forfeit
                    pass
            category["segments"].append(segment)
        index += 1

    return results


def get_competition_info(soup: BeautifulSoup, url: str) -> dict:
    info = {}
    info["url"] = url
    match = re.search(r"^(.*?)\n\nCategory\nSegment", soup.text, flags=re.DOTALL)
    info_header = match.group(1)
    info_lines = list(
        filter(lambda l: l != "", map(lambda l: l.strip(), info_header.split("\n")))
    )
    info["competition"] = info_lines[0]  # Title
    info["type"] = _competition_type(info["competition"])
    info["location"] = info_lines[1].split("/")[0].strip()
    info["country"] = info_lines[1].split("/")[1].strip()
    info["rink_name"] = info_lines[2]

    date_pattern = r"^((0[1-9]|[12][0-9]|3[01])(/|\.)(0[1-9]|1[012])(/|\.)(19|20)\d\d)?(- | - | -)((0[1-9]|[12][0-9]|3[01])(/|\.)(0[1-9]|1[012])(/|\.)(19|20)\d\d)?$"
    if re.match(date_pattern, info_lines[3]):
        info["start"], info["end"] = _parse_dates(info_lines[3])
    else:
        print(f"Cannot parse dates: {url}")
        pass

    return info


def _crawl_entry(url) -> pd.DataFrame:
    if not is_valid(url):
        print(f"Not a valid URL: {url}")
        return None
    resp = requests.get(url)
    if resp.ok:
        soup = BeautifulSoup(resp.content, "html.parser")
        df = pd.DataFrame(
            columns=["Surname", "First Name", "Full name", "Club", "Nationality"]
        )
        rows = _find_table_from_header(soup.find_all("table"), "No.").find_all("tr")
        for r in rows[1:]:
            cells = r.find_all("td")
            full_name = cells[1].text.strip()
            if full_name == "":
                continue
            surname = " ".join(
                list(filter(lambda w: w.isupper(), full_name.split(" ")))
            )
            first_name = " ".join(
                list(filter(lambda w: not w.isupper(), full_name.split(" ")))
            )
            df.loc[len(df.index)] = [
                surname,
                first_name,
                full_name,
                cells[2].text.strip(),
                cells[3].text.strip() if len(cells) >= 4 else "FRA",
            ]
        return df
    else:
        print(f"Error {resp.status_code} when trying to crawl {url}")
        return None


def get_entries(master_table: dict) -> pd.DataFrame:
    entries = pd.DataFrame(
        columns=[
            "Surname",
            "First Name",
            "Full name",
            "Club",
            "Nationality",
            "Category",
            "Genre",
        ]
    )
    for cat in master_table.values():
        genre = (
            "M" if re.match(r"(Messieurs|Homme)", cat["name"].split(" ")[-1]) else "F"
        )
        df_entry = _crawl_entry(cat["entries_link"])
        df_entry["Category"] = cat["name"]
        df_entry["Genre"] = genre
        entries = pd.concat([entries, df_entry])
    entries = entries.sort_values(by="Surname")
    return entries


def crawl_competition(
    url, dest_dir, overwrite_entries=False, overwrite_info=False, overwrite_scores=False
):
    """
    Crawls a competition page and extracts all links to score cards.
    """
    print(f"{YELLOW}[*] Crawling: {url}{RESET}")
    dest_path = Path(dest_dir)
    if not dest_path.exists():
        dest_path.mkdir()

    soup = load_competition_url(url)
    if soup is None:
        return
    master_table = _master_table(soup, url)

    if overwrite_entries or not dest_path.joinpath("entries.csv").exists():
        entries = get_entries(master_table)
        with open(Path(dest_dir).joinpath("entries.csv"), "w") as f:
            entries.to_csv(f, sep=";", index=False)

    if overwrite_info or not dest_path.joinpath("info.json").exists():
        info = get_competition_info(soup, url)
        with open(dest_path.joinpath("info.json"), "w") as f:
            json.dump(info, f, indent=4, default=str)
            pprint(info)

    nb_segments = 0
    missing = 0
    downloaded = 0
    failed = 0
    existing = 0
    dest_scores = dest_path.joinpath("scores")
    if not dest_scores.exists():
        dest_scores.mkdir()
    for cat in master_table.values():
        for seg in cat["segments"]:
            nb_segments += 1
            if "scores_link" in seg:
                link = seg["scores_link"]
                if (
                    overwrite_scores
                    or not dest_scores.joinpath(Path(urlparse(link).path).name).exists()
                ):
                    status = download_file(link, dest_scores)
                    downloaded += 1 if status else 0
                    failed += 1 if not status else 0
                else:
                    existing += 1
            else:
                missing += 1

    print(
        f"[+] Total score sheets downloaded (out of {nb_segments}): {downloaded} downloaded / {existing} existing / {failed} failed / {missing} missing"
    )
    return {
        "nb_segments": nb_segments,
        "missing": missing,
        "downloaded": downloaded,
        "failed": failed,
        "existing": existing,
    }


if __name__ == "__main__":

    # competitions_occitanie = [
    #   "http://isujs.so.free.fr/Resultats/Resultats-2021-2022/TF-Font-Romeu-2021/",
    #   "http://isujs.so.free.fr/Resultats/Resultats-2021-2022/Challenge-Font-Romeu-2021/",
    #   "http://www.toulouseclubpatinage.com/Divers/html-TCP-2021-TF/",
    #   "http://www.toulouseclubpatinage.com/Divers/html-TCP-2021-Challenge/",
    #   "http://blagnac-patinage-sur-glace.fr/Resultats_competitions_ligue_Occitanie/html_castres_2022/index1.htm",
    #   "https://www.toulouseclubpatinage.com/Divers/html-SFC-SO-2022-TCP/",
    #   "https://www.toulouseclubpatinage.com/Divers/html-TCP-2022-Challenge/",
    #   "http://isujs.so.free.fr/Resultats/Resultats-2021-2022/Regional-Nimes-2022/",
    #   "http://isujs.so.free.fr/Resultats/Resultats-2021-2022/Challenge-Nimes-2022/",
    #   "http://blagnac-patinage-sur-glace.fr/trophee_blagnac_2022/index.htm",
    #   "https://blagnac-patinage-sur-glace.fr/challenge_blagnac_2022/index.htm",
    # ]

    # competitions_nationales = [
    #   "http://ligue-des-alpes-patinage.org/CSNPA/Saison20212022/TDF_2021_A1_Courbevoie_RESULTS",
    #   "http://ligue-des-alpes-patinage.org/CSNPA/Saison20212022/TDF_2021_A2_Valence_RESULTS/",
    #   "http://ligue-des-alpes-patinage.org/CSNPA/Saison20212022/CupOfNice_2021_RESULTS/",
    #   "http://ligue-des-alpes-patinage.org/CSNPA/Saison20212022/TDF_2021_B4_Romorantin_RESULTS/",
    #   "http://ligue-des-alpes-patinage.org/CSNPA/Saison20212022/TDF_2021_B5_Louviers_RESULTS/",
    #   "http://ligue-des-alpes-patinage.org/CSNPA/Saison20212022/TDF_2021_B6_Charleville_RESULTS/",
    #   "http://ligue-des-alpes-patinage.org/CSNPA/Saison20212022/SFC-SE_2022_NICE_RESULTS/",
    #   "http://ligue-des-alpes-patinage.org/CSNPA/Saison20212022/TDF_2022_C7_Bercy_RESULTS/",
    #   "http://ligue-des-alpes-patinage.org/CSNPA/Saison20212022/TDF_2022_C8_Garges_RESULTS/",
    #   "http://ligue-des-alpes-patinage.org/CSNPA/Saison20212022/TDF_2022_C9_Nantes_RESULTS/",
    #   "http://ligue-des-alpes-patinage.org/CSNPA/Saison20212022/SFC-IDF_2022_CERGY_RESULTS/",
    #   "http://ligue-des-alpes-patinage.org/CSNPA/Saison20212022/SFC-SO_2022_TOULOUSE_RESULTS/",
    #   "http://ligue-des-alpes-patinage.org/CSNPA/Saison20212022/SFC-NO_2022_CAEN_RESULTS/",
    #   "http://ligue-des-alpes-patinage.org/CSNPA/Saison20212022/SFC-NE_2022_COMPIEGNE_RESULTS/",
    #   "http://ligue-des-alpes-patinage.org/CSNPA/Saison20212022/CDF_JUNB_2022_TOURS_RESULTS/",
    #   "http://ligue-des-alpes-patinage.org/CSNPA/Saison20212022/CRITERIUM_2022_LE_HAVRE_RESULTS/",
    #   "http://ligue-des-alpes-patinage.org/CSNPA/Saison20212022/FC2022_ANNECY_RESULTS/",
    # ]

    competitions_occitanie = [
        "http://isujs.so.free.fr/Resultats/Resultats-2022-2023/CSNPA-VIOLETTES/",
        "http://isujs.so.free.fr/Resultats/Resultats-2022-2023/CHALLENGE-VIOLETTES/",
    ]

    competitions_nationales = [
        "http://www.isuresults.com/results/season2223/jgpfra2022/",
        "http://ligue-des-alpes-patinage.org/CSNPA/Saison20222023/Masters2022",
        "http://ligue-des-alpes-patinage.org/CSNPA/Saison20222023/COUPE%20DE%20L%20OUVERTURE%202022/",
        "http://ligue-des-alpes-patinage.org/CSNPA/Saison20222023/FFSG_CSNPA_TDF_COLMAR_A1/",
        "http://ligue-des-alpes-patinage.org/CSNPA/Saison20222023/FFSG_CSNPA_TDF_BELFORT_A2/",
    ]

    for comp in competitions_occitanie + competitions_nationales:
        # for comp in (competitions_occitanie + competitions_nationales):
        uri = Path(urlparse(comp).path)
        if uri.suffix != "":  # remove index.htm(l)
            competition_name = uri.parent.name
        else:
            if not comp[-1] == "/":
                comp = comp + "/"  # Add trailing slash if missing
            competition_name = uri.name
        crawl_competition(
            comp,
            Path("./data/competitions/2022-2023").joinpath(competition_name),
            overwrite_entries=True,
            overwrite_info=True,
        )
