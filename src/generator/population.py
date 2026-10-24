"""Synthetic IBD population and static EHR (brief §6.1–6.2).

Returns three things:
  patients    – the static EHR table a clinician would see (one row per patient)
  conditions  – ICD-10 coded diagnosis history (past diagnoses)
  hidden      – per-patient physiology used by the simulators; ground truth only,
                never a model input
"""
import numpy as np
import pandas as pd
from faker import Faker

# Weighted towards the states with published Indian IBD cohorts (Punjab, Telangana, Karnataka, Delhi).
STATES = ["Karnataka", "Telangana", "Tamil Nadu", "Maharashtra", "Delhi", "Punjab",
          "Uttar Pradesh", "West Bengal", "Kerala", "Gujarat"]
STATE_P = [0.15, 0.14, 0.10, 0.12, 0.10, 0.09, 0.10, 0.08, 0.07, 0.05]
SEVERITY = ["remission", "mild", "moderate", "severe"]
DEVICES = ["Apple Watch", "Fitbit", "Oura Ring", "Samsung Galaxy Watch", "Noise ColorFit", "Amazfit"]
DEVICE_P = [0.20, 0.17, 0.08, 0.18, 0.22, 0.15]

# Per-severity: annual flare rate and remission-level latent inflammation.
FLARE_RATE = {"remission": 0.25, "mild": 0.45, "moderate": 0.75, "severe": 1.2}
BASE_INFLAMMATION = {"remission": 0.05, "mild": 0.10, "moderate": 0.16, "severe": 0.24}

MED_CHOICES = {  # (UC/CD, severity) -> (options, probabilities)
    ("UC", "remission"): (["5-ASA", "thiopurine"], [0.85, 0.15]),
    ("UC", "mild"): (["5-ASA", "thiopurine"], [0.75, 0.25]),
    ("UC", "moderate"): (["5-ASA", "thiopurine", "anti-TNF", "vedolizumab"], [0.15, 0.45, 0.28, 0.12]),
    ("UC", "severe"): (["thiopurine", "anti-TNF", "vedolizumab", "steroid"], [0.15, 0.40, 0.25, 0.20]),
    ("CD", "remission"): (["none", "5-ASA", "thiopurine", "anti-TNF"], [0.15, 0.10, 0.50, 0.25]),
    ("CD", "mild"): (["5-ASA", "thiopurine", "anti-TNF"], [0.12, 0.58, 0.30]),
    ("CD", "moderate"): (["thiopurine", "anti-TNF", "vedolizumab", "steroid"], [0.30, 0.45, 0.12, 0.13]),
    ("CD", "severe"): (["anti-TNF", "vedolizumab", "steroid"], [0.55, 0.25, 0.20]),
}


def _date_before(ref, days):
    return (ref - pd.to_timedelta(np.asarray(days, dtype=float), unit="D")).normalize()


