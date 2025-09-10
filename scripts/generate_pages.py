#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import csv
import re
import json
import html
from pathlib import Path
from datetime import datetime
try:
    # Python 3.9+
    from zoneinfo import ZoneInfo
    TZ_MOSCOW = ZoneInfo("Europe/Moscow")
except Exception:
    TZ_MOSCOW = None  # на всякий

# ------------------------ Настройки ------------------------

SITE_BASE = os.environ.get("SITE_BASE", "https://gorod-legends.ru").rstrip("/")
CSV_CANDIDATES = [
    Path("pages.csv"),
    Path("data/pages.csv"),
]
OUT_ROOT = Path(".")          # корень репозитория
TEMPLATE_CANDIDATES = [
    Path("templates/chat.html"),
    Path("templates/page.html"),
]

# ------------------------ Утилиты --------------------------

def now_moscow_iso():
    dt = datetime.utcnow()
    if TZ_MOSCOW:
        dt = datetime.now(TZ_MOSCOW)
    return dt.isoformat(timespec="seconds")

def norm_url(u: str) -> str:
    """Нормализуем URL как в сайтах: с ведущим и закрывающим слешем."""
    if not u:
        return "/"
    u = u.strip()
    if not u.startswith("/"):
        u = "/" + u
    if not u.endswith("/"):
        u = u + "/"
    return u

def slugify_from_url(u: str) -> str:
    u = norm_url(u)
    seg = u.strip("/").split("/")[-1]
    return seg or "index"

def split_pipes(s: str):
    if not s:
        return []
    return [x.strip() for x in s.split("|") if x.strip()]

def paragraphize(text: str) -> str:
    if not text:
        return ""
    # двойные переносы -> отдельные <p>, одиночные сохраняем как есть
    parts = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    if not parts:
        return f"<p>{html.escape(text.strip())}</p>"
    return "".join(f"<p>{html.escape(p)}</p>" for p in parts)

def listify(items, cls="list"):
    if not items:
        return ""
    return "<ul class=\"%s\">%s</ul>" % (
        cls,
        "".join(f"<li>{html.escape(i)}</li>" for i in items),
    )

def code_list(items, cls="examples"):
    if not items:
        return ""
    return "<ul class=\"%s\">%s</ul>" % (
        cls,
        "".join(f"<li><code>{html.escape(i)}</code></li>" for i in items),
    )

def human_from_slug(slug: str) -> str:
    slug = slug.strip("/").split("/")[-1]
    slug = slug.replace("-", " ").replace("_", " ")
    return slug.capitalize() if slug else "Смотреть"

def parse_internal_links(raw: str, title_by_url: dict):
    """
    Поддерживаем два формата:
      1) "url1||Анкор 1||url2||Анкор 2"  (пары)
      2) "url1|url2|url3"                (только урлы; анкор берём из title_by_url или из слага)
    """
    if not raw:
        return []

    links = []
    if "||" in raw:
        # пары url||anchor
        chunks = [c.strip() for c in raw.split("||") if c.strip()]
        # ожидаем чётное число элементов: url, anchor, url, anchor...
        i = 0
        while i < len(chunks):
            href = chunks[i]; anchor = None
            if i + 1 < len(chunks):
                anchor = chunks[i + 1]
            i += 2
            href = norm_url(href)
            if not anchor:
                anchor = title_by_url.get(href) or human_from_slug(href)
            links.append((href, anchor))
    else:
        # просто список урлов через |
        for href in split_pipes(raw):
            href = norm_url(href)
            anchor = title_by_url.get(href) or human_from_slug(href)
            links.append((href, anchor))
    return links

def render_internal_links(links):
    if not links:
        return ""
    items = []
    for href, anchor in links:
        items.append(
            f'''<a class="related-card" href="{html.escape(href)}">
  <span class="related-title">{html.escape(anchor)}</span>
  <span class="related-more">Открыть →</span>
</a>'''
        )
    return '<div class="related-grid">\n' + "\n".join(items) + "\n</div>"

def faq_json_ld(pairs, canonical):
    if not pairs:
        return ""
    js = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {"@type": "Answer", "text": a},
            }
            for q, a in pairs if q and a
        ],
    }
    json_text = json.dumps(js, ensure_ascii=False, separators=(",", ":"))
    return '<script type="application/ld+json">' + html.escape(json_text) + "</script>"

def render_faq_html(pairs):
    if not pairs:
        return ""
    blocks = []
    for q, a in pairs:
        if not (q and a): 
            continue
        blocks.append(
            f'''<details class="faq">
  <summary>{html.escape(q)}</summary>
  <div class="answer">{paragraphize(a)}</div>
</details>'''
        )
    return "\n".join(blocks)

