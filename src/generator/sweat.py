"""INVESTIGATIONAL simulated sweat-biosensor stream (brief §6.7; roadmap only).

Sweat-based inflammation sensors are not FDA-cleared or CDSCO-approved for IBD
monitoring. This stream exists only to quantify the *potential* value of a
continuous inflammation signal (ablation version C) and must stay optional.
sweat_x[t] = baseline + k * inflammation[t] + sensor drift[t] + noise[t].
"""
import numpy as np

MARKERS = {  # name: (baseline, k, noise sd, cold effect)
    "sweat_crp_ng_ml": (1.0, 6.0, 1.2, 1.5),
    "sweat_calprotectin_ng_ml": (40.0, 160.0, 30.0, 0.0),
    "sweat_il6_pg_ml": (2.0, 6.0, 1.5, 3.0),
    "sweat_tnf_alpha_pg_ml": (3.0, 5.0, 1.2, 0.5),
}


def simulate_sweat(hidden, I, ctx, wear_day, rng):
    P, D = I.shape
    cold = ctx["cold"].astype(float)
    has = hidden["has_sweat_sensor"].to_numpy(dtype=bool)
    out = {}
    for name, (base, k, sd, cold_k) in MARKERS.items():
        b = base * rng.lognormal(0, 0.25, (P, 1))
        drift = np.cumsum(rng.normal(0, 0.02 * base, (P, D)), axis=1)  # slow electrode drift
        out[name] = np.clip(b + k * I + drift + cold_k * cold + rng.normal(0, sd, (P, D)), 0, None).round(2)
    contact = rng.binomial(24, rng.uniform(0.75, 0.95, (P, 1)), (P, D))  # hourly readings with skin contact
    valid = has[:, None] & wear_day & (rng.random((P, D)) > rng.uniform(0.10, 0.20, (P, 1))) & (contact >= 6)
    for name in MARKERS:
        out[name] = np.where(valid, out[name], np.nan)
    out["hourly_readings"] = np.where(valid, contact, 0)
    return out, valid, has
