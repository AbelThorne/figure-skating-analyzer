import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
PDF_DIR = DATA_DIR / "pdfs"
DB_PATH = DATA_DIR / "skating.db"
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

# Club configuration
CLUB_NAME = os.environ.get("CLUB_NAME", "Toulouse Club Patinage")
CLUB_SHORT = os.environ.get("CLUB_SHORT", "TOUCP")

# Ensure data directories exist
DATA_DIR.mkdir(exist_ok=True)
PDF_DIR.mkdir(exist_ok=True)
