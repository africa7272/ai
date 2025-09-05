#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SEO-автоген: читает /data/batch.csv и генерит:
- /requests/<slug>/index.html (усиленный SEO-шаблон)
- /assets/og/<slug>.png (соц-изображение 1200x630)
- sitemap.xml (с <lastmod>)
- rss.xml (последние 50)
- robots.txt (с ссылкой на sitemap)

Запуск локально:  python3 scripts/autogen_seo.py
Запуск в CI:     GitHub Actions (см. workflow)
"""

import csv, os, re, random, hashlib, datetime, json
from pathlib import Path

# ---------- Базовые настройки ----------
SITE_BASE = "https://gorod-legends.ru"
BOT_URL   = "https://t.me/luciddreams?start=_tgr_ChFKPawxOGRi"
DATA_CSV  = "data/batch.csv"
OUT_DIR   = "requests"
OG_DIR    = "assets/og"

TWITTER_SITE = "@yourbrand"   # при необходимости замените
ORG_NAME     = "Luna Chat"

BLOCKLIST = [
    "несовершеннолет", "teen", "детск", "насилие", "rape", "инцест", "порн", "наркот"
]

# ---------- Транслитерация для slug ----------
MAP = {"а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"e","ж":"zh","з":"z","и":"i","й":"y","к":"k","л":"l",
       "м":"m","н":"n","о":"o","п":"p","р":"r","с":"s","т":"t","у":"u","ф":"f","х":"h","ц":"c","ч":"ch","ш":"sh",
       "щ":"sch","ъ":"","ы":"y","ь":"","э":"e","ю":"yu","я":"ya"}
def slugify(text: str) -> str:
    t = (text or "").strip().lower()
    out = []
    for ch in t:
        if ch in MAP: out.append(MAP[ch])
        elif ch.isalnum(): out.append(ch)
        elif ch in " _./+|–—": out.append("-")
        else: out.append("-")
    s = re.sub(r"-{2,}", "-", "".join(out)).strip("-")
    return s or "page"

def blocked(s: str) -> bool:
    s = (s or "").lower()
    return any(b in s for b in BLOCKLIST)

# ---------- Лексикон и вспомогалки ----------
INTROS = [
  "Ищете {kw}? Выберите образ, нажмите — и вы уже в тёплом диалоге без неловкости.",
  "Запрос «{kw}» встречается часто, но важен личный тон. Попробуйте начать беседу прямо сейчас.",
  "Нужен {kw}? Один клик — и переписка в Telegram уже открыта.",
  "Если вам близко «{kw}», начните мягко и дружелюбно — атмосфера создана для комфорта.",
  "«{kw}» — это про лёгкий флирт и уважение к границам. Начните с приветствия и короткой искры."
]
BENEFITS = [
  "Лёгкий старт: без форм и ожиданий — сразу в Telegram.",
  "Выбор настроения: романтика, игра или спокойный тон.",
  "Анонимность и уважительные правила общения.",
  "Образ собеседницы можно менять в любой момент.",
  "24/7 — отвечаем, когда удобно вам.",
  "Мягкая подача без откровенных описаний."
]
CTA = ["Открыть чат в Telegram","Начать переписку","Попробовать сейчас","Запустить бот","Перейти к общению"]
LSI = [
  "виртуальная собеседница","бот для общения","анонимный чат","лёгкий флирт",
  "онлайн-диалог","чат в Telegram","подсказки что написать","спокойная беседа",
  "выбор образа","без регистрации"
]
FAQ_Q = [
  "Нужна ли регистрация для {kw}?",
  "Это анонимно и безопасно?",
  "Можно ли менять образ собеседницы?",
  "Подходит ли «{kw}» для ночных разговоров?",
  "Есть ли ограничения 18+?"
]
FAQ_A = [
  "Регистрация не нужна — просто нажмите кнопку, чат откроется сразу в Telegram.",
  "Мы поддерживаем уважительный тон и мягкую модерацию. Не делитесь личными данными.",
  "Да, образ можно менять в любое время — под настроение беседы.",
  "Да, формат подходит: темп беседы выбираете вы, можно вести разговор спокойно.",
  "Сервис предназначен для совершеннолетних пользователей (18+)."
]

def choose(seed: str, arr: list, k: int = 1):
    rnd = random.Random(int(hashlib.sha256(seed.encode()).hexdigest(), 16))
    return (rnd.sample(arr, k) if k > 1 else rnd.choice(arr))

def make_lsi_paragraphs(seed: str, kw: str, words: int = 180) -> str:
    rnd = random.Random(int(hashlib.sha256((seed + "lsi").encode()).hexdigest(), 16))
    pool = LSI + [kw]

    def sentence():
        picks = rnd.sample(pool, k=min(5, len(pool)))
        core = f"{picks[0].capitalize()} — это про {picks[1]}, {picks[2]} и {picks[3]}."
        tail = f" Здесь вы можете начать {picks[4]} без спешки: достаточно выбрать образ и задать тон."
        s = core + tail
        if kw not in s.lower():
            s += f" Запрос «{kw}» раскрывается мягко и уважительно."
        return s

    out = []
    while sum(len(x.split()) for x in out) < words:
        out.append(sentence())

    text = " ".join(out)
    tokens = text.split()
    n = min(max(160, len(tokens)), 220)
    return " ".join(tokens[:n])

def tokens(s: str):
    return set(re.findall(r"[a-zA-Zа-яА-Я0-9]+", (s or "").lower()))

def pick_related(this_slug: str, rows: list, k: int = 4):
    me = None
    for r in rows:
        if r["slug"] == this_slug:
            me = tokens(r.get("keyword","") + " " + r.get("title",""))
            break
    scored = []
    for r in rows:
        if r["slug"] == this_slug: 
            continue
        t = tokens(r.get("keyword","") + " " + r.get("title",""))
        score = len(me & t) / max(1, len(me | t)) if me else 0
        scored.append((score, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [x[1] for x in scored[:k]]

# ---------- Tailwind + стили (НЕ f-строка) ----------
HEAD_CSS = """
  <link rel="preconnect" href="https://cdn.tailwindcss.com" crossorigin>
  <link rel="dns-prefetch" href="https://cdn.tailwindcss.com">
  <link rel="preconnect" href="https://mc.yandex.ru">
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      theme: { extend: {
        colors: {
          brand:{950:'#0B0A0C',900:'#130F12',800:'#1B1418',700:'#29181F',600:'#3A1E2B'},
          accent:{500:'#C72C41',400:'#E1495B'}, gold:{400:'#F2C14E'}
        },
        boxShadow:{soft:'0 10px 24px rgba(0,0,0,0.25)'}
      } }
    }
  </script>
  <style>
    html{scroll-behavior:smooth}
    .glass{backdrop-filter:blur(10px);background:rgba(19,15,18,.45);border:1px solid rgba(255,255,255,.06)}
    .hero{background:
      radial-gradient(1200px 600px at 80% -10%, rgba(199,44,65,.35), transparent 60%),
      radial-gradient(900px 500px at 10% -20%, rgba(242,193,78,.25), transparent 60%),
      linear-gradient(180deg,#130F12 0%,#1B1418 60%,#0B0A0C 100%)}
    .hidden-photo{position:relative;overflow:hidden}
    .hidden-photo::before{content:"";position:absolute;inset:0;background:
      radial-gradient(120px 120px at 50% 30%, rgba(255,228,230,.80), transparent 60%),
      radial-gradient(200px 140px at 50% 70%, rgba(231,84,106,.65), transparent 60%),
      radial-gradient(600px 260px at 40% -20%, rgba(199,44,65,.25), transparent 70%),
      radial-gradient(600px 260px at 70% 120%, rgba(242,193,78,.18), transparent 70%);
      filter:blur(14px) saturate(1.1);transform:scale(1.1);opacity:.95}
    .hidden-photo::after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,.15),rgba(0,0,0,.4))}
    .tile-overlay{position:absolute;inset:0;display:flex;align-items:center;justify-content:center}
  </style>
