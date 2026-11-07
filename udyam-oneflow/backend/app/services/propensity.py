"""Lead intelligence from the trained models (scripts/train_propensity.py).

* Existing 5,000 leads: out-of-fold scores from reports/lead_scores.csv, so no
  lead is scored by a model that saw its own outcome.
* Live advisor sessions: the saved logistic model (models/propensity.joblib) on
  the same leak-safe features, calibrated to the 7.36% base rate, with its top
  contributing features as plain-language reasons; models/mrr.joblib predicts
  monthly value for the expected-value ranking.
Feature engineering is imported from the training script so the two can't drift.
"""
from __future__ import annotations

import importlib.util
import json
import warnings
from functools import lru_cache

import numpy as np
import pandas as pd

from app import config
from app.dataio import SEGMENT_NAME, catalogue_frame, gstin_frame, leads_frame, udyam_frame
from app.schemas import BusinessProfile

SCRIPT = config.BACKEND_DIR.parent / "scripts" / "train_propensity.py"

REASON_TEXT = {
    "lead_source": "came via {v}", "segment": "{v}", "business_type": "is a {v}", "city": "is in {v}",
    "city_tier": "tier-{v} city", "preferred_language": "prefers {v}", "annual_turnover_band": "turnover {v}",
    "has_gstin": "GSTIN: {v}", "has_udyam": "Udyam: {v}", "current_internet": "uses {v} today",
    "current_provider": "current provider {v}", "contact_role": "contact is {v}", "gst_status": "GST status {v}",
    "constitution": "{v}", "employee_count": "team size", "num_sites": "number of sites",
    "monthly_telecom_spend_inr": "current telecom spend", "n_poi": "number of products asked about",
    "poi_min_cost": "value of products asked about", "poi_max_cost": "value of products asked about",
    "spend_per_site": "spend per site", "spend_per_emp": "spend per employee",
    "poi_cost_to_spend": "ask vs current spend", "gst_age_days": "age of GST registration",
    "udyam_age_days": "age of Udyam registration",
}


