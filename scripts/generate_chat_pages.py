#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SEO-ориентированный генератор страниц (без изображений) для gorod-legends.ru

Гарантии:
- Визуально как эталонная страница (берём header/styles/footer из --template)
- Богатый текст без картинок: ToC, секции, советы, примеры, FAQ
- Структурка JSON-LD: WebPage + BreadcrumbList + FAQPage + ItemList(related)
- Жёсткая перелинковка: блок "Ещё по теме" всегда заполнен (подбирается по CSV)

CSV (новая схема, см. ниже):
url,title,keyword,description,intro,cta,bullets,variants,examples,tips_do,tips_avoid,sec1_h2,sec1_text,sec2_h2,sec2_text,sec3_h2,sec3_text,faq1_q,faq1_a,...,faq10_q,faq10_a

Поля optional: h1, related (pipe: /chat/.../), brand

Запуск:
  python3 scripts/generate_chat_pages.py \
    --csv data/pages.csv \
    --out . \
    --template docs/chat/chat-s-devushkoi-online/index.html \
    --clean --replace-md
"""

import os, csv, pathlib, re, html, json, argparse, sys, shutil
from datetime import datetime, timezone
from typing import List, Dict

# ---------- CLI ----------
p = argparse.ArgumentParser(description="Generate SEO-rich chat landings from CSV.")
p.add_argument("--csv", default="data/pages.csv", help="Path to CSV")
p.add_argument("--out", default=".", help="Output root (repo root)")
p.add_argument("--template", default="docs/chat/chat-s-devushkoi-online/index.html",
               help="Master HTML to copy header/styles/footer from")
p.add_argument("--clean", action="store_true", help="Remove page folder before writing")
p.add_argument("--replace-md", action="store_true", help="Delete *.md/*.mdx in page folder")
args = p.parse_args()

ROOT = pathlib.Path(".").resolve()
CSV_PATH = (ROOT / args.csv).resolve()
OUT_ROOT = (ROOT / args.out).resolve()
TPL_PATH = (ROOT / args.template).resolve()

# ---------- ENV ----------
BASE_URL   = os.getenv("BASE_URL", "https://gorod-legends.ru").rstrip("/")
BOT_URL    = os.getenv("BOT_URL", "https://t.me/luciddreams?start=_tgr_ChFKPawxOGRi")
METRIKA_ID = os.getenv("METRIKA_ID", "103658483")
OG_DEFAULT = os.getenv("OG_DEFAULT", "/assets/og-cover.jpg")
WRITE_SITEMAP = os.getenv("WRITE_SITEMAP", "0") == "1"
BRAND_DEFAULT = os.getenv("BRAND", "Luna Chat")

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

def split_pipe(val: str) -> List[str]:
    if not val: return []
    if "|" in val:
        return [s.strip() for s in val.split("|") if s.strip()]
    # поддержим перевод строки
    return [s.strip(" •-—\t") for s in val.splitlines() if s.strip()]

def para_html(text: str) -> str:
    if not text: return ""
    # Разбиваем двойным переводом строки или | на абзацы
    parts = [t.strip() for t in re.split(r"\n{2,}|\|", text) if t.strip()]
    return "\n".join(f"<p class=\"mt-3 text-zinc-300\">{esc(t)}</p>" for t in parts)

def slugify(s: str) -> str:
    s = re.sub(r"<.*?>", "", s or "")
    s = s.strip().lower()
    s = s.replace("ё", "e")
    s = re.sub(r"[^a-z0-9а-я\s_-]", "", s)
    s = re.sub(r"\s+", "-", s)
    return s[:80].strip("-") or "sec"

# ---------- master parts from template ----------
master = read_text(TPL_PATH)
if not master:
    print(f"[ERR] Template not found: {TPL_PATH}", file=sys.stderr); sys.exit(2)

tailwind_cfg = extract(master, r"<script>\s*tailwind\.config[\s\S]*?</script>") \
               or extract(read_text(ROOT/"index.html"), r"<script>\s*tailwind\.config[\s\S]*?</script>")
style_block  = extract(master, r"<style>[\s\S]*?</style>") \
               or extract(read_text(ROOT/"index.html"), r"<style>[\s\S]*?</style>")
header_block = extract(master, r"<header[\s\S]*?</header>")
footer_block = extract(master, r"<footer[\s\S]*?</footer>")
tw_cdn = '<script src="https://cdn.tailwindcss.com"></script>'

def normalize_header(h: str) -> str:
    if not h: return ""
    h = re.sub(r'(<header[\s\S]*?<a\s+href=")[^"]*', r'\1/', h, count=1)  # бренд → /
    h = re.sub(r'href="https?://t\.me/[^"]+"', f'href="{BOT_URL}"', h)     # CTA → бот
    h = re.sub(r'(>)(\s*)(Открыть в Telegram)(\s*)(<)', r'\1Открыть в Telegram\5', h)
    return h
header_block = normalize_header(header_block)

# ---------- page template ----------
PAGE_TMPL = """<!doctype html>
<html lang="ru">
<head>
  <!-- build: {build_tag} -->
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title_full}</title>
  <meta name="description" content="{desc_final}">
  <meta name="robots" content="index,follow,max-snippet:-1,max-image-preview:large,max-video-preview:-1">
  <link rel="canonical" href="{canonical}">
  <meta name="theme-color" content="#100B10">

  <meta property="og:type" content="article">
  <meta property="og:title" content="{title_full}">
  <meta property="og:description" content="{desc_final}">
  <meta property="og:url" content="{canonical}">
  <meta property="og:image" content="{og_image}">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{title_full}">
  <meta name="twitter:description" content="{desc_final}">
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

    <!-- TOC -->
    {toc_html}

    <!-- BENEFITS -->
    {benefits_html}

    <!-- SECTIONS -->
    {sections_html}

    <!-- DO/DONT + EXAMPLES -->
    {advice_html}
    {examples_html}

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

