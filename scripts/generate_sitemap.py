#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, subprocess, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]  # корень репозитория (ai/)
SITE_BASE = os.environ.get("SITE_BASE", "https://gorod-legends.ru").rstrip("/")
OUT_PATH  = ROOT / "sitemap.xml"

# По умолчанию CSV не используем (0). Поставьте 1, если хотите ДОБАВЛЯТЬ урлы из CSV.
INCLUDE_CSV = os.environ.get("SITEMAP_INCLUDE_CSV", "0") == "1"
CSV_CANDIDATES = [ROOT / "pages.csv", ROOT / "data" / "pages.csv"]

# Папки, которые надо ПРОПУСТИТЬ при сканировании HTML
EXCLUDE_DIRS = {
    ".git", ".github", "scripts", "templates", "assets", "static",
    "data", "requests", "node_modules", "docs"  # старое размещение
}

# Файлы, которые точно не попадут в карту
EXCLUDE_FILES = {"404.html"}

MSK = ZoneInfo("Europe/Moscow")

def is_excluded(rel: Path) -> bool:
    """Путь (относительно ROOT) попадает в исключённые папки?"""
    return any(part in EXCLUDE_DIRS for part in rel.parts)

def file_lastmod(path: Path) -> datetime.datetime:
    """Дата последнего коммита файла -> Europe/Moscow; fallback — mtime."""
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
    # если нет истории (маловероятно) — берём mtime
    return datetime.datetime.fromtimestamp(path.stat().st_mtime, tz=datetime.timezone.utc).astimezone(MSK)

def rel_to_url(rel: Path) -> str:
    """Преобразовать относительный путь HTML в канонический URL."""
    if rel.name == "index.html":
        url = "/" + "/".join(rel.parent.parts) + "/"
    else:
        url = "/" + "/".join(rel.parts)
    url = url.replace("//", "/")
    if url == "//":
        url = "/"
    return url

def urls_from_files() -> dict[str, datetime.datetime]:
    items: dict[str, datetime.datetime] = {}
    for fp in ROOT.rglob("*.html"):
        rel = fp.relative_to(ROOT)
        if is_excluded(rel):
            continue
        if fp.name in EXCLUDE_FILES:
            continue
        u = rel_to_url(rel)
        if not u:
            continue
        items[u] = file_lastmod(fp)
    # Корень сайта (/) если есть index.html в корне
    if (ROOT / "index.html").exists():
        items["/"] = file_lastmod(ROOT / "index.html")
    return items

def urls_from_csv() -> dict[str, datetime.datetime]:
    """Опционально: добавить URL из CSV (если нужно). lastmod = сейчас (MSK)."""
    import csv
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
            if not u.endswith("/") and u.endswith(".html") is False:
                u += "/"
            items.setdefault(u, now_msk)
    return items

def main():
    # 1) Берём все реальные HTML из репозитория
    items = urls_from_files()

    # 2) (Опционально) Добавляем из CSV — только как дополнение
    if INCLUDE_CSV:
        items.update(urls_from_csv())

    # 3) Пишем sitemap.xml
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
    print(f"[OK] sitemap.xml: {len(items)} urls -> {OUT_PATH}")

if __name__ == "__main__":
    main()
