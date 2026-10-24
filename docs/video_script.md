# Video script — IBD Digital Twin (target 18 minutes)

The submission form asks for a **15–20 minute** video; aim for 18:00 and never go past 20:00. Record the deck (`docs/presentation.pptx`) with a webcam inset, then switch to a screen recording of the live dashboard for section 7. Times are cumulative. Rehearse once with a timer. If you run long, cut from sections 1–5, never from the demo.

Before recording, run `make dashboard`, open http://localhost:8501 and keep the sidebar visible.

| # | Section | Slide | Duration | Ends at |
|---|---|---|---|---|
| 1 | Problem and India context | 1–2 | 2:30 | 2:30 |
| 2 | Evidence | 3 | 1:30 | 4:00 |
| 3 | Twin concept | 4 | 1:30 | 5:30 |
| 4 | Architecture | 5 | 2:30 | 8:00 |
| 5 | Synthetic data | 6–7 | 2:30 | 10:30 |
| 6 | Model results and ablation | 8–9 | 2:30 | 13:00 |
| 7 | **Live demo**: Ananya, an emergency, Cancer Safety | 10–12 + dashboard | 3:30 | 16:30 |
| 8 | India pathway and roadmap | 13 | 0:45 | 17:15 |
| 9 | Limitations and close | 14–15 | 0:45 | 18:00 |

---

## 1. Problem (slides 1–2, 2:30)

- Introduce the team and college (15 s).
- "Most teams will build a twin for diabetes or hypertension. We picked a disease where a twin changes the outcome most: inflammatory bowel disease."
- IBD in one sentence: lifelong inflammation of the gut, ulcerative colitis or Crohn's. No cure; patients cycle between remission and flares.
- India numbers (slide 2):
  - About 1.4 million patients, the largest in Asia.
  - Peak age 20–40.
  - Median 15-month diagnostic delay, costing 5.5 months of household income.
- **Pre-empt "is IBD prevalent?":** "It isn't diabetes-sized. It is in the acceleration stage — where Korea and Japan were 20–30 years ago — and it is now as common in rural symptomatic patients as in cities, while specialists stay in tier-1 cities."
- Today's care is reactive: the patient travels after the flare hits. Our one-liner: **a blood-pressure cuff for gut inflammation.**

## 2. Evidence (slide 3, 1:30)

- Mount Sinai, *Gastroenterology* 2025, 309 patients: smartwatch HRV falls and resting heart rate rises up to **7 weeks** before flares (F1 up to 0.90).
- Antwerp: stool calprotectin rises about **3 months** before UC relapse; two consecutive highs are 100% specific.
- Symptoms lag inflammation and can mislead. Wearables + labs resolve that mismatch.
- "The science exists. Nobody has packaged it as a twin a doctor can use."

## 3. Twin concept (slide 4, 1:30)

Cover the four verbs:
- **Mirror:** each signal compared with the patient's *own* baseline.
- **Predict:** calibrated 14-day flare risk plus a 28-day outlook.
- **Simulate:** what-if before acting.
- **Protect:** emergency rules and cancer surveillance.

Line: "Simulate is what makes it a twin, not just a classifier."

## 4. Architecture (slide 5, 2:30)

Walk the five layers top to bottom (open `docs/architecture.pdf` if zooming helps):
1. Synthetic patients and streams.
2. Fusion and personal baselines, one row per patient-day.
3. LightGBM vs a logistic baseline, SHAP, what-if.
4. Alerts and Cancer Safety rules.
5. The Streamlit dashboard.

Spend 45 s on the **red box**:
- Ground truth is used for labels and scoring only.
- We drop lab fields that encode hidden state.
- We read only prescriptions and logged colds from the events table.
- "There is an automated test that scrambles every data point after day t and proves features at day t don't change."

Close with: layers 2–5 are disease-agnostic (COPD, heart failure next), and new sensors are just new columns.

## 5. Synthetic data (slides 6–7, 2:30)

- Synthea has no IBD module, so we built a seeded generator: 800 patients × 365 days.
- One hidden variable, latent inflammation, drives every stream with lags and noise. There's an 8–12 week pre-flare ramp, and 20% of episodes settle on their own.
- Why it's hard:
  - Decoys: 1,562 colds, 2,234 stressful weeks, NSAID courses and gut infections.
  - Missing data: the watch is worn 83% of days.
  - "Silent" patients and IBS overlap.
