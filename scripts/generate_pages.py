#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Luna Chat — генератор/обновлятор страниц из CSV с умной перелинковкой.

Формат CSV (25 колонок):
url,title,keyword,slug,description,intro,cta,bullets,tags,examples,tips_do,tips_avoid,h2a_title,h2a_text,h2b_title,h2b_text,h2c_title,h2c_text,faq1_q,faq1_a,faq2_q,faq2_a,faq3_q,faq3_a,internal_links

Правила:
- bullets / tags / examples / tips_do / tips_avoid — пункты через |
- internal_links — элементы через |:
    "/chat/slug/"  ИЛИ  "Анкор::/chat/slug/"
- Выводит HTML по пути <out>/<url>/index.html (ведущие/замыкающие слэши нормализуются)
- Добавляет автоперелинковку на предыдущие 5 страниц текущей выборки.

ENV:
- SITE_BASE (default: https://gorod-legends.ru)
- BOT_URL   (default: https://t.me/luciddreams?start=_tgr_ChFKPawxOGRi)
"""

import argparse, csv, html, json, os, re, sys, unicodedata
from pathlib import Path
from datetime import datetime

SITE_BASE = os.environ.get("SITE_BASE", "https://gorod-legends.ru")
BOT_URL   = os.environ.get("BOT_URL", "https://t.me/luciddreams?start=_tgr_ChFKPawxOGRi")

REQUIRED = [
    "url","title","keyword","slug","description","intro","cta","bullets","tags","examples",
    "tips_do","tips_avoid","h2a_title","h2a_text","h2b_title","h2b_text","h2c_title","h2c_text",
    "faq1_q","faq1_a","faq2_q","faq2_a","faq3_q","faq3_a","internal_links"
]

def slugify(s: str) -> str:
    s = unicodedata.normalize('NFKD', s).encode('ascii','ignore').decode('ascii')
    s = re.sub(r'[^a-zA-Z0-9\-_/]+','-', s.lower()).strip('-')
    s = re.sub(r'-{2,}','-', s)
    return s

def normalize_url(u: str) -> str:
    u = (u or "").strip()
    if not u.startswith("/"): u = "/" + u
    if not u.endswith("/"):  u = u + "/"
    return u

def ensure_index_path(url: str, out_root: Path) -> Path:
    u = normalize_url(url)
    parts = [p for p in u.split("/") if p]
    return out_root.joinpath(*parts, "index.html")

def split_items(s: str):
    return [i.strip() for i in (s or "").split("|") if i and i.strip()]

def humanize_from_url(url: str) -> str:
    # Берём последний НЕ пустой сегмент
    parts = [p for p in url.strip().split("/") if p]
    slug = parts[-1] if parts else url.strip("/").replace("/", "")
    name = slug.replace("-", " ").strip()
    # Title Case с аккуратной капитализацией
    return " ".join(w.capitalize() for w in name.split())

def make_bullets_html(items):
    if not items:
        return '<li class="text-zinc-400">Скоро дополним.</li>'
    rows = []
    for it in items:
        rows.append(
            '<li class="flex gap-3">'
            '<span class="w-2 h-2 mt-2 rounded-full bg-accent-500"></span>'
            f'<span class="text-zinc-300">{html.escape(it)}</span></li>'
        )
    return "\n".join(rows)

def make_tag_chips(tags):
    if not tags: 
        return ''
    chips = []
    for t in tags:
        chips.append(
            f'<span class="px-3 py-1 rounded-lg bg-white/5 text-zinc-300 text-xs">{html.escape(t)}</span>'
        )
    return "\n".join(chips)

def make_examples_html(examples):
    if not examples: 
        return ''
    lis = [f'<li class="glass rounded-lg px-3 py-2"><code class="text-sm">{html.escape(ex)}</code></li>'
           for ex in examples]
    return "\n".join(lis)

def make_list_html(items):
    if not items:
        return '<li class="text-zinc-400">Скоро дополним.</li>'
    return "\n".join(
        f'<li class="flex gap-2"><span class="mt-2 w-2 h-2 bg-gold-400 rounded-full"></span>'
        f'<span class="text-zinc-300">{html.escape(it)}</span></li>' for it in items
    )

_title_tag_re = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_h1_tag_re    = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I | re.S)
_tag_strip_re = re.compile(r"<[^>]+>")

def read_title_from_existing_page(url: str, out_root: Path) -> str | None:
    """Пробуем вытащить <h1> или <title> из уже сгенерированного файла."""
    p = ensure_index_path(url, out_root)
    if not p.exists():
        return None
    try:
        txt = p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
    m = _h1_tag_re.search(txt) or _title_tag_re.search(txt)
    if not m: 
        return None
    raw = m.group(1)
    clean = _tag_strip_re.sub("", raw).strip()
    return clean or None

def build_title_index(all_rows: list[dict]) -> dict:
    """Создаём быстрый индекс URL → Title из CSV текущего запуска."""
    idx = {}
    for r in all_rows:
        u = normalize_url(r.get("url",""))
        t = (r.get("title") or "").strip()
        if u and t:
            idx[u] = t
    return idx

def parse_internal_items(field: str) -> list[tuple[str,str|None]]:
    """
    Возвращает список (url, anchor|None)
    Поддерживает 'Анкор::/chat/slug/' и '/chat/slug/'
    """
    items = []
    for raw in split_items(field):
        if "::" in raw:
            label, url = raw.split("::", 1)
            items.append( (normalize_url(url.strip()), (label or "").strip() or None) )
        else:
            items.append( (normalize_url(raw), None) )
    return items

def make_internal_links_html(field: str, title_index: dict, out_root: Path) -> str:
    items = parse_internal_items(field)
    if not items:
        return '<p class="text-zinc-400">Скоро добавим больше страниц.</p>'
    cards = []
    for url, anchor in items:
        # 1) приоритет: анкор из CSV
        label = anchor
        # 2) потом title из текущего CSV
        if not label:
            label = title_index.get(url)
        # 3) потом title из уже сгенерированного HTML
        if not label:
            label = read_title_from_existing_page(url, out_root)
        # 4) fallback: «очеловеченный» слаг
        if not label:
            label = humanize_from_url(url)

        full = f"{SITE_BASE.rstrip('/')}{url}"
        cards.append(
            f'<a href="{html.escape(full)}" class="glass rounded-xl p-4 hover:bg-white/10 transition">'
            f'<div class="text-white font-medium">{html.escape(label)}</div>'
            f'<div class="text-xs text-zinc-400 mt-1">Открыть →</div></a>'
        )
    return "\n".join(cards)

def faq_block_and_json(row: dict):
    qas = [
        (row.get("faq1_q",""), row.get("faq1_a","")),
        (row.get("faq2_q",""), row.get("faq2_a","")),
        (row.get("faq3_q",""), row.get("faq3_a","")),
    ]
    blocks = []
    schema = {"@context":"https://schema.org","@type":"FAQPage","mainEntity":[]}
    for q,a in qas:
        q, a = (q or "").strip(), (a or "").strip()
        if not q or not a: 
            continue
        blocks.append(
            f'<details class="glass rounded-xl p-4">'
            f'<summary class="cursor-pointer font-medium text-white">{html.escape(q)}</summary>'
            f'<p class="mt-2 text-zinc-300">{html.escape(a)}</p>'
            f'</details>'
        )
        schema["mainEntity"].append({
            "@type":"Question","name": q,
            "acceptedAnswer":{"@type":"Answer","text": a}
        })
    if not blocks:
        blocks.append('<p class="text-zinc-400">Вопросы появятся позже.</p>')
    return "\n".join(blocks), json.dumps(schema, ensure_ascii=False)

def article_jsonld(title, description, canonical, keywords, ts_iso):
    data = {
        "@context":"https://schema.org",
        "@type":"Article",
        "headline": title,
        "description": description,
        "inLanguage": "ru",
        "mainEntityOfPage": canonical,
        "author": {"@type":"Organization","name":"Luna Chat"},
        "publisher": {"@type":"Organization","name":"Luna Chat"},
        "datePublished": ts_iso,
        "dateModified": ts_iso,
        "keywords": keywords
    }
    return json.dumps(data, ensure_ascii=False)

def breadcrumbs_jsonld(canonical, title):
    data = {
        "@context":"https://schema.org",
        "@type":"BreadcrumbList",
        "itemListElement":[
            {"@type":"ListItem","position":1,"name":"Главная","item": SITE_BASE.rstrip('/') + "/"},
            {"@type":"ListItem","position":2,"name":"Чат","item": SITE_BASE.rstrip('/') + "/chat/"},
            {"@type":"ListItem","position":3,"name": title, "item": canonical}
        ]
    }
    return json.dumps(data, ensure_ascii=False)

def render(template: str, ctx: dict) -> str:
    out = template
    for k,v in ctx.items():
        out = out.replace(f"{{{{{k}}}}}", v)
    return out

def read_csv_all(csv_path: Path) -> list[dict]:
    rows = []
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as fh:
        header_line = fh.readline()
        if not header_line:
            raise SystemExit("[ERR] CSV файл пуст.")
        header = next(csv.reader([header_line]))
        header_lower = [h.strip().lower() for h in header]
        wanted_lower = [h.lower() for h in REQUIRED]
        if header_lower != wanted_lower:
            raise SystemExit(
                "[ERR] Неверные заголовки CSV.\n"
                f"Ожидается:\n{','.join(REQUIRED)}\n"
                f"Получено:\n{','.join(header)}"
            )
        fh.seek(0)
        reader = csv.DictReader(fh)
        for idx, row in enumerate(reader, start=2):
            extras = row.get(None)
            if extras not in (None, [], ""):
                raise SystemExit(
                    f"[ERR] Лишние столбцы в CSV на строке {idx}. "
                    f"Проверь кавычки вокруг ячеек с запятыми. Лишние: {extras}"
                )
            row["_lineno"] = idx
            rows.append(row)
    return rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="Путь к CSV (utf-8 / utf-8-sig)")
    ap.add_argument("--template", required=True, help="Путь к HTML-шаблону")
    ap.add_argument("--out", default=".", help="Корень вывода (по умолчанию: .)")
    ap.add_argument("--auto_prev", type=int, default=5, help="Сколько предыдущих страниц добавлять в перелинковку (default: 5)")
    args = ap.parse_args()

    tpl_path = Path(args.template)
    if not tpl_path.exists():
        print(f"[ERR] Template not found: {tpl_path}", file=sys.stderr)
        sys.exit(2)
    template = tpl_path.read_text(encoding="utf-8")

    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)

    # Грузим все строки, строим индекс Title по URL
    all_rows = read_csv_all(Path(args.csv))
    title_index = build_title_index(all_rows)

    prev_urls: list[str] = []  # очередь последних с нормализованными URL

    total = 0
    for row in all_rows:
        lineno = row["_lineno"]

        # Базовые поля
        url   = normalize_url(row.get("url") or "")
        title = (row.get("title") or "").strip()
        desc  = (row.get("description") or "").strip()
        intro = (row.get("intro") or "").strip()
        cta   = (row.get("cta") or "Открыть в Telegram").strip()
        keyword = (row.get("keyword") or "").strip()
        _ = slugify(row.get("slug","") or title)

        # Массивы
        bullets  = split_items(row.get("bullets",""))
        tags     = split_items(row.get("tags",""))
        examples = split_items(row.get("examples",""))
        tips_do  = split_items(row.get("tips_do",""))
        tips_no  = split_items(row.get("tips_avoid",""))

        # H2-блоки
        h2a_title = (row.get("h2a_title") or "").strip()
        h2a_text  = (row.get("h2a_text")  or "").strip()
        h2b_title = (row.get("h2b_title") or "").strip()
        h2b_text  = (row.get("h2b_text")  or "").strip()
        h2c_title = (row.get("h2c_title") or "").strip()
        h2c_text  = (row.get("h2c_text")  or "").strip()

        # Выходной путь
        dst = ensure_index_path(url, out_root)
        dst.parent.mkdir(parents=True, exist_ok=True)

        # Автоперелинковка (предыдущие N)
        auto_prev = []
        for pu in prev_urls[-args.auto_prev:][::-1]:
            tt = title_index.get(pu) or read_title_from_existing_page(pu, out_root) or humanize_from_url(pu)
            auto_prev.append(f"{tt}::{pu}")
        prev_urls.append(url)

        # Склеиваем ручные ссылки из CSV + авто
        manual = row.get("internal_links","") or ""
        manual_items = split_items(manual)
        # прибавим авто, но не дублируем
        present = set(manual_items)
        for item in auto_prev:
            if item not in present:
                manual_items.append(item)
                present.add(item)
        all_links_field = "|".join(manual_items)

        # HTML-фрагменты
        bullets_html = make_bullets_html(bullets)
        tags_html = make_tag_chips(tags)
        examples_html = make_examples_html(examples)
        tips_do_html = make_list_html(tips_do)
        tips_avoid_html = make_list_html(tips_no)
        faq_html, faq_json = faq_block_and_json(row)
        related_html = make_internal_links_html(all_links_field, title_index, out_root)

        # SEO
        canonical = f"{SITE_BASE.rstrip('/')}{url}"
        ts_iso = datetime.utcnow().isoformat(timespec="seconds")+"Z"
        keywords_meta = ", ".join([k for k in [keyword] + tags if k])

        # JSON-LD (Article + Breadcrumbs + FAQ)
        article_json = article_jsonld(title, desc, canonical, keywords_meta, ts_iso)
        crumbs_json = breadcrumbs_jsonld(canonical, title)
        jsonld_bundle = "[{}]".format(",".join([article_json, crumbs_json, faq_json]))

        # Подстановка
        ctx = {
            "BUILD_TS": ts_iso,
            "TITLE": html.escape(title),
            "DESCRIPTION": html.escape(desc),
            "H1": html.escape(title),
            "INTRO": html.escape(intro),
            "BULLETS_HTML": bullets_html,
            "FAQ_HTML": faq_html,
            "JSONLD_BUNDLE": jsonld_bundle,
            "CANONICAL": canonical,
            "BOT_URL": BOT_URL,
            "CTA": html.escape(cta),
            "TAGS_HTML": tags_html,
            "EXAMPLES_HTML": examples_html,
            "TIPS_DO_HTML": tips_do_html,
            "TIPS_AVOID_HTML": tips_avoid_html,
            "H2A_TITLE": html.escape(h2a_title) if h2a_title else "",
            "H2A_TEXT": html.escape(h2a_text) if h2a_text else "",
            "H2B_TITLE": html.escape(h2b_title) if h2b_title else "",
            "H2B_TEXT": html.escape(h2b_text) if h2b_text else "",
            "H2C_TITLE": html.escape(h2c_title) if h2c_title else "",
            "H2C_TEXT": html.escape(h2c_text) if h2c_text else "",
            "INTERNAL_LINKS_HTML": related_html,
            "KEYWORDS_META": html.escape(keywords_meta),
        }

        html_out = render(template, ctx)
        dst.write_text(html_out, encoding="utf-8")
        print(f"[OK] line {lineno}: {url} -> {dst}")
        total += 1

    print(f"[DONE] Generated/updated {total} page(s) into {out_root}")

if __name__ == "__main__":
    main()
