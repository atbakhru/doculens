import os
from pathlib import Path

DATA = Path(os.getenv("DATA_DIR", ".data"))
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA / 'doculens.db'}")
MAX_BYTES = 20 * 1024 * 1024
MAX_PAGES = 30
MAX_PIXELS = 24_000_000
MAX_CLUSTER_PAGES = 500
MODEL_VERSION = "sift128-layout128-v1"
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"
API_TOKEN = os.getenv("API_TOKEN", "")
SIGNING_KEY = os.getenv("SIGNING_KEY", "local-demo-only-change-before-hosting")
STORAGE = os.getenv("STORAGE_BACKEND", "local")
if not DEMO_MODE and (len(API_TOKEN) < 24 or len(SIGNING_KEY) < 32 or SIGNING_KEY.startswith("local-demo")):
    raise RuntimeError("Hosted mode requires a strong API_TOKEN and SIGNING_KEY")
DATA.mkdir(parents=True, exist_ok=True)
