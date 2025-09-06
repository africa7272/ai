#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_feeds.py — делаем sitemap.xml и rss.xml для GitHub Pages.

✓ Берём страницы из CSV (data/pages.csv | content/pages.csv | pages.csv | content.csv | data.csv)
✓ Если CSV нет — сканируем docs/**/index.html
✓ Не падаем на пустых данных, всё экранируем
✓ Домен берём из SITE_ORIGIN, бренд — из BRAND_NAME

ENV:
  SITE_ORIGIN=https://your-domain.tld
  BRAND_NAME="Luna Chat"
"""

from __future__ import annotations
import csv, html, os, sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"
CANDIDATE_CSV = [
    ROOT / "data" / "pages.csv",
    ROOT / "content" / "pages.csv",
    ROOT / "pages.csv",
    ROOT / "content.csv",
    ROOT / "data.csv",
]

SITE_ORIGIN = os.environ.get("SITE_ORIGIN", "https://example.com").rstrip("/")
BRAND_NAME = os.environ.get("BRAND_NAME", "Luna Chat")

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def esc(s: str) -> str:
    return html.escape((s or "").strip(), quote=True)

def ensure_dir(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)

def _norm_url(path: str) -> str:
    """превращаем '/foo' в абсолютный URL https://host/foo/"""
    if not path:
        return SITE_ORIGIN + "/"
    path = path if path.startswith("/") else "/" + path
    if not path.endswith("/"):
        path += "/"
    return SITE_ORIGIN + path

def read_from_csv():
    csv_path = next((p for p in CANDIDATE_CSV if p.exists()), None)
    if not csv_path:
        return []
    items = []
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, 1):
            url = (row.get("url") or "").strip()
            slug = (row.get("slug") or "").strip().strip("/")
            if not url:
                if slug:
                    url = f"/chat/{slug}/"
                else:
                    # пропускаем строку без url/slug, но не падаем
                    continue
            title = (row.get("title") or row.get("og_title") or row.get("h1") or "").strip() or url.strip("/")
            desc = (row.get("description") or row.get("og_description") or "").strip()
            items.append({
                "loc": _norm_url(url),
                "title": title,
                "desc": desc,
                "updated": now_iso(),
            })
    return items

def scan_docs():
    """Fallback: собрать страницы из docs/**/index.html"""
    if not DOCS_DIR.exists():
        return []
    items = []
    for p in DOCS_DIR.rglob("index.html"):
        rel = p.parent.relative_to(DOCS_DIR).as_posix()
        url_path = "/" + (rel + "/" if rel != "." else "")
        items.append({
            "loc": _norm_url(url_path),
            "title": rel.strip("/") or BRAND_NAME,
            "desc": "",
            "updated": now_iso(),
        })
    # уникализируем по loc
    seen = set(); out = []
    for it in items:
        if it["loc"] in seen: 
            continue
        seen.add(it["loc"]); out.append(it)
    return sorted(out, key=lambda x: x["loc"])

def write_sitemap(items):
    if not items:
        return
    out = DOCS_DIR / "sitemap.xml"
    ensure_dir(out)
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    ]
    for it in items:
        lines += [
            "  <url>",
            f"    <loc>{esc(it['loc'])}</loc>",
            f"    <lastmod>{esc(it['updated'])}</lastmod>",
            "    <changefreq>weekly</changefreq>",
            "    <priority>0.6</priority>",
            "  </url>"
        ]
    lines.append("</urlset>")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"SITEMAP ✓ {out.relative_to(ROOT)}")

def write_rss(items):
    if not items:
        return
    out = DOCS_DIR / "rss.xml"
    ensure_dir(out)
    now = now_iso()
    header = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0">',
        "  <channel>",
        f"    <title>{esc(BRAND_NAME)}</title>",
        f"    <link>{esc(SITE_ORIGIN + '/')}</link>",
        f"    <description>{esc('Обновления раздела чатов')}</description>",
        f"    <lastBuildDate>{esc(now)}</lastBuildDate>",
        "    <language>ru</language>",
    ]
    body = []
    for it in items:
        body += [
            "    <item>",
            f"      <title>{esc(it['title'])}</title>",
            f"      <link>{esc(it['loc'])}</link>",
            f"      <guid isPermaLink=\"true\">{esc(it['loc'])}</guid>",
            f"      <pubDate>{esc(it['updated'])}</pubDate>",
        ]
        if it.get("desc"):
            body.append(f"      <description>{esc(it['desc'])}</description>")
        body += [
            "    </item>"
        ]
    footer = [
        "  </channel>",
        "</rss>"
    ]
    out.write_text("\n".join(header + body + footer) + "\n", encoding="utf-8")
    print(f"RSS     ✓ {out.relative_to(ROOT)}")

def main() -> int:
    items = read_from_csv()
    if not items:
        items = scan_docs()

    # если и тут пусто — просто успешно выходим, чтобы пайплайн не падал
    if not items:
        print("ℹ️  Нет данных для фидов — пропускаю генерацию.")
        return 0

    write_sitemap(items)
    write_rss(items)
    print("✅ Feeds готово.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
