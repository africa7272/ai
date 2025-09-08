#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, csv, html, email.utils
from datetime import datetime, timezone, timedelta
from pathlib import Path

SITE_BASE = os.environ.get("SITE_BASE", "https://gorod-legends.ru").rstrip("/")
SITE_TITLE = os.environ.get("SITE_TITLE", "Luna Chat")
SITE_DESCRIPTION = os.environ.get("SITE_DESCRIPTION", "Уютное общение 24/7")
LANGUAGE = "ru"

CSV_PATH = Path("pages.csv") if Path("pages.csv").exists() else Path("data/pages.csv")
OUT_PATH = Path("rss.xml")  # <-- В КОРНЕ

def norm_url(u: str) -> str:
    u = (u or "").strip()
    if not u.startswith("/"): u = "/" + u
    if not u.endswith("/"):  u = u + "/"
    return u

def main():
    if not CSV_PATH.exists():
        raise SystemExit(f"[ERR] CSV not found: {CSV_PATH}")

    with open(CSV_PATH, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    rows_rev = list(reversed(rows))
    now = datetime.now(timezone.utc)
    last_build = email.utils.format_datetime(now)

    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0">',
        '  <channel>',
        f'    <title>{html.escape(SITE_TITLE)}</title>',
        f'    <link>{SITE_BASE}</link>',
        f'    <description>{html.escape(SITE_DESCRIPTION)}</description>',
        f'    <language>{LANGUAGE}</language>',
        f'    <lastBuildDate>{last_build}</lastBuildDate>',
        f'    <pubDate>{last_build}</pubDate>',
    ]

    for i, r in enumerate(rows_rev):
        u = (r.get("url") or "").strip()
        if not u: continue
        link = f"{SITE_BASE}{norm_url(u)}"
        title = (r.get("title") or u.strip("/")).strip()
        desc  = (r.get("description") or r.get("intro") or "").strip()
        pub   = email.utils.format_datetime(now - timedelta(minutes=i))
        out += [
            "    <item>",
            f"      <title>{html.escape(title)}</title>",
            f"      <link>{link}</link>",
            f"      <description>{html.escape(desc)}</description>",
            f"      <pubDate>{pub}</pubDate>",
            f"      <guid isPermaLink=\"true\">{link}</guid>",
            "    </item>"
        ]

    out += ["  </channel>", "</rss>"]
    OUT_PATH.write_text("\n".join(out), encoding="utf-8")
    print(f"[DONE] {OUT_PATH} ({len(rows_rev)} items)")

if __name__ == "__main__":
    main()
