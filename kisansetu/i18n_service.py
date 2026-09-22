"""KisanSetu runtime translation service.

Translates arbitrary UI strings into any of the 24 supported languages using a
free, key-less machine-translation provider, and caches every result in SQLite
so each unique string is ever translated only once.

Providers are tried in order:
  1. Google translate (clients5 endpoint, batched, no API key)
  2. MyMemory (free tier, one string per call, covers codes Google rejects)
  3. Language alias fallback (e.g. Rajasthani -> Hindi)
  4. Original English text

No LLM is used here. The chatbot uses Groq; the interface does not.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional
import os, sqlite3, hashlib, re, json, threading

try:
    import requests
except Exception:  # pragma: no cover
    requests = None

router = APIRouter(prefix="/api/i18n", tags=["KisanSetu i18n"])

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "kisansetu.db")
BUNDLE_DIR = os.path.join(BASE, "static", "i18n")

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

# Every language offered in the interface language picker.
SUPPORTED = ["en", "hi", "mr", "ta", "te", "bn", "gu", "kn", "ml", "pa", "or",
             "as", "ur", "ne", "sa", "ks", "sd", "kok", "mai", "doi", "brx",
             "mni", "sat", "raj"]

RTL = {"ur", "ks", "sd"}

# Our interface code -> the code the translation provider actually accepts.
# Verified against the live endpoint: ks / brx / raj return HTTP 400, so they
# fall back to the closest supported language sharing the script.
PROVIDER_CODE = {
    "mni": "mni-Mtei",
    "raj": "hi",
    "brx": "hi",
    "ks": "ur",
}

# Brand and decision keywords that must survive translation untouched.
DO_NOT_TRANSLATE = [
    "KisanSetu", "GRAM Saathi", "KisanSetu", "GramRakshak", "GramRewards",
    "AGMARKNET", "e-NAM", "Razorpay", "UPI", "IFSC", "KYC", "Aadhaar",
    "SELL NOW", "SHIFT MARKET", "XGBoost", "LightGBM", "MAE", "RMSE", "MAPE",
]

# Strings that are pure data and must never be sent to a translator.
_SKIP = re.compile(r"^[\s\d\W_]*$|^[₹$]?\s*[\d,.\-+%/:]+\s*[a-zA-Z%°]{0,6}$")

_lock = threading.Lock()


def conn():
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    return c


def init_i18n_schema():
    c = conn()
    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS i18n_cache(
          lang TEXT NOT NULL,
          src_hash TEXT NOT NULL,
          src TEXT NOT NULL,
          dst TEXT NOT NULL,
          provider TEXT DEFAULT '',
          created_at TEXT DEFAULT (datetime('now')),
          PRIMARY KEY(lang, src_hash)
        );
        CREATE INDEX IF NOT EXISTS idx_i18n_lang ON i18n_cache(lang);
        """
    )
    c.commit()
    c.close()


