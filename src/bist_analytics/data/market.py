"""Yahoo retrieval is isolated from deterministic analysis and offline tests."""

import re
import time
from pathlib import Path

import numpy as np
import pandas as pd

from bist_analytics.io import sha256, utc_now, write_json

_TICKER_SHAPE = re.compile(r"^(?:\^?[A-Z0-9]{2,10}\.IS|[A-Z]{2,6}=X)$")


def is_fx(ticker: str) -> bool:
    return ticker.endswith("=X")


def is_index(ticker: str) -> bool:
    # BIST indices are exposed under names like XU100.IS, XBANK.IS, XUSIN.IS.
    return ticker.endswith(".IS") and ticker.replace(".IS", "").startswith("X")


def file_key(ticker: str) -> str:
    if not _TICKER_SHAPE.match(ticker):
        raise ValueError(f"INVALID_SYMBOL: {ticker!r} must match 'XXXX.IS' or 'XXX=X'")
    return ticker.replace("=", "_")


def validate_market(frame: pd.DataFrame, ticker: str = "THYAO.IS") -> dict:
    if frame.empty:
        raise ValueError("NO_PRICE_DATA: empty market table")
    required = ["open", "high", "low", "close", "adj_close", "volume"]
    if missing := set(required) - set(frame.columns):
        raise ValueError(f"Missing market columns: {sorted(missing)}")
    if not isinstance(frame.index, pd.DatetimeIndex) or frame.index.hasnans:
        raise ValueError("Market index must contain valid dates")
    if frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        raise ValueError("Market dates must be unique and sorted")
    prices = frame[required[:-1]]
    if not np.isfinite(prices.to_numpy(dtype=float)).all() or (prices <= 0).any().any():
        raise ValueError("Market prices must be finite and positive; missing prices are not filled")
    bad = (frame.low > frame[["open", "close"]].min(axis=1) + 1e-8) | (
        frame.high < frame[["open", "close"]].max(axis=1) - 1e-8
    ) | (frame.low > frame.high)
    if bad.any() and not is_fx(ticker):
        raise ValueError(f"Invalid OHLC range at {frame.index[bad][0]}")
    equity = ticker.endswith(".IS") and not is_index(ticker)
    if (frame.volume.dropna() < 0).any() or (equity and frame.volume.isna().any()):
        raise ValueError("Stock volume must be present and nonnegative")
    return {"ticker": ticker, "rows": len(frame), "first": str(frame.index.min().date()),
            "last": str(frame.index.max().date()), "zero_volume_sessions": int((frame.volume == 0).sum()),
            "large_close_moves": int((frame.close.pct_change(fill_method=None).abs() > 0.25).sum()),
            "inconsistent_ohlc_rows": int(bad.sum()),
            "fx_usage": "close only; provider OHLC inconsistencies retained and flagged" if is_fx(ticker) else None}


def normalize_download(raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
    data = raw.copy()
    if isinstance(data.columns, pd.MultiIndex):
        level = next((i for i in range(data.columns.nlevels) if ticker in data.columns.get_level_values(i)), None)
        if level is None:
            raise ValueError("Requested ticker missing from provider columns")
        data = data.xs(ticker, level=level, axis=1)
    data.columns = [str(c).lower().replace(" ", "_") for c in data.columns]
    data.index = pd.DatetimeIndex(pd.to_datetime(data.index))
    if data.index.tz is not None:
        data.index = data.index.tz_localize(None)
    data.index = data.index.normalize()
    data.index.name = "date"
    data = data.sort_index()
    # Index/FX adjusted close equals close when no adjustment column is supplied.
    if "adj_close" not in data and (is_fx(ticker) or is_index(ticker)):
        data["adj_close"] = data["close"]
    for col in ["dividends", "stock_splits"]:
        if col not in data:
            data[col] = 0.0
    validate_market(data, ticker)
    return data


def adjusted_view(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    factor = frame.adj_close / frame.close
    result["raw_close"] = frame.close
    for col in ["open", "high", "low", "close"]:
        result[col] = frame[col] * factor
    result["adjustment_factor"] = factor
    return result


def read_market(path: Path, ticker: str) -> pd.DataFrame:
    data = pd.read_csv(path, parse_dates=["date"]).set_index("date")
    validate_market(data, ticker)
    return data


def get_stock_history(ticker: str, start: str, end: str, directory: Path, refresh: bool = False) -> pd.DataFrame:
    key = file_key(ticker)
    if pd.Timestamp(start) >= pd.Timestamp(end):
        raise ValueError("INVALID_DATES: end is exclusive and must follow start")
    path = directory / f"{key}.csv"
    metadata_path = directory / f"{key}.metadata.json"
    if path.exists() and not refresh:
        import json

        meta = json.loads(metadata_path.read_text(encoding="utf-8"))
        if meta["request"]["start"] != start or meta["request"]["end"] != end:
            raise ValueError("Cached bounds differ. Use fetch --refresh explicitly.")
        if meta["sha256"] != sha256(path):
            raise ValueError("Cached market hash mismatch")
        return read_market(path, ticker)
    import yfinance as yf
    cache = directory / ".yfinance_cache"
    cache.mkdir(parents=True, exist_ok=True)
    yf.set_tz_cache_location(str(cache))

    last_error = None
    for attempt in range(3):
        try:
            raw = yf.download(ticker, start=start, end=end, interval="1d", auto_adjust=False,
                              actions=True, progress=False, threads=False, timeout=25,
                              multi_level_index=True, repair=False)
            data = normalize_download(raw, ticker)
            directory.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".csv.tmp")
            data.to_csv(temporary, float_format="%.12g")
            temporary.replace(path)
            write_json(metadata_path, {"source": "Yahoo Finance via yfinance", "ticker": ticker,
                "request": {"start": start, "end": end, "interval": "1d", "auto_adjust": False,
                            "actions": True, "repair": False}, "retrieved_at": utc_now(),
                "yfinance_version": yf.__version__, "sha256": sha256(path),
                "quality": validate_market(data, ticker),
                "return_basis": "provider adjusted OHLC; preserve raw prices and actions"})
            return read_market(path, ticker)
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Market retrieval failed for {ticker}: {last_error}") from last_error
