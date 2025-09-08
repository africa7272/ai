<!-- PATH: /generate_rss.py  (корень репозитория) -->
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Единый RSS (rss.xml) по всем страницам из pages.csv.
Сортировка — по порядку в CSV (последние строки = более новые).
BASE берём из ENV SITE_BASE (или https://gorod-legends.ru).
"""

import os, csv, html, email.utils
from datetime import datetime, timezone, timedelta
from pathlib import Path

SITE_BASE = os.environ.get("SITE_BASE", "https://gorod-legends.ru").rstrip("/")
SITE_TITLE = os.environ.get("SITE_TITLE", "Luna Chat")
SITE_DESCRIPTION = os.environ.get("SITE_DESCRIPTION", "Уютное общение 24/7")
LANGUAGE = "ru"

CSV_PATH = Path("pages.csv")
OUT_PATH = Path("docs/rss.xml")

def norm_url(u: str) -> str:
    u = (u or "").strip()
    if not u.startswith("/"): u = "/" + u
    if not u.endswith("/"):  u = u + "/"
    return u

def main():
    with open(CSV_PATH, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Новые — снизу CSV
    rows_rev = list(reversed(rows))
    now = datetime.now(timezone.utc)
    last_build = email.utils.format_datetime(now)

    out = []
    out.append('<?xml version="1.0" encoding="UTF-8"?>')
    out.append('<rss version="2.0">')
    out.append('  <channel>')
    out.append(f'    <title>{html.escape(SITE_TITLE)}</title>')
    out.append(f'    <link>{SITE_BASE}</link>')
    out.append(f'    <description>{html.escape(SITE_DESCRIPTION)}</description>')
    out.append(f'    <language>{LANGUAGE}</language>')
    out.append(f'    <lastBuildDate>{last_build}</lastBuildDate>')
    out.append(f'    <pubDate>{last_build}</pubDate>')

    for i, r in enumerate(rows_rev):
        u = (r.get("url") or "").strip()
        if not u:
            continue
        u = norm_url(u)
        link = f"{SITE_BASE}{u}"
        title = (r.get("title") or u.strip("/")).strip()
        desc  = (r.get("description") or r.get("intro") or "").strip()
        dt    = now - timedelta(minutes=i)
        pub   = email.utils.format_datetime(dt)

        out.append("    <item>")
        out.append(f"      <title>{html.escape(title)}</title>")
        out.append(f"      <link>{link}</link>")
        out.append(f"      <description>{html.escape(desc)}</description>")
        out.append(f"      <pubDate>{pub}</pubDate>")
        out.append(f"      <guid isPermaLink=\"true\">{link}</guid>")
        out.append("    </item>")

    out.append("  </channel>")
    out.append("</rss>")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(out), encoding="utf-8")
    print(f"[DONE] {OUT_PATH} ({len(rows_rev)} items)")

if __name__ == "__main__":
    main()
