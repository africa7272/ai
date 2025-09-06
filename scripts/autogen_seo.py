#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
autogen_seo.py — генератор SEO-страниц и OG-изображений
Теперь поддерживает «полные» лендинги (lead, bullets, FAQ, CTA) и
умеет строить url из slug, если url отсутствует в CSV.
"""

from __future__ import annotations

import csv
import os
import re
import sys
import html
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

# ====== Параметры проекта ======
ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_CSV = [
    ROOT / "data" / "pages.csv",
    ROOT / "content" / "pages.csv",
    ROOT / "pages.csv",
    ROOT / "content.csv",
    ROOT / "data.csv",
]

OG_DIR = ROOT / "static" / "og"
DOCS_DIR = ROOT / "docs"        # GitHub Pages
GENERATE_HTML = True            # выключите, если HTML собираете другим пайплайном

SITE_NAME = "gorod-legends.ru • чат с девушкой"
OG_SIZE = (1200, 630)
OG_BG = (14, 14, 18)
OG_TITLE_FILL = (245, 245, 245)
OG_FOOTER_FILL = (170, 170, 170)
TITLE_MAX_LINES = 4

# Ссылка для CTA-кнопки (можно переопределить через переменную окружения)
CTA_HREF = os.environ.get("CTA_HREF", "/")

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

# ---------- Шаблоны HTML ----------

HTML_TEMPLATE_SIMPLE = """<!doctype html>
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
<meta name="robots" content="{robots}">
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
    <p class="lead">{lead}</p>
    <img class="og" src="/static/og/{og_slug}.png" alt="{title}">
    <footer>Обновлено: {updated_at}</footer>
  </div>
