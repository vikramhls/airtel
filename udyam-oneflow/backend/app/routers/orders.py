from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app import config
from app.routers.common import problem, require_session
from app.services import orders

router = APIRouter(tags=["orders"])


class OrderIn(BaseModel):
    session_id: str
    quote_id: str


class AdvanceIn(BaseModel):
    days: int | None = None
    to_stage: str | None = None


class FailIn(BaseModel):
    reason: str = "ADDRESS_PROOF_EXPIRED"


class ResolveIn(BaseModel):
    action: str


def _found(order: dict | None) -> dict:
    if not order:
        raise problem(404, "ORDER_NOT_FOUND", "Order not found.", "Check the order ID in your confirmation message.")
    return order


@router.post("/orders")
def place(body: OrderIn):
    require_session(body.session_id)
    try:
        return orders.create(body.session_id, body.quote_id)
    except KeyError:
        raise problem(404, "QUOTE_NOT_FOUND", "Quote not found for this session.", "Build a quote first.")


@router.get("/orders/{order_id}")
def track(order_id: str):
    return _found(orders.get(order_id))


@router.get("/session/{session_id}/orders")
def session_orders(session_id: str):
    require_session(session_id)
    return orders.by_session(session_id)


@router.post("/orders/{order_id}/resolve")
def resolve(order_id: str, body: ResolveIn):
    if body.action not in ("recheck_kyc", "remove_gst_products", "reactivate_gstin"):
        raise problem(422, "BAD_ACTION", "Unknown action.", None)
    return _found(orders.resolve(order_id, body.action))


@router.post("/orders/{order_id}/help")
def help_request(order_id: str):
    return _found(orders.need_help(order_id))


def _admin() -> None:
    if not config.ADMIN_ENABLED:
        raise problem(403, "ADMIN_DISABLED", "Demo controls are off.", None)


@router.post("/admin/orders/{order_id}/advance")
def advance(order_id: str, body: AdvanceIn):
    _admin()
    return _found(orders.advance(order_id, body.days, body.to_stage))


@router.post("/admin/orders/{order_id}/fail")
def fail(order_id: str, body: FailIn):
    _admin()
    try:
        return _found(orders.fail(order_id, body.reason))
    except ValueError:
        raise problem(422, "BAD_REASON", "Unknown block reason.", ", ".join(orders.BLOCKS))
