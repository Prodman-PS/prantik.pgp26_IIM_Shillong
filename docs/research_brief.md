# IBD Digital Twin — Clinical & Literature Research Brief

> **Synthetic data only — not medical advice.** Background epidemiology, wearable & biomarker literature, clinical rules, and design rationale for the IBD Digital Twin prototype (*Team prantik.pgp26, IIM Shillong*).

---

## 2. Why IBD (and how to defend it)

### 2.1 What IBD is
- Chronic immune-mediated inflammation of the gut. Two main types:
  - **Ulcerative colitis (UC):** colon only, inner lining, continuous from rectum.
  - **Crohn’s disease (CD):** anywhere mouth→anus, full thickness, skip lesions → strictures, fistulas.
- Develops from **genes + environment + gut microbes + immune overreaction** (gut barrier weakens → immune system attacks gut bacteria and can’t switch off).
- **No cure**; managed lifelong like hypertension, but **relapsing-remitting** (flares vs remission) and often symptomatic.

### 2.2 Key India statistics (use in pitch)
| Fact | Value | Source |
|---|---|---|
| Estimated IBD patients (2010) | ~1.4 million (2nd only to USA); 1.1M UC + ~0.3M CD | Kedia & Ahuja, “Pivot to Asia” (PMC5323305) |
| GBD estimate | 0.13M (1990) → 0.27M (2019) — doubled | Indian J Gastroenterol 2023 (PubMed 37783933) |
| GBD 2021 analysis | ~642,357 cases in India | G20 GBD analysis (PMC12826281) |
| Clinician estimate | >15 lakh | AIG Hyderabad (IANS, 2023) |
| UC prevalence (Punjab) | 44.3 per 100,000; incidence 6.02 | Sood et al., *Gut* 2003 |
| Hyderabad incidence (ACCESS) | IBD 9.31; CD 3.91; UC 5.4 per 100,000 | Ng et al., *Gastroenterology* 2013 |
| 30,000+ colonoscopy study | 5.4% IBD among symptomatic; no rural–urban difference; CD > UC even in villages | Banerjee et al., *Lancet Reg Health SEA* 2023 |
| Rural shift | Rural IBD 0.1% (2006) → >5% (2023) among symptomatic | AIG / IANS |
| Peak age | 20–40 years (working population) | AIG |
| Diagnostic delay | Median 15 months; CD 27 vs UC 8 months | Indian J Gastroenterol 2025/26 (PubMed 40682729) |
| Cost of delay | ₹1,36,029 median = 5.5× monthly household income | same |
| Global stage | India in **“acceleration in incidence”** stage | Hracs/Kaplan et al., *Nature* 2025 |
| Growth vs world | India IBD rising faster than global rate | Giri et al., *Intest Res* 2024 |

### 2.3 The “is IBD prevalent?” defence (slide 1)
Judges may compare IBD (0.3–1.5M) to diabetes (101M). Frame as **high-impact and fast-rising**, not most common:
- “India has the largest IBD population in Asia and it is growing faster than the global rate.”
- “India is in IBD’s *acceleration stage* (Nature 2025) — where Korea/Japan were 20–30 years ago.” (Korea UC prevalence quadrupled 1997–2005; Japan CD 2.9→13.5/100k 1986–98.)
- “It hits 20–40-year-olds and is diagnosed after a median 15-month delay.”
- “Specialists are concentrated in tier-1 cities, but disease is now equally common in rural symptomatic patients.”

### 2.4 Alternatives considered (scoring summary — our judgement)
Scored on brief fit, wearable evidence, data availability, India impact, originality, demo wow, future growth (/70):

| Idea | Total |
|---|---|
| Chemotherapy fever (febrile neutropenia) | 58 |
| **IBD flare prediction (chosen)** | **56** |
| Diabetic foot ulcer risk | 56 |
| Parkinson’s falls | 56 |
| Elderly falls/frailty | 56 |
| Post-surgery at home | 53 |

