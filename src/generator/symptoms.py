"""Daily symptom check-in from the patient app (brief §6.6).

Symptoms follow a lagged (~1–2 week) copy of inflammation, scaled by each
patient's symptom sensitivity, so they appear late in the pre-flare ramp.
Mismatch cases: "silent" patients (low sensitivity) and IBS overlap (symptoms
without inflammation). Partial Mayo (UC, 0–9) and Harvey-Bradshaw (CD) are derived.
"""
import numpy as np
import pandas as pd

from .scenarios import overlay_windows

SYMPTOM_FLARE_THRESHOLD = {"UC": 5, "CD": 8}  # partial Mayo ≥ 5, HBI ≥ 8


def _ema(x, alpha):
    out = np.empty_like(x)
    out[:, 0] = x[:, 0]
    for t in range(1, x.shape[1]):
        out[:, t] = alpha * x[:, t] + (1 - alpha) * out[:, t - 1]
    return out


def simulate_symptoms(patients, hidden, I, ctx, overlays, rng):
    P, D = I.shape
    col = lambda c: hidden[c].to_numpy(dtype=float)[:, None]
    uc = (patients["ibd_type"].to_numpy() == "UC")[:, None]
    colonic = uc | np.isin(patients["disease_extent"].to_numpy(), ["L2 colonic", "L3 ileocolonic"])[:, None]
    perianal = patients["perianal_disease"].to_numpy(dtype=bool)[:, None]
    stoma = patients["stoma"].to_numpy(dtype=bool)[:, None]
    f = lambda k: ctx[k].astype(float)
    cold, gut, stress = f("cold"), f("gut_infection"), f("stress")

    ibs = np.zeros((P, D))
    for i in np.flatnonzero(hidden["ibs_overlap"].to_numpy()):
        for _ in range(rng.poisson(6 * D / 365)):
            s = int(rng.integers(0, D))
            ibs[i, s:s + int(rng.integers(2, 6))] = 1

    lagged = _ema(I, 0.12)
    drive = np.clip((lagged - 0.3) / 0.6, 0, 2) * col("symptom_sensitivity")
    drive = np.where(stoma, 0, drive)
    N = lambda sd: rng.normal(0, sd, (P, D))

    stools = rng.poisson(np.clip(col("normal_stools") + np.where(uc, 5.5, 3.5) * drive + 4 * gut + 2 * ibs, 0.1, None)).astype(float)
    p_blood = np.where(uc, 0.02 + 0.55 * drive, 0.005 + 0.2 * drive * colonic) + 0.15 * gut
    blood = rng.random((P, D)) < np.clip(np.where(stoma, 0, p_blood), 0, 0.97)
    urgency = np.clip(np.round(1.6 * drive + 1.2 * gut + 0.8 * ibs + N(0.4)), 0, 3)
    pain = np.clip(np.round(0.8 + np.where(uc, 2.5, 4.5) * drive + 4 * gut + 3 * ibs + N(1.0)), 0, 10)
    fatigue = np.clip(np.round(2 + 3.5 * drive + 2.5 * cold + 1.2 * stress + N(1.2)), 0, 10)
    mood = np.clip(np.round(7.2 - 2 * drive - 2 * stress - 0.8 * cold + N(1.0)), 0, 10)
    wellbeing = np.clip(np.round(1.6 * drive + 0.8 * cold + 0.5 * ibs + 0.8 * gut + N(0.45)), 0, 4)
    joint_pain = rng.random((P, D)) < 0.03 + 0.15 * drive
    fever = (cold > 0) & (rng.random((P, D)) < 0.4)
    vomiting = (gut > 0) & (rng.random((P, D)) < 0.3)
    flags = {k: np.zeros((P, D), dtype=bool) for k in ["night_sweats", "breathlessness", "dizziness", "no_stool_or_gas"]}
    temp = np.where(fever, rng.uniform(37.8, 38.6, (P, D)), np.nan)
    weight_off = np.zeros((P, D))

    def window(kind):
        for i, a, b, extra in overlay_windows(overlays, kind):
            yield i, slice(a, b), b - a, extra

    for i, s, n, _ in window("acute_severe_colitis"):
        stools[i, s] = rng.integers(8, 13, n)
        blood[i, s], urgency[i, s], wellbeing[i, s] = True, 3, 4
        pain[i, s], fatigue[i, s] = rng.integers(6, 9, n), 8
        temp[i, s] = rng.uniform(38.3, 38.9, n)
    for i, s, n, _ in window("vte"):
        flags["breathlessness"][i, s] = True
        fatigue[i, s] = np.minimum(fatigue[i, s] + 2, 10)
    for i, s, n, _ in window("sepsis"):
        temp[i, s] = rng.uniform(38.8, 39.5, n)
        pain[i, s], wellbeing[i, s] = 7, 4
    for i, s, n, _ in window("bowel_obstruction"):
        vomiting[i, s], flags["no_stool_or_gas"][i, s] = True, True
        stools[i, s], pain[i, s] = 0, rng.integers(8, 10, n)
    for i, s, n, _ in window("stoma_dehydration"):
        stools[i, s] = rng.integers(14, 19, n)  # stoma bag emptyings
        flags["dizziness"][i, s] = True
    for i, s, n, _ in window("tb_reactivation"):
        ramp = np.linspace(0, 1, n)
        temp[i, s] = np.where(rng.random(n) < 0.7 * ramp + 0.1, rng.uniform(37.6, 38.1, n), np.nan)
        flags["night_sweats"][i, s] = rng.random(n) < 0.6 * ramp + 0.05
        fatigue[i, s] = np.minimum(fatigue[i, s] + np.round(3 * ramp), 10)
        weight_off[i, s] -= 4 * ramp
    for i, s, n, _ in window("crc_red_flags"):
        blood[i, s] |= rng.random(n) < 0.25  # bleeding while otherwise in remission
        stools[i, s] += rng.poisson(1.5, n)  # changed bowel habit
        weight_off[i, s] -= 5 * np.linspace(0, 1, n)
    for i, s, n, extra in window("weight_loss"):
        weight_off[i, s] -= extra["kg"] * np.linspace(0, 1, n)

    # Derived activity indices
    excess = stools - col("normal_stools")
    stool_sub = np.digitize(excess, [0.5, 2.5, 4.5])
    bleed_sub = np.where(blood, np.where(drive < 0.6, 1, np.where(drive < 1.3, 2, 3)), 0)
    pga = np.clip(np.round(wellbeing * 0.75), 0, 3)
    pmayo = stool_sub + bleed_sub + pga
    liquid = rng.binomial(stools.astype(int), np.clip(0.1 + 0.6 * drive + 0.5 * gut, 0, 1))
    complications = joint_pain.astype(int) + (perianal & (drive > 0.6)) + (rng.random((P, D)) < 0.05 * drive)
    hbi = wellbeing + np.clip(np.round(pain / 3), 0, 3) + liquid + complications
    score = np.where(uc, pmayo, hbi).astype(float)

    weight = (patients["weight_kg"].to_numpy(dtype=float)[:, None] - 2.0 * _ema(np.clip(I - col("base_inflammation"), 0, None), 0.03)
              + weight_off + N(0.35))

    # What the patient actually submits
    checked_in = rng.random((P, D)) < np.clip(col("checkin_compliance") + 0.15 * drive, 0, 0.99)
    for kind in ["acute_severe_colitis", "vte", "sepsis", "bowel_obstruction", "stoma_dehydration"]:
        for i, s, n, _ in window(kind):
            checked_in[i, s] = True
    weighed = rng.random((P, D)) < 0.6 / 7

    fields = {
        "stool_frequency": stools, "blood_in_stool": blood, "urgency_0_3": urgency, "abdominal_pain_0_10": pain,
        "fatigue_0_10": fatigue, "mood_0_10": mood, "general_wellbeing_0_4": wellbeing, "joint_pain": joint_pain,
        "body_temp_c": np.round(temp, 1), "vomiting": vomiting, **flags,
        "weight_kg": np.where(weighed, np.round(weight, 1), np.nan),
        "partial_mayo": np.where(uc, pmayo, np.nan), "harvey_bradshaw": np.where(uc, np.nan, hbi),
    }
    return fields, checked_in, score
