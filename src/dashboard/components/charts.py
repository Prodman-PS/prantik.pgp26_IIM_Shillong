"""Plotly figures for the patient view."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

GREEN, AMBER, RED, GREY = "#2e8b57", "#e69f00", "#d64545", "#8a8f98"
BLUE, BAND = "#3b6ea5", "rgba(59,110,165,0.15)"
LIGHT = {"green": GREEN, "amber": AMBER, "red": RED, "grey": GREY, "flare": "#7b5ea7"}


def _layout(fig, h=260, **kw):
    kw = {"hovermode": "x unified", "legend": dict(orientation="h", y=-0.2), **kw}
    fig.update_layout(height=h, margin=dict(l=10, r=10, t=36, b=10), **kw)
    return fig


def gauge(risk, light, title="14-day flare risk", h=190):
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=100 * risk, number={"suffix": "%", "font": {"size": 24, "color": LIGHT[light]}, "valueformat": ".0f"},
        gauge={"axis": {"range": [0, 100], "tickvals": [0, 20, 50, 100], "tickfont": {"size": 10}},
               "bar": {"color": LIGHT[light], "thickness": 0.3},
               "steps": [{"range": [0, 20], "color": "rgba(46,139,87,0.18)"},
                         {"range": [20, 50], "color": "rgba(230,159,0,0.2)"},
                         {"range": [50, 100], "color": "rgba(214,69,69,0.2)"}]},
        title={"text": title, "font": {"size": 13}}))
    fig.update_layout(height=h, margin=dict(l=18, r=18, t=46, b=0))
    return fig


def risk_trend(d, today, events=None, days=60):
    w = d[(d["date"] > today - pd.Timedelta(days=days)) & (d["date"] <= today)]
    fig = go.Figure()
    for y0, y1, c in [(0, 20, "rgba(46,139,87,0.10)"), (20, 50, "rgba(230,159,0,0.12)"), (50, 100, "rgba(214,69,69,0.10)")]:
        fig.add_hrect(y0=y0, y1=y1, fillcolor=c, line_width=0)
    fig.add_trace(go.Scatter(x=w["date"], y=100 * w["risk"], mode="lines", line=dict(color=BLUE, width=2.5),
                             name="14-day risk", hovertemplate="%{y:.0f}%"))
    if "risk28" in w:
        fig.add_trace(go.Scatter(x=w["date"], y=100 * w["risk28"], mode="lines", line=dict(color="#7b5ea7", width=2, dash="dot"),
                                 name="28-day outlook", hovertemplate="%{y:.0f}%"))
    for t, label in (events or []):
        if today - pd.Timedelta(days=days) < t <= today:
            fig.add_vline(x=t, line=dict(color=GREY, dash="dash", width=1))
            fig.add_annotation(x=t, y=95, text=label, showarrow=False, font=dict(size=10, color=GREY), xanchor="left")
    fig.update_yaxes(range=[0, 100], ticksuffix="%")
    fig = _layout(fig, 240, title=f"Risk over the last {days} days")
    fig.update_layout(legend=dict(orientation="h", y=1.12, x=1, xanchor="right"))
    return fig


def signal_panel(feat, today, flares, days=120):
    """HRV, resting HR, steps, SpO₂, sleep vs the personal baseline band (baseline ± 1 robust SD)."""
    specs = [("hrv", "HRV (RMSSD, ms)"), ("rhr", "Resting HR (bpm)"), ("steps", "Steps / day"),
             ("spo2", "SpO₂ (%)"), ("sleep", "Sleep (h)")]
    w = feat[(feat["date"] > today - pd.Timedelta(days=days)) & (feat["date"] <= today)]
    fig = make_subplots(rows=len(specs), cols=1, shared_xaxes=True, vertical_spacing=0.035,
                        subplot_titles=[s[1] for s in specs])
    for i, (k, _label) in enumerate(specs, start=1):
        raw, base, sc = w[f"d_{k}_raw"], w[f"d_{k}_base"], w[f"d_{k}_scale"]
        fig.add_trace(go.Scatter(x=w["date"], y=base + sc, line=dict(width=0), showlegend=False, hoverinfo="skip"), i, 1)
        fig.add_trace(go.Scatter(x=w["date"], y=base - sc, fill="tonexty", fillcolor=BAND, line=dict(width=0),
                                 name="Personal baseline ±1 SD", showlegend=(i == 1), hoverinfo="skip"), i, 1)
        fig.add_trace(go.Scatter(x=w["date"], y=base, line=dict(color=BLUE, width=1, dash="dot"), showlegend=False,
                                 name="baseline"), i, 1)
        fig.add_trace(go.Scatter(x=w["date"], y=raw, mode="lines+markers", marker=dict(size=3), line=dict(color="#1f2933", width=1.2),
                                 name="Measured", showlegend=(i == 1)), i, 1)
        fig.add_trace(go.Scatter(x=w["date"], y=raw.rolling(7, min_periods=2).mean(), line=dict(color=RED, width=2),
                                 name="7-day average", showlegend=(i == 1)), i, 1)
    for t in flares:
        if today - pd.Timedelta(days=days) < t <= today:
            fig.add_vline(x=t, line=dict(color=RED, dash="dash", width=1))
    fig.update_annotations(font_size=12)
    return _layout(fig, 820, title="Watch signals vs personal baseline (red dashed = recorded flare onset)")


def labs_panel(labs, today, age):
    labs = labs[labs["date"] <= today]
    fig = make_subplots(rows=1, cols=3, subplot_titles=["Faecal calprotectin (µg/g)", "CRP (mg/L)", "Haemoglobin (g/dL)"])
    for j, (test, color) in enumerate([("faecal_calprotectin", RED), ("crp", AMBER), ("haemoglobin", BLUE)], start=1):
        s = labs[labs["test"] == test].sort_values("date")
        fig.add_trace(go.Scatter(x=s["date"], y=s["value"], mode="lines+markers", line=dict(color=color),
                                 name=test, showlegend=False), 1, j)
    # age-adjusted calprotectin bands (CLAUDE.md §3.2): <50 normal (>4 y), 50–250 borderline, >250 active
    normal = 50 if age > 4 else 275 if age >= 1 else 350
    fig.add_hline(y=normal, line=dict(color=GREEN, dash="dot"), row=1, col=1, annotation_text=f"normal < {normal}",
                  annotation_position="top left", annotation_font_size=10)
    fig.add_hline(y=250, line=dict(color=RED, dash="dot"), row=1, col=1, annotation_text="active > 250",
                  annotation_position="top left", annotation_font_size=10)
    fig.add_hline(y=5, line=dict(color=AMBER, dash="dot"), row=1, col=2)
    fig.add_hline(y=12, line=dict(color=BLUE, dash="dot"), row=1, col=3)
    fig.update_annotations(font_size=12)
    return _layout(fig, 280, hovermode="closest")


def sweat_panel(sw, today, days=120):
    w = sw[(sw["date"] > today - pd.Timedelta(days=days)) & (sw["date"] <= today)]
    fig = go.Figure()
    for c, name in [("sweat_calprotectin_ng_ml", "Sweat calprotectin"), ("sweat_crp_ng_ml", "Sweat CRP"),
                    ("sweat_il6_pg_ml", "IL-6"), ("sweat_tnf_alpha_pg_ml", "TNF-α")]:
        s = w[c].rolling(7, min_periods=2).mean()
        fig.add_trace(go.Scatter(x=w["date"], y=s / s.iloc[: min(28, len(s))].median() if len(s) else s, name=name))
    fig.add_hline(y=1, line=dict(color=GREY, dash="dot"))
    fig.update_yaxes(title="× personal level (7-day avg)")
    return _layout(fig, 260, title="Sweat biomarkers (investigational, simulated)")


def intraday(h, today, hours=72):
    w = h[(h["timestamp"] > today + pd.Timedelta(days=1) - pd.Timedelta(hours=hours)) &
          (h["timestamp"] <= today + pd.Timedelta(days=1))]
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=w["timestamp"], y=w["heart_rate_bpm"], name="Heart rate", line=dict(color=RED)), secondary_y=False)
    fig.add_trace(go.Scatter(x=w["timestamp"], y=w["hrv_rmssd_ms"], name="HRV", line=dict(color=BLUE)), secondary_y=True)
    for _, g in w[w["asleep"].astype(bool)].groupby((~w["asleep"].astype(bool)).cumsum()):
        fig.add_vrect(x0=g["timestamp"].min(), x1=g["timestamp"].max(), fillcolor="rgba(90,90,160,0.10)", line_width=0)
    fig.update_yaxes(title_text="bpm", secondary_y=False)
    fig.update_yaxes(title_text="ms", secondary_y=True)
    return _layout(fig, 240, title=f"Last {hours} hours (shaded = asleep)")