"""

# --- Yandex.Metrika snippet (ОБЫЧНАЯ строка, не f-строка!) ---
METRIKA_SNIPPET = """
<!-- Yandex.Metrika counter -->
<script type="text/javascript">
 (function(m,e,t,r,i,k,a){m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};m[i].l=1*new Date();
 for (var j=0;j<document.scripts.length;j++){if(document.scripts[j].src===r){return;}}
 k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)})(window, document,'script','https://mc.yandex.ru/metrika/tag.js?id=103658483','ym');
 ym(103658483,'init',{ssr:true, webvisor:true, clickmap:true, ecommerce:"dataLayer", accurateTrackBounce:true, trackLinks:true});
</script>
<noscript><div><img src="https://mc.yandex.ru/watch/103658483" style="position:absolute; left:-9999px;" alt=""></div></noscript>
<!-- /Yandex.Metrika counter -->
"""

# ---------- OG-картинка 1200x630 ----------
def ensure_og(slug: str, title: str) -> str:
    """Создаёт /assets/og/<slug>.png, если его ещё нет. Возвращает путь."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return str(Path(OG_DIR) / f"{slug}.png")  # пропустим, если Pillow не установлен

    Path(OG_DIR).mkdir(parents=True, exist_ok=True)
    path = Path(OG_DIR) / f"{slug}.png"
    if path.exists():
        return str(path)

    W, H = 1200, 630
    im = Image.new("RGB", (W, H), (19, 15, 18))
    draw = ImageDraw.Draw(im)

    # простая «полосатая» подложка
    for y in range(0, H, 6):
        draw.line([(0, y), (W, y)], fill=(199, 44, 65))

    # затемняем края
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 110))
    im = Image.alpha_composite(im.convert("RGBA"), overlay).convert("RGB")

    # шрифт
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    try:
        font_big = ImageFont.truetype(font_path, 66)
        font_small = ImageFont.truetype(font_path, 28)
    except Exception:
        font_big = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # перенос по словам
    def wrap(text, width=24):
        words = text.split()
        lines, line = [], ""
        for w in words:
            t = (line + " " + w).strip()
            if len(t) <= width:
                line = t
            else:
                lines.append(line); line = w
        if line: lines.append(line)
        return lines[:4]

    lines = wrap(title, 24)
    y = 210 - len(lines) * 40
    for ln in lines:
        w, _ = draw.textsize(ln, font=font_big)
        draw.text(((W - w) / 2, y), ln, fill=(255, 255, 255), font=font_big)
        y += 80

    cap = "Luna Chat — уютное общение"
    w, _ = draw.textsize(cap, font=font_small)
    draw.text(((W - w) / 2, H - 90), cap, fill=(240, 240, 240), font=font_small)

    im.save(str(path), "PNG")
    return str(path)

