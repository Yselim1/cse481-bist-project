"""Macro context series: TCMB EVDS (USD/TRY, EUR/TRY, policy rate) and TÜİK CPI.

All series are release-date aligned so backtests and the agent see values only after they
were published. Offline reproduction uses the cached CSVs committed under `data/raw/macro/`.
Network fetches run only on explicit `--refresh`.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Literal

import pandas as pd

from bist_analytics.io import sha256, utc_now, write_json

MACRO_DIR = "data/raw/macro"

Series = Literal["usdtry", "eurtry", "policy_rate", "cpi_yoy"]
# EVDS provides frequent updates; CPI is monthly (released mid-month for the prior month).
EVDS_SERIES = {"usdtry": "TP.DK.USD.A.YTL", "eurtry": "TP.DK.EUR.A.YTL",
               "policy_rate": "TP.APIFON4"}
TUIK_CPI_SERIES = "TP.FG.J0"  # EVDS proxy; TÜİK CPI headline index, monthly.


def _cache_path(root: Path, series: Series) -> Path:
    return root / MACRO_DIR / f"{series}.csv"


def _meta_path(root: Path, series: Series) -> Path:
    return root / MACRO_DIR / f"{series}.metadata.json"


def read_macro(root: Path, series: Series) -> pd.DataFrame:
    """Read a cached macro series; returns columns `{date, value, published_at, source}`."""
    path = _cache_path(root, series)
    if not path.exists():
        raise FileNotFoundError(f"Macro series {series} not cached at {path}")
    meta = json.loads(_meta_path(root, series).read_text(encoding="utf-8"))
    if sha256(path) != meta["sha256"]:
        raise ValueError(f"Macro hash mismatch for {series}")
    frame = pd.read_csv(path, parse_dates=["date", "published_at"])
    required = {"date", "value", "published_at", "source"}
    if missing := required - set(frame.columns):
        raise ValueError(f"Missing macro columns for {series}: {sorted(missing)}")
    return frame.sort_values("published_at").reset_index(drop=True)


def macro_context_as_of(root: Path, as_of: pd.Timestamp | str, series: list[Series] | None = None) -> dict:
    """Return the latest known value for each series known by `as_of` (release-time safe)."""
    instant = pd.Timestamp(as_of)
    if instant.tzinfo is not None:
        instant = instant.tz_convert("UTC").tz_localize(None)
    series = series or list(EVDS_SERIES.keys()) + ["cpi_yoy"]
    out: dict[str, dict | None] = {}
    for name in series:
        try:
            frame = read_macro(root, name)
        except FileNotFoundError:
            out[name] = None
            continue
        published = frame.published_at
        if hasattr(published.dt, "tz") and published.dt.tz is not None:
            published = published.dt.tz_convert("UTC").dt.tz_localize(None)
        visible = frame.loc[published <= instant]
        if visible.empty:
            out[name] = None
            continue
        last = visible.iloc[-1]
        out[name] = {"value": float(last.value),
                     "observation_date": str(pd.Timestamp(last.date).date()),
                     "published_at": str(pd.Timestamp(last.published_at).date()),
                     "source": str(last.source)}
    return out


def fetch_evds_series(code: str, start: str, end: str, api_key: str) -> pd.DataFrame:
    """Fetch an EVDS series. Requires an EVDS API key from https://evds2.tcmb.gov.tr/ .

    This is the network path; offline reproduction reads from `data/raw/macro/*.csv`.
    """
    import requests  # type: ignore[import-not-found]
    url = f"https://evds2.tcmb.gov.tr/service/evds/series={code}&startDate={start}&endDate={end}" \
          f"&type=json&aggregationTypes=avg&formulas=0&frequency=5"
    last_err = None
    for attempt in range(3):
        try:
            response = requests.get(url, headers={"key": api_key}, timeout=20)
            response.raise_for_status()
            body = response.json()
            rows = body.get("items") or []
            frame = pd.DataFrame(rows)
            if frame.empty:
                raise RuntimeError(f"EVDS returned no rows for {code}")
            value_col = next(c for c in frame.columns if c.startswith(code.replace(".", "_")))
            out = pd.DataFrame({"date": pd.to_datetime(frame["Tarih"], format="%d-%m-%Y", errors="coerce"),
                                "value": pd.to_numeric(frame[value_col], errors="coerce")})
            return out.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
        except Exception as exc:
            last_err = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"EVDS fetch failed for {code}: {last_err}") from last_err


def refresh_evds(root: Path, api_key: str, start: str, end: str) -> dict[str, int]:
    """Download USD/TRY, EUR/TRY and policy-rate series into the macro cache."""
    counts = {}
    for series, code in EVDS_SERIES.items():
        frame = fetch_evds_series(code, start, end, api_key)
        # Daily series publish same-day end-of-session; best assumption without a release calendar.
        frame["published_at"] = frame.date
        frame["source"] = f"TCMB EVDS {code}"
        path = _cache_path(root, series)  # type: ignore[arg-type]
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)
        write_json(_meta_path(root, series), {"series": series, "code": code,  # type: ignore[arg-type]
                                              "retrieved_at": utc_now(),
                                              "rows": len(frame), "sha256": sha256(path)})
        counts[series] = len(frame)
    return counts


def refresh_tuik_cpi(root: Path, api_key: str, start: str, end: str) -> int:
    """Download the TÜİK CPI (year-on-year), compute YoY change, and store release-date aligned."""
    frame = fetch_evds_series(TUIK_CPI_SERIES, start, end, api_key)
    # TÜİK releases the prior-month CPI around the 3rd business day of the current month.
    # Conservative: published_at = observation_month_end + 5 calendar days.
    frame["published_at"] = frame.date + pd.Timedelta(days=5)
    frame["source"] = f"TÜİK via EVDS {TUIK_CPI_SERIES}"
    frame["yoy"] = frame.value.pct_change(12)
    frame = frame.dropna(subset=["yoy"]).reset_index(drop=True)
    frame = frame.rename(columns={"value": "cpi_index"}).assign(value=lambda f: f.yoy)
    path = _cache_path(root, "cpi_yoy")
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    write_json(_meta_path(root, "cpi_yoy"), {"series": "cpi_yoy", "code": TUIK_CPI_SERIES,
                                             "retrieved_at": utc_now(), "rows": len(frame),
                                             "sha256": sha256(path)})
    return len(frame)
