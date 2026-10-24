"""Fuse EHR + wearables + symptoms + labs (+ sweat) into one causal row per patient-day.

    python -m src.features.fusion          # writes data/features/features.parquet + labels.parquet

Column prefixes define the data stream (used for the A/B/C ablation):
    w_  wearables          s_  symptom check-ins      e_  EHR static + conditions + context
    l_  labs               x_  sweat (investigational) d_  display-only (plain-language values, never a model input)
Every feature at day t uses data dated ≤ t only (tests/test_features.py::test_no_leakage).
"""
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .baselines import observable_quiet, personal_baseline, zscore
from .io import RECORD_END, RECORD_START, load_labels, load_observable
from .windows import any_in_last, days_since, rolling_slope, window_stats

OUT_DIR = Path(__file__).resolve().parents[2] / "data" / "features"
LAB_HISTORY_START = pd.Timestamp("2025-06-01")   # pre-record lab history in the dataset
SYMPTOM_THRESHOLD = {"UC": 5.0, "CD": 8.0}       # partial Mayo / HBI flare thresholds

WEARABLE_SIGNALS = {   # feature name -> source column (hrv_amp is derived)
    "hrv": "hrv_rmssd_ms", "rhr": "resting_hr_bpm", "hr": "hr_mean_bpm", "steps": "steps",
    "spo2": "spo2_pct", "sleep": "sleep_duration_h", "sleepeff": "sleep_efficiency",
    "skintemp": "skin_temp_dev_c", "resp": "resp_rate_brpm", "hrvamp": None,
}
SWEAT_SIGNALS = {"scrp": "sweat_crp_ng_ml", "scal": "sweat_calprotectin_ng_ml",
                 "sil6": "sweat_il6_pg_ml", "stnf": "sweat_tnf_alpha_pg_ml"}
LAB_TESTS = {"fc": "faecal_calprotectin", "crp": "crp", "hb": "haemoglobin", "ferritin": "ferritin",
             "albumin": "albumin", "plt": "platelets", "wbc": "wbc", "tnftrough": "anti_tnf_trough", "alp": "alp"}

CATEGORICAL = {
    "sex": ["F", "M"], "region": ["urban", "rural"], "ibd_type": ["UC", "CD"],
    "disease_extent": ["E1 proctitis", "E2 left-sided", "E3 pancolitis", "L1 ileal", "L2 colonic", "L3 ileocolonic"],
    "cd_behaviour": ["B1 inflammatory", "B2 stricturing", "B3 penetrating"],
    "disease_severity": ["remission", "mild", "moderate", "severe"],
    "smoking_status": ["never", "former", "current"],
    "current_medication": ["none", "5-ASA", "thiopurine", "anti-TNF", "vedolizumab", "steroid"],
}
NUMERIC = ["age", "age_at_diagnosis", "years_since_diagnosis", "diagnostic_delay_months", "past_flares_count",
           "hospitalisations", "childhood_antibiotic_courses", "medication_adherence", "bmi"]
BOOLEAN = ["perianal_disease", "prior_misdiagnosis_tb", "stoma", "stricture_flag", "pseudopolyps_flag", "psc_flag",
           "family_history_ibd", "family_history_crc", "nod2_variant", "il23r_r381q_protective", "hla_drb1_0103",
           "nsaid_use", "ppi_use", "prior_dysplasia"]
CONDITION_FLAGS = {"D50.9": "iron_def_anaemia", "F41.2": "anxiety_depression", "M07.6": "arthropathy",
                   "K56.6": "stricture_hx", "K60.3": "fistula", "H20.9": "uveitis", "L52": "erythema_nodosum",
                   "K83.0": "psc_dx", "M85.8": "osteopenia", "A18.3": "tb_misdiagnosis_hx"}


def _grid(df, col, dates, pids, agg="mean"):
    """Long table -> (days × patients) frame on a fixed calendar."""
    if df.empty:
        return pd.DataFrame(np.nan, index=dates, columns=pids)
    g = df.pivot_table(index="date", columns="patient_id", values=col, aggfunc=agg)
    return g.reindex(index=dates, columns=pids).astype(float)