@lru_cache(maxsize=1)
def _train_module():
    spec = importlib.util.spec_from_file_location("train_propensity", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


@lru_cache(maxsize=1)
def _models():
    import joblib

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        lr = joblib.load(config.MODELS_DIR / "propensity.joblib")
        mrr = joblib.load(config.MODELS_DIR / "mrr.joblib")
    return lr, mrr


@lru_cache(maxsize=1)
def _frames():
    leads = pd.read_csv(config.DATA_DIR / "smb_leads.csv", parse_dates=["created_date"])
    cat = pd.read_csv(config.DATA_DIR / "product_catalogue.csv")
    gst = pd.read_csv(config.DATA_DIR / "mock_gstin_registry.csv", parse_dates=["registration_date"])
    udy = pd.read_csv(config.DATA_DIR / "mock_udyam_registry.csv", parse_dates=["date_of_registration"])
    return leads, cat, gst, udy


@lru_cache(maxsize=1)
def calibration() -> dict:
    """Class-weighted LR inflates probabilities; rescale so mean score == base rate
    (the same correction the training script applies to its blended score)."""
    leads, cat, gst, udy = _frames()
    _, X = _train_module().features(leads, cat, gst, udy)
    lr, _ = _models()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        p = lr.predict_proba(X)[:, 1]
    base = float((leads.outcome == "Activated").mean())
    churn = float((leads.loc[leads.outcome == "Activated", "churned_within_6_months"] == "Y").mean())
    return {"factor": base / float(p.mean()), "base_rate": base, "retention": 1 - churn,
            "p33": float(np.quantile(p * base / p.mean(), 0.33)), "p67": float(np.quantile(p * base / p.mean(), 0.67))}


def available() -> bool:
    return (config.MODELS_DIR / "propensity.joblib").exists() and SCRIPT.exists()


def metrics() -> dict:
    path = config.REPORTS_DIR / "propensity.json"
    return json.loads(path.read_text()) if path.exists() else {}


def _row_from_profile(profile: BusinessProfile, source: str, lang: str) -> pd.DataFrame:
    seg = SEGMENT_NAME.get(profile.segment or "micro", "Micro retail & services")
    interest = ";".join(profile.requested_products)
    return pd.DataFrame([{
        "lead_id": "LIVE", "created_date": pd.Timestamp(config.REFERENCE_DATE), "lead_source": source,
        "business_name": profile.business_name or "", "business_type": profile.business_type or "",
        "segment": seg, "city": profile.city or "", "city_tier": profile.city_tier or 1, "state": profile.state or "",
        "preferred_language": {"hi": "Hindi", "ta": "Tamil"}.get(lang, "English"),
        "employee_count": profile.employees or 1, "num_sites": profile.sites or 1,
        "annual_turnover_band": "Missing", "has_gstin": "Y" if profile.has_gstin else "N",
        "gstin": profile.gstin or "", "has_udyam": "Y" if profile.has_udyam else "N",
        "udyam_number": profile.udyam_number or "", "current_internet": profile.current_internet or "Missing",
        "current_provider": profile.current_provider or "Missing",
        "monthly_telecom_spend_inr": profile.current_spend_inr or np.nan,
        "products_of_interest": interest, "contact_role": "Owner",
    }])


def score_profile(profile: BusinessProfile, source: str = "Website form", lang: str = "en") -> dict | None:
    """Live score for an advisor session (0-100), reasons, predicted MRR and routing."""
    if not available():
        return None
    _, cat, gst, udy = _frames()
    row = _row_from_profile(profile, source, lang)
    _, X = _train_module().features(row, cat, gst, udy)
    lr, mrr_model = _models()
    cal = calibration()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        p = float(np.clip(lr.predict_proba(X)[:, 1][0] * cal["factor"], 0, 1))
        mrr = float(np.expm1(mrr_model.predict(X)[0]))
        pre, clf = lr.named_steps["p"], lr.named_steps["m"]
        z = pre.transform(X)
        z = z.toarray() if hasattr(z, "toarray") else z
    contrib = z[0] * clf.coef_[0]
    names = pre.get_feature_names_out()
    order = np.argsort(-np.abs(contrib))
    reasons = []
    for j in order[:4]:
        if abs(contrib[j]) < 0.05:
            continue
        reasons.append({"feature": _pretty(names[j]), "effect": "raises" if contrib[j] > 0 else "lowers",
                        "weight": round(float(contrib[j]), 3)})
    return {"score": round(p * 100, 1), "probability": round(p, 4), "pred_mrr_inr": round(mrr),
            "expected_annual_value_inr": round(p * mrr * 12 * cal["retention"]),
            "routing": route(p, profile), "reasons": reasons[:3],
            "model": "logistic regression (scripts/train_propensity.py), calibrated to base rate",
            "base_rate_pct": round(cal["base_rate"] * 100, 2)}


def _pretty(feature: str) -> str:
    name = feature.split("__", 1)[-1]
    if name.startswith("missingindicator_"):
        base = name[len("missingindicator_"):]
        return {"gst_age_days": "no GST registration on file", "udyam_age_days": "no Udyam registration on file",
                "monthly_telecom_spend_inr": "current spend unknown"}.get(base, f"{base} unknown")
    for col, template in REASON_TEXT.items():
        if name == col:
            return template.replace("{v}", "").strip()
        if name.startswith(col + "_"):
            return template.format(v=name[len(col) + 1:])
    return name


def route(p: float, profile: BusinessProfile) -> str:
    """Action chips for the cockpit (docs/08 section 3)."""
    cal = calibration()
    complex_ = profile.segment in ("multi", "mfg")
    if not profile.has_gstin and p < cal["p67"]:
        return "GST help first"
    if p >= cal["p67"] and complex_:
        return "Assisted visit"
    if p >= cal["p67"]:
        return "Self-serve link"
    if p >= cal["p33"]:
        return "Call now"
    return "WhatsApp link, not call"


ROUTE_ACTION = {
    "1. Field Sales VIP (high propensity + high value)": "Assisted visit",
    "2. Channel partner assisted": "Assisted visit",
    "3. Self-serve link (fast track)": "Self-serve link",
    "4. GST help first (unlock path)": "GST help first",
    "5. Nurture via WhatsApp link (low touch)": "WhatsApp link, not call",
}


@lru_cache(maxsize=1)
def lead_scores() -> pd.DataFrame:
    path = config.REPORTS_DIR / "lead_scores.csv"
    df = pd.read_csv(path)
    leads = leads_frame()[["lead_id", "stage_reached", "drop_reason", "current_provider",
                           "monthly_telecom_spend_inr", "employee_count", "num_sites"]]
    df = df.merge(leads, on="lead_id", how="left")
    df["action"] = df["routing"].map(ROUTE_ACTION).fillna("Call now")
    df["reasons"] = df["reasons"].fillna("").map(
        lambda s: [_pretty("x__" + r.strip()) for r in s.split(";") if r.strip()])
    return df


def leads_queue(min_score: float = 0, segment: str | None = None, action: str | None = None,
                open_only: bool = False, limit: int = 100, offset: int = 0, sort: str = "value") -> dict:
    df = lead_scores()
    if min_score:
        df = df[df["propensity"] >= min_score]
    if segment:
        df = df[df["segment"].str.lower().str.contains(segment.lower())]
    if action:
        df = df[df["action"] == action]
    if open_only:
        df = df[df["outcome"] != "Activated"]
    key = "expected_annual_value_inr" if sort == "value" else "propensity"
    df = df.sort_values(key, ascending=False)
    page = df.iloc[offset: offset + limit]
    rows = json.loads(page.to_json(orient="records"))
    return {"total": int(len(df)), "rows": rows,
            "note": "Scores are out-of-fold (5-fold CV): no lead was scored by a model trained on its own outcome."}


def lead_detail(lead_id: str) -> dict | None:
    df = lead_scores()
    hit = df[df["lead_id"] == lead_id]
    if hit.empty:
        return None
    row = json.loads(hit.iloc[0:1].to_json(orient="records"))[0]
    raw = leads_frame()
    lead = raw[raw["lead_id"] == lead_id].iloc[0].to_dict()
    from app.utils.mask import mask_gstin, mask_udyam

    row["profile"] = {k: lead.get(k) for k in ("business_type", "city", "city_tier", "preferred_language",
                                                "employee_count", "num_sites", "has_gstin", "products_of_interest",
                                                "current_internet", "current_provider")}
    row["profile"]["gstin"] = mask_gstin(lead.get("gstin"))
    row["profile"]["udyam_number"] = mask_udyam(lead.get("udyam_number"))
    row["next_action"] = {
        "Assisted visit": "Book an assisted visit: multi-site or high value, worth a person's time.",
        "Self-serve link": "Send the OneFlow link on WhatsApp; this lead can finish on their own.",
        "GST help first": "Offer GST registration help first: it unlocks the GST-only products.",
        "WhatsApp link, not call": "Low propensity: send a WhatsApp link instead of calling.",
        "Call now": "Call today: average propensity, a short call can move it forward.",
    }[row["action"]]
    return row
