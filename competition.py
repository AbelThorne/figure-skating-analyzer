from pathlib import Path
from pprint import pprint
from typing import List
from bs4 import BeautifulSoup
import colorama
import requests
from urllib.parse import urlparse, urljoin
from dateutil.parser import parse as date_parse
import re
import pandas as pd
import json
import enum

from parse_pdfs import parse_pdf_from_path

# init the colorama module
colorama.init()
GREEN = colorama.Fore.GREEN
GRAY = colorama.Fore.LIGHTBLACK_EX
RESET = colorama.Fore.RESET
YELLOW = colorama.Fore.YELLOW

def _is_valid(url):
  parsed = urlparse(url)
  return bool(parsed.netloc) and bool(parsed.scheme)

class CompetitionStatus(enum.IntFlag):
  EMPTY = 0
  URL_NOT_VALID = 1
  INCOMPLETE_LOAD = 2
  FULLY_LOADED = 100
  
  def __repr__(self):
    return f'status.{self._name_}'
  __str__ = object.__str__
globals().update(CompetitionStatus.__members__)

class Competition(object):

  def __init__(self) -> None:
      self._url = None
      self._name = None
      self._type = None
      self._start = None
      self._end = None
      self._location = None
      self._rink_name = None
      self._status = CompetitionStatus.EMPTY
      
      self._save_dir = None
      self._scores_dir = None
      self._parsed_dir = None

      self._performances = None

      self._entries = pd.DataFrame(columns=["Surname", "First Name", "Full name", "Club", "Nationality", "Category", "Genre"])
      self._master_table = None

  @property
  def url(self):
    return self._url 

  @property
  def name(self):
    return self._name

  @property
  def type(self):
    return self._type

  @property
  def url(self):
    return self._url 

  @property
  def start(self):
    return self._start 

  @property
  def end(self):
    return self._end

  @property
  def location(self):
    return self._location

  @property
  def rink_name(self):
    return self._rink_name

  @property
  def nb_entries(self):
    return len(self._entries)

  @property
  def status(self):
    return self._status
  
  @property
  def ok(self):
    return self._status == CompetitionStatus.FULLY_LOADED

  @property
  def scores_dir(self):
    return self._scores_dir

  @scores_dir.setter
  def scores_dir(self, new_dir: Path):
    if not new_dir.is_dir():
      print(f"Invalid path for score: {new_dir}")
    else:
      self._scores_dir = new_dir

  @property
  def save_dir(self):
    return self._save_dir

  @save_dir.setter
  def save_dir(self, new_dir: Path):
    if not new_dir.is_dir():
      print(f"Invalid path to save to: {new_dir}")
    else:
      self._save_dir = new_dir
      if self._scores_dir is None:
        self._scores_dir = self._save_dir.joinpath("scores")
      if self._parsed_dir is None:
        self._parsed_dir = self._save_dir.joinpath("parsed_scores")

  @classmethod
  def load_from_dir(cls, path: Path,  crawl_to_complete=False) -> 'Competition':
    return cls().from_dir(path, crawl_to_complete)


  @classmethod
  def load_from_url(cls, url: str) -> 'Competition':
    return cls().from_url(url)
  

  def __str__(self) -> str:

      nb_categories = len(self._master_table) if self._master_table is not None else "N/A"
      nb_score_cards = len(list(filter(lambda f: f.is_file() and f.suffix == '.pdf', list(self._scores_dir.iterdir())))) if self._scores_dir is not None else "N/A"

      result = f""
      result += f"              Competition: {self._name}\n"
      result += f"                     Type: {self._type}\n"
      result += f"                 Location: {self._location}\n"
      result += f"                    Start: {self._start}\n"
      result += f"                      End: {self._end}\n"
      result += f"                     Rink: {self._rink_name}\n"
      result += f"               Nb Entries: {self.nb_entries}\n"
      result += f"            Nb Categories: {nb_categories}\n"
      result += f" Nb Score cards available: {nb_score_cards}"
      return result


  def save(self, dest_path: Path=None, overwrite=False) -> bool:
    
    if self._status != CompetitionStatus.FULLY_LOADED:
      print("Competition is not fully loaded, cannot save")
      return

    if dest_path is None and self._save_dir is None:
      print("No directory to save to")
      return
    
    if dest_path is not None:
      self._save_dir = dest_path
      if self._scores_dir is None:
        self._scores_dir = self._save_dir.joinpath("scores")

    if not self._save_dir.exists():
      self._save_dir.mkdir(parents=True)
    if overwrite or not self._save_dir.joinpath('entries.csv').exists():
      with open(self._save_dir.joinpath('entries.csv'), 'w') as f:
          self._entries.to_csv(f, sep=";", index=False)
    if overwrite or not self._save_dir.joinpath('info.json').exists():
      info = {
        "url": self._url,
        "competition": self._name,
        "type": self._type,
        "start": self._start,
        "end": self._end,
        "location": self._location,
        "rink_name": self._rink_name,
        "scores_dir": self._scores_dir.relative_to(self._save_dir),
        "parsed_dir": self._parsed_dir.relative_to(self._save_dir)
      }
      with open(self._save_dir.joinpath('info.json'), 'w') as f:          
        json.dump(info, f, indent=4, default=str)
    if overwrite or not self._save_dir.joinpath('master_table.json').exists():
      with open(self._save_dir.joinpath('master_table.json'), 'w') as f:          
        json.dump(self._master_table, f, indent=4, default=str)


  def from_dir(self, path: Path, crawl_to_complete: bool=False, set_as_save_dir: bool=True) -> 'Competition':
    info_missing = False
    entries_missing = False
    master_table_missing = False

    if not path.is_dir():
      print("Directory does not exist, cannot load")
      return self

    if path.joinpath('entries.csv').exists():
      with open(path.joinpath('entries.csv'), 'r') as f:
        self._entries = pd.read_csv(f, sep=";", header='infer')
    else:
      self._entries = pd.DataFrame(columns=["Surname", "First Name", "Full name", "Club", "Nationality", "Category", "Genre"])
      entries_missing = True

    if path.joinpath('info.json').exists():
      with open(path.joinpath('info.json'), 'r') as f:
        info = json.load(f)
        self._url = info["url"] if "url" in info else None
        self._name = info["competition"] if "competition" in info else None
        self._type = info["type"] if "type" in info else None
        self._start = date_parse(info["start"]).date() if "start" in info else None
        self._end = date_parse(info["end"]).date() if "end" in info else None
        self._location = info["location"] if "location" in info else None
        self._rink_name = info["rink_name"] if "rink_name" in info else None
        self._scores_dir = path.joinpath(info["scores_dir"]) if "scores_dir" in info else None
        self._parsed_dir = path.joinpath(info["parsed_dir"]) if "parsed_dir" in info else None
        if self._url is None or self._name is None or self._start is None or self._end is None:
          info_missing = True
    else:
      self._url = None
      self._name = None
      self._type = None
      self._start = None
      self._end = None
      self._location = None
      self._rink_name = None
      info_missing = True

    if path.joinpath('master_table.json').exists():
      with open(path.joinpath('master_table.json'), 'r') as f:
        self._master_table = json.load(f)
    else:
      self._master_table = None
      master_table_missing = True
    
    if entries_missing or master_table_missing or info_missing:
      self._status = CompetitionStatus.INCOMPLETE_LOAD
    else:
      self._status = CompetitionStatus.FULLY_LOADED

    if self._status == CompetitionStatus.INCOMPLETE_LOAD and crawl_to_complete and self._url is not None:
      soup = self._parse_url_content()
      if soup is not None:
        if master_table_missing:
          self._extract_master_table(soup)
          master_table_missing = False
        if entries_missing:
          self._get_entries_from_master_table()
          entries_missing = False
        if info_missing:
          self._get_info()
          info_missing = False

    if entries_missing or master_table_missing or info_missing:
      self._status = CompetitionStatus.INCOMPLETE_LOAD
    else:
      self._status = CompetitionStatus.FULLY_LOADED
    
    if set_as_save_dir:
      self.save_dir = path

    return self


  def from_url(self, url: str) -> 'Competition':
    print(f"{YELLOW}[*] Loading competition from {url}{RESET}")
    self._url = url
    soup = self._parse_url_content()
    if soup is not None:
      self._extract_master_table(soup)  
      self._get_entries_from_master_table()
      self._get_info(soup)
      self._status = CompetitionStatus.FULLY_LOADED
    
    return self


  def download_scores(self, dest_path: Path=None, overwrite:bool=False, relative=False) -> dict:

    if self._master_table is None:
      print("No master table available, generate it from URL first")
      return None

    if relative and self._save_dir is None:
      print("Cannot set scores path relative to save directory: save directory is None")
      return None

    if relative and dest_path is not None:
      dest_path = self._save_dir.joinpath(dest_path)

    if dest_path is None and self._scores_dir is None:
      print("No directory to save scores to")
      return None
    
    if not dest_path is None:
      self._scores_dir = dest_path

    nb_segments = 0
    missing = 0
    downloaded = 0
    failed = 0
    existing = 0

    if not self._scores_dir.exists():
      self._scores_dir.mkdir()
    for cat in self._master_table.values():
      for seg in cat["segments"]:
        nb_segments += 1
        if "scores_link" in seg:
          link = seg["scores_link"]
          if overwrite or not self._scores_dir.joinpath(Path(urlparse(link).path).name).exists():
            status = self._download_file(link, self._scores_dir)
            downloaded += 1 if status else 0
            failed += 1 if not status else 0
          else:
            existing += 1
        else:
          missing += 1

    print(f"[+] Total score sheets downloaded (out of {nb_segments}): {downloaded} downloaded / {existing} existing / {failed} failed / {missing} missing")
    return {
      "nb_segments": nb_segments,
      "missing": missing,
      "downloaded": downloaded,
      "failed": failed,
      "existing": existing,
    }


  def _download_file(self, url: str, dest_path: Path) -> bool:
    file_name = Path(urlparse(url).path).name
    if not dest_path.exists():
      print(f"{dest_path}: Destination directory does not exist")
      return False
    r = requests.get(url, allow_redirects=True)
    if not r.ok:
      print(f"{file_name}: File not found")
      return False
    return open(dest_path.joinpath(file_name), 'wb').write(r.content) > 0


  def _parse_url_content(self) -> BeautifulSoup:
      if not _is_valid(self.url):
        self._status = CompetitionStatus.URL_NOT_VALID
        print(f"Not a valid URL: {self.url}")
        return None
      resp = requests.get(self.url)
      if resp.ok:
        return BeautifulSoup(resp.content, "html.parser")
      else:
        print(f"Error {resp.status_code} when trying to crawl {self.url}")
        return None

  def parse_scores(self, dest_path: Path, overwrite=False, relative=True):

    if self._scores_dir is None:
      print("Scores directory is not set, stopping.")
      return

    if relative and self._save_dir is None:
      print("Cannot set parsed path relative to save directory: save directory is None")
      return None

    if relative and dest_path is not None:
      dest_path = self._save_dir.joinpath(dest_path)

    if dest_path is None and self._parsed_dir is None:
      print("No directory to save parsed scores to")
      return None
    
    if not dest_path is None:
      self._parsed_dir = dest_path

    if not self._parsed_dir.exists():
      self._parsed_dir.mkdir()

    for file in self._scores_dir.iterdir():
      if not file.is_file() or file.suffix != ".pdf":
        continue
      print(f"--- {file.name} ---")
      file_name = self._parsed_dir.joinpath(file.with_suffix(".json").name)
      if overwrite or not file_name.exists():
        parsed = parse_pdf_from_path(file)
        with open(file_name, "w") as f:
           json.dump(parsed, f, indent=4, default=str)
      

  def load_parsed_score(self):
    if self._parsed_dir is None:
      print("No directory for parsed scores, stopping.")
      return
    
    self._performances = []
    for file in self._parsed_dir.iterdir():
      if not file.is_file() or file.suffix != '.json':
        continue
      with open(f, 'r') as f:
        self._performances.append(json.load(f))
    
  def generate_competition_results(self):
    pass


  def _extract_master_table(self, soup: BeautifulSoup) -> None:
    self._master_table = {}
    table = soup.find("table")
    rows = table.find_all("tr")
    rows = rows[1:] # removing headers
    index = 0
    category = None
    segment = None
    while index < len(rows):
      cells = rows[index].find_all("td")
      if cells[0].text != "":
        if category is not None:
          self._master_table[category["name"]] = category
        category = {} # new category
        category["segments"] = []
        category["name"] = cells[0].text
        category["entries_link"] = urljoin(self.url, cells[2].find("a").attrs.get("href"))
        category["results_link"] = urljoin(self.url, cells[3].find("a").attrs.get("href"))
      else: # Going through the category segments
        segment = {} # New segment
        segment["name"] = cells[1].text
        segment["officials_link"] = urljoin(self.url, cells[2].find("a").attrs.get("href"))
        segment["details_link"] = urljoin(self.url, cells[3].find("a").attrs.get("href"))
        if len(cells) >= 5: # Sometimes there are no score cards (for some challenges)
          try:
            segment["scores_link"] = urljoin(self.url, cells[4].find("a").attrs.get("href"))
          except: # Link can be omitted if the category is empty or if all skaters were forfeit     
            pass     
        category["segments"].append(segment)
      index += 1
  

  def _get_info(self, soup: BeautifulSoup) -> None:
    match = re.search(r'^(.*?)CategorySegment', soup.text, flags=re.DOTALL)
    info_header = match.group(1)
    info_lines = list(filter(lambda l: l != '', map(lambda l: l.strip(), info_header.split("\n"))))
    self._name = info_lines[0] # Title
    self._infer_type()
    remaining_lines = info_lines[2:] # Title and Header 2 repeated
    date_pattern = r"^((0[1-9]|[12][0-9]|3[01])/(0[1-9]|1[012])/(19|20)\d\d)?(- | - | -)((0[1-9]|[12][0-9]|3[01])/(0[1-9]|1[012])/(19|20)\d\d)?$"
    date_line = [(idx,l) for idx,l in enumerate(remaining_lines) if re.match(date_pattern, l)]
    if len(date_line) != 1:
      print(f"Cannot find dates: {self.url}")
      pass
    else:
      self._parse_dates(date_line[0][1])
      del remaining_lines[date_line[0][0]]
    rink_pattern = r"Patinoire|PATINOIRE(.+)"
    rink_line = [(idx,l) for idx,l in enumerate(remaining_lines) if re.match(rink_pattern, l)]
    if len(rink_line) != 1:
      print(f"No rink name: {self.url}")
      pass
    else:
      self._rink_name = rink_line[0][1]
      del remaining_lines[rink_line[0][0]]
    if len(remaining_lines) > 0:
      if remaining_lines[0] != self._name:
        self._location = remaining_lines[0]
    

  def _infer_type(self) -> None:
    pattern = r"(?P<TF>TF | TF | TF)|(?P<TdF>TDF | TDF | TDF)|(?P<Challenge>CHALLENGE)|(?P<SFC>SELECTION FRANCE CLUB|SFC)|(?P<Criterium>CRITERIUM|CRIT )|(?P<CdF>Coupe de France)"
    match = re.search(pattern, self._name, flags=re.IGNORECASE)
    if match is None: 
      # We try on URL
      match = re.search(pattern, urlparse(self._url).path, flags=re.IGNORECASE)
    
    if match is not None:
      type = dict(filter(lambda elem: elem[1] is not None, match.groupdict().items()))
      if len(type) == 1:
        self._type = type.popitem()[0]


  def _parse_dates(self, line) -> None:
    match line.split(" "):
      case [date1, "-", date2]:
        self._start = date_parse(date1).date()
        self._end = date_parse(date2).date()
      case ["-", date1] | [date1, "-"] | [date1]:
        self._start = date_parse(date1).date()
        self._end = self._start
      case _:
        pass


  def _get_entries_from_master_table(self) -> None: 
    self._entries = pd.DataFrame(columns=["Surname", "First Name", "Full name", "Club", "Nationality", "Category", "Genre"])     
    for cat in self._master_table.values():
      genre = "M" if cat["name"].split(" ")[-1] == "Messieurs" else "F" 
      df_entry = self._crawl_entry(cat["entries_link"])
      if df_entry is not None:
        df_entry["Category"] = cat["name"] 
        df_entry["Genre"] = genre
        self._entries = pd.concat([self._entries, df_entry])        
    self._entries = self._entries.sort_values(by="Surname")


  def _crawl_entry(self, url:str) -> pd.DataFrame:
    if not _is_valid(url):
      print(f"Not a valid URL: {url}")
      return None
    resp = requests.get(url)
    if resp.ok:
      soup = BeautifulSoup(resp.content, "html.parser")
      df = pd.DataFrame(columns=["Surname", "First Name", "Full name", "Club", "Nationality"])
      rows = soup.find("table").find_all("tr")
      for r in rows[1:]:
        cells = r.find_all("td")
        full_name = cells[1].text.strip()
        surname = " ".join(list(filter(lambda w: w.isupper(), full_name.split(" "))))
        first_name = " ".join(list(filter(lambda w: not w.isupper(), full_name.split(" "))))
        df.loc[len(df.index)] = [
          surname,
          first_name,
          full_name,
          cells[2].text.strip(),
          cells[3].text.strip() if len(cells) >= 4 else "FRA"
        ]
      return df
    else:
      print(f"Error {resp.status_code} when trying to crawl {url}")
      return None


