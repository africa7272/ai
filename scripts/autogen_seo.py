#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
autogen_seo.py — генератор SEO-страниц и OG-изображений
Совместим с Pillow 8–11 (без textsize), TZ-aware время, безопасные шрифты.

Что делает:
1) Ищет CSV с данными страниц (порядок поиска ниже).
2) Для каждой строки:
   - берёт URL (обязателен) и заголовок (title|og_title|h1).
   - генерирует OG-картинку 1200x630 в static/og/<slug>.png
   - (опционально) кладёт простую HTML-страницу в docs/<url>/index.html
     (если не нужно — выставьте GENERATE_HTML=False)

CSV — подхватываются любые из:
  - data/pages.csv
  - content/pages.csv
  - pages.csv
  - content.csv
  - data.csv

Минимальные колонки: url + (title | og_title | h1)
Доп.: description | og_description

Зависимости: Pillow (и любой truetype-шрифт в системе).
"""

from __future__ import annotations

import csv
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

# ====== Параметры проекта (можете под себя подправить) ======
ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_CSV = [
    ROOT / "data" / "pages.csv",
    ROOT / "content" / "pages.csv",
    ROOT / "pages.csv",
    ROOT / "content.csv",
    ROOT / "data.csv",
]

OG_DIR = ROOT / "static" / "og"
DOCS_DIR = ROOT / "docs"        # GitHub Pages часто смотрит сюда
GENERATE_HTML = True            # если страницы собираете другим пайплайном — поставьте False

SITE_NAME = "gorod-legends.ru • чат с девушкой"
OG_SIZE = (1200, 630)
OG_BG = (14, 14, 18)
OG_TITLE_FILL = (245, 245, 245)
OG_FOOTER_FILL = (170, 170, 170)
TITLE_MAX_LINES = 4

FONTS_CANDIDATES_BOLD = [
    "assets/Inter-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]
FONTS_CANDIDATES_REG = [
    "assets/Inter-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]

HTML_TEMPLATE = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>{title}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{description}">
<meta property="og:title" content="{og_title}">
<meta property="og:description" content="{og_description}">
<meta property="og:type" content="article">
<meta property="og:image" content="/static/og/{og_slug}.png">
<meta name="robots" content="index,follow">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<style>
  body {{ margin:0; font: 16px/1.6 -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Ubuntu,Arial,sans-serif; color:#111; }}
  .wrap {{ max-width: 860px; margin: 48px auto; padding: 0 20px; }}
  h1 {{ font-size: 32px; line-height:1.25; margin: 0 0 16px; }}
  p.lead {{ font-size: 18px; color:#444; margin: 0 0 20px; }}
  .og {{ margin: 24px 0; border-radius: 12px; width: 100%; height: auto; }}
  footer {{ margin: 48px 0 0; color:#666; font-size: 14px; }}
</style>
</head>
<body>
  <div class="wrap">
    <h1>{h1}</h1>
    <p class="lead">{description}</p>
    <img class="og" src="/static/og/{og_slug}.png" alt="{title}">
    <footer>Обновлено: {updated_at}</footer>
  </div>
</body>
</html>
"""

# ========================= Утилиты ==========================

def slugify_url_to_leaf(url: str) -> str:
    """
    Берём последний сегмент URL (без /) и нормализуем под имя файла.
    /chat/devushka-online/  -> 'devushka-online'
    """
    leaf = [seg for seg in url.strip().split("/") if seg]
    leaf = leaf[-1] if leaf else "page"
    leaf = leaf.lower()
    leaf = leaf.replace("ё", "е")
    # только латиница/цифры/-/_
    leaf = re.sub(r"[^a-z0-9\-_]+", "-", leaf)
    leaf = re.sub(r"-{2,}", "-", leaf).strip("-")
    return leaf or "page"


def find_first_existing(paths: Iterable[Path]) -> Optional[Path]:
    for p in paths:
        if p.exists():
            return p
    return None


def ensure_dir(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)


def now_utc_iso() -> str:
    # TZ-aware (устраняет DeprecationWarning по utcnow)
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ==================== Загрузка данных =======================

@dataclass
class PageRow:
    url: str
    title: str
    description: str
    og_title: str
    og_description: str

    @property
    def slug(self) -> str:
        return slugify_url_to_leaf(self.url)

    @staticmethod
    def from_dict(d: Dict[str, str]) -> "PageRow":
        url = (d.get("url") or "").strip()
        if not url:
            raise ValueError("CSV row is missing required 'url'")

        # выбираем лучший доступный заголовок
        title = (d.get("title") or d.get("og_title") or d.get("h1") or "").strip()
        if not title:
            raise ValueError("CSV row is missing one of ['title','og_title','h1']")

        description = (d.get("description") or d.get("og_description") or "").strip()
        og_title = (d.get("og_title") or title).strip()
        og_description = (d.get("og_description") or description or title).strip()

        return PageRow(url=url, title=title, description=description,
                       og_title=og_title, og_description=og_description)


def load_rows() -> List[PageRow]:
    csv_path = find_first_existing(CANDIDATE_CSV)
    if not csv_path:
        print("⚠️  CSV с данными не найден. Пропускаю генерацию страниц, оставлю лишь OG для safety.", file=sys.stderr)
        return []

    rows: List[PageRow] = []
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, d in enumerate(reader, 1):
            try:
                rows.append(PageRow.from_dict(d))
            except Exception as e:
                print(f"⚠️  Строка {i} пропущена: {e}", file=sys.stderr)
    print(f"✔ Найдено строк: {len(rows)} из файла {csv_path.relative_to(ROOT)}")
    return rows


