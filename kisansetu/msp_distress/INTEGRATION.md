# MSP Distress Redressal — integration pack

Copy this entire `msp_distress/` folder into another KisanSetu / FastAPI project. It does **not** replace existing routes, tables, or UI. Host apps only add a router, a static mount, and a small dashboard hook.

## What you get

| File | Role |
|---|---|
| `distress_engine.py` | Pure math: `F_dynamic = P_MSP × Q_m + storage + logistics` |
| `schema.py` | SQLite tables + demo MSP / cold-store / FCI seed |
| `api.py` | FastAPI routes under `/api/v1/...` |
| `frontend/msp_distress.js` | Banner, 3 pathway cards, floor visualizer |
| `frontend/msp_distress.css` | Scoped `.msp-*` styles |
| `test_distress_engine.py` | Grade A/B/C, zero storage days, transport, bid floor |

## 1. Backend (FastAPI)

```python
from fastapi.staticfiles import StaticFiles
    from msp_distress.api import router as msp_distress_router
    from msp_distress import FRONTEND_DIR

app.include_router(msp_distress_router)
app.mount("/msp-distress", StaticFiles(directory=FRONTEND_DIR), name="msp_distress")
```

Place the package next to `app.py` (same folder as this project's `chagpt/msp_distress`).

Auth is reused from the host `app.user` dependency (JWT). Tables are created with `CREATE TABLE IF NOT EXISTS` on first import.

## 2. Frontend

In your HTML shell:

```html
<link rel="stylesheet" href="/msp-distress/msp_distress.css">
<script src="/msp-distress/msp_distress.js"></script>
```

Host page must already define `api()`, `toast()`, `esc()`, `fmt()`, `$`, and `me` (this repo's `static/app.js` already does).

Farmer dashboard (append only):

```javascript
$('content').innerHTML = existingHtml + '<div id="mspDistressMount"></div>';
if (window.MSPDistress) MSPDistress.mountDashboard('mspDistressMount');
```

Dedicated page:

```javascript
if (k === 'mspDistress') {
  return me.role === 'buyer' ? MSPDistress.renderBuyerPage() : MSPDistress.renderFarmerPage();
}
```

Add a nav item `['mspDistress','🛡']`.

## 3. API contract

- `POST /api/v1/distress/evaluate` — `crop` or `crop_id`, `quantity`, `quality_grade`, `lat`/`lon` → `is_distress`, `P_forecast`, `P_MSP`, `F_dynamic`, `pathways`
- `POST /api/v1/marketplace/reverse-bid/distress-list` — min bid locked to `F_dynamic`
- `POST /api/v1/marketplace/reverse-bid/{id}/bid` — **400 if bid < F_dynamic**
- `POST /api/v1/cold-storage/book` — e-DWR hash + updated floor
- `POST /api/v1/finance/dwr-loan` — mock 70% advance
- `GET /api/v1/govt/procurement-centers` — nearest FCI / state yards
- `POST /api/v1/govt/procurement-token` — pre-filled PDF token

Quality multipliers: Grade A `1.10`, B `1.00`, C `0.85`.

## 4. Tests

From the folder that contains `msp_distress` (here: `chagpt/`):

```powershell
python -m unittest msp_distress.test_distress_engine -v
```
