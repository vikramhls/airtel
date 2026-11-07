#!/usr/bin/env python3
"""Train the OneFlow lead-intelligence models (leak-safe) and write reports.

Usage:  python3 -I scripts/train_propensity.py --data backend/app/data --out reports --models models

Produces:
  reports/propensity.json        metrics (5-fold CV + 20% holdout), feature list, leakage assertion
  reports/lead_scores.csv        out-of-fold propensity, predicted MRR, expected value, routing, top-2 reasons
  reports/propensity_dashboard.png   ROC curves + feature importance + funnel by segment + chases vs churn/NPS
  models/propensity.joblib, models/mrr.joblib

Design rules (see docs/15_ML_TRAINING.md):
  * Only fields KNOWN AT LEAD CREATION are features (no stage/date/outcome/bundle columns).
  * Registry-derived features (GST status, GST age, constitution) are allowed: they are looked up from the GSTIN/Udyam
    the lead already supplied.
  * Lead scores shown to users are OUT-OF-FOLD (cross_val_predict) so no lead is scored by a model that trained on it.
  * Reference date for ages is 2026-07-15 (never wall-clock).
"""
import argparse, json, os, sys
import numpy as np, pandas as pd
import joblib
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import (RandomForestClassifier, GradientBoostingClassifier,
                              HistGradientBoostingClassifier, VotingClassifier, GradientBoostingRegressor)
from sklearn.model_selection import StratifiedKFold, KFold, cross_val_predict, cross_val_score, train_test_split
from sklearn.metrics import roc_auc_score, average_precision_score, roc_curve, r2_score, mean_absolute_error

REF = pd.Timestamp("2026-07-15")
SEED = 42

FORBIDDEN = {  # outcome / post-creation fields: must never be features
    "stage_reached", "outcome", "drop_reason", "contacted_date", "needs_assessed_date", "quote_accepted_date",
    "kyc_complete_date", "activated_date", "days_lead_to_activation", "customer_follow_up_calls", "bundle_products",
    "monthly_bundle_value_inr", "one_time_setup_inr", "contract_months", "churned_within_6_months", "nps_score",
    "acquisition_cost_inr",
}
CAT = ["lead_source", "segment", "business_type", "city", "city_tier", "preferred_language", "annual_turnover_band",
       "has_gstin", "has_udyam", "current_internet", "current_provider", "contact_role", "gst_status", "constitution"]
NUM = ["employee_count", "num_sites", "monthly_telecom_spend_inr", "n_poi", "poi_min_cost", "poi_max_cost",
       "spend_per_site", "spend_per_emp", "poi_cost_to_spend", "gst_age_days", "udyam_age_days"]


def load(data):
    leads = pd.read_csv(f"{data}/smb_leads.csv", parse_dates=["created_date"])
    cat = pd.read_csv(f"{data}/product_catalogue.csv")
    gst = pd.read_csv(f"{data}/mock_gstin_registry.csv", parse_dates=["registration_date"])
    udy = pd.read_csv(f"{data}/mock_udyam_registry.csv", parse_dates=["date_of_registration"])
    return leads, cat, gst, udy


def features(leads, cat, gst, udy):
    d = leads.copy()
    price = cat.set_index("product_id")[["price_min_inr_per_month", "price_max_inr_per_month"]]
    def poi(s, col):
        ids = [x for x in str(s).split(";") if x in price.index]
        return float(price.loc[ids, col].sum()) if ids else 0.0
    d["n_poi"] = d.products_of_interest.fillna("").apply(lambda s: len([x for x in s.split(";") if x]))
    d["poi_min_cost"] = d.products_of_interest.fillna("").apply(lambda s: poi(s, "price_min_inr_per_month"))
    d["poi_max_cost"] = d.products_of_interest.fillna("").apply(lambda s: poi(s, "price_max_inr_per_month"))
    d = d.merge(gst[["gstin", "status", "constitution", "registration_date"]].rename(
        columns={"status": "gst_status", "registration_date": "gst_reg"}), on="gstin", how="left")
    d = d.merge(udy[["udyam_number", "date_of_registration"]].rename(columns={"date_of_registration": "udy_reg"}),
                on="udyam_number", how="left")
    d["gst_status"] = d.gst_status.fillna("Missing")
    d["constitution"] = d.constitution.fillna("Missing")
    d["gst_age_days"] = (REF - d.gst_reg).dt.days
    d["udyam_age_days"] = (REF - d.udy_reg).dt.days
    d["spend_per_site"] = d.monthly_telecom_spend_inr / d.num_sites.clip(lower=1)
    d["spend_per_emp"] = d.monthly_telecom_spend_inr / d.employee_count.clip(lower=1)
    d["poi_cost_to_spend"] = d.poi_min_cost / d.monthly_telecom_spend_inr.clip(lower=1)
    d["city_tier"] = d.city_tier.astype(str)
    for c in CAT:
        d[c] = d[c].astype(str)
    X = d[CAT + NUM]
    assert not (set(X.columns) & FORBIDDEN), "LEAKAGE: forbidden column used as feature"
    return d, X