def crawl_season_2021_20211(dest_dir):
  competitions_occitanie = [
    "http://isujs.so.free.fr/Resultats/Resultats-2021-2022/TF-Font-Romeu-2021/",
    "http://isujs.so.free.fr/Resultats/Resultats-2021-2022/Challenge-Font-Romeu-2021/",
    "http://www.toulouseclubpatinage.com/Divers/html-TCP-2021-TF/",
    "http://www.toulouseclubpatinage.com/Divers/html-TCP-2021-Challenge/",
    "http://blagnac-patinage-sur-glace.fr/Resultats_competitions_ligue_Occitanie/html_castres_2022/index1.htm",
    "https://www.toulouseclubpatinage.com/Divers/html-SFC-SO-2022-TCP/",
    "https://www.toulouseclubpatinage.com/Divers/html-TCP-2022-Challenge/",
    "http://isujs.so.free.fr/Resultats/Resultats-2021-2022/Regional-Nimes-2022/",
    "http://isujs.so.free.fr/Resultats/Resultats-2021-2022/Challenge-Nimes-2022/",
    "http://blagnac-patinage-sur-glace.fr/trophee_blagnac_2022/index.htm",
    "https://blagnac-patinage-sur-glace.fr/challenge_blagnac_2022/index.htm",
  ]

  competitions_nationales = [
    "http://ligue-des-alpes-patinage.org/CSNPA/Saison20212022/TDF_2021_A1_Courbevoie_RESULTS/",
    "http://ligue-des-alpes-patinage.org/CSNPA/Saison20212022/TDF_2021_A2_Valence_RESULTS/",
    "http://ligue-des-alpes-patinage.org/CSNPA/Saison20212022/CupOfNice_2021_RESULTS/",
    "http://ligue-des-alpes-patinage.org/CSNPA/Saison20212022/TDF_2021_B4_Romorantin_RESULTS/",
    "http://ligue-des-alpes-patinage.org/CSNPA/Saison20212022/TDF_2021_B5_Louviers_RESULTS/",
    "http://ligue-des-alpes-patinage.org/CSNPA/Saison20212022/TDF_2021_B6_Charleville_RESULTS/",
    "http://ligue-des-alpes-patinage.org/CSNPA/Saison20212022/SFC-SE_2022_NICE_RESULTS/",
    "http://ligue-des-alpes-patinage.org/CSNPA/Saison20212022/TDF_2022_C7_Bercy_RESULTS/",
    "http://ligue-des-alpes-patinage.org/CSNPA/Saison20212022/TDF_2022_C8_Garges_RESULTS/",
    "http://ligue-des-alpes-patinage.org/CSNPA/Saison20212022/TDF_2022_C9_Nantes_RESULTS/",
    "http://ligue-des-alpes-patinage.org/CSNPA/Saison20212022/SFC-IDF_2022_CERGY_RESULTS/",
    "http://ligue-des-alpes-patinage.org/CSNPA/Saison20212022/SFC-SO_2022_TOULOUSE_RESULTS/",
    "http://ligue-des-alpes-patinage.org/CSNPA/Saison20212022/SFC-NO_2022_CAEN_RESULTS/",
    "http://ligue-des-alpes-patinage.org/CSNPA/Saison20212022/SFC-NE_2022_COMPIEGNE_RESULTS/",
    "http://ligue-des-alpes-patinage.org/CSNPA/Saison20212022/CDF_JUNB_2022_TOURS_RESULTS/",
    "http://ligue-des-alpes-patinage.org/CSNPA/Saison20212022/CRITERIUM_2022_LE_HAVRE_RESULTS/",
    "http://ligue-des-alpes-patinage.org/CSNPA/Saison20212022/FC2022_ANNECY_RESULTS/",
  ]

  for comp in (competitions_occitanie + competitions_nationales):
    competition = Competition.load_from_url(comp)
    competition.save(Path(dest_dir).joinpath(competition.name))

def load_season(season_dir) -> List['Competition']:
  dir_path = Path(season_dir)
  competitions = []
  for comp_dir in dir_path.iterdir():
    if comp_dir.is_dir():
      competitions.append(Competition.load_from_dir(comp_dir))
  
  return competitions


if __name__ == "__main__":
  # crawl_season_2021_20211("data/competitions/2021-2022")
  competitions = load_season("data/competitions/2021-2022")
  for c in competitions:
    print(f"##### {c.name} #####\n")
    c.parse_scores("parsed_scores", overwrite=False)
  


