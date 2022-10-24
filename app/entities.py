from pathlib import Path
from datetime import date

from sqlalchemy import Column, Integer, Float, Unicode, String, Date, ForeignKey, Table
from sqlalchemy.orm import registry, sessionmaker, relationship
from sqlalchemy_schemadisplay import create_schema_graph

mapper_registry = registry()
Base = mapper_registry.generate_base()

########### Entities Relation Diagram ##############

#      Skater (n) ---- has members ---- (1) Club 
#      Skater (1) ----- realizes ------ (n) Performance
#      Skater (m) -- participates to -- (n) Competitions [ via Inscriptions ]
# Competition (1) ------ contains ----- (n) Performance

#####################################################s

####### INSCRIPTIONS:  Association Table SKATER - COMPETITION

inscription_table = Table("inscriptions", Base.metadata,
  Column('skater_id', ForeignKey("skaters.id"), primary_key=True),
  Column('competition_id', ForeignKey("competitions.id"), primary_key=True),
)

#####################################################

####### SKATER Entity definition
class Skater(Base):
  """ Defines a Skater instance
  A Skater is a physical person who participated in at least one Competition. 
  For each Competition a Skater participated to, a got a Performance. A Skater is
  also associated to a Club. 
  """

  __tablename__ = "skaters"
  
  id = Column(Integer, primary_key=True)
  full_name = Column(Unicode, nullable=False)
  first_name = Column(Unicode)
  last_name = Column(Unicode)
  birth_date = Column(Date) 
  genre = Column(String(1))
  nation = Column(String)

  club_id = Column(Integer, ForeignKey('clubs.id'), nullable=False)

  club = relationship("Club", back_populates="skaters")
  performances = relationship("Performance", back_populates="skater")
  competitions = relationship("Competition", secondary=inscription_table, back_populates="skaters")

  def __init__(self, full_name: str, club: str, birth_date:date=None):
      self.full_name = full_name
      self.first_name = " ".join(list(filter(lambda w: not w.isupper(), full_name.split(" "))))
      self.last_name = " ".join(list(filter(lambda w: w.isupper(), self.full_name.split(" "))))
      self.club = club
      self.birth_date = birth_date

#####################################################

####### CLUB Entity definition
class Club(Base):

  __tablename__ = "clubs"

  id = Column(Integer, primary_key=True)
  name = Column(Unicode, nullable=False)
  abbrev = Column(Unicode(10))
  city = Column(Unicode)

  skaters = relationship("Skater", back_populates="club")

#####################################################


####### COMPETITION Entity definition
class Competition(Base):

  __tablename__ = "competitions"

  id = Column(Integer, primary_key=True)
  name = Column(Unicode, nullable=False)
  type = Column(String(10))
  start = Column(Date)
  end = Column(Date)
  location = Column(Unicode)
  rink_name = Column(Unicode)
  url = Column(Unicode)
 
  skaters = relationship("Skater", secondary=inscription_table, back_populates="competitions")
  performances = relationship("Performance", back_populates="competition")

#####################################################

####### PERFORMANCE Entity definition
class Performance(Base):

  __tablename__ = "performances"

  id = Column(Integer, primary_key=True)
  skater_id = Column(Integer, ForeignKey('skaters.id'), nullable=False)
  competition_id = Column(Integer, ForeignKey('competitions.id'), nullable=False)

  rank = Column(Integer)
  starting_number = Column(Integer)
  total_segment_score = Column(Float)
  total_element_score = Column(Float)
  total_component_score = Column(Float)
  total_deductions = Column(Float)
  bonifications = Column(Float)
  
  skater = relationship("Skater", back_populates="performances")
  competition = relationship("Competition", back_populates="performance")
#####################################################

#####################################################
def init_db(engine):
  Base.metadata.create_all(bind=engine)
#####################################################

#####################################################
def graph_erd(graph_path:Path) -> None:

  graph = create_schema_graph(metadata=Base.metadata,
    show_datatypes=False, # The image would get nasty big if we'd show the datatypes
    show_indexes=False, # ditto for indexes
    rankdir='LR', # From left to right (instead of top to bottom)
    concentrate=False # Don't try to join the relation lines together
  )
  graph.write_png(graph_path) # write out the file
#####################################################