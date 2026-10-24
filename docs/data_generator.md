# Synthetic data generator (`src/generator/`)

**All data in this repository is synthetic.** No real patient data was used, in line with the DPDP Act and HIPAA sandbox rules. Nothing here is medical advice or a validated clinical tool.

Synthea has no IBD module, so this is a custom, seeded Python generator built to the spec in `CLAUDE.md` §6.
It fuses the two streams the challenge requires:

| Challenge requirement | What the generator produces |
|---|---|
| **Static / historical EHR**: demographics, past diagnoses, labs, genetic markers | `patients.csv` (§6.2 fields, Montreal classification), `conditions.csv` (ICD-10 history), 120 days of pre-record lab history, NOD2 / IL23R / HLA-DRB1\*01:03 markers |
| **Dynamic / real-time wearables**: HRV, sleep stages, steps | Daily resting HR, mean HR, nightly and daytime HRV, steps, SpO₂, sleep duration, efficiency and stage minutes, awakenings, skin temperature, respiratory rate. An hourly stream is included for the demo patients |
| **Adverse event to predict** | `flare_within_14d`: will an IBD flare start in the next 14 days? |

```bash
pip install -r requirements.txt
python -m src.generator --n-patients 800 --seed 42     # or: make data   (~30 s)
python -m pytest -q tests                              # or: make test   (12 sanity tests)
```

Options: `--n-patients`, `--days` (record length, default 365), `--seed`, `--end-date` ("today" on the dashboard, default 2026-09-30), `--out`, `--format auto|parquet|csv`.
Tables are written as Parquet when `pyarrow` is installed, otherwise as CSV.
On Windows on ARM, pyarrow has no native wheel, so use an x64 Python build; it runs under emulation.

### How it works

Everything is driven by one hidden variable per patient-day: **latent inflammation** (`latent.py`).
Each observed stream is a noisy, lagged or confounded view of it.

1. **Population** (`population.py`):
   - Peak onset age 20–40, with ~10% paediatric and ~5% over-60 onset.
   - 57% male; ~55% UC / 45% CD.
   - Severity mix: 21% remission, 32% mild, 34% moderate, 14% severe.
   - Urban and rural patients, where rural means a 1.5× longer diagnostic delay and fewer lab visits.
   - Crohn's previously misdiagnosed as intestinal TB.
   - Medications assigned by IBD type and severity.
2. **Flares** arrive by a Poisson process.
   - The daily hazard rises with: prior flares, poor adherence, smoking (CD), NOD2, recent NSAIDs, gut infection, antibiotics, steroid taper, and being in year 1 after diagnosis.
   - Each flare is preceded by an **8–12 week ramp** in inflammation.
   - 20% of episodes are subclinical and settle on their own.
   - 70% of flares get an 8-week steroid course; 40% lead to therapy escalation.
3. **Wearables** (`wearables.py`) drift with inflammation, scaled by each patient's *responsiveness*. Some patients' signals barely move, so the task isn't trivially easy.
   - HRV falls and its day–night amplitude flattens.
   - Resting HR rises, steps and SpO₂ fall, sleep worsens, skin temperature and respiratory rate rise.
   - **Decoys:** viral colds, stressful weeks, alcohol nights, exercise days.
   - **Missingness:** 8–18% random non-wear days plus multi-day gaps. Some devices don't report HRV or skin temperature at all.
4. **Symptoms** (`symptoms.py`) follow inflammation with a 1–2 week lag, so they appear late in the ramp.
   - Partial Mayo (UC) and Harvey-Bradshaw (CD) scores are derived from them.
   - Mismatch cases are built in: "silent" patients with low symptom sensitivity, and IBS overlap (symptoms with no inflammation).
5. **Labs** (`labs.py`):
   - **Routine panels** every 30–90 days, or 60–110 days for rural patients.
   - **Faecal calprotectin** is age-adjusted and coupled less tightly in CD. It is confounded by NSAIDs, gut infections and PPIs, and is raised by CRC in the red-flag patients.
   - **CRP** is low in half of UC patients ("non-responders") and raised by infections.
   - **Other tests:** Hb, ferritin, albumin, platelets and WBC; LFTs and CA 19-9 for PSC patients; anti-TNF trough levels.
   - **Smart escalation:** worrying symptoms or wearable drift trigger a **home calprotectin test**. A result above 250 triggers a clinic follow-up.
6. **Sweat sensor** (`sweat.py`, **investigational**): sweat CRP, sweat calprotectin, IL-6 and TNF-α for ~30% of patients.
   - Noisier than stool calprotectin, with electrode drift and 10–20% dropped readings.
   - Simulated only. No such device is approved for IBD monitoring.