Earlier scoring (/60): AF→stroke 54, COPD+AQI 53, heart failure 51, IBD 48, T2D 48 (low originality).
**Decision:** Stay with IBD — top-tier tie, highest originality, strongest disease-specific wearable evidence, and our research head start. Architecture should be **disease-agnostic** so we can mention extension to COPD/heart failure.

---

## 3. Clinical Evidence Base (what the model is built on)

### 3.1 Wearables predict IBD flares (core evidence)
**Hirten et al., Mount Sinai, *Gastroenterology*, Jan 2025 (IBD Forecast study)**
- 309 IBD patients, 36 US states; Apple Watch / Fitbit / Oura Ring.
- During flares: **HRV ↓**, **heart rate ↑**, **resting HR ↑**, **steps ↓**; circadian HRV pattern differs flare vs remission.
- Signals altered **up to 7 weeks before** inflammatory and symptomatic flares (HRV, HR, RHR, steps, SpO₂).
- Combined-metric models: **F1 up to 0.90** (inflammatory flares), **0.83** (symptomatic).
- Mechanism: inflammation → reduced parasympathetic / increased sympathetic tone.
- Wearables help resolve the **symptom–inflammation mismatch**.

### 3.2 Faecal calprotectin (gut-specific inflammation marker)
- Protein from neutrophils; stool level = gut inflammation.
- **Levels (adults & children >4 yrs):** <50 µg/g normal; 50–200 borderline (repeat); >200–250 active likely; >500 marked.
- **Age effects:** much higher in infants (median ~174 µg/g ≤18 months; ~83 at 1–4 yrs); slight rise >60 yrs (median ~27). Child cut-offs used in one study: <350 (first year), <275 (1–4 yrs), <50 (>4 yrs).
- **Rises before relapse:** UC patients on infliximab who flared had >300 mg/kg **3 months before** flare; two consecutive >300 readings 1 month apart → **100% specificity** (Antwerp study). Asymptomatic patients with repeated elevated FC → **53–83%** relapse within 2–3 months (systematic review). FC >200 after de-escalation strongly predicted relapse (only 4.4% relapsed while <200).
- Stronger in **UC** than CD (CD pooled sens 0.75 / spec 0.71 at >150).
- **Confounders (raise FC without IBD):** gut infections, NSAIDs, PPIs, intestinal TB, colorectal cancer/polyps, diverticulitis, microscopic colitis, coeliac (mild), GI bleeding, infant food allergy. **IBS does not raise FC.**
- **Home tests:** IBDoc, CalproSmart (smartphone-read lateral flow; CalproSmart has API integration to hospital systems). India availability unconfirmed.
- **Blood/saliva calprotectin:** NOT a substitute (426-patient study 2026: serum not a surrogate; saliva doesn’t correlate). Serum is ~2× plasma due to ex-vivo neutrophil release; centrifuge serum <2 h, plasma <6 h.

### 3.3 CRP (blood)
- Body-wide inflammation marker — **not gut-specific** (infection, injury, exercise also raise it). Many UC patients have normal CRP during flares.
- Finger-prick CRP: home self-sampling matched hospital CRP (ρ=0.99, 81 patients, >95% success); ProciseDx POCT r=0.98, 2–4 min (clinic).
- hs-CRP heart risk: <1 low, 1–3 average, >3 high.

### 3.4 Interpretation matrix (use in twin logic)
| Calprotectin | CRP | Likely meaning |
|---|---|---|
| High | High | IBD flare with systemic inflammation (more severe) |
| High | Normal | Gut inflammation (common in UC) |
| Normal | High | Likely non-gut cause (e.g., infection) |
| Rising + wearable drift | — | Strongest flare warning |

### 3.5 Disease severity distribution (for synthetic population)
Patient survey (long-standing disease): CD — inactive 18.4%, mild 34.0%, moderate 34.5%, severe 11.4%; UC — 26.4/32.8/29.4/8.9%.
UC meta-analysis (17 cohorts): 70–80% relapse within 10 years; 10–15% aggressive; most active at diagnosis.
Hospitalisation (biologic era, Australia): ~1/3 CD, 24% UC, mostly in year 1.
Indian disease generally milder, but Asian CD often complicated (ACCESS: 52% complicated vs 24% Australia).