def generate_population(n, rng, ref_date):
    """`ref_date` is the last day of the wearable record ("today" on the dashboard)."""
    ref = pd.Timestamp(ref_date)
    fake = Faker("en_IN")
    fake.seed_instance(int(rng.integers(2 ** 31)))
    u = lambda: rng.random(n)

    sex = rng.choice(["M", "F"], n, p=[0.57, 0.43])
    band = rng.choice(["paediatric", "adult", "older"], n, p=[0.10, 0.85, 0.05])
    age_dx = np.select([band == "paediatric", band == "older"],
                       [rng.uniform(6, 17.9, n), rng.uniform(60, 72, n)],
                       rng.normal(30, 7, n).clip(18, 59))
    ibd_type = rng.choice(["UC", "CD"], n, p=[0.55, 0.45])
    uc, cd = ibd_type == "UC", ibd_type == "CD"
    new_dx = u() < 0.15
    # Every patient was diagnosed before the 120-day burn-in starts; "new" = still in year 1 at enrolment.
    years_dx = np.where(new_dx, rng.uniform(1.34, 2.1, n), rng.gamma(1.6, 3.5, n).clip(1.4, 30))
    age = np.floor(age_dx + years_dx).astype(int)

    severity = np.array([rng.choice(SEVERITY, p=[0.05, 0.30, 0.45, 0.20] if nd else [0.24, 0.34, 0.30, 0.12])
                         for nd in new_dx])
    severe, moderate = severity == "severe", severity == "moderate"

    rural = u() < 0.35
    state = rng.choice(STATES, n, p=STATE_P)
    delay = rng.lognormal(np.log(np.where(cd, 27, 8)), 0.7) * np.where(rural, 1.5, 1.0)
    prior_tb = u() < np.where(cd, 0.22, 0.03) * np.where(rural, 1.4, 1.0)

    # Montreal classification
    uc_extent = rng.choice(["E1 proctitis", "E2 left-sided", "E3 pancolitis"], n, p=[0.25, 0.40, 0.35])
    cd_location = rng.choice(["L1 ileal", "L2 colonic", "L3 ileocolonic"], n, p=[0.35, 0.25, 0.40])
    cd_behaviour = rng.choice(["B1 inflammatory", "B2 stricturing", "B3 penetrating"], n, p=[0.60, 0.25, 0.15])
    extent = np.where(uc, uc_extent, cd_location)
    behaviour = np.where(cd, cd_behaviour, "")
    perianal = cd & (u() < 0.20)

    annual_rate = np.array([FLARE_RATE[s] for s in severity])
    past_flares = rng.poisson(annual_rate * years_dx * 0.8)
    hospitalisations = rng.binomial(past_flares, np.where(severe, 0.4, 0.18))
    resection = cd & (u() < (0.04 + 0.015 * years_dx + 0.15 * (behaviour != "B1 inflammatory")).clip(0, 0.6))
    surgeries = np.where(resection, "ileocaecal resection", "none")
    stricture = (cd & ((behaviour == "B2 stricturing") | ((behaviour == "B3 penetrating") & (u() < 0.3)))) | (uc & (u() < 0.02))
    pseudopolyps = (uc & (extent != "E1 proctitis") & (years_dx > 5) & (u() < 0.15)) | (cd & (u() < 0.05))

    psc = u() < np.where(uc, 0.04, 0.01)
    fh_ibd, fh_crc = u() < 0.10, u() < 0.06
    # Genetic markers. NOD2 risk variants are rare in South Asians; IL23R R381Q is protective;
    # HLA-DRB1*01:03 is linked to extensive / severe UC.
    nod2 = u() < np.where(cd, 0.10, 0.03)
    il23r = u() < 0.06
    hla_drb1 = u() < np.where(uc, 0.08, 0.04)

    smoking = np.where(u() < np.where(sex == "M", 0.13, 0.02), "current",
                       np.where(u() < 0.08, "former", "never"))
    antibiotics = rng.poisson(np.where(cd, 4.2, 3.5))
    nsaid, ppi = u() < 0.15, u() < 0.20

    meds = np.array([rng.choice(MED_CHOICES[(t, s)][0], p=MED_CHOICES[(t, s)][1]) for t, s in zip(ibd_type, severity)])
    adherence = (rng.beta(7, 2, n) - np.where(rural, 0.05, 0)).clip(0.3, 1.0)

    long_extensive = uc & (extent != "E1 proctitis") & (years_dx >= 8)
    prior_dysplasia = u() < np.where(long_extensive, 0.06, 0.005)
    colonoscopy_gap = rng.uniform(30, 365 * np.minimum(years_dx, 6).clip(0.2))
    biologic = np.isin(meds, ["anti-TNF", "vedolizumab"])
    tb_status = np.where(biologic, np.where(u() < 0.85, "IGRA negative", "not documented"),
                         np.where(prior_tb, "treated (empirical ATT)", "not done"))
    tb_date = np.where(tb_status == "IGRA negative", _date_before(ref, rng.uniform(30, 4 * 365, n)), pd.NaT)
    hpv_date = np.where((sex == "F") & (age >= 25) & (u() < 0.55), _date_before(ref, rng.uniform(30, 6 * 365, n)), pd.NaT)
    skin_date = np.where(np.isin(meds, ["thiopurine", "anti-TNF"]) & (u() < 0.5),
                         _date_before(ref, rng.uniform(30, 3 * 365, n)), pd.NaT)

    height = np.where(sex == "M", rng.normal(167, 6.5, n), rng.normal(154, 6, n))
    height = np.where(age < 15, height - (15 - age) * 5.5, height)
    bmi = (rng.normal(21.5, 3.5, n) - 1.0 * severe).clip(14, 35)
    weight = bmi * (height / 100) ** 2

    comorbid_p = {
        "iron-deficiency anaemia": 0.22 + 0.12 * severe, "anxiety/depression": 0.20 + 0.05 * severe,
        "peripheral arthritis": 0.12, "osteopenia": 0.06 + 0.06 * (severe | moderate),
        "hypertension": 0.03 + 0.12 * (age > 45), "erythema nodosum": 0.03, "uveitis": 0.02,
    }
    has = {k: u() < p for k, p in comorbid_p.items()}
    comorbidities = ["; ".join(k for k in comorbid_p if has[k][i]) or "none" for i in range(n)]

    first = [fake.first_name_male() if s == "M" else fake.first_name_female() for s in sex]
    last = [fake.last_name()[0] for _ in range(n)]

    patients = pd.DataFrame({
        "patient_id": [f"P{i:04d}" for i in range(1, n + 1)],
        "display_name": [f"{f} {l}." for f, l in zip(first, last)],
        "age": age, "sex": sex, "region": np.where(rural, "rural", "urban"), "state": state,
        "ibd_type": ibd_type, "disease_extent": extent, "cd_behaviour": behaviour, "perianal_disease": perianal,
        "disease_severity": severity,
        "age_at_diagnosis": age_dx.round(1), "years_since_diagnosis": years_dx.round(1),
        "diagnostic_delay_months": delay.round(1), "prior_misdiagnosis_tb": prior_tb,
        "past_flares_count": past_flares, "hospitalisations": hospitalisations, "surgeries": surgeries,
        "stoma": False, "stricture_flag": stricture, "pseudopolyps_flag": pseudopolyps, "psc_flag": psc,
        "family_history_ibd": fh_ibd, "family_history_crc": fh_crc,
        "nod2_variant": nod2, "il23r_r381q_protective": il23r, "hla_drb1_0103": hla_drb1,
        "smoking_status": smoking, "childhood_antibiotic_courses": antibiotics,
        "nsaid_use": nsaid, "ppi_use": ppi,
        "current_medication": meds, "medication_adherence": adherence.round(2),
        "prior_dysplasia": prior_dysplasia, "last_colonoscopy_date": _date_before(ref, colonoscopy_gap),
        "tb_screening_status": tb_status, "tb_screening_date": tb_date,
        "hpv_screen_date": hpv_date, "last_skin_check": skin_date,
        "height_cm": height.round(1), "weight_kg": weight.round(1), "bmi": bmi.round(1),
        "comorbidities": comorbidities, "wearable_device": rng.choice(DEVICES, n, p=DEVICE_P),
    })

    active = rng.random(n) < 0.2
    hidden = pd.DataFrame({
        "patient_id": patients["patient_id"],
        "base_inflammation": np.array([BASE_INFLAMMATION[s] for s in severity]) * rng.lognormal(0, 0.2, n),
        "annual_flare_rate": annual_rate * rng.lognormal(0, 0.25, n),
        # How strongly this patient's wearables move with inflammation (some barely do).
        "wearable_responsiveness": rng.uniform(0.3, 1.3, n),
        # Symptom sensitivity: <0.6 = "silent" inflammation; ibs_overlap = symptoms without inflammation.
        "symptom_sensitivity": np.where(u() < 0.10, rng.uniform(0.3, 0.55, n), rng.uniform(0.8, 1.25, n)),
        "ibs_overlap": u() < 0.08,
        "crp_responder": np.where(uc & (u() < 0.5), 0.3, 1.0),
        "fc_coupling": np.select([uc, extent == "L1 ileal", extent == "L2 colonic"], [1.0, 0.5, 1.0], 0.75),
        "rhr_base": (rng.normal(68, 8, n) - 5 * active + 3 * (smoking == "current")).clip(48, 95),
        "rmssd_base": (rng.normal(40, 12, n) - 0.3 * (age - 35) + 6 * active).clip(12, 100),
        "steps_base": (rng.normal(7000, 2500, n) + 4000 * active - 1500 * severe).clip(1500, 20000),
        "spo2_base": rng.normal(97.2, 0.8, n).clip(94.5, 99.5),
        "sleep_base_h": rng.normal(7.0, 0.6, n).clip(5, 9),
        "sleep_eff_base": rng.normal(0.88, 0.04, n).clip(0.7, 0.97),
        "resp_rate_base": rng.normal(14.5, 1.5, n).clip(10, 20),
        "exercises": active,
        "drinker": u() < np.where(sex == "M", 0.30, 0.06),
        "missing_rate": rng.uniform(0.08, 0.18, n),
        "checkin_compliance": rng.uniform(0.5, 0.95, n),
        "lab_interval_days": np.where(rural, rng.uniform(60, 110, n), rng.uniform(30, 90, n)),
        "normal_stools": np.where(uc, rng.uniform(1, 2, n), rng.uniform(1.3, 2.8, n)),
        "hb_base": np.where(sex == "M", rng.normal(14.6, 0.8, n), rng.normal(12.9, 0.7, n)),
        "ferritin_base": rng.lognormal(np.log(np.where(sex == "M", 110, 50)), 0.4),
        "has_sweat_sensor": u() < 0.3,
    })
    return patients, hidden


