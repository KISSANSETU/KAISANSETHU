# GRAM AI / KisanSetu V3 — SIH Integrated Prototype

## Farmer
- Dashboard: Today's Income, total income, open offers, GramPoints and a single plain-language Today's Recommendation. Removed the four SELL/WAIT/SHIFT/STORE dashboard cards.
- Crops & Forecasts: harvest history/open-for-buyers state; verified crop publishing requires live GPS + live camera/photo + automatic quality inspection first; token money, transport rate/radius and buyer visibility are stored. 1/3/7 day forecasts, final recommendation, trend chart, net-income chart and Maharashtra market-by-market predictions are displayed.
- Market & Offers: buyer pitch, buyer trust data, View details, Wait, Decline, Accept, Negotiate and Chat.
- Pre-orders: full AI advice, 1/3/7 prices, transport/market costs, fair range and token. Farmer acceptance moves to AWAITING_TOKEN; buyer must complete verified token payment before final ACCEPTED status.
- Transport & Groups: current transport requests, verified transport options, shared route option and collective selling groups.
- Payments & Rewards: secure transaction/refund monitoring, redeemable reward catalogue, transport cashback/fee waiver/priority matching, expiry dates, cancellation-health messaging.
- Profile: contact/address/farm data, masked payout details, KYC + live selfie. New users are marketplace-gated until KYC is verified. Demo Farmer/Buyer are pre-verified only for SIH demo flow.
- Feedback: after-order farmer/buyer/transport feedback plus platform requirements.
- Grievances: GramRakshak complaint creation, voice input and photo/video/PDF evidence.
- Link India: all-India seller map and profiles; Maharashtra selling remains the primary portal context.
- Chats: buyer/farmer conversation threads, negotiation messages and voice input.

## Buyer
- Dashboard: area, purchases, spend, pre-orders, GramPoints, order tracking and recommendations.
- Discover Harvest: Maharashtra listings/upcoming harvests with quality status, farmer KYC status, certificate, quantity, location, price, transport cost/radius and actions to order/negotiate/chat/pre-order.
- Pre-orders: farmer decision status, AI fair range, 1/3/7 forecast, token and secure token payment activation.
- My Orders: order totals, logistics, tracking history and complaint entry.
- Bulk & Shared Logistics: buyer purchase pools, nearby buyer network and spare-capacity transport concept.
- Rewards/Profile/Feedback/Grievances/Connect Buyers/Chats are role-specific.

## Admin
- Dashboard: verified payment revenue, farmer/buyer counts, pending KYC, grievances and risk.
- Users & KYC: masked KYC, live-photo status, Verify KYC, Warn/Block/Unblock/Terminate and direct admin message.
- Markets: market data, farmer/buyer details and charts.
- Payments: expected/confirmed amount, signature, webhook, status and refund.
- Grievances: status/severity/AI-assisted resolution and risk alerts.
- State Analytics: state selector (Maharashtra default) and graphs.
- Feedback & Requirements: review and message users.

## Multilingual
24 selectable language packs are available. Role navigation is language-bound across all 24. Main operational screens, graph titles and core actions use the translation-key layer; Marathi/Hindi/Tamil/Telugu have the deepest prototype translations. GRAM Saathi and speech-recognition locale switch with the selected language. Names, mandi names and authoritative database values are not machine-translated.

## YOLO honesty
`models/crop_grade.pt` is the expected trained Grade_A/Grade_B/Grade_C Ultralytics classification weight. If it is absent, the included `yolo11n-cls.pt` is used only as a **demo YOLO image-validation component** plus an explicitly labelled image-quality heuristic fallback. Do not claim validated agricultural Grade A/B/C accuracy until `train_yolo.py` has produced trained crop-grade weights.

## Run
```powershell
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python seed.py
python migrate_quality.py
python -m uvicorn app:app --reload
```
Open http://127.0.0.1:8000 and hard refresh once (Ctrl+Shift+R).