### 3.6 Complications & extreme scenarios
- **Toxic megacolon:** ~5% of severe UC attacks; mortality 0–2% in IBD with modern care; **>40%** if colectomy after perforation (vs 2–8% without).
- Perforation/sepsis (steroids can mask signs), massive bleeding, strictures/obstruction, fistulas, abscesses, short bowel syndrome.
- **Colorectal cancer:** up to ~8% within 20 years of UC (older data; now falling). Pathway: inflammation → dysplasia (often flat) → cancer. Surveillance colonoscopy from ~8 years after diagnosis; yearly with PSC.
- PSC → bile duct cancer; VTE risk ↑ in flares; anaemia; osteoporosis; uveitis; depression/anxiety.
- **India-specific:** Crohn’s vs intestinal TB misdiagnosis — dangerous both ways (immunosuppressing missed TB; delaying CD with empirical ATT).

### 3.7 Risk factors worth encoding as EHR features
- Antibiotic exposure (esp. childhood): meta-analysis OR ~1.41 (28 studies, 153,027 IBD pts); childhood RR 1.42 overall, **1.59 CD**, 1.23 UC; dose-response. (Note: ACCESS Asia case-control found antibiotics *protective* in Asia — mixed evidence.) India = largest antibiotic consumer by volume, mostly OTC.
- Smoking (worsens CD), NOD2 genotype, family history, prior flares, steroid use, medication adherence, NSAID/PPI use.

---

## 4. Digital Twin Concept (plain language)

> A digital twin is a **virtual copy of the patient** that stays in sync with their real data, so the doctor can **mirror** (see current state), **predict** (forecast flares), and **simulate** (“what if we change treatment?”) before acting on the real patient.

Real-world precedents: Twin Health (Whole Body Digital Twin for diabetes; operates in India incl. Fortis-CDOC; RCT across India), Siemens Healthineers heart twin (MRI+ECG), Dassault Living Heart (FDA collaboration), Unlearn.AI (digital-twin control arms).

**Gap we fill:** Digital twins exist for heart and diabetes; wearable IBD flare prediction is proven in research — **no IBD digital twin product exists yet.**

---

## 5. Prediction Target (adverse event definition)

**Primary label:** `flare_within_14d` = 1 if a flare **onset** occurs in days (t+1 … t+14), using only data up to day t.

Flare onset definition (synthetic ground truth): latent inflammation crosses flare threshold AND symptom score crosses threshold (and/or calprotectin >250 confirmed). Keep both an *inflammatory* and a *symptomatic* flare flag (Mount Sinai distinguishes both).

Secondary outputs:
- 14-day flare risk probability (0–1) → traffic-light: 🟢 <20%, 🟠 20–50%, 🔴 >50% (tunable).
- Emergency alert flags (hours-level) — see §9.1.
- Long-term CRC risk level + surveillance due date — see §9.2.

---

## 6. Synthetic Data Specification

> Synthea has **no IBD module** (it has COPD, sleep apnoea, etc.). Build a **custom Python generator** (numpy + Faker). MIMIC-IV requires PhysioNet credentialing + CITI training (days–weeks) — optional, not required.

### 6.1 Population (N = 500–1,000)
- Age at diagnosis: peak 20–40; include ~10% paediatric (<18) and ~5% >60.
- Sex: slight male predominance (Indian cohorts M>F).
- IBD type: ~55% UC / 45% CD (recent Indian data shows CD rising; AIG colonoscopy CD>UC).
- Severity mix: ~20–25% remission, 30–35% mild, ~30% moderate, ~10% severe.
- Region: urban/rural flag (no difference in IBD proportion; rural = longer diagnostic delay, fewer specialists).

