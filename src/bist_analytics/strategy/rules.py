from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from bist_analytics.config import StrategyConfig

Mode = Literal["combined", "technical", "buy_hold"]


@dataclass(frozen=True)
class Decision:
    action: str
    reason: str


def generate_signal(row: pd.Series, holding: bool, entry_price: float, holding_sessions: int,
                    config: StrategyConfig, mode: Mode = "combined") -> Decision:
    if mode not in {"combined", "technical", "buy_hold"}:
        raise ValueError(f"Unknown strategy mode: {mode}")
    if mode == "buy_hold":
        return Decision("HOLD", "buy_and_hold")
    def finite(*keys):
        return all(np.isfinite(row.get(key, np.nan)) for key in keys)
    if holding:
        if row.close <= entry_price * (1-config.stop_loss):
            return Decision("SELL", "close_stop_loss")
        if holding_sessions >= config.max_holding_sessions:
            return Decision("SELL", "maximum_holding_period")
        if mode == "combined":
            if not finite("fundamental_score") or not row.get("financial_fresh", False):
                return Decision("SELL", "fundamentals_unavailable_or_stale")
            if row.fundamental_score <= 2:
                return Decision("SELL", "fundamental_deterioration")
        if not finite("sma_fast", "sma_slow", "rsi"):
            return Decision("SELL", "technical_data_unavailable")
        if row.sma_fast <= row.sma_slow:
            return Decision("SELL", "trend_reversal")
        if row.rsi >= 70:
            return Decision("SELL", "rsi_exit")
        return Decision("HOLD", "retain_position")
    if not finite("technical_score", "sma_fast", "sma_slow", "support_distance"):
        return Decision("HOLD", "technical_warmup_or_no_support")
    if row.sma_fast <= row.sma_slow:
        return Decision("HOLD", "trend_filter")
    if row.support_distance > config.support_distance:
        return Decision("HOLD", "support_too_far")
    if mode == "technical":
        return Decision("BUY", "technical_entry") if row.technical_score >= 4 else Decision("HOLD", "technical_score_filter")
    if not finite("fundamental_score", "combined_score") or not row.get("financial_fresh", False):
        return Decision("HOLD", "fundamentals_unavailable_or_stale")
    if row.fundamental_score < config.fundamental_min_score:
        return Decision("HOLD", "fundamental_score_filter")
    if row.combined_score < config.entry_score:
        return Decision("HOLD", "combined_score_filter")
    return Decision("BUY", "combined_entry")
