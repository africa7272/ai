#!/usr/bin/env python3
import runpy
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
runpy.run_path(str(ROOT / "generate_rss.py"), run_name="__main__")
