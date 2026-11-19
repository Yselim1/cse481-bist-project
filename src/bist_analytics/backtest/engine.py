from dataclasses import dataclass

import numpy as np
import pandas as pd

from bist_analytics.config import ProjectConfig
from bist_analytics.strategy.rules import Decision, Mode, generate_signal

ORDER_COLUMNS = ["decision_date", "execution_date", "side", "units", "reference_price", "fill_price",
                 "commission", "slippage_cost", "cash_after", "reason"]
TRADE_COLUMNS = ["entry_date", "exit_date", "entry_price", "exit_price", "units", "net_pnl",
                 "net_return", "holding_sessions", "entry_reason", "exit_reason", "status"]


@dataclass
class BacktestResult:
    daily: pd.DataFrame
    orders: pd.DataFrame
    trades: pd.DataFrame
    signals: pd.DataFrame
    mode: str
    initial_capital: float


def replay_order_equity(features: pd.DataFrame, result: BacktestResult) -> pd.Series:
    """Gross counterfactual holding execution dates/sides fixed, without fees or slippage."""
    cash, units = result.initial_capital, 0.0
    orders = result.orders.set_index("execution_date") if len(result.orders) else result.orders
    values = []
    for day,row in features.reindex(result.daily.index).iterrows():
        if len(orders) and day in orders.index:
            side = orders.loc[day,"side"]
            if side == "BUY":
                units, cash = cash/row.open, 0.0
            else:
                cash, units = units*row.open, 0.0
        values.append(cash+units*row.close)
    return pd.Series(values,index=result.daily.index,name="gross_same_executions_equity")


def run_backtest(features: pd.DataFrame, config: ProjectConfig, mode: Mode = "combined",
                 start: str | None = None, end: str | None = None) -> BacktestResult:
    start = pd.Timestamp(start or config.evaluation_start)
    end = pd.Timestamp(end or config.evaluation_end)
    data = features.loc[(features.index >= start) & (features.index < end)]
    if data.empty:
        raise ValueError("INSUFFICIENT_HISTORY: empty evaluation interval")
    if not np.isfinite(data[["open", "close"]].to_numpy()).all() or (data[["open", "close"]] <= 0).any().any():
        raise ValueError("Invalid execution or mark price; missing prices cannot be filled")
    if data.index.has_duplicates or not data.index.is_monotonic_increasing:
        raise ValueError("Backtest dates must be unique and ascending")
    cash = config.initial_capital
    units = 0.0
    entry_price = entry_cost = 0.0
    entry_i, entry_day, entry_reason = -1, None, ""
    pending, pending_date = None, None
    commission, slippage = config.commission_bps/10_000, config.slippage_bps/10_000
    daily, orders, trades, signals = [], [], [], []
    previous_equity = config.initial_capital
    for i, (day, row) in enumerate(data.iterrows()):
        if mode == "buy_hold" and i == 0:
            pending, pending_date = Decision("BUY", "scheduled_buy_and_hold_entry"), None
        fees_today = slippage_today = 0.0
        executed_side = ""
        if pending:
            executed_side = pending.action
            reference = float(row.open)
            fill = reference * (1+slippage if pending.action == "BUY" else 1-slippage)
            if pending.action == "BUY":
                if units > 0:
                    raise AssertionError("Repeated entry into an existing position")
                bought = cash / (fill*(1+commission))
                fees_today = bought*fill*commission
                slippage_today = bought*(fill-reference)
                entry_cost = bought*fill+fees_today
                cash -= entry_cost
                units, entry_price = bought, fill
                entry_i, entry_day, entry_reason = i, day, pending.reason
                order_units = units
            else:
                if units <= 0:
                    raise AssertionError("Cannot sell while flat")
                fees_today = units*fill*commission
                slippage_today = units*(reference-fill)
                proceeds = units*fill-fees_today
                cash += proceeds
                trades.append({"entry_date": entry_day, "exit_date": day, "entry_price": entry_price,
                    "exit_price": fill, "units": units, "net_pnl": proceeds-entry_cost,
                    "net_return": proceeds/entry_cost-1, "holding_sessions": i-entry_i,
                    "entry_reason": entry_reason, "exit_reason": pending.reason, "status": "closed"})
                order_units, units = units, 0.0
            orders.append({"decision_date": pending_date, "execution_date": day, "side": pending.action,
                "units": order_units, "reference_price": reference, "fill_price": fill,
                "commission": fees_today, "slippage_cost": slippage_today, "cash_after": cash,
                "reason": pending.reason})
            pending = None
        equity = cash+units*float(row.close)
        if cash < -1e-7 or equity <= 0:
            raise AssertionError("Invalid cash/equity accounting")
        holding_sessions = i-entry_i+1 if units > 0 else 0
        decision = (Decision("HOLD", "exit_session_cooldown") if executed_side == "SELL"
                    else generate_signal(row, units > 0, entry_price, holding_sessions, config.strategy, mode))
        record = {"date": day, "action": decision.action, "reason": decision.reason,
                  "position": int(units > 0), "next_session_order": decision.action in {"BUY", "SELL"}}
        for key in ["close", "sma_fast", "sma_slow", "rsi", "support", "support_distance", "technical_score",
                    "fundamental_score", "combined_score", "financial_period", "financial_age_days"]:
            record[key] = row.get(key)
        signals.append(record)
        daily.append({"date": day, "equity": equity, "cash": cash, "units": units,
            "position_value": units*float(row.close), "position": int(units > 0),
            "return": equity/previous_equity-1, "commission": fees_today, "slippage_cost": slippage_today})
        previous_equity = equity
        if decision.action in {"BUY", "SELL"}:
            pending, pending_date = decision, day
    if units > 0:
        mark_value = units*float(data.iloc[-1].close)
        trades.append({"entry_date": entry_day, "exit_date": pd.NaT, "entry_price": entry_price,
            "exit_price": np.nan, "units": units, "net_pnl": mark_value-entry_cost,
            "net_return": mark_value/entry_cost-1, "holding_sessions": len(data)-entry_i,
            "entry_reason": entry_reason, "exit_reason": "marked_open_at_end", "status": "open"})
    return BacktestResult(pd.DataFrame(daily).set_index("date"), pd.DataFrame(orders, columns=ORDER_COLUMNS),
                          pd.DataFrame(trades, columns=TRADE_COLUMNS), pd.DataFrame(signals).set_index("date"),
                          mode, config.initial_capital)
