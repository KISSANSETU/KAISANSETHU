"""FastAPI routes for Distress Redressal & Dynamic MSP Floor.

Drop-in router. Host app only needs:
    from msp_distress import router as msp_router
    app.include_router(msp_router)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
import hashlib
import os
import sqlite3
import secrets

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .distress_engine import (
    DistressEngineError,
    bid_meets_floor,
    dwr_loan_advance,
    evaluate_floor,
    haversine_km,
    logistics_from_distance,
)
from .schema import init_msp_schema

router = APIRouter(tags=["MSP Distress Redressal"])

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BASE, "kisansetu.db")
TOKEN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tokens")
os.makedirs(TOKEN_DIR, exist_ok=True)

DEFAULT_LAT = 18.5204
DEFAULT_LON = 73.8567
DEFAULT_STORAGE_DAILY = 0.35


def _conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def _now():
    return datetime.now(timezone.utc).isoformat()


def _row(r):
    return dict(r) if r else None


def _get_user():
    from app import user
    return user


def _require(u, *roles):
    if u["role"] not in roles:
        raise HTTPException(403, "This action is not available for your portal role")


def _ensure_schema():
    init_msp_schema(DB)


_ensure_schema()


class EvaluateIn(BaseModel):
    crop_id: Optional[int] = None
    crop: Optional[str] = None
    quantity: float = Field(default=1000, gt=0, description="Quantity in kg")
    quality_grade: str = Field(default="B")
    lat: float = Field(default=DEFAULT_LAT)
    lon: float = Field(default=DEFAULT_LON)
    holding_days: float = Field(default=0, ge=0)
    storage_daily_per_kg: Optional[float] = Field(default=None, ge=0)
    logistics_per_kg: Optional[float] = Field(default=None, ge=0)
    current_offer_per_kg: Optional[float] = Field(default=None, ge=0)
    dest_lat: Optional[float] = None
    dest_lon: Optional[float] = None


class ReverseListIn(BaseModel):
    crop: str = Field(min_length=2)
    quality_grade: str = "B"
    quantity_kg: float = Field(gt=0)
    lat: float = DEFAULT_LAT
    lon: float = DEFAULT_LON
    origin_district: str = ""
    origin_state: str = "Maharashtra"
    holding_days: float = Field(default=0, ge=0)
    storage_daily_per_kg: float = Field(default=0, ge=0)
    logistics_per_kg: Optional[float] = None
    dest_lat: Optional[float] = None
    dest_lon: Optional[float] = None


class ReverseBidIn(BaseModel):
    bid_per_kg: float = Field(gt=0)
    buyer_district: str = ""
    logistics_per_kg: float = Field(default=0, ge=0)


class ColdBookIn(BaseModel):
    facility_id: int
    crop: str = Field(min_length=2)
    quality_grade: str = "B"
    quantity_kg: float = Field(gt=0)
    days_booked: int = Field(ge=0, le=90)
    lat: float = DEFAULT_LAT
    lon: float = DEFAULT_LON
    current_offer_per_kg: Optional[float] = None


class DwrLoanIn(BaseModel):
    booking_id: int


class ProcurementTokenIn(BaseModel):
    center_id: int
    crop: str = Field(min_length=2)
    quality_grade: str = "B"
    quantity_kg: float = Field(gt=0)


def _resolve_crop(c, crop_id: Optional[int], crop: Optional[str]):
    row = None
    if crop_id:
        row = c.execute("SELECT * FROM crops WHERE id=?", (crop_id,)).fetchone()
    if row is None and crop:
        row = c.execute("SELECT * FROM crops WHERE name=?", (crop.strip(),)).fetchone()
    if row is None and crop:
        return {"id": None, "name": crop.strip()}
    if row is None:
        raise HTTPException(400, "Provide crop or crop_id")
    return {"id": row["id"], "name": row["name"]}


def _msp_for(c, crop_name: str, crop_id: Optional[int] = None) -> float:
    row = None
    if crop_id:
        row = c.execute(
            """SELECT msp_price_per_kg FROM msp_baseline_rates
               WHERE crop_id=? ORDER BY effective_year DESC LIMIT 1""",
            (crop_id,),
        ).fetchone()
    if row is None:
        row = c.execute(
            """SELECT msp_price_per_kg FROM msp_baseline_rates
               WHERE crop=? COLLATE NOCASE ORDER BY effective_year DESC LIMIT 1""",
            (crop_name,),
        ).fetchone()
    if row is None:
        raise HTTPException(404, f"No MSP baseline seeded for crop '{crop_name}'")
    return float(row["msp_price_per_kg"])


def _forecast_mandi(c, crop_name: str, lat: float, lon: float) -> tuple[float, Optional[int], str]:
    market = c.execute(
        """SELECT id, name, district, lat, lon,
                  ((lat-?)*(lat-?)+(lon-?)*(lon-?)) d
           FROM markets ORDER BY d LIMIT 1""",
        (lat, lat, lon, lon),
    ).fetchone()
    if not market:
        latest = c.execute(
            """SELECT modal_price FROM prices WHERE crop=? ORDER BY price_date DESC LIMIT 1""",
            (crop_name,),
        ).fetchone()
        if not latest:
            raise HTTPException(404, f"No mandi price history for {crop_name}")
        return float(latest["modal_price"]) / 100.0, None, "unknown"
    latest = c.execute(
        """SELECT modal_price FROM prices
           WHERE crop=? AND market_id=? ORDER BY price_date DESC LIMIT 1""",
        (crop_name, market["id"]),
    ).fetchone()
    avg7 = c.execute(
        """SELECT avg(modal_price) p FROM (
               SELECT modal_price FROM prices
               WHERE crop=? AND market_id=? ORDER BY price_date DESC LIMIT 7
           )""",
        (crop_name, market["id"]),
    ).fetchone()
    # Seeded prices are ₹/quintal; convert to ₹/kg for the floor engine.
    current = float((latest["modal_price"] if latest else avg7["p"] or 0)) / 100.0
    forecast = float(avg7["p"] or (latest["modal_price"] if latest else 0)) / 100.0
    # Blend: use 7-day average as predicted mandi price.
    predicted = forecast if forecast else current
    print(
        f"[MSP-API] mandi={market['name']} crop={crop_name} "
        f"P_current/kg={current:.2f} P_forecast/kg={predicted:.2f}"
    )
    return predicted, market["id"], market["name"]


def _recovery_days(p_forecast: float, p_msp: float) -> int:
    if p_forecast >= p_msp:
        return 7
    gap = (p_msp - p_forecast) / max(p_msp, 1e-6)
    if gap < 0.08:
        return 10
    if gap < 0.18:
        return 14
    return 21


def _pathways(is_distress: bool, f_dynamic: float, p_msp: float):
    return [
        {
            "id": "REVERSE_BID",
            "title": "Out-of-District Reverse Bidding",
            "summary": "Sell to verified buyers outside your mandi distress zone. Starting bid cannot go below F_dynamic.",
            "floor": f_dynamic,
            "recommended": is_distress,
        },
        {
            "id": "COLD_STORAGE",
            "title": "Cold Storage & 70% Cash Advance",
            "summary": "Book a partner cold store, issue an e-DWR, and take a mock fintech loan of 70% of stored value.",
            "floor": f_dynamic,
            "recommended": is_distress,
        },
        {
            "id": "GOVT_MSP",
            "title": "Government Procurement (Official MSP)",
            "summary": "Route to the nearest FCI / State MSP centre with a pre-filled digital token.",
            "floor": p_msp,
            "recommended": is_distress,
        },
    ]


@router.post("/api/v1/distress/evaluate")
def evaluate_distress(body: EvaluateIn, u=Depends(_get_user())):
    """Return distress flag, forecast, MSP, F_dynamic and the 3 redressal pathways."""
    _require(u, "farmer", "buyer", "admin")
    c = _conn()
    crop = _resolve_crop(c, body.crop_id, body.crop)
    p_msp = _msp_for(c, crop["name"], crop["id"])
    predicted, market_id, market_name = _forecast_mandi(c, crop["name"], body.lat, body.lon)
    holding = body.holding_days
    if holding == 0:
        holding = _recovery_days(predicted, p_msp)
    logistics = body.logistics_per_kg
    if logistics is None:
        logistics = 0.0
        if body.dest_lat is not None and body.dest_lon is not None:
            logistics = logistics_from_distance(
                haversine_km(body.lat, body.lon, body.dest_lat, body.dest_lon)
            )
    daily = body.storage_daily_per_kg if body.storage_daily_per_kg is not None else 0.0
    try:
        breakdown = evaluate_floor(
            p_msp=p_msp,
            quality_grade=body.quality_grade,
            p_mandi_predicted=predicted,
            storage_daily_per_kg=daily,
            holding_days=holding if daily else 0,
            logistics_per_kg=logistics,
            p_current_offer=body.current_offer_per_kg,
        )
    except DistressEngineError as e:
        c.close()
        raise HTTPException(400, str(e))

    event_id = None
    if breakdown.is_distress and u["role"] == "farmer":
        cur = c.execute(
            """INSERT INTO distress_events
               (farmer_id, crop_id, crop, local_mandi_price, dynamic_floor_calculated,
                p_msp, quality_grade, status, district, created_at)
               VALUES (?,?,?,?,?,?,?,'OPEN',?,?)""",
            (
                u["id"],
                crop["id"],
                crop["name"],
                predicted,
                breakdown.f_dynamic,
                p_msp,
                breakdown.quality_grade,
                u.get("district") or "",
                _now(),
            ),
        )
        event_id = cur.lastrowid
        c.commit()
        print(f"[MSP-API] distress event #{event_id} opened for farmer={u['id']} crop={crop['name']}")
    c.close()

    payload = breakdown.as_dict()
    payload.update(
        {
            "crop": crop["name"],
            "crop_id": crop["id"],
            "quantity_kg": body.quantity,
            "market_id": market_id,
            "market_name": market_name,
            "suggested_holding_days": _recovery_days(predicted, p_msp),
            "event_id": event_id,
            "pathways": _pathways(breakdown.is_distress, breakdown.f_dynamic, p_msp),
            "P_forecast": breakdown.p_mandi_predicted,
            "P_MSP": breakdown.p_msp,
            "F_dynamic": breakdown.f_dynamic,
        }
    )
    print(f"[MSP-API] evaluate ok is_distress={breakdown.is_distress} F_dynamic={breakdown.f_dynamic}")
    return payload


@router.get("/api/v1/distress/msp-rates")
def list_msp_rates(u=Depends(_get_user())):
    c = _conn()
    rows = [dict(r) for r in c.execute(
        "SELECT * FROM msp_baseline_rates ORDER BY crop"
    ).fetchall()]
    c.close()
    return rows


@router.get("/api/v1/distress/events")
def list_events(u=Depends(_get_user())):
    c = _conn()
    if u["role"] == "admin":
        rows = c.execute("SELECT * FROM distress_events ORDER BY event_id DESC LIMIT 100").fetchall()
    else:
        rows = c.execute(
            "SELECT * FROM distress_events WHERE farmer_id=? ORDER BY event_id DESC LIMIT 50",
            (u["id"],),
        ).fetchall()
    c.close()
    return [dict(r) for r in rows]


@router.post("/api/v1/marketplace/reverse-bid/distress-list")
def create_distress_listing(body: ReverseListIn, u=Depends(_get_user())):
    """Farmer posts an out-of-zone lot. Min bid is locked to F_dynamic."""
    _require(u, "farmer", "admin")
    c = _conn()
    crop = _resolve_crop(c, None, body.crop)
    p_msp = _msp_for(c, crop["name"], crop["id"])
    predicted, _, _ = _forecast_mandi(c, crop["name"], body.lat, body.lon)
    logistics = body.logistics_per_kg
    if logistics is None:
        logistics = 0.0
        if body.dest_lat is not None and body.dest_lon is not None:
            logistics = logistics_from_distance(
                haversine_km(body.lat, body.lon, body.dest_lat, body.dest_lon)
            )
    breakdown = evaluate_floor(
        p_msp=p_msp,
        quality_grade=body.quality_grade,
        p_mandi_predicted=predicted,
        storage_daily_per_kg=body.storage_daily_per_kg,
        holding_days=body.holding_days if body.storage_daily_per_kg else 0,
        logistics_per_kg=logistics,
    )
    district = body.origin_district or u.get("district") or ""
    cur = c.execute(
        """INSERT INTO distress_reverse_listings
           (farmer_id, crop, quality_grade, quantity_kg, origin_district, origin_state,
            lat, lon, f_dynamic, min_bid_per_kg, p_msp_quality, logistics_per_kg, status, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'OPEN',?)""",
        (
            u["id"],
            crop["name"],
            breakdown.quality_grade,
            body.quantity_kg,
            district,
            body.origin_state or u.get("state") or "Maharashtra",
            body.lat,
            body.lon,
            breakdown.f_dynamic,
            breakdown.f_dynamic,
            breakdown.p_msp_quality,
            logistics,
            _now(),
        ),
    )
    listing_id = cur.lastrowid
    c.commit()
    c.close()
    print(f"[MSP-API] reverse listing #{listing_id} min_bid={breakdown.f_dynamic}")
    return {
        "listing_id": listing_id,
        "min_bid_per_kg": breakdown.f_dynamic,
        "cost_breakdown": {
            "base_msp_quality": breakdown.p_msp_quality,
            "quality_grade": breakdown.quality_grade,
            "quality_certificate_multiplier": breakdown.q_m,
            "distance_logistics": logistics,
            "F_dynamic": breakdown.f_dynamic,
        },
        "status": "OPEN",
    }


@router.get("/api/v1/marketplace/reverse-bid/listings")
def list_reverse_listings(u=Depends(_get_user())):
    c = _conn()
    if u["role"] == "farmer":
        rows = c.execute(
            """SELECT * FROM distress_reverse_listings
               WHERE farmer_id=? ORDER BY listing_id DESC""",
            (u["id"],),
        ).fetchall()
    else:
        origin = (u.get("district") or "").strip()
        rows = c.execute(
            """SELECT l.*, u.name farmer_name FROM distress_reverse_listings l
               JOIN users u ON u.id=l.farmer_id
               WHERE l.status='OPEN'
               ORDER BY listing_id DESC"""
        ).fetchall()
        if origin:
            # Prefer lots whose origin district differs from the buyer (out-of-zone).
            ranked = sorted(
                rows,
                key=lambda r: (0 if (r["origin_district"] or "").lower() != origin.lower() else 1),
            )
            rows = ranked
    listings = [dict(r) for r in rows]
    for item in listings:
        bids = c.execute(
            "SELECT * FROM distress_reverse_bids WHERE listing_id=? ORDER BY bid_per_kg DESC",
            (item["listing_id"],),
        ).fetchall()
        item["bids"] = [dict(b) for b in bids]
        item["cost_breakdown"] = {
            "base_bid_floor": item["min_bid_per_kg"],
            "quality_grade_certificate": item["quality_grade"],
            "p_msp_quality": item["p_msp_quality"],
            "distance_logistics": item["logistics_per_kg"],
        }
    c.close()
    return listings


@router.post("/api/v1/marketplace/reverse-bid/{listing_id}/bid")
def place_reverse_bid(listing_id: int, body: ReverseBidIn, u=Depends(_get_user())):
    """Reject any buyer bid below F_dynamic."""
    _require(u, "buyer", "admin")
    c = _conn()
    listing = c.execute(
        "SELECT * FROM distress_reverse_listings WHERE listing_id=? AND status='OPEN'",
        (listing_id,),
    ).fetchone()
    if not listing:
        c.close()
        raise HTTPException(404, "Open distress listing not found")
    floor = float(listing["f_dynamic"])
    if not bid_meets_floor(body.bid_per_kg, floor):
        c.close()
        print(f"[MSP-API] REJECTED bid {body.bid_per_kg} < F_dynamic {floor}")
        raise HTTPException(
            400,
            f"Bid ₹{body.bid_per_kg:.2f}/kg is below Dynamic MSP Floor ₹{floor:.2f}/kg and was blocked.",
        )
    buyer_district = body.buyer_district or u.get("district") or ""
    out_of_zone = True
    if buyer_district and listing["origin_district"]:
        out_of_zone = buyer_district.strip().lower() != listing["origin_district"].strip().lower()
    cur = c.execute(
        """INSERT INTO distress_reverse_bids
           (listing_id, buyer_id, bid_per_kg, buyer_district, logistics_per_kg, status, created_at)
           VALUES (?,?,?,?,?,'OFFERED',?)""",
        (listing_id, u["id"], body.bid_per_kg, buyer_district, body.logistics_per_kg, _now()),
    )
    c.commit()
    bid_id = cur.lastrowid
    c.close()
    print(f"[MSP-API] accepted reverse bid #{bid_id} @ {body.bid_per_kg} >= floor {floor} out_of_zone={out_of_zone}")
    return {
        "bid_id": bid_id,
        "status": "OFFERED",
        "F_dynamic": floor,
        "bid_per_kg": body.bid_per_kg,
        "out_of_zone": out_of_zone,
    }


@router.get("/api/v1/cold-storage/facilities")
def list_facilities(lat: float = DEFAULT_LAT, lon: float = DEFAULT_LON, u=Depends(_get_user())):
    c = _conn()
    rows = c.execute("SELECT * FROM cold_storage_facilities").fetchall()
    c.close()
    out = []
    for r in rows:
        item = dict(r)
        item["distance_km"] = haversine_km(lat, lon, r["lat"], r["lon"])
        out.append(item)
    out.sort(key=lambda x: x["distance_km"])
    return out


@router.post("/api/v1/cold-storage/book")
def book_cold_storage(body: ColdBookIn, u=Depends(_get_user())):
    """Book a slot, recompute F_dynamic with holding days, and issue e-DWR."""
    _require(u, "farmer", "admin")
    c = _conn()
    fac = c.execute(
        "SELECT * FROM cold_storage_facilities WHERE facility_id=?",
        (body.facility_id,),
    ).fetchone()
    if not fac:
        c.close()
        raise HTTPException(404, "Cold storage facility not found")
    crop = _resolve_crop(c, None, body.crop)
    p_msp = _msp_for(c, crop["name"], crop["id"])
    predicted, _, _ = _forecast_mandi(c, crop["name"], body.lat, body.lon)
    logistics = logistics_from_distance(haversine_km(body.lat, body.lon, fac["lat"], fac["lon"]))
    breakdown = evaluate_floor(
        p_msp=p_msp,
        quality_grade=body.quality_grade,
        p_mandi_predicted=predicted,
        storage_daily_per_kg=float(fac["daily_rate_per_kg"]),
        holding_days=body.days_booked,
        logistics_per_kg=logistics,
        p_current_offer=body.current_offer_per_kg,
    )
    nonce = secrets.token_hex(8)
    dwr_hash = hashlib.sha256(
        f"{u['id']}|{body.facility_id}|{crop['name']}|{body.quantity_kg}|{body.days_booked}|{nonce}|{_now()}".encode()
    ).hexdigest()
    cur = c.execute(
        """INSERT INTO cold_storage_bookings
           (farmer_id, facility_id, crop, quality_grade, quantity_kg, days_booked,
            daily_rate_per_kg, logistics_per_kg, f_dynamic, dwr_hash, status, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,'DEPOSITED',?)""",
        (
            u["id"],
            body.facility_id,
            crop["name"],
            breakdown.quality_grade,
            body.quantity_kg,
            body.days_booked,
            float(fac["daily_rate_per_kg"]),
            logistics,
            breakdown.f_dynamic,
            dwr_hash,
            _now(),
        ),
    )
    booking_id = cur.lastrowid
    crop_value = round(body.quantity_kg * breakdown.p_msp_quality, 2)
    advance = dwr_loan_advance(crop_value)
    c.execute(
        """INSERT INTO dwr_loans
           (farmer_id, booking_id, dwr_hash, crop_value, ltv, advance_amount, status, created_at)
           VALUES (?,?,?,?,?,?,'OFFERED',?)""",
        (u["id"], booking_id, dwr_hash, crop_value, 0.70, advance, _now()),
    )
    c.commit()
    c.close()
    print(f"[MSP-API] cold booking #{booking_id} DWR={dwr_hash[:12]}… F_dynamic={breakdown.f_dynamic}")
    return {
        "booking_id": booking_id,
        "dwr_hash": dwr_hash,
        "e_dwr": {
            "receipt": f"DWR-{booking_id:06d}",
            "hash": dwr_hash,
            "facility": fac["name"],
            "quantity_kg": body.quantity_kg,
            "days_booked": body.days_booked,
        },
        "F_dynamic": breakdown.f_dynamic,
        "breakdown": breakdown.as_dict(),
        "loan_offer": {
            "endpoint": "/api/v1/finance/dwr-loan",
            "ltv": 0.70,
            "crop_value": crop_value,
            "advance_amount": advance,
            "status": "OFFERED",
        },
    }


@router.get("/api/v1/cold-storage/bookings")
def my_bookings(u=Depends(_get_user())):
    c = _conn()
    rows = c.execute(
        """SELECT b.*, f.name facility_name, f.district facility_district
           FROM cold_storage_bookings b
           JOIN cold_storage_facilities f ON f.facility_id=b.facility_id
           WHERE b.farmer_id=? ORDER BY booking_id DESC""",
        (u["id"],),
    ).fetchall()
    c.close()
    return [dict(r) for r in rows]


@router.post("/api/v1/finance/dwr-loan")
def dwr_loan(body: DwrLoanIn, u=Depends(_get_user())):
    """Fintech mock: 70% cash advance against a deposited e-DWR."""
    _require(u, "farmer", "admin")
    c = _conn()
    loan = c.execute(
        "SELECT * FROM dwr_loans WHERE booking_id=? AND farmer_id=?",
        (body.booking_id, u["id"]),
    ).fetchone()
    if not loan:
        c.close()
        raise HTTPException(404, "No DWR loan offer for this booking")
    c.execute(
        "UPDATE dwr_loans SET status='DISBURSED_MOCK' WHERE loan_id=?",
        (loan["loan_id"],),
    )
    c.commit()
    out = dict(loan)
    out["status"] = "DISBURSED_MOCK"
    c.close()
    print(f"[MSP-API] mock DWR loan disbursed loan_id={loan['loan_id']} amount={loan['advance_amount']}")
    return out


@router.get("/api/v1/govt/procurement-centers")
def procurement_centers(
    lat: float = DEFAULT_LAT,
    lon: float = DEFAULT_LON,
    crop: Optional[str] = None,
    u=Depends(_get_user()),
):
    c = _conn()
    rows = c.execute("SELECT * FROM govt_procurement_centers").fetchall()
    c.close()
    out = []
    for r in rows:
        item = dict(r)
        item["distance_km"] = haversine_km(lat, lon, r["lat"], r["lon"])
        if crop and crop.lower() not in (r["crops"] or "").lower():
            item["crop_match"] = False
        else:
            item["crop_match"] = True
        out.append(item)
    out.sort(key=lambda x: (0 if x["crop_match"] else 1, x["distance_km"]))
    return out


def _write_token_pdf(path: str, data: dict) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from reportlab.lib import colors

    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("KisanSetu", styles["Title"]),
        Paragraph("Government MSP Procurement Token", styles["Heading2"]),
        Spacer(1, 8),
        Paragraph(
            "Pre-filled registration token for FCI / State Mandi procurement. "
            "This is a prototype document for SIH demonstration.",
            styles["Normal"],
        ),
        Spacer(1, 12),
    ]
    table = Table(
        [
            ["Token", data["token_code"]],
            ["Farmer", data["farmer_name"]],
            ["Crop", data["crop"]],
            ["Grade", data["quality_grade"]],
            ["Quantity (kg)", str(data["quantity_kg"])],
            ["Centre", data["center_name"]],
            ["Agency", data["agency"]],
            ["District", data["district"]],
            ["Issued", data["created_at"]],
        ],
        colWidths=[55 * mm, 110 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e9f6ee")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cfe2d6")),
                ("PADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(table)
    doc.build(story)


@router.post("/api/v1/govt/procurement-token")
def procurement_token(body: ProcurementTokenIn, u=Depends(_get_user())):
    _require(u, "farmer", "admin")
    c = _conn()
    center = c.execute(
        "SELECT * FROM govt_procurement_centers WHERE center_id=?",
        (body.center_id,),
    ).fetchone()
    if not center:
        c.close()
        raise HTTPException(404, "Procurement centre not found")
    token_code = f"MSP-{body.center_id:03d}-{u['id']:04d}-{secrets.token_hex(3).upper()}"
    pdf_name = f"{token_code}.pdf"
    pdf_path = os.path.join(TOKEN_DIR, pdf_name)
    farmer_name = u.get("name") or c.execute("SELECT name FROM users WHERE id=?", (u["id"],)).fetchone()["name"]
    payload = {
        "token_code": token_code,
        "farmer_name": farmer_name,
        "crop": body.crop,
        "quality_grade": body.quality_grade.upper(),
        "quantity_kg": body.quantity_kg,
        "center_name": center["name"],
        "agency": center["agency"],
        "district": center["district"],
        "created_at": _now(),
    }
    _write_token_pdf(pdf_path, payload)
    c.execute(
        """INSERT INTO govt_procurement_tokens
           (farmer_id, center_id, crop, quality_grade, quantity_kg, token_code, pdf_path, created_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            u["id"],
            body.center_id,
            body.crop,
            body.quality_grade.upper(),
            body.quantity_kg,
            token_code,
            pdf_name,
            payload["created_at"],
        ),
    )
    c.commit()
    c.close()
    print(f"[MSP-API] procurement token {token_code} issued")
    return {
        **payload,
        "pdf_url": f"/api/v1/govt/procurement-token/{token_code}/pdf",
        "portal_url": center["portal_url"],
    }


@router.get("/api/v1/govt/procurement-token/{token_code}/pdf")
def download_token_pdf(token_code: str, u=Depends(_get_user())):
    path = os.path.join(TOKEN_DIR, f"{token_code}.pdf")
    if not os.path.isfile(path):
        raise HTTPException(404, "Token PDF not found")
    return FileResponse(path, media_type="application/pdf", filename=f"{token_code}.pdf")
