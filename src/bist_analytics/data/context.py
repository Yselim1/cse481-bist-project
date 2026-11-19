"""Validated, timestamped KAP context; this layer never changes strategy scores."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

CONTEXT_FILE = "data/raw/kap/thyao_context_events.csv"
REQUIRED = {"event_id", "published_at", "category", "title", "summary", "source_url", "evidence_status"}


def context_path_for(ticker: str) -> str:
    """Return the relative KAP context path for a ticker (e.g. THYAO.IS -> data/raw/kap/thyao_context_events.csv)."""
    slug = ticker.replace(".IS", "").lower()
    return f"data/raw/kap/{slug}_context_events.csv"


def load_context_events(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, keep_default_na=False)
    missing = REQUIRED - set(frame.columns)
    if missing:
        raise ValueError(f"Missing context columns: {sorted(missing)}")
    if frame.event_id.duplicated().any():
        raise ValueError("Duplicate context event_id")
    frame["published_at"] = pd.to_datetime(frame.published_at, utc=True)
    if frame.published_at.isna().any() or not frame.source_url.str.startswith("https://fintables.com/").all():
        raise ValueError("Context events require timestamped Fintables evidence")
    allowed = {"financial_report", "investment", "fleet", "partnership"}
    if not set(frame.category).issubset(allowed) or not (frame.evidence_status == "reviewed").all():
        raise ValueError("Invalid context category or evidence status")
    return frame.sort_values("published_at").reset_index(drop=True)


def context_as_of(events: pd.DataFrame, as_of: str | pd.Timestamp, limit: int = 20) -> pd.DataFrame:
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    instant = pd.Timestamp(as_of)
    if instant.tzinfo is None:
        instant = instant.tz_localize("Europe/Istanbul").tz_convert("UTC")
    else:
        instant = instant.tz_convert("UTC")
    return events.loc[events.published_at <= instant].tail(limit).copy()