def prep():
    return ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=10, sparse_output=False), CAT),
        ("num", Pipeline([("imp", SimpleImputer(strategy="median", add_indicator=True)),
                          ("sc", StandardScaler())]), NUM)])


def models():
    lr = Pipeline([("p", prep()), ("m", LogisticRegression(max_iter=2000, C=0.5, class_weight="balanced"))])
    rf = Pipeline([("p", prep()), ("m", RandomForestClassifier(300, min_samples_leaf=10, class_weight="balanced_subsample",
                                                                n_jobs=-1, random_state=SEED))])
    gb = Pipeline([("p", prep()), ("m", GradientBoostingClassifier(n_estimators=150, max_depth=3, learning_rate=0.05,
                                                                   subsample=0.8, random_state=SEED))])
    hgb = Pipeline([("p", prep()), ("m", HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=200,
                                                                        class_weight="balanced", random_state=SEED))])
    vote = Pipeline([("p", prep()), ("m", VotingClassifier([
        ("lr", LogisticRegression(max_iter=2000, C=0.5, class_weight="balanced")),
        ("rf", RandomForestClassifier(300, min_samples_leaf=10, class_weight="balanced_subsample", n_jobs=-1, random_state=SEED)),
        ("gb", GradientBoostingClassifier(n_estimators=150, max_depth=3, learning_rate=0.05, subsample=0.8, random_state=SEED))],
        voting="soft"))])
    return {"lr": lr, "rf": rf, "gb": gb, "hgb": hgb, "soft_vote": vote}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True); ap.add_argument("--out", default="reports"); ap.add_argument("--models", default="models")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True); os.makedirs(a.models, exist_ok=True)

    leads, cat, gst, udy = load(a.data)
    d, X = features(leads, cat, gst, udy)
    y = (d.outcome == "Activated").astype(int).values
    print(f"[INFO] leads={len(d)} activated={y.sum()} ({y.mean():.2%}); features={X.shape[1]}")

    skf = StratifiedKFold(5, shuffle=True, random_state=SEED)
    ms = models(); cv = {}
    for k, m in ms.items():
        s = cross_val_score(m, X, y, cv=skf, scoring="roc_auc", n_jobs=1)
        pr = cross_val_score(m, X, y, cv=skf, scoring="average_precision", n_jobs=1)
        cv[k] = {"roc_auc_mean": round(s.mean(), 4), "roc_auc_std": round(s.std(), 4), "pr_auc_mean": round(pr.mean(), 4)}
        print(f"  {k:10s} ROC-AUC {s.mean():.4f} (+/- {s.std():.4f})  PR-AUC {pr.mean():.4f}")

    # holdout 80/20 (for the ROC chart) -------------------------------------------------
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, stratify=y, random_state=SEED)
    hold = {}; curves = {}
    for k, m in models().items():
        m.fit(Xtr, ytr); p = m.predict_proba(Xte)[:, 1]
        hold[k] = {"roc_auc": round(roc_auc_score(yte, p), 4), "pr_auc": round(average_precision_score(yte, p), 4)}
        curves[k] = roc_curve(yte, p)
    print("  holdout:", {k: v["roc_auc"] for k, v in hold.items()})

    # OUT-OF-FOLD scores for every lead (explainable model = LR) --------------------------
    oof_lr = cross_val_predict(models()["lr"], X, y, cv=skf, method="predict_proba")[:, 1]
    oof_gb = cross_val_predict(models()["gb"], X, y, cv=skf, method="predict_proba")[:, 1]
    p = 0.5 * oof_lr + 0.5 * oof_gb   # blend of explainable + non-linear
    # calibrate so mean score == base rate (class_weight inflates LR)
    p = np.clip(p * (y.mean() / p.mean()), 0, 1)
    p_auc = roc_auc_score(y, p)
    print(f"  OOF blended score AUC (all 5000, out-of-fold): {p_auc:.4f}")

    # fit final LR for reasons + coefficients -------------------------------------------
    lr = models()["lr"].fit(X, y)
    pre, clf = lr.named_steps["p"], lr.named_steps["m"]
    names = pre.get_feature_names_out()
    Z = pre.transform(X); Z = Z.toarray() if hasattr(Z, "toarray") else Z
    contrib = Z * clf.coef_[0]
    def label(n):
        n = n.split("__", 1)[1]
        return n
    top2 = [[label(names[j]) for j in np.argsort(-np.abs(r))[:2]] for r in contrib]
    coefs = sorted(zip(names, clf.coef_[0]), key=lambda t: -abs(t[1]))[:15]

    # MRR regression on activated leads --------------------------------------------------
    act = d.outcome.eq("Activated").values
    Xa, ya = X[act], np.log1p(d.loc[act, "monthly_bundle_value_inr"].values)
    reg = Pipeline([("p", prep()), ("m", GradientBoostingRegressor(n_estimators=200, max_depth=3, learning_rate=0.05,
                                                                   subsample=0.8, random_state=SEED))])
    kf = KFold(5, shuffle=True, random_state=SEED)
    oof_m = cross_val_predict(reg, Xa, ya, cv=kf)
    r2 = r2_score(ya, oof_m); mae = mean_absolute_error(np.expm1(ya), np.expm1(oof_m))
    print(f"  MRR (log) 5-fold R2={r2:.3f}  MAE=Rs {mae:,.0f}  (n={act.sum()})")
    reg.fit(Xa, ya)
    mrr = np.expm1(reg.predict(X))

    # Expected value + routing ------------------------------------------------------------
    churn = (d.loc[act, "churned_within_6_months"] == "Y").mean()
    ev = p * mrr * 12 * (1 - churn)           # annual, retention-adjusted. Document this formula on the slide.
    d["propensity"] = (p * 100).round(1); d["pred_mrr_inr"] = mrr.round(0); d["expected_annual_value_inr"] = ev.round(0)
    d["reasons"] = ["; ".join(t) for t in top2]
    hi_ev = np.quantile(ev, 0.80); hi_p = np.quantile(p, 0.67); lo_p = np.quantile(p, 0.33)
    def route(r):
        complex_ = r.segment in ("Small multi-site businesses", "Small manufacturers")
        if r.has_gstin == "N" and r.propensity / 100 < hi_p: return "4. GST help first (unlock path)"
        if r.expected_annual_value_inr >= hi_ev and r.propensity / 100 >= hi_p: return "1. Field Sales VIP (high propensity + high value)"
        if r.expected_annual_value_inr >= hi_ev or (complex_ and r.propensity / 100 >= lo_p): return "2. Channel partner assisted"
        if r.propensity / 100 >= hi_p: return "3. Self-serve link (fast track)"
        return "5. Nurture via WhatsApp link (low touch)"
    d["routing"] = d.apply(route, axis=1)
    cols = ["lead_id", "business_name", "segment", "city", "lead_source", "has_gstin", "propensity", "pred_mrr_inr",
            "expected_annual_value_inr", "routing", "reasons", "outcome"]
    d[cols].sort_values("expected_annual_value_inr", ascending=False).to_csv(f"{a.out}/lead_scores.csv", index=False)
    print(d.routing.value_counts().to_string())
    print("\nTOP 8 by expected annual value:\n", d.sort_values("expected_annual_value_inr", ascending=False)[
        ["lead_id", "business_name", "segment", "propensity", "pred_mrr_inr", "expected_annual_value_inr", "routing"]].head(8).to_string(index=False))

    # Lift table (honest value of the score) -----------------------------------------------
    dec = pd.qcut(p, 5, labels=False, duplicates="drop")
    lift = pd.DataFrame({"q": dec, "y": y}).groupby("q").y.agg(["mean", "size"]).round(4)
    lift.index = [f"Q{int(i)+1}" for i in lift.index]
    print("\nActivation rate by score quintile (Q5 = highest):\n", lift.to_string())

    # Save ---------------------------------------------------------------------------------
    best = max(cv, key=lambda k: cv[k]["roc_auc_mean"])
    rep = {"n_leads": int(len(d)), "base_rate": round(float(y.mean()), 4), "features_cat": CAT, "features_num": NUM,
           "forbidden_assert": "passed", "cv_5fold": cv, "holdout_20pct": hold, "best_cv_model": best,
           "oof_blended_auc": round(float(p_auc), 4), "top_lr_coefficients": [(n, round(float(c), 3)) for n, c in coefs],
           "mrr_regression": {"cv_r2_log": round(float(r2), 3), "cv_mae_inr": round(float(mae), 0), "n_train": int(act.sum())},
           "retention_factor": round(float(1 - churn), 3), "ev_formula": "propensity x predicted_MRR x 12 x (1 - six_month_churn)",
           "lift_by_quintile": lift.reset_index().rename(columns={"index": "quintile"}).to_dict("records"),
           "routing_counts": d.routing.value_counts().to_dict(),
           "notes": "Modest AUC: the synthetic data has weak signal. Report honestly; use score for prioritisation, not prediction."}
    json.dump(rep, open(f"{a.out}/propensity.json", "w"), indent=2, default=float)
    joblib.dump(lr, f"{a.models}/propensity.joblib"); joblib.dump(reg, f"{a.models}/mrr.joblib")

    # Dashboard ----------------------------------------------------------------------------
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig, ax = plt.subplots(2, 2, figsize=(15, 10))
        for k, (fpr, tpr, _) in curves.items():
            ax[0, 0].plot(fpr, tpr, label=f"{k} (AUC={hold[k]['roc_auc']:.3f})", lw=2.5 if k == "soft_vote" else 1)
        ax[0, 0].plot([0, 1], [0, 1], "--", c="grey"); ax[0, 0].set_title("A. ROC (20% holdout)"); ax[0, 0].legend(fontsize=8)
        ax[0, 0].set_xlabel("False positive rate"); ax[0, 0].set_ylabel("True positive rate")
        c15 = coefs[:12][::-1]
        ax[0, 1].barh([label(n) for n, _ in c15], [c for _, c in c15], color=["#c0392b" if c < 0 else "#1e8449" for _, c in c15])
        ax[0, 1].set_title("B. Top logistic coefficients (green = raises activation)")
        order = ["Lead", "Contacted", "Needs assessed", "Quote accepted", "KYC complete", "Activated"]
        flags = pd.DataFrame({"seg": d.segment, "c": d.contacted_date.notna(), "n": d.needs_assessed_date.notna(),
                              "q": d.quote_accepted_date.notna(), "k": d.kyc_complete_date.notna(), "a": act})
        for s, g in flags.groupby("seg"):
            ax[1, 0].plot(order, [100, *[g[c].mean() * 100 for c in ["c", "n", "q", "k", "a"]]], marker="o", label=s)
        ax[1, 0].set_title("C. Funnel survival by segment (%)"); ax[1, 0].legend(fontsize=8); ax[1, 0].tick_params(axis="x", labelsize=8)
        a_ = d[act]; g = a_.groupby("customer_follow_up_calls").agg(churn=("churned_within_6_months", lambda s: (s == "Y").mean() * 100),
                                                                   nps=("nps_score", "mean"))
        ax[1, 1].bar(g.index, g.churn, color="#e67e22"); ax[1, 1].set_ylabel("6-month churn %"); ax[1, 1].set_xlabel("Follow-up calls")
        t = ax[1, 1].twinx(); t.plot(g.index, g.nps, c="teal", marker="s"); t.set_ylabel("NPS")
        ax[1, 1].set_title("D. Status chases vs churn and NPS (why the tracker matters)")
        plt.tight_layout(); plt.savefig(f"{a.out}/propensity_dashboard.png", dpi=150)
    except Exception as e:
        print("[WARN] chart skipped:", e)
    print(f"\n[OK] wrote {a.out}/propensity.json, lead_scores.csv, propensity_dashboard.png; models in {a.models}/")


if __name__ == "__main__":
    main()
