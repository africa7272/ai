#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
autogen_seo.py — генератор SEO-страниц «под ключ» + OG-изображений.

Делает Готовые лендинги в едином стиле сайта:
• URL берётся из `url`, либо автоматически строится из `slug` → /chat/<slug>/
• Красивый «полный» шаблон: lead, буллеты, FAQ, CTA-кнопки (ссылка на бота — на каждой странице)
• Внешний CSS (/static/seo.css) — создаётся, если его нет (правишь 1 файл — обновляются все страницы)
• OG 1200×630, Open Graph, Twitter Card, canonical, robots/noindex, JSON-LD FAQ
• Перезаписывает существующие HTML и OG (чтобы исправить прежние «скучные» заглушки)

CSV — ищется в порядке:
  data/pages.csv, content/pages.csv, pages.csv, content.csv, data.csv

Минимум для строки: (title | og_title | h1) + (url | slug)
Поддерживаемые колонки (любой подмножество):
  url, slug, title, h1, description, og_title, og_description, intro, bullets,
  faq1_q, faq1_a, ... faq10_q, faq10_a, cta, cta_href, noindex, keyword, canonical

Переменные окружения (необязательно):
  SITE_ORIGIN=https://gorod-legends.ru
  CTA_HREF=https://t.me/your_bot
  CTA_TEXT="Открыть чат в Telegram"
"""

from __future__ import annotations

import csv, os, re, sys, html, json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

# ========= Конфиг проекта =========
ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_CSV = [
    ROOT / "data" / "pages.csv",
    ROOT / "content" / "pages.csv",
    ROOT / "pages.csv",
    ROOT / "content.csv",
    ROOT / "data.csv",
]

DOCS_DIR = ROOT / "docs"
STATIC_DIR = ROOT / "static"
OG_DIR = STATIC_DIR / "og"
CSS_PATH = STATIC_DIR / "seo.css"

GENERATE_HTML = True

SITE_NAME = "gorod-legends.ru • чат с девушкой"
SITE_ORIGIN = os.environ.get("SITE_ORIGIN", "https://gorod-legends.ru").rstrip("/")
ALWAYS_ADD_CTA = True  # ← ссылка на бота будет на каждой странице
DEFAULT_CTA_TEXT = os.environ.get("CTA_TEXT", "Открыть чат в Telegram")
GLOBAL_CTA_HREF = os.environ.get("CTA_HREF", "/go/telegram")

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

# ========= HTML-шаблон =========

HTML_HEAD = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>{title}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{description}">
{meta_keywords}
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{og_title}">
<meta property="og:description" content="{og_description}">
<meta property="og:type" content="article">
<meta property="og:image" content="{og_image}">
<meta property="og:url" content="{canonical}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{og_title}">
<meta name="twitter:description" content="{og_description}">
<meta name="twitter:image" content="{og_image}">
<meta name="robots" content="{robots}">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="/static/seo.css?v=1">
<script type="application/ld+json">
{faq_json_ld}
</script>
</head>
<body>
<header class="seo-header">
  <div class="seo-max">
    <a class="seo-brand" href="/">gorod-legends.ru</a>
    <a class="seo-top-cta" href="{cta_href}">{cta_text}</a>
  </div>
</header>
"""

HTML_FOOT = """
<footer class="seo-footer">
  <div class="seo-max">
    <div class="seo-updated">Обновлено: {updated_at}</div>
    <div class="seo-copy">© {year} gorod-legends.ru</div>
  </div>
</footer>
</body>
</html>
"""

HTML_BODY = """
<main class="seo-main">
  <div class="seo-max">
    <article class="seo-article">
      <h1 class="seo-h1">{h1}</h1>
      <p class="seo-lead">{lead}</p>

      <img class="seo-og" src="{og_image_path}" alt="{title}">

      {bullets_html}
      {faq_html}

      <div class="seo-cta-bar">
        <a class="seo-cta" href="{cta_href}">{cta_text}</a>
      </div>
    </article>
  </div>
</main>
"""

# ========= Утилиты =========

def find_first_existing(paths: Iterable[Path]) -> Optional[Path]:
    return next((p for p in paths if p.exists()), None)

def ensure_dir(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)

def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def esc(s: str) -> str:
    return html.escape((s or "").strip())

