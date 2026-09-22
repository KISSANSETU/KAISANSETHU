"""SQLite schema + demo seed for the MSP Distress module.

Tables are created with IF NOT EXISTS so existing KisanSetu
databases are never wiped. Safe to call on every API startup.
"""
from __future__ import annotations

import sqlite3
from typing import Optional

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS msp_baseline_rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    crop_id INTEGER,
    crop TEXT NOT NULL,
    msp_price_per_kg REAL NOT NULL,
    effective_year INTEGER NOT NULL,
    season TEXT NOT NULL DEFAULT 'KHARIF',
    UNIQUE(crop, effective_year, season)
);

CREATE TABLE IF NOT EXISTS distress_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    farmer_id INTEGER NOT NULL,
    crop_id INTEGER,
    crop TEXT NOT NULL,
    local_mandi_price REAL NOT NULL,
    dynamic_floor_calculated REAL NOT NULL,
    p_msp REAL NOT NULL DEFAULT 0,
    quality_grade TEXT NOT NULL DEFAULT 'B',
    status TEXT NOT NULL DEFAULT 'OPEN',
    district TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cold_storage_facilities (
    facility_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    partner TEXT NOT NULL DEFAULT '',
    district TEXT NOT NULL,
    state TEXT NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    daily_rate_per_kg REAL NOT NULL,
    capacity_kg REAL NOT NULL DEFAULT 50000,
    phone TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS cold_storage_bookings (
    booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
    farmer_id INTEGER NOT NULL,
    facility_id INTEGER NOT NULL,
    crop TEXT NOT NULL,
    quality_grade TEXT NOT NULL DEFAULT 'B',
    quantity_kg REAL NOT NULL,
    days_booked INTEGER NOT NULL,
    daily_rate_per_kg REAL NOT NULL,
    logistics_per_kg REAL NOT NULL DEFAULT 0,
    f_dynamic REAL NOT NULL,
    dwr_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'DEPOSITED',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS distress_reverse_listings (
    listing_id INTEGER PRIMARY KEY AUTOINCREMENT,
    farmer_id INTEGER NOT NULL,
    crop TEXT NOT NULL,
    quality_grade TEXT NOT NULL DEFAULT 'B',
    quantity_kg REAL NOT NULL,
    origin_district TEXT NOT NULL DEFAULT '',
    origin_state TEXT NOT NULL DEFAULT '',
    lat REAL,
    lon REAL,
    f_dynamic REAL NOT NULL,
    min_bid_per_kg REAL NOT NULL,
    p_msp_quality REAL NOT NULL,
    logistics_per_kg REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'OPEN',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS distress_reverse_bids (
    bid_id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id INTEGER NOT NULL,
    buyer_id INTEGER NOT NULL,
    bid_per_kg REAL NOT NULL,
    buyer_district TEXT NOT NULL DEFAULT '',
    logistics_per_kg REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'OFFERED',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS govt_procurement_centers (
    center_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    agency TEXT NOT NULL,
    district TEXT NOT NULL,
    state TEXT NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    crops TEXT NOT NULL DEFAULT '',
    portal_url TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS dwr_loans (
    loan_id INTEGER PRIMARY KEY AUTOINCREMENT,
    farmer_id INTEGER NOT NULL,
    booking_id INTEGER NOT NULL,
    dwr_hash TEXT NOT NULL,
    crop_value REAL NOT NULL,
    ltv REAL NOT NULL,
    advance_amount REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'OFFERED',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS govt_procurement_tokens (
    token_id INTEGER PRIMARY KEY AUTOINCREMENT,
    farmer_id INTEGER NOT NULL,
    center_id INTEGER NOT NULL,
    crop TEXT NOT NULL,
    quality_grade TEXT NOT NULL,
    quantity_kg REAL NOT NULL,
    token_code TEXT NOT NULL,
    pdf_path TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
"""

# Demo MSP floors in ₹/kg (GOI MSP ₹/qtl ÷ 100, plus horticulture safety floors).
MSP_SEED = [
    ("Wheat", 22.75, 2025, "RABI"),
    ("Rice", 23.00, 2025, "KHARIF"),
    ("Maize", 20.90, 2025, "KHARIF"),
    ("Soybean", 48.92, 2025, "KHARIF"),
    ("Groundnut", 63.77, 2025, "KHARIF"),
    ("Cotton", 71.21, 2025, "KHARIF"),
    ("Turmeric", 85.00, 2025, "KHARIF"),
    ("Chilli", 100.00, 2025, "KHARIF"),
    ("Tomato", 24.00, 2025, "RABI"),
    ("Onion", 22.00, 2025, "RABI"),
    ("Potato", 20.00, 2025, "RABI"),
    ("Banana", 35.00, 2025, "KHARIF"),
]

COLD_STORAGE_SEED = [
    ("Pune Agro Cold Chain", "Maharashtra Cold Partners", "Pune", "Maharashtra", 18.5204, 73.8567, 0.35, 80000, "020-2550-1101"),
    ("Nashik Onion CA Store", "Nashik FPO Cold Hub", "Nashik", "Maharashtra", 19.9975, 73.7898, 0.28, 120000, "0253-246-2200"),
    ("Nagpur Orange Belt Store", "Vidarbha Warehousing", "Nagpur", "Maharashtra", 21.1458, 79.0882, 0.32, 60000, "0712-254-3300"),
    ("Solapur Dry Belt Store", "Solapur APMC Partner", "Solapur", "Maharashtra", 17.6599, 75.9064, 0.30, 50000, "0217-274-4400"),
    ("Ahmedabad Packhouse", "Gujarat Cold Grid", "Ahmedabad", "Gujarat", 23.0225, 72.5714, 0.40, 70000, "079-2658-5500"),
]

PROCUREMENT_SEED = [
    ("FCI Pune District Office", "FCI", "Pune", "Maharashtra", 18.5310, 73.8440, "Wheat,Rice,Maize", "https://fci.gov.in", "020-2612-7000"),
    ("MahaFPC MSP Procurement — Pune", "State Mandi / MahaFPC", "Pune", "Maharashtra", 18.5074, 73.8077, "Onion,Soybean,Tomato", "https://mahapmcs.org", "020-2550-2211"),
    ("FCI Nashik Depot", "FCI", "Nashik", "Maharashtra", 19.9975, 73.7898, "Wheat,Onion,Maize", "https://fci.gov.in", "0253-257-1100"),
    ("MSWC Nagpur Procurement Yard", "State Warehousing", "Nagpur", "Maharashtra", 21.1458, 79.0882, "Soybean,Cotton,Rice", "https://mswc.in", "0712-256-8800"),
    ("FCI Ludhiana", "FCI", "Ludhiana", "Punjab", 30.9010, 75.8573, "Wheat,Rice,Maize", "https://fci.gov.in", "0161-244-2000"),
    ("FCI Ahmedabad", "FCI", "Ahmedabad", "Gujarat", 23.0225, 72.5714, "Wheat,Groundnut,Cotton", "https://fci.gov.in", "079-2325-0100"),
]


def init_msp_schema(db_path: str, crop_lookup: Optional[dict] = None) -> None:
    """Create tables and seed demo MSP / facility rows if empty."""
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA_SQL)
    crop_lookup = crop_lookup or {}

    if c.execute("SELECT COUNT(*) n FROM msp_baseline_rates").fetchone()["n"] == 0:
        for crop, price, year, season in MSP_SEED:
            crop_id = crop_lookup.get(crop)
            try:
                if crop_id is None:
                    row = c.execute("SELECT id FROM crops WHERE name=?", (crop,)).fetchone()
                    crop_id = row["id"] if row else None
            except sqlite3.OperationalError:
                crop_id = crop_id
            c.execute(
                """INSERT INTO msp_baseline_rates
                   (crop_id, crop, msp_price_per_kg, effective_year, season)
                   VALUES (?,?,?,?,?)""",
                (crop_id, crop, price, year, season),
            )
        print("[MSP-SCHEMA] Seeded msp_baseline_rates")

    if c.execute("SELECT COUNT(*) n FROM cold_storage_facilities").fetchone()["n"] == 0:
        c.executemany(
            """INSERT INTO cold_storage_facilities
               (name, partner, district, state, lat, lon, daily_rate_per_kg, capacity_kg, phone)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            COLD_STORAGE_SEED,
        )
        print("[MSP-SCHEMA] Seeded cold_storage_facilities")

    if c.execute("SELECT COUNT(*) n FROM govt_procurement_centers").fetchone()["n"] == 0:
        c.executemany(
            """INSERT INTO govt_procurement_centers
               (name, agency, district, state, lat, lon, crops, portal_url, phone)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            PROCUREMENT_SEED,
        )
        print("[MSP-SCHEMA] Seeded govt_procurement_centers")

    c.commit()
    c.close()
    print("[MSP-SCHEMA] Distress tables ready")
