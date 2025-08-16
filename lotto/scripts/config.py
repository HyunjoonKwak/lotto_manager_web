import os
from pathlib import Path
from dotenv import load_dotenv

ENV_DIR = Path(__file__).resolve().parent
load_dotenv(ENV_DIR / ".env")

APP_ROOT     = Path(os.getenv("APP_ROOT", "/volume1/web/lotto"))
DB_PATH      = str(Path(os.getenv("DB_PATH", APP_ROOT / "database" / "lotto.db")))
SCRIPTS_PATH = str(Path(os.getenv("SCRIPTS_PATH", APP_ROOT / "scripts")))
LOG_DIR      = str(Path(os.getenv("LOG_DIR", APP_ROOT / "logs")))
FLASK_HOST   = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT   = int(os.getenv("FLASK_PORT", "8080"))

def ensure_dirs():
    for p in [APP_ROOT, Path(DB_PATH).parent, Path(SCRIPTS_PATH), Path(LOG_DIR)]:
        Path(p).mkdir(parents=True, exist_ok=True)
