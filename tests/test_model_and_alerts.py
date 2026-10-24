"""WS2–WS4 acceptance tests (Build Guide §8).

Model tests need `make train` to have run (they skip otherwise).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.alerts.cancer_safety import cancer_safety
from src.alerts.daily import build_daily
from src.alerts.emergency_rules import RULES, evaluate
from src.features.fusion import build_features
from src.features.io import load_labels, load_observable
from src.models.train import make_folds

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts"
trained = pytest.mark.skipif(not (ART / "model_fold0.txt").exists(), reason="run `make train` first")

SEEDED = {"acute_severe_colitis": ["P0002", "P0003", "P0004"], "vte": ["P0005", "P0006"],
          "sepsis": ["P0007", "P0008"], "bowel_obstruction": ["P0009", "P0010"],
          "stoma_dehydration": ["P0011", "P0012"], "tb_reactivation": ["P0016", "P0017"]}


@pytest.fixture(scope="module")
def tables():
    return load_observable()


@pytest.fixture(scope="module")
def daily(tables):
    feats = build_features(tables)
    return build_daily(tables, feats)


# ---------------- split ----------------
def test_grouped_split():
    labels = load_labels()
    fold = make_folds(labels)
    assert set(fold) == set(labels["patient_id"].unique())
    assert set(fold.values()) == set(range(5))
    for k in range(5):
        test_p = {p for p, f in fold.items() if f == k}
        train_p = {p for p, f in fold.items() if f != k}
        assert not test_p & train_p
    if (ART / "folds.json").exists():
        assert json.loads((ART / "folds.json").read_text()) == fold


# ---------------- model artifacts ----------------
@trained
def test_metrics_files():
    assert (ART / "metrics_baseline.json").exists()
    m = json.loads((ART / "metrics.json").read_text())
    assert m["main"]["pr_auc"] > m["baseline"]["pr_auc"]
    assert m["main"]["pr_auc"] < 0.95, "suspiciously high PR-AUC: check for leakage"
    for k in ("median_lead_time_days", "false_alarms_per_patient_month", "brier", "auroc", "f1"):
        assert m["main"][k] is not None
    ab = pd.read_csv(ART / "ablation.csv")
    assert {"LightGBM A", "LightGBM B", "LightGBM C", "LightGBM D"} <= set(ab["model"])


@pytest.fixture(scope="module")
def model_rows():
    from src.models.twin import load_model
    feats = pd.read_parquet(ROOT / "data/features/features.parquet",
                            filters=[("patient_id", "in", ["P0001", "P0100", "P0420"])])
    return load_model(), feats


@trained
def test_explain_returns_5(model_rows):
    from src.models.explain import explain_row
    model, feats = model_rows
    for pid in ["P0001", "P0100", "P0420"]:
        rows = feats[feats["patient_id"] == pid]
        for i in [0, 120, 320, 364]:
            out = explain_row(model, rows.iloc[i], pid)
            assert len(out) == 5
            assert all(isinstance(o["sentence"], str) and len(o["sentence"]) > 5 for o in out)
            assert len({o["driver"] for o in out}) == 5


@trained
def test_whatif_moves_risk(model_rows):
    from src.models.whatif import LABEL, whatif
    model, feats = model_rows
    rows = feats[feats["patient_id"] == "P0001"]
    row = rows[rows["date"] == pd.Timestamp("2026-08-17")].iloc[0]
    low = whatif(model, row, "P0001", adherence=0.3)
    high = whatif(model, row, "P0001", adherence=1.0)
    assert low["projected_risk"] != high["projected_risk"]
    assert "Model-estimated" in high["label"]
    assert 0 <= high["projected_risk"] <= 1


# ---------------- emergency rules ----------------
def test_emergency_rules(daily):
    hits = evaluate(daily)
    seeded_all = sum(SEEDED.values(), [])
    for rule, pids in SEEDED.items():
        for p in pids:
            assert hits.loc[daily["patient_id"] == p, rule].any(), f"{rule} did not fire on {p}"
        other = ~daily["patient_id"].isin(pids)
        assert hits.loc[other, rule].mean() < 0.01, f"{rule} fires on ≥1% of other patient-days"
    # the rule fires inside the seeded emergency window
    ev = pd.read_csv(ROOT / "data/synthetic/events.csv", parse_dates=["start_date", "end_date"])
    for rule, pids in SEEDED.items():
        kind = ("red_flag_" if rule == "tb_reactivation" else "emergency_") + rule
        for p in pids:
            e = ev[(ev["patient_id"] == p) & (ev["event_type"] == kind)].iloc[0]
            days = daily.loc[(daily["patient_id"] == p) & hits[rule], "date"]
            assert days.between(e["start_date"], e["end_date"]).any(), f"{rule} on {p} outside its window"
    assert set(RULES) == set(SEEDED)


# ---------------- cancer safety ----------------
def test_cancer_safety(tables, daily):
    pts = tables["patients"].set_index("patient_id")
    today = pd.Timestamp("2026-09-30")
    for p in ["P0013", "P0014", "P0015"]:
        row = daily[(daily["patient_id"] == p) & (daily["date"] == today)].iloc[0]
        cs = cancer_safety(pts.loc[p], row, today)
        assert cs.risk_level == "high", p
        assert cs.red_flags, p
        assert cs.overdue and cs.next_due < today, p
        assert cs.interval_years == 1
    # Ananya: medium risk, colonoscopy due in ~4 months, not overdue
    row = daily[(daily["patient_id"] == "P0001") & (daily["date"] == today)].iloc[0]
    cs = cancer_safety(pts.loc["P0001"], row, today)
    assert cs.risk_level == "medium" and not cs.overdue and 3 <= cs.months_to_due <= 5
