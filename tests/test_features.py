"""WS1 acceptance tests (Build Guide §8): no leakage, label handling."""
import numpy as np
import pandas as pd
import pytest

from src.features.fusion import build_features, feature_columns, training_mask
from src.features.io import load_labels, load_observable

PIDS = ["P0001", "P0002", "P0007", "P0013", "P0100", "P0250"]
CUTOFF = pd.Timestamp("2026-04-15")


@pytest.fixture(scope="module")
def tables():
    t = load_observable()
    return {k: (v[v["patient_id"].isin(PIDS)].copy() if "patient_id" in v else v) for k, v in t.items()}


def _scramble_future(tables, cutoff, rng):
    """Replace every observation dated after `cutoff` with shuffled / random values."""
    out = {}
    for k, df in tables.items():
        df = df.copy()
        if k in ("patients", "conditions"):
            out[k] = df
            continue
        date_col = "start_date" if k == "context_events" else "date"
        fut = df[date_col] > cutoff
        if k == "context_events":
            # drop future events and inject fake ones
            fake = df[~fut].sample(frac=1.0, random_state=1).head(20).copy()
            fake["start_date"] = cutoff + pd.to_timedelta(rng.integers(1, 150, len(fake)), unit="D")
            fake["end_date"] = fake["start_date"] + pd.Timedelta(days=5)
            df = pd.concat([df[~fut], fake])
        else:
            num = df.select_dtypes("number").columns
            for c in num:
                df[c] = df[c].astype(float)
                vals = df.loc[fut, c].to_numpy()
                df.loc[fut, c] = rng.permutation(vals) * rng.uniform(0.5, 2.0) if len(vals) else vals
            # also drop a random third of future rows (missingness changes must not matter either)
            df = df.drop(df[fut].sample(frac=0.33, random_state=2).index)
        out[k] = df
    return out


def test_no_leakage(tables):
    rng = np.random.default_rng(0)
    a = build_features(tables, PIDS)
    b = build_features(_scramble_future(tables, CUTOFF, rng), PIDS)
    cols = feature_columns(a, groups=("w", "s", "e", "l", "x", "d"))
    past = a["date"] <= CUTOFF
    pd.testing.assert_frame_equal(a.loc[past, cols].reset_index(drop=True), b.loc[past, cols].reset_index(drop=True))
    # sanity: the scramble really did change the future
    assert not a.loc[~past, cols].equals(b.loc[~past, cols])


def test_one_row_per_patient_day(tables):
    f = build_features(tables, PIDS)
    assert len(f) == len(PIDS) * 365
    assert not f.duplicated(["patient_id", "date"]).any()


def test_no_ground_truth_columns(tables):
    f = build_features(tables, PIDS)
    banned = ["inflammation", "flare", "in_flare", "scenario", "reason", "setting", "days_to_next"]
    model_cols = feature_columns(f)
    allowed = {"e_past_flares_count"}  # EHR history field, known at the start of the record
    assert not [c for c in model_cols if any(b in c for b in banned) and c not in allowed]
    assert not [c for c in model_cols if c.startswith("d_")]


def test_training_rows():
    lab = load_labels()
    m = training_mask(lab)
    assert lab.loc[m, "flare_within_14d"].notna().all()
    assert not lab.loc[m, "in_flare"].astype(bool).any()
    assert m.sum() < len(lab)
