from pathlib import Path
import json
from datetime import date
from dateutil.parser import parse as date_parse

from create_db import init_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from entities import Competition

def load_competitions(season_path:Path, session: Session):
  competitions = [f for f in season_path.iterdir() if f.is_dir()]
  for c_path in competitions:
    with open(c_path.joinpath("infos.json"), "r") as f:
      infos = json.load(f) 
      comp = Competition(
        name = infos["competition"],
        type = infos["type"],
        start = date_parse(infos["start"]).date() if "start" in infos else None,
        end = date_parse(infos["end"]).date() if "start" in infos else None,
        location = infos.get("location", None),
        rink_name = infos.get("rink_name", None),
        url = infos.get("url", None)
      )
      comp.upsert(session)


if __name__ == "__main__":
  db_path = ":memory:"
  # db_path = "app/figure_skating.test.db"

  engine = create_engine(f"sqlite:///{db_path}", echo=True)
  init_db()
  
  with sessionmaker(bind=engine) as s:
    pass
