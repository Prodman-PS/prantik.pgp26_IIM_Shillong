"""Trend alerts (days to weeks) driven by the 14-day risk and lab trends.

- Risk crosses 20% → amber, 50% → red (traffic light from CLAUDE.md §5), for the 14-day
  risk and for the secondary 28-day outlook.
- Wearable drift: ≥ 2 of 3 core watch signals (HRV↓, RHR↑, steps↓) off baseline on ≥ 7 of the
  last 14 days with no cold / gut infection logged → amber, prompts a home calprotectin.
- Smart escalation: amber/red with no calprotectin in the last 14 days → "order home calprotectin".
- Two consecutive calprotectin results > 250 → "clinician review".
- Hb down ≥ 1 g/dL over 3 months → anaemia trend.
"""
import numpy as np
import pandas as pd

AMBER, RED = 0.20, 0.50


DRIFT_DAYS = 7


def traffic_light(risk):
    if risk is None or (isinstance(risk, float) and np.isnan(risk)):
        return "grey"
    return "red" if risk >= RED else "amber" if risk >= AMBER else "green"


def wearable_drift(day):
    """Early-warning rule on the watch alone (decoy-checked)."""
    if active_flare(day):
        return False
    decoy = (day.get("e_ctx_cold_7d", 0) or 0) > 0 or (day.get("e_ctx_gut_infection_28d", 0) or 0) > 0
    return (day.get("w_comove_core_days14", 0) or 0) >= DRIFT_DAYS and not decoy


ACTIVE_FLARE_SYMPTOMS = 0.8   # 7-day symptom score ≥ 80% of the flare threshold


def active_flare(day):
    """Observable 'already in a flare': symptoms near the flare threshold or on a steroid course.
    The flare model predicts *new onsets*, so for these patients risk scores are not shown as alerts."""
    sym = day.get("s_index_mean7", np.nan)
    return bool((pd.notna(sym) and sym >= ACTIVE_FLARE_SYMPTOMS) or (day.get("e_ctx_steroid_active", 0) or 0) > 0)


def twin_status(risk14, risk28, drift=False, in_flare=False):
    """Overall light = worst of the 14-day risk, the 28-day outlook and the drift rule (drift caps at amber).
    Patients already in an observable flare get their own status ('flare')."""
    if in_flare:
        return "flare"
    order = ["grey", "green", "amber", "red"]
    lights = [traffic_light(risk14), traffic_light(risk28), "amber" if drift else "green"]
    return max(lights, key=order.index)


def suggested_action(risk, fc_days_since, two_consec_high, risk28=0.0, drift=False, in_flare=False):
    if in_flare:
        return "In an active flare: manage per flare plan; the twin keeps watching for emergency patterns"
    risk = max(risk, risk28 or 0.0, AMBER if drift else 0.0)
    if two_consec_high:
        return "Two calprotectin results > 250: clinician review / teleconsult and review therapy"
    if risk >= RED:
        return ("Teleconsult this week and review therapy" if fc_days_since is not None and fc_days_since <= 14
                else "Order home calprotectin now and book a teleconsult")
    if risk >= AMBER:
        return ("Order home calprotectin test" if fc_days_since is None or np.isnan(fc_days_since) or fc_days_since > 14
                else "Watch closely; recheck in 7 days")
    return "Routine monitoring"


def trend_alerts(scores: pd.DataFrame, daily: pd.DataFrame):
    """scores: patient_id, date, risk. daily: frame from daily.build_daily. Returns long alert table."""
    d = daily[["patient_id", "date", "l_fc_two_consec_high", "l_hb_trend90", "l_hb_last", "w_comove_core_days14",
               "e_ctx_cold_7d", "e_ctx_gut_infection_28d", "s_index_mean7", "e_ctx_steroid_active"]].merge(
        scores[["patient_id", "date", "risk", "risk28"]], on=["patient_id", "date"], how="left")
    d = d.sort_values(["patient_id", "date"])
    flare = (d["s_index_mean7"] >= ACTIVE_FLARE_SYMPTOMS) | (d["e_ctx_steroid_active"] > 0)
    # onset-risk alerts are suppressed while the patient is already in a flare
    d["risk"] = d["risk"].where(~flare, 0.0)
    d["risk28"] = d["risk28"].where(~flare, 0.0)
    prev = d.groupby("patient_id")["risk"].shift(1)
    prev28 = d.groupby("patient_id")["risk28"].shift(1)
    decoy = (d["e_ctx_cold_7d"] > 0) | (d["e_ctx_gut_infection_28d"] > 0)
    d["drift"] = (d["w_comove_core_days14"] >= DRIFT_DAYS) & ~decoy & ~flare
    prev_drift = d.groupby("patient_id")["drift"].shift(1).fillna(False).astype(bool)
    rows = []

    def add(mask, tier, rule, title, detail_fn, action):
        for r in d[mask].itertuples(index=False):
            rows.append({"patient_id": r.patient_id, "date": r.date, "tier": tier, "kind": "trend", "rule": rule,
                         "title": title, "detail": detail_fn(r), "action": action})

    add((d["risk"] >= RED) & ~(prev >= RED), "red", "risk_red", "14-day flare risk high",
        lambda r: f"Risk {100 * r.risk:.0f}% (≥ 50%)", "Teleconsult and review therapy")
    add((d["risk"] >= AMBER) & ~(prev >= AMBER), "amber", "risk_amber", "14-day flare risk rising",
        lambda r: f"Risk {100 * r.risk:.0f}% (≥ 20%)", "Smart escalation: order home calprotectin")
    add((d["risk28"] >= RED) & ~(prev28 >= RED) & ~(d["risk"] >= RED), "red", "outlook_red",
        "Flare likely within 4 weeks", lambda r: f"28-day outlook {100 * r.risk28:.0f}%", "Teleconsult and review therapy")
    add((d["risk28"] >= AMBER) & ~(prev28 >= AMBER) & ~(d["risk"] >= AMBER), "amber", "outlook_amber",
        "28-day outlook rising", lambda r: f"28-day outlook {100 * r.risk28:.0f}%", "Order home calprotectin")
    add(d["drift"] & ~prev_drift, "amber", "wearable_drift", "Watch signals drifting from baseline",
        lambda r: f"HRV, resting HR and steps off baseline together on {r.w_comove_core_days14:.0f} of 14 days; "
                  "no cold or infection logged", "Smart escalation: order home calprotectin")
    fc2 = d["l_fc_two_consec_high"] > 0
    add(fc2 & ~(d.groupby("patient_id")["l_fc_two_consec_high"].shift(1) > 0), "amber", "fc_two_high",
        "Two consecutive calprotectin > 250", lambda r: "Persistent gut inflammation", "Clinician review")
    hb = d["l_hb_trend90"] <= -1.0
    add(hb & ~(d.groupby("patient_id")["l_hb_trend90"].shift(1) <= -1.0), "amber", "hb_falling",
        "Haemoglobin falling", lambda r: f"Hb {r.l_hb_last:.1f} g/dL, {r.l_hb_trend90:+.1f} over 3 months",
        "Check iron studies; consider bleeding source")
    return pd.DataFrame(rows, columns=["patient_id", "date", "tier", "kind", "rule", "title", "detail", "action"])