def load_template():
    for p in TEMPLATE_CANDIDATES:
        if p.exists():
            return p.read_text(encoding="utf-8")
    # Фолбэк-шаблон (минимальный, но аккуратный)
    return """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>{{meta_title}}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{{meta_description}}">
<meta name="keywords" content="{{meta_keywords}}">
<meta name="robots" content="index,follow">
<link rel="canonical" href="{{canonical}}">
<meta property="og:type" content="article">
<meta property="og:locale" content="ru_RU">
<meta property="og:title" content="{{meta_title}}">
<meta property="og:description" content="{{meta_description}}">
<meta property="og:url" content="{{canonical}}">
<meta name="sitemap:changefreq" content="{{changefreq}}">
<meta name="sitemap:priority" content="{{priority}}">
<style>
body{margin:0;background:#0b0b0f;color:#e8e8ee;font:16px/1.6 system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif}
.wrap{max-width:960px;margin:0 auto;padding:24px}
.header{display:flex;justify-content:space-between;align-items:center;margin:10px 0 24px}
.brand{font-weight:700;color:#f3f3f7}
.cta{display:inline-block;background:#e34b5a;color:#fff;padding:10px 16px;border-radius:12px;text-decoration:none}
h1{font-size:28px;margin:8px 0 16px}
h2{font-size:22px;margin:28px 0 12px}
section{margin:20px 0}
.list, .tips{list-style:disc;padding-left:20px}
.examples li code{background:#15151c;padding:6px 8px;border-radius:8px;display:inline-block}
.tags{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0 0;padding:0;list-style:none}
.tags li{background:#15151c;border:1px solid #262633;border-radius:999px;padding:6px 10px}
.faq{background:#101018;border:1px solid #242432;border-radius:12px;margin:10px 0;padding:10px 14px}
.faq summary{cursor:pointer;font-weight:600}
.related-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px;margin:6px 0 24px}
.related-card{display:flex;justify-content:space-between;align-items:center;text-decoration:none;background:#111119;border:1px solid #232334;border-radius:14px;padding:14px;color:#e8e8ee}
.related-card:hover{border-color:#3a3a55}
.related-title{font-weight:600}
.related-more{opacity:.75}
.small{opacity:.6;font-size:12px}
hr{border:0;border-top:1px solid #232334;margin:24px 0}
</style>
{{faq_json_ld}}
</head>
<body>
<div class="wrap">
  <div class="header">
    <div class="brand">Luna Chat</div>
    <a class="cta" href="https://t.me" target="_blank" rel="nofollow noopener">{{cta}}</a>
  </div>

  <h1>{{h1}}</h1>
  <section class="intro">{{intro_html}}</section>

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

  <section>
    <h2>{{scenario1_title}}</h2>
    {{scenario1_text_html}}
  </section>

  <section>
    <h2>{{scenario2_title}}</h2>
    {{scenario2_text_html}}
  </section>

  <section>
    <h2>{{scenario3_title}}</h2>
    {{scenario3_text_html}}
  </section>

  <section>
    <h2>Советы</h2>
    <div class="grid">
      <h3>Что делать</h3>
      {{tips_do_html}}
      <h3>Чего избегать</h3>
      {{tips_avoid_html}}
    </div>
  </section>

  <section>
    <h2>Частые вопросы</h2>
    {{faq_html}}
  </section>

  <section>
    <h2>Ещё по теме</h2>
    {{internal_links_html}}
  </section>

  <hr>
  <section>
    <ul class="tags">{{tags_html}}</ul>
  </section>

  <p class="small">Обновлено: {{lastmod}}</p>
</div>
</body>
</html>
"""

def render(template: str, ctx: dict) -> str:
    html_out = template
    for k, v in ctx.items():
        html_out = html_out.replace("{{" + k + "}}", v)
    # Неоставшиеся плейсхолдеры глушим пустотой, чтобы не торчали
    html_out = re.sub(r"\{\{[a-zA-Z0-9_\-]+\}\}", "", html_out)
    return html_out

# ------------------------ Основной процесс -----------------

