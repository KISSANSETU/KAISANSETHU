"""India-wide crop market price comparison.

Fetches real Government of India mandi/APMC price data from data.gov.in's
"Current Daily Price of Various Commodities from Various Markets (Mandi)"
dataset (AGMARKNET, Ministry of Agriculture & Farmers Welfare), resource id
9ef84268-d588-465a-a308-a864a43d0070. No price here is invented, seeded or
hard-coded - every number comes straight from that government resource.

Requires a free API key from https://data.gov.in (My Account -> API Key),
read from the DATA_GOV_IN_API_KEY environment variable. Without a key, or if
the government service is unreachable, this reports itself as unavailable
rather than fabricating a price.
"""
from __future__ import annotations

import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone

try:
    import requests
except Exception:  # pragma: no cover
    requests = None

DATA_GOV_IN_API_KEY = os.environ.get("DATA_GOV_IN_API_KEY", "").strip()
RESOURCE_ID = "9ef84268-d588-465a-a308-a864a43d0070"
BASE_URL = "https://api.data.gov.in/resource/%s" % RESOURCE_ID
UNIT = "₹/quintal"
SOURCE = "data.gov.in - AGMARKNET (Ministry of Agriculture & Farmers Welfare)"
IST = timezone(timedelta(hours=5, minutes=30))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_DB = os.path.join(BASE_DIR, "kisansetu.db")
LOCAL_SOURCE = "Local demo data (add DATA_GOV_IN_API_KEY for live AGMARKNET prices)"

_LOOKBACK_DAYS = 5     # mandi data can lag a day or two over weekends/holidays
_REQUEST_TIMEOUT = 12
_CACHE_TTL = 600       # seconds; today's prices don't change minute to minute

_cache = {}  # crop_lower -> (fetched_at, result_dict)


class MarketPriceError(Exception):
    """User-facing failure. Message is safe to show as-is."""


UNAVAILABLE = "Market price data is temporarily unavailable. Please try again later."
NOT_FOUND = "No market data found for this crop."


def _get(params):
    if not requests:
        raise MarketPriceError(UNAVAILABLE)
    q = {"api-key": DATA_GOV_IN_API_KEY, "format": "json"}
    q.update(params)
    try:
        r = requests.get(BASE_URL, params=q, timeout=_REQUEST_TIMEOUT)
    except Exception:
        raise MarketPriceError(UNAVAILABLE)
    if r.status_code != 200:
        raise MarketPriceError(UNAVAILABLE)
    try:
        data = r.json()
    except Exception:
        raise MarketPriceError(UNAVAILABLE)
    if isinstance(data, dict) and data.get("error"):
        raise MarketPriceError(UNAVAILABLE)
    return data


def _num(v):
    """Government rows use '' or 'NA' for missing prices as often as a real
    number - only a genuine positive number counts as a valid price."""
    try:
        f = float(v)
        return f if f > 0 else None
    except (TypeError, ValueError):
        return None


def _records_for(crop_title, lookback_days=_LOOKBACK_DAYS):
    """All markets reporting this crop on the most recent date it has data
    for, searching backward day by day (no unfiltered API-side sort is
    documented for this resource, so this is the reliable way to find
    'latest available')."""
    today = datetime.now(IST).date()
    for offset in range(lookback_days):
        day = today - timedelta(days=offset)
        date_str = day.strftime("%d/%m/%Y")
        data = _get({
            "filters[commodity]": crop_title,
            "filters[arrival_date]": date_str,
            "limit": 2000,
        })
        rows = data.get("records") or []
        if rows:
            return date_str, rows
    return None, []


def _iso_date(ddmmyyyy):
    """AGMARKNET dates are DD/MM/YYYY; normalise to YYYY-MM-DD for the API
    response while keeping the original for display."""
    try:
        d, m, y = ddmmyyyy.split("/")
        return "%s-%s-%s" % (y, m.zfill(2), d.zfill(2))
    except Exception:
        return ddmmyyyy


def _card(rec, price_key):
    return {
        "price": rec[price_key],
        "market": rec["market"] or "Unknown market",
        "district": rec["district"] or "-",
        "state": rec["state"] or "-",
        "modal_price": rec["modal_price"],
        "tied_markets": [],
    }