# ---------- Формирование HTML страницы ----------
def html_page(row: dict, rows_all: list, now_iso: str) -> str:
    title = row["title"].strip()
    kw = row["keyword"].strip()
    slug = row["slug"]
    desc = (row.get("description") or "").strip()
    intro = row.get("intro") or choose(slug + "intro", INTROS).format(kw=kw)
    cta = row.get("cta") or choose(slug + "cta", CTA)

    if row.get("bullets"):
        bullets = [b.strip() for b in row["bullets"].split("|") if b.strip()]
    else:
        bullets = choose(slug + "bens", BENEFITS, k=3)
    bullets_li = "\n".join(f"<li>{b}</li>" for b in bullets)

    # FAQ
    faqs = []
    if row.get("faq1_q") and row.get("faq1_a"): faqs.append((row["faq1_q"], row["faq1_a"]))
    if row.get("faq2_q") and row.get("faq2_a"): faqs.append((row["faq2_q"], row["faq2_a"]))
    if row.get("faq3_q") and row.get("faq3_a"): faqs.append((row["faq3_q"], row["faq3_a"]))
    if not faqs:
        faqs = list(zip(choose(slug + "faqq", [q.format(kw=kw) for q in FAQ_Q], k=3),
                        choose(slug + "faqa", FAQ_A, k=3)))
    faq_html = "\n".join(
        f'<details class="glass rounded-2xl p-5"><summary class="cursor-pointer font-medium text-white">{q}</summary><p class="mt-3 text-zinc-300">{a}</p></details>'
        for q, a in faqs
    )
    faq_ld = {"@context":"https://schema.org","@type":"FAQPage",
              "mainEntity":[{"@type":"Question","name":q,"acceptedAnswer":{"@type":"Answer","text":a}} for q,a in faqs]}

    # LSI-текст
    lsi_text = make_lsi_paragraphs(slug, kw, words=180)

    # Похожие
    related = pick_related(slug, rows_all, k=4)
    related_html = "\n".join(
        f'<li><a class="underline hover:text-zinc-200" href="/{OUT_DIR}/{r["slug"]}/">{r["title"]}</a></li>'
        for r in related
    )

    url = f"{SITE_BASE}/{OUT_DIR}/{slug}/"
    og_rel_path = f"/{OG_DIR}/{slug}.png"
    page_meta_desc = (desc or f"{title}: {kw}. Лёгкий старт, уважительный тон и уютный флирт. Нажмите — чат откроется в Telegram.")[:160]
    published = now_iso
    modified  = now_iso

    # JSON-LD
    web_ld = {
      "@context":"https://schema.org",
      "@type":"WebPage",
      "name": title, "url": url,
      "datePublished": published, "dateModified": modified,
      "isPartOf":{"@type":"WebSite","name": ORG_NAME, "url": SITE_BASE},
      "about": kw
    }
    breadcrumbs_ld = {
      "@context":"https://schema.org","@type":"BreadcrumbList",
      "itemListElement":[
        {"@type":"ListItem","position":1,"name":"Главная","item":SITE_BASE+"/"},
        {"@type":"ListItem","position":2,"name":"Запросы","item":SITE_BASE+f"/{OUT_DIR}/"},
        {"@type":"ListItem","position":3,"name":title,"item":url}
      ]
    }

    # HTML (ВАЖНО: Метрика вставляется как {METRIKA_SNIPPET}, а не «сырым» кодом)
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} | Luna Chat</title>
<meta name="description" content="{page_meta_desc}">
<link rel="canonical" href="{url}">
<link rel="alternate" hreflang="ru" href="{url}">
<link rel="alternate" hreflang="x-default" href="{url}">
<meta name="robots" content="index,follow">
<meta name="theme-color" content="#100B10">

