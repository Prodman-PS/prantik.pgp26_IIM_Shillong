"""Load the observable tables. Ground truth is loaded separately and only for labels.

Observable = what a real clinic + patient app would have on the day:
patients.csv, conditions.csv, wearables_daily, symptoms, labs (test/value only),
sweat, and a whitelist of *observable* rows from events.csv (prescriptions and
patient-reported illnesses — see OBSERVABLE_EVENTS). Everything else in events.csv
(flare ramps, onsets, emergencies, stress, alcohol) and ground_truth/ is never read here.
"""
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "synthetic"
RECORD_START = pd.Timestamp("2025-10-01")
RECORD_END = pd.Timestamp("2026-09-30")

# Rows of events.csv a real system would know about on their start date:
# prescriptions are in the EHR; colds and gut infections are logged by the patient / GP.
OBSERVABLE_EVENTS = ["nsaid_course", "antibiotic_course", "steroid_course", "steroid_taper_end",
                     "gut_infection", "cold"]


def _read(name, data_dir):
    p = Path(data_dir)
    for ext in (".parquet", ".csv"):
        f = p / f"{name}{ext}"
        if f.exists():
            return pd.read_parquet(f) if ext == ".parquet" else pd.read_csv(f)
    raise FileNotFoundError(f"{name} not found in {p} — copy 03_Dataset/ into data/synthetic/ or run `make data`")


def _dates(df, cols):
    for c in cols:
        if c in df:
            df[c] = pd.to_datetime(df[c])
    return df


def load_observable(data_dir=DATA_DIR):
    t = {
        "patients": _read("patients", data_dir),
        "conditions": _dates(_read("conditions", data_dir), ["onset_date"]),
        "wearables": _dates(_read("wearables_daily", data_dir), ["date"]),
        "symptoms": _dates(_read("symptoms", data_dir), ["date"]),
        "labs": _dates(_read("labs", data_dir), ["date"]),
        "sweat": _dates(_read("sweat", data_dir), ["date"]),
    }
    # Never pass the lab `setting`/`reason` columns on: values such as "sepsis" or
    # "twin_escalation" encode the simulator's hidden state.
    t["labs"] = t["labs"][["patient_id", "date", "test", "value"]]
    ev = _read("events", data_dir)
    ev = ev[ev["event_type"].isin(OBSERVABLE_EVENTS)][["patient_id", "event_type", "start_date", "end_date"]]
    t["context_events"] = _dates(ev.copy(), ["start_date", "end_date"])
    return t


def load_labels(data_dir=DATA_DIR):
    """Targets only. Used for training/evaluation, never as model input."""
    lat = _dates(_read("ground_truth/latent_daily", data_dir), ["date"])
    return lat[["patient_id", "date", "flare_within_14d", "in_flare", "flare_onset", "days_to_next_flare"]]


def load_events_truth(data_dir=DATA_DIR):
    """Full events table — evaluation and dashboard markers of *past* flares only."""
    return _dates(_read("events", data_dir), ["start_date", "end_date"])
