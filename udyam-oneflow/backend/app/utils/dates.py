"""Date rules. Every function takes the reference date explicitly - business
logic never reads the wall clock."""
from __future__ import annotations

from datetime import date, timedelta

from app import config

ISO = "%Y-%m-%d"


def parse(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def days_between(a: date, b: date) -> int:
    return (a - b).days


def within_days(value: date | None, days: int, ref: date | None = None) -> bool:
    ref = ref or config.REFERENCE_DATE
    if value is None:
        return False
    age = (ref - value).days
    return 0 <= age <= days and age >= 0


def age_days(value: date | None, ref: date | None = None) -> int | None:
    ref = ref or config.REFERENCE_DATE
    if value is None:
        return None
    return (ref - value).days


def not_expired(value: date | None, ref: date | None = None) -> bool:
    ref = ref or config.REFERENCE_DATE
    if value is None:
        return False
    return value >= ref


def add_working_days(start: date, days: int) -> date:
    """Simple working-day arithmetic: Sundays are skipped (documented simplification)."""
    current = start
    remaining = max(days, 0)
    while remaining > 0:
        current += timedelta(days=1)
        if current.weekday() != 6:  # Sunday
            remaining -= 1
    return current


def demo_today(offset_days: int = 0) -> date:
    return config.REFERENCE_DATE + timedelta(days=offset_days)


def iso(value: date | None) -> str | None:
    return value.isoformat() if value else None