<meta property="og:type" content="article">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{page_meta_desc}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{og_rel_path}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Luna Chat — уютное общение и флирт">
<meta property="og:site_name" content="{ORG_NAME}">
<meta property="og:locale" content="ru_RU">
<meta property="article:published_time" content="{published}">
<meta property="article:modified_time" content="{modified}">
<meta property="og:updated_time" content="{modified}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:site" content="{TWITTER_SITE}">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{page_meta_desc}">
<meta name="twitter:image" content="{og_rel_path}">
<link rel="icon" href="/favicon.ico">

{HEAD_CSS}
<script type="application/ld+json">{json.dumps(web_ld, ensure_ascii=False)}</script>
<script type="application/ld+json">{json.dumps(breadcrumbs_ld, ensure_ascii=False)}</script>
<script type="application/ld+json">{json.dumps(faq_ld, ensure_ascii=False)}</script>
</head>
<body class="bg-brand-900 text-zinc-100 antialiased">

<header class="border-b border-white/5 bg-brand-900/80 backdrop-blur">
  <div class="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
    <a href="/" class="flex items-center gap-3"><span class="inline-flex w-9 h-9 rounded-2xl bg-accent-500/90 shadow-soft"></span><span class="text-lg font-semibold">Luna Chat</span></a>
    <nav class="hidden md:flex items-center gap-8 text-sm text-zinc-300">
      <a href="/characters/" class="hover:text-white">Персонажи</a>
      <a href="/{OUT_DIR}/" class="hover:text-white">Запросы</a>
      <a href="/guides/" class="hover:text-white">Гайды</a>
    </nav>
    <a href="{BOT_URL}" target="_blank" rel="noopener" class="hidden md:inline-flex px-4 py-2 rounded-xl bg-accent-500 hover:bg-accent-400 text-white font-medium shadow-soft">{cta}</a>
  </div>