def slugify_url_to_leaf(url: str) -> str:
    segs = [s for s in url.strip().split("/") if s]
    leaf = (segs[-1] if segs else "page").lower()
    leaf = leaf.replace("ё", "е")
    leaf = re.sub(r"[^a-z0-9\-_]+", "-", leaf)
    leaf = re.sub(r"-{2,}", "-", leaf).strip("-")
    return leaf or "page"

def split_bullets(s: str) -> List[str]:
    if not s:
        return []
    parts = re.split(r"\s*\|\s*|\r?\n", s.strip())
    return [p for p in (x.strip() for x in parts) if p]

def is_true(val: str) -> bool:
    return (val or "").strip().lower() in {"1","true","yes","y","да","on"}

# ========= Модель строки =========

@dataclass
class PageRow:
    url: str
    title: str
    h1: str
    description: str
    og_title: str
    og_description: str
    intro: str
    bullets: List[str]
    faqs: List[Tuple[str, str]]
    cta_text: str
    cta_href: str
    robots: str
    keyword: str
    canonical: str

    @property
    def slug(self) -> str:
        return slugify_url_to_leaf(self.url)

    @staticmethod
    def from_dict(d: Dict[str, str]) -> "PageRow":
        # URL / SLUG
        raw_url = (d.get("url") or "").strip()
        slug = (d.get("slug") or "").strip().strip("/")
        if not raw_url:
            if not slug:
                raise ValueError("CSV row is missing required 'url' (и нет 'slug' для автосборки)")
            raw_url = f"/chat/{slug}/"
        if not raw_url.startswith("/"): raw_url = "/" + raw_url
        if not raw_url.endswith("/"): raw_url += "/"

        # Заголовки и описания
        title = (d.get("title") or d.get("og_title") or d.get("h1") or "").strip()
        if not title:
            raise ValueError("CSV row is missing one of ['title','og_title','h1']")
        h1 = (d.get("h1") or title).strip()
        description = (d.get("description") or d.get("og_description") or "").strip()
        intro = (d.get("intro") or "").strip()
        og_title = (d.get("og_title") or title).strip()
        og_description = (d.get("og_description") or description or intro or title).strip()

        # Контентные блоки
        bullets = split_bullets(d.get("bullets") or "")
        faqs: List[Tuple[str, str]] = []
        for i in range(1, 11):
            q = (d.get(f"faq{i}_q") or "").strip()
            a = (d.get(f"faq{i}_a") or "").strip()
            if q and a:
                faqs.append((q, a))

        # CTA (на каждой странице)
        cta_text = (d.get("cta") or "").strip()
        if ALWAYS_ADD_CTA and not cta_text:
            cta_text = DEFAULT_CTA_TEXT
        cta_href = (d.get("cta_href") or "").strip() or GLOBAL_CTA_HREF

        # Индексация/мета
        robots = "noindex,nofollow" if is_true(d.get("noindex")) else "index,follow"
        keyword = (d.get("keyword") or "").strip()
        canonical = (d.get("canonical") or "").strip()
        if not canonical:
            canonical = f"{SITE_ORIGIN}{raw_url}"

        return PageRow(
            url=raw_url, title=title, h1=h1,
            description=description, og_title=og_title, og_description=og_description,
            intro=intro, bullets=bullets, faqs=faqs,
            cta_text=cta_text, cta_href=cta_href,
            robots=robots, keyword=keyword, canonical=canonical
        )

# ========= Загрузка CSV =========

def load_rows() -> List[PageRow]:
    csv_path = find_first_existing(CANDIDATE_CSV)
    if not csv_path:
        print("⚠️  CSV с данными не найден. Пропускаю генерацию.", file=sys.stderr)
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

# ========= OG (Pillow) =========

def _load_first_font(candidates: List[str], size: int):
    from PIL import ImageFont
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()

def _measure_text(draw, text: str, font, multiline: bool = False, **kw) -> Tuple[int, int]:
    try:
        if multiline:
            bbox = draw.multiline_textbbox((0,0), text, font=font, **kw)
        else:
            bbox = draw.textbbox((0,0), text, font=font, **kw)
        return bbox[2]-bbox[0], bbox[3]-bbox[1]
    except AttributeError:
        if multiline: return draw.multiline_textsize(text, font=font, **kw)
        return draw.textsize(text, font=font, **kw)

