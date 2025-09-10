#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Генератор страниц из CSV (новый формат):

url,title,keyword,slug,meta_title,meta_description,h1,intro,cta,bullets,tags,examples,
tips_do,tips_avoid,h2a_title,h2a_text,h2b_title,h2b_text,h2c_title,h2c_text,h2d_title,h2d_text,
scenario1_title,scenario1_text,scenario2_title,scenario2_text,scenario3_title,scenario3_text,
faq1_q,faq1_a,faq2_q,faq2_a,faq3_q,faq3_a,faq4_q,faq4_a,faq5_q,faq5_a,faq6_q,faq6_a,
internal_links,changefreq,priority,canonical

Особенности:
- Путь берётся из url (например /chat/foo/ -> chat/foo/index.html)
- Внутренние ссылки можно передавать списком через | (без анкоров);
  анкор скрипт попробует найти по заголовку H1/Title готовой страницы или сгенерирует из слага.
- Если нужно кастомный анкор, можно указать как `/path||Анкор` (двойной «|» отделяет анкор от URL).
- CTA ссылка берётся из env CTA_URL (по умолчанию /18plus/).
- SITE_BASE берётся из env SITE_BASE (по умолчанию https://gorod-legends.ru) — для canonical/OG.
"""

import csv
import os
import re
import html
from pathlib import Path
from datetime import datetime, timezone, timedelta

SITE_BASE = os.getenv("SITE_BASE", "https://gorod-legends.ru").rstrip("/")
CTA_URL   = os.getenv("CTA_URL", "/18plus/")

ROOT = Path(".")  # корень репозитория (где лежат chat/, hub/ и т.д.)

def read_csv_rows(csv_path: Path):
    if not csv_path.exists():
        # fallback: data/pages.csv -> pages.csv
        alt = Path("pages.csv")
        if alt.exists():
            csv_path = alt
        else:
            raise SystemExit(f"[ERR] CSV not found: {csv_path}")
    rows = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({k: (v or "").strip() for k, v in r.items()})
    return rows

def ensure_trailing_slash(u: str) -> str:
    u = (u or "").strip()
    if not u:
        return "/"
    if not u.startswith("/"):
        u = "/" + u
    if not u.endswith("/"):
        u = u + "/"
    return u

def esc(s: str) -> str:
    return html.escape(s or "", quote=True)

def split_pipe(s: str):
    # generic splitter for lists stored as "a|b|c"
    return [x.strip() for x in (s or "").split("|") if x.strip()]

def pretty_from_slug(slug: str) -> str:
    slug = (slug or "").strip("/").split("/")[-1]
    s = slug.replace("-", " ").replace("_", " ")
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return "Подробнее"
    return s[:1].upper() + s[1:]

def url_to_file(url: str) -> Path:
    # /chat/foo/ -> chat/foo/index.html
    u = ensure_trailing_slash(url)
    return ROOT / u.lstrip("/") / "index.html"

def guess_anchor_for_url(u: str, rows_map):
    """Пытаемся найти анкор для внутренней ссылки:
       1) по заголовку H1/Title уже сгенерированной страницы
       2) по данным из CSV (h1/title)
       3) из слага"""
    try_file = url_to_file(u)
    if try_file.exists():
        txt = try_file.read_text("utf-8", errors="ignore")
        # <h1>...</h1>
        m = re.search(r"<h1[^>]*>(.*?)</h1>", txt, re.I | re.S)
        if m:
            t = re.sub(r"<[^>]+>", "", m.group(1)).strip()
            if t:
                return t
        # <title>...</title>
        m = re.search(r"<title[^>]*>(.*?)</title>", txt, re.I | re.S)
        if m:
            t = re.sub(r"<[^>]+>", "", m.group(1)).strip()
            if t:
                return t
    # по CSV
    if u in rows_map:
        t = rows_map[u].get("h1") or rows_map[u].get("title") or rows_map[u].get("meta_title")
        if t:
            return t
    # из слага
    return pretty_from_slug(u)

def parse_internal_links(raw: str, rows_map):
    """Поддержка двух форматов элементов:
       - '/path'                         (анкор определяется автоматически)
       - '/path||Анкор'                  (кастомный анкор)
       Элементы разделяются одиночным |
    """
    out = []
    for chunk in split_pipe(raw):
        if "||" in chunk:
            u, a = chunk.split("||", 1)
            u, a = u.strip(), a.strip()
            if u:
                out.append((u, a or guess_anchor_for_url(u, rows_map)))
        else:
            u = chunk
            out.append((u, guess_anchor_for_url(u, rows_map)))
    return out

def ul(items, klass=""):
    if not items:
        return ""
    li = "\n".join(f"<li>{esc(i)}</li>" for i in items)
    cls = f' class="{klass}"' if klass else ""
    return f"<ul{cls}>\n{li}\n</ul>"

def faq_block(pairs):
    if not pairs:
        return "", []
    details = []
    for q, a in pairs:
        if not (q or a):
            continue
        details.append(
            f'<details class="faq-item"><summary>{esc(q)}</summary><div><p>{esc(a)}</p></div></details>'
        )
    return "\n".join(details), pairs

def faq_json_ld(pairs, canonical):
    if not pairs:
        return ""
    js = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question",
             "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in pairs if q and a
        ]
    }
    return f'<script type="application/ld+json">{html.escape(str(js).replace("'", '"'))}</script>'

def now_msk_iso():
    # только для og:updated_time; sitemap берёт дату из коммитов
    msk = timezone(timedelta(hours=3))
    return datetime.now(msk).isoformat(timespec="seconds")

def render_page(row, rows_map):
    url          = ensure_trailing_slash(row.get("url") or f"/chat/{row.get('slug','')}/")
    slug         = (row.get("slug") or "").strip()
    title        = row.get("title") or row.get("h1") or row.get("meta_title") or pretty_from_slug(slug)
    meta_title   = row.get("meta_title") or title
    meta_descr   = row.get("meta_description") or row.get("description") or ""
    h1           = row.get("h1") or title
    intro        = row.get("intro") or ""
    cta_text     = row.get("cta") or "Открыть в Telegram"

    bullets      = split_pipe(row.get("bullets"))
    tags         = split_pipe(row.get("tags"))
    examples     = split_pipe(row.get("examples"))
    tips_do      = split_pipe(row.get("tips_do"))
    tips_avoid   = split_pipe(row.get("tips_avoid"))

    h2a_title    = row.get("h2a_title") or ""
    h2a_text     = row.get("h2a_text") or ""
    h2b_title    = row.get("h2b_title") or ""
    h2b_text     = row.get("h2b_text") or ""
    h2c_title    = row.get("h2c_title") or ""
    h2c_text     = row.get("h2c_text") or ""
    h2d_title    = row.get("h2d_title") or ""
    h2d_text     = row.get("h2d_text") or ""

    sc1_title    = row.get("scenario1_title") or ""
    sc1_text     = row.get("scenario1_text") or ""
    sc2_title    = row.get("scenario2_title") or ""
    sc2_text     = row.get("scenario2_text") or ""
    sc3_title    = row.get("scenario3_title") or ""
    sc3_text     = row.get("scenario3_text") or ""

    faq_pairs = [
        (row.get("faq1_q"), row.get("faq1_a")),
        (row.get("faq2_q"), row.get("faq2_a")),
        (row.get("faq3_q"), row.get("faq3_a")),
        (row.get("faq4_q"), row.get("faq4_a")),
        (row.get("faq5_q"), row.get("faq5_a")),
        (row.get("faq6_q"), row.get("faq6_a")),
    ]
    faq_pairs = [(q.strip(), a.strip()) for q, a in faq_pairs if (q or a)]
    faq_html, faq_for_jsonld = faq_block(faq_pairs)

    internal_links = parse_internal_links(row.get("internal_links", ""), rows_map)

    changefreq   = (row.get("changefreq") or "").lower()
    priority     = (row.get("priority") or "").strip()
    canonical    = (row.get("canonical") or (SITE_BASE + url)).strip()

    # Составные кусочки
    tags_html      = "" if not tags else '<div class="tags">' + " ".join(f'<span class="tag">{esc(t)}</span>' for t in tags) + "</div>"
    bullets_html   = ul(bullets, "bullets")
    examples_html  = ul(examples, "examples")
    tips_do_html   = ul(tips_do, "tips-do")
    tips_avoid_html= ul(tips_avoid, "tips-avoid")

    # внутренние ссылки (карточки)
    more_html = ""
    if internal_links:
        cards = []
        for link, text in internal_links:
            cards.append(f'<a class="card" href="{esc(link)}"><span>{esc(text)}</span><em>Открыть →</em></a>')
        more_html = '<section class="more"><h2>Ещё по теме</h2><div class="cards">' + "\n".join(cards) + "</div></section>"

    # JSON-LD FAQ
    faq_ld = faq_json_ld(faq_for_jsonld, canonical)

    # Мета для changefreq/priority (чтобы не потерять значения и можно было использовать дальше)
    sitemap_meta = ""
    if changefreq:
        sitemap_meta += f'<meta name="sitemap:changefreq" content="{esc(changefreq)}"/>\n'
    if priority:
        sitemap_meta += f'<meta name="sitemap:priority" content="{esc(priority)}"/>\n'

    # Простая разметка. Использует BEM/классы без зависимостей — подставится ваш CSS.
    html_page = f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>{esc(meta_title)}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{esc(meta_descr)}">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:type" content="article">
<meta property="og:title" content="{esc(meta_title)}">
<meta property="og:description" content="{esc(meta_descr)}">
<meta property="og:url" content="{esc(canonical)}">
<meta property="article:modified_time" content="{now_msk_iso()}">
{sitemap_meta}{faq_ld}
<style>
/* лёгкий системный стиль — опционально (можно убрать, если у вас свой CSS) */
body{{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;background:#0f0f10;color:#eaeaea;}}
.container{{max-width:980px;margin:0 auto;padding:24px 16px;}}
.header{{display:flex;align-items:center;gap:12px;}}
.btn{{display:inline-block;background:#e05666;color:#fff;padding:10px 16px;border-radius:10px;text-decoration:none;font-weight:600}}
.tags{{margin:8px 0 12px 0;display:flex;flex-wrap:wrap;gap:8px}}
.tag{{background:#1b1b1f;border:1px solid #2a2a2f;border-radius:999px;padding:4px 10px;font-size:12px;opacity:.9}}
.lead{{opacity:.9;margin:12px 0 18px 0;}}
.grid{{display:grid;gap:16px}}
.grid-2{{grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}}
section{{margin:28px 0}}
h1{{font-size:28px;margin:0 0 6px 0}}
h2{{font-size:20px;margin:18px 0 8px 0}}
ul{{margin:8px 0 8px 18px}}
.card{{display:flex;flex-direction:column;gap:2px;border:1px solid #25252a;background:#141417;padding:14px;border-radius:12px;text-decoration:none;color:inherit}}
.card em{{opacity:.6;font-style:normal;font-size:12px}}
.more .cards{{display:grid;gap:10px;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));}}
.faq-item summary{{cursor:pointer;font-weight:600}}
.small-muted{{font-size:12px;opacity:.6}}
.chips{{display:flex;gap:8px;flex-wrap:wrap}}
.hero-cta{{text-align:right}}
</style>
</head>
<body>
  <div class="container">
    <header class="header">
      <div style="width:10px;height:10px;background:#d44;border-radius:50%;"></div>
      <strong>Luna Chat</strong>
      <div class="hero-cta" style="margin-left:auto;">
        <a class="btn" href="{esc(CTA_URL)}" rel="noopener">{esc(cta_text)}</a>
      </div>
    </header>

    <article>
      <h1>{esc(h1)}</h1>
      {tags_html}
      <p class="lead">{esc(intro)}</p>

      {bullets_html}

      <section>
        <h2>{esc(h2a_title)}</h2>
        <p>{esc(h2a_text)}</p>
      </section>
      <section>
        <h2>{esc(h2b_title)}</h2>
        <p>{esc(h2b_text)}</p>
      </section>
      <section>
        <h2>{esc(h2c_title)}</h2>
        <p>{esc(h2c_text)}</p>
      </section>
      <section>
        <h2>{esc(h2d_title)}</h2>
        <p>{esc(h2d_text)}</p>
      </section>

      <section class="grid-2">
        <div>
          <h2>Примеры фраз</h2>
          {examples_html}
        </div>
        <div>
          <h2>Что делать</h2>
          {tips_do_html}
          <h2 style="margin-top:14px">Чего избегать</h2>
          {tips_avoid_html}
        </div>
      </section>

      {"<section><h2>"+esc(sc1_title)+"</h2><p>"+esc(sc1_text)+"</p></section>" if sc1_title or sc1_text else ""}
      {"<section><h2>"+esc(sc2_title)+"</h2><p>"+esc(sc2_text)+"</p></section>" if sc2_title or sc2_text else ""}
      {"<section><h2>"+esc(sc3_title)+"</h2><p>"+esc(sc3_text)+"</p></section>" if sc3_title or sc3_text else ""}

      <section>
        <h2>Частые вопросы</h2>
        {faq_html}
      </section>

      {more_html}

      <footer style="margin-top:34px">
        <div class="small-muted">© 2025 Luna Chat · 18+. Пользуйтесь уважительно. Не делитесь личными данными.</div>
      </footer>
    </article>
  </div>
</body>
</html>"""
    return url, html_page

def build_pages(csv_path: Path):
    rows = read_csv_rows(csv_path)

    # мапа url -> исходные данные для анкоров
    rows_map = {}
    for r in rows:
        u = ensure_trailing_slash(r.get("url") or "")
        if u:
            rows_map[u] = r

    for r in rows:
        url, html_page = render_page(r, rows_map)
        out_file = url_to_file(url)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(html_page, encoding="utf-8")
        print(f"[OK] {url} -> {out_file}")

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default="data/pages.csv", help="Путь к CSV (по умолчанию data/pages.csv)")
    args = parser.parse_args()
    build_pages(Path(args.csv))

if __name__ == "__main__":
    main()