- Chart: before a flare, resting HR +4 bpm, HRV 87% of baseline, steps 89%. Calprotectin 539 vs 49 µg/g. "These are design assumptions taken from the literature, not measurements."
- Slide 7, the four steps:
  1. Personal baseline on quiet days.
  2. Rolling windows and slopes.
  3. LightGBM with calibration.
  4. 5-fold cross-validation **grouped by patient**: no patient is ever in both train and test.
- Mention the rule: "if PR-AUC goes above 0.95 we treat it as a leakage bug."

## 6. Results (slides 8–9, 2:30)

- Main model on held-out patients: PR-AUC **0.881** vs 0.844 for logistic regression; AUROC 0.995.
- **99% of flare onsets caught** (408 of 411), with a median warning of **15 days**. The 28-day outlook gives a 20-day warning.
- **0.038 false alarms per patient-month** — about one per patient every two years.
- Ablation (slide 9) — the key slide:
  - Watch + EHR alone: PR-AUC 0.565, 68% of flares, with zero patient effort.
  - Adding calprotectin: 0.731.
  - Adding a 30-second daily check-in: 0.881.
  - The simulated sweat sensor adds +0.003, "so it stays investigational until it beats a stool test."

## 7. Live demo (3:30) — switch to the dashboard

**Ananya (2:00).** Use the sidebar **Ananya replay** buttons in order:

1. **Wk 1 · baseline**
   - Point at the patient card: 28, UC, 11 years, 5-ASA, 72% adherence.
   - Status green, 0%. Signals sit inside her personal baseline band.
2. **Wk 4 · watch drift**
   - Status amber. The alerts feed shows *Watch signals drifting*: HRV, resting HR and steps off baseline on 7 of 14 days.
   - Read the decoy check: "no cold, fever or infection logged."
   - Suggested action: *order home calprotectin*.
3. **Wk 5 · calprotectin 310**
   - The home test reads 310. The 28-day outlook jumps to **53%, red**.
   - Read the *Why* panel: day–night HRV rhythm −45%, resting HR 64 → 69, calprotectin 310 (+280).
   - Suggested action: teleconsult and review therapy.
   - Open the what-if table. Say honestly: "the model sees therapy as a static field, so it only nudges the number. A real twin would add treatment-effect evidence."
4. **Wk 6 · therapy optimised**
   - The *therapy ↑* marker appears on the risk chart on 19 Aug. Risk stays high while signals settle.
5. **Wk 9 · back to baseline**
   - Green. "Flare averted. Every number you just saw is the model's out-of-fold output for a patient it never trained on."

**Emergency (0:45).**
- Patient dropdown → **P0007 (Sepsis on steroids)**. Set "Today" to **8 Apr 2026**.
- Red banner: *Possible sepsis / abscess on steroids*. Fever, high HR, fast breathing, HRV crash, CRP support.
- "Steroids mask the signs; the watch doesn't." Mention there are six such rules, each tested on its seeded patients, and that each fires on under 0.005% of other days.

**Cancer Safety (0:45).**
- Open **P0013**, "Today" 30 Sep 2026, and scroll to the Cancer Safety panel.
- High CRC risk (20 years of pancolitis, active inflammation, inflammation burden).
- Colonoscopy overdue by nearly 4 years.
- Red flags: falling Hb, 4 kg weight loss, bleeding in remission.
- Switch to **Population** view: the overdue-surveillance list on the left.
- "The twin makes sure no high-risk patient misses the colonoscopy that catches cancer at stage I — about 90% five-year survival — instead of stage IV."

## 8. India pathway (slide 13, 0:45)

- **Today:** works with the watch people already own, plus a home stool test and a 30-second check-in. Teleconsult closes the rural distance.
- **Next:** a pilot with a gastroenterology centre — ethics approval, DPDP consent, the CDSCO software-as-medical-device route.
- **Later:** continuous sweat sensors once validated. Then the same twin for COPD and heart failure.

## 9. Limitations and close (slides 14–15, 0:45)

- Read the six limitation cards quickly. The key two: synthetic data, and what-if is not causal.
- "The twin flags risk; it never diagnoses."
- Close: "Digital twins exist for heart and diabetes. Wearable IBD flare prediction is proven in research. No one has combined them into an IBD digital twin. That's what we built." Thank the jury.

---

**Checklist before upload:** total length 15:00–20:00 · upload as unlisted YouTube · paste the link into the README table · check the link opens in a private window.
