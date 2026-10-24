"""WS2: train the 14-day flare model with a patient-grouped 5-fold split.

    python -m src.models.train            # or: make train

For every outer fold: the training patients are split again (80/20, by patient) into
fit / validation sets. The validation set is used for LightGBM early stopping, Platt
calibration and the alert threshold (max F1). The held-out fold is only scored.
Each patient is therefore scored by a model that never saw them; the dashboard shows
these out-of-fold risks.

Outputs (artifacts/): metrics.json, metrics_baseline.json, ablation.csv, oof_scores.parquet,
folds.json, model_fold{k}.txt + calibration.json (main model D), plots,
and the secondary 28-day outlook (model_outlook_fold{k}.txt, metrics_outlook.json).
"""
import json
import time
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupShuffleSplit, StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src.features.fusion import OUT_DIR as FEATURE_DIR, feature_columns, training_mask

from .evaluate import assert_beats_baseline, best_f1_threshold, classification_metrics, event_metrics

ART = Path(__file__).resolve().parents[2] / "artifacts"
SEED = 42
N_FOLDS = 5
MAIN = "D"
ABLATION = {   # name -> (feature groups, description). A/B/C follow Build Guide §7 WS2 step 6.
    "A": (("w", "e"), "Wearables + EHR"),
    "B": (("w", "e", "l"), "A + labs (calprotectin, CRP, Hb...)"),
    "C": (("w", "e", "l", "x"), "B + sweat sensor (investigational)"),
    "D": (("w", "s", "e", "l"), "B + symptom check-ins (main model)"),
    "E": (("w", "s", "e", "l", "x"), "D + sweat sensor (investigational)"),
}
ALL_CONFIGS = tuple(ABLATION)
OUTLOOK_DAYS = 28
LGB_PARAMS = dict(objective="binary", learning_rate=0.03, num_leaves=31, min_child_samples=200,
                  feature_fraction=0.5, bagging_fraction=0.8, bagging_freq=1, lambda_l2=5.0,
                  max_bin=63, verbose=-1, seed=SEED, num_threads=0)


class Platt:
    """Sigmoid calibration on the logit of the raw score (fit on the validation patients)."""

    def fit(self, p, y):
        z = np.log(np.clip(p, 1e-6, 1 - 1e-6) / np.clip(1 - p, 1e-6, None)).reshape(-1, 1)
        lr = LogisticRegression(C=1e4).fit(z, y)
        self.a, self.b = float(lr.coef_[0, 0]), float(lr.intercept_[0])
        return self

    def __call__(self, p):
        z = np.log(np.clip(p, 1e-6, 1 - 1e-6) / np.clip(1 - p, 1e-6, None))
        return 1 / (1 + np.exp(-(self.a * z + self.b)))

    def to_dict(self):
        return {"a": self.a, "b": self.b}

    @classmethod
    def from_dict(cls, d):
        c = cls()
        c.a, c.b = d["a"], d["b"]
        return c


def make_folds(labels):
    """Patient → fold, stratified by whether the patient has any flare onset."""
    pat = labels.groupby("patient_id")["flare_onset"].max().fillna(0).astype(int)
    sgkf = StratifiedGroupKFold(n_splits=N_FOLDS, shuffle=True, random_state=SEED)
    fold = {}
    for k, (_, te) in enumerate(sgkf.split(pat.index, pat.values, groups=pat.index)):
        for p in pat.index[te]:
            fold[p] = k
    return fold


def _inner_split(pids):
    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEED)
    fit_idx, val_idx = next(gss.split(pids, groups=pids))
    return set(pids[fit_idx]), set(pids[val_idx])


def fit_lgbm(Xf, yf, Xv, yv):
    spw = float(np.sqrt((yf == 0).sum() / max((yf == 1).sum(), 1)))   # class weight on positives
    dtr = lgb.Dataset(Xf, yf, free_raw_data=False)
    dva = lgb.Dataset(Xv, yv, reference=dtr)
    booster = lgb.train({**LGB_PARAMS, "scale_pos_weight": spw, "metric": "average_precision"}, dtr,
                        num_boost_round=1500, valid_sets=[dva],
                        callbacks=[lgb.early_stopping(100, verbose=False)])
    return booster