<!-- JSON-LD -->
<script type="application/ld+json">
{webpage_jsonld}
</script>
<script type="application/ld+json">
{breadcrumbs_jsonld}
</script>
<script type="application/ld+json">
{faq_jsonld}
</script>
<script type="application/ld+json">
{related_jsonld}
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

# ---------- content builders ----------
def benefits_block(bullets: List[str]) -> str:
    if not bullets: return ""
    lis = "\n".join(
        f'<li class="flex gap-3"><span class="w-2 h-2 mt-2 rounded-full bg-accent-500"></span><span class="text-zinc-300">{esc(b)}</span></li>'
        for b in bullets
    )
    return f"""
    <section class="py-10 border-t border-white/5">
      <div class="max-w-6xl mx-auto px-4">
        <h2 class="text-2xl font-semibold">Почему это удобно</h2>
        <ul class="mt-4 grid gap-3">{lis}</ul>
      </div>
    </section>"""

def advice_block(do_list: List[str], avoid_list: List[str]) -> str:
    if not do_list and not avoid_list: return ""
    col_do = "".join(f'<li class="py-1">✔ {esc(x)}</li>' for x in do_list)
    col_avoid = "".join(f'<li class="py-1">✖ {esc(x)}</li>' for x in avoid_list)
    return f"""
    <section class="py-10 border-t border-white/5">
      <div class="max-w-6xl mx-auto px-4">
        <h2 class="text-2xl font-semibold">Что делать и чего избегать</h2>
        <div class="mt-4 grid md:grid-cols-2 gap-6">
          <div class="glass rounded-xl p-4"><h3 class="font-medium text-white">Советы</h3><ul class="mt-2 text-zinc-300">{col_do or '<li class="py-1 text-zinc-400">Добавим позже.</li>'}</ul></div>
          <div class="glass rounded-xl p-4"><h3 class="font-medium text-white">Избегайте</h3><ul class="mt-2 text-zinc-300">{col_avoid or '<li class="py-1 text-zinc-400">Добавим позже.</li>'}</ul></div>
        </div>
      </div>
    </section>"""

def examples_block(examples: List[str], keyword: str) -> str:
    if not examples: return ""
    lis = "".join(f'<li class="py-1">&laquo;{esc(x)}&raquo;</li>' for x in examples[:12])
    return f"""
    <section class="py-10 border-t border-white/5" id="primeri">
      <div class="max-w-6xl mx-auto px-4">
        <h2 class="text-2xl font-semibold">Примеры первых фраз для «{esc(keyword)}»</h2>
        <ul class="mt-3 text-zinc-300">{lis}</ul>
      </div>
    </section>"""