def build_conditions(patients, rng, ref_date):
    """ICD-10 coded past diagnoses, derived from the static fields."""
    ref = pd.Timestamp(ref_date)
    rows = []
    icd_uc = {"E1 proctitis": ("K51.2", "Ulcerative (chronic) proctitis"),
              "E2 left-sided": ("K51.5", "Left sided colitis"),
              "E3 pancolitis": ("K51.0", "Ulcerative (chronic) pancolitis")}
    icd_cd = {"L1 ileal": ("K50.0", "Crohn's disease of small intestine"),
              "L2 colonic": ("K50.1", "Crohn's disease of large intestine"),
              "L3 ileocolonic": ("K50.8", "Crohn's disease of both small and large intestine")}
    other = {"iron-deficiency anaemia": ("D50.9", "Iron deficiency anaemia"),
             "anxiety/depression": ("F41.2", "Mixed anxiety and depressive disorder"),
             "peripheral arthritis": ("M07.6", "Enteropathic arthropathy"),
             "osteopenia": ("M85.8", "Osteopenia"), "hypertension": ("I10", "Essential hypertension"),
             "erythema nodosum": ("L52", "Erythema nodosum"), "uveitis": ("H20.9", "Uveitis")}
    for p in patients.itertuples(index=False):
        dx = ref - pd.Timedelta(days=p.years_since_diagnosis * 365.25)
        code, desc = (icd_uc if p.ibd_type == "UC" else icd_cd)[p.disease_extent]
        rows.append((p.patient_id, code, desc, dx.normalize()))
        between = lambda: (dx + pd.Timedelta(days=rng.uniform(0, max(p.years_since_diagnosis, 0.1)) * 365.25)).normalize()
        if p.prior_misdiagnosis_tb:
            rows.append((p.patient_id, "A18.3", "Tuberculosis of intestines (later revised to IBD)",
                         (dx - pd.Timedelta(days=p.diagnostic_delay_months * 30)).normalize()))
        if p.perianal_disease:
            rows.append((p.patient_id, "K60.3", "Anal fistula", between()))
        if p.stricture_flag:
            rows.append((p.patient_id, "K56.6", "Intestinal stricture / obstruction", between()))
        if p.psc_flag:
            rows.append((p.patient_id, "K83.0", "Primary sclerosing cholangitis", between()))
        if p.prior_dysplasia:
            rows.append((p.patient_id, "K63.89", "Colonic dysplasia on surveillance biopsy", between()))
        if p.surgeries != "none":
            rows.append((p.patient_id, "Z90.49", f"Status post {p.surgeries}", between()))
        if p.stoma:
            rows.append((p.patient_id, "Z93.2", "Ileostomy status", between()))
        for name, (c, d) in other.items():
            if name in p.comorbidities:
                rows.append((p.patient_id, c, d, between()))
    return pd.DataFrame(rows, columns=["patient_id", "icd10", "description", "onset_date"])
