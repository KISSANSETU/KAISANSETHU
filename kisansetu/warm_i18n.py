"""Pre-warm the translation cache so language switching is instant on demo day.

Pulls the interface strings out of index.html and app.js, translates them into
every supported language through i18n_service (free provider, SQLite-cached),
and writes static/i18n/<lang>.json so the browser gets one warm bundle per
language instead of translating on first view.

  python warm_i18n.py            # every language
  python warm_i18n.py hi mr ta   # only these
"""
from __future__ import annotations

import os, re, io, json, sys, time

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "static")
OUT_DIR = os.path.join(STATIC, "i18n")

sys.path.insert(0, BASE)
from i18n_service import SUPPORTED, translate_batch, skippable, init_i18n_schema


def from_html(path):
    """Visible text and translatable attributes from the shell page."""
    if not os.path.exists(path):
        return []
    s = io.open(path, encoding="utf-8").read()
    s = re.sub(r"<(script|style)\b.*?</\1>", " ", s, flags=re.S | re.I)
    found = re.findall(r">([^<>{}]{2,120})<", s)
    for attr in ("placeholder", "title", "aria-label", "alt"):
        found += re.findall(r'%s="([^"]{2,120})"' % attr, s)
    return found


def from_js(path):
    """Interface strings from the SPA: markup text, labels and quoted literals."""
    if not os.path.exists(path):
        return []
    s = io.open(path, encoding="utf-8").read()
    out = []

    # Text between tags inside template literals, e.g. `<b>Best Market</b>`
    out += re.findall(r">([A-Za-z][^<>{}`$\n]{1,110})<", s)

    # Attribute text inside template literals.
    for attr in ("placeholder", "title", "aria-label", "alt", "label"):
        out += re.findall(r'%s="([A-Za-z][^"{}$\n]{1,110})"' % attr, s)

    # Values of the built-in English dictionary and any single-quoted UI label.
    out += re.findall(r"[A-Za-z0-9_]+:'([A-Za-z][^'\\\n]{1,110})'", s)

    # toast('...') and tr('...') style calls.
    out += re.findall(r"toast\(\s*'([^'\\\n]{2,110})'", s)
    out += re.findall(r'toast\(\s*"([^"\\\n]{2,110})"', s)

    # Option labels: <option value="X">Label</option> already covered by the
    # first pattern; chart axis titles and headings often sit in plain quotes.
    out += re.findall(r"text:\s*'([A-Za-z][^'\\\n]{2,110})'", s)
    return out


def clean(items):
    seen, out = set(), []
    for raw in items:
        s = re.sub(r"\s+", " ", (raw or "")).strip()
        s = s.replace("&amp;", "&").replace("&nbsp;", " ").strip()
        if not s or s in seen:
            continue
        if skippable(s):
            continue
        # Drop anything that still holds template or code syntax.
        if re.search(r"[{}$`\\]|=>|\bfunction\b|</", s):
            continue
        if len(s) < 2 or len(s) > 160:
            continue
        seen.add(s)
        out.append(s)
    return out


def collect():
    items = []
    items += from_html(os.path.join(STATIC, "index.html"))
    items += from_js(os.path.join(STATIC, "app.js"))
    items += from_js(os.path.join(STATIC, "chatbot.js"))
    return clean(items)


def main():
    init_i18n_schema()
    os.makedirs(OUT_DIR, exist_ok=True)

    strings = collect()
    print("Extracted %d unique interface strings." % len(strings))
    io.open(os.path.join(OUT_DIR, "en.json"), "w", encoding="utf-8").write(
        json.dumps({s: s for s in strings}, ensure_ascii=False, indent=0))

    langs = [a for a in sys.argv[1:] if a in SUPPORTED and a != "en"]
    if not langs:
        langs = [l for l in SUPPORTED if l != "en"]

    for lang in langs:
        t0 = time.time()
        done = translate_batch(strings, lang)
        mapping = {s: d for s, d in zip(strings, done) if d and d != s}
        path = os.path.join(OUT_DIR, "%s.json" % lang)
        io.open(path, "w", encoding="utf-8").write(
            json.dumps(mapping, ensure_ascii=False, indent=0))
        print("  %-4s %5d strings  %6.1fs  -> %s" %
              (lang, len(mapping), time.time() - t0, os.path.basename(path)))

    print("\nDone. Bundles are in static/i18n/ and the SQLite cache is warm.")


if __name__ == "__main__":
    main()