</body>
</html>
"""

HTML_TEMPLATE_FULL = """<!doctype html>
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
<meta name="robots" content="{robots}">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<style>
  :root {{
    --fg:#111; --muted:#444; --line:#eee; --cta:#111; --cta-bg:#ffd95c; --card:#fafafa;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font: 16px/1.65 -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Ubuntu,Arial,sans-serif; color:var(--fg); background:#fff; }}
  .wrap {{ max-width: 860px; margin: 48px auto; padding: 0 20px; }}
  h1 {{ font-size: 34px; line-height:1.25; margin: 0 0 14px; letter-spacing:-0.2px; }}
  p.lead {{ font-size: 18px; color:var(--muted); margin: 0 0 22px; }}
  .og {{ margin: 20px 0 28px; border-radius: 12px; width: 100%; height: auto; }}
  ul.bullets {{ padding:0; margin: 0 0 20px; list-style: none; }}
  ul.bullets li {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:10px 12px; margin: 8px 0; }}
  section.faq {{ border-top:1px solid var(--line); padding-top:18px; margin-top:12px; }}
  section.faq h2 {{ font-size:20px; margin:0 0 8px; }}
  section.faq .qa {{ margin: 12px 0; }}
  section.faq .q {{ font-weight:600; margin:0 0 4px; }}
  section.faq .a {{ margin:0; color:var(--fg); }}
  .cta-box {{ margin: 28px 0 4px; }}
  .cta {{ display:inline-block; padding:12px 18px; border-radius:12px; text-decoration:none; font-weight:600; color:var(--cta); background:var(--cta-bg); }}
  footer {{ margin: 36px 0 0; color:#666; font-size: 14px; }}
</style>
</head>
<body>
  <div class="wrap">
    <h1>{h1}</h1>
    <p class="lead">{lead}</p>
    <img class="og" src="/static/og/{og_slug}.png" alt="{title}">
    {bullets_html}
    {faq_html}
    {cta_html}
    <footer>Обновлено: {updated_at}</footer>
  </div>
</body>
</html>
"""

# ========================= Утилиты ==========================

def slugify_url_to_leaf(url: str) -> str:
    segs = [s for s in url.strip().split("/") if s]
    leaf = (segs[-1] if segs else "page").lower()
    leaf = leaf.replace("ё", "е")
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
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def esc(s: str) -> str:
    return html.escape(s or "")

def split_bullets(s: str) -> List[str]:
    if not s:
        return []
    # поддержим разделители: | или перенос строки
    parts = re.split(r"\s*\|\s*|\r?\n", s.strip())
    return [p.strip() for p in parts if p.strip()]

# ==================== Загрузка данных =======================

@dataclass
class PageRow:
    url: str
    title: str
    description: str
    og_title: str
    og_description: str
    h1: str
    intro: str
    bullets: List[str]
    faqs: List[Tuple[str, str]]
    cta: str
    robots: str  # "index,follow" | "noindex,nofollow"

    @property
    def slug(self) -> str:
        return slugify_url_to_leaf(self.url)

    @staticmethod
    def from_dict(d: Dict[str, str]) -> "PageRow":
        # url или сборка из slug
        raw_url = (d.get("url") or "").strip()
        slug = (d.get("slug") or "").strip().strip("/")
        if not raw_url:
            if slug:
                raw_url = f"/chat/{slug}/"
            else:
                raise ValueError("CSV row is missing required 'url' (и нет 'slug' для автосборки)")
        if not raw_url.startswith("/"):
            raw_url = "/" + raw_url
        if not raw_url.endswith("/"):
            raw_url += "/"

        # заголовки/описания
        title = (d.get("title") or d.get("og_title") or d.get("h1") or "").strip()
        if not title:
            raise ValueError("CSV row is missing one of ['title','og_title','h1']")
        h1 = (d.get("h1") or title).strip()
        description = (d.get("description") or d.get("og_description") or "").strip()
        intro = (d.get("intro") or "").strip()
        og_title = (d.get("og_title") or title).strip()
        og_description = (d.get("og_description") or description or intro or title).strip()

        # bullets / FAQ / CTA
        bullets = split_bullets(d.get("bullets") or "")
        faqs: List[Tuple[str, str]] = []
        for i in range(1, 11):
            q = (d.get(f"faq{i}_q") or "").strip()
            a = (d.get(f"faq{i}_a") or "").strip()
            if q and a:
                faqs.append((q, a))
        cta = (d.get("cta") or "").strip()

        # robots (noindex обработка)
        ni = (d.get("noindex") or "").strip().lower()
        is_noindex = ni in {"1", "true", "yes", "y", "да", "on"}
        robots = "noindex,nofollow" if is_noindex else "index,follow"

        return PageRow(
            url=raw_url,
            title=title,
            description=description,
            og_title=og_title,
            og_description=og_description,
            h1=h1,
            intro=intro,
            bullets=bullets,
            faqs=faqs,
            cta=cta,
            robots=robots,
        )

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
    try:
        return ImageFont.load_default()
    except Exception:
        raise RuntimeError("Не удалось загрузить ни один шрифт для Pillow.")

def _measure_text(draw, text: str, font, multiline: bool = False, **kw) -> Tuple[int, int]:
    try:
        if multiline:
            bbox = draw.multiline_textbbox((0, 0), text, font=font, **kw)
        else:
            bbox = draw.textbbox((0, 0), text, font=font, **kw)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    except AttributeError:
        if multiline:
            return draw.multiline_textsize(text, font=font, **kw)
        return draw.textsize(text, font=font, **kw)

def _wrap_text(draw, text: str, font, max_width: int, max_lines: int) -> str:
    words = re.split(r"\s+", text.strip())
    lines: List[str] = []
    cur: List[str] = []

    for idx, w in enumerate(words):
        probe = (" ".join(cur + [w])).strip()
        w_px, _ = _measure_text(draw, probe, font)
        if w_px <= max_width or not cur:
            cur.append(w)
        else:
            lines.append(" ".join(cur))
            cur = [w]
            if len(lines) >= max_lines - 1:
                tail = " ".join(cur + words[idx+1:])
                while _measure_text(draw, tail + "…", font)[0] > max_width and len(tail) > 3:
                    tail = tail[:-1].rstrip()
                lines.append((tail + "…") if tail else "…")
                break
    if cur and len(lines) < max_lines:
        lines.append(" ".join(cur))
    return "\n".join(lines[:max_lines])

def ensure_og(slug: str, title_text: str) -> Path:
    from PIL import Image, ImageDraw
    OG_DIR.mkdir(parents=True, exist_ok=True)
    out = OG_DIR / f"{slug}.png"

    img = Image.new("RGB", OG_SIZE, OG_BG)
    draw = ImageDraw.Draw(img)

    font_big = _load_first_font(FONTS_CANDIDATES_BOLD, 72)
    font_small = _load_first_font(FONTS_CANDIDATES_REG, 32)

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

    footer_text = SITE_NAME
    w_f, h_f = _measure_text(draw, footer_text, font_small)
    draw.text(((OG_SIZE[0] - w_f) // 2, OG_SIZE[1] - h_f - 36), footer_text, font=font_small, fill=OG_FOOTER_FILL)

    img.save(out, format="PNG", optimize=True)
    return out

# ============ Рендер helpers для «полного» шаблона ============

def render_bullets(items: List[str]) -> str:
    if not items:
        return ""
    lis = "\n".join(f"<li>{esc(x)}</li>" for x in items)
    return f'<ul class="bullets">\n{lis}\n</ul>'

def render_faq(faqs: List[Tuple[str, str]]) -> str:
    if not faqs:
        return ""
    blocks = []
    for q, a in faqs:
        blocks.append(
            f'<div class="qa"><div class="q">{esc(q)}</div><p class="a">{esc(a)}</p></div>'
        )
    body = "\n".join(blocks)
    return f'<section class="faq">\n<h2>Вопросы и ответы</h2>\n{body}\n</section>'

def render_cta(text: str) -> str:
    if not text:
        return ""
    return f'<div class="cta-box"><a class="cta" href="{esc(CTA_HREF)}">{esc(text)}</a></div>'

# =================== Генерация HTML ===================

def write_html(row: PageRow) -> Path:
    """
    Пишет HTML-страницу в docs/<url>/index.html (перезаписывает).
    Шаблон выбирается автоматически: full, если есть intro/bullets/faq/cta.
    """
    og_slug = row.slug
    url = row.url

    target_dir = DOCS_DIR / url.lstrip("/")
    if not str(target_dir).endswith("/"):
        target_dir = Path(str(target_dir) + "/")
    file_path = target_dir / "index.html"
    ensure_dir(file_path)

    is_full = bool(row.intro or row.bullets or row.faqs or row.cta)
    lead = row.intro or row.description or row.og_description or row.title

    if is_full:
        html_out = HTML_TEMPLATE_FULL.format(
            title=esc(row.title),
            h1=esc(row.h1 or row.title),
            description=esc(row.description or lead),
            og_title=esc(row.og_title or row.title),
            og_description=esc(row.og_description or row.description or lead),
            og_slug=esc(og_slug),
            robots=row.robots,
            lead=esc(lead),
            bullets_html=render_bullets(row.bullets),
            faq_html=render_faq(row.faqs),
            cta_html=render_cta(row.cta),
            updated_at=esc(now_utc_iso()),
        )
    else:
        html_out = HTML_TEMPLATE_SIMPLE.format(
            title=esc(row.title),
            h1=esc(row.h1 or row.title),
            description=esc(row.description or lead),
            og_title=esc(row.og_title or row.title),
            og_description=esc(row.og_description or row.description or lead),
            og_slug=esc(og_slug),
            robots=row.robots,
            lead=esc(lead),
            updated_at=esc(now_utc_iso()),
        )

    file_path.write_text(html_out, encoding="utf-8")
    return file_path

# ========================= Main =============================

def main() -> int:
    rows = load_rows()
    if not rows:
        print("ℹ️  Данных нет — ничего не сгенерировано. Проверьте путь к CSV.")
        return 0

    cnt_og = 0
    cnt_html = 0

    for row in rows:
        slug = row.slug
        og_path = ensure_og(slug, row.og_title or row.title)
        cnt_og += 1
        print(f"OG ✓ {og_path.relative_to(ROOT)}")

        if GENERATE_HTML:
            html_path = write_html(row)
            cnt_html += 1
            print(f"HTML ✓ {html_path.relative_to(ROOT)}")

    print(f"\n✅ Готово. OG: {cnt_og}  HTML: {cnt_html}  (UTC: {now_utc_iso()})")
    return 0

if __name__ == "__main__":
    sys.exit(main())
