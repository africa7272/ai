#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re, html, datetime
from pathlib import Path
from email.utils import format_datetime

# === Нормализация ссылок на Telegram-бота по всему сайту ===
def normalize_tg_links():
    """
    Во всех .html:
      - любые href на https://t.me/luciddreams?start=... → заменяем на каноническую
      - добавляем target="_blank" и rel="nofollow noopener" на эти ссылки
    Другие t.me (например, SafeNetVpn_bot) не трогаем.
    """
    import re
    from pathlib import Path

    TG_URL = "https://t.me/luciddreams?start=_tgr_ChFKPawxOGRi"
    root = Path(__file__).resolve().parents[1]  # корень репозитория

    changed = 0
    # любые варианты ссылки на нашего бота
    href_any = re.compile(r'https://t\.me/luciddreams\?start=[^"\s<]+', re.I)
    # <a ... href="TG_URL" ...> и <a ... href='TG_URL' ...>
    href_canonical_dq = re.compile(r'<a\b([^>]*?)href="' + re.escape(TG_URL) + r'"([^>]*)>', re.I)
    href_canonical_sq = re.compile(r"<a\b([^>]*?)href='" + re.escape(TG_URL) + r"'([^>]*)>", re.I)

    def add_attrs(m, quote='"'):
        before, after = m.group(1), m.group(2)
        tag = f"<a{before}href={quote}{TG_URL}{quote}{after}>"
        low = tag.lower()
        if "target=" not in low:
            tag = tag[:-1] + ' target="_blank">'
        if "rel=" not in low:
            tag = tag[:-1] + ' rel="nofollow noopener">'
        return tag

    for p in root.rglob("*.html"):
        txt = p.read_text(encoding="utf-8", errors="ignore")
        orig = txt

        # 1) заменить любые варианты ссылки на каноническую
        txt = href_any.sub(TG_URL, txt)

        # 2) добавить target/rel, если их нет
        txt = href_canonical_dq.sub(lambda m: add_attrs(m, '"'), txt)
        txt = href_canonical_sq.sub(lambda m: add_attrs(m, "'"), txt)

        if txt != orig:
            p.write_text(txt, encoding="utf-8")
            changed += 1

    print(f"Normalized Telegram links in {changed} files.")


ROOT = Path(__file__).resolve().parents[1]
SITE = "https://gorod-legends.ru"
ART_DIR = ROOT / "articles"
LATEST_LIMIT = 50
BUILD_AT = datetime.datetime.utcnow()

def read_meta(text: str):
    def m(name):
        mo = re.search(rf'<meta\s+name=["\']{re.escape(name)}["\']\s+content=["\'](.*?)["\']', text, flags=re.I|re.S)
        return mo.group(1).strip() if mo else ""
    tmo = re.search(r"<title>(.*?)</title>", text, flags=re.I|re.S)
    title = html.unescape(tmo.group(1).strip()) if tmo else ""
    desc  = m("description")
    date  = m("date")  # ожидаем YYYY-MM-DD
    # Фолбек, если даты нет — ставим текущую
    if not date:
        date = BUILD_AT.strftime("%Y-%m-%d")
    # h1 как фолбек заголовка
    if not title:
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", text, flags=re.I|re.S)
        if h1:
            title = re.sub("<.*?>", "", h1.group(1)).strip()
    return {"title": title, "desc": desc, "date": date}

def collect_articles():
    items = []
    for p in sorted(ART_DIR.glob("*.html")):
        if p.name.lower() == "index.html":
            continue
        rel = "/" + p.relative_to(ROOT).as_posix()
        txt = p.read_text(encoding="utf-8", errors="ignore")
        meta = read_meta(txt)
        y = meta["date"][:4]
        items.append({
            "path": rel,
            "title": meta["title"] or p.stem.replace("-", " ").title(),
            "desc": meta["desc"] or "",
            "date": meta["date"],
            "year": y,
        })
    # Новые первыми
    items.sort(key=lambda x: x["date"], reverse=True)
    return items

def write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