def make_sections(rec: Dict[str,str], keyword: str, variants: List[str]) -> List[Dict[str,str]]:
    # Если секции заданы вручную — используем их. Иначе соберём универсальные.
    secs = []
    for i in [1,2,3]:
        h2 = (rec.get(f"sec{i}_h2") or "").strip()
        t  = (rec.get(f"sec{i}_text") or "").strip()
        if h2 or t:
            secs.append({"h2": h2 or "О чём эта страница", "html": para_html(t)})
    if secs:
        return secs

    # Автогенерация (без изображений)
    vline = (", ".join(variants[:3])) if variants else ""
    s1 = {
        "h2": f"Как начать {keyword} — мягко и без неловкости",
        "html": para_html(
            f"Начните с короткого приветствия и одной тёплой фразы. "
            f"Если хочется конкретики — используйте один из примеров ниже. "
            f"Главное — сохранить уважительный, спокойный тон и дать собеседнице пространство для ответа."
        )
    }
    s2 = {
        "h2": f"Что писать дальше и как поддерживать {keyword}",
        "html": para_html(
            "Держите комфортный темп: задавайте лёгкие вопросы, отмечайте детали и возвращайтесь к теме, "
            "на которую пришёл отклик. Не страшно делать паузы — диалог может идти в удобном для вас ритме."
            + (f" Вариации запроса: {vline}." if vline else "")
        )
    }
    s3 = {
        "h2": "Ошибки, которых лучше избежать",
        "html": para_html(
            "Не торопите события, не переходите к откровенным темам без явного согласия. "
            "Старайтесь обходиться без резких формулировок и личных вопросов — особенно в начале."
        )
    }
    return [s1, s2, s3]

def sections_html(sections: List[Dict[str,str]]) -> str:
    parts = []
    for s in sections:
        hid = slugify(s["h2"])
        parts.append(
            f'<section id="{hid}" class="py-10 border-t border-white/5">'
            f'<div class="max-w-6xl mx-auto px-4">'
            f'<h2 class="text-2xl font-semibold">{esc(s["h2"])}</h2>'
            f'{s["html"]}'
            f'</div></section>'
        )
    return "\n".join(parts)

def toc_from_sections(sections: List[Dict[str,str]]) -> str:
    if not sections: return ""
    lis = "".join(
        f'<li><a class="hover:underline text-zinc-300" href="#{slugify(s["h2"])}">{esc(s["h2"])}</a></li>'
        for s in sections
    )
    return f"""
    <nav aria-label="Содержание" class="border-t border-white/5">
      <div class="max-w-6xl mx-auto px-4 py-6">
        <div class="glass rounded-xl p-4">
          <div class="text-sm uppercase tracking-wide text-zinc-400">Содержание</div>
          <ul class="mt-2 grid sm:grid-cols-2 gap-2">{lis}</ul>
        </div>
      </div>
    </nav>"""

def faq_items(rec: Dict[str,str]) -> List[Dict[str,str]]:
    items = []
    for i in range(1, 11):
        q = (rec.get(f"faq{i}_q") or "").strip()
        a = (rec.get(f"faq{i}_a") or "").strip()
        if q and a: items.append({"q": q, "a": a})
    return items

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

def build_related(all_rows: List[Dict[str,str]], current_url: str, manual: List[str], limit: int = 6):
    # manual → приоритет; затем соседи того же первого сегмента
    cur = norm_url(current_url)
    by_url = {norm_url(r.get("url","")): r for r in all_rows}
    items = []
    for u in manual:
        u = norm_url(u)
        if u in by_url and u != cur:
            items.append(by_url[u])
    if len(items) < limit:
        parts = [p for p in cur.strip("/").split("/") if p]
        prefix = "/" + (parts[0] if parts else "") + "/"
        mux = [r for r in all_rows if norm_url(r.get("url","")).startswith(prefix) and norm_url(r.get("url","")) != cur]
        # без дублей:
        seen = {norm_url(i.get("url","")) for i in items}
        for r in mux:
            u = norm_url(r.get("url",""))
            if u not in seen:
                items.append(r)
                seen.add(u)
            if len(items) >= limit: break
    # Fallback на «три кита»
    FALLBACK = ["/chat/chat-s-devushkoi-online/","/chat/anonimnyi-chat-s-devushkoi/","/chat/chat-bez-registracii/"]
    if len(items) < 3:
        for u in FALLBACK:
            r = by_url.get(norm_url(u))
            if r and norm_url(u) != cur and r not in items:
                items.append(r)
            if len(items) >= limit: break

    html_cards = []
    for r in items[:limit]:
        title = r.get("title") or r.get("keyword") or "Подробнее"
        href = norm_url(r["url"])
        html_cards.append(f'<a class="glass rounded-xl p-4 hover:bg-white/10" href="{esc(href)}">{esc(title)}</a>')

    # JSON-LD ItemList
    itemlist = {
        "@context":"https://schema.org","@type":"ItemList",
        "itemListElement":[
            {"@type":"ListItem","position":i+1,
             "url": f"{BASE_URL}{norm_url(r['url'])}",
             "name": r.get("title") or r.get("keyword") or "Подробнее"}
            for i, r in enumerate(items[:limit])
        ]
    }
    return ("\n".join(html_cards), json.dumps(itemlist, ensure_ascii=False, separators=(",",":")))

