"""Ground-truth flare onsets, daily labels and the events table (brief §5, §6.9).

Per episode:
  inflammatory_flare_onset – first day latent inflammation ≥ FLARE_THRESHOLD
  symptomatic_flare_onset  – first day the 3-day mean symptom index (partial Mayo / HBI) ≥ threshold
  flare_onset (primary)    – first day both hold
flare_within_14d[t] = 1 if a flare onset falls in days t+1 … t+14 (NaN where that window
runs past the end of the record).
"""
import numpy as np
import pandas as pd

from .latent import FLARE_THRESHOLD
from .symptoms import SYMPTOM_FLARE_THRESHOLD

HORIZON = 14
DECOY_EVENTS = ["cold", "gut_infection", "stress", "nsaid", "antibiotic"]


def _runs(flag):
    """[(start, end_exclusive)] of contiguous True runs."""
    d = np.diff(np.concatenate([[0], flag.astype(int), [0]]))
    return list(zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)))


def _within(onsets, horizon):
    """1 if an onset falls in t+1 … t+horizon; NaN if none seen but the window is cut off by the record end."""
    P, D = onsets.shape
    c = np.concatenate([np.zeros((P, 1)), np.cumsum(onsets, axis=1)], axis=1)
    t = np.arange(D)
    hit = (c[:, np.minimum(t + horizon + 1, D)] - c[:, np.minimum(t + 1, D)]) > 0
    truncated = (t + horizon >= D)[None, :]
    return np.where(hit, 1.0, np.where(truncated, np.nan, 0.0))


def _days_to_next(onsets):
    P, D = onsets.shape
    out = np.full((P, D), np.nan)
    nxt = np.full(P, np.nan)
    for t in range(D - 1, -1, -1):
        out[:, t] = nxt - t
        nxt = np.where(onsets[:, t], t, nxt)
    return out


def label_episodes(patients, I, score, episodes):
    P, D = I.shape
    thr = np.array([SYMPTOM_FLARE_THRESHOLD[t] for t in patients["ibd_type"]])[:, None]
    sym3 = pd.DataFrame(score.T).rolling(3, min_periods=1).mean().to_numpy().T
    symptomatic_day = sym3 >= thr
    inflamed_day = I >= FLARE_THRESHOLD
    onset = {k: np.zeros((P, D), dtype=bool) for k in ["flare", "inflammatory", "symptomatic"]}
    in_flare = np.zeros((P, D), dtype=bool)
    for ep in episodes:
        i, a, b = ep["patient_idx"], ep["ramp_start"], min(ep["end"], D)
        first = lambda m: (a + int(np.argmax(m))) if m.any() else None
        ep["inflammatory_onset"] = first(inflamed_day[i, a:b])
        ep["symptomatic_onset"] = first(symptomatic_day[i, a:b])
        ep["flare_onset"] = first(inflamed_day[i, a:b] & symptomatic_day[i, a:b])
        for key, k in [("flare_onset", "flare"), ("inflammatory_onset", "inflammatory"), ("symptomatic_onset", "symptomatic")]:
            if ep[key] is not None:
                onset[k][i, ep[key]] = True
        start = ep["flare_onset"] if ep["flare_onset"] is not None else ep["inflammatory_onset"]
        if start is not None:
            in_flare[i, start:b] = True
    labels = {
        "flare_onset": onset["flare"].astype(int),
        "flare_within_14d": _within(onset["flare"], HORIZON),
        "inflammatory_flare_within_14d": _within(onset["inflammatory"], HORIZON),
        "symptomatic_flare_within_14d": _within(onset["symptomatic"], HORIZON),
        "days_to_next_flare": _days_to_next(onset["flare"]),
        "in_flare": in_flare,
    }
    return labels, symptomatic_day


def build_events(patients, ctx, overlays, episodes, symptomatic_day, episode_mask, dates, burn):
    ids = patients["patient_id"].to_numpy()
    D = len(dates)
    day = lambda t: dates[min(int(t), D - 1)] if t is not None else pd.NaT
    rows = []
    add = lambda i, kind, a, b=None, detail="": rows.append((ids[i], kind, day(a), day(b) if b is not None else pd.NaT, detail))

    for ep in episodes:
        i = ep["patient_idx"]
        tag = f"source={ep['tag']}; peak_inflammation={ep['peak']:.2f}"
        if ep["subclinical"]:
            add(i, "subclinical_inflammation", ep["ramp_start"], ep["end"] - 1, tag)
            continue
        add(i, "flare_ramp_start", ep["ramp_start"], ep["ramp_end"] - 1, tag)
        if ep["averted"]:
            add(i, "flare_averted", ep["ramp_end"], ep["end"] - 1, tag)
        for key, kind in [("inflammatory_onset", "inflammatory_flare_onset"),
                          ("symptomatic_onset", "symptomatic_flare_onset"), ("flare_onset", "flare_onset")]:
            if ep[key] is not None:
                add(i, kind, ep[key], None, tag)
        if not ep["averted"]:
            add(i, "flare_resolved", ep["end"] - 1)
        if ep["steroid_start"] is not None:
            add(i, "steroid_course", ep["steroid_start"], ep["steroid_start"] + 55, "prednisolone taper, 8 weeks")
            add(i, "steroid_taper_end", ep["steroid_start"] + 56)
        if ep["escalated_day"] is not None:
            add(i, "therapy_optimised" if ep["averted"] else "therapy_escalated", ep["escalated_day"])

    for kind in DECOY_EVENTS:
        for i in range(len(ids)):
            for a, b in _runs(ctx[kind][i]):
                add(i, kind if kind in ("cold", "gut_infection", "stress") else f"{kind}_course", a, b - 1, "decoy/context")

    for i, kind, a, b, _ in overlays:
        if kind in ("acute_severe_colitis", "vte", "sepsis", "bowel_obstruction", "stoma_dehydration"):
            add(i, f"emergency_{kind}", a, b - 1, "seeded demo scenario")
            if kind == "acute_severe_colitis":
                add(i, "hospital_admission", a + 1, b + 3, "IV steroids")
        elif kind in ("crc_red_flags", "tb_reactivation"):
            add(i, f"red_flag_{kind}", a, b - 1, "seeded demo scenario")

    # Symptom spikes with no inflammatory episode behind them (IBS overlap, gastroenteritis)
    for i in range(len(ids)):
        for a, b in _runs(symptomatic_day[i] & ~episode_mask[i]):
            add(i, "symptom_spike_without_inflammation", a, b - 1, "decoy")

    ev = pd.DataFrame(rows, columns=["patient_id", "event_type", "start_date", "end_date", "details"])
    ev["in_record"] = ev["end_date"].fillna(ev["start_date"]) >= dates[burn]
    return ev.sort_values(["patient_id", "start_date", "event_type"]).reset_index(drop=True)