### 6.2 Static EHR fields
```
patient_id, age, sex, region (urban/rural), state
ibd_type (UC/CD), disease_extent (UC: E1 proctitis/E2 left/E3 pancolitis; CD: L1 ileal/L2 colonic/L3 ileocolonic, B1/B2/B3 behaviour, perianal flag)
years_since_diagnosis, diagnostic_delay_months, prior_misdiagnosis_TB (bool)
past_flares_count, hospitalisations, surgeries (colectomy/resection), stricture_flag, pseudopolyps_flag
psc_flag, family_history_ibd, family_history_crc, nod2_variant (bool)
smoking_status, childhood_antibiotic_courses, nsaid_use, ppi_use
current_medication (5-ASA / thiopurine / anti-TNF / vedolizumab / steroid), medication_adherence (0–1)
prior_dysplasia, last_colonoscopy_date, tb_screening_status, hpv_screen_date, last_skin_check
bmi, comorbidities
```

### 6.3 Latent inflammation process (drives everything)
- Each patient has hidden daily `inflammation[t]` (0 = remission … 1+ = severe).
- Flares scheduled via Poisson process; **rate modulated by risk** (↑ prior flares, ↓ adherence, smoking for CD, recent steroid taper/de-escalation, recent gut infection, NSAIDs).
- Pre-flare ramp: inflammation rises gradually over **~8–12 weeks** before symptomatic onset (supports calprotectin 3-month lead and wearable 7-week lead).
- More flare activity in year 1 after diagnosis.

### 6.4 Wearable stream (daily; optionally hourly → aggregated)
Personal baselines drawn per patient (e.g., RHR ~ N(68, 8) bpm; RMSSD ~ N(40, 12) ms; steps ~ N(7000, 2500)).
Signals & pre-flare drift (**design assumptions** — tune so the model is not trivially easy):
| Signal | Flare-ward change (assumption) | Notes |
|---|---|---|
| HRV (RMSSD) | ↓ 10–25% from baseline over final ~4–7 weeks | add circadian amplitude flattening |
| Resting HR | ↑ 3–8 bpm | best measured during sleep |
| Heart rate (mean) | ↑ modestly | |
| Steps | ↓ 15–40% | fatigue/pain |
| SpO₂ | small shift | Mount Sinai listed oxygenation |
| Sleep duration/efficiency, night awakenings | worsening | plausible, not validated — secondary features |
| Skin temperature | small ↑ | plausible, not validated |
| Respiratory rate | small ↑ | plausible |

Noise & realism (mandatory):
- Day-to-day noise, weekday/weekend activity pattern, circadian rhythm.
- **Decoys:** viral colds (fever, HR↑, HRV↓ for 3–7 days, no calprotectin rise), stressful weeks, alcohol/late nights, exercise days.
- Missing data: 10–20% random days + occasional multi-day gaps (device not worn).

### 6.5 Lab stream (periodic)
- **Faecal calprotectin:** every 1–3 months routinely + extra test triggered when twin risk is high (“smart escalation”). Value ≈ f(inflammation) with lognormal noise; baseline age-adjusted (§3.2); confounder bumps (NSAID, infection).
- **CRP:** every 1–3 months; responds to inflammation and to infections (decoys).
- Haemoglobin, ferritin, albumin, platelets, WBC; liver enzymes (ALP/GGT/bilirubin) for PSC patients.
- Optional: drug levels (anti-TNF trough).

### 6.6 Symptom stream (daily app check-in)
- Stool frequency, blood (Y/N), urgency, abdominal pain (0–10), fatigue, mood.
- Derived partial Mayo (UC) / Harvey-Bradshaw (CD) scores.
- Symptoms lag inflammation (appear late in ramp); include symptom–inflammation mismatch cases.

### 6.7 Optional simulated sweat-sensor stream (roadmap; label “investigational”)
- Markers: sweat CRP, sweat calprotectin, IL-6, TNF-α; hourly → daily aggregate.
- `sweat_x[t] = baseline + k*inflammation[t] + drift[t] + noise[t]`; drop 10–20% readings (poor skin contact). Noisier than stool calprotectin.
- Must be **optional** in the model (most real Indian patients won’t have it).

