#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv, os, re, html, json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SITE_BASE = os.getenv("SITE_BASE", "https://gorod-legends.ru").rstrip("/")
TELEGRAM_URL = os.getenv("TELEGRAM_URL", "https://t.me/luciddreams?start=_tgr_ChFKPawxOGRi")
TZ = ZoneInfo("Europe/Moscow")

CSV_CANDIDATES = [ROOT / "pages.csv", ROOT / "data/pages.csv"]
CSV_PATH = next((p for p in CSV_CANDIDATES if p.exists()), None)
if not CSV_PATH:
    raise SystemExit("[ERR] CSV not found: pages.csv or data/pages.csv")

OUT_DIR = ROOT / "chat"
ASSETS_CSS = "assets/chat.css"
ASSETS_JS  = "assets/chat.js"

# ---------- helpers ----------

def norm_url(u: str) -> str:
    u = (u or "").strip()
    if not u:
        return ""
    if not u.startswith("/"):
        u = "/" + u
    if not u.endswith("/"):
        u = u + "/"
    return u

def slug_from_url(u: str) -> str:
    u = norm_url(u)
    return u.strip("/").split("/")[-1]

def split_list(s: str) -> list[str]:
    s = (s or "").strip()
    return [x.strip() for x in s.split("|") if x.strip()] if s else []