</header>

<nav aria-label="Хлебные крошки" class="max-w-6xl mx-auto px-4 mt-4 text-sm text-zinc-400">
  <ol class="flex gap-2">
    <li><a class="underline" href="/">Главная</a> ›</li>
    <li><a class="underline" href="/{OUT_DIR}/">Запросы</a> ›</li>
    <li aria-current="page">{title}</li>
  </ol>
</nav>

<section class="hero">
  <div class="max-w-6xl mx-auto px-4 pt-12 pb-14 md:pt-20 md:pb-18">
    <div class="max-w-3xl">
      <h1 class="text-4xl md:text-5xl font-extrabold leading-tight">{title}</h1>
      <p class="mt-5 text-lg text-zinc-300">{intro}</p>
      <div class="mt-7"><a href="{BOT_URL}" target="_blank" rel="noopener" class="inline-flex px-6 py-3 rounded-2xl bg-accent-500 hover:bg-accent-400 text-white font-semibold shadow-soft">{cta}</a></div>
    </div>
  </div>
</section>

<main class="max-w-6xl mx-auto px-4 py-12">
  <div class="grid md:grid-cols-2 gap-6">
    <a href="{BOT_URL}" target="_blank" rel="noopener" class="group glass rounded-2xl overflow-hidden block">
      <div class="hidden-photo h-48">
        <div class="tile-overlay opacity-0 group-hover:opacity-100 transition-opacity"><span class="px-3 py-1 rounded-lg bg-black/40 text-white text-sm">{cta}</span></div>
      </div>
      <div class="p-5">
        <h2 class="font-semibold text-white">Ключевая тема: «{kw}»</h2>
        <ul class="mt-2 list-disc pl-6 text-zinc-300 space-y-1">
          {bullets_li}
        </ul>
      </div>
    </a>

    <article class="glass rounded-2xl p-6">
      <h2 class="text-xl font-semibold text-white">Как это выглядит</h2>
      <p class="mt-2 text-zinc-300">Запрос «{kw}» мы раскрываем мягко и уважительно: без грубости и без откровенных описаний. Вы выбираете образ, темп и настроение переписки.</p>
      <p class="mt-2 text-zinc-300">Нажмите кнопку — чат с выбранной собеседницей откроется в Telegram. Начать можно за минуту.</p>
      <div class="mt-4"><a href="{BOT_URL}" target="_blank" rel="noopener" class="inline-flex px-5 py-3 rounded-2xl bg-accent-500 hover:bg-accent-400 text-white font-semibold">{cta}</a></div>
    </article>
  </div>

  <section class="mt-10">
    <h2 class="text-2xl font-bold">Подробнее о теме</h2>
    <p class="mt-3 text-zinc-300">{make_lsi_paragraphs(slug, kw, words=180)}</p>
  </section>

  <section class="mt-10">
    <h2 class="text-2xl font-bold">Вопросы и ответы</h2>
    <div class="mt-4 space-y-3">
      {faq_html}
    </div>
  </section>

  <aside class="mt-10 text-sm">
    <h3 class="font-semibold text-white">Похожие темы</h3>
    <ul class="mt-2 list-disc pl-5 text-zinc-300">
      {related_html}
    </ul>
  </aside>

  <div class="mt-10 text-sm text-zinc-400">
    Полезно: <a class="underline hover:text-zinc-200" href="/characters/">выбрать образ</a> ·
    <a class="underline hover:text-zinc-200" href="/guides/how-to-start/">как начать</a>
  </div>
</main>

<footer class="py-10 border-t border-white/5">
  <div class="max-w-6xl mx-auto px-4 grid md:grid-cols-3 gap-6 text-sm text-zinc-400">
    <div><div class="text-white font-semibold">{ORG_NAME}</div><p class="mt-2">Уютное общение, лёгкий флирт и поддержка — 24/7.</p></div>
    <nav class="grid gap-2">
      <a href="/pages/about.html" class="hover:text-white">О проекте</a>
      <a href="/pages/contact.html" class="hover:text-white">Контакты</a>
      <a href="/pages/terms.html" class="hover:text-white">Условия</a>
      <a href="/pages/privacy.html" class="hover:text-white">Политика конфиденциальности</a>
    </nav>
    <div><p>18+. Пользуйтесь уважительно. Не делитесь личными данными.</p><p class="mt-2">© <span id="y"></span> {ORG_NAME}</p></div>
  </div>
