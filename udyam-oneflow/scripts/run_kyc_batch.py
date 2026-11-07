"""Run all 12 KYC applicants (47 images) through the Smart KYC pipeline.

Usage:  python scripts/run_kyc_batch.py
Writes:
  reports/kyc_extractions.json   OCR fields + confidence per image (cache, keyed by file name + size)
  reports/kyc_report.md          per-applicant check table + one-line human summary
  reports/kyc_report.json        same, machine-readable
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app import config  # noqa: E402
from app.services.kyc import extract, score, validate  # noqa: E402
from app.services.kyc.cache import CACHE_PATH, cache_key  # noqa: E402
from app.utils.mask import mask_payload  # noqa: E402

FILES = {"gst": "gst_certificate", "udyam": "udyam_certificate",
         "address": "address_proof", "signatory_id": "signatory_id"}
STATUS_ICON = {"pass": "PASS", "fail": "FAIL"}


def main() -> None:
    cache = json.loads(CACHE_PATH.read_text()) if CACHE_PATH.exists() else {}
    applicants = sorted({p.name.split("_")[0] for p in config.DOCS_DIR.glob("K*_*.png")})
    report: dict[str, dict] = {}
    started = time.time()
    for applicant in applicants:
        docs: dict[str, dict] = {}
        for doc_type, stem in FILES.items():
            path = config.DOCS_DIR / f"{applicant}_{stem}.png"
            if not path.exists():
                continue
            key = cache_key(path.name, path.read_bytes())
            if key not in cache:
                result = extract.extract(path.read_bytes(), doc_type)
                cache[key] = {"fields": result["fields"], "confidence": result["confidence"],
                              "engine": result["engine"], "quality": result["quality"]}
                print(f"  {path.name}: {time.time() - started:.1f}s", flush=True)
            docs[doc_type] = cache[key]
        checks = validate.validate(docs, consent_recorded=True)
        missing = [d for d in validate.DOC_TYPES if d not in docs]
        ready = score.readiness(checks, missing)
        report[applicant] = {
            "documents": {d: mask_payload(v["fields"]) for d, v in docs.items()},
            "checks": checks,
            "score": ready["score"],
            "state": ready["state"],
            "next_action": ready["next_action"],
            "summary": ready["summary"],
        }
        CACHE_PATH.write_text(json.dumps(cache, indent=1))

    (config.REPORTS_DIR / "kyc_report.json").write_text(json.dumps(report, indent=2))
    lines = [
        "# Smart KYC batch report (12 synthetic applicants)",
        "",
        f"Reference date {config.REFERENCE_DATE}. OCR engine: {next(iter(cache.values()))['engine'] if cache else 'n/a'}. "
        "Registries are the mock CSVs. Identifiers are masked.",
        "",
        "| Applicant | Business | Score | State | Exceptions |",
        "|---|---|---|---|---|",
    ]
    for applicant, rep in report.items():
        name = (rep["documents"].get("gst", {}).get("trade_name")
                or rep["documents"].get("udyam", {}).get("enterprise_name") or "?")
        fails = [c["code"] for c in rep["checks"] if c["status"] == "fail"]
        lines.append(f"| {applicant} | {name} | {rep['score']['passed']}/{rep['score']['total']} | "
                     f"{rep['state']} | {', '.join(fails) or 'none'} |")
    for applicant, rep in report.items():
        lines += ["", f"## {applicant}", "", f"**Summary:** {rep['summary']}", ""]
        if rep["next_action"]:
            lines.append(f"**Next action:** {rep['next_action']['label']}")
            lines.append("")
        lines += ["| Check | Result | Detail |", "|---|---|---|"]
        for c in rep["checks"]:
            lines.append(f"| {c['code']} | {STATUS_ICON[c['status']]}"
                         f"{' (' + c['severity'] + ')' if c['status'] == 'fail' else ''} | {c['detail']} |")
    (config.REPORTS_DIR / "kyc_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[OK] {len(report)} applicants -> reports/kyc_report.md ({time.time() - started:.0f}s)")


if __name__ == "__main__":
    main()