### 6.8 Emergency & long-term scenarios to seed (for demo)
- A few patients with **acute severe colitis** (RHR >90, fever, ≥6 bloody stools/day, CRP ↑).
- A few with **VTE pattern** (sudden RHR jump + SpO₂ drop + immobility during flare).
- A few with **sepsis-like pattern** on steroids.
- A few **long-standing extensive UC** patients with **overdue colonoscopy** + red flags (falling Hb, weight loss, persistent FC despite therapy).
- A few **TB-reactivation-like** patients on anti-TNF (low-grade fever, night sweats, weight loss).

### 6.9 Outputs
`data/synthetic/patients.csv`, `wearables_daily.parquet`, `labs.parquet`, `symptoms.parquet`, `sweat.parquet` (optional), `events.csv` (ground-truth flares/emergencies). Seeded & reproducible (`--seed`). Optional FHIR R4 bundle export.

---

## 7. Feature Engineering (fusion layer)

Per patient, per day t (no future leakage):
- **Personal baseline**: rolling remission-period median/MAD per signal (e.g., first 60 remission days, updated).
- **Deviation z-scores**: (value − baseline)/baseline_sd for HRV, RHR, HR, steps, SpO₂, sleep, temp.
- **Rolling windows**: 7/14/28-day means, std, min/max; **slopes** (linear trend over 7/14/28 d).
- **Circadian features**: HRV day–night amplitude, phase (if hourly data).
- **Co-movement**: count of signals simultaneously beyond thresholds (HRV↓ & RHR↑ & steps↓).
- **Lab features**: last calprotectin, change from previous, days since last test, two-consecutive-high flag; last CRP; Hb trend.
- **Symptom features**: 7-day partial Mayo/HBI mean & trend.
- **Static EHR features**: attached to every row.
- **Context flags**: recent NSAID/PPI, recent infection/travel, recent antibiotics, steroid taper.
- **Cumulative inflammation burden**: months with FC >250 or in flare (for cancer module).

---

## 8. Modelling

### 8.1 Models
1. **Baseline:** logistic regression (show improvement).
2. **Main:** LightGBM/XGBoost on tabular features (handles missing values natively — good for optional sweat stream).
3. **Optional:** LSTM/temporal CNN on raw sequences.

### 8.2 Validation rules (critical)
- **Split by patient**, never by day (no patient in both train and test). Use grouped K-fold.
- Strict temporal causality: features at t use data ≤ t only.
- Handle class imbalance (flare-onset windows are rare): class weights / focal loss; report PR-AUC.

### 8.3 Metrics to report
AUROC, PR-AUC, F1, sensitivity/specificity at chosen threshold, **average warning lead time (days)**, **false alarms per patient-month**, calibration (Brier/reliability plot).

**Ablation (key slide):**
| Version | Inputs |
|---|---|
| A | Wearables + EHR |
| B | A + periodic calprotectin |
| C | B + simulated sweat stream |
Show the incremental value of each stream (quantifies the future-sensor value “X”).

### 8.4 Explainability & what-if
- **SHAP** top drivers per prediction (“HRV down 22% over 10 days; calprotectin 310; 3 flares last year”).
- **What-if simulator:** change modifiable inputs (adherence → 100%, switch to biologic, stop NSAID) → re-run model → show projected risk change. (This makes it a *twin*, not just a classifier.)
- Avoid overclaiming causality — present as “model-estimated”.

---

## 9. Alerts & Safety Modules

### 9.1 Two-tier alerts
- 🟠 **Trend alerts (days–weeks):** rising flare risk, anaemia trend, surveillance due.
  - Smart escalation: high risk → prompt home calprotectin test; two consecutive high results → recommend clinician review.
- 🔴 **Emergency alerts (hours):**
  | Pattern | Possible condition |
  |---|---|
  | RHR >90 + fever + ≥6 bloody stools/day + CRP↑ | Acute severe colitis / toxic megacolon risk |
  | Sudden RHR jump + SpO₂ drop + breathlessness/immobility | Possible VTE/PE |
  | Fever + high RHR + resp rate↑ + HRV crash (esp. on steroids) | Sepsis/abscess |
  | Vomiting + no stool/gas in stricture patient | Bowel obstruction |
  | High stool output + RHR↑ + dizziness (stoma) | Dehydration/AKI |
  | Low-grade fever + night sweats + weight loss on anti-TNF | TB reactivation |
  → Advise urgent contact / emergency care. Never auto-diagnose.

