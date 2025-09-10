#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, csv, subprocess, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# корень репозитория: .../ai/
ROOT = Path(__file__).resolve().parents[1]

SITE_BASE = os.environ.get("SITE_BASE", "https://gorod-legends.ru").rstrip("/")
OUT_PATH  = ROOT / "sitemap.xml"

# где искать дополнительные URL’ы (если HTML еще не создан)
CSV_CANDIDATES = [ROOT / "pages.csv", ROOT / "data/pages.csv"]

# что включать/исключать при сканировании файлов
INCLUDE_DIRS = {"", "chat", "guides", "pages", "18plus"}  # можно расширять при желании
EXCLUDE_DIRS = {".git", ".github", "scripts", "templates", "assets", "static", "data", "characters", "requests"}
EXCLUDE_FILES = {"404.html"}  # 404 в карте сайта не нужен

MSK = ZoneInfo("Europe/Moscow")

def file_lastmod(path: Path) -> datetime.datetime:
    """Дата последнего коммита файла -> Europe/Moscow; запасной вариант — mtime."""
    try:
        r = subprocess.run(
            ["git", "log", "-1", "--format=%cI", str(path)],
            capture_output=True, text=True, cwd=ROOT, check=True
        )
        iso = r.stdout.strip()
        if iso:
            dt = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
            return dt.astimezone(MSK)
    except Exception:
        pass
    return datetime.datetime.fromtimestamp(path.stat().st_mtime, tz=datetime.timezone.utc).astimezone(MSK)

def path_to_url(fp: Path) -> str:
    rel = fp.relative_to(ROOT)
    parts = list(rel.parts)
    if parts and parts[0] in EXCLUDE_DIRS:
        return ""
    if parts and parts[0] not in INCLUDE_DIRS:
        # разрешаем файлы в корне (index.html и т.п.)
        if len(parts) > 1:
            return ""
    if rel.name == "index.html":
        url = "/" + "/".join(rel.parent.parts) + "/"
    else:
        url = "/" + "/".join(rel.parts)
    return url.replace("//", "/")

def urls_from_files() -> dict[str, datetime.datetime]:
    items: dict[str, datetime.datetime] = {}
    for fp in ROOT.rglob("*.html"):
        if fp.name in EXCLUDE_FILES:
            continue
        u = path_to_url(fp)
        if not u:
            continue
        items[u] = file_lastmod(fp)
    # корень сайта
    if (ROOT / "index.html").exists():
        items["/"] = file_lastmod(ROOT / "index.html")
    return items

def urls_from_csv() -> dict[str, datetime.datetime]:
    items: dict[str, datetime.datetime] = {}
    csv_path = next((p for p in CSV_CANDIDATES if p.exists()), None)
    if not csv_path:
        return items
    now_msk = datetime.datetime.now(tz=MSK)
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            u = (row.get("url") or "").strip()
            if not u:
                continue
            if not u.startswith("/"):
                u = "/" + u
            if not u.endswith("/"):
                u += "/"
            items.setdefault(u, now_msk)  # не перетираем дату, если файл уже дал более точную
    return items

def main():
    items = urls_from_files()
    items.update(urls_from_csv())

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    ]
    for u in sorted(items):
        lastmod = items[u].isoformat(timespec="seconds")
        lines += [
            "  <url>",
            f"    <loc>{SITE_BASE}{u}</loc>",
            f"    <lastmod>{lastmod}</lastmod>",
            "  </url>"
        ]
    lines.append("</urlset>")

    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Written {OUT_PATH} with {len(items)} urls")

if __name__ == "__main__":
    main()
