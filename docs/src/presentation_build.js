const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const { applyTheme } = require("/root/.claude/skills/synced/96286b5f-d54f-48b7-95a9-ae71ffeeedf6_a33d5dcf-b39e-408f-bc24-f5cd76b04dc0/pptx/scripts/apply_theme.js");
const fa = require("react-icons/fa");
const md = require("react-icons/md");

const OUT = process.argv[2];
const DOCS = "/home/claude/ibd-digital-twin/docs/";
const ART = "/home/claude/ibd-digital-twin/artifacts/";
const SCR = "/tmp/claude-0/-home-claude/5342148a-6d67-56e7-abdc-82031b469b9e/scratchpad/deck/";

const THEME = {
  name: "IBD Twin",
  headFontFace: "Cambria", bodyFontFace: "Calibri",
  colors: { dk1: "1F2633", lt1: "FFFFFF", dk2: "14324A", lt2: "EEF3F6",
            accent1: "E4572E", accent2: "1B998B", accent3: "F2A541", accent4: "6C4F9E",
            accent5: "2E8B57", accent6: "8A8F98", hlink: "1B998B", folHlink: "6C4F9E" },
};
const HEX = THEME.colors;

async function icon(Comp, color, size = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Comp, { color: "#" + color, size: String(size) }));
  const buf = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}

