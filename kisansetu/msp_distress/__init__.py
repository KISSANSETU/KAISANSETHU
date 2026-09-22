"""KisanSetu Distress Redressal & Dynamic MSP Floor — portable package.

Import the router only when wiring FastAPI so unit tests can run without
the web stack:

    from msp_distress.api import router
    from msp_distress import FRONTEND_DIR
"""
from pathlib import Path

from .distress_engine import (
    dynamic_msp_floor,
    evaluate_floor,
    quality_multiplier,
)
from .schema import init_msp_schema

FRONTEND_DIR = str(Path(__file__).resolve().parent / "frontend")


def __getattr__(name):
    if name == "router":
        from .api import router
        return router
    raise AttributeError(name)


__all__ = [
    "router",
    "FRONTEND_DIR",
    "dynamic_msp_floor",
    "evaluate_floor",
    "quality_multiplier",
    "init_msp_schema",
]
