"""IBD Digital Twin — doctor dashboard (Streamlit).

    streamlit run src/dashboard/app.py        # or: make dashboard

Decision support on synthetic data. The twin flags risk; it never diagnoses.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from src.alerts.cancer_safety import cancer_safety  # noqa: E402
from src.alerts.trend_alerts import (AMBER, RED, active_flare, suggested_action, traffic_light, twin_status,  # noqa: E402
                                     wearable_drift)
from src.dashboard.components import charts, data  # noqa: E402
from src.models.explain import explain_row  # noqa: E402
from src.models.twin import load_model  # noqa: E402
from src.models.whatif import LABEL as WHATIF_LABEL, MEDS, PRESETS, whatif  # noqa: E402

st.set_page_config(page_title="IBD Digital Twin", page_icon="🩺", layout="wide")

START, END = date(2025, 10, 1), date(2026, 9, 30)
EMOJI = {"green": "🟢", "amber": "🟠", "red": "🔴", "grey": "⚪", "flare": "🟣"}
STATUS = {"green": "Low", "amber": "Rising", "red": "High", "grey": "No data", "flare": "In active flare"}
SCENARIO_LABEL = {"ananya_demo": "Ananya demo story", "acute_severe_colitis": "Acute severe colitis", "vte": "VTE / PE",
                  "sepsis_on_steroids": "Sepsis on steroids", "bowel_obstruction": "Bowel obstruction",
                  "stoma_dehydration": "Stoma dehydration", "crc_red_flags": "CRC red flags",
                  "tb_reactivation": "TB reactivation"}
# Ananya's story (Build Guide §3): ramp begins 11 Jul 2026, home calprotectin 310 on 17 Aug, therapy optimised 19 Aug.
ANANYA_REPLAY = {"Wk 1 · baseline": date(2026, 7, 13), "Wk 4 · watch drift": date(2026, 8, 11),
                 "Wk 5 · calprotectin 310": date(2026, 8, 18), "Wk 6 · therapy optimised": date(2026, 8, 24),
                 "Wk 9 · back to baseline": date(2026, 9, 14)}

# ------------------------------------------------------------------ state
ss = st.session_state
ss.setdefault("today", date(2026, 8, 18))
ss.setdefault("pid", "P0001")
ss.setdefault("view", "Patient")


def _goto(pid=None, day=None, view=None):
    if pid:
        ss.pid = pid
    if day:
        ss.today = day
    if view:
        ss.view = view


_missing = [f for f in (data.FEAT, data.ART / "daily.parquet", data.ART / "alerts.parquet", data.ART / "model_fold0.txt")
            if not f.exists()]
if _missing:
    st.error("Derived files are missing. Run `make features` (about 45 seconds; trained models are already in "
             "artifacts/) or the full `make train` (about 15 minutes), then reload this page.  \n"
             "Missing: " + ", ".join(str(f.relative_to(data.ROOT)) for f in _missing))
    st.stop()

P = data.patients()
SCEN = data.scenarios()
D = data.daily()
A = data.alerts()

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.markdown("### 🩺 IBD Digital Twin")
    st.radio("View", ["Population", "Patient", "Model results"], key="view", horizontal=True)
    st.slider("Today", min_value=START, max_value=END, key="today", format="DD MMM YYYY")
    c1, c2 = st.columns(2)
    c1.button("◀ 1 week", on_click=lambda: _goto(day=max(START, ss.today - timedelta(days=7))), width="stretch")
    c2.button("1 week ▶", on_click=lambda: _goto(day=min(END, ss.today + timedelta(days=7))), width="stretch")

    order = list(SCEN) + [p for p in P.index if p not in SCEN]
    fmt = lambda p: f"{p} · {P.loc[p, 'display_name']} ({P.loc[p, 'ibd_type']})" + (
        f" — {SCENARIO_LABEL.get(SCEN[p], SCEN[p])}" if p in SCEN else "")
    st.selectbox("Patient", order, key="pid", format_func=fmt)

    st.markdown("**▶ Ananya replay**")
    for label, d in ANANYA_REPLAY.items():
        st.button(label, key=f"replay_{label}", on_click=_goto, kwargs={"pid": "P0001", "day": d, "view": "Patient"},
                  width="stretch")
    st.caption("Synthetic data only · not medical advice · flags risk, never diagnoses")

today = pd.Timestamp(ss.today)
st.warning("**Synthetic data only — not medical advice.** This proof-of-concept flags risk for clinician review; "
           "it does not diagnose. Sweat-sensor data is investigational and simulated.", icon="⚠️")


# ------------------------------------------------------------------ helpers
@st.cache_data(show_spinner=False)
def population_table(day: pd.Timestamp):
    d = D[D["date"] == day].set_index("patient_id")
    prev = D[D["date"] == day - pd.Timedelta(days=7)].set_index("patient_id")["risk28"]
    recent = A[(A["date"] <= day) & (A["date"] > day - pd.Timedelta(days=7))]
    rows = []
    for pid, r in d.iterrows():
        p = P.loc[pid]
        cs = cancer_safety(p, r, day, risk=r["risk"])
        al = recent[recent["patient_id"] == pid]
        em = al[al["kind"] == "emergency"]["title"].unique().tolist()
        tr = al[al["kind"] == "trend"]["title"].unique().tolist()
        if cs.overdue:
            surv = "Overdue"
        elif cs.surveillance_applies:
            surv = f"Due in {cs.months_to_due:.0f} mo"
        else:
            surv = "—"
        drift = wearable_drift(r)
        status = twin_status(r["risk"], r["risk28"], drift, active_flare(r))
        rows.append({"patient_id": pid, "name": p["display_name"], "age": int(p["age"]), "type": p["ibd_type"],
                     "light": "🚨" if em else EMOJI[status], "status": status, "risk": 100 * r["risk"], "risk28": 100 * r["risk28"],
                     "change_7d": 100 * (r["risk28"] - prev.get(pid, np.nan)), "drift": "⌚ drift" if drift else "",
                     "emergency": " · ".join(em), "trend_alerts": " · ".join(tr),
                     "crc_risk": cs.risk_level, "colonoscopy": surv, "red_flags": len(cs.red_flags),
                     "overdue": cs.overdue, "scenario": SCENARIO_LABEL.get(SCEN.get(pid, ""), "")})
    t = pd.DataFrame(rows)
    t["_em"] = t["emergency"].ne("")
    t["_st"] = t["status"].map({"red": 4, "amber": 3, "flare": 2, "green": 1, "grey": 0})
    return t.sort_values(["_em", "_st", "risk", "risk28"], ascending=False).drop(columns=["_em", "_st"]).reset_index(drop=True)


def population_view():
    t = population_table(today)
    st.subheader(f"My IBD patients · {today:%d %b %Y}")
    k = st.columns(6)
    k[0].metric("🔴 High", int((t["status"] == "red").sum()), help="14-day risk or 28-day outlook ≥ 50%")
    k[1].metric("🟠 Rising", int((t["status"] == "amber").sum()), help="Risk or outlook 20–50%, or watch drift")
    k[2].metric("🟣 In flare", int((t["status"] == "flare").sum()),
                help="Already flaring (symptoms near threshold or on steroids); onset risk not applicable")
    k[3].metric("🟢 Low", int((t["status"] == "green").sum()))
    k[4].metric("🚨 Emergency (7 d)", int(t["emergency"].ne("").sum()))
    k[5].metric("🔬 Colonoscopy overdue", int(t["overdue"].sum()))

    q = st.text_input("Filter by name or ID", placeholder="e.g. Ananya or P0013")
    view = t if not q else t[t["name"].str.contains(q, case=False) | t["patient_id"].str.contains(q, case=False)]
    st.caption("Sorted by emergency alerts, then status (worst of 14-day risk, 28-day outlook and watch drift). "
               "Select a row to open the patient.")
    ev = st.dataframe(
        view, hide_index=True, height=480, on_select="rerun", selection_mode="single-row", key="poptable",
        column_order=["light", "patient_id", "name", "age", "type", "risk", "risk28", "change_7d", "drift", "emergency",
                      "trend_alerts", "crc_risk", "colonoscopy", "red_flags", "scenario"],
        column_config={
            "light": st.column_config.TextColumn("", width="small"),
            "patient_id": "ID", "name": "Name", "age": "Age", "type": "Type",
            "risk": st.column_config.ProgressColumn("14-day risk", format="%.0f%%", min_value=0, max_value=100),
            "risk28": st.column_config.ProgressColumn("28-day outlook", format="%.0f%%", min_value=0, max_value=100),
            "change_7d": st.column_config.NumberColumn("Δ outlook 7 d", format="%+.0f pts"),
            "drift": "Watch",
            "emergency": "🚨 Emergency (7 d)", "trend_alerts": "🟠 Trend alerts (7 d)",
            "crc_risk": "CRC risk", "colonoscopy": "Colonoscopy", "red_flags": "Red flags",
            "scenario": "Seeded demo",
        })
    sel = ev.selection.rows if ev and hasattr(ev, "selection") else []
    if sel:
        pid = view.iloc[sel[0]]["patient_id"]
        st.button(f"Open {pid} · {P.loc[pid, 'display_name']} →", type="primary",
                  on_click=_goto, kwargs={"pid": pid, "view": "Patient"})

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### 🔬 Overdue surveillance colonoscopy")
        od = t[t["overdue"]].sort_values("red_flags", ascending=False)
        st.dataframe(od[["patient_id", "name", "crc_risk", "red_flags"]], hide_index=True, height=240,
                     column_config={"patient_id": "ID", "name": "Name", "crc_risk": "CRC risk", "red_flags": "Red flags"})
    with c2:
        st.markdown("##### 🚨 Emergency alerts, last 7 days")
        em = A[(A["kind"] == "emergency") & (A["date"] <= today) & (A["date"] > today - pd.Timedelta(days=7))]
        em = em.sort_values("date", ascending=False).drop_duplicates(["patient_id", "rule"])
        st.dataframe(em[["date", "patient_id", "title", "action"]], hide_index=True, height=240,
                     column_config={"date": st.column_config.DateColumn("Date", format="DD MMM"), "patient_id": "ID",
                                    "title": "Pattern", "action": "Advice"})


def _card(p, d_today, flares_so_far):
    meds = f"{p['current_medication']} · adherence {100 * p['medication_adherence']:.0f}%"
    extent = p["disease_extent"] + (f", {p['cd_behaviour']}" if isinstance(p["cd_behaviour"], str) and p["cd_behaviour"] else "")
    genes = [g for g, c in [("NOD2", "nod2_variant"), ("IL23R R381Q (protective)", "il23r_r381q_protective"),
                            ("HLA-DRB1*01:03", "hla_drb1_0103")] if str(p[c]).lower() == "true"]
    st.markdown(f"### {p['display_name']}  \n"
                f"**{p['age']} y {p['sex']}** · {p['region']}, {p['state']} · `{p['patient_id']}`")
    st.markdown(
        f"- **{'Ulcerative colitis' if p['ibd_type'] == 'UC' else 'Crohn’s disease'}** — {extent}\n"
        f"- {p['years_since_diagnosis']:.0f} years since diagnosis (diagnostic delay {p['diagnostic_delay_months']:.0f} mo)\n"
        f"- **Therapy:** {meds}\n"
        f"- **Flares:** {p['past_flares_count']} before record · {flares_so_far} this year · "
        f"{p['hospitalisations']} hospitalisations · surgery: {p['surgeries']}\n"
        f"- **Genetics:** {', '.join(genes) or 'no markers'} · **Smoking:** {p['smoking_status']}\n"
        f"- **Comorbidities:** {p['comorbidities'] if isinstance(p['comorbidities'], str) else 'none'} · "
        f"**Device:** {p['wearable_device']}")


def patient_view(pid):
    p = P.loc[pid]
    d = D[D["patient_id"] == pid].sort_values("date")
    feat = data.features_for(pid)
    row_d = d[d["date"] == today].iloc[0]
    frow = feat[feat["date"] == today].iloc[0]
    risk, risk28 = float(row_d["risk"]), float(row_d["risk28"])
    drift = wearable_drift(row_d)
    in_flare = active_flare(row_d)
    light = twin_status(risk, risk28, drift, in_flare)
    fl = data.recorded_flares(pid)
    past = fl[fl["start_date"] <= today]
    flare_days = past.loc[past["event_type"] == "flare_onset", "start_date"].tolist()
    marks = [(t, "flare") for t in flare_days] + [
        (t, "therapy ↑") for t in past.loc[past["event_type"].isin(["therapy_optimised", "therapy_escalated"]), "start_date"]]
    m14, m28 = load_model(14), load_model(28)

    # 1–2: card, gauge, trend
    c1, c2, c3 = st.columns([1.25, 1.15, 1.5])
    with c1:
        _card(p, row_d, len(flare_days))
    with c2:
        st.markdown(f"<div style='text-align:center;font-size:1.2rem;padding-top:0.6rem'>Twin status: {EMOJI[light]} "
                    f"<b>{STATUS[light]}</b>"
                    f"{'<br><span style=font-size:0.9rem>⌚ watch drift (7+ of 14 days)</span>' if drift else ''}</div>",
                    unsafe_allow_html=True)
        g1, g2 = st.columns(2)
        g1.plotly_chart(charts.gauge(risk, traffic_light(risk), "14-day risk", 170), key="gauge14")
        g2.plotly_chart(charts.gauge(risk28, traffic_light(risk28), "28-day outlook", 170), key="gauge28")
    with c3:
        st.plotly_chart(charts.risk_trend(d, today, marks), key="trend")

    # 7–8: suggested action + alerts
    c1, c2 = st.columns([1, 1.4])
    with c1:
        st.markdown("##### ✅ Suggested action")
        act = suggested_action(risk, frow.get("l_fc_days_since"), frow.get("l_fc_two_consec_high", 0) > 0, risk28, drift,
                               in_flare)
        em_now = A[(A["patient_id"] == pid) & (A["kind"] == "emergency") & (A["date"] <= today) &
                   (A["date"] > today - pd.Timedelta(days=2))]
        if len(em_now):
            r = em_now.iloc[-1]
            st.error(f"**🚨 {r['title']}** — {r['detail']}.  \n**{r['action']}.**")
        (st.error if light == "red" else st.warning if light == "amber" else st.info if light == "flare" else st.success)(act)
        cold = frow.get("e_ctx_cold_7d", 0) > 0 or frow.get("e_ctx_gut_infection_28d", 0) > 0
        if light in ("amber", "red"):
            st.caption("Decoy check: " + ("⚠️ a cold / infection is logged — some watch changes may be explained by it."
                                          if cold else "no cold, fever or infection logged — drift is not explained by a decoy."))
    with c2:
        st.markdown("##### 🔔 Alerts feed (last 60 days)")
        al = A[(A["patient_id"] == pid) & (A["date"] <= today) & (A["date"] > today - pd.Timedelta(days=60))]
        al = al.sort_values("date", ascending=False).drop_duplicates(["rule", "date"])
        al = al[~((al["kind"] == "emergency") & al.duplicated("rule", keep="first"))]
        if al.empty:
            st.caption("No alerts in the last 60 days.")
        for r in al.head(8).itertuples():
            icon = "🚨" if r.kind == "emergency" else EMOJI[r.tier]
            st.markdown(f"{icon} **{r.date:%d %b}** · {r.title} — {r.detail} · _{r.action}_")

    # 5–6: why + what-if
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### 🧠 Why is the risk at this level?")
        default = 1 if traffic_light(risk28) != "green" and risk28 > risk else 0
        which = st.radio("Explain", ["14-day risk", "28-day outlook"], index=default, horizontal=True,
                         key=f"explain_{pid}_{today:%Y%m%d}", label_visibility="collapsed")
        mod = m28 if which == "28-day outlook" else m14
        for e in explain_row(mod, frow, pid, p["ibd_type"]):
            arrow = "🔺" if e["direction"] == "raises risk" else "🔻"
            st.markdown(f"{arrow} {e['sentence']} — *{e['direction']}*")
        st.caption("Top 5 drivers by SHAP value (LightGBM TreeSHAP), grouped by signal. Associations, not causes.")
    with c2:
        st.markdown("##### 🧪 What-if simulator")
        names = {"adherence_100": "Adherence → 100%", "switch_anti_tnf": "Switch to anti-TNF",
                 "stop_nsaids": "Stop NSAIDs", "optimise_therapy": "Optimise therapy (all three)"}
        rows = []
        for k, ch in PRESETS.items():
            a, b = whatif(m14, frow, pid, **ch), whatif(m28, frow, pid, **ch)
            rows.append({"Scenario": names[k], "14-day": f"{100 * a['projected_risk']:.0f}% ({100 * a['change']:+.1f})",
                         "28-day": f"{100 * b['projected_risk']:.0f}% ({100 * b['change']:+.1f})"})
        st.markdown(f"Now: **{100 * risk:.0f}%** (14-day) · **{100 * risk28:.0f}%** (28-day)")
        st.dataframe(pd.DataFrame(rows), hide_index=True)
        with st.expander("Custom scenario", expanded=False):
            adh = st.slider("Medication adherence", 0.0, 1.0, float(p["medication_adherence"]), 0.05, key=f"adh_{pid}")
            med = st.selectbox("Medication", MEDS, index=MEDS.index(p["current_medication"]), key=f"med_{pid}")
            nsaid = st.checkbox("Stop NSAIDs", key=f"nsaid_{pid}")
            cc = st.columns(2)
            for col, mod, lab in [(cc[0], m14, "14-day"), (cc[1], m28, "28-day")]:
                r = whatif(mod, frow, pid, adherence=adh, medication=med, stop_nsaids=nsaid)
                col.metric(f"Projected {lab} risk", f"{100 * r['projected_risk']:.0f}%", f"{100 * r['change']:+.1f} pts",
                           delta_color="inverse")
        st.caption(WHATIF_LABEL + ". Small changes are expected: the model sees therapy only as a static EHR field, "
                   "so it cannot learn a treatment effect from this data.")

    # 3: signals
    st.markdown("##### 📈 Signals vs personal baseline")
    tabs = st.tabs(["Daily trends (120 days)", "Intraday (demo patients)"])
    with tabs[0]:
        st.plotly_chart(charts.signal_panel(feat, today, flare_days), key="signals")
    with tabs[1]:
        h = data.hourly_for(pid)
        if h.empty:
            st.caption("Hourly stream is only simulated for the 17 demo patients.")
        else:
            st.plotly_chart(charts.intraday(h, today), key="intraday")

    # 4: labs
    st.markdown("##### 🧫 Labs timeline")
    labs = data.labs_for(pid)
    st.plotly_chart(charts.labs_panel(labs, today, p["age"]), key="labs")
    last = labs[labs["date"] <= today].sort_values("date").groupby("test").tail(1)
    last = last[last["test"].isin(["faecal_calprotectin", "crp", "haemoglobin", "ferritin", "albumin"])]
    st.caption(" · ".join(f"{t.test.replace('_', ' ')} {t.value:g} {t.unit} ({t.date:%d %b})" for t in last.itertuples()))

    # 9: cancer safety
    st.markdown("##### 🛡️ Cancer Safety — surveillance support, not cancer detection")
    cs = cancer_safety(p, row_d, today, risk=risk)
    c1, c2, c3 = st.columns([1, 1.3, 1.2])
    lv = {"low": "🟢 Low", "medium": "🟠 Medium", "high": "🔴 High"}[cs.risk_level]
    c1.metric("CRC risk level", lv)
    if cs.surveillance_applies:
        due = (f"Overdue by {-cs.months_to_due:.0f} months" if cs.overdue else f"Due in {cs.months_to_due:.0f} months")
        c1.markdown(f"**Next colonoscopy:** {cs.next_due:%b %Y} — {'🔴 ' if cs.overdue else ''}{due}  \n"
                    f"Interval {cs.interval_years} yr · last {cs.last_colonoscopy:%b %Y}")
    else:
        c1.markdown("Surveillance not yet due.")
    c2.markdown("**Why this level**  \n" + "  \n".join(f"• {x}" for x in cs.reasons))
    c3.markdown("**Red flags**  \n" + ("  \n".join(f"⚠️ {x}" for x in cs.red_flags) if cs.red_flags else "None"))
    if cs.screening:
        st.markdown("**Other screening tracker:** " + " · ".join(
            f"{'🔴' if s['overdue'] else '✅'} {s['item']}: {s['status']}" for s in cs.screening))

    # 10: sweat
    sw = data.sweat_for(pid)
    with st.expander("💧 Continuous inflammation: investigational, simulated data", expanded=False):
        if sw.empty:
            st.caption("This patient has no sweat sensor (most patients won't). The model works without it.")
        else:
            st.plotly_chart(charts.sweat_panel(sw, today), key="sweat")
            st.caption("Simulates an investigational sweat-biomarker wearable. No such device is FDA- or "
                       "CDSCO-approved for IBD monitoring. Used only in ablation C, not in the main model.")


def model_view():
    m = data.metrics()
    mm, bb = m["main"], m["baseline"]
    st.subheader("Model results — held-out patients (5-fold, grouped by patient)")
    k = st.columns(6)
    k[0].metric("PR-AUC", f"{mm['pr_auc']:.3f}", f"{mm['pr_auc'] - bb['pr_auc']:+.3f} vs logistic")
    k[1].metric("AUROC", f"{mm['auroc']:.3f}")
    k[2].metric("Flares caught", f"{100 * mm['event_sensitivity']:.0f}%")
    k[3].metric("Median warning", f"{mm['median_episode_lead_days']:.0f} days")
    k[4].metric("False alarms / pt-month", f"{mm['false_alarms_per_patient_month']:.3f}")
    k[5].metric("Brier score", f"{mm['brier']:.4f}")
    try:
        o = data.outlook_metrics()
        st.markdown(f"**Secondary 28-day outlook** (same inputs, folds and method): PR-AUC {o['pr_auc']:.3f} · "
                    f"AUROC {o['auroc']:.3f} · flares caught {100 * o['event_sensitivity']:.0f}% · median warning "
                    f"{o['median_episode_lead_days']:.0f} days · {o['false_alarms_per_patient_month']:.3f} false alarms / pt-month")
    except FileNotFoundError:
        pass
    st.markdown("##### Ablation — value of each data stream (14-day target)")
    st.dataframe(data.ablation(), hide_index=True)
    c = st.columns(3)
    for col, f, cap in zip(c, ["pr_curve.png", "calibration.png", "feature_importance.png"],
                           ["Precision–recall", "Calibration", "Top features"]):
        if (data.ART / f).exists():
            col.image(str(data.ART / f), caption=cap)
    st.caption(f"Target: {m['target']}. Alert threshold chosen per fold on validation patients (max F1). "
               "Lead time = days from the start of the alert episode to flare onset. Synthetic data: correlations "
               "exist because the generator puts them there.")


if ss.view == "Population":
    population_view()
elif ss.view == "Model results":
    model_view()
else:
    patient_view(ss.pid)