def para(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    parts = [f"<p>{html.escape(p.strip())}</p>" for p in re.split(r"\n{2,}|\r?\n", t) if p.strip()]
    return "\n".join(parts)

def parse_internal_links(s: str) -> list[dict]:
    """
    Поддержка:
      "/chat/foo/|Название||/chat/bar/|Другое"
    и наследие:
      "/chat/foo/|/chat/bar/"  (в этом случае текст вытянем сами)
    """
    s = (s or "").strip()
    if not s:
        return []
    items = []
    if "||" in s:
        for p in [p for p in s.split("||") if p.strip()]:
            if "|" in p:
                href, text = p.split("|", 1)
                items.append({"href": norm_url(href), "text": text.strip()})
    else:
        for href in split_list(s):
            items.append({"href": norm_url(href), "text": ""})
    return items

def out_path_for(url: str, slug: str) -> Path:
    s = (slug or "").strip().strip("/")
    if not s:
        s = slug_from_url(url or "")
    if not s:
        raise ValueError("empty slug/url")
    return OUT_DIR / s / "index.html"

def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")

def pretty_from_slug(u: str) -> str:
    s = slug_from_url(u)
    s = s.replace("-", " ")
    # первая буква заглавная
    return s[:1].upper() + s[1:]

# ---------- UI render ----------

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
    s = "".join(f'<a class="chip link glow" href="{html.escape(l["href"])}">{html.escape(l["text"])}</a>' for l in links)
    return f'<div class="related">{s}</div>'

def render_scenarios(rows: list[tuple[str, str]]) -> str:
    rows = [(t, d) for (t, d) in rows if (t or d)]
    if not rows: return ""
    cards = []
    for t, d in rows:
        cards.append(
            f"""<div class="card glow">
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

# ---------- title index for anchors ----------

def build_title_index(rows: list[dict]) -> dict:
    idx = {}
    # из CSV
    for r in rows:
        u = norm_url(r.get("url",""))
        if not u: 
            continue
        t = (r.get("title") or r.get("h1") or r.get("meta_title") or "").strip()
        if t:
            idx[u] = t

    # из уже сгенерированных страниц (h1)
    if OUT_DIR.exists():
        for p in OUT_DIR.glob("*/index.html"):
            url_path = f"/chat/{p.parent.name}/"
            if url_path in idx: 
                continue
            try:
                txt = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            m = re.search(r"<h1[^>]*>(.*?)</h1>", txt, flags=re.S|re.I)
            if m:
                h1 = re.sub(r"<.*?>", "", m.group(1)).strip()
                if h1:
                    idx[url_path] = h1
    return idx

def enrich_related(links: list[dict], title_index: dict) -> list[dict]:
    out = []
    for l in links:
        href = norm_url(l.get("href",""))
        text = (l.get("text") or "").strip()
        if not text:
            text = title_index.get(href) or pretty_from_slug(href)
        out.append({"href": href, "text": text})
    return out

# ---------- render full page ----------

def render_page(row: dict, title_index: dict) -> str:
    url           = norm_url(row.get("url",""))
    title         = row.get("title","").strip()
    meta_title    = (row.get("meta_title") or title).strip() or title
    meta_desc     = row.get("meta_description","").strip()
    h1            = (row.get("h1") or title).strip() or title
    intro         = row.get("intro","").strip()
    cta_text      = (row.get("cta") or "Открыть чат в Telegram").strip()
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
    scenarios     = [
        (row.get("scenario1_title","").strip(), row.get("scenario1_text","").strip()),
        (row.get("scenario2_title","").strip(), row.get("scenario2_text","").strip()),
        (row.get("scenario3_title","").strip(), row.get("scenario3_text","").strip()),
    ]
    faqs          = [
        (row.get("faq1_q","").strip(), row.get("faq1_a","").strip()),
        (row.get("faq2_q","").strip(), row.get("faq2_a","").strip()),
        (row.get("faq3_q","").strip(), row.get("faq3_a","").strip()),
        (row.get("faq4_q","").strip(), row.get("faq4_a","").strip()),
        (row.get("faq5_q","").strip(), row.get("faq5_a","").strip()),
        (row.get("faq6_q","").strip(), row.get("faq6_a","").strip()),
    ]
    related       = enrich_related(parse_internal_links(row.get("internal_links","")), title_index)
    canonical     = (row.get("canonical","").strip() or f"{SITE_BASE}{url}")

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

    body = []

    if bullets:
        body.append(f"""
<section class="panel glow">
  <div class="panel-title">Что внутри</div>
  {render_list(bullets)}
</section>
""")

    if examples:
        body.append(f"""
<section>
  <h2>Подсказки и примеры</h2>
  {render_chips(examples)}
</section>
""")

    def h2_block(title, text):
        if not (title or text): return ""
        return f"<section><h2>{html.escape(title)}</h2>{para(text)}</section>"

    body.append(h2_block(h2a_title, h2a_text))
    body.append(h2_block(h2b_title, h2b_text))
    body.append(h2_block(h2c_title, h2c_text))
    body.append(h2_block(h2d_title, h2d_text))

    if any(t for (t, _) in scenarios):
        body.append("<section><h2>Сценарии</h2>" + render_scenarios(scenarios) + "</section>")

    tips_do = split_list(row.get("tips_do",""))
    tips_avoid = split_list(row.get("tips_avoid",""))
    if tips_do or tips_avoid:
        tips = "<section class='two-col'>"
        if tips_do:
            tips += "<div class='panel'><h3>Стоит делать</h3>" + render_list(tips_do) + "</div>"
        if tips_avoid:
            tips += "<div class='panel'><h3>Чего избегать</h3>" + render_list(tips_avoid) + "</div>"
        tips += "</section>"
        body.append(tips)

    body.append(render_faq(faqs))

    if related:
        body.append("<section><h2>Ещё по теме</h2>" + render_related(related) + "</section>")

    foot = """
</main>

<footer class="site-foot">
  <div class="container">
    <small>© 2025 Luna Chat • Уважайте границы, 18+</small>
  </div>
</footer>
</body></html>
"""
    return head + "\n".join([b for b in body if b]) + foot

# ---------- main ----------

DEFAULT_CSS = r"""
:root{
  --bg:#0e0e12; --panel:#16171d; --text:#e8e8ec; --muted:#a7a8ae; --border:#25262d;
  --brand:#ff6b9a; --brand2:#8b5cf6; --chip:#1a1b22; --glow:rgba(255,107,154,.28);
}
*{box-sizing:border-box}
body.theme-dark{margin:0;background:var(--bg);color:var(--text);font:16px/1.65 system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,"Helvetica Neue",Arial}
a{color:var(--brand);text-decoration:none}
.container{max-width:74ch;margin:0 auto;padding:24px}
section+section{margin-top:24px}
.site-top{position:sticky;top:0;background:rgba(14,14,18,.76);backdrop-filter:saturate(130%) blur(8px);border-bottom:1px solid var(--border);z-index:30}
.site-top .container{display:flex;gap:16px;align-items:center;justify-content:space-between}
.brand{font-weight:700;color:#fff}
.btn{display:inline-flex;align-items:center;justify-content:center;padding:10px 16px;border-radius:14px;border:1px solid transparent;background:var(--panel);color:#fff}
.btn.primary{background:linear-gradient(180deg,var(--brand),var(--brand2));box-shadow:0 8px 28px rgba(139,92,246,.32)}
.sticky-cta{position:relative}
@media (max-width:720px){.sticky-cta{position:fixed;right:16px;top:12px}}

.hero h1{margin:0 0 8px;font-size:clamp(24px,4.6vw,34px);line-height:1.2}
.lead{color:var(--muted);margin:0 0 16px}
.pill-row{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 10px}
.pill{display:inline-flex;align-items:center;padding:6px 10px;border-radius:999px;background:var(--chip);border:1px solid var(--border);color:#cfd0d5;font-size:.9rem}

.panel{background:var(--panel);border:1px solid var(--border);border-radius:16px;padding:16px}
.panel-title{font-weight:600;margin:0 0 8px}
.glow{box-shadow:0 0 0 1px var(--border), 0 10px 30px var(--glow)}

h2{margin:0 0 8px;font-size:1.25rem}
h3{margin:14px 0 6px;font-size:1.05rem}
.ul{padding-left:20px}

.chips{display:flex;flex-wrap:wrap;gap:10px}
.chip{display:inline-flex;align-items:center;border:1px solid var(--border);background:linear-gradient(180deg,#181922,#12131a);border-radius:12px;padding:7px 11px;color:#dadbe1;transition:transform .08s ease, box-shadow .2s ease}
.chip:hover{transform:translateY(-1px);box-shadow:0 8px 18px var(--glow)}
.chip.link{color:#fff}

.related{display:flex;flex-wrap:wrap;gap:10px}

.grid-3{display:grid;gap:12px;grid-template-columns:repeat(3,1fr)}
@media (max-width:920px){.grid-3{grid-template-columns:1fr}}

.card{background:linear-gradient(180deg,#15161b,#12131a);border:1px solid var(--border);border-radius:16px;padding:14px}
.card-title{font-weight:600;margin-bottom:6px}

.two-col{display:grid;gap:16px;grid-template-columns:1fr 1fr}
@media (max-width:920px){.two-col{grid-template-columns:1fr}}

.faq-wrap{margin:6px 0 20px}
.faq{background:#121318;border:1px solid var(--border);border-radius:12px;margin:10px 0;padding:0;overflow:hidden}
.faq>summary{list-style:none;cursor:pointer;padding:12px 14px;font-weight:600;position:relative}
.faq>summary::after{content:"+";position:absolute;right:12px;top:10px;color:#fff;opacity:.55}
.faq[open]>summary::after{content:"—";}
.faq[open]>summary{border-bottom:1px solid var(--border)}
.faq .faq-a{padding:12px 14px;color:#cfd0d5}

.site-foot{border-top:1px solid var(--border);margin-top:32px}
small{color:var(--muted)}
"""

DEFAULT_JS = r"""// можно расширить — копирование текста чипов по клику и т.п."""

def main():
    print(f"[i] CSV: {CSV_PATH}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if not rows:
        raise SystemExit("[ERR] CSV has no rows")

    title_index = build_title_index(rows)

    for r in rows:
        try:
            out_path = out_path_for(r.get("url",""), r.get("slug",""))
        except Exception as e:
            print(f"[skip] row without slug/url: {e}")
            continue
        html_page = render_page(r, title_index)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html_page, encoding="utf-8")
        print("[ok]", out_path.relative_to(ROOT))

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

if __name__ == "__main__":
    main()
