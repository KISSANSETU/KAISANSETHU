"""India-wide crop market price comparison endpoint.

Wraps market_price_service.py's live AGMARKNET (data.gov.in) lookup behind a
single authenticated endpoint. The frontend never sees the API key.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from market_price_service import compare_prices, MarketPriceError

router = APIRouter(prefix="/api", tags=["GRAM AI Market Prices"])


def get_user_dep():
    # Late import mirrors chatbot_api/voice_api and avoids a circular import.
    from app import user
    return user


@router.get("/market-prices")
def market_prices(crop: str = "", u=Depends(get_user_dep())):
    crop = (crop or "").strip()
    if not crop:
        return JSONResponse(status_code=400, content={
            "success": False, "message": "Enter a crop name to search."})
    try:
        return compare_prices(crop)
    except MarketPriceError as e:
        status = 404 if str(e) == "No market data found for this crop." else 503
        return JSONResponse(status_code=status,
                             content={"success": False, "message": str(e)})
