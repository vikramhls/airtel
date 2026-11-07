"""Product catalogue: the single source of prices, terms, install days and rules."""
from __future__ import annotations

from dataclasses import dataclass

from app.dataio import catalogue_frame


def _ints(value: str) -> tuple[int, ...]:
    return tuple(int(p) for p in str(value).split(";") if str(p).strip())


def _ids(value: str) -> tuple[str, ...]:
    return tuple(p.strip() for p in str(value).split("|") if p.strip())


def _segs(value: str) -> tuple[str, ...]:
    return tuple(p.strip() for p in str(value).split(";") if p.strip())


@dataclass(frozen=True)
class Product:
    id: str
    category: str
    name: str
    description: str
    unit: str
    price_min: int
    price_max: int
    setup: int
    min_contract: int
    tiers: tuple[int, ...]
    min_employees: int
    min_sites: int
    requires_gstin: bool
    requires_one_of: tuple[str, ...]
    install_days: int
    segments: tuple[str, ...]

    @property
    def mid_price(self) -> int:
        return round((self.price_min + self.price_max) / 2)

    def band(self) -> tuple[int, int]:
        return (self.price_min, self.price_max)


_CACHE: tuple[Product, ...] | None = None


def all_products() -> tuple[Product, ...]:
    global _CACHE
    if _CACHE is None:
        items = []
        for row in catalogue_frame().itertuples(index=False):
            items.append(
                Product(
                    id=row.product_id.strip(),
                    category=row.category.strip(),
                    name=row.product_name.strip(),
                    description=row.description.strip(),
                    unit=row.unit.strip(),
                    price_min=int(row.price_min_inr_per_month),
                    price_max=int(row.price_max_inr_per_month),
                    setup=int(row.one_time_setup_inr),
                    min_contract=int(row.min_contract_months),
                    tiers=_ints(row.available_city_tiers),
                    min_employees=int(row.min_employees),
                    min_sites=int(row.min_sites),
                    requires_gstin=row.requires_gstin.strip().upper() == "Y",
                    requires_one_of=_ids(row.requires_one_of),
                    install_days=int(row.typical_install_days),
                    segments=_segs(row.target_segments),
                )
            )
        _CACHE = tuple(items)
    return _CACHE


def get(product_id: str) -> Product | None:
    pid = (product_id or "").strip().upper()
    for p in all_products():
        if p.id == pid:
            return p
    return None


def as_dict(p: Product) -> dict:
    return {
        "product_id": p.id,
        "category": p.category,
        "name": p.name,
        "description": p.description,
        "unit": p.unit,
        "price_min_inr_per_month": p.price_min,
        "price_max_inr_per_month": p.price_max,
        "one_time_setup_inr": p.setup,
        "min_contract_months": p.min_contract,
        "available_city_tiers": list(p.tiers),
        "min_employees": p.min_employees,
        "min_sites": p.min_sites,
        "requires_gstin": p.requires_gstin,
        "requires_one_of": list(p.requires_one_of),
        "typical_install_days": p.install_days,
        "target_segments": list(p.segments),
    }


def find_by_name(text: str) -> Product | None:
    """Resolve a human mention ('Fibre 100', 'whatsapp', 'CCTV') to a product."""
    low = (text or "").lower()
    if not low:
        return None
    best: tuple[int, Product] | None = None
    for p in all_products():
        tokens = [p.name.lower(), p.description.lower()]
        score = 0
        if p.name.lower() in low or p.id.lower() in low:
            score = 100
        elif p.name.lower().split("(")[0].strip() in low:
            score = 80
        else:
            for word in set(w.strip(",-()").lower() for w in p.name.split()):
                if len(word) >= 4 and word in low:
                    score += 10
        if score and (best is None or score > best[0]):
            best = (score, p)
    return best[1] if best else None
