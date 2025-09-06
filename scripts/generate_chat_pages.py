#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Генератор HTML-страниц для /docs/chat/... по CSV

Зачем: чтобы ВСЕ новые страницы выглядели как эталон
/docs/chat/chat-s-devushkoi-online/ (градиентный hero, буллеты,
FAQ, липкая CTA и т.д.), но с разными текстами из таблицы.

Делает:
- Читает CSV (по умолчанию data/pages.csv)
- Для каждой строки пишет <repo>/<url>/index.html (всегда перезаписывает)
- Тянет <style>, tailwind.config, <header>, <footer> из эталонной HTML-страницы
- Может чистить папку страницы (--clean) и удалять конкурирующие .md/.mdx (--replace-md)
- Ставит build-ярлык в <head> для визуальной проверки обновления

Обязательные колонки CSV: url,title,description
Необязательные: h1,intro,cta,bullets,faq1_q,faq1_a … faq10_q,faq10_a

ENV (для CI):
  BASE_URL      (default: https://gorod-legends.ru)
  BOT_URL       (default: https://t.me/luciddreams?start=_tgr_ChFKPawxOGRi)
  METRIKA_ID    (default: 103658483)
  OG_DEFAULT    (default: /assets/og-cover.jpg)
  WRITE_SITEMAP ("1" — писать sitemap.xml)
"""

import os, csv, pathlib, re, html, json, argparse, sys, shutil
from datetime import datetime, timezone
from typing import List, Dict

# ---------- CLI ----------
p = argparse.ArgumentParser(description="Generate /docs/chat pages from CSV.")
p.add_argument("--csv", default="data/pages.csv", help="CSV path")
p.add_argument("--out", default=".", help="Output root (repo root)")
p.add_argument("--template", default="docs/chat/chat-s-devushkoi-online/index.html",
               help="Master HTML (эталон) — из него возьмём header/styles/footer")
p.add_argument("--clean", action="store_true", help="Очистить папку страницы перед записью")
p.add_argument("--replace-md", action="store_true", help="Удалять index.md/mdx и *.md/mdx в папке страницы")
args = p.parse_args()

ROOT = pathlib.Path(".").resolve()
CSV_PATH = (ROOT / args.csv).resolve()
OUT_ROOT = (ROOT / args.out).resolve()
TEMPLATE = (ROOT / args.template).resolve()

# ---------- ENV ----------
BASE_URL   = os.getenv("BASE_URL", "https://gorod-legends.ru").rstrip("/")
BOT_URL    = os.getenv("BOT_URL", "https://t.me/luciddreams?start=_tgr_ChFKPawxOGRi")
METRIKA_ID = os.getenv("METRIKA_ID", "103658483")
OG_DEFAULT = os.getenv("OG_DEFAULT", "/assets/og-cover.jpg")
WRITE_SITEMAP = os.getenv("WRITE_SITEMAP", "0") == "1"

BUILD_TAG = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# ---------- helpers ----------
def read_text(p: pathlib.Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore") if p.exists() else ""

def extract(text: str, pattern: str) -> str:
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(0) if m else ""

def esc(x: str) -> str:
    return html.escape((x or "").strip(), quote=True)

def norm_url(u: str) -> str:
    u = (u or "").strip()
    if not u: return "/"
    if not u.startswith("/"): u = "/" + u
    if not u.endswith("/"):  u = u + "/"
    u = re.sub(r"//+", "/", u)
    return u

def bullets_block(val: str) -> str:
    if not val: return ""
    items = [s.strip() for s in (val.split("|") if "|" in val else val.splitlines()) if s.strip()]
    if not items: return ""
    lis = "\n".join(
        f'<li class="flex gap-3"><span class="w-2 h-2 mt-2 rounded-full bg-accent-500"></span><span class="text-zinc-300">{esc(it)}</span></li>'
        for it in items
    )
    return f"""
    <section class="py-10 border-t border-white/5">
      <div class="max-w-6xl mx-auto px-4">
        <h2 class="text-2xl font-semibold">Почему это удобно</h2>
        <ul class="mt-4 grid gap-3">{lis}</ul>
      </div>
    </section>"""

def faq_items(rec: Dict[str,str]) -> List[Dict[str,str]]:
    res = []
    for i in range(1, 11):
        q = (rec.get(f"faq{i}_q") or "").strip()
        a = (rec.get(f"faq{i}_a") or "").strip()
        if q and a: res.append({"q": q, "a": a})
    return res

def faq_html(items: List[Dict[str,str]]) -> str:
    if not items:
        return '<p class="text-zinc-400">Вопросов пока нет — задайте в нашем Telegram.</p>'
    return "\n".join(
        f'<details class="glass rounded-xl p-4"><summary class="cursor-pointer font-medium text-white">{esc(it["q"])}</summary><p class="mt-2 text-zinc-300">{esc(it["a"])}</p></details>'
        for it in items
    )

def faq_jsonld(items: List[Dict[str,str]]) -> str:
    if not items: return "{}"
    data = {"@context":"https://schema.org","@type":"FAQPage",
            "mainEntity":[{"@type":"Question","name":it["q"],
                           "acceptedAnswer":{"@type":"Answer","text":it["a"]}} for it in items]}
    return json.dumps(data, ensure_ascii=False, separators=(",",":"))

def build_related(rows: List[Dict[str,str]], current_url: str, limit: int = 6) -> str:
    parts = [p for p in current_url.strip("/").split("/") if p]
    prefix = "/" + "/".join(parts[:3]) + "/" if len(parts) >= 3 else "/" + "/".join(parts) + "/"
    pool = [r for r in rows if norm_url(r.get("url","")).startswith(prefix) and norm_url(r.get("url","")) != current_url]
    cards = []
    for r in pool[:limit]:
        title = r.get("title") or r.get("keyword") or "Подробнее"
        href = norm_url(r["url"])
        cards.append(f'<a class="glass rounded-xl p-4 hover:bg-white/10" href="{esc(href)}">{esc(title)}</a>')
    return "\n".join(cards) or '<p class="text-zinc-400">Скоро добавим больше страниц.</p>'

# ---------- master template parts (из эталона) ----------
master = read_text(TEMPLATE)
if not master:
    print(f"[ERR] Не найден эталонный HTML: {TEMPLATE}", file=sys.stderr); sys.exit(2)

tailwind_cfg = extract(master, r"<script>\s*tailwind\.config[\s\S]*?</script>") \
               or extract(read_text(ROOT/"index.html"), r"<script>\s*tailwind\.config[\s\S]*?</script>")
style_block  = extract(master, r"<style>[\s\S]*?</style>") \
               or extract(read_text(ROOT/"index.html"), r"<style>[\s\S]*?</style>")
header_block = extract(master, r"<header[\s\S]*?</header>")
footer_block = extract(master, r"<footer[\s\S]*?</footer>")
tw_cdn = '<script src="https://cdn.tailwindcss.com"></script>'

# Нормализуем шапку: бренд → '/', CTA → BOT_URL
def normalize_header(h: str) -> str:
    if not h: return ""
    h = re.sub(r'(<header[\s\S]*?<a\s+href=")[^"]*', r'\1/', h, count=1)
    h = re.sub(r'href="https?://t\.me/[^"]+"', f'href="{BOT_URL}"', h)
    h = re.sub(r'(>)(\s*)(Открыть в Telegram)(\s*)(<)', r'\1Открыть в Telegram\5', h)
    return h

header_block = normalize_header(header_block)

PAGE_TMPL = """<!doctype html>
<html lang="ru">
<head>
  <!-- build: {build_tag} -->
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <meta name="description" content="{desc}">
  <link rel="canonical" href="{canonical}">
  <meta name="theme-color" content="#100B10">

  <meta property="og:type" content="article">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{desc}">
  <meta property="og:url" content="{canonical}">
  <meta property="og:image" content="{og_image}">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{title}">
  <meta name="twitter:description" content="{desc}">
  <meta name="twitter:image" content="{og_image}">

  {tw_cdn}
  {tailwind_cfg}
  {style_block}
</head>
<body class="bg-brand-900 text-zinc-100 selection:bg-accent-500 selection:text-white">
{header}

  <main>
    <!-- HERO -->
    <section class="gradient-hero pt-10 pb-10 border-b border-white/5">
      <div class="max-w-6xl mx-auto px-4 grid md:grid-cols-2 gap-8 items-center">
        <div>
          <h1 class="text-3xl md:text-4xl font-bold leading-tight">{h1}</h1>
          <p class="mt-4 text-zinc-300">{intro}</p>
          <div class="mt-6 flex flex-wrap gap-3">
            <a href="{bot_url}" target="_blank" rel="noopener nofollow" class="inline-flex items-center gap-2 px-5 py-3 rounded-xl bg-accent-500 hover:bg-accent-400 text-white font-medium shadow-soft">{cta}</a>
            <a href="#faq" class="inline-flex items-center gap-2 px-5 py-3 rounded-xl bg-white/5 hover:bg-white/10 text-white">Вопросы и ответы</a>
          </div>
        </div>
        <div class="relative hidden md:block">
          <div class="hidden-photo rounded-2xl h-64"></div>
          <div class="tile-overlay"><span class="px-3 py-1 rounded-full bg-white/10 text-xs text-white/80">Анонимно · Без VPN · 24/7</span></div>
        </div>
      </div>
    </section>

    {bullets_html}

    <!-- FAQ -->
    <section id="faq" class="py-10 border-t border-white/5">
      <div class="max-w-6xl mx-auto px-4">
        <h2 class="text-2xl font-semibold">Частые вопросы</h2>
        <div class="mt-4 space-y-3">
          {faq_html}
        </div>
      </div>
    </section>

    <!-- Related -->
    <section class="py-10 border-t border-white/5">
      <div class="max-w-6xl mx-auto px-4">
        <h2 class="text-2xl font-semibold">Ещё по теме</h2>
        <div class="mt-4 grid sm:grid-cols-2 md:grid-cols-3 gap-3">
          {related_html}
        </div>
      </div>
    </section>
  </main>

  <!-- Sticky CTA (mobile) -->
  <div class="fixed inset-x-0 bottom-0 z-40 md:hidden backdrop-blur bg-brand-900/80 border-t border-white/10">
    <div class="max-w-6xl mx-auto px-4 py-3">
      <a href="{bot_url}" target="_blank" rel="noopener nofollow" class="flex items-center justify-center px-5 py-3 rounded-xl bg-accent-500 text-white font-semibold">{cta}</a>
    </div>
  </div>

{footer}

<script type="application/ld+json">
{faq_jsonld}
</script>

<!-- Yandex.Metrika -->
<script type="text/javascript">
(function(m,e,t,r,i,k,a){{
  m[i]=m[i]||function(){{(m[i].a=m[i].a||[]).push(arguments)}};
  m[i].l=1*new Date();
  for (var j=0; j<document.scripts.length; j++) {{ if (document.scripts[j].src===r) return; }}
  k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)
}})(window, document, 'script', 'https://mc.yandex.ru/metrika/tag.js?id={metrika}', 'ym');
ym({metrika}, 'init', {{ssr:true, webvisor:true, clickmap:true, ecommerce:"dataLayer", accurateTrackBounce:true, trackLinks:true}});
</script>
<noscript><div><img src="https://mc.yandex.ru/watch/{metrika}" style="position:absolute; left:-9999px;" alt=""></div></noscript>

<script>document.getElementById('y')&&(document.getElementById('y').textContent=new Date().getFullYear());</script>
</body>
</html>
"""

# ---------- main ----------
def main() -> int:
    if not CSV_PATH.exists():
        print(f"[ERR] CSV не найден: {CSV_PATH}", file=sys.stderr); return 2

    # читаем CSV
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    # защита от дублей: берём последнюю запись на each url
    by_url: Dict[str, Dict[str,str]] = {}
    for rec in rows:
        u = norm_url(rec.get("url",""))
        if u != "/":
            by_url[u] = rec

    generated = []
    for url, rec in by_url.items():
        out_dir = (OUT_ROOT / url.lstrip("/")).resolve()

        # чистим папку (если нужно)
        if args.clean and out_dir.exists():
            shutil.rmtree(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        # удаляем конкурирующие md/mdx (если нужно)
        if args.replace_md:
            for pattern in ("index.md","index.mdx","*.md","*.mdx"):
                for p in out_dir.glob(pattern):
                    try:
                        p.unlink()
                        print(f"⊖ removed {p.relative_to(ROOT)}")
                    except Exception as e:
                        print(f"[WARN] cannot remove {p}: {e}")

        out_file = out_dir / "index.html"

        title = (rec.get("title") or rec.get("keyword") or "Чат с девушкой онлайн").strip()
        desc  = (rec.get("description") or rec.get("intro") or "Уютное общение, лёгкий флирт и поддержка 24/7. Откройте чат в Telegram.").strip()
        h1    = (rec.get("h1") or title).strip()
        intro = (rec.get("intro") or desc).strip()
        cta   = (rec.get("cta") or "Открыть в Telegram").strip()
        bullets = rec.get("bullets","")

        faqs = faq_items(rec)

        html_out = PAGE_TMPL.format(
            build_tag=BUILD_TAG,
            title=esc(title),
            desc=esc(desc),
            canonical=esc(f"{BASE_URL}{url}"),
            og_image=esc(OG_DEFAULT),
            tw_cdn=tw_cdn,
            tailwind_cfg=tailwind_cfg,
            style_block=style_block,
            header=header_block,
            footer=footer_block,
            h1=esc(h1),
            intro=esc(intro),
            bot_url=esc(BOT_URL),
            cta=esc(cta),
            bullets_html=bullets_block(bullets),
            faq_html=faq_html(faqs),
            related_html=build_related(rows, url, 6),
            faq_jsonld=faq_jsonld(faqs),
            metrika=esc(METRIKA_ID),
        )

        out_file.write_text(html_out, encoding="utf-8")
        generated.append(url)
        print(f"✔ {url} → {out_file.relative_to(ROOT)}")

    # опционально sitemap
    if WRITE_SITEMAP and generated:
        sm = OUT_ROOT / "sitemap.xml"
        with sm.open("w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
            for u in generated:
                f.write("  <url>\n")
                f.write(f"    <loc>{BASE_URL}{u}</loc>\n")
                f.write(f"    <lastmod>{BUILD_TAG}</lastmod>\n")
                f.write("    <changefreq>weekly</changefreq>\n")
                f.write("    <priority>0.7</priority>\n")
                f.write("  </url>\n")
            f.write("</urlset>\n")
        print(f"✔ sitemap.xml → {sm.relative_to(ROOT)}")

    print(f"Готово: сгенерировано/обновлено — {len(generated)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
