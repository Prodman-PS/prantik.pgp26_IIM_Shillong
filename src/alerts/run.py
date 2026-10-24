"""Precompute the alert feed and the dashboard's daily table.

    python -m src.alerts.run      # after src.models.train; part of `make train`
"""
from pathlib import Path

import pandas as pd

from src.features.fusion import OUT_DIR as FEATURE_DIR
from src.features.io import load_observable

from .daily import build_daily
from .emergency_rules import alerts_for
from .trend_alerts import trend_alerts

ART = Path(__file__).resolve().parents[2] / "artifacts"


def main():
    tables = load_observable()
    feats = pd.read_parquet(FEATURE_DIR / "features.parquet")
    daily = build_daily(tables, feats)
    scores = pd.read_parquet(ART / "oof_scores.parquet")
    daily = daily.merge(scores[["patient_id", "date", "risk", "risk28"]], on=["patient_id", "date"], how="left")
    em = alerts_for(daily)
    tr = trend_alerts(scores, daily)
    alerts = pd.concat([em, tr], ignore_index=True).sort_values(["patient_id", "date", "tier"])
    alerts.to_parquet(ART / "alerts.parquet", index=False)
    daily.to_parquet(ART / "daily.parquet", index=False)
    print(f"alerts: {len(em):,} emergency patient-days, {len(tr):,} trend alerts → {ART / 'alerts.parquet'}")
    print(em.groupby("rule")["patient_id"].nunique().rename("patients").to_string())


if __name__ == "__main__":
    main()
