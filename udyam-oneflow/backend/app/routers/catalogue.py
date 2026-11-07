from __future__ import annotations

from fastapi import APIRouter

from app.config import PRICING_POLICY
from app.dataio import cities
from app.services import catalogue
from app.services.segmenter import known_types

router = APIRouter(tags=["catalogue"])


@router.get("/catalogue")
def list_products():
    return {"products": [catalogue.as_dict(p) for p in catalogue.all_products()],
            "pricing_policy": {**PRICING_POLICY,
                               "rule": "term under 12 months: top of band; 12 months: midpoint; 24+ months: bottom of band"},
            "source": "product_catalogue.csv"}


@router.get("/meta")
def meta():
    return {"cities": cities(),
            "business_types": ["CA firm" if t == "ca firm" else t.capitalize() for t in known_types()]}
