#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Генератор страниц из нового CSV (расширенный формат).
— Компактные, «плиточные» блоки.
— Нормальные анкоры перелинковки (url|title).
— Кнопка CTA ведёт на TELEGRAM_URL (env) или дефолтную ссылку.
— Каноникал, OpenGraph, JSON-LD.
"""

import csv, os, re, html, json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

# --- Параметры окружения ---
ROOT = Path(__file__).resolve().parents[1]        # корень каталога ai/
SITE_BASE = os.getenv("SITE_BASE", "https://gorod-legends.ru").rstrip("/")
TELEGRAM_URL = os.getenv("TELEGRAM_URL", "https://t.me/luciddreams?start=_tgr_ChFKPawxOGRi")
TZ = ZoneInfo("Europe/Moscow")

# CSV может лежать в ./pages.csv или ./data/pages.csv
CSV_CANDIDATES = [ROOT / "pages.csv", ROOT / "data/pages.csv"]
CSV_PATH = next((p for p in CSV_CANDIDATES if p.exists()), None)
if not CSV_PATH:
    raise SystemExit("[ERR] CSV not found: pages.csv or data/pages.csv")

OUT_DIR = ROOT / "chat"     # все страницы раздела «чат» здесь
ASSETS_CSS = "assets/chat.css"
ASSETS_JS  = "assets/chat.js"

# --- Утилиты парсинга полей CSV ---

def split_list(s: str) -> list[str]:
    s = (s or "").strip()
    if not s:
        return []
    return [x.strip() for x in s.split("|") if x.strip()]

def para(text: str) -> str:
    """Разбить на абзацы по \n и обернуть в <p>"""
    t = (text or "").strip()
    if not t:
        return ""
    parts = [f"<p>{html.escape(p.strip())}</p>" for p in re.split(r"\n{2,}|\r?\n", t) if p.strip()]
    return "\n".join(parts)

def parse_internal_links(s: str) -> list[dict]:
    """
    Поддержка двух форматов:
    1) "/chat/foo/|Название||/chat/bar/|Другое"
    2) "/chat/foo/|/chat/bar/" (устаревший — анкором станет сам url)
    Разделитель между парами — '||'
    Если '||' не найдено, пытаемся по одному '|' (старый CSV).
    """
    s = (s or "").strip()
    if not s:
        return []
    items = []
    if "||" in s:
        pairs = [p for p in s.split("||") if p.strip()]
        for p in pairs:
            if "|" in p:
                href, text = p.split("|", 1)
                items.append({"href": href.strip(), "text": text.strip() or href.strip()})
    else:
        # старый стиль: просто список URL через '|'
        for href in split_list(s):
            items.append({"href": href, "text": href})
    return items

def safe_slug(url: str, slug: str) -> str:
    """Вернуть чистый slug. Если в CSV есть полный url — вытащим последний сегмент."""
    if slug:
        return slug.strip().strip("/")
    u = (url or "").strip()
    if not u:
        return ""
    tail = u.rstrip("/").split("/")[-1]
    return tail

def out_path_for(url: str, slug: str) -> Path:
    s = safe_slug(url, slug)
    if not s:
        raise ValueError("slug is empty")
    return OUT_DIR / s / "index.html"

def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")

# --- Рендеринг готовых блоков ---

def render_badges(items: list[str]) -> str:
    if not items: return ""
    return '<div class="pill-row">' + "".join(f'<span class="pill">{html.escape(x)}</span>' for x in items) + "</div>"

def render_list(items: list[str]) -> str:
    if not items: return ""
    li = "".join(f"<li>{html.escape(x)}</li>" for x in items)
    return f"<ul class='ul'>{li}</ul>"

def render_chips(items: list[str]) -> str:
    if not items: return ""
    return '<div class="chips">' + "".join(f'<span class="chip">{html.escape(x)}</span>' for x in items) + "</div>"

def render_related(links: list[dict]) -> str:
    if not links: return ""
    s = "".join(f'<a class="chip link" href="{html.escape(l["href"])}">{html.escape(l["text"])}</a>' for l in links)
    return f'<div class="related">{s}</div>'

def render_scenarios(rows: list[tuple[str, str]]) -> str:
    rows = [(t, d) for (t, d) in rows if (t or d)]
    if not rows: return ""
    cards = []
    for t, d in rows:
        cards.append(
            f"""<div class="card">
    <div class="card-title">{html.escape(t or "Сценарий")}</div>
    <div class="card-text">{para(d)}</div>