def fit_logistic(Xf, yf):
    return make_pipeline(SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True),
                         StandardScaler(),
                         LogisticRegression(C=0.05, class_weight="balanced", max_iter=500)).fit(Xf, yf)


def run_config(name, X_all, feats, labels, train_mask, fold, model="lgbm", save_models=False, prefix="model"):
    groups, desc = ABLATION[name]
    cols = feature_columns(feats, groups)
    X = X_all[cols].to_numpy(np.float32)
    y = labels["flare_within_14d"].fillna(0).to_numpy(int)
    pid = feats["patient_id"].to_numpy()
    fold_of_row = pd.Series(pid).map(fold).to_numpy()
    risk = np.full(len(feats), np.nan)
    thr_row = np.full(len(feats), np.nan)
    fold_info = []
    for k in range(N_FOLDS):
        t0 = time.time()
        tr_p = np.array(sorted({p for p, f in fold.items() if f != k}))
        fit_p, val_p = _inner_split(tr_p)
        fit_m = train_mask & np.isin(pid, list(fit_p))
        val_m = train_mask & np.isin(pid, list(val_p))
        if model == "lgbm":
            m = fit_lgbm(X[fit_m], y[fit_m], X[val_m], y[val_m])
            raw = lambda A: m.predict(A, num_iteration=m.best_iteration)
        else:
            m = fit_logistic(X[fit_m], y[fit_m])
            raw = lambda A: m.predict_proba(A)[:, 1]
        cal = Platt().fit(raw(X[val_m]), y[val_m])
        thr = best_f1_threshold(y[val_m], cal(raw(X[val_m])))
        te = fold_of_row == k
        risk[te] = cal(raw(X[te]))
        thr_row[te] = thr
        info = {"fold": k, "threshold": thr, "calibration": cal.to_dict(),
                "n_fit_patients": len(fit_p), "n_val_patients": len(val_p)}
        if model == "lgbm":
            info["best_iteration"] = int(m.best_iteration)
        fold_info.append(info)
        if save_models:
            if model == "lgbm":
                m.save_model(str(ART / f"{prefix}_fold{k}.txt"), num_iteration=m.best_iteration)
            else:
                joblib.dump(m, ART / f"baseline_fold{k}.joblib")
        print(f"  [{name}/{model}] fold {k}: thr={thr:.3f} ({time.time() - t0:.0f}s)", flush=True)

    ev = train_mask   # evaluation rows: label known, not in flare, held-out patient
    alert = risk >= thr_row
    cls = classification_metrics(y[ev], risk[ev], alert[ev])
    scored = labels.assign(alert=alert)
    evt = event_metrics(scored)
    amber = event_metrics(labels.assign(alert=risk >= 0.20))
    metrics = {"config": name, "inputs": desc, "model": model, "n_features": len(cols), **cls, **evt,
               "amber_20pct": {k: amber[k] for k in ("event_sensitivity", "median_lead_time_days",
                                                     "false_alarms_per_patient_month")},
               "folds": fold_info}
    return metrics, risk, thr_row, cols


