# GRAM AI / KisanSetu — SIH 2026 Integrated Prototype

This build preserves the original FastAPI + SQLite + XGBoost/LightGBM + YOLO-ready project and adds a non-destructive `innovation_api.py` layer plus a simplified green-and-white role-based UI.

## What is integrated

### Role-based portals
- Login first asks: **Farmer / Buyer / Admin**.
- Farmer: Home, Crops & Forecasts, Market & Offers, Pre-Orders, Transport & Groups, Payments & Rewards, Help & Profile.
- Buyer: Home, Discover Harvests, Pre-Orders, Orders & Payments, Bulk & Logistics, Trust & Rewards, Help & Profile.
- Admin: Overview, Users & KYC, Markets & AI, Payments, Grievances & Risk, Analytics, Settings.
- Technical ML labels are hidden from normal farmer/buyer screens and shown only in admin/model monitoring.

### Maharashtra-first, pan-India-ready
- Maharashtra is the UI/API default state.
- State selector refreshes state-aware markets, buyers, harvests, transport, demand and analytics.
- Existing all-India seeded market data is retained.

### 24-language + voice architecture
- 24 selectable locale packs: English, the 22 Scheduled Languages, plus Rajasthani.
- Core navigation/actions change together with one global language setting.
- Web Speech API uses the selected locale for microphone input where the browser supports that language.
- Voice buttons are included in farmer harvest, feedback, grievance and chatbot flows.
- For production-grade translation/conversational coverage, connect an approved translation/LLM provider behind the same locale layer.

### AI Pre-Orders
- Farmers publish expected harvest crop, quantity, date and expected price.
- Buyers can pre-order partial quantities.
- Advice compares the offer with 1/3/7-day market outlook, costs, net farmer value and buyer reliability.
- Output: **ACCEPT / NEGOTIATE / WAIT**, fair negotiation range and trust-based deposit percentage.
- Farmer decides the pre-order.
- FPO/group selling tables and UI are included.
- Demand heatmap uses pre-order demand when available and falls back to market demand signals.

### GramRewards & Trust
- Reward ledger and transparent rules.
- Buyer reliability, harvest commitment, instant-payment score and zero-cancellation streak.
- Trust-based pre-order deposits.
- Estimated farmer income-improvement indicator.
- GramGuarantee is modeled as eligibility-based platform credits/fee waivers, not a guaranteed investment/market return.

### GramRakshak
- Farmer/buyer grievance records with linked order/payment IDs.
- Voice complaint transcript support.
- Photo/video/PDF evidence endpoint with SHA-256 evidence hashes.
- Rule/AI-assisted severity: Low / Medium / High / Critical.
- SLA due time and automatic escalation when overdue.
- Risk alerts for high-severity patterns.
- Admin grievance and risk dashboards plus district grievance heatmap.
- Satisfaction confirmation endpoint before final closure/reopen.

### KYC / Aadhaar-ready security
- KYC queue and admin decision workflow.
- **Never stores a full Aadhaar number.** Only last 4 digits, masking, consent and provider reference are stored in this prototype.
- This is **not live UIDAI authentication**. Production Aadhaar authentication/eKYC requires an authorised KUA/AUA/KSA or approved KYC provider.

### Razorpay Test Mode payment architecture
- Backend derives payable amount from the trusted order/pre-order database record.
- Frontend never supplies the authoritative payable amount.
- Client payment signature is verified on the backend.
- Razorpay webhook signature is independently verified.
- Payment becomes `SUCCESS` only when both client signature and webhook verification are complete.
- If confirmed gateway amount is greater than the backend expected amount, the difference is recorded as overpayment and a refund is initiated to the original gateway payment.
- Refund states: PROCESSING / REFUNDED / FAILED.
- Admin transaction/refund monitoring is included.
- Demo mode demonstrates the same state machine without real money.

## Important production warning

The included SQLite DB, demo OTP, test payments, seeded mandi data and local rule-based chatbot are SIH prototype components. For production, use a persistent database such as PostgreSQL, authoritative live market/weather data, a production SMS provider, trained/validated crop-quality weights, regulated payment credentials/webhooks and an authorised KYC provider.

## Run locally (Windows PowerShell)

```powershell
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python seed.py
python migrate_quality.py
python -m uvicorn app:app --reload
```

Starting `app` automatically creates the new SIH tables without deleting existing legacy tables.

Open:

```text
http://127.0.0.1:8000
```

Demo accounts:
- Farmer: `farmer@gram.ai` / `Farmer@123`
- Buyer: `buyer@gram.ai` / `Buyer@123`
- Admin: `admin@gram.ai` / `Admin@123`

## Razorpay test setup

Set environment variables (do not commit secrets):

```text
GRAMAI_PAYMENT_DEMO=0
RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=...
RAZORPAY_WEBHOOK_SECRET=...
```

Configure the Razorpay webhook endpoint to:

```text
POST https://YOUR-DOMAIN/api/v2/payments/webhook
```

Use Razorpay Test Mode credentials only for the SIH demo.

## YOLO note

`quality_model.py` expects a trained classification model at:

```text
models/crop_grade.pt
```

The included `yolo11n-cls.pt` is a generic pretrained classifier and must **not** be presented as a validated Grade A/B/C crop-quality model. Train your crop-grade dataset using `train_yolo.py`, validate it, then place the resulting best weights at `models/crop_grade.pt`.
