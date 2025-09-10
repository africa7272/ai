#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, re, csv, json, html
from pathlib import Path
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
    TZ_MOSCOW = ZoneInfo("Europe/Moscow")
except Exception:
    TZ_MOSCOW = None

# ---------- настройки ----------
SITE_BASE = os.environ.get("SITE_BASE", "https://gorod-legends.ru").rstrip("/")
CSV_CANDIDATES = [Path("pages.csv"), Path("data/pages.csv")]
OUT_ROOT = Path(".")
BOT_URL_DEFAULT = "https://t.me/luciddreams?start=_tgr_ChFKPawxOGRi"
TEMPLATE_CANDIDATES = [Path("templates/chat.html"), Path("templates/page.html")]

# ---------- утилиты ----------
def now_moscow_iso():
    dt = datetime.utcnow()
    if TZ_MOSCOW:
        dt = datetime.now(TZ_MOSCOW)
    return dt.isoformat(timespec="seconds")

def norm_url(u: str) -> str:
    if not u: return "/"
    u = u.strip()
    if not u.startswith("/"): u = "/" + u
    if not u.endswith("/"): u = u + "/"
    return u

def split_pipes(s: str):
    if not s: return []
    return [x.strip() for x in s.split("|") if x.strip()]

def paragraphize(text: str) -> str:
    if not text: return ""
    parts = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    if not parts: return f"<p>{html.escape(text.strip())}</p>"
    return "".join(f"<p>{html.escape(p)}</p>" for p in parts)

def listify(items, cls="list"):
    if not items: return ""
    return "<ul class=\"%s\">%s</ul>" % (cls, "".join(f"<li>{html.escape(i)}</li>" for i in items))

def chips(items, cls="chips"):
    if not items: return ""
    return "<div class=\"%s\">%s</div>" % (cls, "".join(f"<span class=\"chip\">{html.escape(i)}</span>" for i in items))

def code_chips(items, cls="chips"):
    if not items: return ""
    return "<div class=\"%s\">%s</div>" % (cls, "".join(f"<span class=\"chip\"><code>{html.escape(i)}</code></span>" for i in items))

def human_from_slug(url: str) -> str:
    slug = url.strip("/").split("/")[-1]
    slug = slug.replace("-", " ").replace("_", " ")
    return slug.capitalize() if slug else "Смотреть"

def faq_json_ld(pairs):
    if not pairs: return ""
    js = {"@context":"https://schema.org","@type":"FAQPage",
          "mainEntity":[{"@type":"Question","name":q,"acceptedAnswer":{"@type":"Answer","text":a}} for q,a in pairs if q and a]}
    return '<script type="application/ld+json">' + html.escape(json.dumps(js, ensure_ascii=False, separators=(",",":"))) + "</script>"

def render(template: str, ctx: dict) -> str:
    html_out = template
    for k, v in ctx.items():
        html_out = html_out.replace("{{" + k + "}}", v)
    return re.sub(r"\{\{[a-zA-Z0-9_\-]+\}\}", "", html_out)

# ---------- индексация заголовков уже сгенерированных страниц ----------
H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I|re.S)
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I|re.S)

def strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "").strip()

def scan_titles_from_repo():
    res = {}
    for base in ("chat", "guides", "pages"):
        p = OUT_ROOT / base
        if not p.exists(): continue
        for idx in p.rglob("index.html"):
            try:
                raw = idx.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            h1 = H1_RE.search(raw)
            t = TITLE_RE.search(raw)
            text = strip_tags(h1.group(1) if h1 else (t.group(1) if t else ""))
            if not text: continue
            url = "/" + idx.parent.as_posix().strip("/") + "/"
            res[url] = text
    return res

def parse_internal_links(raw: str, title_index: dict):
    if not raw: return []
    pairs = []
    if "||" in raw:
        chunks = [c.strip() for c in raw.split("||") if c.strip()]
        i = 0
        while i < len(chunks):
            href = norm_url(chunks[i]); i += 1
            anchor = chunks[i] if i < len(chunks) else ""
            i += 1
            if not anchor: anchor = title_index.get(href) or human_from_slug(href)
            pairs.append((href, anchor))
    else:
        for href in split_pipes(raw):
            href = norm_url(href)
            anchor = title_index.get(href) or human_from_slug(href)
            pairs.append((href, anchor))
    return pairs

def render_internal_links(links):
    if not links: return ""
    cards = []
    for href, anchor in links:
        cards.append(f'''<a class="card" href="{html.escape(href)}">
  <span class="card-title">{html.escape(anchor)}</span>
  <span class="card-more">Открыть →</span>
</a>''')
    return '<div class="grid-cards">\n' + "\n".join(cards) + "\n</div>"