def main():
    csv_path = None
    for c in CSV_CANDIDATES:
        if c.exists():
            csv_path = c
            break
    if not csv_path:
        raise SystemExit("[ERR] CSV not found: pages.csv or data/pages.csv")

    rows = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    # Мапа для анкоров внутренних ссылок
    title_by_url = {}
    for r in rows:
        url = norm_url(r.get("url") or ("/chat/" + (r.get("slug") or slugify_from_url("")) + "/"))
        title = (r.get("title") or r.get("h1") or "").strip()
        if url and title:
            title_by_url[url] = title

    template = load_template()
    lastmod = now_moscow_iso()

    for r in rows:
        # поля CSV
        url = norm_url(r.get("url") or "")
        slug = (r.get("slug") or slugify_from_url(url))
        out_dir = OUT_ROOT / Path(url.strip("/"))
        out_path = out_dir / "index.html"
        out_dir.mkdir(parents=True, exist_ok=True)

        title = (r.get("title") or "").strip()
        h1 = (r.get("h1") or title or "").strip()

        meta_title = (r.get("meta_title") or title or h1 or "").strip()
        meta_description = (r.get("meta_description") or r.get("description") or "").strip()
        meta_keywords = ",".join(split_pipes(r.get("tags") or ""))

        intro_html = paragraphize(r.get("intro") or "")
        cta = (r.get("cta") or "Открыть в Telegram").strip()

        bullets_html = listify(split_pipes(r.get("bullets") or ""), cls="list")
        tips_do_html = listify(split_pipes(r.get("tips_do") or ""), cls="tips")
        tips_avoid_html = listify(split_pipes(r.get("tips_avoid") or ""), cls="tips")
        tags_html = "".join(f"<li>#{html.escape(t)}</li>" for t in split_pipes(r.get("tags") or ""))

        examples_html = code_list(split_pipes(r.get("examples") or ""), cls="examples")

        # h2 секции (a..d)
        h2a_title = (r.get("h2a_title") or "").strip()
        h2a_text_html = paragraphize(r.get("h2a_text") or "")
        h2b_title = (r.get("h2b_title") or "").strip()
        h2b_text_html = paragraphize(r.get("h2b_text") or "")
        h2c_title = (r.get("h2c_title") or "").strip()
        h2c_text_html = paragraphize(r.get("h2c_text") or "")
        h2d_title = (r.get("h2d_title") or "").strip()
        h2d_text_html = paragraphize(r.get("h2d_text") or "")

        # сценарии
        scenario1_title = (r.get("scenario1_title") or "").strip()
        scenario1_text_html = paragraphize(r.get("scenario1_text") or "")
        scenario2_title = (r.get("scenario2_title") or "").strip()
        scenario2_text_html = paragraphize(r.get("scenario2_text") or "")
        scenario3_title = (r.get("scenario3_title") or "").strip()
        scenario3_text_html = paragraphize(r.get("scenario3_text") or "")

        # FAQ пары
        faq_pairs = []
        for i in range(1, 7):
            q = (r.get(f"faq{i}_q") or "").strip()
            a = (r.get(f"faq{i}_a") or "").strip()
            if q and a:
                faq_pairs.append((q, a))
        faq_html = render_faq_html(faq_pairs)

        # Внутренние ссылки
        internal_links_raw = r.get("internal_links") or ""
        internal_links = parse_internal_links(internal_links_raw, title_by_url)
        internal_links_html = render_internal_links(internal_links)

        # каноникал и sitemap метаданные
        changefreq = (r.get("changefreq") or "weekly").strip()
        priority = (r.get("priority") or "0.7").strip()
        canonical = (r.get("canonical") or (SITE_BASE + url)).strip()

        # JSON-LD
        faq_schema = faq_json_ld(faq_pairs, canonical)

        ctx = {
            "meta_title": html.escape(meta_title),
            "meta_description": html.escape(meta_description),
            "meta_keywords": html.escape(meta_keywords),
            "canonical": html.escape(canonical),
            "h1": html.escape(h1),
            "intro_html": intro_html,
            "cta": html.escape(cta),
            "bullets_html": bullets_html,
            "tags_html": tags_html,
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
            "scenario1_title": html.escape(scenario1_title),
            "scenario1_text_html": scenario1_text_html,
            "scenario2_title": html.escape(scenario2_title),
            "scenario2_text_html": scenario2_text_html,
            "scenario3_title": html.escape(scenario3_title),
            "scenario3_text_html": scenario3_text_html,
            "faq_html": faq_html,
            "faq_json_ld": faq_schema,
            "internal_links_html": internal_links_html,
            "changefreq": html.escape(changefreq),
            "priority": html.escape(priority),
            "lastmod": html.escape(lastmod),
        }

        page_html = render(template, ctx)
        out_path.write_text(page_html, encoding="utf-8")
        print(f"[OK] {url} -> {out_path}")

    print(f"\nDone. Generated {len(rows)} page(s).")

if __name__ == "__main__":
    main()