</div>"""
        )
    return '<div class="grid-3">' + "".join(cards) + "</div>"

def render_faq(qas: list[tuple[str, str]]) -> str:
    qas = [(q, a) for (q, a) in qas if (q or a)]
    if not qas: return ""
    blocks = []
    for q, a in qas:
        blocks.append(
            f"""<details class="faq">
  <summary>{html.escape(q or "Вопрос")}</summary>
  <div class="faq-a">{para(a)}</div>
</details>"""
        )
    return "<section class='faq-wrap'>" + "".join(blocks) + "</section>"

def json_ld(site_base: str, url_path: str, meta_title: str, meta_desc: str) -> str:
    data = {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "url": f"{site_base}{url_path}",
        "name": meta_title,
        "description": meta_desc,
        "inLanguage": "ru",
        "dateModified": now_iso(),
    }
    return '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False) + "</script>"

def render_page(row: dict) -> str:
    # поля CSV
    url           = row.get("url","").strip()
    title         = row.get("title","").strip()
    meta_title    = row.get("meta_title", title).strip() or title
    meta_desc     = row.get("meta_description", "").strip()
    h1            = row.get("h1", title).strip() or title
    intro         = row.get("intro","").strip()
    cta_text      = row.get("cta", "Открыть чат в Telegram").strip() or "Открыть чат в Telegram"
    bullets       = split_list(row.get("bullets",""))
    examples      = split_list(row.get("examples",""))
    tags          = split_list(row.get("tags",""))
    tips_do       = split_list(row.get("tips_do",""))
    tips_avoid    = split_list(row.get("tips_avoid",""))
    h2a_title     = row.get("h2a_title","").strip()
    h2a_text      = row.get("h2a_text","").strip()
    h2b_title     = row.get("h2b_title","").strip()
    h2b_text      = row.get("h2b_text","").strip()
    h2c_title     = row.get("h2c_title","").strip()
    h2c_text      = row.get("h2c_text","").strip()
    h2d_title     = row.get("h2d_title","").strip()
    h2d_text      = row.get("h2d_text","").strip()
    scenarios = [
        (row.get("scenario1_title","").strip(), row.get("scenario1_text","").strip()),
        (row.get("scenario2_title","").strip(), row.get("scenario2_text","").strip()),
        (row.get("scenario3_title","").strip(), row.get("scenario3_text","").strip()),
    ]
    faqs = [
        (row.get("faq1_q","").strip(), row.get("faq1_a","").strip()),
        (row.get("faq2_q","").strip(), row.get("faq2_a","").strip()),
        (row.get("faq3_q","").strip(), row.get("faq3_a","").strip()),
        (row.get("faq4_q","").strip(), row.get("faq4_a","").strip()),
        (row.get("faq5_q","").strip(), row.get("faq5_a","").strip()),
        (row.get("faq6_q","").strip(), row.get("faq6_a","").strip()),
    ]
    related       = parse_internal_links(row.get("internal_links",""))
    canonical     = (row.get("canonical","").strip() or f"{SITE_BASE}{url}")

    # шапка и hero
    head = f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>{html.escape(meta_title)}</title>
<meta name="description" content="{html.escape(meta_desc)}" />
<link rel="canonical" href="{html.escape(canonical)}" />
<meta property="og:type" content="article" />
<meta property="og:title" content="{html.escape(meta_title)}" />
<meta property="og:description" content="{html.escape(meta_desc)}" />
<meta property="og:url" content="{html.escape(canonical)}" />
<link rel="stylesheet" href="/{ASSETS_CSS}">
<script defer src="/{ASSETS_JS}"></script>
{json_ld(SITE_BASE, url, meta_title, meta_desc)}
</head>
<body class="theme-dark">
<header class="site-top">
  <div class="container">
    <a class="brand" href="/">Luna Chat</a>
    <a class="btn primary sticky-cta" href="{html.escape(TELEGRAM_URL)}">Открыть чат в Telegram</a>
  </div>
</header>

<main class="container">
  <section class="hero">
    <h1>{html.escape(h1)}</h1>
    <p class="lead">{html.escape(intro)}</p>
    {render_badges(bullets[:4] or tags[:4])}
    <div class="hero-cta">
      <a class="btn primary" href="{html.escape(TELEGRAM_URL)}">{html.escape(cta_text)}</a>
    </div>
  </section>
"""
    # тело
    body = []

    # карточка-пояснение под бейджами (если есть текст)
    if any([h2a_text, h2b_text]):
        body.append('<section class="note">' + para("Современная модель поддерживает дружелюбный 18+ диалог. Вы задаёте тон и границы, а система бережно подстраивается.") + "</section>")

    # блок «Что внутри»
    what_inside = tips = ""
    if bullets:
        what_inside = f"""
<section>
  <h2>Что внутри</h2>
  {render_list(bullets)}
</section>
"""
    # «Подсказки и примеры»
    examples_html = ""
    if examples:
        examples_html = f"""
<section>
  <h2>Подсказки и примеры</h2>
  {render_chips(examples)}
</section>
"""
    # три тематических блока h2*
    def h2_block(title, text):
        if not (title or text): return ""
        return f"<section><h2>{html.escape(title or '')}</h2>{para(text)}</section>"

    thematic = "".join([
        h2_block(h2a_title, h2a_text),
        h2_block(h2b_title, h2b_text),
        h2_block(h2c_title, h2c_text),
        h2_block(h2d_title, h2d_text),
    ])

    # «Сценарии»
    scen = ""
    if any(t for (t, _) in scenarios):
        scen = "<section><h2>Сценарии</h2>" + render_scenarios(scenarios) + "</section>"

    # do/avoid
    if tips_do or tips_avoid:
        tips = "<section class='two-col'>"
        if tips_do:
            tips += "<div><h3>Стоит делать</h3>" + render_list(tips_do) + "</div>"
        if tips_avoid:
            tips += "<div><h3>Чего избегать</h3>" + render_list(tips_avoid) + "</div>"
        tips += "</section>"

    # FAQ
    faq_html = render_faq(faqs)

    # Перелинковка
    related_html = ""
    if related:
        related_html = "<section><h2>Ещё по теме</h2>" + render_related(related) + "</section>"

    body.append(what_inside)
    body.append(examples_html)
    body.append(thematic)
    body.append(scen)
    body.append(tips)
    body.append(faq_html)
    body.append(related_html)

    # футер
    foot = f"""
</main>

<footer class="site-foot">
  <div class="container">
    <small>© 2025 Luna Chat • Уважайте границы, 18+</small>
  </div>
</footer>
</body></html>
"""
    return head + "\n".join([b for b in body if b]) + foot

