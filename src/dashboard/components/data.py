"""Cached data access for the dashboard. Everything here reads precomputed artifacts."""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data" / "synthetic"
ART = ROOT / "artifacts"
FEAT = ROOT / "data" / "features" / "features.parquet"


@st.cache_data(show_spinner=False)
def patients():
    p = pd.read_csv(DATA / "patients.csv")
    for c in ["last_colonoscopy_date", "tb_screening_date", "hpv_screen_date", "last_skin_check"]:
        p[c] = pd.to_datetime(p[c], errors="coerce")
    return p.set_index("patient_id", drop=False)


@st.cache_data(show_spinner=False)
def scenarios():
    return pd.read_csv(DATA / "demo_scenarios.csv").set_index("patient_id")["scenario"].to_dict()


@st.cache_data(show_spinner="Loading the twin…")
def daily():
    return pd.read_parquet(ART / "daily.parquet")


@st.cache_data(show_spinner=False)
def alerts():
    return pd.read_parquet(ART / "alerts.parquet")


@st.cache_data(show_spinner=False)
def metrics():
    return json.loads((ART / "metrics.json").read_text())


@st.cache_data(show_spinner=False)
def outlook_metrics():
    return json.loads((ART / "metrics_outlook.json").read_text())


@st.cache_data(show_spinner=False)
def ablation():
    return pd.read_csv(ART / "ablation.csv")


@st.cache_data(show_spinner=False)
def features_for(pid):
    return pd.read_parquet(FEAT, filters=[("patient_id", "==", pid)]).reset_index(drop=True)


@st.cache_data(show_spinner=False)
def labs_for(pid):
    l = pd.read_parquet(DATA / "labs.parquet", filters=[("patient_id", "==", pid)])
    return l[["date", "test", "value", "unit"]]


@st.cache_data(show_spinner=False)
def sweat_for(pid):
    return pd.read_parquet(DATA / "sweat.parquet", filters=[("patient_id", "==", pid)])


@st.cache_data(show_spinner=False)
def hourly_for(pid):
    f = DATA / "wearables_hourly_demo.parquet"
    h = pd.read_parquet(f, filters=[("patient_id", "==", pid)])
    h["timestamp"] = pd.to_datetime(h["timestamp"])
    return h


@st.cache_data(show_spinner=False)
def recorded_flares(pid):
    """Flare onsets as the clinic would have recorded them (shown only once they are in the past)."""
    ev = pd.read_csv(DATA / "events.csv", parse_dates=["start_date"])
    ev = ev[(ev["patient_id"] == pid) & ev["event_type"].isin(["flare_onset", "therapy_escalated", "therapy_optimised",
                                                               "steroid_course", "hospital_admission"])]
    return ev[["event_type", "start_date"]]


@st.cache_data(show_spinner=False)
def medication_events(pid):
    ev = pd.read_csv(DATA / "events.csv", parse_dates=["start_date", "end_date"])
    return ev[(ev["patient_id"] == pid) & ev["event_type"].isin(["nsaid_course", "antibiotic_course", "cold",
                                                                 "gut_infection", "steroid_course"])]