def _plots(y, p_main, p_base, metrics, booster_cols):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from sklearn.calibration import calibration_curve
    from sklearn.metrics import precision_recall_curve

    fig, ax = plt.subplots(figsize=(5.5, 4.5))
    for p, lab in [(p_main, f"LightGBM (PR-AUC {metrics['main']['pr_auc']:.3f})"),
                   (p_base, f"Logistic baseline (PR-AUC {metrics['baseline']['pr_auc']:.3f})")]:
        pr, rc, _ = precision_recall_curve(y, p)
        ax.plot(rc, pr, label=lab)
    ax.axhline(y.mean(), ls="--", c="grey", lw=1, label=f"Prevalence {y.mean():.3f}")
    ax.set(xlabel="Recall", ylabel="Precision", title="14-day flare: held-out patients")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(ART / "pr_curve.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(5, 4.5))
    for p, lab in [(p_main, "LightGBM"), (p_base, "Logistic")]:
        fp, mp = calibration_curve(y, p, n_bins=12, strategy="quantile")
        ax.plot(mp, fp, marker="o", ms=3, label=lab)
    ax.plot([0, 1], [0, 1], ls="--", c="grey", lw=1)
    lim = max(0.3, float(np.nanmax(p_main)) * 0.6)
    ax.set(xlim=(0, lim), ylim=(0, lim), xlabel="Predicted risk", ylabel="Observed flare rate",
           title="Calibration (reliability)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(ART / "calibration.png", dpi=150)
    plt.close(fig)

    gains = np.zeros(len(booster_cols))
    for k in range(N_FOLDS):
        b = lgb.Booster(model_file=str(ART / f"model_fold{k}.txt"))
        gains += b.feature_importance("gain")
    imp = pd.Series(gains / gains.sum(), index=booster_cols).sort_values().tail(20)
    fig, ax = plt.subplots(figsize=(6, 5.5))
    imp.plot.barh(ax=ax, color="#3b6ea5")
    ax.set(xlabel="Share of total gain", title="Top 20 features (LightGBM, main model D)")
    fig.tight_layout()
    fig.savefig(ART / "feature_importance.png", dpi=150)
    plt.close(fig)
    imp.sort_values(ascending=False).to_csv(ART / "feature_importance.csv", header=["gain_share"])


def main(configs=ALL_CONFIGS):
    ART.mkdir(exist_ok=True)
    t0 = time.time()
    feats = pd.read_parquet(FEATURE_DIR / "features.parquet")
    labels = pd.read_parquet(FEATURE_DIR / "labels.parquet")
    assert (feats["patient_id"].to_numpy() == labels["patient_id"].to_numpy()).all()
    train_mask = training_mask(labels).to_numpy()
    fold = make_folds(labels)
    (ART / "folds.json").write_text(json.dumps(fold, indent=0))
    y = labels["flare_within_14d"].fillna(0).to_numpy(int)
    print(f"{len(feats):,} patient-days, {train_mask.sum():,} training rows, "
          f"{y[train_mask].mean():.2%} positive", flush=True)

    print("Baseline: logistic regression (main-model inputs)", flush=True)
    base, p_base, _, _ = run_config(MAIN, feats, feats, labels, train_mask, fold, model="logistic", save_models=True)
    (ART / "metrics_baseline.json").write_text(json.dumps(base, indent=2))

    results, main_out = {}, None
    for name in configs:
        print(f"LightGBM config {name}: {ABLATION[name][1]}", flush=True)
        m, risk, thr, cols = run_config(name, feats, feats, labels, train_mask, fold, save_models=(name == MAIN))
        results[name] = m
        if name == MAIN:
            main_out = (m, risk, thr, cols)

    m, risk, thr, cols = main_out
    assert_beats_baseline(m, base)
    metrics = {"target": "flare_within_14d (onset in days t+1..t+14)", "split": f"{N_FOLDS}-fold grouped by patient",
               "main_config": MAIN, "main": m, "baseline": base,
               "ablation": {k: {c: v[c] for c in ("inputs", "pr_auc", "auroc", "event_sensitivity",
                                                  "median_lead_time_days", "median_episode_lead_days", "false_alarms_per_patient_month")}
                            for k, v in results.items()},
               "runtime_s": round(time.time() - t0)}
    (ART / "metrics.json").write_text(json.dumps(metrics, indent=2))
    (ART / "feature_list.json").write_text(json.dumps(cols))
    (ART / "calibration.json").write_text(json.dumps(
        {"thresholds": [f["threshold"] for f in m["folds"]], "platt": [f["calibration"] for f in m["folds"]]}, indent=2))

    rows = []
    for k, v in [("Logistic (D inputs)", base)] + [(f"LightGBM {n}", results[n]) for n in configs]:
        rows.append({"model": k, "inputs": v["inputs"], "n_features": v["n_features"],
                     "pr_auc": round(v["pr_auc"], 3), "auroc": round(v["auroc"], 3), "brier": round(v["brier"], 4),
                     "f1": round(v["f1"], 3), "sensitivity": round(v["sensitivity"], 3),
                     "specificity": round(v["specificity"], 3), "event_sensitivity": round(v["event_sensitivity"], 3),
                     "median_lead_days": v["median_lead_time_days"], "median_episode_lead_days": v["median_episode_lead_days"],
                     "false_alarms_per_pt_month": round(v["false_alarms_per_patient_month"], 3)})
    pd.DataFrame(rows).to_csv(ART / "ablation.csv", index=False)

    oof = feats[["patient_id", "date"]].assign(risk=risk.astype(np.float32), threshold=thr.astype(np.float32),
                                               risk_baseline=p_base.astype(np.float32),
                                               fold=feats["patient_id"].map(fold).astype(int))
    oof.to_parquet(ART / "oof_scores.parquet", index=False)
    _plots(y[train_mask], risk[train_mask], p_base[train_mask], metrics, cols)
    print(pd.DataFrame(rows).to_string(index=False))
    train_outlook(feats, labels, fold)
    print(f"done in {time.time() - t0:.0f}s → {ART}")


def horizon_labels(labels, horizon):
    """flare_within_{horizon}d from the flare-onset ground truth (NaN where the window passes the record end)."""
    pids = labels["patient_id"].unique()
    on = labels["flare_onset"].fillna(0).to_numpy().reshape(len(pids), -1)
    D = on.shape[1]
    c = np.concatenate([np.zeros((len(pids), 1)), np.cumsum(on, axis=1)], axis=1)
    t = np.arange(D)
    hit = (c[:, np.minimum(t + horizon + 1, D)] - c[:, np.minimum(t + 1, D)]) > 0
    lab = np.where(hit, 1.0, np.where((t + horizon >= D)[None, :], np.nan, 0.0)).ravel()
    return labels.assign(flare_within_14d=lab)   # column name kept so the shared code path is reused


def train_outlook(feats=None, labels=None, fold=None, horizon=OUTLOOK_DAYS):
    """Secondary 28-day outlook: same inputs, folds and method as the main model, longer horizon.
    Shown next to the 14-day risk on the dashboard; the 14-day model remains the evaluated target."""
    feats = feats if feats is not None else pd.read_parquet(FEATURE_DIR / "features.parquet")
    labels = labels if labels is not None else pd.read_parquet(FEATURE_DIR / "labels.parquet")
    fold = fold or {k: int(v) for k, v in json.loads((ART / "folds.json").read_text()).items()}
    L = horizon_labels(labels, horizon)
    mask = training_mask(L).to_numpy()
    print(f"Outlook model: flare within {horizon} days ({L.loc[mask, 'flare_within_14d'].mean():.2%} positive)", flush=True)
    m, risk, thr, _ = run_config(MAIN, feats, feats, L, mask, fold, save_models=True, prefix="model_outlook")
    m["target"] = f"flare_within_{horizon}d"
    (ART / "metrics_outlook.json").write_text(json.dumps(m, indent=2))
    (ART / "calibration_outlook.json").write_text(json.dumps(
        {"thresholds": [f["threshold"] for f in m["folds"]], "platt": [f["calibration"] for f in m["folds"]],
         "horizon_days": horizon}, indent=2))
    oof = pd.read_parquet(ART / "oof_scores.parquet")
    oof["risk28"] = risk.astype(np.float32)
    oof.to_parquet(ART / "oof_scores.parquet", index=False)
    print(f"  outlook PR-AUC {m['pr_auc']:.3f}, flares caught {m['event_sensitivity']:.1%}, "
          f"median warning {m['median_episode_lead_days']} d")


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["outlook"]:
        train_outlook()
    else:
        main(tuple(sys.argv[1:]) or ALL_CONFIGS)