### 9.2 Cancer Safety panel (rule-based; “surveillance support, not cancer detection”)
**CRC risk score inputs:** years since diagnosis (≥8), extent (pancolitis), PSC, family history CRC, prior dysplasia, strictures/pseudopolyps, **cumulative inflammation burden** (twin-unique).
**Outputs:** risk level (low/medium/high) + next surveillance colonoscopy date (e.g., high: 1 yr; low: 3–5 yr; PSC: yearly) + overdue flag.
**CRC red flags:** FC persistently high despite effective therapy; falling Hb/ferritin; unexplained weight loss; bleeding in remission; changed bowel habit after stability; **mismatch** (labs worsening while wearables/flare signals stable).
**Other cancer screening tracker:**
| Cancer | Link | Signals/reminders |
|---|---|---|
| Bile duct | PSC | ALP/GGT/bilirubin trend, CA 19-9, imaging due |
| Small bowel | Small-bowel CD | obstruction symptoms, anaemia |
| Anal/fistula | Perianal CD | fistula change reports |
| Lymphoma | Thiopurines ± anti-TNF | fevers, sweats, nodes, counts; drug exposure |
| Skin | Thiopurines (NMSC), anti-TNF (melanoma) | annual skin check due |
| Cervical | Immunosuppression/HPV | Pap/HPV screen due |
| Urinary tract | Thiopurines | haematuria report |
Inflammation-driven cancers ↑ with uncontrolled disease; treatment-linked ones relate to drug exposure — untreated disease is **not** safer.

---

## 10. Doctor Dashboard (Streamlit)

Panels:
1. **Patient card:** demographics, IBD type/extent, meds, flare history, years since diagnosis.
2. **Flare risk gauge:** 14-day probability + traffic light + trend over last 60 days.
3. **Signal trends:** HRV, RHR, steps, SpO₂, sleep vs personal baseline band; past flares marked.
4. **Labs timeline:** calprotectin (with age-adjusted thresholds), CRP, Hb.
5. **“Why” panel:** SHAP top drivers in plain language.
6. **What-if sliders:** adherence, medication switch, NSAID stop → projected risk.
7. **Suggested action:** e.g., “Order home calprotectin”, “Teleconsult”, “Review therapy”.
8. **Alerts feed:** 🟠 trend / 🔴 emergency.
9. **Cancer Safety panel:** CRC risk level, next colonoscopy, red flags, screening tracker.
10. **Optional:** sweat-sensor panel labelled *“Continuous inflammation — investigational, simulated data.”*
11. **Population view:** list of patients sorted by risk; overdue surveillance list.

Example card:
```
Ananya R. — Ulcerative colitis (11 yrs)
Flare risk (14 days):   🟢 Low 12%
CRC risk level:         🟠 Medium
Next colonoscopy:       Due in 4 months
Red flags:              ⚠️ Hb falling 3 mo   ⚠️ Weight −3.5 kg
Suggested action:       Review + consider earlier colonoscopy
```

Demo story for video (“Ananya”, 28, Bengaluru, UC): Week 1 baseline green → Week 4 HRV slipping, RHR 64→69, risk amber 34% → Week 5 decoy check (no fever/cough), prompt home calprotectin = 310 → doctor dashboard red 71% with SHAP reasons and what-if (“optimise therapy → 22%”) → teleconsult adjustment → Week 9 back to baseline; flare averted.

---

