"""Periodic lab results (brief §6.5).

Routine clinic panels every 1–3 months (longer for rural patients), plus
"smart escalation": a home faecal calprotectin test when symptoms or wearable
drift look worrying, and a clinic follow-up when that home test comes back high.
"""
import numpy as np
import pandas as pd

from .latent import _recent
from .symptoms import SYMPTOM_FLARE_THRESHOLD

UNITS = {
    "faecal_calprotectin": "ug/g", "crp": "mg/L", "haemoglobin": "g/dL", "ferritin": "ng/mL",
    "albumin": "g/dL", "platelets": "10^9/L", "wbc": "10^9/L", "alp": "U/L", "ggt": "U/L",
    "bilirubin": "mg/dL", "ca19_9": "U/mL", "anti_tnf_trough": "ug/mL", "creatinine": "mg/dL", "sodium": "mmol/L",
}
EMERGENCIES = ["acute_severe_colitis", "vte", "sepsis", "bowel_obstruction", "stoma_dehydration"]


def simulate_labs(patients, hidden, I, ctx, overlays, score, wear, dates, burn, rng):
    P, D = I.shape
    rows = []
    chronic = np.stack([np.convolve(I[i], np.ones(60) / 60)[:D] for i in range(P)])  # trailing 60-day mean
    bleed_like = np.stack([np.convolve(np.clip(I[i] - 0.5, 0, None), np.ones(45) / 45)[:D] for i in range(P)])
    by_patient = {}
    for i, kind, a, b, extra in overlays:
        by_patient.setdefault(i, []).append((kind, a, b, extra))

    for i, (pat, hid) in enumerate(zip(patients.to_dict("records"), hidden.to_dict("records"))):
        pid = pat["patient_id"]
        uc = pat["ibd_type"] == "UC"
        ov = by_patient.get(i, [])
        nsaid7, gut7 = _recent(ctx["nsaid"][i], 7) | ctx["nsaid"][i], _recent(ctx["gut_infection"][i], 7) | ctx["gut_infection"][i]
        fc_base = (35 if pat["age"] > 60 else 25) * rng.lognormal(0, 0.3)
        crp_base = 1.5 * rng.lognormal(0, 0.5)
        trough_base = 6 * pat["medication_adherence"] ** 2 * rng.lognormal(0, 0.3)

        def active(kind, t):
            return [(a, b, e) for k, a, b, e in ov if k == kind and a <= t < b]

        def calprotectin(t, home):
            v = fc_base + 850 * I[i, t] ** 1.7 * hid["fc_coupling"] * rng.lognormal(0, 0.35 if uc else 0.5)
            v += rng.uniform(80, 250) if nsaid7[t] else 0
            v += rng.uniform(200, 700) if gut7[t] else 0
            v *= 1.25 if pat["ppi_use"] else 1
            if active("crc_red_flags", t):
                v += rng.uniform(300, 550)  # persistent FC despite therapy
            if active("acute_severe_colitis", t):
                v = max(v, rng.uniform(1500, 2800))
            return float(np.clip(v, 30, 1000) if home else np.clip(v, 10, 3000))

        def panel(t, setting, reason):
            out = {}
            if setting == "home" or rng.random() < 0.85:
                out["faecal_calprotectin"] = calprotectin(t, setting == "home")
            if setting == "home":
                return out
            cold, gut, steroid = ctx["cold"][i, t], gut7[t], ctx["steroid"][i, t]
            crp = crp_base * rng.lognormal(0, 0.3) + 45 * I[i, t] ** 2 * hid["crp_responder"]
            crp += rng.uniform(5, 20) * cold + rng.uniform(15, 60) * gut
            hb = hid["hb_base"] - 2.2 * chronic[i, t] - 3 * bleed_like[i, t] + rng.normal(0, 0.3)
            ferritin = hid["ferritin_base"] * (1 - 0.6 * min(bleed_like[i, t] * 3, 0.8)) + 150 * I[i, t]
            ferritin *= rng.lognormal(0, 0.2)
            wbc = 6.8 + 3 * I[i, t] + 2.5 * steroid + 3 * (cold or gut) + rng.normal(0, 0.8)
            wbc -= 1.5 if pat["current_medication"] == "thiopurine" else 0
            albumin = 4.4 - 0.9 * I[i, t] + rng.normal(0, 0.15)
            platelets = 260 + 200 * I[i, t] + rng.normal(0, 30)

            for a, b, e in active("hb_decline", t) + active("crc_red_flags", t):
                frac = (t - a) / max(b - a - 1, 1)
                start = e.get("from", e.get("hb_from"))
                end = e.get("to", e.get("hb_to"))
                hb = start + (end - start) * frac + rng.normal(0, 0.15)
                if active("crc_red_flags", t):
                    ferritin = min(ferritin, rng.uniform(6, 15))
            if active("acute_severe_colitis", t):
                crp, albumin = rng.uniform(60, 150), rng.uniform(2.5, 3.0)
            if active("sepsis", t):
                crp, wbc = rng.uniform(180, 260), rng.uniform(17, 21)
            if active("tb_reactivation", t):
                crp = rng.uniform(15, 40)
            out.update(crp=crp, haemoglobin=hb, ferritin=ferritin, albumin=albumin, platelets=platelets, wbc=wbc)
            if pat["psc_flag"]:
                prog = t / D
                out.update(alp=rng.uniform(250, 420) * (1 + 0.3 * prog), ggt=rng.uniform(150, 350) * (1 + 0.3 * prog),
                           bilirubin=rng.uniform(0.8, 1.8) * (1 + 0.4 * prog))
                if reason == "routine" and rng.random() < 0.3:
                    out["ca19_9"] = rng.uniform(10, 38)
            if pat["current_medication"] == "anti-TNF" and rng.random() < 0.4:
                out["anti_tnf_trough"] = trough_base * rng.lognormal(0, 0.25)
            if pat["stoma"]:
                out.update(creatinine=rng.uniform(0.75, 1.05), sodium=rng.uniform(136, 142))
                if active("stoma_dehydration", t):
                    out.update(creatinine=rng.uniform(1.8, 2.4), sodium=rng.uniform(129, 132))
            return out

        def emit(t, setting, reason, values=None):
            for test, v in (values or panel(t, setting, reason)).items():
                rows.append((pid, dates[t], test, round(float(v), 2), UNITS[test], setting, reason))

        # Routine clinic visits across the whole timeline (burn-in = historical labs)
        t = int(rng.integers(0, int(hid["lab_interval_days"])))
        while t < D:
            emit(t, "clinic", "routine")
            t += int(hid["lab_interval_days"] * rng.uniform(0.8, 1.2))

        # Emergency presentations and scripted demo tests
        for kind, a, b, e in ov:
            if kind in EMERGENCIES:
                emit(min(a + 1, D - 1), "emergency", kind)
            elif kind == "forced_home_fc":
                emit(a, "home", "twin_escalation", {"faecal_calprotectin": e["value"]})
            elif kind == "followup_clinic_labs":
                emit(a, "clinic", "follow_up")
        if any(k in ("forced_home_fc",) for k, *_ in ov):
            continue  # demo patient: no random escalations

        # Smart escalation during the wearable record
        thr = SYMPTOM_FLARE_THRESHOLD[pat["ibd_type"]] - 2
        sym3 = pd.Series(score[i]).rolling(3, min_periods=1).mean().to_numpy()
        rhr7 = pd.Series(wear["resting_hr_bpm"][i]).rolling(7, min_periods=4).mean().to_numpy()
        hrv7 = pd.Series(wear["hrv_rmssd_ms"][i]).rolling(7, min_periods=4).mean().to_numpy()
        wear_flag = (rhr7 > hid["rhr_base"] + 4) & ((hrv7 < 0.85 * hid["rmssd_base"]) | np.isnan(hrv7))
        last_fc = -999
        for t in range(burn, D - 3):
            if t - last_fc < 21:
                continue
            reason = "symptom_triggered" if sym3[t] >= thr else "twin_escalation" if wear_flag[t] else None
            if reason and rng.random() < 0.35:
                td = t + int(rng.integers(1, 4))
                vals = panel(td, "home", reason)
                emit(td, "home", reason, vals)
                last_fc = td
                follow = td + int(rng.integers(7, 15))
                if vals["faecal_calprotectin"] > 250 and follow < D:
                    emit(follow, "clinic", "follow_up")

    labs = pd.DataFrame(rows, columns=["patient_id", "date", "test", "value", "unit", "setting", "reason"])
    return labs.sort_values(["patient_id", "date", "test"]).reset_index(drop=True)