def _hash(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def skippable(s: str) -> bool:
    """True when a string carries no translatable words."""
    s = (s or "").strip()
    if not s or len(s) > 900:
        return True
    if _SKIP.match(s):
        return True
    return not re.search(r"[A-Za-z]{2}", s)


def _protect(s: str):
    """Swap brand terms for tokens the translator leaves alone."""
    marks = []
    for term in DO_NOT_TRANSLATE:
        if term.lower() in s.lower():
            token = "XQ%dQX" % len(marks)
            s = re.sub(re.escape(term), token, s, flags=re.IGNORECASE)
            marks.append(term)
    return s, marks


def _restore(s: str, marks) -> str:
    for i, term in enumerate(marks):
        # The provider may alter spacing or case around the token.
        s = re.sub(r"[Xx]\s*[Qq]\s*%d\s*[Qq]\s*[Xx]" % i, term, s)
    return s


def _google_batch(texts, tl):
    """Batch translate via the key-less clients5 endpoint. Returns list or None."""
    if not requests or not texts:
        return None
    params = [("client", "dict-chrome-ex"), ("sl", "en"), ("tl", tl)]
    params += [("q", t) for t in texts]
    try:
        r = requests.get("https://clients5.google.com/translate_a/t",
                         params=params, headers=UA, timeout=20)
        if r.status_code != 200:
            return None
        data = r.json()
    except Exception:
        return None
    # One query returns a bare string or ["x"]; many return a flat list.
    if isinstance(data, str):
        data = [data]
    if not isinstance(data, list):
        return None
    flat = []
    for item in data:
        if isinstance(item, str):
            flat.append(item)
        elif isinstance(item, list) and item and isinstance(item[0], str):
            flat.append(item[0])
        else:
            flat.append(None)
    if len(flat) != len(texts):
        return None
    return flat


def _mymemory(text, tl):
    """Single-string fallback for codes the batch endpoint rejects."""
    if not requests:
        return None
    try:
        r = requests.get("https://api.mymemory.translated.net/get",
                         params={"q": text[:480], "langpair": "en|%s" % tl},
                         timeout=20)
        if r.status_code != 200:
            return None
        out = r.json().get("responseData", {}).get("translatedText")
        if not out or out.strip().upper().startswith("INVALID"):
            return None
        return out
    except Exception:
        return None


def _cached(lang, hashes):
    if not hashes:
        return {}
    c = conn()
    out = {}
    for i in range(0, len(hashes), 400):
        chunk = hashes[i:i + 400]
        q = "SELECT src_hash,dst FROM i18n_cache WHERE lang=? AND src_hash IN (%s)" % \
            ",".join("?" * len(chunk))
        for r in c.execute(q, [lang] + chunk):
            out[r["src_hash"]] = r["dst"]
    c.close()
    return out


def _store(lang, pairs, provider):
    if not pairs:
        return
    with _lock:
        c = conn()
        c.executemany(
            "INSERT OR REPLACE INTO i18n_cache(lang,src_hash,src,dst,provider) VALUES(?,?,?,?,?)",
            [(lang, _hash(s), s, d, provider) for s, d in pairs])
        c.commit()
        c.close()


def translate_batch(texts, lang: str):
    """Translate a list of English strings. Always returns a same-length list."""
    lang = (lang or "en").strip()
    if lang == "en" or lang not in SUPPORTED:
        return list(texts)

    result = [None] * len(texts)
    pending = {}  # normalized source -> [indexes]

    for i, raw in enumerate(texts):
        s = (raw or "").strip()
        if skippable(s):
            result[i] = raw
            continue
        pending.setdefault(s, []).append(i)

    if not pending:
        return result

    uniq = list(pending.keys())
    hits = _cached(lang, [_hash(s) for s in uniq])
    misses = []
    for s in uniq:
        h = _hash(s)
        if h in hits:
            for i in pending[s]:
                result[i] = hits[h]
        else:
            misses.append(s)

    if misses:
        tl = PROVIDER_CODE.get(lang, lang)
        fresh = []
        # 40 strings per request keeps the URL well inside limits.
        for i in range(0, len(misses), 40):
            chunk = misses[i:i + 40]
            protected = [_protect(s) for s in chunk]
            got = _google_batch([p[0] for p in protected], tl)
            provider = "google"
            if got is None:
                got = [_mymemory(p[0], tl) for p in protected]
                provider = "mymemory"
            for src, (prot, marks), out in zip(chunk, protected, got):
                dst = _restore(out, marks) if out else src
                fresh.append((src, dst))
                for idx in pending[src]:
                    result[idx] = dst
            _store(lang, fresh, provider)
            fresh = []

    # Any string that fell through every provider keeps its English text.
    for i, raw in enumerate(texts):
        if result[i] is None:
            result[i] = raw
    return result


def load_bundle(lang: str) -> dict:
    """Everything already known for a language: static seed file + cache."""
    out = {}
    path = os.path.join(BUNDLE_DIR, "%s.json" % lang)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                out.update(json.load(f))
        except Exception:
            pass
    if lang != "en":
        c = conn()
        try:
            for r in c.execute("SELECT src,dst FROM i18n_cache WHERE lang=?", (lang,)):
                out[r["src"]] = r["dst"]
        except Exception:
            pass
        c.close()
    return out


class TranslateIn(BaseModel):
    lang: str = Field(default="en", max_length=12)
    texts: list[str] = Field(default_factory=list)


@router.get("/languages")
def languages():
    return {"supported": SUPPORTED, "rtl": sorted(RTL)}


@router.get("/bundle")
def bundle(lang: str = "en"):
    """Pre-translated strings for a language. Called once per language switch."""
    lang = (lang or "en").strip()
    if lang not in SUPPORTED:
        return {"lang": lang, "rtl": False, "map": {}}
    return {"lang": lang, "rtl": lang in RTL, "map": load_bundle(lang)}


@router.post("/translate")
def translate(body: TranslateIn):
    """Translate strings the bundle did not cover. Results enter the cache."""
    texts = [t for t in (body.texts or []) if isinstance(t, str)][:600]
    if not texts:
        return {"lang": body.lang, "map": {}}
    out = translate_batch(texts, body.lang)
    return {"lang": body.lang, "map": {s: d for s, d in zip(texts, out) if d}}