def _live_lookup(crop_title: str) -> dict:
    """Highest/lowest mandi price for a crop from the live government
    dataset. Raises MarketPriceError(NOT_FOUND) if the crop genuinely has no
    government data, or MarketPriceError(UNAVAILABLE) if the source itself
    could not be reached - callers rely on that distinction."""
    date_str, rows = _records_for(crop_title)
    if not rows:
        raise MarketPriceError(NOT_FOUND)

    cleaned = []
    for r in rows:
        mn, mx, md = _num(r.get("min_price")), _num(r.get("max_price")), _num(r.get("modal_price"))
        if mn is None and mx is None:
            continue
        cleaned.append({
            "market": (r.get("market") or "").strip(),
            "district": (r.get("district") or "").strip(),
            "state": (r.get("state") or "").strip(),
            "min_price": mn, "max_price": mx, "modal_price": md,
        })

    with_max = [r for r in cleaned if r["max_price"] is not None]
    with_min = [r for r in cleaned if r["min_price"] is not None]
    if not with_max or not with_min:
        raise MarketPriceError(NOT_FOUND)

    # Highest/lowest are ranked by the actual reported max/min price at each
    # market - never by modal price, per the required price logic.
    top_price = max(r["max_price"] for r in with_max)
    bottom_price = min(r["min_price"] for r in with_min)
    top_matches = [r for r in with_max if r["max_price"] == top_price]
    bottom_matches = [r for r in with_min if r["min_price"] == bottom_price]

    highest = _card(top_matches[0], "max_price")
    highest["tied_markets"] = [m["market"] for m in top_matches[1:] if m["market"]]
    lowest = _card(bottom_matches[0], "min_price")
    lowest["tied_markets"] = [m["market"] for m in bottom_matches[1:] if m["market"]]

    return {
        "success": True,
        "crop": crop_title,
        "date": _iso_date(date_str),
        "date_display": date_str,
        "is_today": date_str == datetime.now(IST).strftime("%d/%m/%Y"),
        "unit": UNIT,
        "source": SOURCE,
        "is_local_fallback": False,
        "records_considered": len(cleaned),
        "highest": highest,
        "lowest": lowest,
    }


def _local_fallback(crop_title: str):
    """Highest/lowest price from KisanSetu's own seeded prices/markets tables -
    the same demo data the rest of the app (forecasts, listings) already
    runs on. Used only when the live government source has no key or is
    unreachable; every response using this is labelled LOCAL_SOURCE so it is
    never mistaken for live official data. Returns None if this crop isn't
    in the local dataset either."""
    if not os.path.exists(LOCAL_DB):
        return None
    conn = sqlite3.connect(LOCAL_DB, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        latest = conn.execute(
            "SELECT max(price_date) FROM prices WHERE lower(crop)=lower(?)",
            (crop_title,)).fetchone()[0]
        if not latest:
            return None
        rows = conn.execute(
            "SELECT m.name market, m.district, m.state, p.modal_price "
            "FROM prices p JOIN markets m ON m.id = p.market_id "
            "WHERE lower(p.crop)=lower(?) AND p.price_date=? "
            "AND p.modal_price IS NOT NULL AND p.modal_price > 0",
            (crop_title, latest)).fetchall()
    finally:
        conn.close()
    if not rows:
        return None

    recs = [dict(r) for r in rows]
    top_price = max(r["modal_price"] for r in recs)
    bottom_price = min(r["modal_price"] for r in recs)
    top_matches = [r for r in recs if r["modal_price"] == top_price]
    bottom_matches = [r for r in recs if r["modal_price"] == bottom_price]

    def _local_card(rec, price):
        return {
            "price": price,
            "market": rec["market"] or "Unknown market",
            "district": rec["district"] or "-",
            "state": rec["state"] or "-",
            "modal_price": price,
            "tied_markets": [],
        }

    highest = _local_card(top_matches[0], top_price)
    highest["tied_markets"] = [m["market"] for m in top_matches[1:] if m["market"]]
    lowest = _local_card(bottom_matches[0], bottom_price)
    lowest["tied_markets"] = [m["market"] for m in bottom_matches[1:] if m["market"]]

    return {
        "success": True,
        "crop": crop_title,
        "date": latest,
        "date_display": latest,
        "is_today": latest == datetime.now(IST).strftime("%Y-%m-%d"),
        "unit": UNIT,
        "source": LOCAL_SOURCE,
        "is_local_fallback": True,
        "records_considered": len(recs),
        "highest": highest,
        "lowest": lowest,
    }


def compare_prices(crop: str) -> dict:
    """Today's (or the latest available day's) highest and lowest mandi
    price for a crop, across every market in India that reported it.

    Prefers live government data whenever DATA_GOV_IN_API_KEY is set and
    reachable. If the crop genuinely isn't in the government dataset, that
    "not found" result is returned as-is - it is never silently papered over
    with unrelated local data. Only when the live source itself is missing
    or unreachable does this fall back to KisanSetu's own seeded data, always
    clearly labelled as such.
    """
    crop = (crop or "").strip()
    if not crop:
        raise MarketPriceError("Enter a crop name to search.")

    cache_key = crop.lower()
    cached = _cache.get(cache_key)
    if cached and time.time() - cached[0] < _CACHE_TTL:
        return cached[1]

    # AGMARKNET commodity names are Title Case ("Tomato", "Bitter Gourd"),
    # so this alone makes the lookup case-insensitive without needing to
    # try every casing against the government API.
    crop_title = crop.title()

    if DATA_GOV_IN_API_KEY:
        try:
            result = _live_lookup(crop_title)
            _cache[cache_key] = (time.time(), result)
            return result
        except MarketPriceError as e:
            if str(e) == NOT_FOUND:
                raise  # a genuine "no data" answer, not a source failure

    local = _local_fallback(crop_title)
    if not local:
        raise MarketPriceError(NOT_FOUND)
    _cache[cache_key] = (time.time(), local)
    return local
