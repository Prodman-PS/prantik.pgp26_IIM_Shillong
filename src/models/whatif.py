"""WS3: what-if simulator — re-score today's row with changed modifiable inputs.

Output is model-estimated association, not a causal effect of treatment.
"""
import pandas as pd

MEDS = ["none", "5-ASA", "thiopurine", "anti-TNF", "vedolizumab", "steroid"]
LABEL = "Model-estimated (re-scored with changed inputs; not a causal treatment effect)"

PRESETS = {
    "adherence_100": {"adherence": 1.0},
    "switch_anti_tnf": {"medication": "anti-TNF"},
    "stop_nsaids": {"stop_nsaids": True},
    "optimise_therapy": {"adherence": 1.0, "medication": "anti-TNF", "stop_nsaids": True},
}


def apply_changes(row: pd.Series, adherence=None, medication=None, stop_nsaids=False):
    r = row.copy()
    if adherence is not None:
        r["e_medication_adherence"] = float(adherence)
    if medication is not None:
        if medication not in MEDS:
            raise ValueError(f"medication must be one of {MEDS}")
        for m in MEDS:
            r[f"e_current_medication={m}"] = 1.0 if m == medication else 0.0
    if stop_nsaids:
        for c in ("e_nsaid_use", "e_ctx_nsaid_active", "e_ctx_nsaid_14d"):
            r[c] = 0.0
    return r


def whatif(model, row: pd.Series, patient_id, **changes):
    base = float(model.predict(row.to_frame().T, patient_id=patient_id)[0])
    new = float(model.predict(apply_changes(row, **changes).to_frame().T, patient_id=patient_id)[0])
    return {"current_risk": base, "projected_risk": new, "change": new - base, "changes": changes, "label": LABEL}


def all_presets(model, row, patient_id):
    return {k: whatif(model, row, patient_id, **v) for k, v in PRESETS.items()}
