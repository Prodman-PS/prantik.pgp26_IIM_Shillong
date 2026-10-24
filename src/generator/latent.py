"""Hidden daily inflammation and life-context events (brief §6.3, decoys from §6.4).

inflammation[t] is the single latent variable every observed stream is drawn
from: 0 ≈ deep remission, ≥ FLARE_THRESHOLD = inflammatory flare, 1+ = severe.
Flares arrive by a Poisson process whose daily hazard is modulated by EHR risk
factors and recent context, and each one is preceded by an 8–12 week ramp.
"""
import numpy as np

FLARE_THRESHOLD = 0.6
CONTEXT = ["cold", "gut_infection", "stress", "nsaid", "antibiotic", "alcohol", "exercise", "steroid"]


def _recent(flag, window):
    """recent[t] = flag was true on any of days t-window … t-1 (strictly past)."""
    c = np.concatenate([[0], np.cumsum(flag)])
    t = np.arange(len(flag))
    return (c[t] - c[np.maximum(t - window, 0)]) > 0


def make_context(pat, hid, n_days, weekday, rng, quiet=()):
    ctx = {k: np.zeros(n_days, dtype=bool) for k in CONTEXT}

    def place(key, per_year, lo, hi):
        for _ in range(rng.poisson(per_year * n_days / 365)):
            s = int(rng.integers(0, n_days))
            ctx[key][s:s + int(rng.integers(lo, hi + 1))] = True

    place("cold", 2.0, 3, 7)  # viral URTI decoy: fever, HR up, HRV down, no calprotectin rise
    place("gut_infection", 0.35, 3, 6)  # gastroenteritis: calprotectin confounder + flare trigger
    place("stress", 3.0, 5, 10)
    place("nsaid", 3.0 if pat["nsaid_use"] else 0.3, 4, 10)
    place("antibiotic", 0.8, 5, 7)
    weekend_night = np.isin(weekday, [4, 5])
    p_alc = np.where(weekend_night, 0.4, 0.04) if hid["drinker"] else np.where(weekday == 5, 0.03, 0.0)
    ctx["alcohol"] = rng.random(n_days) < p_alc
    p_ex = (np.where(weekday >= 5, 0.6, 0.45) if hid["exercises"] else np.full(n_days, 0.08))
    ctx["exercise"] = rng.random(n_days) < p_ex
    if pat["current_medication"] == "steroid":  # steroid-dependent patients
        ctx["steroid"][:] = True
    for a, b in quiet:
        for k in CONTEXT:
            if k not in ("exercise", "steroid"):
                ctx[k][a:b] = False
    return ctx


def random_episode_spec(severity, rng):
    if rng.random() < 0.2:  # subclinical: inflammation rises then settles without a flare
        return {"ramp": int(rng.integers(28, 57)), "peak": rng.uniform(0.35, 0.55), "subclinical": True,
                "resolve": int(rng.integers(21, 43)), "curve": rng.uniform(1.6, 2.4)}
    return {"ramp": int(rng.integers(56, 85)),
            "peak": rng.uniform(0.8, 1.3) * (1.15 if severity == "severe" else 1.0),
            "plateau": int(rng.integers(14, 43)), "resolve": int(rng.integers(21, 57)),
            "curve": rng.uniform(1.6, 2.4), "subclinical": False,
            "steroid_delay": int(rng.integers(10, 21)) if rng.random() < 0.7 else None}


def episode_curve(base, spec, rng):
    """Excess inflammation above `base` for one episode, plus the ramp length actually used."""
    ramp = spec["ramp"]
    s = np.arange(1, ramp + 1) / ramp
    rise = (spec["peak"] - base) * s ** spec["curve"]
    if spec.get("truncate"):  # treatment stopped the ramp early (flare averted)
        rise = rise[:spec["truncate"]]
    top = rise[-1]
    parts = [rise]
    if not spec.get("subclinical") and not spec.get("truncate"):
        plateau = spec["plateau"]
        if spec.get("steroid_delay") is not None:
            plateau = min(plateau, spec["steroid_delay"] + int(rng.integers(7, 22)))
        parts.append(top * (1 + rng.normal(0, 0.04, plateau)))
    parts.append(top * np.linspace(1, 0, spec["resolve"] + 1)[1:] ** 1.5)
    return np.concatenate(parts), len(rise)