(async () => {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9";
  pres.title = "IBD Digital Twin";
  pres.author = "Team prantik.pgp26 — IIM Shillong";
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  const C = pres.SchemeColor;

  pres.defineSlideMaster({
    title: "DARK", background: { color: C.text2 },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 1.55, w: 8.8, h: 1.4, fontSize: 40, bold: true, align: "left",
                                  color: C.background1, valign: "bottom", margin: 0 }, text: "" } },
      { placeholder: { options: { name: "body", type: "body", x: 0.6, y: 3.1, w: 8.8, h: 1.5, fontSize: 16,
                                  color: C.background2, valign: "top", margin: 0 }, text: "" } },
      { text: { text: "Synthetic data only · flags risk, never diagnoses",
                options: { x: 0.6, y: 5.1, w: 8.8, h: 0.3, fontSize: 10, color: C.accent6, margin: 0 } } },
    ],
  });
  pres.defineSlideMaster({
    title: "CONTENT", background: { color: C.background1 },
    margin: [0.5, 0.5, 0.6, 0.5],
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.32, w: 9.0, h: 0.65, fontSize: 22, bold: true, align: "left",
                                  color: C.text2, valign: "middle", margin: 0 }, text: "" } },
      { text: { text: "IBD Digital Twin · synthetic data only",
                options: { x: 0.5, y: 5.22, w: 6, h: 0.25, fontSize: 9, color: C.accent6, margin: 0 } } },
    ],
    slideNumber: { x: 9.0, y: 5.2, w: 0.5, h: 0.25, fontSize: 9, color: HEX.accent6, align: "right" },
  });

  const card = (s, x, y, w, h, fill = C.background2, name = "card") =>
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: fill }, line: { color: fill }, objectName: name });
  const txt = (s, text, o) => s.addText(text, { isTextBox: true, margin: 0, color: C.text1, fontSize: 14, valign: "top", ...o });
  const stat = (s, x, y, w, big, small, color = C.accent1) => {
    txt(s, big, { x, y, w, h: 0.75, fontSize: 36, bold: true, color, fontFace: THEME.headFontFace, valign: "bottom", objectName: "stat" });
    txt(s, small, { x, y: y + 0.8, w, h: 0.75, fontSize: 12, color: C.text1 });
  };
  const iconCircle = async (s, x, y, Comp, fill, d = 0.55) => {
    s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: fill }, line: { color: fill }, objectName: "icon-bg" });
    s.addImage({ data: await icon(Comp, "FFFFFF"), x: x + d * 0.22, y: y + d * 0.22, w: d * 0.56, h: d * 0.56, objectName: "icon" });
  };

  // 1 — title
  pres.addSection({ title: "Opening" });
  let s = pres.addSlide({ masterName: "DARK", sectionTitle: "Opening" });
  s.addText("IBD Digital Twin", { placeholder: "title" });
  s.addText([
    { text: "Predicting inflammatory bowel disease flares weeks before they hit", options: { breakLine: true } },
    { text: "Team prantik.pgp26 · IIM Shillong (Prantik Sarkar & Swapnil Ghatak)", options: { fontSize: 13, color: HEX.accent3 } },
  ], { placeholder: "body" });
  s.addImage({ data: await icon(fa.FaHeartbeat, HEX.accent1), x: 0.6, y: 0.7, w: 0.7, h: 0.7, objectName: "logo" });
  s.addNotes("Introduce the team. One line: a blood-pressure cuff for gut inflammation. Happiest Health Digital Twin challenge, Phase 1 submission.");

  // 2 — problem
  pres.addSection({ title: "Problem" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Problem" });
  s.addText("India has Asia's largest IBD population, and it is growing fast", { placeholder: "title" });
  const st = [["~1.4M", "patients in India (2010 est.), largest in Asia", C.accent1],
              ["20–40", "peak age: hits the working years", C.accent2],
              ["15 mo", "median diagnostic delay", C.accent4],
              ["5.5×", "monthly household income lost to that delay (₹1.36 lakh)", C.accent3]];
  st.forEach(([b, t, c], i) => { card(s, 0.5 + i * 2.3, 1.35, 2.1, 2.0); stat(s, 0.7 + i * 2.3, 1.45, 1.75, b, t, c); });
  txt(s, [
    { text: "Acceleration stage: ", options: { bold: true } },
    { text: "India is where Korea and Japan were 20–30 years ago (Nature 2025).", options: { breakLine: true } },
    { text: "Not just a city disease: ", options: { bold: true } },
    { text: "no rural–urban difference among 30,000+ symptomatic patients (AIG), but specialists sit in tier-1 cities.", options: { breakLine: true } },
    { text: "No cure: ", options: { bold: true } },
    { text: "care means keeping patients out of flares, yet today we react after the flare has hit." },
  ], { x: 0.5, y: 3.6, w: 9, h: 1.45, fontSize: 14, paraSpaceAfter: 4 });
  s.addNotes("3 minutes. Answer 'is IBD prevalent?' with growth and severity, not headcount. Sources: Kedia & Ahuja Pivot to Asia; Indian J Gastroenterol diagnostic delay study; Hracs/Kaplan Nature 2025; Banerjee et al. Lancet Reg Health SEA 2023.");

  // 3 — evidence
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Problem" });
  s.addText("The body warns us weeks before a flare", { placeholder: "title" });
  const ev = [[fa.FaHeartbeat, C.accent1, "7 weeks", "Smartwatch HRV falls, resting HR rises and steps drop up to 7 weeks before IBD flares; F1 up to 0.90", "Hirten et al., Mount Sinai, Gastroenterology 2025"],
              [md.MdScience, C.accent2, "3 months", "Stool calprotectin > 300 three months before UC relapse; two consecutive highs → 100% specificity", "Antwerp infliximab cohort"],
              [fa.FaUserMd, C.accent4, "Mismatch", "Symptoms lag inflammation and mislead; wearables + labs resolve the symptom–inflammation mismatch", "Systematic review, repeated calprotectin"]];
  for (let i = 0; i < 3; i++) {
    const [I, c, big, body, src] = ev[i]; const x = 0.5 + i * 3.05;
    card(s, x, 1.3, 2.85, 3.6);
    await iconCircle(s, x + 0.25, 1.5, I, c);
    txt(s, big, { x: x + 0.25, y: 2.2, w: 2.4, h: 0.6, fontSize: 30, bold: true, color: c, fontFace: THEME.headFontFace });
    txt(s, body, { x: x + 0.25, y: 2.9, w: 2.4, h: 1.4, fontSize: 13 });
    txt(s, src, { x: x + 0.25, y: 4.35, w: 2.4, h: 0.4, fontSize: 10, color: C.accent6, italic: true });
  }
  s.addNotes("2 minutes. The evidence base. Emphasise this is research-proven but not productised: no IBD digital twin exists.");

  // 4 — concept
  pres.addSection({ title: "Solution" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Solution" });
  s.addText("A virtual patient that mirrors, predicts, simulates and protects", { placeholder: "title" });
  const cc = [[md.MdPerson, C.accent2, "Mirror", "EHR + watch + daily check-in + labs, each signal against the patient's own baseline"],
              [md.MdTrendingUp, C.accent1, "Predict", "Calibrated risk of a flare starting in 14 days, plus a 28-day outlook"],
              [md.MdTune, C.accent4, "Simulate", "What-if: adherence 100%, anti-TNF, stop NSAIDs (model-estimated)"],
              [md.MdShield, C.accent5, "Protect", "6 emergency rules within hours; Cancer Safety panel for colonoscopy surveillance"]];
  for (let i = 0; i < 4; i++) {
    const [I, c, h, b] = cc[i]; const x = 0.5 + (i % 2) * 4.6, y = 1.3 + Math.floor(i / 2) * 1.85;
    card(s, x, y, 4.4, 1.65);
    await iconCircle(s, x + 0.25, y + 0.3, I, c, 0.7);
    txt(s, h, { x: x + 1.2, y: y + 0.25, w: 3.0, h: 0.4, fontSize: 18, bold: true, color: c });
    txt(s, b, { x: x + 1.2, y: y + 0.7, w: 3.0, h: 0.85, fontSize: 13 });
  }
  s.addNotes("2 minutes. Twin concept. The simulate step is what makes this a twin rather than a classifier.");

  // 5 — architecture
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Solution" });
  s.addText("Five layers, one-way data flow, ground truth kept out", { placeholder: "title" });
  s.addImage({ path: DOCS + "architecture.png", x: 1.35, y: 1.1, w: 7.3, h: 4.0, objectName: "architecture" });
  s.addNotes("3 minutes. Walk the five layers top to bottom. Stress: ground truth is labels-only; lab reason/setting dropped; only prescriptions and logged colds/infections read from events. Disease-agnostic layers 2-5; sensor-agnostic.");

  // 6 — synthetic data
  pres.addSection({ title: "Data and model" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Data and model" });
  s.addText("800 synthetic patients × 365 days, built to be hard", { placeholder: "title" });
  txt(s, [
    { text: "Latent inflammation drives every stream with lags and noise", options: { bullet: true, breakLine: true } },
    { text: "8–12 week pre-flare ramp; 20% of episodes settle on their own", options: { bullet: true, breakLine: true } },
    { text: "Decoys: 1,562 colds, 2,234 stress weeks, 565 NSAID courses, 286 gut infections", options: { bullet: true, breakLine: true } },
    { text: "Missing data: watch worn 83% of days, check-ins 73%", options: { bullet: true, breakLine: true } },
    { text: "\"Silent\" patients and IBS overlap (symptoms without inflammation)", options: { bullet: true, breakLine: true } },
    { text: "17 seeded demo patients incl. Ananya and 6 emergency scenarios", options: { bullet: true } },
  ], { x: 0.5, y: 1.25, w: 4.4, h: 3.7, fontSize: 14, paraSpaceAfter: 6 });
  s.addChart(pres.charts.BAR, [{ name: "Quiet periods", labels: ["Resting HR Δ (bpm)", "HRV (% of baseline)", "Steps (% of baseline)"], values: [0.5, 99.2, 105.9] },
                               { name: "28 days pre-flare", labels: ["Resting HR Δ (bpm)", "HRV (% of baseline)", "Steps (% of baseline)"], values: [4.0, 86.9, 88.9] }], {
    x: 5.1, y: 1.15, w: 4.4, h: 3.0, barDir: "bar", barGrouping: "clustered", chartColors: [HEX.accent6, HEX.accent1],
    showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 10, dataLabelFontFace: "+mn-lt", dataLabelColor: HEX.dk1,
    catAxisLabelFontSize: 10, catAxisLabelFontFace: "+mn-lt", catAxisLabelColor: HEX.dk1, valAxisHidden: true,
    valGridLine: { style: "none" }, catGridLine: { style: "none" }, showLegend: true, legendPos: "b", legendFontSize: 10, legendFontFace: "+mn-lt",
    showTitle: true, title: "Wearables drift before a flare", titleFontSize: 12, titleFontFace: "+mn-lt", titleColor: HEX.dk2, objectName: "drift-chart" });
  txt(s, "Calprotectin median: 49 µg/g quiet vs 539 µg/g in the 28 days pre-flare", { x: 5.1, y: 4.3, w: 4.4, h: 0.6, fontSize: 12, italic: true, color: C.text2 });
  s.addNotes("3 minutes. Synthea has no IBD module, so we built a seeded generator. Drift sizes are design assumptions informed by the literature, not measurements.");

  // 7 — fusion + model
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Data and model" });
  s.addText("Personal baselines, causal features, patient-grouped validation", { placeholder: "title" });
  const steps = [["1", "Personal baseline", "Median / MAD of each signal over the patient's own quiet days (no cold, NSAID, steroid, high calprotectin)"],
                 ["2", "Features at day t", "z-scores; 7/14/28-day mean, SD, min, max, slope; co-movement; lab deltas; symptom trends; context flags"],
                 ["3", "Model", "Logistic baseline vs LightGBM; class weights; Platt calibration; threshold on validation patients"],
                 ["4", "Validation", "5-fold CV grouped by patient; out-of-fold scores in the dashboard; leakage test scrambles all data after t"]];
  steps.forEach(([n, h, b], i) => {
    const x = 0.5 + i * 2.3;
    card(s, x, 1.3, 2.1, 3.0);
    s.addShape(pres.shapes.OVAL, { x: x + 0.2, y: 1.5, w: 0.5, h: 0.5, fill: { color: C.accent2 }, line: { color: C.accent2 }, objectName: "step-num" });
    txt(s, n, { x: x + 0.2, y: 1.5, w: 0.5, h: 0.5, align: "center", valign: "middle", bold: true, color: C.background1, fontSize: 16 });
    txt(s, h, { x: x + 0.2, y: 2.15, w: 1.75, h: 0.4, bold: true, fontSize: 15, color: C.text2 });
    txt(s, b, { x: x + 0.2, y: 2.6, w: 1.75, h: 1.6, fontSize: 12 });
  });
  txt(s, "Target: a flare onset (inflammatory and symptomatic) in days t+1 to t+14. 2.3% of training rows are positive, so we report PR-AUC.",
      { x: 0.5, y: 4.5, w: 9, h: 0.5, fontSize: 13, italic: true, color: C.text2 });
  s.addNotes("Explain no-leakage: features at t use data up to t only; there is a pytest that proves it. Guard: PR-AUC above 0.95 is treated as a bug.");

  // 8 — results
  pres.addSection({ title: "Results" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
  s.addText("Catches 99% of flares about 2 weeks ahead and rarely cries wolf", { placeholder: "title" });
  const rs = [["0.881", "PR-AUC on held-out patients (logistic 0.844)", C.accent1],
              ["99%", "of flare onsets caught (408 of 411) by an alert in the 14 days before", C.accent2],
              ["15 days", "median warning lead time (28-day outlook: 20 days)", C.accent4],
              ["0.038", "false alarms per patient-month (≈ 1 per 26 months)", C.accent5]];
  rs.forEach(([b, t, c], i) => { card(s, 0.5 + i * 2.3, 1.3, 2.1, 2.0); stat(s, 0.7 + i * 2.3, 1.4, 1.75, b, t, c); });
  s.addTable([
    [{ text: "Held-out patients", options: { bold: true, color: HEX.lt1, fill: { color: HEX.dk2 } } },
     { text: "LightGBM", options: { bold: true, color: HEX.lt1, fill: { color: HEX.dk2 } } },
     { text: "Logistic", options: { bold: true, color: HEX.lt1, fill: { color: HEX.dk2 } } }],
    ["AUROC", "0.995", "0.990"], ["F1 at threshold", "0.810", "0.792"],
    ["Sensitivity / specificity (days)", "0.86 / 0.99", "0.81 / 0.99"], ["Brier score", "0.0063", "0.0072"],
  ], { x: 0.5, y: 3.5, w: 9, colW: [4.2, 2.4, 2.4], fontSize: 12, rowH: 0.3, border: { type: "solid", color: HEX.lt2, pt: 1 }, color: HEX.dk1 });
  s.addNotes("3 minutes. 5-fold patient-grouped CV. Lead time is from the start of the alert episode to onset. Synthetic data: strong metrics show the pipeline works, not clinical accuracy.");

  // 9 — ablation
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
  s.addText("Every stream earns its place, except the sweat sensor (for now)", { placeholder: "title" });
  s.addChart(pres.charts.BAR, [{ name: "PR-AUC", labels: ["A  Watch + EHR", "B  + labs", "C  + sweat", "D  + daily check-in", "E  D + sweat"], values: [0.565, 0.731, 0.734, 0.881, 0.878] }], {
    x: 0.5, y: 1.15, w: 5.6, h: 3.8, barDir: "col", chartColors: [HEX.accent2, HEX.accent2, HEX.accent6, HEX.accent1, HEX.accent6],
    showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 11, dataLabelFontFace: "+mn-lt", dataLabelColor: HEX.dk1, dataLabelFormatCode: "0.000",
    catAxisLabelFontSize: 10, catAxisLabelFontFace: "+mn-lt", catAxisLabelColor: HEX.dk1, valAxisHidden: true, valAxisMinVal: 0, valAxisMaxVal: 1,
    valGridLine: { style: "none" }, catGridLine: { style: "none" }, showLegend: false,
    showTitle: true, title: "PR-AUC, 14-day flare onset (held-out patients)", titleFontSize: 12, titleFontFace: "+mn-lt", titleColor: HEX.dk2, objectName: "ablation-chart" });
  card(s, 6.4, 1.25, 3.1, 3.7);
  txt(s, [
    { text: "Watch alone finds 68% of flares", options: { bold: true, breakLine: true } },
    { text: "passively, with no patient effort.", options: { breakLine: true } },
    { text: " ", options: { breakLine: true, fontSize: 6 } },
    { text: "Calprotectin adds the most per test", options: { bold: true, breakLine: true } },
    { text: "PR-AUC 0.57 → 0.73; 90% of flares.", options: { breakLine: true } },
    { text: " ", options: { breakLine: true, fontSize: 6 } },
    { text: "A 30-second check-in closes the gap", options: { bold: true, breakLine: true } },
    { text: "99% of flares; symptoms rise in the final 2 weeks.", options: { breakLine: true } },
    { text: " ", options: { breakLine: true, fontSize: 6 } },
    { text: "Sweat sensor: +0.003", options: { bold: true, breakLine: true } },
    { text: "Stays investigational until it beats stool tests." },
  ], { x: 6.6, y: 1.4, w: 2.75, h: 3.45, fontSize: 12 });
  s.addNotes("The ablation quantifies the value of each stream: A wearables+EHR, B +labs, C +sweat, D +symptoms (main), E D+sweat.");

  // 10 — Ananya
  pres.addSection({ title: "Demo" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Demo" });
  s.addText("Ananya, 28, Bengaluru: a flare averted", { placeholder: "title" });
  const lab = ["06 Jul","09 Jul","12 Jul","15 Jul","18 Jul","21 Jul","24 Jul","27 Jul","30 Jul","02 Aug","05 Aug","08 Aug","11 Aug","14 Aug","17 Aug","20 Aug","23 Aug","26 Aug","29 Aug","01 Sep","04 Sep","07 Sep","10 Sep","13 Sep","16 Sep","19 Sep"];
  const labS = lab.map((l, i) => (i % 4 === 0 ? l : ""));
  const r14 = [0,0,0,0,0,0,0.1,0,0,0.2,0.2,0.2,0.3,0.6,2.0,15.7,18.8,32.0,14.0,0.5,0.1,0,0,0,0,0];
  const r28 = [0.1,0.3,0.3,0.3,0.4,0.4,0.9,1.2,2.0,5.3,10.2,15.0,9.6,8.8,46.0,83.9,84.8,89.8,86.0,45.1,11.7,2.6,1.0,0.9,0,0];
  s.addChart(pres.charts.LINE, [{ name: "28-day outlook (%)", labels: labS, values: r28 }, { name: "14-day risk (%)", labels: labS, values: r14 }], {
    x: 0.4, y: 1.1, w: 5.7, h: 3.9, chartColors: [HEX.accent4, HEX.accent2], lineSize: 2.5, lineDataSymbol: "none",
    catAxisLabelFontSize: 9, catAxisLabelFontFace: "+mn-lt", catAxisLabelColor: HEX.dk1, catAxisLabelRotate: 0,
    valAxisLabelFontSize: 9, valAxisLabelFontFace: "+mn-lt", valAxisLabelColor: HEX.dk1, valAxisMinVal: 0, valAxisMaxVal: 100, valAxisMajorUnit: 25,
    valGridLine: { color: "E3E7EB", size: 0.5 }, catGridLine: { style: "none" }, showLegend: true, legendPos: "b", legendFontSize: 10, legendFontFace: "+mn-lt",
    showTitle: true, title: "Model output for P0001 (out-of-fold)", titleFontSize: 12, titleFontFace: "+mn-lt", titleColor: HEX.dk2, objectName: "ananya-chart" });
  const tl = [["Wk 1 · 13 Jul", "Green: at baseline", C.accent5],
              ["Wk 4 · 11 Aug", "Amber: watch drift on 7 of 14 days, no cold → home calprotectin", C.accent3],
              ["Wk 5 · 17–18 Aug", "Red: calprotectin 310, outlook 53%; HRV rhythm −45%, RHR 64→69", C.accent1],
              ["Wk 6 · 19–24 Aug", "Therapy optimised; outlook peaks while signals settle", C.accent4],
              ["Wk 9 · 14 Sep", "Green: back to baseline, flare averted", C.accent5]];
  tl.forEach(([w, t, c], i) => {
    const y = 1.15 + i * 0.78;
    s.addShape(pres.shapes.OVAL, { x: 6.35, y: y + 0.06, w: 0.2, h: 0.2, fill: { color: c }, line: { color: c }, objectName: "tl-dot" });
    txt(s, w, { x: 6.7, y, w: 2.8, h: 0.25, fontSize: 11, bold: true, color: C.text2 });
    txt(s, t, { x: 6.7, y: y + 0.25, w: 2.8, h: 0.5, fontSize: 10.5 });
  });
  s.addNotes("4 minutes live demo: use the Ananya replay buttons in the sidebar. Then open P0002 on its emergency day (acute severe colitis) and P0013 for the Cancer Safety panel. Every number shown is model output, not scripted.");

  // 11 — dashboard
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Demo" });
  s.addText("The doctor's view: status, why, what-if and next step", { placeholder: "title" });
  s.addImage({ path: SCR + "patient_top.png", x: 0.5, y: 1.1, w: 4.0 * 1040 / 1070, h: 4.0, objectName: "dashboard" });
  const dash = [["Population view", "All patients sorted by emergency, then status; overdue colonoscopies"],
                ["Patient view", "Card, 14-day + 28-day gauges, signals vs baseline band, labs, alerts"],
                ["Why + what-if", "Top-5 SHAP drivers in plain words; re-score with therapy changes"],
                ["Replay", "Date slider sets 'today' for any patient"]];
  dash.forEach(([h, b], i) => {
    txt(s, h, { x: 5.0, y: 1.2 + i * 0.95, w: 4.5, h: 0.3, fontSize: 14, bold: true, color: C.accent2 });
    txt(s, b, { x: 5.0, y: 1.5 + i * 0.95, w: 4.5, h: 0.55, fontSize: 12 });
  });
  s.addNotes("Run locally with one command: make dashboard. Streamlit + Plotly.");

  // 12 — safety
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Demo" });
  s.addText("Safety nets: emergencies in hours, cancer surveillance in years", { placeholder: "title" });
  const H = (t) => ({ text: t, options: { bold: true, color: HEX.lt1, fill: { color: HEX.dk2 } } });
  s.addTable([[H("Emergency rule"), H("Pattern"), H("Seeded")],
    ["Acute severe colitis", "≥6 bloody stools + RHR > 90 + fever", "P0002–04"],
    ["VTE / PE", "RHR jump + SpO₂ drop + immobility", "P0005–06"],
    ["Sepsis on steroids", "Fever + RHR + resp rate ↑ + HRV crash", "P0007–08"],
    ["Bowel obstruction", "Vomiting + no stool/gas, stricture", "P0009–10"],
    ["Stoma dehydration", "High output + RHR ↑ + dizziness", "P0011–12"],
    ["TB reactivation", "Fevers + night sweats + weight loss, anti-TNF", "P0016–17"]],
    { x: 0.5, y: 1.2, w: 5.6, colW: [1.7, 2.9, 1.0], fontSize: 11, rowH: 0.36, border: { type: "solid", color: HEX.lt2, pt: 1 }, color: HEX.dk1 });
  txt(s, "Every rule fires on its seeded patients and on < 0.005% of other patient-days",
      { x: 0.5, y: 3.95, w: 5.6, h: 0.5, fontSize: 12, italic: true, color: C.text2 });
  card(s, 6.4, 1.2, 3.1, 3.75);
  await iconCircle(s, 6.6, 1.35, md.MdShield, C.accent5);
  txt(s, "Cancer Safety", { x: 7.3, y: 1.45, w: 2.1, h: 0.4, fontSize: 16, bold: true, color: C.accent5 });
  txt(s, [
    { text: "CRC risk level (BSG 2019 + inflammation burden)", options: { bullet: true, breakLine: true } },
    { text: "Next colonoscopy: 1 / 3 / 5 years; PSC yearly; overdue flag", options: { bullet: true, breakLine: true } },
    { text: "Red flags: falling Hb, weight loss, bleeding in remission, labs worse while watch is stable", options: { bullet: true, breakLine: true } },
    { text: "Skin, HPV, PSC and TB screening tracker", options: { bullet: true } },
  ], { x: 6.6, y: 2.05, w: 2.75, h: 2.4, fontSize: 11.5, paraSpaceAfter: 4 });
  txt(s, "Surveillance support, not cancer detection", { x: 6.6, y: 4.5, w: 2.75, h: 0.35, fontSize: 10, italic: true, color: C.accent6 });
  s.addNotes("Show P0007 on 8 Apr 2026 (sepsis) and P0013 Cancer Safety. Stage I CRC ~90% 5-year survival vs stage IV ~13-15%.");

  // 13 — roadmap
  pres.addSection({ title: "Close" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Close" });
  s.addText("India pathway: start with the watch people already own", { placeholder: "title" });
  const rm = [[fa.FaClock, C.accent2, "Today", "Smartwatch + home calprotectin + 30-second check-in; teleconsult for rural patients far from a specialist"],
              [md.MdScience, C.accent3, "Next", "Pilot with a gastroenterology centre under ethics approval and DPDP Act consent; CDSCO software-as-medical-device pathway"],
              [md.MdSensors, C.accent4, "Later", "Continuous sweat-biomarker sensors once validated (CDSCO investigational route); extend the twin to COPD and heart failure"]];
  for (let i = 0; i < 3; i++) {
    const [I, c, h, b] = rm[i]; const x = 0.5 + i * 3.05;
    card(s, x, 1.3, 2.85, 3.5);
    await iconCircle(s, x + 0.25, 1.5, I, c);
    txt(s, h, { x: x + 0.25, y: 2.2, w: 2.4, h: 0.45, fontSize: 20, bold: true, color: c });
    txt(s, b, { x: x + 0.25, y: 2.75, w: 2.4, h: 1.9, fontSize: 13 });
  }
  s.addNotes("1 minute. Layers 2-5 are disease-agnostic; the sensor slot is sensor-agnostic.");

  // 14 — limitations
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Close" });
  s.addText("What this prototype does not prove", { placeholder: "title" });
  const lim = [["Synthetic data", "Correlations exist because the generator puts them there; drift sizes are literature-informed assumptions"],
               ["Not causal", "What-if re-scores the model; therapy is a static EHR field, so projected changes are small and not treatment effects"],
               ["Non-specific signals", "Colds, stress and alcohol move the watch too; mitigated by logged decoys, labs and symptoms"],
               ["Confounded labs", "Calprotectin rises with NSAIDs, infections, PPIs, TB, CRC; CRP is not gut-specific"],
               ["Investigational sensor", "No FDA or CDSCO approval for sweat-based IBD monitoring"],
               ["Not validated in India", "Needs ethics approval, DPDP compliance, CDSCO pathway and clinician oversight"]];
  lim.forEach(([h, b], i) => {
    const x = 0.5 + (i % 2) * 4.6, y = 1.2 + Math.floor(i / 2) * 1.25;
    card(s, x, y, 4.4, 1.1);
    txt(s, h, { x: x + 0.2, y: y + 0.12, w: 4.0, h: 0.3, fontSize: 14, bold: true, color: C.accent1 });
    txt(s, b, { x: x + 0.2, y: y + 0.45, w: 4.0, h: 0.6, fontSize: 11.5 });
  });
  s.addNotes("1 minute. Flags risk, never diagnoses.");

  // 15 — close
  s = pres.addSlide({ masterName: "DARK", sectionTitle: "Close" });
  s.addText("No one has built an IBD digital twin. We did.", { placeholder: "title" });
  s.addText([
    { text: "Flares caught weeks ahead · emergencies within hours · no missed colonoscopy", options: { breakLine: true } },
    { text: "github.com/Prodman-PS/prantik.pgp26_IIM_Shillong · make dashboard", options: { fontSize: 13, color: HEX.accent3 } },
  ], { placeholder: "body" });
  s.addNotes("Close with the one-liner. Thank the jury.");

  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})();
