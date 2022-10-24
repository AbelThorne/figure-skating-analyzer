from elasticsearch_dsl import Object, connections, Search, Document, InnerDoc, Index, Text, Date, Integer, Double, Keyword
import json
import sys
from pathlib import Path
import numpy as np
from datetime import datetime
import re


CACERT = "/Users/julien/projects/skate_performance_analyser/app/http_ca.crt"
HOST = "https://elastic:31QXCQ899L8WiPQRQ*hT@localhost:9200"

class Elements(InnerDoc):
  pass

class Components(InnerDoc):
  pass

class Club(InnerDoc):
  name = Text(required=True, fields={'raw': Keyword()})
  short = Text(required=True, fields={'raw': Keyword()})
  group = Text(required=False, fields={'raw': Keyword()})

class Performance(Document):
  name = Text(required=True, fields={'raw': Keyword()})
  club = Object(Club)
  city = Text(required=True, fields={'raw': Keyword()})
  competition = Text(required=True, fields={'raw': Keyword()})
  type = Text(required=True, fields={'raw': Keyword()})
  start = Date(required=True, default_timezone='UTC')
  end = Date(required=True, default_timezone='UTC')
  nation = Text(required=True, fields={'raw': Keyword()})
  program = Text(required=True)
  season = Text(required=True, fields={'raw': Keyword()})
  starting_number = Integer(required=True)
  rank = Integer(required=True)
  total_component_score = Double(required=True)
  total_deductions = Double(required=True)
  total_element_score = Double(required=True)
  total_segment_score = Double(required=True)

  elements = Object(Elements)
  components = Object(Components)

  class Index:
    name = "performances"

tcp_ecole_de_glace = [
  "Saskia ERNY",
  "Eva CASTELLANOS",
  "Mia HERVE",
  "Naissa SIMON-GUERIN",
  "Paloma LE SAINT HUBY",
  "Rose CABIROL",
  "Yohan SANTOS",
  "Lilian BROQUA",
  "Nell ERNY",
  "Izia ERNY",
  "Angelika ARKHIPOV",
]

tcp_competiteurs_avances = [
  "Alexandrine CALBO",
  "Clemence VIALA",
  "Hugo GUILLOTEAU",
  "Syrine PITIE",
  "Shaims PITIE",
  "Themis REY",
  "Samantha SANDOVAL. ROUGON",
  "Maelys TARZAALI"
]

tcp_competiteurs_club = [
  "Yaelle BOUQUIER",
  "Adele BOUQUIER",
  "Elise PASTEUR",
  "Chloe BRAS",
  "Sophie VIGNOLE",
  "Julie GONZALES",
  "Sofia AIT-OUBBA",
  "Tamara LATRASSE",
  "Mathys BUE-HUBERT",
  "Laura PASCUAL",
  "Elise DRUNOT",
  "Eva FLOREK",
  "Celia KIBITI",
  "Victoria LLEDOS",
  "Amandine CATUSSE",
  "Marion VIALA",
  "Alyson CALMELS",
  "Besma BOUSSOUALIN",
]

tcp = [{"name": n, "group": g} for n,g in zip(
  tcp_ecole_de_glace+tcp_competiteurs_avances+tcp_competiteurs_club,
  ["Ecole de glace"]*len(tcp_ecole_de_glace) + ["Competiteurs Avances"]*len(tcp_competiteurs_avances) + ["Competiteurs Club"]*len(tcp_competiteurs_club))
]

def get_skater_club(name: str) -> dict:
  
  found_tcp = list(filter(lambda entry: entry["name"] == name, tcp))
  
  if len(found_tcp) > 0:
    result = {}
    result["name"] = "Toulouse Club Patinage"
    result["short"] = "TCP"
    result["group"] = found_tcp[0]["group"]
    return result
  else:
    return None

def filter_nan(d):
  if isinstance(d, dict):
      return {k: filter_nan(v) for k, v in d.items() if not (isinstance(v, float) and np.isnan(v))}
  elif isinstance(d, list):
      return [filter_nan(v) for v in d]
  else:
      return d


def clean_name(name:str) -> str:
  result = re.sub(r'( -.+-$)|( \*.+\*$)', '', name)
  if result is not name:
    print("Name cleaning: {} was transformed into {}".format(name, result))
  return result    


def preprocess_performance(perf: dict) -> dict:
  processed = perf["metadata"].copy()
  processed["start"] = datetime.strptime(processed["start"], "%d/%m/%Y")
  processed["end"] = datetime.strptime(processed["end"], "%d/%m/%Y")
  processed["name"] = clean_name(processed["name"])
  processed["elements"] = filter_nan(perf["elements"])
  processed["components"] = filter_nan(perf["components"])
  processed["components"]["avg_factor"] = np.average([c["factor"] for c in perf["components"].values()])
  processed["components"]["total_unfactored"] = sum([c["scores_of_panel"] for c in perf["components"].values()])
  processed["components"]["avg_unfactored"] = np.average([c["scores_of_panel"] for c in perf["components"].values()])

  club = get_skater_club(processed["name"])
  if club is not None:
    processed["club"] = club

  return processed

if __name__ == "__main__":

  root = Path(__file__).parent

  connections.create_connection(hosts=[HOST], ca_certs=CACERT, )
  Performance.init()
  
  json_path = Path(root.joinpath("../output/json"))
  competitions = [d for d in json_path.iterdir() if d.is_dir()]
  for i, comp in enumerate(competitions):
    sys.stderr.write("\n### {} ###\n".format(comp.name))
    paths = comp.glob("*.json")
    for path in paths:
      sys.stderr.write("\n___ {} ___\n".format(path.name[:-4]))
      with open(path) as f:
        program = json.load(f)
        for perf in program["performances"]:
          doc = Performance(**preprocess_performance(perf))
          meta = doc.save(return_doc_meta=True)  
          print(meta)
        print("Saved {} performances".format(len(program["performances"])))
