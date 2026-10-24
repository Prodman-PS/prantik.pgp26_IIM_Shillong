"""WS3: turn SHAP contributions into the top-5 plain-language drivers for a patient-day.

SHAP values come from LightGBM's built-in TreeSHAP (pred_contrib=True; same algorithm as
shap.TreeExplainer). Features from the same signal (e.g. all HRV windows) are summed into
one driver so the doctor sees five different reasons, not five versions of one.
"""
import math
import re

import numpy as np
import pandas as pd

MEDS = ["none", "5-ASA", "thiopurine", "anti-TNF", "vedolizumab", "steroid"]


def family(col):
    if col.startswith("e_current_medication="):
        return "e_medication"
    if "=" in col:
        return col.split("=")[0]
    p = col.split("_")
    if p[0] == "e" and p[1] == "ctx":
        return "e_ctx_steroid" if "steroid" in col else f"e_ctx_{p[2]}"
    if p[0] == "e":
        return col
    return f"{p[0]}_{p[1]}"


def _f(row, c, default=np.nan):
    v = row.get(c, default)
    try:
        v = float(v)
    except (TypeError, ValueError):
        return default
    return v


def _ok(v):
    return v is not None and not (isinstance(v, float) and math.isnan(v))


def _describe(fam, row, ibd_type):
    g = lambda c: _f(row, c)
    score = "partial Mayo" if ibd_type == "UC" else "Harvey-Bradshaw"
    thr = 5 if ibd_type == "UC" else 8
    W = {  # wearables: natural-unit display columns
        "w_hrv": lambda: f"HRV {g('d_hrv_pct7'):+.0f}% vs personal baseline (7-day avg)" if _ok(g("d_hrv_pct7")) else "HRV not reported by device",
        "w_rhr": lambda: f"Resting HR {g('d_rhr_delta7'):+.1f} bpm vs baseline ({g('d_rhr_base'):.0f} → {g('d_rhr_base') + g('d_rhr_delta7'):.0f})",
        "w_hr": lambda: f"Average heart rate {g('d_hr_delta7'):+.1f} bpm vs baseline",
        "w_steps": lambda: f"Daily steps {g('d_steps_pct7'):+.0f}% vs baseline",
        "w_spo2": lambda: f"SpO₂ {g('d_spo2_delta7'):+.1f} points vs baseline",
        "w_sleep": lambda: f"Sleep duration {g('d_sleep_pct7'):+.0f}% vs baseline",
        "w_sleepeff": lambda: f"Sleep efficiency {100 * g('d_sleepeff_delta7'):+.1f} points vs baseline",
        "w_skintemp": lambda: f"Skin temperature {g('d_skintemp_delta7'):+.2f} °C vs baseline",
        "w_resp": lambda: f"Respiratory rate {g('d_resp_delta7'):+.1f} breaths/min vs baseline",
        "w_hrvamp": lambda: f"Day–night HRV rhythm {g('d_hrvamp_pct7'):+.0f}% vs baseline (flattening = inflammation sign)",
        "w_comove": lambda: f"{g('w_comove_core'):.0f} of 3 core watch signals (HRV, resting HR, steps) off baseline together",
        "w_wear": lambda: f"Watch worn on {100 * g('w_wear_rate14'):.0f}% of the last 14 days",
    }
    S = {
        "s_index": lambda: f"{score} score averaging {g('s_index_mean7') * thr:.1f} over 7 days (flare threshold {thr})",
        "s_urgency": lambda: f"Bowel urgency averaging {g('s_urgency_mean7'):.1f}/3 over 7 days",
        "s_fatigue": lambda: f"Fatigue averaging {g('s_fatigue_mean7'):.1f}/10 over 7 days",
        "s_pain": lambda: f"Abdominal pain averaging {g('s_pain_mean7'):.1f}/10 over 7 days",
        "s_stool": lambda: f"{g('s_stool_mean7'):.1f} stools/day on average over 7 days",
        "s_blood": lambda: f"Blood in stool on {100 * g('s_blood_mean7'):.0f}% of check-ins this week",
        "s_wellbeing": lambda: f"General wellbeing score {g('s_wellbeing_mean7'):.1f}/4 (higher = worse)",
        "s_temp": lambda: f"Highest logged temperature this week {g('s_temp_max7'):.1f} °C",
        "s_weight": lambda: f"Weight {g('s_weight_change90'):+.1f} kg over 3 months",
        "s_checkin": lambda: f"Symptom check-ins on {100 * g('s_checkin_rate14'):.0f}% of the last 14 days",
        "s_night": lambda: "Night sweats reported this week" if g("s_night_sweats_7d") > 0 else "No night sweats this week",
        "s_vomiting": lambda: "Vomiting reported this week" if g("s_vomiting_7d") > 0 else "No vomiting this week",
    }
    L = {
        "l_fc": lambda: (f"Calprotectin {g('l_fc_last'):.0f} µg/g"
                         + (f" ({g('l_fc_delta'):+.0f} vs previous)" if _ok(g("l_fc_delta")) else "")
                         + f", {g('l_fc_days_since'):.0f} days ago") if _ok(g("l_fc_last")) else "No calprotectin on file",
        "l_crp": lambda: f"CRP {g('l_crp_last'):.1f} mg/L" + (f" ({g('l_crp_delta'):+.1f} vs previous)" if _ok(g("l_crp_delta")) else ""),
        "l_hb": lambda: f"Haemoglobin {g('l_hb_last'):.1f} g/dL" + (f" ({g('l_hb_trend90'):+.1f} over 3 months)" if _ok(g("l_hb_trend90")) else ""),
        "l_ferritin": lambda: f"Ferritin {g('l_ferritin_last'):.0f} ng/mL" + (f" ({g('l_ferritin_delta'):+.0f} vs previous)" if _ok(g("l_ferritin_delta")) else ""),
        "l_albumin": lambda: f"Albumin {g('l_albumin_last'):.2f} g/dL" + (f" ({g('l_albumin_delta'):+.2f} vs previous)" if _ok(g("l_albumin_delta")) else ""),
        "l_plt": lambda: f"Platelets {g('l_plt_last'):.0f} ×10⁹/L",
        "l_wbc": lambda: f"White cell count {g('l_wbc_last'):.1f} ×10⁹/L",
        "l_tnftrough": lambda: f"Anti-TNF trough level {g('l_tnftrough_last'):.1f} µg/mL",
        "l_alp": lambda: f"ALP {g('l_alp_last'):.0f} U/L",
    }
    X = {k: (lambda k=k: f"Sweat {n} trend vs baseline (investigational sensor)") for k, n in
         [("x_scrp", "CRP"), ("x_scal", "calprotectin"), ("x_sil6", "IL-6"), ("x_stnf", "TNF-α")]}
    E = {
        "e_medication": lambda: "On " + next((m for m in MEDS if g(f"e_current_medication={m}") == 1), "unknown therapy"),
        "e_medication_adherence": lambda: f"Medication adherence {100 * g('e_medication_adherence'):.0f}%",
        "e_past_flares_count": lambda: f"{g('e_past_flares_count'):.0f} past flares on record",
        "e_ctx_nsaid": lambda: "NSAID course in the last 14 days" if g("e_ctx_nsaid_14d") > 0 else "No recent NSAIDs",
        "e_nsaid_use": lambda: "Regular NSAID use on record" if g("e_nsaid_use") > 0 else "No regular NSAID use",
        "e_ctx_cold": lambda: "Cold logged this week (explains some watch changes)" if g("e_ctx_cold_7d") > 0 else "No cold or infection logged",
        "e_ctx_antibiotic": lambda: "Antibiotic course in the last 4 weeks" if g("e_ctx_antibiotic_28d") > 0 else "No recent antibiotics",
        "e_ctx_gut": lambda: "Gut infection in the last 4 weeks" if g("e_ctx_gut_infection_28d") > 0 else "No recent gut infection",
        "e_ctx_steroid": lambda: ("On a steroid course" if g("e_ctx_steroid_active") > 0 else
                                  "Steroid taper ended in the last 60 days" if g("e_ctx_steroid_taper_ended_60d") > 0 else
                                  "No recent steroids"),
        "e_years_since_diagnosis": lambda: f"{g('e_years_since_diagnosis'):.0f} years since diagnosis",
        "e_disease_severity": lambda: "Baseline disease severity: " + next(
            (s for s in ["remission", "mild", "moderate", "severe"] if g(f"e_disease_severity={s}") == 1), "unknown"),
        "e_smoking_status": lambda: "Smoking status: " + next(
            (s for s in ["never", "former", "current"] if g(f"e_smoking_status={s}") == 1), "unknown"),
        "e_nod2_variant": lambda: "NOD2 risk variant" if g("e_nod2_variant") > 0 else "No NOD2 risk variant",
    }
    for table in (W, S, L, X, E):
        if fam in table:
            try:
                return table[fam]()
            except (TypeError, ValueError):
                break
    name = re.sub(r"^[a-z]_", "", fam).replace("_", " ").replace("=", ": ")
    return name[0].upper() + name[1:]


def explain_row(model, row: pd.Series, patient_id, ibd_type="UC", top_n=5):
    """Top-n drivers for one patient-day as plain sentences, ranked by |SHAP| per signal family."""
    contrib, _bias = model.contributions(row, patient_id)
    fam = contrib.groupby(contrib.index.map(family)).sum()
    top = fam.reindex(fam.abs().sort_values(ascending=False).index).head(top_n)
    out = []
    for f, v in top.items():
        out.append({"driver": f, "sentence": _describe(f, row, ibd_type),
                    "direction": "raises risk" if v > 0 else "lowers risk", "shap_logodds": round(float(v), 3)})
    return out
