"""Unit checklist from docs/11 (engine, KYC rules, dates, masking, model, simulator)."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from app import config
from app.dataio import data_counts, gstin_frame
from app.schemas import BusinessProfile as P
from app.services import catalogue, pricing, propensity, simulator
from app.services.bundler import recommend
from app.services.kyc.validate import validate
from app.utils import gstin as g
from app.utils.mask import mask_gstin, mask_id, mask_payload, mask_udyam

APP = Path(__file__).resolve().parent.parent / "app"


def test_seed_counts():
    assert data_counts() == {"catalogue": 25, "leads": 5000, "gstin_registry": 3534, "udyam_registry": 2723}


def test_gstin_checksum_all_registry_rows():
    values = gstin_frame()["gstin"].tolist()
    assert len(values) == 3534 and all(g.checksum_ok(v) for v in values)
    flipped = values[0][:-1] + ("A" if values[0][-1] != "A" else "B")
    assert not g.checksum_ok(flipped)


def test_gstin_format():
    assert g.format_ok("32TTNXB7384T1ZW")            # X at position 6 accepted (synthetic)
    assert not g.format_ok("32TTNXB7384T1Z")         # wrong length
    assert not g.format_ok("32TTN1B7384T1ZW")


def _check(checks, code):
    return next(c for c in checks if c["code"] == code)


def test_udyam_requires_district_00():
    ok = validate({"udyam": {"fields": {"udyam_number": "UDYAM-KL-00-3078801"}}})
    bad = validate({"udyam": {"fields": {"udyam_number": "UDYAM-KL-12-3078801"}}})
    assert _check(ok, "UDYAM_FORMAT")["status"] == "pass"
    assert _check(bad, "UDYAM_FORMAT")["status"] == "fail"


def test_address_proof_90_day_edges():
    def status(d):
        return _check(validate({"address": {"fields": {"bill_date": d, "supply_address": "x", "billed_to": "y"}}}),
                      "ADDR_DATE_FRESH")["status"]
    assert status("2026-04-16") == "pass"
    assert status("2026-04-15") == "fail"
    assert status("2026-07-16") == "fail"   # future-dated


def test_id_validity_edges():
    def status(d):
        return _check(validate({"signatory_id": {"fields": {"valid_till": d, "id_no": "SYN-ID-123456"}}}),
                      "ID_NOT_EXPIRED")["status"]
    assert status("2026-07-15") == "pass"
    assert status("2026-07-14") == "fail"


def test_pricing_policy_and_totals():
    p01 = catalogue.get("P01")
    assert pricing.unit_price(p01, 12) == 1099 and pricing.unit_price(p01, 24) == 999
    assert pricing.unit_price(catalogue.get("P15"), 1) == 1499     # < 12 months -> top of band
    rec = recommend(P(business_type="Restaurant chain", city="Hyderabad", employees=40, sites=5, has_gstin=True,
                      gstin_status="Active", needs=["internet", "mobile", "billing_pos", "cctv"]))
    for rung in rec.ladder:
        assert rung.total_monthly == sum(i.unit_price * i.qty for i in rung.items)
        assert rung.total_setup == sum(i.setup_inr for i in rung.items)


def test_setup_per_qty_rules():
    p23 = catalogue.get("P23")
    assert pricing.setup_for(p23, 4) == 7200
    assert pricing.setup_for(catalogue.get("P13"), 1) == 1000          # per number: x1


def test_dependency_picks_cheapest_or_unlocks():
    rec = recommend(P(business_type="Kirana store", city="Chennai", employees=4, has_gstin=False, needs=["wifi"],
                      fibre_available=False))
    assert rec.trace["auto_added"][0]["product"] == "P04"


def test_ladder_climbs():
    rec = recommend(P(business_type="Dental clinic", city="Pune", employees=8, has_gstin=True, gstin_status="Active",
                      needs=["internet", "mobile"], current_spend_inr=2500))
    totals = [r.total_monthly for r in rec.ladder]
    assert totals[0] < totals[1] < totals[2]
    start_ids = {i.product_id for i in rec.ladder[0].items}
    assert all(i.product_id in {x.product_id for x in rec.ladder[1].items} for i in rec.ladder[0].items)
    assert all(not i.is_addon for i in rec.ladder[0].items) and start_ids == {"P01", "P07"}


def test_masking():
    assert mask_gstin("32TTNXB7384T1ZW") == "32" + "•" * 10 + "1ZW"
    assert "3078801" not in mask_udyam("UDYAM-KL-00-3078801")
    assert "123456" not in mask_id("SYN-ID-123456")
    out = json.dumps(mask_payload({"gstin": "32TTNXB7384T1ZW", "nested": [{"udyam_number": "UDYAM-KL-00-3078801"}]}))
    assert "32TTNXB7384T1ZW" not in out and "3078801" not in out


def test_no_wall_clock_in_business_logic():
    pattern = re.compile(r"datetime\.now\(|date\.today\(")
    for path in (APP / "services").rglob("*.py"):
        assert not pattern.search(path.read_text(encoding="utf-8")), path


def test_propensity_no_leakage_and_auc():
    report = propensity.metrics()
    assert report["forbidden_assert"] == "passed"
    forbidden = {"stage_reached", "outcome", "drop_reason", "days_lead_to_activation", "customer_follow_up_calls",
                 "monthly_bundle_value_inr", "churned_within_6_months", "nps_score", "acquisition_cost_inr"}
    assert not (set(report["features_cat"] + report["features_num"]) & forbidden)
    assert report["cv_5fold"]["lr"]["roc_auc_mean"] > 0.6


def test_live_score_uses_trained_model():
    out = propensity.score_profile(P(business_type="Kirana store", segment="micro", city="Chennai", city_tier=1,
                                     employees=4, has_gstin=False))
    assert 0 <= out["score"] <= 100 and out["routing"] and out["reasons"]


def test_simulator_zero_recovery_is_baseline():
    out = simulator.simulate({"recovery": {k: 0 for k in simulator.DEFAULT_RECOVERY}})
    assert [round(x) for x in out["projected"]["funnel"]] == [5000, 3406, 1974, 861, 588, 368]
    base = simulator.simulate()
    assert base["projected"]["activations"] > 368
    s = simulator.sensitivity()
    assert s["low"]["activations"] < s["base"]["activations"] < s["high"]["activations"]


def test_reference_date():
    assert config.REFERENCE_DATE == date(2026, 7, 15)
