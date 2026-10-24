"""Metrics for the 14-day flare model (Build Guide §7 WS2 step 5)."""
import numpy as np
import pandas as pd
from sklearn.metrics import (average_precision_score, brier_score_loss, f1_score, precision_recall_curve,
                             roc_auc_score)

DAYS_PER_MONTH = 30.44


def best_f1_threshold(y, p):
    prec, rec, thr = precision_recall_curve(y, p)
    f1 = 2 * prec * rec / np.clip(prec + rec, 1e-12, None)
    i = int(np.nanargmax(f1[:-1]))
    return float(thr[i])


def classification_metrics(y, p, alert):
    y, p, alert = np.asarray(y, int), np.asarray(p, float), np.asarray(alert, bool)
    tp, fp = int((alert & (y == 1)).sum()), int((alert & (y == 0)).sum())
    fn, tn = int((~alert & (y == 1)).sum()), int((~alert & (y == 0)).sum())
    return {
        "auroc": float(roc_auc_score(y, p)),
        "pr_auc": float(average_precision_score(y, p)),
        "brier": float(brier_score_loss(y, p)),
        "f1": float(f1_score(y, alert)),
        "sensitivity": tp / max(tp + fn, 1),
        "specificity": tn / max(tn + fp, 1),
        "precision": tp / max(tp + fp, 1),
        "positive_rate": float(y.mean()),
        "n_rows": int(len(y)),
    }


def _runs(flag):
    d = np.diff(np.concatenate([[0], flag.astype(int), [0]]))
    return list(zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)))


def event_metrics(scored, alert_col="alert", horizon=14):
    """Per-onset lead time and per-patient-month false alarms.

    scored: one row per patient-day with columns patient_id, date, flare_onset, in_flare,
            flare_within_14d (NaN at record end), and the boolean alert column.
    - An onset is *detected* if an alert fires on any of the `horizon` days before it;
      lead time = onset day − first alert day in that window.
    - A *false alarm* is an alert episode (run of consecutive alert days outside flares)
      that starts on a day whose label is 0, i.e. no onset follows within `horizon` days.
    """
    leads, run_leads, missed, false_alarms, monitored_days = [], [], 0, 0, 0
    for _, g in scored.sort_values(["patient_id", "date"]).groupby("patient_id", sort=False):
        alert = g[alert_col].to_numpy(bool)
        onset = g["flare_onset"].to_numpy() == 1
        in_flare = g["in_flare"].to_numpy(bool)
        label = g["flare_within_14d"].to_numpy()
        for t in np.flatnonzero(onset):
            w = alert[max(0, t - horizon):t]
            if w.any():
                first = t - (len(w) - int(np.argmax(w)))
                leads.append(t - first)
                # walk back through the same alert episode (gaps of ≤ 2 days bridged), capped at 56 days
                s, gap = first, 0
                while s - 1 >= max(0, t - 56) and gap <= 2 and not in_flare[s - 1]:
                    s -= 1
                    gap = 0 if alert[s] else gap + 1
                run_leads.append(t - (s + gap))
            else:
                missed += 1
        usable = ~in_flare & ~np.isnan(label)
        monitored_days += int(usable.sum())
        for a, _b in _runs(alert & ~in_flare):
            if usable[a] and label[a] == 0:
                false_alarms += 1
    n_on = len(leads) + missed
    return {
        "onsets": n_on,
        "onsets_detected": len(leads),
        "event_sensitivity": len(leads) / max(n_on, 1),
        "median_lead_time_days": float(np.median(leads)) if leads else None,
        "mean_lead_time_days": float(np.mean(leads)) if leads else None,
        # how long before onset the alert episode that caught the flare actually began (not capped at 14 d)
        "median_episode_lead_days": float(np.median(run_leads)) if run_leads else None,
        "false_alarms": false_alarms,
        "patient_months": monitored_days / DAYS_PER_MONTH,
        "false_alarms_per_patient_month": false_alarms / max(monitored_days / DAYS_PER_MONTH, 1e-9),
    }


def assert_beats_baseline(main, baseline):
    """Gate 2: LightGBM must beat logistic regression on PR-AUC on held-out patients."""
    assert main["pr_auc"] > baseline["pr_auc"], (
        f"LightGBM PR-AUC {main['pr_auc']:.3f} does not beat baseline {baseline['pr_auc']:.3f}")
    if main["pr_auc"] > 0.95:
        raise AssertionError(f"PR-AUC {main['pr_auc']:.3f} > 0.95: treat as a leakage bug (Build Guide §8)")
