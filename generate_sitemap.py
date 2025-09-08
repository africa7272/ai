<!-- PATH: /generate_sitemap.py  (корень репозитория) -->
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Единый sitemap.xml по всем страницам из pages.csv.
BASE берём из ENV SITE_BASE (или https://gorod-legends.ru).
"""

import os, csv
from datetime import datetime
from pathlib import Path

SITE_BASE = os.environ.get("SITE_BASE", "https://gorod-legends.ru").rstrip("/")
CSV_PATH  = Path("pages.csv")
OUT_PATH  = Path("docs/sitemap.xml")

def norm_url(u: str) -> str:
    u = (u or "").strip()
    if not u.startswith("/"): u = "/" + u
    if not u.endswith("/"):  u = u + "/"
    return u

def main():
    rows = []
    with open(CSV_PATH, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            u = r.get("url","").strip()
            if u:
                rows.append(norm_url(u))

    now_iso = datetime.utcnow().date().isoformat()  # YYYY-MM-DD
    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    for u in rows:
        full = f"{SITE_BASE}{u}"
        lines.append("  <url>")
        lines.append(f"    <loc>{full}</loc>")
        lines.append(f"    <lastmod>{now_iso}</lastmod>")
        lines.append("    <changefreq>weekly</changefreq>")
        lines.append("    <priority>0.7</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"[DONE] {OUT_PATH} ({len(rows)} urls)")

if __name__ == "__main__":
    main()
