"""Causal rolling-window statistics on (days × patients) frames."""
import numpy as np
import pandas as pd

WINDOWS = (7, 14, 28)


def rolling_slope(x: pd.DataFrame, w: int, min_periods=None):
    """OLS slope per day over the trailing w days, ignoring missing values."""
    min_periods = min_periods or max(3, w // 3)
    t = pd.DataFrame(np.repeat(np.arange(len(x), dtype=float)[:, None], x.shape[1], axis=1),
                     index=x.index, columns=x.columns)
    valid = x.notna()
    tv, xv = t.where(valid), x.where(valid)
    r = lambda a: a.rolling(w, min_periods=1).sum()
    n = valid.astype(float).rolling(w, min_periods=1).sum()
    st, sx, stt, stx = r(tv.fillna(0)), r(xv.fillna(0)), r((tv ** 2).fillna(0)), r((tv * xv).fillna(0))
    den = n * stt - st ** 2
    slope = (n * stx - st * sx) / den.replace(0, np.nan)
    return slope.where(n >= min_periods)


def window_stats(x: pd.DataFrame, name: str, windows=WINDOWS, stats=("mean", "std", "min", "max", "slope")):
    out = {}
    for w in windows:
        mp = max(2, w // 3)
        roll = x.rolling(w, min_periods=mp)
        for s in stats:
            if s == "slope":
                out[f"{name}_slope{w}"] = rolling_slope(x, w)
            else:
                out[f"{name}_{s}{w}"] = getattr(roll, s)()
    return out


def days_since(flag: pd.DataFrame, cap=999):
    """Days since flag was last True (inclusive of today = 0). NaN-safe, causal."""
    idx = np.arange(len(flag), dtype=float)[:, None]
    last = pd.DataFrame(np.where(flag.to_numpy(dtype=bool), idx, np.nan), index=flag.index, columns=flag.columns).ffill()
    return (-last).add(idx[:, 0], axis=0).clip(upper=cap)


def any_in_last(flag: pd.DataFrame, w: int):
    return flag.astype(float).rolling(w, min_periods=1).max().fillna(0) > 0
