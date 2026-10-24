"""Seeded demo patients (brief §6.8 and the "Ananya" story in §10).

Each scenario rewrites a few EHR fields so the patient is clinically coherent,
scripts their inflammation episodes, and registers *overlays*: windows in which
the stream simulators apply the scenario's signature (e.g. RHR > 90 + fever +
bloody stools for acute severe colitis).
"""
import numpy as np
import pandas as pd

# scenario -> number of patients
SCENARIOS = {
    "ananya_demo": 1, "acute_severe_colitis": 3, "vte": 2, "sepsis_on_steroids": 2,
    "bowel_obstruction": 2, "stoma_dehydration": 2, "crc_red_flags": 3, "tb_reactivation": 2,
}


def _set(patients, hidden, i, **fields):
    for k, v in fields.items():
        if k in patients.columns:
            patients.loc[i, k] = v
        else:
            hidden.loc[i, k] = v


def assign_scenarios(patients, hidden, rng, burn, record_days, ref_date):
    """Mutates patients/hidden in place. Returns (scripts, overlays, roster).

    Day numbers inside scripts/overlays are absolute simulation days (burn-in included).
    """
    ref = pd.Timestamp(ref_date)
    R = lambda r: burn + r  # record day -> simulation day
    scripts, overlays, roster = {}, [], []
    idx = 0

    def flare(peak=1.0, ramp=63, plateau=21, resolve=35, steroid_delay=14, curve=2.0):
        return {"ramp": ramp, "peak": peak, "plateau": plateau, "resolve": resolve,
                "curve": curve, "steroid_delay": steroid_delay}

    for scenario, count in SCENARIOS.items():
        for _ in range(count):
            i = idx
            idx += 1
            roster.append((patients.loc[i, "patient_id"], scenario))

            if scenario == "ananya_demo":
                _set(patients, hidden, i, display_name="Ananya R.", age=28, sex="F", region="urban", state="Karnataka",
                     ibd_type="UC", disease_extent="E2 left-sided", cd_behaviour="", perianal_disease=False,
                     disease_severity="mild", age_at_diagnosis=17.0, years_since_diagnosis=11.0,
                     diagnostic_delay_months=7.0, prior_misdiagnosis_tb=False, past_flares_count=6,
                     hospitalisations=1, surgeries="none", stricture_flag=False, pseudopolyps_flag=False,
                     psc_flag=False, family_history_crc=False, smoking_status="never", nsaid_use=False,
                     ppi_use=False, current_medication="5-ASA", medication_adherence=0.72, prior_dysplasia=False,
                     # Medium CRC risk -> 3-yearly surveillance; due ~4 months after "today".
                     last_colonoscopy_date=(ref + pd.DateOffset(months=4) - pd.DateOffset(years=3)).normalize(),
                     tb_screening_status="not done", height_cm=158.0, weight_kg=52.5, bmi=21.0,
                     comorbidities="iron-deficiency anaemia", wearable_device="Apple Watch",
                     base_inflammation=0.05, rhr_base=64.0, rmssd_base=46.0, steps_base=8200.0,
                     wearable_responsiveness=1.6, symptom_sensitivity=1.0, ibs_overlap=False, crp_responder=0.3,
                     missing_rate=0.04, checkin_compliance=0.9, hb_base=12.8, has_sweat_sensor=True, drinker=False)
                # One real flare early in the year, then the averted one: the ramp starts at record day 283
                # and therapy is optimised on day 322 (week 5), so inflammation never reaches flare level.
                scripts[i] = {"tag": scenario, "random_flares": False, "quiet": [(R(286), R(345))],
                              "episodes": [(R(25), flare(peak=1.05, ramp=60)),
                                           (R(283), {"ramp": 56, "peak": 0.9, "curve": 1.6, "truncate": 39,
                                                     "resolve": 21, "therapy_optimised": 39})]}
                overlays += [(i, "hb_decline", R(275), R(record_days), {"from": 12.6, "to": 11.4}),
                             (i, "weight_loss", R(275), R(record_days), {"kg": 3.5}),
                             (i, "forced_home_fc", R(320), R(321), {"value": 310.0}),
                             (i, "followup_clinic_labs", R(352), R(353), {})]

            elif scenario == "acute_severe_colitis":
                yrs = rng.uniform(3, 12)
                _set(patients, hidden, i, ibd_type="UC", disease_extent="E3 pancolitis", cd_behaviour="",
                     perianal_disease=False, disease_severity="severe", years_since_diagnosis=round(yrs, 1),
                     age=int(patients.loc[i, "age_at_diagnosis"] + yrs), surgeries="none",
                     current_medication="thiopurine", crp_responder=1.0, fc_coupling=1.0)
                start = int(rng.integers(40, 230))
                scripts[i] = {"tag": scenario, "random_flares": False,
                              "episodes": [(R(start), flare(peak=1.7, ramp=56, plateau=24, resolve=45, steroid_delay=10))]}
                onset = R(start + 56)
                overlays.append((i, "acute_severe_colitis", onset + 8, onset + 15, {}))

            elif scenario == "vte":
                start = int(rng.integers(40, 240))
                _set(patients, hidden, i, disease_severity="moderate")
                scripts[i] = {"tag": scenario, "random_flares": False,
                              "episodes": [(R(start), flare(peak=1.2, ramp=60, plateau=30))]}
                onset = R(start + 60)
                overlays.append((i, "vte", onset + 16, onset + 20, {}))

            elif scenario == "sepsis_on_steroids":
                start = int(rng.integers(40, 220))
                _set(patients, hidden, i, disease_severity="moderate")
                scripts[i] = {"tag": scenario, "random_flares": False,
                              "episodes": [(R(start), flare(peak=1.15, ramp=60, plateau=40, steroid_delay=12))]}
                steroid_start = R(start + 60 + 12)
                overlays.append((i, "sepsis", steroid_start + 20, steroid_start + 25, {}))

            elif scenario == "bowel_obstruction":
                yrs = rng.uniform(5, 15)
                _set(patients, hidden, i, ibd_type="CD", disease_extent="L1 ileal", cd_behaviour="B2 stricturing",
                     stricture_flag=True, years_since_diagnosis=round(yrs, 1),
                     age=int(patients.loc[i, "age_at_diagnosis"] + yrs), fc_coupling=0.5)
                scripts[i] = {"tag": scenario, "random_flares": True}
                d0 = R(int(rng.integers(60, 330)))
                overlays.append((i, "bowel_obstruction", d0, d0 + 3, {}))

            elif scenario == "stoma_dehydration":
                yrs = rng.uniform(6, 18)
                _set(patients, hidden, i, ibd_type="UC", disease_extent="E3 pancolitis", cd_behaviour="",
                     surgeries="colectomy", stoma=True, disease_severity="remission",
                     years_since_diagnosis=round(yrs, 1), age=int(patients.loc[i, "age_at_diagnosis"] + yrs),
                     current_medication="none", base_inflammation=0.03, normal_stools=5.0)
                scripts[i] = {"tag": scenario, "random_flares": False}
                d0 = R(int(rng.integers(60, 330)))
                overlays.append((i, "stoma_dehydration", d0, d0 + 3, {}))

            elif scenario == "crc_red_flags":
                yrs = rng.uniform(14, 22)
                _set(patients, hidden, i, ibd_type="UC", disease_extent="E3 pancolitis", cd_behaviour="",
                     disease_severity="mild", years_since_diagnosis=round(yrs, 1),
                     age=int(max(patients.loc[i, "age_at_diagnosis"], 20) + yrs), surgeries="none",
                     current_medication="5-ASA",
                     last_colonoscopy_date=(ref - pd.Timedelta(days=int(rng.uniform(4.5, 6) * 365))).normalize(),
                     psc_flag=bool(len(roster) % 3 == 0), prior_dysplasia=bool(len(roster) % 2 == 0),
                     pseudopolyps_flag=True, hb_base=13.0)
                scripts[i] = {"tag": scenario, "random_flares": False, "episodes": [(R(30), flare(peak=0.9))]}
                overlays.append((i, "crc_red_flags", R(245), R(record_days), {"hb_from": 13.0, "hb_to": 10.6}))

            elif scenario == "tb_reactivation":
                _set(patients, hidden, i, current_medication="anti-TNF", tb_screening_status="not documented",
                     tb_screening_date=pd.NaT, disease_severity="moderate")
                scripts[i] = {"tag": scenario, "random_flares": False}
                overlays.append((i, "tb_reactivation", R(290), R(record_days), {}))

    return scripts, overlays, pd.DataFrame(roster, columns=["patient_id", "scenario"])


def overlay_windows(overlays, kind):
    return [(i, a, b, extra) for i, k, a, b, extra in overlays if k == kind]
