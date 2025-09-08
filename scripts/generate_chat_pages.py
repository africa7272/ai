#!/usr/bin/env python3
import sys, runpy
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.argv = [
    "generate_pages.py",
    "--csv", str(ROOT / "pages.csv"),
    "--template", str(ROOT / "templates" / "luna_advanced.html"),
    "--out", str(ROOT / "docs"),
]
runpy.run_path(str(ROOT / "generate_pages.py"), run_name="__main__")