def _event_grid(ev, kinds, dates, pids):
    """True on each day an event of these kinds is active (start ≤ day ≤ end)."""
    out = np.zeros((len(dates), len(pids)), dtype=bool)
    col = {p: j for j, p in enumerate(pids)}
    d0 = dates[0]
    sub = ev[ev["event_type"].isin(kinds) & ev["patient_id"].isin(col)]
    for p, a, b in zip(sub["patient_id"], sub["start_date"], sub["end_date"].fillna(sub["start_date"])):
        i, k = (a - d0).days, (b - d0).days
        if k < 0 or i >= len(dates):
            continue
        out[max(i, 0):min(k, len(dates) - 1) + 1, col[p]] = True
    return pd.DataFrame(out, index=dates, columns=pids)


def _static(patients, conditions, dates, pids):
    p = patients.set_index("patient_id").reindex(pids)
    static = {}
    for c in NUMERIC:
        static[f"e_{c}"] = pd.to_numeric(p[c], errors="coerce").to_numpy(dtype=float)
    for c in BOOLEAN:
        static[f"e_{c}"] = p[c].astype(str).str.lower().eq("true").to_numpy(dtype=float)
    for c, levels in CATEGORICAL.items():
        v = p[c].fillna("").astype(str)
        for lv in levels:
            static[f"e_{c}={lv}"] = (v == lv).to_numpy(dtype=float)
    static["e_surgery_any"] = (~p["surgeries"].fillna("none").isin(["none", ""])).to_numpy(dtype=float)
    static["e_device_no_hrv"] = 0.0  # filled below from data availability (not from device names)
    # Conditions: flag active from its onset date onwards (later diagnoses only switch on after onset).
    cond = {}
    for code, name in CONDITION_FLAGS.items():
        sub = conditions[conditions["icd10"] == code].groupby("patient_id")["onset_date"].min()
        onset = sub.reindex(pids).to_numpy()
        cond[f"e_cond_{name}"] = pd.DataFrame(
            (dates.to_numpy()[:, None] >= onset[None, :]) & ~pd.isna(onset)[None, :], index=dates, columns=pids)
    return static, cond


