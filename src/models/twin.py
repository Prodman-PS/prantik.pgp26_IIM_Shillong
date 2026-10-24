"""Load the trained twin model and score / explain patient-days.

Each patient is scored by the fold model that held them out in cross-validation,
so dashboard risks and explanations are always out-of-sample.
"""
import json
from functools import lru_cache
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

ART = Path(__file__).resolve().parents[2] / "artifacts"


class TwinModel:
    def __init__(self, art_dir=ART, horizon=14):
        """horizon=14: the main 14-day model. horizon=28: the secondary 28-day outlook."""
        art_dir = Path(art_dir)
        prefix, calib = ("model", "calibration.json") if horizon == 14 else ("model_outlook", "calibration_outlook.json")
        self.horizon = horizon
        self.features = json.loads((art_dir / "feature_list.json").read_text())
        self.fold = json.loads((art_dir / "folds.json").read_text())
        cal = json.loads((art_dir / calib).read_text())
        self.thresholds = cal["thresholds"]
        self.platt = cal["platt"]
        self.boosters = [lgb.Booster(model_file=str(art_dir / f"{prefix}_fold{k}.txt")) for k in range(len(self.platt))]

    def _fold(self, pid):
        return int(self.fold.get(pid, 0))

    def _cal(self, k, p):
        a, b = self.platt[k]["a"], self.platt[k]["b"]
        z = np.log(np.clip(p, 1e-6, 1 - 1e-6) / np.clip(1 - p, 1e-6, None))
        return 1 / (1 + np.exp(-(a * z + b)))

    def matrix(self, rows: pd.DataFrame):
        return rows.reindex(columns=self.features).to_numpy(np.float32)

    def predict(self, rows: pd.DataFrame, patient_id=None):
        """Calibrated 14-day flare risk for rows (all from one patient, or with a patient_id column)."""
        pids = rows["patient_id"].to_numpy() if patient_id is None else np.full(len(rows), patient_id)
        X = self.matrix(rows)
        out = np.empty(len(rows))
        for k in np.unique([self._fold(p) for p in pids]):
            m = np.array([self._fold(p) == k for p in pids])
            out[m] = self._cal(k, self.boosters[k].predict(X[m]))
        return out

    def contributions(self, row: pd.Series, patient_id):
        """TreeSHAP contributions (log-odds of the raw model) for a single row; last entry is the bias."""
        k = self._fold(patient_id)
        X = self.matrix(row.to_frame().T)
        c = self.boosters[k].predict(X, pred_contrib=True)[0]
        return pd.Series(c[:-1], index=self.features), float(c[-1])

    def threshold(self, patient_id):
        return float(self.thresholds[self._fold(patient_id)])


@lru_cache(maxsize=2)
def load_model(horizon=14, art_dir=str(ART)):
    return TwinModel(art_dir, horizon)
