#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, csv
from datetime import datetime
from pathlib import Path

SITE_BASE = os.environ.get("SITE_BASE", "https://gorod-legends.ru").rstrip("/")
CSV_PATH  = Path("pages.csv") if Path("pages.csv").exists() else Path("data/pages.csv")
OUT_PATH  = Path("sitemap.xml")  # <-- В КОРНЕ

def norm_url(u: str) -> str:
    u = (u or "").strip()
    if not u.startswith("/"): u = "/" + u
    if not u.endswith("/"):  u = u + "/"
    return u

def main():
    if not CSV_PATH.exists():
        raise SystemExit(f"[ERR] CSV not found: {CSV_PATH}")

    urls = []
    with open(CSV_PATH, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            u = r.get("url","").strip()
            if u: urls.append(norm_url(u))

    now_iso = datetime.utcnow().date().isoformat()
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    ]
    for u in urls:
        lines += [
            "  <url>",
            f"    <loc>{SITE_BASE}{u}</loc>",
            f"    <lastmod>{now_iso}</lastmod>",
            "    <changefreq>weekly</changefreq>",
            "    <priority>0.7</priority>",
            "  </url>"
        ]
    lines.append("</urlset>")

    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"[DONE] {OUT_PATH} ({len(urls)} urls)")

if __name__ == "__main__":
    main()
