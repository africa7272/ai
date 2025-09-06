#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import csv, os, re, sys, html, json, random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

# ========= Конфиг =========
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

SITE_ORIGIN = os.environ.get("SITE_ORIGIN", "https://gorod-legends.ru").rstrip("/")
SITE_NAME   = os.environ.get("BRAND_NAME", "Luna Chat")
DEFAULT_CTA_TEXT = os.environ.get("CTA_TEXT", "Открыть в Telegram")
GLOBAL_CTA_HREF  = os.environ.get("CTA_HREF",  "/go/telegram")

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

# ========= Шаблоны (НЕ f-строки!) =========
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
<link rel="stylesheet" href="/static/seo.css?v=2">
<script type="application/ld+json">
{faq_json_ld}
</script>
</head>
<body>
<div class="agebar"><span class="age">18</span><span>Сервис для совершеннолетних пользователей. Уютное общение без грубостей.</span></div>
<header class="site-header">
  <div class="max">
    <a class="brand" href="/"><span class="dot"></span>{site_name}</a>
    <nav class="nav">
      <a href="/#features">Преимущества</a>
      <a href="/#how">Как это работает</a>
      <a href="/#personas">Персонажи</a>
      <a href="/#faq">Вопросы</a>
    </nav>
    <a class="top-cta" href="{cta_href}">{cta_text}</a>
  </div>
</header>
"""

HTML_BODY = """
<main class="page">
  <div class="max">
    <article class="card">
      <h1 class="h1">{h1}</h1>
      <p class="lead">{lead}</p>

      <img class="og" src="{og_image_path}" alt="{title}">

      {bullets_html}
      {seo_sections}
      {faq_html}

      <div class="cta-bar">
        <a class="cta" href="{cta_href}">{cta_text}</a>
      </div>
    </article>

    {hub_html}
  </div>
</main>
"""

HTML_FOOT = """
<footer class="site-footer">
  <div class="max">
    <div class="updated">Обновлено: {updated_at}</div>
    <div class="copy">© {year} {site_name}</div>
  </div>