## 11. Suggested Repo Structure
```
prantik.pgp26_IIM_Shillong/
├── README.md                  # submission sections (see §1)
├── LICENSE                    # MIT or Apache-2.0
├── CLAUDE.md                  # this brief
├── requirements.txt / pyproject.toml
├── data/
│   └── synthetic/             # generated outputs (gitignore large files or keep small sample)
├── src/
│   ├── generator/             # population.py, latent.py, wearables.py, labs.py, symptoms.py, sweat.py, events.py
│   ├── features/              # baselines.py, windows.py, fusion.py
│   ├── models/                # train.py, evaluate.py, explain.py, whatif.py
│   ├── alerts/                # trend_alerts.py, emergency_rules.py, cancer_safety.py
│   ├── interop/               # fhir_export.py (optional)
│   └── dashboard/             # app.py (Streamlit), components/
├── notebooks/                 # EDA, model comparison, ablation
├── tests/                     # pytest: no leakage, patient-split, generator sanity, rules
├── docs/
│   ├── architecture.md / architecture.pdf
│   ├── presentation.pdf
│   └── evidence.md            # references (§14)
└── scripts/                   # make_data.sh, train.sh, run_dashboard.sh
```

Architecture diagram (5 layers): **Synthetic patients (EHR)** → **Wearable/lab/symptom/sweat streams** → **Fusion & personal baselines** → **Prediction + explainability + what-if** → **Alerts & doctor dashboard**.

---

## 12. Deliverables Checklist (for Claude Code to help produce)
- [ ] `make data` → synthetic dataset (seeded)
- [ ] `make train` → trained LightGBM + baseline; metrics JSON; ablation table
- [ ] `make dashboard` → Streamlit app with demo patients incl. “Ananya”
- [ ] Tests passing (leakage, grouped split, rule triggers)
- [ ] README with all required sections + run instructions + disclaimer
- [ ] Architecture diagram (export to PDF/PPT)
- [ ] Presentation outline (§13) → PDF/PPT
- [ ] 20+ min video script outline (§13)
- [ ] Licence file

---

## 13. Pitch & Video Outline (20+ minutes)
1. **Problem (3 min):** IBD in India — acceleration stage, young patients, 15-month delay, ₹1.36L cost of delay, tier-1 specialist concentration, rural spread, TB confusion, no cure → management is everything. “Blood-pressure cuff for gut inflammation” analogy.
2. **Evidence (2 min):** Mount Sinai 7-week lead; calprotectin 3-month lead; F1 0.90.
3. **Twin concept (2 min):** mirror / predict / simulate.
4. **Architecture (3 min):** 5 layers; disease-agnostic; sensor-agnostic (sweat-sensor slot).
5. **Synthetic data (3 min):** how realism, decoys, missingness and personal baselines were built.
6. **Model & results (3 min):** metrics, lead time, false-alarm rate, ablation A/B/C.
7. **Live demo (4 min):** Ananya story; emergency alert demo; Cancer Safety panel.
8. **India pathway & roadmap (1 min):** today (smartwatch + home calprotectin) → CDSCO investigational pilots of sweat sensors (MD-16/17, MD-22/23) → approved continuous sensors; extension to COPD/heart failure.
9. **Limitations & ethics (1 min).**

Key one-liners:
- “Digital twins exist for heart and diabetes; wearable IBD flare prediction is proven in research — no one has combined them into an IBD digital twin. That’s what we built.”
- “The twin doesn’t just predict flares — it makes sure no high-risk IBD patient misses the colonoscopy that could catch cancer at stage I (~90% 5-yr survival) instead of stage IV (~13–15%).”

---

## 14. Limitations, Ethics & Disclaimers (include in README)
- Synthetic data only; drift magnitudes are **design assumptions** informed by literature, not measured.
- Wearable signals are non-specific (colds, stress, alcohol, exercise) — mitigated by EHR context and lab confirmation; twin **flags risk, never diagnoses**.
- Calprotectin confounders and age effects; CRP non-specific.
- Sweat sensors (e.g., EnLiSense IBD AWARE) are **not FDA-cleared**, marketed only as general-wellness devices; disease monitoring investigational; no CDSCO approval found — simulated only.
- Not validated on real Indian patients; real deployment would need ethics approval, DPDP Act compliance, CDSCO pathway, clinician oversight.
- Bias: training population assumptions may not reflect all Indian regions/phenotypes.

---