# ---------- шаблон ----------
def load_template():
    for p in TEMPLATE_CANDIDATES:
        if p.exists(): return p.read_text(encoding="utf-8")
    return """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>{{meta_title}}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{{meta_description}}">
<meta name="keywords" content="{{meta_keywords}}">
<link rel="canonical" href="{{canonical}}">
<meta property="og:type" content="article">
<meta property="og:locale" content="ru_RU">
<meta property="og:title" content="{{meta_title}}">
<meta property="og:description" content="{{meta_description}}">
<meta property="og:url" content="{{canonical}}">
<meta name="robots" content="index,follow">
<meta name="sitemap:changefreq" content="{{changefreq}}">
<meta name="sitemap:priority" content="{{priority}}">
<style>
:root{--bg:#0b0b0f;--panel:#101018;--line:#222232;--muted:#a9a9bd;--text:#e9e9ee;--accent:#ff5b7f}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.6 system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif}
.container{max-width:880px;margin:0 auto;padding:20px}
.header{display:flex;gap:16px;justify-content:space-between;align-items:center;margin:6px 0 18px}
.brand{font-weight:700;letter-spacing:.2px}
.btn{display:inline-block;background:var(--accent);color:#fff;text-decoration:none;padding:10px 16px;border-radius:12px;box-shadow:0 6px 16px rgba(255,91,127,.25)}
.btn:hover{opacity:.95}
.lead{color:var(--muted);margin:8px 0 4px}
h1{font-size:28px;margin:8px 0 8px}
h2{font-size:22px;margin:22px 0 8px}
section{margin:14px 0 16px}
.list{list-style:disc;padding-left:20px}
.grid-2{display:grid;gap:14px}
@media(min-width:760px){.grid-2{grid-template-columns:1fr 1fr}}
.card-panel{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:12px 14px}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:6px 0}
.chip{display:inline-flex;align-items:center;border:1px solid var(--line);background:#111119;border-radius:999px;padding:6px 10px}
.grid-cards{display:grid;gap:12px}
@media(min-width:760px){.grid-cards{grid-template-columns:repeat(3,1fr)}}
.card{display:flex;justify-content:space-between;align-items:center;text-decoration:none;color:var(--text);background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:12px 14px}
.card:hover{border-color:#3a3a55}
.card-title{font-weight:600}
.card-more{opacity:.7}
details.faq{background:var(--panel);border:1px solid var(--line);border-radius:12px;margin:8px 0;padding:8px 12px}
details.faq summary{cursor:pointer;font-weight:600}
.small{opacity:.6;font-size:12px}
hr{border:0;border-top:1px solid var(--line);margin:18px 0}
</style>
{{faq_json_ld}}
</head>
<body>
<div class="container">
  <div class="header">
    <div class="brand">Luna Chat</div>
    <a class="btn" href="{{cta_url}}" target="_blank" rel="nofollow noopener">{{cta_text}}</a>
  </div>

  <h1>{{h1}}</h1>
  <p class="lead">{{lead}}</p>

  <section class="card-panel">
    <div class="chips">{{badges_html}}</div>
    {{intro_html}}
  </section>

  <section>
    <h2>Что внутри</h2>
    {{bullets_html}}
  </section>

  <section>
    <h2>Подсказки и примеры</h2>
    {{examples_html}}
  </section>

  <section>
    <h2>{{h2a_title}}</h2>
    {{h2a_text_html}}
  </section>
  <section>
    <h2>{{h2b_title}}</h2>
    {{h2b_text_html}}
  </section>
  <section>
    <h2>{{h2c_title}}</h2>
    {{h2c_text_html}}
  </section>
  <section>
    <h2>{{h2d_title}}</h2>
    {{h2d_text_html}}
  </section>

  <div class="grid-2">
    <section class="card-panel">
      <h2 style="margin-top:0">Что делать</h2>
      {{tips_do_html}}
    </section>
    <section class="card-panel">
      <h2 style="margin-top:0">Чего избегать</h2>
      {{tips_avoid_html}}
    </section>
  </div>

  <section>
    <h2>Сценарии</h2>
    <div class="card-panel">{{scenario1_block}}</div>
    <div class="card-panel">{{scenario2_block}}</div>
    <div class="card-panel">{{scenario3_block}}</div>
  </section>

  <section>
    <h2>Частые вопросы</h2>
    {{faq_html}}
  </section>

  <section>
    <h2>Ещё по теме</h2>
    {{internal_links_html}}
  </section>

  <p><a class="btn" href="{{cta_url}}" target="_blank" rel="nofollow noopener">{{cta_text}}</a></p>

  <hr>
  <p class="small">18+. Используйте уважительно. Обновлено: {{lastmod}}</p>
</div>
</body>
</html>
"""

