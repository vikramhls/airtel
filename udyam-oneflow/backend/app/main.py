"""Udyam OneFlow API. Run: uvicorn app.main:app --reload --port 8000 (from backend/)."""
from __future__ import annotations

import logging
import threading

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import config, db
from app.dataio import data_counts
from app.routers import advisor, catalogue, checkout, kyc, orders, partner, quote
from app.services import llm, propensity
from app.services.kyc import service as kyc_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
app = FastAPI(title="Udyam OneFlow API", version="1.0",
              description="Accel Business advisor, quote, Smart KYC, tracker and partner cockpit (synthetic data).")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])

for module in (advisor, catalogue, quote, checkout, kyc, orders, partner):
    app.include_router(module.router, prefix="/api")


@app.exception_handler(StarletteHTTPException)
async def http_problem(_: Request, exc: StarletteHTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "HTTP_ERROR", "message": str(exc.detail),
                                                              "fix_hint": None}
    return JSONResponse(status_code=exc.status_code, content=detail)


@app.exception_handler(RequestValidationError)
async def validation_problem(_: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    return JSONResponse(status_code=422, content={
        "code": "VALIDATION_ERROR", "message": "Some request fields are missing or invalid.",
        "fix_hint": f"{'.'.join(str(p) for p in first.get('loc', []))}: {first.get('msg', '')}"})


@app.on_event("startup")
def startup() -> None:
    db.connect()

    def warm() -> None:   # first LLM call and first model score are the slow ones; pay that cost now
        try:
            propensity.calibration()
        except Exception:
            logging.getLogger(__name__).warning("propensity warm-up skipped")
        llm.warmup()

    threading.Thread(target=warm, daemon=True).start()


@app.get("/api/health")
def health():
    model = propensity.metrics()
    return {"status": "ok", "reference_date": config.REFERENCE_DATE.isoformat(), "rows": data_counts(),
            "llm": llm.status(), "ocr": kyc_service.status(),
            "model": {"available": propensity.available(),
                      "cv_roc_auc_lr": model.get("cv_5fold", {}).get("lr", {}).get("roc_auc_mean"),
                      "oof_blended_auc": model.get("oof_blended_auc")}}


# Serve the built frontend (frontend/dist) from the same port when it exists.
DIST = config.BACKEND_DIR.parent / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        target = DIST / path
        if path and target.is_file():
            return FileResponse(target)
        return FileResponse(DIST / "index.html")
