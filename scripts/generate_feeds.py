#!/usr/bin/env python3
import os, datetime

BASE = "https://gorod-legends.ru"
skip = {"404.html"}
def pages():
  out = []
  for root, _, files in os.walk("."):
    for f in files:
      if not f.endswith(".html"): continue
      rel = os.path.join(root, f)[2:]
      if rel.startswith(".github") or rel.startswith("scripts"): continue
      if rel.startswith("assets/"): continue
      if f.startswith("yandex_"): continue
      if rel in skip: continue
      out.append(rel.replace("\\","/"))
  return sorted(out)

def write_sitemap(items):
  xml = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
  for rel in items:
    xml.append(f"  <url><loc>{BASE}/{rel}</loc></url>")
  xml.append("</urlset>")
  open("sitemap.xml","w",encoding="utf-8").write("\n".join(xml))

def write_rss(items):
  now = datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")
  xml = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<rss version="2.0"><channel>',
         f"<title>Luna Chat — обновления</title>",
         f"<link>{BASE}/</link>",
         f"<description>Новости и обновления сервиса</description>",
         f"<language>ru</language>",
         f"<lastBuildDate>{now}</lastBuildDate>"]
  for rel in items[:20]:
    url = f"{BASE}/{rel}"
    xml += [ "<item>",
             f"<title>{rel}</title>",
             f"<link>{url}</link>",
             f"<guid isPermaLink=\"true\">{url}</guid>",
             "</item>" ]
  xml.append("</channel></rss>")
  open("rss.xml","w",encoding="utf-8").write("\n".join(xml))

if __name__ == "__main__":
  items = [""] + pages()  # "" -> корень (index.html)
  items = [i if i else ""]
  items = [("index.html" if i=="" else i) for i in items]
  items = list(dict.fromkeys(items))
  write_sitemap([i if i!="index.html" else "" for i in items])
  write_rss(items)