def layout_list(title, items, canonical_url):
    lis = []
    for it in items:
        lis.append(f'''<li>
  <a href="{it["path"]}">{html.escape(it["title"])}</a>
  <div class="meta">{it["date"]}</div>
  <p class="desc">{html.escape(it["desc"][:220])}</p>
</li>''')
    return f'''<!doctype html><html lang="ru"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(title)} — список материалов">
<link rel="canonical" href="{canonical_url}">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="alternate icon" href="/favicon.ico" sizes="any">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<style>
body{{font-family:Arial,system-ui;background:#0d0d17;color:#f5f5f5;margin:0}}
main{{max-width:880px;margin:0 auto;padding:24px 18px}}
a{{color:#e56fc6;text-decoration:none}} a:hover{{text-decoration:underline}}
h1{{font-size:32px;margin:6px 0 16px}}
ul{{list-style:none;padding:0;display:grid;gap:14px}}
li{{border:1px solid #262636;border-radius:12px;padding:12px;background:#10101a}}
.meta{{font-size:13px;color:#b9b9c3;margin:4px 0}}
.desc{{font-size:14px;color:#ddd;margin:6px 0 0}}
nav a{{margin-right:10px}}
</style>
</head><body><main>
<nav><a href="/">Главная</a> · <a href="/articles/">Статьи</a></nav>
<h1>{html.escape(title)}</h1>
<ul>{''.join(lis)}</ul>
</main></body></html>'''

def build_articles_index(items):
    latest = items[:LATEST_LIMIT]
    html_out = layout_list("Статьи Lucid Dreams — последние материалы", latest, f"{SITE}/articles/")
    write(ROOT / "articles" / "index.html", html_out)

def build_year_archives(items):
    by_year = {}
    for it in items:
        by_year.setdefault(it["year"], []).append(it)
    for y, arr in by_year.items():
        # уже отсортированы по дате убыв.
        title = f"Архив {y} — статьи Lucid Dreams"
        url = f"{SITE}/articles/{y}/"
        html_out = layout_list(title, arr, url)
        write(ROOT / "articles" / y / "index.html", html_out)

def build_sitemap(items):
    urls = [
        {"loc": f"{SITE}/", "prio":"0.9"},
        {"loc": f"{SITE}/articles/", "prio":"0.7"},
    ]
    years = sorted({it["year"] for it in items})
    for y in years:
        urls.append({"loc": f"{SITE}/articles/{y}/", "prio":"0.6"})
    for it in items:
        urls.append({"loc": f"{SITE}{it['path']}", "prio":"0.75"})
    today = BUILD_AT.strftime("%Y-%m-%d")
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        lines.append(
            f"<url><loc>{u['loc']}</loc><lastmod>{today}</lastmod>"
            f"<changefreq>weekly</changefreq><priority>{u['prio']}</priority></url>"
        )
    lines.append('</urlset>')
    write(ROOT / "sitemap.xml", "\n".join(lines))

def build_rss(items, limit=20):
    now_http = format_datetime(BUILD_AT)
    parts = [f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>Lucid Dreams — обновления</title>
  <link>{SITE}/</link>
  <description>Новые статьи Lucid Dreams.</description>
  <language>ru-ru</language>
  <lastBuildDate>{now_http}</lastBuildDate>
  <ttl>180</ttl>''']
    for it in items[:limit]:
        parts.append(f'''  <item>
    <title>{html.escape(it["title"])}</title>
    <link>{SITE}{it["path"]}</link>
    <guid isPermaLink="true">{SITE}{it["path"]}</guid>
    <pubDate>{now_http}</pubDate>
    <description>{html.escape((it["desc"] or it["title"])[:260])}</description>
  </item>''')
    parts.append('</channel></rss>')
    write(ROOT / "rss.xml", "\n".join(parts))

def main():
        normalize_tg_links()  # <-- добавить эту строку
    items = collect_articles()
    build_articles_index(items)
    build_year_archives(items)
    build_sitemap(items)
    build_rss(items)
    print(f"Built {len(items)} articles → index, year archives, sitemap, rss.")
    items = collect_articles()
    build_articles_index(items)
    build_year_archives(items)
    build_sitemap(items)
    build_rss(items)
    print(f"Built {len(items)} articles → index, year archives, sitemap, rss.")

if __name__ == "__main__":
    main()
