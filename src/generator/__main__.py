"""Generate the synthetic IBD Digital Twin dataset (brief §6).

    python -m src.generator --n-patients 800 --seed 42

Tables are written as Parquet when pyarrow is installed, otherwise CSV
(use --format to force one).
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .population import build_conditions, generate_population
from .scenarios import assign_scenarios
from .latent import simulate_latent, FLARE_THRESHOLD
from .wearables import simulate_wearables, hourly_for
from .symptoms import simulate_symptoms, SYMPTOM_FLARE_THRESHOLD
from .labs import simulate_labs
from .sweat import simulate_sweat
from .events import HORIZON, build_events, label_episodes

BURN_IN_DAYS = 120  # simulated before the wearable record so episodes / lab history are already in progress


def _has_parquet():
    try:
        import pyarrow  # noqa: F401
        return True
    except ImportError:
        return False


def generate(n_patients=800, days=365, seed=42, end_date="2026-09-30"):
    """Run the full simulation in memory. Returns a dict of DataFrames + metadata."""
    rng = np.random.default_rng(seed)
    end = pd.Timestamp(end_date)
    D = BURN_IN_DAYS + days
    dates = pd.date_range(end=end, periods=D, freq="D")
    weekday = dates.day_of_week.to_numpy()

    patients, hidden = generate_population(n_patients, rng, end)
    scripts, overlays, roster = assign_scenarios(patients, hidden, rng, BURN_IN_DAYS, days, end)
    overlays = [(i, k, a, min(b, D), e) for i, k, a, b, e in overlays if a < D - 1]  # short runs
    conditions = build_conditions(patients, rng, end)

    I, phase, ctx, episodes = simulate_latent(patients, hidden, D, patients["years_since_diagnosis"].to_numpy(),
                                              weekday, rng, scripts)
    wear = simulate_wearables(patients, hidden, I, ctx, overlays, weekday, rng)
    sym_fields, checked_in, score = simulate_symptoms(patients, hidden, I, ctx, overlays, rng)
    labels, symptomatic_day = label_episodes(patients, I, score, episodes)
    labs = simulate_labs(patients, hidden, I, ctx, overlays, score, wear, dates, BURN_IN_DAYS, rng)
    sweat, sweat_valid, has_sweat = simulate_sweat(hidden, I, ctx, wear["wear_day"], rng)
    episode_mask = phase > 0
    events = build_events(patients, ctx, overlays, episodes, symptomatic_day, episode_mask, dates, BURN_IN_DAYS)

    # Flatten the wearable-record window into long daily tables
    rec = slice(BURN_IN_DAYS, D)
    P = len(patients)
    pid = np.repeat(patients["patient_id"].to_numpy(), days)
    date_col = np.tile(dates[rec].to_numpy(), P)
    flat = lambda a: a[:, rec].ravel()

    wear_cols = {k: flat(v) for k, v in wear.items() if k != "wear_day"}
    wearables_daily = pd.DataFrame({"patient_id": pid, "date": date_col, **wear_cols})
    worn = flat(wear["wear_day"])
    wearables_daily = wearables_daily[worn].reset_index(drop=True)

    symptoms = pd.DataFrame({"patient_id": pid, "date": date_col, **{k: flat(v) for k, v in sym_fields.items()}})
    symptoms = symptoms[flat(checked_in)].reset_index(drop=True)

    sweat_df = pd.DataFrame({"patient_id": pid, "date": date_col, **{k: flat(v) for k, v in sweat.items()}})
    sweat_df = sweat_df[flat(sweat_valid)].reset_index(drop=True)

    latent_daily = pd.DataFrame({
        "patient_id": pid, "date": date_col,
        "inflammation": flat(I).round(4), "flare_phase": flat(phase),
        **{k: flat(v) for k, v in labels.items()},
        **{f"ctx_{k}": flat(v) for k, v in ctx.items()},
    })

    demo_ids = set(roster["patient_id"])
    hourly = hourly_for(wearables_daily[wearables_daily["patient_id"].isin(demo_ids)], rng)

    hidden_out = hidden.merge(roster, on="patient_id", how="left")
    return {
        "patients": patients, "conditions": conditions, "wearables_daily": wearables_daily,
        "wearables_hourly_demo": hourly, "labs": labs[labs["date"] >= dates[0]], "symptoms": symptoms,
        "sweat": sweat_df, "events": events, "latent_daily": latent_daily, "hidden_params": hidden_out,
        "scenarios": roster, "meta": {"dates": dates, "burn": BURN_IN_DAYS, "episodes": episodes, "I": I},
    }


def summarize(out):
    pts, lat, ev, labs = out["patients"], out["latent_daily"], out["events"], out["labs"]
    years = len(lat) / len(pts) / 365
    rec_ev = ev[ev["in_record"]]
    onsets = rec_ev[rec_ev["event_type"] == "flare_onset"]
    fc = labs[labs["test"] == "faecal_calprotectin"].merge(lat[["patient_id", "date", "flare_phase", "days_to_next_flare"]],
                                                         on=["patient_id", "date"], how="inner")
    pre = fc["days_to_next_flare"].between(1, 28)
    quiet = (fc["flare_phase"] == 0) & ~(fc["days_to_next_flare"] <= 90)
    w = out["wearables_daily"].merge(lat[["patient_id", "date", "days_to_next_flare", "flare_phase"]], on=["patient_id", "date"])
    w = w.merge(out["hidden_params"][["patient_id", "rhr_base", "rmssd_base", "steps_base"]], on="patient_id")
    w_pre, w_q = w[w["days_to_next_flare"].between(1, 28)], w[(w["flare_phase"] == 0) & ~(w["days_to_next_flare"] <= 90)]
    rel = lambda df: {"resting_hr_delta_bpm": round(float((df.resting_hr_bpm - df.rhr_base).mean()), 2),
                      "hrv_pct_of_baseline": round(float((df.hrv_rmssd_ms / df.rmssd_base).mean() * 100), 1),
                      "steps_pct_of_baseline": round(float((df.steps / df.steps_base).mean() * 100), 1)}
    days_total = len(pts) * 365
    return {
        "patients": len(pts),
        "ibd_type": pts["ibd_type"].value_counts(normalize=True).round(3).to_dict(),
        "severity": pts["disease_severity"].value_counts(normalize=True).round(3).to_dict(),
        "paediatric_onset_pct": round(float((pts["age_at_diagnosis"] < 18).mean() * 100), 1),
        "onset_over_60_pct": round(float((pts["age_at_diagnosis"] > 60).mean() * 100), 1),
        "male_pct": round(float((pts["sex"] == "M").mean() * 100), 1),
        "flare_onsets_in_record": int(len(onsets)),
        "flares_per_patient_year": round(len(onsets) / (len(pts) * years), 3),
        "patients_with_flare_pct": round(onsets["patient_id"].nunique() / len(pts) * 100, 1),
        "inflammatory_only_onsets": int((rec_ev["event_type"] == "inflammatory_flare_onset").sum() - len(onsets)),
        "flare_within_14d_positive_pct": round(float(np.nanmean(lat["flare_within_14d"]) * 100), 2),
        "wearable_days_present_pct": round(len(out["wearables_daily"]) / days_total * 100, 1),
        "symptom_checkin_days_pct": round(len(out["symptoms"]) / days_total * 100, 1),
        "sweat_sensor_patients": int(out["sweat"]["patient_id"].nunique()),
        "lab_results": int(len(labs)),
        "calprotectin_median_quiet_ug_g": round(float(fc.loc[quiet, "value"].median()), 1),
        "calprotectin_median_28d_pre_flare_ug_g": round(float(fc.loc[pre, "value"].median()), 1),
        "wearables_quiet_periods": rel(w_q),
        "wearables_28d_pre_flare": rel(w_pre),
        "decoy_events": rec_ev["event_type"].value_counts().reindex(
            ["cold", "gut_infection", "stress", "nsaid_course", "antibiotic_course", "symptom_spike_without_inflammation"]).fillna(0).astype(int).to_dict(),
    }


def write(out, out_dir, fmt):
    out_dir = Path(out_dir)
    (out_dir / "ground_truth").mkdir(parents=True, exist_ok=True)
    ext = "parquet" if fmt == "parquet" or (fmt == "auto" and _has_parquet()) else "csv"
    save = lambda df, name: (df.to_parquet(out_dir / f"{name}.parquet", index=False) if ext == "parquet"
                             else df.to_csv(out_dir / f"{name}.csv", index=False))
    out["patients"].to_csv(out_dir / "patients.csv", index=False)
    out["conditions"].to_csv(out_dir / "conditions.csv", index=False)
    out["events"].to_csv(out_dir / "events.csv", index=False)
    out["scenarios"].to_csv(out_dir / "demo_scenarios.csv", index=False)
    for name in ["wearables_daily", "wearables_hourly_demo", "labs", "symptoms", "sweat"]:
        save(out[name], name)
    save(out["latent_daily"], "ground_truth/latent_daily")
    out["hidden_params"].to_csv(out_dir / "ground_truth/hidden_params.csv", index=False)
    return ext


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n-patients", type=int, default=800)
    ap.add_argument("--days", type=int, default=365, help="length of the wearable record")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--end-date", default="2026-09-30", help='last day of the record ("today" in the dashboard)')
    ap.add_argument("--out", default="data/synthetic")
    ap.add_argument("--format", choices=["auto", "parquet", "csv"], default="auto")
    args = ap.parse_args()

    t0 = time.time()
    out = generate(args.n_patients, args.days, args.seed, args.end_date)
    ext = write(out, args.out, args.format)
    summary = summarize(out)
    manifest = {
        "generator": "src.generator", "seed": args.seed, "n_patients": args.n_patients, "record_days": args.days,
        "record_start": str(out["meta"]["dates"][out["meta"]["burn"]].date()), "record_end": args.end_date,
        "table_format": ext, "flare_threshold_inflammation": FLARE_THRESHOLD,
        "symptom_flare_threshold": SYMPTOM_FLARE_THRESHOLD, "label_horizon_days": HORIZON,
        "sweat_stream": "INVESTIGATIONAL - simulated only, not an approved device",
        "summary": summary,
    }
    Path(args.out, "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    print(json.dumps(summary, indent=2))
    print(f"\nWrote {ext.upper()} tables to {Path(args.out).resolve()} in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
