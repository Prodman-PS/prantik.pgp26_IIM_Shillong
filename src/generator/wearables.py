"""Daily consumer-wearable stream (brief §6.4) plus an hourly stream for demo patients.

Every signal = personal baseline + inflammation drift (scaled by the patient's
wearable responsiveness) + decoy effects + autocorrelated day-to-day noise.
Drift sizes are design assumptions from the brief, not measured effects.
"""
import numpy as np
import pandas as pd

from .scenarios import overlay_windows

# Devices that do not report a signal at all
NO_HRV = {"Noise ColorFit"}
NO_SKIN_TEMP = {"Noise ColorFit", "Amazfit", "Samsung Galaxy Watch"}


def _ar(rng, shape, sd, phi=0.6):
    z = rng.normal(0, sd * np.sqrt(1 - phi ** 2), shape)
    e = np.empty(shape)
    e[:, 0] = rng.normal(0, sd, shape[0])
    for t in range(1, shape[1]):
        e[:, t] = phi * e[:, t - 1] + z[:, t]
    return e


def _prev_day(x):
    return np.concatenate([np.zeros((x.shape[0], 1), dtype=x.dtype), x[:, :-1]], axis=1)


def simulate_wearables(patients, hidden, I, ctx, overlays, weekday, rng):
    P, D = I.shape
    col = lambda c: hidden[c].to_numpy(dtype=float)[:, None]
    r = col("wearable_responsiveness")
    d = np.clip((I - col("base_inflammation")) / 0.8, 0, 1.8)
    d1 = np.minimum(d, 1.2)
    f = lambda k: ctx[k].astype(float)
    cold, stress, steroid, ex = f("cold"), f("stress"), f("steroid"), f("exercise")
    alc = _prev_day(ctx["alcohol"]).astype(float)  # last night's drinking shows up today
    ex_prev = _prev_day(ctx["exercise"]).astype(float)
    weekend = (weekday >= 5)[None, :].astype(float)

    rhr = col("rhr_base") + 6.5 * r * d1 + 6 * cold + 2 * stress + 3 * alc + 2 * steroid + _ar(rng, (P, D), 1.3)
    rmssd = (col("rmssd_base") * (1 - 0.22 * r * d1).clip(0.4) * (1 - 0.25 * cold) * (1 - 0.12 * stress)
             * (1 - 0.18 * alc) * (1 + 0.05 * ex_prev) * np.exp(_ar(rng, (P, D), 0.09)))
    # Circadian flattening: daytime HRV creeps towards night-time HRV as inflammation rises.
    rmssd_day = rmssd * np.clip(0.68 + 0.15 * r * np.minimum(d, 1.0) + rng.normal(0, 0.03, (P, D)), 0.5, 0.97)
    steps = (col("steps_base") * (1 - 0.15 * weekend) * (1 - 0.30 * r * np.minimum(d, 1.3)).clip(0.3)
             * (1 - 0.35 * cold) * (1 - 0.12 * stress) * (1 + 0.6 * ex) * np.exp(_ar(rng, (P, D), 0.22, 0.3)))
    hr_mean = rhr + 9 + steps / 1000 * 1.1 + 2 * r * d + 3 * cold + _ar(rng, (P, D), 1.5, 0.3)
    spo2 = col("spo2_base") - 0.45 * r * d - 0.3 * cold + _ar(rng, (P, D), 0.35, 0.3)
    sleep_h = (col("sleep_base_h") + 0.45 * weekend - 0.45 * r * np.minimum(d, 1.5) - 0.5 * stress
               - 0.7 * alc - 0.4 * steroid + _ar(rng, (P, D), 0.55, 0.3))
    sleep_eff = (col("sleep_eff_base") - 0.045 * r * np.minimum(d, 1.5) - 0.03 * stress - 0.04 * alc
                 + _ar(rng, (P, D), 0.03, 0.3))
    awakenings = rng.poisson(np.clip(1.3 + 1.3 * d + 0.8 * alc + 0.5 * cold, 0.1, None)).astype(float)
    skin_temp = 0.25 * r * d + 0.7 * cold + _ar(rng, (P, D), 0.15, 0.5)
    resp = col("resp_rate_base") + 1.0 * r * d + 1.2 * cold + _ar(rng, (P, D), 0.4, 0.5)

    # Scenario signatures
    for kind, fn in {
        "acute_severe_colitis": lambda s: (np.maximum(rhr[s], rng.uniform(95, 110)), 1.3, 0.25, 0.6, 3, 0),
        "vte": lambda s: (rhr[s] + 22, 0.2, 0.08, 0.85, 5, -4),
        "sepsis": lambda s: (rhr[s] + 25, 1.8, 0.3, 0.45, 6, -1),
        "bowel_obstruction": lambda s: (rhr[s] + 12, 0.3, 0.2, 0.8, 2, 0),
        "stoma_dehydration": lambda s: (rhr[s] + 15, 0.1, 0.5, 0.85, 1.5, 0),
    }.items():
        for i, a, b, _ in overlay_windows(overlays, kind):
            s = (i, slice(a, b))
            new_rhr, temp, step_mult, hrv_mult, resp_add, spo2_add = fn(s)
            hr_mean[s] += new_rhr - rhr[s] + 8
            rhr[s] = new_rhr
            skin_temp[s] += temp
            steps[s] *= step_mult
            rmssd[s] *= hrv_mult
            rmssd_day[s] *= hrv_mult
            resp[s] += resp_add
            spo2[s] += spo2_add
            sleep_h[s] -= 1.5
    for i, a, b, _ in overlay_windows(overlays, "tb_reactivation"):
        ramp = np.linspace(0, 1, b - a)
        rhr[i, a:b] += 6 * ramp
        hr_mean[i, a:b] += 6 * ramp
        rmssd[i, a:b] *= 1 - 0.15 * ramp
        rmssd_day[i, a:b] *= 1 - 0.15 * ramp
        steps[i, a:b] *= 1 - 0.25 * ramp
        skin_temp[i, a:b] += 0.4 * ramp
        sleep_eff[i, a:b] -= 0.05 * ramp  # night sweats

    sleep_h = sleep_h.clip(2.5, 11)
    sleep_eff = sleep_eff.clip(0.5, 0.99)
    deep_frac = (0.17 * (1 - 0.2 * np.minimum(d, 1.5)) * (1 - 0.3 * alc) * rng.lognormal(0, 0.15, (P, D))).clip(0.05, 0.3)
    rem_frac = (0.22 * (1 - 0.1 * np.minimum(d, 1.5)) * (1 - 0.25 * alc) * rng.lognormal(0, 0.12, (P, D))).clip(0.08, 0.32)
    sleep_min = sleep_h * 60
    out = {
        "resting_hr_bpm": rhr.round(), "hr_mean_bpm": hr_mean.round(),
        "hrv_rmssd_ms": rmssd.round(1), "hrv_rmssd_day_ms": rmssd_day.round(1),
        "steps": np.round(steps.clip(0)), "spo2_pct": spo2.clip(85, 100).round(1),
        "sleep_duration_h": sleep_h.round(2), "sleep_efficiency": sleep_eff.round(3),
        "sleep_deep_min": (sleep_min * deep_frac).round(), "sleep_rem_min": (sleep_min * rem_frac).round(),
        "sleep_light_min": (sleep_min * (1 - deep_frac - rem_frac)).round(),
        "sleep_awake_min": (sleep_min / sleep_eff - sleep_min).round(),
        "night_awakenings": awakenings,
        "skin_temp_dev_c": skin_temp.round(2), "resp_rate_brpm": resp.round(1),
    }

    # Missingness: random non-wear days + multi-day gaps; device capability gaps.
    missing = rng.random((P, D)) < col("missing_rate")
    for i in range(P):
        for _ in range(rng.poisson(2.0 * D / 365)):
            s = int(rng.integers(0, D))
            missing[i, s:s + int(rng.integers(3, 15))] = True
    for kind in ["acute_severe_colitis", "vte", "sepsis", "bowel_obstruction", "stoma_dehydration"]:
        for i, a, b, _ in overlay_windows(overlays, kind):
            missing[i, a - 3:b] = False  # keep the demo signatures visible
    for k in out:
        out[k][missing] = np.nan
    device = patients["wearable_device"].to_numpy()
    for k in ["hrv_rmssd_ms", "hrv_rmssd_day_ms"]:
        out[k][np.isin(device, list(NO_HRV))] = np.nan
    out["skin_temp_dev_c"][np.isin(device, list(NO_SKIN_TEMP))] = np.nan
    out["spo2_pct"][rng.random((P, D)) < 0.15] = np.nan  # SpO2 only on some nights
    out["wear_day"] = ~missing
    return out