</footer>

<script>document.getElementById('y').textContent=new Date().getFullYear()</script>

{METRIKA_SNIPPET}
</body>
</html>
"""

# ---------- Основной процесс ----------
def main():
    # читаем CSV
    if not os.path.exists(DATA_CSV):
        raise SystemExit(f"Не найден файл {DATA_CSV}. Создайте его и добавьте строки.")

    rows = []
    with open(DATA_CSV, newline="", encoding="utf-8") as f:
        rd = csv.DictReader(f)
        for r in rd:
            title = (r.get("title") or "").strip()
            kw    = (r.get("keyword") or "").strip()
            if not title or not kw: 
                continue
            if blocked(title) or blocked(kw):
                continue
            slug  = (r.get("slug") or slugify(title))
            r["title"] = title
            r["keyword"] = kw
            r["slug"] = slug
            rows.append(r)

    if not rows:
        print("Нет валидных строк для генерации.")
        return

    Path(OUT_DIR).mkdir(exist_ok=True)
    Path(OG_DIR).mkdir(parents=True, exist_ok=True)

    # пробуем подключить Pillow для OG
    try:
        import PIL  # noqa: F401
        pil_ok = True
    except Exception:
        pil_ok = False

    now = datetime.datetime.utcnow()
    now_iso = now.replace(microsecond=0).isoformat() + "Z"

    generated_urls = []

    for r in rows:
        slug = r["slug"]

        # OG
        if pil_ok:
            ensure_og(slug, r["title"])

        # HTML
        page_html = html_page(r, rows, now_iso)
        out_dir = Path(OUT_DIR) / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.html").write_text(page_html, encoding="utf-8")
        generated_urls.append(f"{SITE_BASE}/{OUT_DIR}/{slug}/")

    # sitemap.xml (с lastmod)
    urls = set()
    base_paths = ["","characters/","requests/","guides/","18plus/","pages/about.html","pages/contact.html","pages/terms.html","pages/privacy.html"]
    for p in base_paths:
        urls.add(SITE_BASE + "/" + p)
    for u in generated_urls:
        urls.add(u)

    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in sorted(urls):
        sm.append(f'  <url><loc>{u}</loc><lastmod>{now_iso}</lastmod></url>')
    sm.append('</urlset>')
    Path("sitemap.xml").write_text("\n".join(sm), encoding="utf-8")

    # rss.xml (последние 50)
    now_rss = now.strftime("%a, %d %b %Y %H:%M:%S +0000")
    rss = ['<?xml version="1.0" encoding="UTF-8"?>','<rss version="2.0"><channel>',
           "<title>Luna Chat — обновления</title>",
           f"<link>{SITE_BASE}/</link>",
           "<description>Новости и обновления сервиса</description>",
           "<language>ru</language>",
           f"<lastBuildDate>{now_rss}</lastBuildDate>"]
    for u in list(sorted(generated_urls))[-50:]:
        rss += ["<item>", f"<title>{u}</title>", f"<link>{u}</link>",
                f"<guid isPermaLink=\"true\">{u}</guid>", f"<pubDate>{now_rss}</pubDate>", "</item>"]
    rss.append("</channel></rss>")
    Path("rss.xml").write_text("\n".join(rss), encoding="utf-8")

    # robots.txt
    robots = f"""User-agent: *
Allow: /
Sitemap: {SITE_BASE}/sitemap.xml
"""
    Path("robots.txt").write_text(robots, encoding="utf-8")

    print(f"Готово. Сгенерировано страниц: {len(generated_urls)}. OG: {'да' if pil_ok else 'пропущено (Pillow недоступен)'}")

if __name__ == "__main__":
    main()