def _wrap_text(draw, text: str, font, max_width: int, max_lines: int) -> str:
    words = re.split(r"\s+", text.strip())
    lines: List[str] = []; cur: List[str] = []
    for idx, w in enumerate(words):
        probe = (" ".join(cur + [w])).strip()
        w_px, _ = _measure_text(draw, probe, font)
        if w_px <= max_width or not cur:
            cur.append(w)
        else:
            lines.append(" ".join(cur)); cur = [w]
            if len(lines) >= max_lines - 1:
                tail = " ".join(cur + words[idx+1:])
                while _measure_text(draw, tail + "…", font)[0] > max_width and len(tail) > 3:
                    tail = tail[:-1].rstrip()
                lines.append((tail + "…") if tail else "…"); break
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
    x_title = (OG_SIZE[0] - w_title)//2
    y_title = (OG_SIZE[1] - h_title)//2 - 16

    draw.multiline_text((x_title, y_title), wrapped, font=font_big, fill=OG_TITLE_FILL, spacing=6, align="center")

    footer_text = SITE_NAME
    w_f, h_f = _measure_text(draw, footer_text, font_small)
    draw.text(((OG_SIZE[0] - w_f)//2, OG_SIZE[1]-h_f-36), footer_text, font=font_small, fill=OG_FOOTER_FILL)

    img.save(out, format="PNG", optimize=True)
    return out

# ========= Рендер HTML =========

def render_bullets(items: List[str]) -> str:
    if not items: return ""
    lis = "\n".join(f"<li>{esc(x)}</li>" for x in items)
    return f'<ul class="seo-bullets">\n{lis}\n</ul>'

def render_faq(faqs: List[Tuple[str, str]]) -> Tuple[str, str]:
    """Возвращает (faq_html, faq_json_ld)."""
    if not faqs:
        return "", "[]"
    blocks = []
    schema_items = []
    for q, a in faqs:
        blocks.append(f'<div class="seo-qa"><div class="seo-q">{esc(q)}</div><p class="seo-a">{esc(a)}</p></div>')
        schema_items.append({
            "@type": "Question",
            "name": q,
            "acceptedAnswer": {
                "@type": "Answer",
                "text": a
            }
        })
    body = "\n".join(blocks)
    faq_html = f'<section class="seo-faq">\n<h2 class="seo-h2">Вопросы и ответы</h2>\n{body}\n</section>'
    faq_json_ld = json.dumps({"@context":"https://schema.org","@type":"FAQPage","mainEntity":schema_items}, ensure_ascii=False)
    return faq_html, faq_json_ld

def write_html(row: PageRow) -> Path:
    # Путь docs/<url>/index.html
    target_dir = DOCS_DIR / row.url.lstrip("/")
    if not str(target_dir).endswith("/"):
        target_dir = Path(str(target_dir) + "/")
    file_path = target_dir / "index.html"
    ensure_dir(file_path)

    og_slug = row.slug
    og_image_rel = f"/static/og/{og_slug}.png"
    og_image_abs = f"{SITE_ORIGIN}{og_image_rel}"

    # Контент
    lead = row.intro or row.description or row.og_description or row.title
    bullets_html = render_bullets(row.bullets)
    faq_html, faq_json_ld = render_faq(row.faqs)

    # Мета
    meta_keywords = f'<meta name="keywords" content="{esc(row.keyword)}">' if row.keyword else ""

    head = HTML_HEAD.format(
        title=esc(row.title),
        description=esc(row.description or lead),
        meta_keywords=meta_keywords,
        canonical=esc(row.canonical),
        og_title=esc(row.og_title or row.title),
        og_description=esc(row.og_description or row.description or lead),
        og_image=esc(og_image_abs),
        robots=row.robots,
        faq_json_ld=faq_json_ld,
        cta_href=esc(row.cta_href or GLOBAL_CTA_HREF),
        cta_text=esc(row.cta_text or DEFAULT_CTA_TEXT),
    )

    body = HTML_BODY.format(
        h1=esc(row.h1 or row.title),
        lead=esc(lead),
        og_image_path=esc(og_image_rel),
        title=esc(row.title),
        bullets_html=bullets_html,
        faq_html=faq_html,
        cta_href=esc(row.cta_href or GLOBAL_CTA_HREF),
        cta_text=esc(row.cta_text or DEFAULT_CTA_TEXT),
    )

    foot = HTML_FOOT.format(
        updated_at=esc(now_utc_iso()),
        year=datetime.now().year
    )

    html_out = head + body + foot
    file_path.write_text(html_out, encoding="utf-8")
    return file_path

# ========= CSS (создаём, если нет) =========

DEFAULT_CSS = """
:root{
  --seo-bg:#0e0e12; --seo-fg:#f5f7fb; --seo-muted:#a6aec8;
  --seo-accent:#ffd95c; --seo-card:#151720; --seo-line:#262a36;
  --seo-radius:16px; --seo-max:960px;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{background:var(--seo-bg);color:var(--seo-fg);font:16px/1.65 -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Ubuntu,Arial,sans-serif}

.seo-max{max-width:var(--seo-max);margin:0 auto;padding:0 20px}

/* Header */
.seo-header{position:sticky;top:0;z-index:10;background:rgba(14,14,18,.7);backdrop-filter:saturate(150%) blur(10px);border-bottom:1px solid var(--seo-line)}
.seo-header .seo-max{display:flex;align-items:center;gap:16px;justify-content:space-between;height:56px}
.seo-brand{font-weight:700;text-decoration:none;color:var(--seo-fg);letter-spacing:.2px}
.seo-top-cta{display:inline-block;padding:8px 14px;border-radius:12px;text-decoration:none;font-weight:600;color:#111;background:var(--seo-accent)}

/* Article */
.seo-main{padding:28px 0 40px}
.seo-article{background:linear-gradient(180deg,rgba(255,255,255,.02),rgba(255,255,255,0));border:1px solid var(--seo-line);border-radius:var(--seo-radius);padding:20px 18px}
.seo-h1{font-size:34px;line-height:1.25;margin:0 0 10px;letter-spacing:-.2px}
.seo-lead{font-size:18px;color:var(--seo-muted);margin:0 0 16px}
.seo-og{display:block;width:100%;height:auto;border-radius:12px;border:1px solid var(--seo-line);margin:14px 0 18px}

/* Bullets */
.seo-bullets{list-style:none;margin:0 0 18px;padding:0;display:grid;grid-template-columns:1fr 1fr;gap:10px}
.seo-bullets li{background:var(--seo-card);border:1px solid var(--seo-line);border-radius:12px;padding:10px 12px}
@media (max-width:680px){.seo-bullets{grid-template-columns:1fr}}

/* FAQ */
.seo-faq{border-top:1px solid var(--seo-line);padding-top:16px;margin-top:8px}
.seo-h2{font-size:20px;margin:0 0 8px}
.seo-qa{margin:12px 0;padding:10px 12px;border:1px dashed var(--seo-line);border-radius:12px;background:rgba(255,255,255,.02)}
.seo-q{font-weight:700;margin:0 0 6px}
.seo-a{margin:0;color:var(--seo-fg)}

/* CTA */
.seo-cta-bar{display:flex;justify-content:center;margin:22px 0 4px}
.seo-cta{display:inline-block;padding:12px 18px;border-radius:14px;text-decoration:none;font-weight:700;color:#111;background:var(--seo-accent);box-shadow:0 4px 16px rgba(255,217,92,.25)}
.seo-cta:hover{transform:translateY(-1px)}

/* Footer */
.seo-footer{border-top:1px solid var(--seo-line);padding:16px 0;color:var(--seo-muted)}
.seo-footer .seo-max{display:flex;gap:12px;justify-content:space-between;align-items:center;flex-wrap:wrap}
.seo-updated{font-size:14px}
.seo-copy{font-size:14px}
@media (max-width:480px){.seo-h1{font-size:28px}}
""".strip() + "\n"

def ensure_css():
    CSS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not CSS_PATH.exists():
        CSS_PATH.write_text(DEFAULT_CSS, encoding="utf-8")
        print(f"CSS ✓ {CSS_PATH.relative_to(ROOT)} (создан)")

# ========= Main =========

def main() -> int:
    ensure_css()
    rows = load_rows()
    if not rows:
        print("ℹ️  Данных нет — ничего не сгенерировано.")
        return 0

    cnt_og = 0; cnt_html = 0
    for row in rows:
        # OG
        og_path = ensure_og(row.slug, row.og_title or row.title)
        cnt_og += 1
        print(f"OG ✓ {og_path.relative_to(ROOT)}")

        # HTML
        if GENERATE_HTML:
            html_path = write_html(row)
            cnt_html += 1
            print(f"HTML ✓ {html_path.relative_to(ROOT)}")

    print(f"\n✅ Готово. OG: {cnt_og}  HTML: {cnt_html}  (UTC: {now_utc_iso()})")
    return 0

if __name__ == "__main__":
    sys.exit(main())