# =================== Генерация OG (Pillow) ==================

def _load_first_font(candidates: List[str], size: int):
    from PIL import ImageFont
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    # системный запасной
    try:
        return ImageFont.load_default()
    except Exception:
        raise RuntimeError("Не удалось загрузить ни один шрифт для Pillow.")


def _measure_text(draw, text: str, font, multiline: bool = False, **kw) -> Tuple[int, int]:
    """
    Универсальная функция измерения текста:
    Pillow >= 10: textbbox/multiline_textbbox
    Pillow <= 9:  textsize/multiline_textsize
    """
    try:
        if multiline:
            bbox = draw.multiline_textbbox((0, 0), text, font=font, **kw)
        else:
            bbox = draw.textbbox((0, 0), text, font=font, **kw)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    except AttributeError:
        # старые версии Pillow
        if multiline:
            return draw.multiline_textsize(text, font=font, **kw)
        return draw.textsize(text, font=font, **kw)


def _wrap_text(draw, text: str, font, max_width: int, max_lines: int) -> str:
    """
    Грубый перенос по словам так, чтобы уложиться в max_width и max_lines.
    """
    words = re.split(r"\s+", text.strip())
    lines: List[str] = []
    cur: List[str] = []

    for w in words:
        probe = (" ".join(cur + [w])).strip()
        w_px, _ = _measure_text(draw, probe, font)
        if w_px <= max_width or not cur:
            cur.append(w)
        else:
            lines.append(" ".join(cur))
            cur = [w]
            if len(lines) >= max_lines - 1:
                # остаток в последнюю строку и обрезаем при необходимости
                tail = " ".join(cur + words[words.index(w)+1:])
                while _measure_text(draw, tail + "…", font)[0] > max_width and len(tail) > 3:
                    tail = tail[:-1].rstrip()
                lines.append(tail + "…")
                break
    if cur and len(lines) < max_lines:
        lines.append(" ".join(cur))

    return "\n".join(lines[:max_lines])


def ensure_og(slug: str, title_text: str) -> Path:
    """
    Создаёт OG-картинку для страницы со слагом `slug` и заголовком `title_text`.
    Возвращает путь к PNG.
    """
    from PIL import Image, ImageDraw

    OG_DIR.mkdir(parents=True, exist_ok=True)
    out = OG_DIR / f"{slug}.png"

    img = Image.new("RGB", OG_SIZE, OG_BG)
    draw = ImageDraw.Draw(img)

    # загрузка шрифтов
    font_big = _load_first_font(FONTS_CANDIDATES_BOLD, 72)
    font_small = _load_first_font(FONTS_CANDIDATES_REG, 32)

    # перенос и центрирование заголовка
    max_title_width = int(OG_SIZE[0] * 0.86)
    wrapped = _wrap_text(draw, title_text, font_big, max_title_width, TITLE_MAX_LINES)
    w_title, h_title = _measure_text(draw, wrapped, font_big, multiline=True, spacing=6)
    x_title = (OG_SIZE[0] - w_title) // 2
    y_title = (OG_SIZE[1] - h_title) // 2 - 16

    draw.multiline_text(
        (x_title, y_title),
        wrapped,
        font=font_big,
        fill=OG_TITLE_FILL,
        spacing=6,
        align="center",
    )

    # футер/домен
    footer_text = SITE_NAME
    w_f, h_f = _measure_text(draw, footer_text, font_small)
    draw.text(((OG_SIZE[0] - w_f) // 2, OG_SIZE[1] - h_f - 36), footer_text, font=font_small, fill=OG_FOOTER_FILL)

    img.save(out, format="PNG", optimize=True)
    return out


# =================== Генерация HTML (опц.) ==================

def write_html(row: PageRow) -> Path:
    """
    Пишет простую HTML-страницу в docs/<url>/index.html
    """
    og_slug = row.slug
    url = row.url

    # путь вида docs/chat/devushka-online/index.html
    target_dir = DOCS_DIR / url.lstrip("/")
    if not str(target_dir).endswith("/"):
        target_dir = Path(str(target_dir) + "/")
    file_path = target_dir / "index.html"
    ensure_dir(file_path)

    html = HTML_TEMPLATE.format(
        title=row.title,
        h1=row.title,
        description=row.description or row.og_description or row.title,
        og_title=row.og_title or row.title,
        og_description=row.og_description or row.description or row.title,
        og_slug=og_slug,
        updated_at=now_utc_iso(),
    )

    file_path.write_text(html, encoding="utf-8")
    return file_path


# ========================= Main =============================

def main() -> int:
    rows = load_rows()

    # Если CSV не найден — не падаем: просто выходим успешно (чтобы Action не валился)
    if not rows:
        print("ℹ️  Данных нет — ничего не сгенерировано. Проверьте путь к CSV.")
        return 0

    cnt_og = 0
    cnt_html = 0

    for row in rows:
        slug = row.slug
        # OG
        og_path = ensure_og(slug, row.og_title or row.title)
        cnt_og += 1
        print(f"OG ✓ {og_path.relative_to(ROOT)}")

        # HTML (если включено)
        if GENERATE_HTML:
            html_path = write_html(row)
            cnt_html += 1
            print(f"HTML ✓ {html_path.relative_to(ROOT)}")

    print(f"\n✅ Готово. OG: {cnt_og}  HTML: {cnt_html}  (UTC: {now_utc_iso()})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
