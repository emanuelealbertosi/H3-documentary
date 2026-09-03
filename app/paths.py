from pathlib import Path
import os
ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("DOCUMENTARIAI_DATA", str(ROOT / "data"))).resolve()
DATA.mkdir(parents=True, exist_ok=True)
JOBS = DATA / "jobs"
JOBS.mkdir(exist_ok=True)
DEFAULT_PIPELINE = str(ROOT / "pipeline")
