#!/usr/bin/env python3
import re, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
HTMLS = list(ROOT.glob("*.html")) + list((ROOT / "articles").glob("*.html"))

BOT_HREFS = [
    r'https://t\.me/normwpn_bot\?start=referral_228691787',
    r'https://t\.me/SafeNetVpn_bot\?start=afrrica'
]
href_re = "(" + "|".join(BOT_HREFS) + ")"

# добавляет rel="nofollow sponsored noopener" если его нет
def patch_html(p: pathlib.Path):
    s = p.read_text(encoding="utf-8")
    def repl(m):
        tag = m.group(0)
        # уже есть rel?
        if re.search(r'\srel\s*=\s*"[^\"]*"', tag):
            # добавим недостающие значения
            def add_vals(match):
                vals = set(match.group(1).split())
                for v in ["nofollow", "sponsored", "noopener"]:
                    vals.add(v)
                return f'rel="{" ".join(sorted(vals))}"'
            tag = re.sub(r'rel\s*=\s*"([^"]*)"', add_vals, tag, count=1)
        else:
            tag = tag.replace(m.group(1), f'{m.group(1)} rel="nofollow sponsored noopener"')
        return tag
    new = re.sub(rf'<a\b([^>]*?)href="({href_re})"([^>]*)>', 
                 lambda m: repl(m), s, flags=re.IGNORECASE)
    if new != s:
        p.write_text(new, encoding="utf-8")
        return True
    return False

changed = 0
for f in HTMLS:
    if patch_html(f):
        changed += 1
print(f"Patched files: {changed}")