</footer>
</body>
</html>
"""

DEFAULT_CSS = """
:root{
  --bg:#0d0e12; --fg:#f5f7fb; --muted:#a6aec8; --line:#272a33;
  --card:#151720; --accent:#e14857; --accent-2:#ff6b7a;
  --radius:16px; --max:960px;
}
*{box-sizing:border-box} html,body{margin:0;padding:0}
body{background:var(--bg);color:var(--fg);font:16px/1.65 -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Ubuntu,Arial,sans-serif}
/* age bar */
.agebar{background:#111; color:#ffd95c; font-size:13px; display:flex; gap:10px; align-items:center; padding:6px 12px; border-bottom:1px solid var(--line)}
.agebar .age{display:inline-grid; place-items:center; width:22px; height:22px; border-radius:50%; background:#b91818; color:#fff; font-weight:700; font-size:12px}
.max{max-width:var(--max);margin:0 auto;padding:0 20px}
/* header */
.site-header{position:sticky;top:0;z-index:10;background:#13151b; border-bottom:1px solid var(--line)}
.site-header .max{display:flex;align-items:center;justify-content:space-between;gap:16px;height:60px}
.brand{display:flex;align-items:center;gap:10px;text-decoration:none;color:var(--fg);font-weight:700}
.brand .dot{width:28px;height:28px;border-radius:50%;background:#c43a49;display:inline-block}
.nav{display:flex;gap:22px}
.nav a{color:var(--muted);text-decoration:none}
.nav a:hover{color:var(--fg)}
.top-cta{display:inline-block;background:var(--accent);color:#fff;text-decoration:none;padding:10px 16px;border-radius:12px;font-weight:700;box-shadow:0 6px 18px rgba(225,72,87,.25)}
/* page */
.page{padding:28px 0 40px}
.card{background:linear-gradient(180deg,rgba(255,255,255,.02),rgba(255,255,255,0));border:1px solid var(--line);border-radius:var(--radius);padding:22px 18px}
.h1{font-size:34px;line-height:1.25;margin:0 0 10px}
.lead{font-size:18px;color:var(--muted);margin:0 0 16px}
.og{display:block;width:100%;height:auto;border-radius:12px;border:1px solid var(--line);margin:14px 0 18px}
/* bullets */
.bullets{list-style:none;margin:0 0 18px;padding:0;display:grid;grid-template-columns:1fr 1fr;gap:10px}
.bullets li{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 12px}
@media (max-width:720px){.bullets{grid-template-columns:1fr}}
/* seo sections */
.sec{margin:18px 0}
.h2{font-size:20px;margin:0 0 8px}
/* faq */
.faq{border-top:1px solid var(--line);padding-top:16px;margin-top:8px}
.qa{margin:12px 0;padding:10px 12px;border:1px dashed var(--line);border-radius:12px;background:rgba(255,255,255,.02)}
.q{font-weight:700;margin:0 0 6px}
.a{margin:0}
/* CTA */
.cta-bar{display:flex;justify-content:center;margin:22px 0 4px}
.cta{display:inline-block;padding:12px 18px;border-radius:14px;text-decoration:none;font-weight:700;color:#fff;background:linear-gradient(90deg,var(--accent),var(--accent-2));box-shadow:0 4px 16px rgba(225,72,87,.25)}
.cta:hover{transform:translateY(-1px)}
/* hub chips */
.hub{margin:22px 0 8px}
.chips{display:flex;flex-wrap:wrap;gap:10px}
.chip{display:inline-block;padding:9px 12px;border-radius:999px;background:#1b1e27;border:1px solid var(--line);text-decoration:none;color:#fff}
.chip:hover{background:#232736}
/* footer */
.site-footer{border-top:1px solid var(--line);padding:16px 0;color:#a6aec8}
.site-footer .max{display:flex;gap:12px;justify-content:space-between;align-items:center;flex-wrap:wrap}
.updated,.copy{font-size:14px}
@media (max-width:520px){.h1{font-size:28px}}
""".strip() + "\n"

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
    leaf = (segs[-1] if segs else "page").lower().replace("ё", "е")
    leaf = re.sub(r"[^a-z0-9\-_]+", "-", leaf)
    leaf = re.sub(r"-{2,}", "-", leaf).strip("-")
    return leaf or "page"

def norm_slug(s: str) -> str:
    s = s.strip().strip("/")
    return slugify_url_to_leaf("/" + s + "/")

def split_bullets(s: str) -> List[str]:
    if not s: return []
    parts = re.split(r"\s*\|\s*|\r?\n", s.strip())
    return [p for p in (x.strip() for x in parts) if p]

def is_true(val: str) -> bool:
    return (val or "").strip().lower() in {"1","true","yes","y","да","on"}

# ========= Модель =========
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
    hub: str
    related_slugs: List[str]

    @property
    def slug(self) -> str:
        return slugify_url_to_leaf(self.url)

    @staticmethod
    def from_dict(d: Dict[str, str]) -> "PageRow":
        raw_url = (d.get("url") or "").strip()
        slug = (d.get("slug") or "").strip().strip("/")
        if not raw_url:
            if not slug:
                raise ValueError("CSV row is missing required 'url' (и нет 'slug')")
            raw_url = f"/chat/{slug}/"
        if not raw_url.startswith("/"): raw_url = "/" + raw_url
        if not raw_url.endswith("/"): raw_url += "/"

        title = (d.get("title") or d.get("og_title") or d.get("h1") or "").strip()
        if not title:
            raise ValueError("CSV row is missing one of ['title','og_title','h1']")
        h1 = (d.get("h1") or title).strip()
        description = (d.get("description") or d.get("og_description") or "").strip()
        intro = (d.get("intro") or "").strip()
        og_title = (d.get("og_title") or title).strip()
        og_description = (d.get("og_description") or description or intro or title).strip()

        bullets = split_bullets(d.get("bullets") or "")
        faqs: List[Tuple[str, str]] = []
        for i in range(1, 11):
            q = (d.get(f"faq{i}_q") or "").strip()
            a = (d.get(f"faq{i}_a") or "").strip()
            if q and a:
                faqs.append((q, a))

        cta_text = (d.get("cta") or DEFAULT_CTA_TEXT).strip()
        cta_href = (d.get("cta_href") or GLOBAL_CTA_HREF).strip()

        robots = "noindex,nofollow" if is_true(d.get("noindex")) else "index,follow"
        keyword = (d.get("keyword") or "").strip()
        canonical = (d.get("canonical") or f"{SITE_ORIGIN}{raw_url}").strip()
        hub = (d.get("hub") or "").strip().lower()
        related_slugs = [norm_slug(s) for s in (d.get("related") or "").split(",") if s.strip()]

        return PageRow(
            url=raw_url, title=title, h1=h1, description=description,
            og_title=og_title, og_description=og_description, intro=intro,
            bullets=bullets, faqs=faqs, cta_text=cta_text, cta_href=cta_href,
            robots=robots, keyword=keyword, canonical=canonical,
            hub=hub, related_slugs=related_slugs
        )

# ========= CSV =========
def load_rows() -> List[PageRow]:
    csv_path = find_first_existing(CANDIDATE_CSV)
    if not csv_path:
        print("⚠️  CSV с данными не найден.", file=sys.stderr)
        return []
    rows: List[PageRow] = []
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, d in enumerate(reader, 1):
            try:
                rows.append(PageRow.from_dict(d))
            except Exception as e:
                print(f"⚠️  Строка {i} пропущена: {e}", file=sys.stderr)
    print(f"✔ Найдено строк: {len(rows)} из {csv_path.relative_to(ROOT)}")
    return rows

# ========= OG =========
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
    footer = SITE_NAME
    w_f, h_f = _measure_text(draw, footer, font_small)
    draw.text(((OG_SIZE[0]-w_f)//2, OG_SIZE[1]-h_f-36), footer, font=font_small, fill=OG_FOOTER_FILL)

    img.save(out, format="PNG", optimize=True)
    return out

# ========= Рендер =========
def render_bullets(items: List[str]) -> str:
    if not items: return ""
    lis = "\n".join(f"<li>{esc(x)}</li>" for x in items)
    return '<ul class="bullets">\n' + lis + '\n</ul>'

def render_faq(faqs: List[Tuple[str, str]]) -> Tuple[str, str]:
    if not faqs:
        return "", "[]"
    blocks, schema = [], []
    for q, a in faqs:
        blocks.append(f'<div class="qa"><div class="q">{esc(q)}</div><p class="a">{esc(a)}</p></div>')
        schema.append({"@type":"Question","name":q,"acceptedAnswer":{"@type":"Answer","text":a}})
    html_block = '<section class="faq">\n<h2 class="h2">Вопросы и ответы</h2>\n' + "\n".join(blocks) + "\n</section>"
    json_ld = json.dumps({"@context":"https://schema.org","@type":"FAQPage","mainEntity":schema}, ensure_ascii=False)
    return html_block, json_ld

def generate_seo_sections(row: PageRow) -> str:
    blocks = []
    lead = row.intro or row.description or row.og_description or row.title
    blocks.append('<section class="sec"><h2 class="h2">О чём этот чат</h2><p>' + esc(lead) + "</p></section>")
    if row.bullets:
        paras = []
        for b in row.bullets:
            paras.append("<p><strong>" + esc(b) + ".</strong> Напишите первое короткое сообщение — дальше всё пойдёт в вашем темпе.</p>")
        blocks.append('<section class="sec"><h2 class="h2">Как начать разговор</h2>' + "".join(paras) + "</section>")
    if row.faqs:
        tips = []
        for q, a in row.faqs[:3]:
            tips.append("<p><strong>" + esc(q) + "</strong> " + esc(a) + "</p>")
        blocks.append('<section class="sec"><h2 class="h2">Советы для комфортного диалога</h2>' + "".join(tips) + "</section>")
    return "\n".join(blocks)

def build_hub_html(all_rows: List[PageRow], cur: PageRow, limit: int = 8) -> str:
    by_slug = {r.slug: r for r in all_rows}
    picks: List[PageRow] = []

    for s in cur.related_slugs:
        r = by_slug.get(norm_slug(s))
        if r and r.url != cur.url and r not in picks:
            picks.append(r)

    if len(picks) < limit and cur.hub:
        hub_rows = [r for r in all_rows if r.hub == cur.hub and r.url != cur.url]
        random.shuffle(hub_rows)
        for r in hub_rows:
            if len(picks) >= limit: break
            if r not in picks: picks.append(r)

    if len(picks) < limit:
        rest = [r for r in all_rows if r.url != cur.url and r not in picks]
        random.shuffle(rest)
        picks += rest[: max(0, limit - len(picks))]

    if not picks:
        return ""
    chips = [f'<a class="chip" href="{esc(r.url)}">{esc(r.title)}</a>' for r in picks[:limit]]
    return '<section class="hub"><h2 class="h2">Другие темы</h2><div class="chips">' + "\n".join(chips) + "</div></section>"

def write_html(row: PageRow, all_rows: List[PageRow]) -> Path:
    target_dir = DOCS_DIR / row.url.lstrip("/")
    if not str(target_dir).endswith("/"):
        target_dir = Path(str(target_dir) + "/")
    file_path = target_dir / "index.html"
    ensure_dir(file_path)

    og_slug = row.slug
    og_image_rel = "/static/og/" + og_slug + ".png"
    og_image_abs = SITE_ORIGIN + og_image_rel

    lead = row.intro or row.description or row.og_description or row.title
    bullets_html = render_bullets(row.bullets)
    faq_html, faq_json_ld = render_faq(row.faqs)
    seo_sections = generate_seo_sections(row)
    hub_html = build_hub_html(all_rows, row, limit=8)
    meta_keywords = '<meta name="keywords" content="' + esc(row.keyword) + '">' if row.keyword else ""

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
        site_name=esc(SITE_NAME),
    )

    body = HTML_BODY.format(
        h1=esc(row.h1 or row.title),
        lead=esc(lead),
        og_image_path=esc(og_image_rel),
        title=esc(row.title),
        bullets_html=bullets_html,
        seo_sections=seo_sections,
        faq_html=faq_html,
        cta_href=esc(row.cta_href or GLOBAL_CTA_HREF),
        cta_text=esc(row.cta_text or DEFAULT_CTA_TEXT),
        hub_html=hub_html,
    )

    foot = HTML_FOOT.format(
        updated_at=esc(now_utc_iso()),
        year=datetime.now().year,
        site_name=esc(SITE_NAME),
    )

    file_path.write_text(head + body + foot, encoding="utf-8")
    return file_path

# ========= CSS =========
def ensure_css():
    CSS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not CSS_PATH.exists():
        CSS_PATH.write_text(DEFAULT_CSS, encoding="utf-8")
        print("CSS ✓", CSS_PATH.relative_to(ROOT), "(создан)")

# ========= Main =========
def load_first_existing(paths: Iterable[Path]) -> Optional[Path]:
    return find_first_existing(paths)

def load_rows_safe() -> List[PageRow]:
    return load_rows()

def main() -> int:
    ensure_css()
    rows = load_rows_safe()
    if not rows:
        print("ℹ️  Данных нет — ничего не сгенерировано.")
        return 0

    from PIL import Image  # чтобы падать раньше, если Pillow не установлен
    cnt_og = 0; cnt_html = 0
    for row in rows:
        og_path = ensure_og(row.slug, row.og_title or row.title); cnt_og += 1
        print("OG ✓", og_path.relative_to(ROOT))
        if GENERATE_HTML:
            html_path = write_html(row, rows); cnt_html += 1
            print("HTML ✓", html_path.relative_to(ROOT))

    print("\n✅ Готово. OG:", cnt_og, " HTML:", cnt_html, " (UTC:", now_utc_iso(), ")")
    return 0

if __name__ == "__main__":
    sys.exit(main())
