"""Sanity tests for the synthetic data generator (brief §6, §12)."""
import numpy as np
import pandas as pd
import pytest

from src.generator.__main__ import generate
from src.generator.scenarios import SCENARIOS


@pytest.fixture(scope="module")
def data():
    return generate(n_patients=250, days=365, seed=7)


def _quiet(lat):
    return (lat["flare_phase"] == 0) & ~(lat["days_to_next_flare"] <= 90)


def test_reproducible_with_seed():
    a, b = generate(40, 90, seed=3), generate(40, 90, seed=3)
    for name in ["patients", "wearables_daily", "labs", "symptoms", "events"]:
        pd.testing.assert_frame_equal(a[name], b[name])


def test_population_mix(data):
    p = data["patients"]
    assert 0.45 <= (p["ibd_type"] == "UC").mean() <= 0.65
    assert (p["sex"] == "M").mean() > 0.5
    assert 0.04 <= (p["age_at_diagnosis"] < 18).mean() <= 0.16
    assert 0.08 <= (p["disease_severity"] == "severe").mean() <= 0.25
    required = {"patient_id", "age", "sex", "region", "state", "ibd_type", "disease_extent", "years_since_diagnosis",
                "diagnostic_delay_months", "prior_misdiagnosis_tb", "past_flares_count", "nod2_variant",
                "current_medication", "medication_adherence", "last_colonoscopy_date", "bmi", "comorbidities"}
    assert required <= set(p.columns)


def test_hidden_parameters_not_in_ehr(data):
    hidden_only = set(data["hidden_params"].columns) - {"patient_id"}
    assert not hidden_only & set(data["patients"].columns)


def test_labels_match_flare_onsets(data):
    lat = data["latent_daily"].set_index(["patient_id", "date"])
    onsets = data["events"].query("event_type == 'flare_onset' and in_record")
    checked = 0
    for r in onsets.itertuples():
        for k in range(1, 15):
            key = (r.patient_id, pd.Timestamp(r.start_date) - pd.Timedelta(days=k))
            if key in lat.index:
                assert lat.loc[key, "flare_within_14d"] == 1
                checked += 1
    assert checked > 0
    last = data["latent_daily"]["date"].max()
    tail = data["latent_daily"][data["latent_daily"]["date"] > last - pd.Timedelta(days=14)]
    assert tail["flare_within_14d"].isin([1.0]).sum() + tail["flare_within_14d"].isna().sum() == len(tail)


def test_flare_rate_is_plausible(data):
    onsets = data["events"].query("event_type == 'flare_onset' and in_record")
    per_year = len(onsets) / len(data["patients"])
    assert 0.25 <= per_year <= 0.8
    assert 0.005 <= data["latent_daily"]["flare_within_14d"].mean() <= 0.05


def test_wearables_drift_before_flares(data):
    w = data["wearables_daily"].merge(data["latent_daily"], on=["patient_id", "date"])
    w = w.merge(data["hidden_params"][["patient_id", "rhr_base", "rmssd_base", "steps_base"]], on="patient_id")
    pre, quiet = w[w["days_to_next_flare"].between(1, 28)], w[_quiet(w)]
    assert (pre.resting_hr_bpm - pre.rhr_base).mean() - (quiet.resting_hr_bpm - quiet.rhr_base).mean() > 2
    assert (pre.hrv_rmssd_ms / pre.rmssd_base).mean() < (quiet.hrv_rmssd_ms / quiet.rmssd_base).mean() - 0.05
    assert (pre.steps / pre.steps_base).mean() < (quiet.steps / quiet.steps_base).mean() - 0.1


def test_calprotectin_tracks_inflammation(data):
    fc = data["labs"].query("test == 'faecal_calprotectin'").merge(data["latent_daily"], on=["patient_id", "date"])
    assert fc[fc["days_to_next_flare"].between(1, 28)]["value"].median() > 250
    assert fc[_quiet(fc) & ~fc["ctx_gut_infection"] & ~fc["ctx_nsaid"]]["value"].median() < 80


def test_colds_are_decoys(data):
    """Colds raise resting HR but not calprotectin."""
    lat = data["latent_daily"]
    w = data["wearables_daily"].merge(lat, on=["patient_id", "date"])
    w = w[_quiet(w)]
    assert w[w.ctx_cold].resting_hr_bpm.mean() > w[~w.ctx_cold].resting_hr_bpm.mean() + 3
    fc = data["labs"].query("test == 'faecal_calprotectin'").merge(lat, on=["patient_id", "date"])
    fc = fc[_quiet(fc) & ~fc["ctx_gut_infection"] & ~fc["ctx_nsaid"]]
    assert fc[fc.ctx_cold]["value"].median() < 100


def test_missingness(data):
    present = len(data["wearables_daily"]) / (len(data["patients"]) * 365)
    assert 0.72 <= present <= 0.92  # 10–20% random days + multi-day gaps


def test_seeded_scenarios(data):
    roster = data["scenarios"]
    assert roster["scenario"].value_counts().to_dict() == SCENARIOS
    ev, w, s = data["events"], data["wearables_daily"], data["symptoms"]
    for pid in roster.query("scenario == 'acute_severe_colitis'")["patient_id"]:
        e = ev.query("patient_id == @pid and event_type == 'emergency_acute_severe_colitis'").iloc[0]
        win = lambda df: df[(df.patient_id == pid) & df.date.between(e.start_date, e.end_date)]
        assert (win(w).resting_hr_bpm > 90).all()
        assert (win(s).stool_frequency >= 6).all() and win(s).blood_in_stool.all()
        assert (win(s).body_temp_c > 38).all()
    for kind in ["vte", "sepsis", "bowel_obstruction", "stoma_dehydration"]:
        assert (ev["event_type"] == f"emergency_{kind}").sum() == SCENARIOS[{"sepsis": "sepsis_on_steroids"}.get(kind, kind)]


def test_ananya_demo_story(data):
    p = data["patients"].iloc[0]
    assert p["display_name"] == "Ananya R." and p["ibd_type"] == "UC" and p["age"] == 28
    ev = data["events"].query("patient_id == 'P0001'")
    assert "flare_averted" in set(ev["event_type"])
    late = ev[(ev["event_type"] == "flare_onset") & (ev["start_date"] >= pd.Timestamp("2026-06-01"))]
    assert late.empty
    home = data["labs"].query("patient_id == 'P0001' and setting == 'home'")
    assert (home["value"] == 310).any()


def test_sweat_stream_is_optional(data):
    has = set(data["hidden_params"].query("has_sweat_sensor")["patient_id"])
    sweat_ids = set(data["sweat"]["patient_id"])
    assert sweat_ids <= has and 0.2 <= len(sweat_ids) / len(data["patients"]) <= 0.4
