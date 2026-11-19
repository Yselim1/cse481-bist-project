"""Trailing technical indicators with explicit SMA-seeded recurrences."""

import numpy as np
import pandas as pd

from bist_analytics.config import StrategyConfig


def seeded_average(values: pd.Series, window: int, alpha: float) -> pd.Series:
    result = np.full(len(values), np.nan)
    seed = []
    last = np.nan
    for i, x in enumerate(values.to_numpy(dtype=float)):
        if not np.isfinite(x):
            seed, last = [], np.nan
            continue
        if not np.isfinite(last):
            seed.append(x)
            if len(seed) == window:
                last = float(np.mean(seed))
                result[i] = last
        else:
            last = alpha * x + (1 - alpha) * last
            result[i] = last
    return pd.Series(result, index=values.index)


def ema(values: pd.Series, window: int) -> pd.Series:
    return seeded_average(values, window, 2 / (window + 1))


def rsi(values: pd.Series, window: int = 14) -> pd.Series:
    delta = values.diff()
    gain = seeded_average(delta.clip(lower=0), window, 1 / window)
    loss = seeded_average(-delta.clip(upper=0), window, 1 / window)
    result = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    result = result.mask((loss == 0) & (gain > 0), 100)
    result = result.mask((loss > 0) & (gain == 0), 0)
    return result.mask((loss == 0) & (gain == 0), 50)


def bollinger_bands(values: pd.Series, window: int = 20, num_std: float = 2.0) -> pd.DataFrame:
    middle = values.rolling(window).mean()
    std = values.rolling(window).std(ddof=0)
    return pd.DataFrame({"bb_middle": middle, "bb_upper": middle + num_std * std,
                         "bb_lower": middle - num_std * std,
                         "bb_width": (2 * num_std * std) / middle.replace(0, np.nan)})


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prior = close.shift(1)
    return pd.concat([high - low, (high - prior).abs(), (low - prior).abs()], axis=1).max(axis=1)


def atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    return seeded_average(true_range(high, low, close), window, 1 / window)


def kama(values: pd.Series, window: int = 10, fast: int = 2, slow: int = 30) -> pd.Series:
    """Kaufman Adaptive Moving Average; fast-smoothing when trending, slow-smoothing when choppy."""
    change = (values - values.shift(window)).abs()
    volatility = values.diff().abs().rolling(window).sum()
    efficiency = (change / volatility.replace(0, np.nan)).fillna(0).clip(0, 1)
    fast_sc, slow_sc = 2 / (fast + 1), 2 / (slow + 1)
    smoothing = (efficiency * (fast_sc - slow_sc) + slow_sc) ** 2
    result = np.full(len(values), np.nan)
    arr = values.to_numpy(dtype=float)
    sc = smoothing.to_numpy(dtype=float)
    last = np.nan
    for i in range(len(arr)):
        if i < window or not np.isfinite(arr[i]):
            continue
        if not np.isfinite(last):
            last = arr[i]
        else:
            last = last + sc[i] * (arr[i] - last)
        result[i] = last
    return pd.Series(result, index=values.index)


def supertrend(high: pd.Series, low: pd.Series, close: pd.Series,
               window: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
    """Supertrend: +1 uptrend, -1 downtrend; line flips when close crosses the opposite band."""
    atr_values = atr(high, low, close, window)
    hl2 = (high + low) / 2
    upper = hl2 + multiplier * atr_values
    lower = hl2 - multiplier * atr_values
    final_upper = pd.Series(np.nan, index=close.index)
    final_lower = pd.Series(np.nan, index=close.index)
    direction = pd.Series(0, index=close.index, dtype=int)
    line = pd.Series(np.nan, index=close.index)
    close_arr, upper_arr, lower_arr = close.to_numpy(), upper.to_numpy(), lower.to_numpy()
    fu, fl, dir_, ln = (final_upper.to_numpy().copy(), final_lower.to_numpy().copy(),
                        direction.to_numpy().copy(), line.to_numpy().copy())
    prev_dir = 1
    for i in range(len(close_arr)):
        if not np.isfinite(upper_arr[i]) or not np.isfinite(lower_arr[i]):
            dir_[i] = prev_dir
            continue
        fu[i] = upper_arr[i] if (i == 0 or not np.isfinite(fu[i - 1]) or upper_arr[i] < fu[i - 1] or close_arr[i - 1] > fu[i - 1]) else fu[i - 1]
        fl[i] = lower_arr[i] if (i == 0 or not np.isfinite(fl[i - 1]) or lower_arr[i] > fl[i - 1] or close_arr[i - 1] < fl[i - 1]) else fl[i - 1]
        if i == 0 or not np.isfinite(ln[i - 1]):
            dir_[i], ln[i] = prev_dir, fl[i] if prev_dir > 0 else fu[i]
        elif ln[i - 1] == fu[i - 1]:
            dir_[i] = 1 if close_arr[i] > fu[i] else -1
            ln[i] = fl[i] if dir_[i] > 0 else fu[i]
        else:
            dir_[i] = -1 if close_arr[i] < fl[i] else 1
            ln[i] = fu[i] if dir_[i] < 0 else fl[i]
        prev_dir = dir_[i]
    return pd.DataFrame({"supertrend": ln, "supertrend_direction": dir_, "supertrend_atr": atr_values},
                        index=close.index)


def calculate_indicators(market: pd.DataFrame, config: StrategyConfig | None = None) -> pd.DataFrame:
    settings = config or StrategyConfig()
    result = market.copy()
    result["sma_fast"] = result.close.rolling(settings.sma_fast).mean()
    result["sma_slow"] = result.close.rolling(settings.sma_slow).mean()
    result["ema_fast"] = ema(result.close, settings.sma_fast)
    result["ema_slow"] = ema(result.close, settings.sma_slow)
    result["rsi"] = rsi(result.close)
    result["macd"] = ema(result.close, 12) - ema(result.close, 26)
    result["macd_signal"] = ema(result.macd, 9)
    result["macd_histogram"] = result.macd - result.macd_signal
    result["volume_change"] = result.volume.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    result["volume_mean"] = result.volume.rolling(20).mean()
    result["relative_volume"] = result.volume / result.volume_mean.replace(0, np.nan)
    result["obv"] = (np.sign(result.close.diff()).fillna(0) * result.volume).cumsum()
    result = result.join(bollinger_bands(result.close, 20, 2.0))
    result["atr14"] = atr(result.high, result.low, result.close, 14)
    result["kama10"] = kama(result.close, 10, 2, 30)
    result = result.join(supertrend(result.high, result.low, result.close, 10, 3.0))
    result["technical_ready"] = result[["sma_slow", "rsi", "macd_signal", "relative_volume"]].notna().all(axis=1)
    return result
