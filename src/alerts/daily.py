"""Per patient-day view of raw observations the alert rules read (data up to day t only).

Columns: today's wearable values and the patient's personal baselines (from the feature
table), today's symptom check-in, short look-back counts, latest labs within 3 days, and
static EHR fields.
"""
import numpy as np
import pandas as pd

from src.features.fusion import LAB_HISTORY_START
from src.features.io import RECORD_END, RECORD_START

BASE_COLS = ["d_rhr_raw", "d_rhr_base", "d_spo2_raw", "d_spo2_base", "d_resp_raw", "d_resp_base",
             "d_hrv_raw", "d_hrv_base", "d_steps_raw", "d_steps_base",
             "e_ctx_steroid_active", "l_fc_last", "l_fc_two_consec_high", "l_hb_last", "l_hb_trend90",
             "l_ferritin_last", "l_ferritin_delta", "l_fc_burden_months", "l_crp_last", "l_alp_last",
             "s_index_mean7", "s_weight_change90", "w_comove_core", "w_comove_core_days14", "e_ctx_cold_7d", "e_ctx_gut_infection_28d", "w_rhr_z_mean7", "w_hrv_z_mean7", "w_steps_z_mean7"]
STATIC_COLS = ["patient_id", "display_name", "age", "sex", "ibd_type", "disease_extent", "cd_behaviour", "stoma",
               "stricture_flag", "pseudopolyps_flag", "psc_flag", "family_history_crc", "prior_dysplasia",
               "years_since_diagnosis", "current_medication", "last_colonoscopy_date", "tb_screening_status",
               "tb_screening_date", "hpv_screen_date", "last_skin_check", "past_flares_count", "perianal_disease"]


def build_daily(tables, feats, patient_ids=None):
    pids = list(patient_ids) if patient_ids is not None else tables["patients"]["patient_id"].tolist()
    days = pd.date_range(RECORD_START, RECORD_END, freq="D")
    grid = pd.MultiIndex.from_product([pids, days], names=["patient_id", "date"]).to_frame(index=False)

    f = feats[feats["patient_id"].isin(pids)][["patient_id", "date"] + BASE_COLS]
    d = grid.merge(f, on=["patient_id", "date"], how="left")

    sym = tables["symptoms"]
    sym = sym[sym["patient_id"].isin(pids)].copy()
    keep = ["stool_frequency", "blood_in_stool", "body_temp_c", "vomiting", "no_stool_or_gas", "dizziness",
            "breathlessness", "night_sweats", "abdominal_pain_0_10", "weight_kg"]
    d = d.merge(sym[["patient_id", "date"] + keep], on=["patient_id", "date"], how="left")
    for c in ["blood_in_stool", "vomiting", "no_stool_or_gas", "dizziness", "breathlessness", "night_sweats"]:
        d[c] = d[c].astype("boolean").fillna(False).astype(bool)
    d["checked_in"] = d["stool_frequency"].notna()

    g = d.groupby("patient_id", sort=False)
    roll = lambda col, w, fn="sum": g[col].transform(lambda s: getattr(s.astype(float).rolling(w, min_periods=1), fn)())
    d["lowgrade_fever"] = d["body_temp_c"].between(37.5, 38.5)
    d["fever_days14"] = roll("lowgrade_fever", 14)
    d["night_sweats14"] = roll("night_sweats", 14)
    d["weight_max120"] = roll("weight_kg", 120, "max")
    d["weight_last"] = g["weight_kg"].ffill()
    d["weight_drop120"] = d["weight_max120"] - d["weight_last"]
    d["blood_days14"] = roll("blood_in_stool", 14)

    # most recent CRP / WBC / creatinine within the last 3 days (used as supporting evidence only)
    labs = tables["labs"]
    labs = labs[labs["patient_id"].isin(pids) & labs["test"].isin(["crp", "wbc", "creatinine"])]
    for test in ["crp", "wbc", "creatinine"]:
        lt = labs[labs["test"] == test].groupby(["patient_id", "date"])["value"].max().rename(f"{test}_3d").reset_index()
        d = d.merge(lt, on=["patient_id", "date"], how="left")
        d[f"{test}_3d"] = d.groupby("patient_id", sort=False)[f"{test}_3d"].transform(lambda s: s.ffill(limit=3))

    p = tables["patients"][STATIC_COLS]
    d = d.merge(p, on="patient_id", how="left")
    for c in ["stoma", "stricture_flag", "pseudopolyps_flag", "psc_flag", "family_history_crc", "prior_dysplasia",
              "perianal_disease"]:
        d[c] = d[c].astype(str).str.lower().eq("true")
    return d