# ---------- генерация ----------
def main():
    # CSV
    csv_path = next((p for p in CSV_CANDIDATES if p.exists()), None)
    if not csv_path:
        raise SystemExit("[ERR] CSV not found (pages.csv or data/pages.csv)")

    rows = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    # Заголовки уже существующих HTML
    title_index = scan_titles_from_repo()

    # Заголовки из CSV имеют приоритет
    for r in rows:
        url = norm_url(r.get("url") or "")
        title = (r.get("title") or r.get("h1") or "").strip()
        if url and title:
            title_index[url] = title

    template = load_template()
    lastmod = now_moscow_iso()

    for r in rows:
        url = norm_url(r.get("url") or "")
        out_dir = OUT_ROOT / Path(url.strip("/"))
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "index.html"

        title = (r.get("title") or "").strip()
        h1 = (r.get("h1") or title or "").strip()

        meta_title = (r.get("meta_title") or title or h1 or "").strip()
        meta_description = (r.get("meta_description") or r.get("description") or "").strip()
        meta_keywords = ",".join(split_pipes(r.get("tags") or ""))

        lead = (r.get("lead") or meta_description or "").strip()
        intro_html = paragraphize(r.get("intro") or "")

        badges_html = chips(split_pipes(r.get("bullets") or ""))  # быстрые бейджи над вводным текстом
        bullets_html = listify(split_pipes(r.get("bullets") or ""), cls="list")
        examples_html = code_chips(split_pipes(r.get("examples") or ""))

        tips_do_html = listify(split_pipes(r.get("tips_do") or ""), cls="list")
        tips_avoid_html = listify(split_pipes(r.get("tips_avoid") or ""), cls="list")

        h2a_title = (r.get("h2a_title") or "").strip()
        h2a_text_html = paragraphize(r.get("h2a_text") or "")
        h2b_title = (r.get("h2b_title") or "").strip()
        h2b_text_html = paragraphize(r.get("h2b_text") or "")
        h2c_title = (r.get("h2c_title") or "").strip()
        h2c_text_html = paragraphize(r.get("h2c_text") or "")
        h2d_title = (r.get("h2d_title") or "").strip()
        h2d_text_html = paragraphize(r.get("h2d_text") or "")

        # сценарии — в отдельные панели, чтобы компактно
        s1t, s1 = (r.get("scenario1_title") or "").strip(), paragraphize(r.get("scenario1_text") or "")
        s2t, s2 = (r.get("scenario2_title") or "").strip(), paragraphize(r.get("scenario2_text") or "")
        s3t, s3 = (r.get("scenario3_title") or "").strip(), paragraphize(r.get("scenario3_text") or "")
        scenario1_block = (f"<h3 style='margin-top:0'>{html.escape(s1t)}</h3>{s1}") if (s1t or s1) else ""
        scenario2_block = (f"<h3 style='margin-top:0'>{html.escape(s2t)}</h3>{s2}") if (s2t or s2) else ""
        scenario3_block = (f"<h3 style='margin-top:0'>{html.escape(s3t)}</h3>{s3}") if (s3t or s3) else ""

        # FAQ
        faq_pairs = []
        for i in range(1, 7):
            q = (r.get(f"faq{i}_q") or "").strip()
            a = (r.get(f"faq{i}_a") or "").strip()
            if q and a: faq_pairs.append((q, a))
        faq_html = "\n".join(
            f'<details class="faq"><summary>{html.escape(q)}</summary><div class="answer">{paragraphize(a)}</div></details>'
            for q, a in faq_pairs
        )
        faq_schema = faq_json_ld(faq_pairs)

        # Перелинковка с нормальными анкорами
        internal_links = parse_internal_links(r.get("internal_links") or "", title_index)
        internal_links_html = render_internal_links(internal_links)

        changefreq = (r.get("changefreq") or "weekly").strip()
        priority = (r.get("priority") or "0.7").strip()
        canonical = (r.get("canonical") or (SITE_BASE + url)).strip()

        cta_text = (r.get("cta") or "Открыть чат в Telegram").strip()
        cta_url = (r.get("cta_url") or os.environ.get("BOT_URL") or BOT_URL_DEFAULT).strip()

        ctx = {
            "meta_title": html.escape(meta_title),
            "meta_description": html.escape(meta_description),
            "meta_keywords": html.escape(meta_keywords),
            "canonical": html.escape(canonical),
            "changefreq": html.escape(changefreq),
            "priority": html.escape(priority),
            "h1": html.escape(h1),
            "lead": html.escape(lead),
            "intro_html": intro_html,
            "badges_html": badges_html,
            "bullets_html": bullets_html,
            "examples_html": examples_html,
            "tips_do_html": tips_do_html,
            "tips_avoid_html": tips_avoid_html,
            "h2a_title": html.escape(h2a_title),
            "h2a_text_html": h2a_text_html,
            "h2b_title": html.escape(h2b_title),
            "h2b_text_html": h2b_text_html,
            "h2c_title": html.escape(h2c_title),
            "h2c_text_html": h2c_text_html,
            "h2d_title": html.escape(h2d_title),
            "h2d_text_html": h2d_text_html,
            "scenario1_block": scenario1_block,
            "scenario2_block": scenario2_block,
            "scenario3_block": scenario3_block,
            "faq_html": faq_html,
            "faq_json_ld": faq_schema,
            "internal_links_html": internal_links_html,
            "cta_text": html.escape(cta_text),
            "cta_url": html.escape(cta_url),
            "lastmod": html.escape(now_moscow_iso()),
        }

        html_final = render(load_template(), ctx)
        out_path.write_text(html_final, encoding="utf-8")
        print(f"[OK] {url} -> {out_path}")

    print(f"\nDone. Generated {len(rows)} page(s).")

if __name__ == "__main__":
    main()