def simulate_latent(patients, hidden, n_days, years_at_end, weekday, rng, scripts):
    P = len(patients)
    I = np.zeros((P, n_days))
    phase = np.zeros((P, n_days), dtype=np.int8)  # 0 quiet, 1 ramp, 2 flare/plateau, 3 resolving, 4 subclinical
    ctx_all = {k: np.zeros((P, n_days), dtype=bool) for k in CONTEXT}
    episodes = []

    for i, (pat, hid) in enumerate(zip(patients.to_dict("records"), hidden.to_dict("records"))):
        script = scripts.get(i, {})
        ctx = make_context(pat, hid, n_days, weekday, rng, script.get("quiet", ()))
        base = hid["base_inflammation"]
        excess = np.zeros(n_days)
        rate_mult = 1.0
        recent = {k: _recent(ctx[k], w) for k, w in [("nsaid", 14), ("gut_infection", 30), ("antibiotic", 30)]}
        taper_until = -1

        fixed = (pat["past_flares_count"], pat["medication_adherence"])
        static_mult = ((1 + 0.06 * min(fixed[0], 10)) * (1 + 1.2 * (1 - fixed[1]))
                       * (1.5 if pat["ibd_type"] == "CD" and pat["smoking_status"] == "current" else 1)
                       * (1.2 if pat["ibd_type"] == "CD" and pat["nod2_variant"] else 1)
                       * (0.85 if pat["il23r_r381q_protective"] else 1))
        days_since_dx = years_at_end[i] * 365.25 - (n_days - 1 - np.arange(n_days))

        def add_episode(t, spec, tag):
            nonlocal taper_until, rate_mult
            if t >= n_days:
                return t
            curve, ramp_len = episode_curve(base, spec, rng)
            end = min(t + len(curve), n_days)
            excess[t:end] = np.maximum(excess[t:end], curve[:end - t])
            ep = {"patient_idx": i, "ramp_start": t, "ramp_end": t + ramp_len, "end": t + len(curve),
                  "peak": float(curve.max() + base), "subclinical": bool(spec.get("subclinical")),
                  "averted": bool(spec.get("truncate")), "tag": tag, "steroid_start": None, "escalated_day": None}
            ph = np.full(len(curve), 3, dtype=np.int8)
            ph[:ramp_len] = 1 if not spec.get("subclinical") else 4
            if not spec.get("subclinical") and not spec.get("truncate"):
                ph[ramp_len:ramp_len + (len(curve) - ramp_len - spec["resolve"])] = 2
            phase[i, t:end] = np.maximum(phase[i, t:end], ph[:end - t])
            if spec.get("steroid_delay") is not None:
                s0 = t + ramp_len + spec["steroid_delay"]
                ctx["steroid"][s0:min(s0 + 56, n_days)] = True
                ep["steroid_start"] = s0
                taper_until = s0 + 56 + 60
            if spec.get("therapy_optimised") is not None:
                ep["escalated_day"] = t + spec["therapy_optimised"]
            elif not ep["subclinical"] and rng.random() < 0.4:
                ep["escalated_day"] = t + len(curve)
                rate_mult *= 0.75
            episodes.append(ep)
            return t + len(curve)

        for start, spec in script.get("episodes", []):
            add_episode(start, spec, script.get("tag", "scripted"))

        t = 0
        while t < n_days and script.get("random_flares", True):
            if excess[t] > 0:
                t += 1
                continue
            hazard = hid["annual_flare_rate"] / 365 * static_mult * rate_mult
            hazard *= (1.4 if recent["nsaid"][t] else 1) * (2.0 if recent["gut_infection"][t] else 1)
            hazard *= (1.2 if recent["antibiotic"][t] else 1) * (2.0 if t <= taper_until else 1)
            hazard *= 1.8 if 0 <= days_since_dx[t] < 365 else 1
            if rng.random() < hazard:
                end = add_episode(t, random_episode_spec(pat["disease_severity"], rng), "random")
                t = end + 14  # refractory period
            else:
                t += 1

        noise = np.zeros(n_days)
        z = rng.normal(0, 0.012, n_days)
        for d in range(1, n_days):
            noise[d] = 0.7 * noise[d - 1] + z[d]
        I[i] = np.clip(base + excess + noise, 0, None)
        for k in CONTEXT:
            ctx_all[k][i] = ctx[k]

    return I, phase, ctx_all, episodes
