"""Personal baselines: robust median / MAD over each patient's own quiet days.

All arrays are pandas DataFrames shaped (days × patients), so every rolling
operation runs down the time axis and only ever looks backwards.
"""
import numpy as np
import pandas as pd

BASELINE_WINDOW = 180   # days of history the baseline looks back over
BASELINE_MIN_OBS = 14   # quiet observations needed before a baseline exists


def personal_baseline(x: pd.DataFrame, quiet: pd.DataFrame, window=BASELINE_WINDOW, min_obs=BASELINE_MIN_OBS,
                      scale_floor=1e-6):
    """Median and MAD-based scale from quiet days strictly before day t.

    Returns (median, scale) DataFrames aligned with x. scale = 1.4826 × MAD (≈ SD for normal data).
    """
    xq = x.where(quiet)
    med = xq.rolling(window, min_periods=min_obs).median()
    mad = (xq - med).abs().rolling(window, min_periods=min_obs).median()
    # shift(1): the baseline used on day t is built from days < t only.
    med = med.shift(1).ffill()
    scale = (1.4826 * mad).shift(1).ffill().clip(lower=scale_floor)
    return med, scale


def zscore(x, med, scale, clip=8.0):
    return ((x - med) / scale).clip(-clip, clip)


def observable_quiet(context_any, symptom_norm_7d, fc_last):
    """Quiet day = nothing observable is going on: no context event in the last 7 days,
    symptoms well below the flare threshold, and the last calprotectin below 250."""
    quiet = ~context_any
    quiet &= ~(symptom_norm_7d >= 0.5)         # NaN (no check-ins) counts as quiet
    quiet &= ~(fc_last > 250)
    return quiet