7. **Demo scenarios** (`scenarios.py`), 17 patients from §6.8 (listed in `demo_scenarios.csv`):

   | Patient | Scenario |
   |---|---|
   | P0001 | **Ananya R.**, the §10 video story (below) |
   | P0002–04 | Acute severe colitis: RHR > 90, fever, ≥ 6 bloody stools/day, CRP 60–150 |
   | P0005–06 | VTE pattern: RHR +22, SpO₂ −4, immobility, breathlessness, during a flare |
   | P0007–08 | Sepsis-like on steroids: fever ~39 °C, RHR +25, resp rate +6, HRV crash, CRP ~200, WBC ~19 |
   | P0009–10 | Bowel obstruction in stricturing CD: vomiting, no stool or gas, pain 8–9 |
   | P0011–12 | Ileostomy dehydration: 14–18 bag emptyings, RHR +15, dizziness, creatinine ~2 |
   | P0013–15 | Long-standing pancolitis with overdue colonoscopy: falling Hb and ferritin, weight loss, bleeding in remission, persistent FC while wearables stay stable |
   | P0016–17 | TB reactivation on anti-TNF: low-grade evening fever, night sweats, 4 kg weight loss, no TB screening on file |

   **Ananya's timeline:** RHR 64 → 69 over weeks 1–5 as HRV slips. There are no colds or stress in weeks 4–6, so the decoy check is clean. On 17 Aug 2026 a home calprotectin test reads **310**. Therapy is optimised on 19 Aug and she is back at baseline by week 9, with **no flare onset** (flare averted). She also has Hb 12.6 → 11.4 and −3.5 kg over the last 3 months, and a colonoscopy due in ~4 months, which matches the example dashboard card.

### Output files (`data/synthetic/`)

| File | Grain | Model input? |
|---|---|---|
| `patients.csv` | patient | ✅ static EHR (`display_name` is a Faker pseudonym) |
| `conditions.csv` | diagnosis | ✅ ICD-10 history |
| `wearables_daily.*` | patient × worn day | ✅ |
| `wearables_hourly_demo.*` | demo patient × hour | dashboard only |
| `symptoms.*` | patient × check-in day | ✅ |
| `labs.*` | result (`test`, `value`, `unit`, `setting` clinic/home/emergency, `reason`) | ✅ |
| `sweat.*` | patient × day, sensor owners only | ✅ ablation C only, investigational |
| `events.csv` | event | ❌ ground truth: flare ramps and onsets, steroid courses, decoys, emergencies |
| `ground_truth/latent_daily.*` | patient × day | ❌ labels + latent inflammation + context flags |
| `ground_truth/hidden_params.csv` | patient | ❌ simulator parameters |
| `manifest.json` | | run settings + cohort summary |

Never feed `events.csv` or `ground_truth/` to the model. `latent_daily` carries the targets.

### Prediction targets (`ground_truth/latent_daily`)

- **Inflammatory flare onset:** the first day latent inflammation reaches 0.6.
- **Symptomatic flare onset:** the first day the 3-day mean partial Mayo reaches 5 (UC), or HBI reaches 8 (CD).
- **Flare onset (primary):** the first day both hold. These are kept separate, as the Mount Sinai study distinguishes inflammatory from symptomatic flares.

The label columns are:
- `flare_within_14d`: 1 if a flare onset falls in days t+1 … t+14. It is `NaN` when no onset is seen but the window runs past the end of the record.
- `inflammatory_flare_within_14d` and `symptomatic_flare_within_14d`: the same, for the other two definitions.
- `days_to_next_flare` and `in_flare`.

Exclude `in_flare` days when training an onset predictor.

### Default cohort (seed 42, 800 patients × 365 days)

| Measure | Value |
|---|---|
| Flare onsets | 411 (0.51 per patient-year; 43.5% of patients flare) |
| `flare_within_14d` positive days | 2.0% (rare, so report PR-AUC) |
| Inflammatory-only onsets (no symptomatic flare) | 38 |
| Wearable days present / symptom check-in days | 83% / 73% |
| Median calprotectin: quiet periods vs 28 days before a flare | 49 vs 539 µg/g |
| 28 days before a flare vs quiet periods | Resting HR +4.0 vs +0.5 bpm; HRV 87% vs 99% of baseline; steps 89% vs 106% of baseline |
| Decoys in the record | 1,562 colds, 286 gut infections, 2,234 stress periods, 565 NSAID courses, 11 symptom spikes without inflammation |

The drift sizes are **design assumptions** informed by the literature (Hirten et al., *Gastroenterology* 2025), not measured effects.

### Limitations

- The data is synthetic only. Correlations exist because the generator puts them there.
- Effect sizes, decoy rates and confounders are assumptions to be tuned. They are not validated on Indian patients.
- The demo scenarios are deliberately clear-cut so they can be shown in the dashboard. Real presentations are messier.
- The sweat stream simulates an investigational technology (no FDA or CDSCO approval for IBD monitoring).