# --- Главный проход по CSV ---

def main():
    print(f"[i] CSV: {CSV_PATH}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        raise SystemExit("[ERR] CSV has no rows")

    for r in rows:
        try:
            out_path = out_path_for(r.get("url",""), r.get("slug",""))
        except Exception as e:
            print(f"[skip] row without slug/url: {e}")
            continue

        html_page = render_page(r)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html_page, encoding="utf-8")
        print("[ok]", out_path.relative_to(ROOT))

    # Положим ассеты, если вдруг забыты
    assets_dir = ROOT / "assets"
    assets_dir.mkdir(exist_ok=True)
    css_path = assets_dir / "chat.css"
    js_path = assets_dir / "chat.js"
    if not css_path.exists():
        css_path.write_text(DEFAULT_CSS, encoding="utf-8")
        print("[i] created assets/chat.css")
    if not js_path.exists():
        js_path.write_text(DEFAULT_JS, encoding="utf-8")
        print("[i] created assets/chat.js")

# --- Встроенные минимальные ассеты по умолчанию ---

DEFAULT_CSS = r"""
:root{--bg:#0f0f12;--panel:#15161b;--text:#e7e7ea;--muted:#a6a7ad;--brand:#e3566a;--brand-2:#ff6b8a;--border:#262732}
*{box-sizing:border-box}
body.theme-dark{margin:0;background:var(--bg);color:var(--text);font:16px/1.6 system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,"Helvetica Neue",Arial}
a{color:var(--brand);text-decoration:none}
.container{max-width:72ch;margin:0 auto;padding:24px}
.site-top{position:sticky;top:0;background:rgba(15,15,18,.75);backdrop-filter:saturate(140%) blur(8px);border-bottom:1px solid var(--border);z-index:30}
.site-top .container{display:flex;gap:16px;align-items:center;justify-content:space-between}
.brand{font-weight:700;color:#fff}
.btn{display:inline-flex;align-items:center;justify-content:center;padding:10px 16px;border-radius:14px;border:1px solid transparent;background:var(--panel);color:#fff}
.btn.primary{background:linear-gradient(180deg,var(--brand-2),var(--brand));box-shadow:0 6px 20px rgba(227,86,106,.35)}
.sticky-cta{position:relative}
@media (max-width:720px){.sticky-cta{position:fixed;right:16px;top:12px}}
.hero h1{margin:0 0 8px;font-size:clamp(24px,4.6vw,34px);line-height:1.2}
.lead{color:var(--muted);margin:0 0 16px}
.pill-row{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 6px}
.pill{display:inline-flex;align-items:center;padding:6px 10px;border-radius:999px;background:#1b1c22;border:1px solid var(--border);color:#cfd0d5;font-size:.9rem}
.hero-cta{margin:18px 0 6px}
.note{background:var(--panel);border:1px solid var(--border);padding:16px;border-radius:16px;margin:16px 0}
h2{margin:28px 0 8px;font-size:1.25rem}
h3{margin:14px 0 6px;font-size:1.05rem}
.ul{padding-left:20px}
.chips{display:flex;flex-wrap:wrap;gap:8px}
.chip{display:inline-flex;align-items:center;border:1px solid var(--border);background:#16171d;border-radius:12px;padding:6px 10px}
.chip.link{color:#dfe0e6}
.grid-3{display:grid;gap:12px;grid-template-columns:repeat(3,1fr);margin:12px 0}
@media (max-width:920px){.grid-3{grid-template-columns:1fr}}
.card{background:var(--panel);border:1px solid var(--border);border-radius:16px;padding:14px}
.card-title{font-weight:600;margin-bottom:6px}
.two-col{display:grid;gap:16px;grid-template-columns:1fr 1fr}
@media (max-width:920px){.two-col{grid-template-columns:1fr}}
.faq-wrap{margin:10px 0 24px}
.faq{background:#121318;border:1px solid var(--border);border-radius:12px;margin:8px 0;padding:0}
.faq>summary{list-style:none;cursor:pointer;padding:10px 14px;font-weight:600}
.faq[open]>summary{border-bottom:1px solid var(--border)}
.faq .faq-a{padding:12px 14px;color:#cfd0d5}
.site-foot{border-top:1px solid var(--border);margin-top:32px}
small{color:var(--muted)}
"""

DEFAULT_JS = r"""
// ничего критичного: нативные <details> для FAQ.
// можно добавить автокопирование текста чипов по клику, если потребуется.
"""

if __name__ == "__main__":
    main()
