"""Emergency rules (hours-level). Each rule is a function of the patient-day frame from
daily.build_daily and returns a boolean Series: True where the pattern is present.

These flag patterns for urgent clinician contact. They never diagnose.
"""
import numpy as np
import pandas as pd


def _rhr_jump(d):
    return d["d_rhr_raw"] - d["d_rhr_base"]


def acute_severe_colitis(d):
    """Truelove & Witts-style: ≥6 bloody stools/day + RHR > 90 + fever ≥ 37.8 °C (CRP shown as support)."""
    colonic = d["ibd_type"].eq("UC") | d["disease_extent"].isin(["L2 colonic", "L3 ileocolonic"])
    return colonic & ~d["stoma"] & (d["stool_frequency"] >= 6) & d["blood_in_stool"] & \
        (d["d_rhr_raw"] > 90) & (d["body_temp_c"] >= 37.8)


def vte(d):
    """Sudden RHR jump + SpO₂ drop + immobility (+ breathlessness or fast breathing)."""
    spo2 = d.groupby("patient_id", sort=False)["d_spo2_raw"].transform(lambda s: s.ffill(limit=1))
    spo2_drop = (spo2 - d["d_spo2_base"] <= -3) | (spo2 <= 93)
    immobile = d["d_steps_raw"] <= 0.25 * d["d_steps_base"]
    breath = d["breathlessness"] | (d["d_resp_raw"] - d["d_resp_base"] >= 4)
    return (_rhr_jump(d) >= 15) & spo2_drop & immobile & breath


def sepsis(d):
    """Fever + high RHR + fast breathing + HRV crash, in a patient on steroids (signs may be masked)."""
    on_steroids = (d["e_ctx_steroid_active"] > 0) | d["current_medication"].eq("steroid")
    hrv_crash = (d["d_hrv_raw"] <= 0.6 * d["d_hrv_base"]) | d["d_hrv_raw"].isna()   # some devices lack HRV
    return on_steroids & (d["body_temp_c"] >= 38.5) & (_rhr_jump(d) >= 15) & \
        (d["d_resp_raw"] - d["d_resp_base"] >= 4) & hrv_crash


def bowel_obstruction(d):
    """Vomiting + no stool or gas in stricturing Crohn's."""
    stricturing = d["stricture_flag"] | d["cd_behaviour"].fillna("").str.startswith("B2")
    return stricturing & d["vomiting"] & d["no_stool_or_gas"]


def stoma_dehydration(d):
    """High stoma output (≥ 12 bag emptyings) + RHR up + dizziness."""
    return d["stoma"] & (d["stool_frequency"] >= 12) & (_rhr_jump(d) >= 10) & d["dizziness"]


def tb_reactivation(d):
    """Low-grade fevers + night sweats + weight loss in a patient on anti-TNF."""
    on_biologic = d["current_medication"].isin(["anti-TNF"])
    wt = (d["weight_drop120"] >= 2.0) | (d["weight_drop120"] >= 0.04 * d["weight_max120"])
    return on_biologic & (d["fever_days14"] >= 2) & (d["night_sweats14"] >= 2) & wt


RULES = {
    "acute_severe_colitis": (acute_severe_colitis, "Possible acute severe colitis",
                             "≥6 bloody stools/day, resting HR > 90 and fever", "Same-day hospital assessment"),
    "vte": (vte, "Possible blood clot (VTE / PE)", "Sudden resting-HR jump, SpO₂ drop and immobility",
            "Urgent emergency assessment"),
    "sepsis": (sepsis, "Possible sepsis / abscess on steroids", "Fever, high HR, fast breathing and HRV crash while on steroids",
               "Urgent emergency assessment; steroids can mask signs"),
    "bowel_obstruction": (bowel_obstruction, "Possible bowel obstruction", "Vomiting with no stool or gas in stricturing Crohn's",
                          "Urgent surgical review"),
    "stoma_dehydration": (stoma_dehydration, "Possible stoma dehydration / AKI", "High stoma output, HR up and dizziness",
                          "Same-day fluids and kidney function check"),
    "tb_reactivation": (tb_reactivation, "Possible TB reactivation on anti-TNF", "Low-grade fevers, night sweats and weight loss",
                        "Urgent review; consider pausing anti-TNF and TB work-up"),
}


def evaluate(d):
    """Boolean frame (rule columns) aligned with d."""
    return pd.DataFrame({k: fn(d).fillna(False).astype(bool) for k, (fn, *_r) in RULES.items()}, index=d.index)


def alerts_for(d):
    """Long table of emergency alerts: one row per patient-day-rule that fired."""
    hits = evaluate(d)
    rows = []
    for k, (_fn, title, pattern, action) in RULES.items():
        sub = d.loc[hits[k], ["patient_id", "date", "d_rhr_raw", "body_temp_c", "crp_3d"]]
        for r in sub.itertuples(index=False):
            support = f"CRP {r.crp_3d:.0f} mg/L" if pd.notna(r.crp_3d) else "no recent CRP"
            rows.append({"patient_id": r.patient_id, "date": r.date, "tier": "red", "kind": "emergency", "rule": k,
                         "title": title, "detail": f"{pattern} ({support})", "action": action})
    return pd.DataFrame(rows, columns=["patient_id", "date", "tier", "kind", "rule", "title", "detail", "action"])