def build_breadcrumbs(url: str, title: str):
    # Простые 3 звена: Главная → Чат → Текущая
    items = [
        {"@type":"ListItem","position":1,"name":"Главная","item":f"{BASE_URL}/"},
        {"@type":"ListItem","position":2,"name":"Чат","item":f"{BASE_URL}/chat/"},
        {"@type":"ListItem","position":3,"name":title,"item":f"{BASE_URL}{url}"}
    ]
    return json.dumps({"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":items},
                      ensure_ascii=False, separators=(",",":"))

def build_webpage_sd(title: str, url: str, desc: str):
    data = {
        "@context":"https://schema.org",
        "@type":"WebPage",
        "name": title,
        "url": f"{BASE_URL}{url}",
        "description": desc,
        "inLanguage": "ru",
        "dateModified": BUILD_TAG
    }
    return json.dumps(data, ensure_ascii=False, separators=(",",":"))

def improve_title(title: str, brand: str) -> str:
    # Добавляем бренд, если его нет; бережём длину
    if brand and brand.lower() not in title.lower():
        t = f"{title} | {brand}"
        return t if len(t) <= 62 else f"{title} — {brand}"
    return title

def improve_desc(desc: str, keyword: str) -> str:
    d = (desc or "").strip()
    if len(d) < 110:
        tail = f" Начните {keyword} за 1–2 минуты — без регистрации и VPN."
        d = (d + tail).strip()
    return d[:160]

# ---------- main ----------
def main() -> int:
    if not CSV_PATH.exists():
        print(f"[ERR] CSV not found: {CSV_PATH}", file=sys.stderr); return 2

    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    # Уникализируем по URL (последняя запись выигрывает)
    by_url: Dict[str, Dict[str,str]] = {}
    for r in rows:
        u = norm_url(r.get("url",""))
        if u != "/":
            by_url[u] = r

    generated = []
    for url, rec in by_url.items():
        out_dir = (OUT_ROOT / url.lstrip("/")).resolve()

        if args.clean and out_dir.exists():
            shutil.rmtree(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        if args.replace_md:
            for pattern in ("index.md","index.mdx","*.md","*.mdx"):
                for pth in out_dir.glob(pattern):
                    try: pth.unlink()
                    except: pass

        out_file = out_dir / "index.html"

        brand = (rec.get("brand") or BRAND_DEFAULT).strip()
        title = (rec.get("title") or rec.get("keyword") or "Чат с девушкой онлайн").strip()
        keyword = (rec.get("keyword") or title).strip()
        desc  = (rec.get("description") or rec.get("intro") or "Уютное общение, лёгкий флирт и поддержка 24/7.").strip()
        h1    = (rec.get("h1") or title).strip()
        intro = (rec.get("intro") or desc).strip()
        cta   = (rec.get("cta") or "Открыть в Telegram").strip()

        title_full = improve_title(title, brand)
        desc_final = improve_desc(desc, keyword)

        bullets = split_pipe(rec.get("bullets",""))
        variants = split_pipe(rec.get("variants",""))
        examples = split_pipe(rec.get("examples",""))
        tips_do  = split_pipe(rec.get("tips_do",""))
        tips_avoid = split_pipe(rec.get("tips_avoid",""))
        manual_related = split_pipe(rec.get("related",""))

        # контентные секции
        secs = make_sections(rec, keyword, variants)

        # сборка блоков
        benefits_html = benefits_block(bullets)
        sections_block = sections_html(secs)
        toc_html = toc_from_sections(secs)
        advice_html = advice_block(tips_do, tips_avoid)
        examples_html = examples_block(examples, keyword)

        # FAQ
        faqs = faq_items(rec)
        faq_block = faq_html(faqs)
        faq_sd = faq_jsonld(faqs)

        # Related
        related_block, related_sd = build_related(rows, url, manual_related, 6)

        # JSON-LD
        breadcrumbs_sd = build_breadcrumbs(url, title)
        webpage_sd = build_webpage_sd(title, url, desc_final)

        html_out = PAGE_TMPL.format(
            build_tag=BUILD_TAG,
            title_full=esc(title_full),
            desc_final=esc(desc_final),
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
            toc_html=toc_html,
            benefits_html=benefits_html,
            sections_html=sections_block,
            advice_html=advice_html,
            examples_html=examples_html,
            faq_html=faq_block,
            related_html=related_block,
            webpage_jsonld=webpage_sd,
            breadcrumbs_jsonld=breadcrumbs_sd,
            faq_jsonld=faq_sd,
            related_jsonld=related_sd,
            metrika=esc(METRIKA_ID),
        )

        out_file.write_text(html_out, encoding="utf-8")
        generated.append(url)
        print(f"✔ {url} → {out_file.relative_to(ROOT)}")

    # sitemap.xml
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