def build_features(tables, patient_ids=None, record_start=RECORD_START, record_end=RECORD_END, verbose=False):
    """Return the fused feature table (patient_id, date, features...) for the record window."""
    t0 = time.time()
    patients = tables["patients"]
    pids = list(patient_ids) if patient_ids is not None else patients["patient_id"].tolist()
    keep = lambda df: df[df["patient_id"].isin(pids)]
    days = pd.date_range(record_start, record_end, freq="D")
    xdays = pd.date_range(LAB_HISTORY_START, record_end, freq="D")   # extended calendar for labs/context
    rec = slice(len(xdays) - len(days), None)
    ibd = patients.set_index("patient_id").reindex(pids)["ibd_type"].to_numpy()
    F = {}

    # ---- context flags (EHR prescriptions + patient-reported illness) ----
    ev = keep(tables["context_events"])
    ctx = {k: _event_grid(ev, [k], xdays, pids) for k in
           ["nsaid_course", "antibiotic_course", "steroid_course", "gut_infection", "cold"]}
    taper_end = _event_grid(ev, ["steroid_taper_end"], xdays, pids)
    cx = {
        "e_ctx_nsaid_active": ctx["nsaid_course"], "e_ctx_nsaid_14d": any_in_last(ctx["nsaid_course"], 14),
        "e_ctx_antibiotic_28d": any_in_last(ctx["antibiotic_course"], 28),
        "e_ctx_gut_infection_28d": any_in_last(ctx["gut_infection"], 28),
        "e_ctx_cold_active": ctx["cold"], "e_ctx_cold_7d": any_in_last(ctx["cold"], 7),
        "e_ctx_steroid_active": ctx["steroid_course"],
        "e_ctx_steroid_taper_ended_60d": any_in_last(taper_end, 60),
        "e_ctx_days_since_steroid": days_since(ctx["steroid_course"], cap=400),
    }
    for k, v in cx.items():
        F[k] = v.iloc[rec].astype(float)
    context_any = (any_in_last(ctx["cold"] | ctx["gut_infection"] | ctx["nsaid_course"] | ctx["antibiotic_course"]
                               | ctx["steroid_course"], 7)).iloc[rec]

    # ---- labs (forward-fill only) ----
    labs = keep(tables["labs"])
    lab_last = {}
    for short, test in LAB_TESTS.items():
        lt = labs[labs["test"] == test]
        g = _grid(lt, "value", xdays, pids, agg="max")
        last = g.ffill()
        has = g.notna()
        # previous result: value of the test before the most recent one
        prev_at_test = g.where(has).apply(lambda s: s.dropna().shift(1).reindex(s.index))
        prev = prev_at_test.ffill()
        dsl = days_since(has, cap=400)
        lab_last[short] = last
        F[f"l_{short}_last"] = last.iloc[rec]
        F[f"l_{short}_days_since"] = dsl.where(last.notna()).iloc[rec]
        if short in ("fc", "crp", "hb", "ferritin", "albumin"):
            F[f"l_{short}_delta"] = (last - prev).iloc[rec]
        if short == "fc":
            F["l_fc_log_last"] = np.log1p(last).iloc[rec]
            F["l_fc_two_consec_high"] = ((last > 250) & (prev > 250)).astype(float).iloc[rec]
            F["l_fc_max90"] = g.rolling(90, min_periods=1).max().iloc[rec]
            F["l_fc_count90"] = has.astype(float).rolling(90, min_periods=1).sum().iloc[rec]
            # Cumulative inflammation burden: distinct calendar months with an FC result > 250
            hi = lt[lt["value"] > 250].assign(m=lambda d: d["date"].dt.to_period("M"))
            first = hi.sort_values("date").drop_duplicates(["patient_id", "m"])
            burden = _grid(first.assign(one=1.0), "one", xdays, pids, agg="sum").fillna(0).cumsum()
            F["l_fc_burden_months"] = burden.iloc[rec]
        if short == "hb":
            F["l_hb_trend90"] = (last - last.shift(90)).iloc[rec]
    fc_last = lab_last["fc"].iloc[rec]

    # ---- symptoms ----
    sym = keep(tables["symptoms"]).copy()
    thr = sym["patient_id"].map(dict(zip(pids, ibd))).map(SYMPTOM_THRESHOLD)
    sym["index"] = sym["partial_mayo"].fillna(sym["harvey_bradshaw"])
    sym["index_norm"] = sym["index"] / thr
    sym["temp"] = sym["body_temp_c"].fillna(36.8)        # temperature is only logged when febrile
    for c in ["blood_in_stool", "vomiting", "night_sweats", "breathlessness", "dizziness", "no_stool_or_gas", "joint_pain"]:
        sym[c] = sym[c].astype(float)
    S = {c: _grid(sym, c, days, pids) for c in
         ["index_norm", "stool_frequency", "blood_in_stool", "urgency_0_3", "abdominal_pain_0_10", "fatigue_0_10",
          "general_wellbeing_0_4", "temp", "night_sweats", "vomiting", "dizziness", "breathlessness"]}
    S["checkin"] = S["index_norm"].notna().astype(float)
    sn = S["index_norm"]
    F["s_index_today"] = sn
    F["s_index_mean7"] = sn.rolling(7, min_periods=2).mean()
    F["s_index_mean14"] = sn.rolling(14, min_periods=3).mean()
    F["s_index_slope7"] = rolling_slope(sn, 7)
    F["s_index_slope14"] = rolling_slope(sn, 14)
    F["s_index_max7"] = sn.rolling(7, min_periods=1).max()
    for c, short in [("stool_frequency", "stool"), ("blood_in_stool", "blood"), ("urgency_0_3", "urgency"),
                     ("abdominal_pain_0_10", "pain"), ("fatigue_0_10", "fatigue"), ("general_wellbeing_0_4", "wellbeing")]:
        F[f"s_{short}_mean7"] = S[c].rolling(7, min_periods=2).mean()
        F[f"s_{short}_slope14"] = rolling_slope(S[c], 14)
    F["s_temp_max7"] = S["temp"].rolling(7, min_periods=1).max()
    for c in ["night_sweats", "vomiting", "dizziness", "breathlessness"]:
        F[f"s_{c}_7d"] = S[c].rolling(7, min_periods=1).max()
    F["s_checkin_rate14"] = S["checkin"].rolling(14, min_periods=1).mean()
    wt = _grid(sym, "weight_kg", days, pids).ffill()
    F["s_weight_change90"] = wt - wt.shift(90)
    sym_quiet_ref = F["s_index_mean7"]

    # ---- wearables vs personal baseline ----
    wear = keep(tables["wearables"]).copy()
    wear["hrvamp"] = wear["hrv_rmssd_ms"] - wear["hrv_rmssd_day_ms"]
    quiet = observable_quiet(context_any, sym_quiet_ref, fc_last)
    Z = {}
    worn = None
    for name, col in WEARABLE_SIGNALS.items():
        x = _grid(wear, col or name, days, pids)
        if worn is None:
            worn = _grid(wear, "resting_hr_bpm", days, pids).notna()
        med, scale = personal_baseline(x, quiet)
        z = zscore(x, med, scale)
        Z[name] = z
        F[f"w_{name}_z"] = z
        F.update({f"w_{k}": v for k, v in window_stats(z, f"{name}_z").items()})
        # display-only, natural units ("HRV down 22%", "resting HR +5 bpm")
        m7 = x.rolling(7, min_periods=2).mean()
        if name in ("hrv", "steps", "sleep", "hrvamp"):
            F[f"d_{name}_pct7"] = 100 * (m7 / med - 1)
        else:
            F[f"d_{name}_delta7"] = m7 - med
        F[f"d_{name}_raw"] = x
        F[f"d_{name}_base"] = med
        F[f"d_{name}_scale"] = scale
    F["w_wear_rate14"] = worn.astype(float).rolling(14, min_periods=1).mean()
    m7 = {k: Z[k].rolling(7, min_periods=2).mean() for k in Z}
    core = (m7["hrv"] < -1).astype(int) + (m7["rhr"] > 1).astype(int) + (m7["steps"] < -1).astype(int)
    ext = core + (m7["resp"] > 1).astype(int) + (m7["skintemp"] > 1).astype(int) + (m7["sleepeff"] < -1).astype(int)
    F["w_comove_core"] = core.astype(float).where(worn.rolling(7, min_periods=1).max() > 0)
    F["w_comove_all"] = ext.astype(float).where(worn.rolling(7, min_periods=1).max() > 0)
    F["w_comove_core_days14"] = (core >= 2).astype(float).rolling(14, min_periods=1).sum()

    # ---- sweat (investigational) ----
    sw = keep(tables["sweat"])
    for name, col in SWEAT_SIGNALS.items():
        x = np.log1p(_grid(sw, col, days, pids))
        med, scale = personal_baseline(x, quiet)
        z = zscore(x, med, scale)
        F[f"x_{name}_mean7"] = z.rolling(7, min_periods=2).mean()
        F[f"x_{name}_mean28"] = z.rolling(28, min_periods=5).mean()
        F[f"x_{name}_slope28"] = rolling_slope(z, 28)

    # ---- static EHR + conditions ----
    static, cond = _static(patients, tables["conditions"], xdays, pids)
    for k, v in cond.items():
        F[k] = v.iloc[rec].astype(float)

    # ---- stack to long (patient-major) ----
    D, P = len(days), len(pids)
    cols, arrays = [], []
    for k, v in F.items():
        a = v.reindex(index=days, columns=pids).to_numpy(dtype=np.float32)
        cols.append(k)
        arrays.append(a.T.reshape(-1))
    for k, v in static.items():
        cols.append(k)
        arrays.append(np.repeat(np.asarray(v, dtype=np.float32) if np.ndim(v) else np.full(P, v, np.float32), D))
    out = pd.DataFrame(np.column_stack(arrays), columns=cols)
    # devices that never report HRV: a data-availability flag derived from the observed stream itself
    no_hrv = out.groupby(np.repeat(np.arange(P), D))["w_hrv_z"].transform(lambda s: s.notna().cumsum().eq(0))
    out["e_device_no_hrv"] = no_hrv.astype(np.float32)
    out.insert(0, "date", np.tile(days.to_numpy(), P))
    out.insert(0, "patient_id", np.repeat(pids, D))
    if verbose:
        print(f"features: {out.shape[0]:,} rows × {out.shape[1] - 2} columns in {time.time() - t0:.0f}s")
    return out


def feature_columns(df, groups=("w", "s", "e", "l", "x")):
    return [c for c in df.columns if c.split("_", 1)[0] in groups and c not in ("patient_id", "date")]


def training_mask(labels):
    """Rows usable for training an onset predictor: label known and not already in a flare."""
    return labels["flare_within_14d"].notna() & ~labels["in_flare"].astype(bool)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tables = load_observable()
    feats = build_features(tables, verbose=True)
    labels = load_labels()
    labels = feats[["patient_id", "date"]].merge(labels, on=["patient_id", "date"], how="left")
    feats.to_parquet(OUT_DIR / "features.parquet", index=False)
    labels.to_parquet(OUT_DIR / "labels.parquet", index=False)
    print(f"wrote {OUT_DIR}/features.parquet and labels.parquet")


if __name__ == "__main__":
    main()