## 15. Reference Notes (key sources)
- Mount Sinai wearable IBD study (Hirten et al., *Gastroenterology* 2025): https://www.mountsinai.org/about/newsroom/2025/mount-sinai-study-finds-wearable-devices-can-detect-and-predict-inflammatory-bowel-disease-flare-ups ; summary https://blogs.the-hospitalist.org/content/wearable-devices-may-predict-ibd-flares-weeks-advance
- IBD burden India (Pivot to Asia): https://pmc.ncbi.nlm.nih.gov/articles/PMC5323305
- Epidemiology of IBD in India (Great Shift East): https://pmc.ncbi.nlm.nih.gov/articles/PMC5988149
- AIG 30,000-patient colonoscopy study: https://pmc.ncbi.nlm.nih.gov/articles/PMC10709679
- Punjab UC prevalence (Gut 2003): https://gut.bmj.com/content/52/11/1587
- GBD IBD trends 1990–2019 (Indian J Gastroenterol): https://pubmed.ncbi.nlm.nih.gov/37783933/
- Burden of IBD in India GBD (Intest Res 2024): https://pmc.ncbi.nlm.nih.gov/articles/PMC12884109/
- Global evolution of IBD (Nature 2025): https://www.nature.com/articles/s41586-025-08940-0
- Diagnostic delay & economic burden India: https://pubmed.ncbi.nlm.nih.gov/40682729/
- Calprotectin before relapse (infliximab UC): https://repository.uantwerpen.be/link/irua/113781
- Repeated calprotectin systematic review: https://pmc.ncbi.nlm.nih.gov/articles/PMC5434712
- Calprotectin after de-escalation: https://hal.archives-ouvertes.fr/hal-02013846
- Serum vs faecal calprotectin (Sci Rep 2026): https://iris.unipa.it/handle/10447/704934
- Home calprotectin tests (NICE MIB132): https://nice.org.uk/advice/mib132
- Finger-prick CRP home sampling: https://pmc.ncbi.nlm.nih.gov/articles/PMC10906358/
- Antibiotics & IBD meta-analysis (CGH 2025): https://gastroenterology.acponline.org/archives/2024/03/22/2.htm
- Toxic megacolon review: https://pmc.ncbi.nlm.nih.gov/articles/PMC7245441
- Twin Health RCT (India): https://esc365.escardio.org/journal/1340
- Sweat sensors review (AGA 2026): https://news.gastro.org/issues/2026/january/wearable-devices-show-growing-potential-in-ibd-care/
- EnLiSense (IBD AWARE): https://www.enlisense.com
- CDSCO Medical Devices Rules pathway: https://cdsco.gov.in/opencms/export/sites/CDSCO_WEB/Pdf-documents/medical-device/RegulatoryMDR-2017.pdf
- Synthea module list: https://docs.bcbi.brown.edu/codiac-for-health/ursa-ri/datasets/syntheticri-2026-synthetic-healthcare-records-for-rhode-island/synthea-modules-used-in-the-generation-of-syntheticri-2026.md
- India leading causes of death (GBD 2023 summary): https://visionias.in/current-affairs/upsc-daily-news-summary/article/2025-10-13/the-indian-express/science-and-technology/study-leading-cause-of-deaths-in-india-shifts-from-infectious-to-ncds

---

## 16. First Prompts to Give Claude Code
1. “Read CLAUDE.md. Scaffold the repo structure in §11 with a pyproject, Makefile targets (`data`, `train`, `dashboard`, `test`) and an MIT licence.”
2. “Implement the synthetic generator per §6 with a `--seed` and `--n-patients` CLI. Include decoys, missingness and the seeded demo scenarios in §6.8. Write sanity tests.”
3. “Implement §7 feature fusion with personal baselines and strict no-leakage; add a pytest that fails if any feature uses future data.”
4. “Train baseline + LightGBM per §8 with grouped patient split; output metrics, lead-time and false-alarm stats, and the A/B/C ablation.”
5. “Add SHAP explanations and the what-if simulator (§8.4).”
6. “Implement alerts (§9.1) and the Cancer Safety panel (§9.2) as tested rule modules.”
7. “Build the Streamlit dashboard (§10) with the Ananya demo patient and a population view.”
8. “Write README.md covering every submission item in §1 plus limitations (§14).”