def hourly_for(patient_rows, rng):
    """Hourly HR / HRV / steps for a few demo patients, consistent with their daily values."""
    frames = []
    hours = np.arange(24)
    asleep = (hours < 7) | (hours >= 23)
    step_w = np.where(asleep, 0.0, 1.0) * (1 + 0.8 * np.isin(hours, [8, 9, 18, 19]))
    step_w = step_w / step_w.sum()
    for row in patient_rows.itertuples(index=False):
        rhr, hrm, hn, hd, st = row.resting_hr_bpm, row.hr_mean_bpm, row.hrv_rmssd_ms, row.hrv_rmssd_day_ms, row.steps
        if np.isnan(rhr):
            continue
        awake_hr = (24 * hrm - 8 * rhr) / 16
        hr = np.where(asleep, rhr + rng.normal(0, 1.5, 24), awake_hr + rng.normal(0, 4, 24) + 0.004 * st * step_w * 24)
        hrv = np.where(asleep, hn, hd) * rng.lognormal(0, 0.12, 24) if not np.isnan(hn) else np.full(24, np.nan)
        frames.append(pd.DataFrame({
            "patient_id": row.patient_id,
            "timestamp": pd.Timestamp(row.date) + pd.to_timedelta(hours, unit="h"),
            "heart_rate_bpm": hr.round(), "hrv_rmssd_ms": np.round(hrv, 1),
            "steps": np.round(st * step_w * rng.lognormal(0, 0.3, 24)),
            "asleep": asleep,
        }))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
