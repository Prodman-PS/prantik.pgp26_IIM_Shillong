"""Cancer Safety panel — surveillance support, NOT cancer detection.

CRC surveillance risk follows the BSG 2019 / ECCO structure (CLAUDE.md §9.2), plus the
twin-specific cumulative inflammation burden (months with calprotectin > 250):
  high   → colonoscopy every 1 year   (PSC, dysplasia, stricture, active moderate inflammation, FH CRC)
  medium → every 3 years              (mild active inflammation, pseudopolyps, high burden / many flares)
  low    → every 5 years
Surveillance starts 8 years after diagnosis (at diagnosis for PSC); proctitis alone is excluded.
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

INTERVAL_YEARS = {"high": 1, "medium": 3, "low": 5}
LEVELS = ["low", "medium", "high"]


@dataclass
class CancerSafety:
    risk_level: str
    reasons: list
    surveillance_applies: bool
    interval_years: int | None
    last_colonoscopy: pd.Timestamp | None
    next_due: pd.Timestamp | None
    overdue: bool
    months_to_due: float | None
    red_flags: list = field(default_factory=list)
    screening: list = field(default_factory=list)
    label: str = "Surveillance support, not cancer detection"


def _b(v):
    return str(v).lower() == "true" if not isinstance(v, (bool, np.bool_)) else bool(v)


def crc_risk(p: pd.Series, day: pd.Series):
    """p: patients.csv row. day: daily-frame row for the date being viewed."""
    reasons, level = [], "low"
    bump = lambda lv, why: (reasons.append(why), max(level, lv, key=LEVELS.index))[1]
    extensive = p["disease_extent"] in ("E3 pancolitis", "L2 colonic", "L3 ileocolonic")
    fc = day.get("l_fc_last", np.nan)
    if _b(p["psc_flag"]):
        level = bump("high", "Primary sclerosing cholangitis")
    if _b(p["prior_dysplasia"]):
        level = bump("high", "Prior dysplasia")
    if _b(p["stricture_flag"]) and extensive:
        level = bump("high", "Colonic stricture")
    if _b(p["family_history_crc"]):
        level = bump("high", "Family history of colorectal cancer")
    if extensive and pd.notna(fc) and fc > 250:
        level = bump("high", f"Extensive colitis with active inflammation (calprotectin {fc:.0f})")
    elif extensive and pd.notna(fc) and fc > 100:
        level = bump("medium", f"Extensive colitis with mild activity (calprotectin {fc:.0f})")
    if _b(p["pseudopolyps_flag"]):
        level = bump("medium", "Post-inflammatory polyps")
    burden = day.get("l_fc_burden_months", 0) or 0
    if burden >= 3:
        level = bump("medium", f"Cumulative inflammation burden: {burden:.0f} months with calprotectin > 250")
    if (p.get("past_flares_count", 0) or 0) >= 5:
        level = bump("medium", f"{int(p['past_flares_count'])} past flares (high lifetime inflammation)")
    if not reasons:
        reasons.append("No high-risk features; " + ("extensive" if extensive else "limited") + " disease")
    return level, reasons


def red_flags(day: pd.Series, risk=None):
    """CRC red flags are read in the context of otherwise quiet disease (symptoms below
    60% of the flare threshold): the same findings during an active flare are expected."""
    f = []
    quiet_symptoms = pd.notna(day.get("s_index_mean7")) and day["s_index_mean7"] < 0.6
    if not quiet_symptoms:
        return f
    if day.get("l_fc_two_consec_high", 0) > 0:
        f.append("Calprotectin persistently > 250 on consecutive tests")
    if day.get("l_hb_trend90", 0) <= -1.0 and day.get("l_hb_last", 99) < 12.5:
        f.append(f"Haemoglobin falling ({day['l_hb_trend90']:+.1f} g/dL over 3 months)")
    if pd.notna(day.get("l_ferritin_delta")) and day["l_ferritin_delta"] <= -30 and day.get("l_ferritin_last", 999) < 50:
        f.append(f"Ferritin falling (now {day['l_ferritin_last']:.0f} ng/mL)")
    wl = day.get("s_weight_change90", np.nan)
    if pd.notna(wl) and wl <= -3.0:
        f.append(f"Unexplained weight loss ({wl:+.1f} kg over 3 months)")
    if day.get("blood_days14", 0) >= 3:
        f.append("Rectal bleeding while otherwise in remission")
    labs_worse = (day.get("l_fc_last", 0) or 0) > 250 or (day.get("l_hb_trend90", 0) or 0) <= -1.0
    wear_stable = all(abs(day.get(c, 0) if pd.notna(day.get(c, 0)) else 0) < 1.0
                      for c in ("w_rhr_z_mean7", "w_hrv_z_mean7", "w_steps_z_mean7"))
    if labs_worse and wear_stable and (risk is None or risk < 0.2):
        f.append("Mismatch: labs worsening while wearables and flare risk stay stable")
    return f


def screening_tracker(p: pd.Series, today: pd.Timestamp):
    out = []
    med = p["current_medication"]
    immuno = med in ("thiopurine", "anti-TNF", "vedolizumab", "steroid")

    def due(last, years):
        last = pd.to_datetime(last) if pd.notna(last) and str(last) not in ("", "nan") else None
        if last is None:
            return "Never recorded", True
        nxt = last + pd.DateOffset(years=years)
        return f"Due {nxt:%b %Y}" + (" (overdue)" if nxt < today else ""), nxt < today

    if med in ("thiopurine", "anti-TNF"):
        s, od = due(p.get("last_skin_check"), 1)
        out.append({"item": "Skin check (thiopurine / anti-TNF)", "status": s, "overdue": od})
    if p["sex"] == "F" and 25 <= p["age"] <= 65 and immuno:
        s, od = due(p.get("hpv_screen_date"), 3)
        out.append({"item": "Cervical / HPV screen (immunosuppressed)", "status": s, "overdue": od})
    if _b(p["psc_flag"]):
        out.append({"item": "PSC: liver tests 6-monthly + yearly imaging (bile-duct cancer)", "status": "Track ALP/GGT trend",
                    "overdue": False})
    if med == "anti-TNF":
        tb = str(p.get("tb_screening_status", ""))
        ok = tb.startswith("IGRA negative")
        out.append({"item": "TB screening before / on anti-TNF", "status": tb or "not documented", "overdue": not ok})
    if med == "thiopurine":
        out.append({"item": "Lymphoma awareness (thiopurine)", "status": "Ask about fevers, sweats, nodes", "overdue": False})
    return out


def cancer_safety(p: pd.Series, day: pd.Series, today, risk=None) -> CancerSafety:
    today = pd.Timestamp(today)
    level, reasons = crc_risk(p, day)
    psc = _b(p["psc_flag"])
    applies = psc or (p["years_since_diagnosis"] >= 8 and p["disease_extent"] != "E1 proctitis")
    last = pd.to_datetime(p["last_colonoscopy_date"]) if pd.notna(p["last_colonoscopy_date"]) else None
    if not applies:
        start = "8 years after diagnosis" if p["disease_extent"] != "E1 proctitis" else "not needed for proctitis alone"
        return CancerSafety(level, reasons + [f"Surveillance starts {start}"], False, None, last, None, False, None,
                            red_flags(day, risk), screening_tracker(p, today))
    interval = 1 if psc else INTERVAL_YEARS[level]
    nxt = (last + pd.DateOffset(years=interval)) if last is not None else today
    months = (nxt - today).days / 30.44
    return CancerSafety(level, reasons, True, interval, last, nxt, nxt < today, months,
                        red_flags(day, risk), screening_tracker(p, today))
