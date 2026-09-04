# GRAM AI SIH Architecture

```text
Farmer / Buyer / Admin
        │
        ├── 24-Language UI + selected-language voice input
        │
        ├── JWT Role-Based Access
        │      └── Masked KYC / Aadhaar-ready verification
        │
        ├── Maharashtra-first State Context
        │      └── scalable state selector
        │
        ├── Farmer Intelligence
        │      ├── existing XGBoost + LightGBM 1/3/7-day forecast
        │      ├── Net Realizable Price logic
        │      ├── SELL / WAIT / SHIFT / STORE UX
        │      └── YOLO-ready A/B/C quality verification
        │
        ├── Market Linkage
        │      ├── Upcoming harvests
        │      ├── Partial pre-orders
        │      ├── AI fair negotiation range
        │      ├── Buyer reliability
        │      ├── FPO/group selling
        │      └── Transport & demand heatmaps
        │
        ├── Razorpay Test Payment Layer
        │      ├── backend authoritative amount
        │      ├── client signature verification
        │      ├── webhook verification
        │      ├── reconciliation
        │      └── overpayment refund tracking
        │
        ├── GramRewards / Trust
        │      └── transparent event ledger + adaptive deposit rules
        │
        └── GramRakshak
               ├── voice/text complaint
               ├── linked order/payment evidence
               ├── evidence hashes
               ├── severity + SLA escalation
               ├── risk alerts
               └── admin heatmaps
```

Legacy routes/tables remain in place. New features are added in `innovation_api.py` under `/api/v2/*` and new tables are created with `CREATE TABLE IF NOT EXISTS`.
