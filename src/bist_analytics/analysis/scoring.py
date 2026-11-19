"""Scores return component points and completeness separately."""

import numpy as np
import pandas as pd

from bist_analytics.config import StrategyConfig


def calculate_fundamental_score(features: pd.DataFrame, config: StrategyConfig) -> pd.DataFrame:
    result = features.copy()
    valid_pe = result.pe.where(result.pe > 0).dropna()
    history_median = valid_pe.shift(1).rolling(config.valuation_lookback,
                                              min_periods=config.valuation_min_history).median()
    result["pe_history_median"] = history_median.reindex(result.index)
    components = {
        "growth": (result.revenue_growth > config.revenue_growth_threshold, result.revenue_growth.notna()),
        "profit_growth": (result.net_profit_growth > config.profit_growth_threshold, result.net_profit_growth.notna()),
        "roe": (result.roe > config.roe_threshold, result.roe.notna()),
        "leverage": (result.net_debt_ebitda < config.debt_ebitda_threshold,
                     result.net_debt_ebitda.notna() & (result.ebitda > 0)),
        "valuation": ((result.pe > 0) & (result.pe <= result.pe_history_median),
                      result.pe.notna() & result.pe_history_median.notna()),
    }
    for name, (passed, valid) in components.items():
        result[f"f_{name}"] = passed.astype(float).where(valid)
    cols = [f"f_{name}" for name in components]
    result["fundamental_components"] = result[cols].notna().sum(axis=1)
    result["fundamental_score"] = result[cols].sum(axis=1, min_count=5)
    result["fundamental_label"] = np.select([result.fundamental_score <= 1, result.fundamental_score <= 3,
                                             result.fundamental_score <= 5], ["weak", "neutral", "strong"], "incomplete")
    return result


def add_scores(features: pd.DataFrame, config: StrategyConfig) -> pd.DataFrame:
    result = calculate_fundamental_score(features, config)
    components = {
        "trend": (result.sma_fast > result.sma_slow, result.sma_slow.notna()),
        "rsi": (result.rsi.between(35, 55), result.rsi.notna()),
        "macd": (result.macd > result.macd_signal, result.macd_signal.notna()),
        "volume": (result.relative_volume >= 1, result.relative_volume.notna()),
        "support": (result.support_distance <= config.support_distance, result.support_distance.notna()),
    }
    for name, (passed, valid) in components.items():
        result[f"t_{name}"] = passed.astype(float).where(valid)
    result["technical_score"] = result[[f"t_{name}" for name in components]].sum(axis=1, min_count=5)
    result["combined_score"] = (config.technical_weight * result.technical_score / 5
                                 + (1-config.technical_weight) * result.fundamental_score / 5)
    return result
