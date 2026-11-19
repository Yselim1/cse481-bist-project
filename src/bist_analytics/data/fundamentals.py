"""Validated Fintables imports with explicit release assumptions and vintage flags."""

from pathlib import Path

import pandas as pd

from bist_analytics.schemas import FinancialObservation

OBSERVATION_COLUMNS = list(FinancialObservation.model_fields)


def parse_number(value, locale: str = "en") -> float | None:
    if pd.isna(value) or str(value).strip() in {"", "-", "N/A", "n/a", "None"}:
        return None
    if isinstance(value, (float, int)):
        return float(value)
    text = str(value).strip().replace("\u00a0", "").replace(" ", "")
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    percent = "%" in text
    text = text.replace("%", "")
    if locale == "tr":
        text = text.replace(".", "").replace(",", ".")
    elif locale == "en":
        text = text.replace(",", "")
    else:
        raise ValueError("Number locale must be tr or en")
    number = float(text) * (-1 if negative else 1)
    return number / 100 if percent else number


def load_observations(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"MISSING_FUNDAMENTALS: supply audited Fintables observations at {path}")
    raw = pd.read_csv(path, keep_default_na=False)
    rows = []
    for i, record in enumerate(raw.to_dict("records"), 2):
        try:
            if record.get("value", "") == "":
                record["value"] = None
            record = {k: v for k, v in record.items() if v != "" or k in {"value", "notes"}}
            item = FinancialObservation.model_validate(record)
            row = item.model_dump()
            row["value"] = None if item.value is None else item.value * item.scale
            row["scale"] = 1.0
            rows.append(row)
        except Exception as exc:
            raise ValueError(f"Invalid fundamental CSV row {i}: {exc}") from exc
    frame = pd.DataFrame(rows, columns=OBSERVATION_COLUMNS)
    for col in ["period_end", "published_at", "assumed_published_at", "retrieved_at"]:
        frame[col] = pd.to_datetime(frame[col])
    key = ["ticker", "metric", "period_end", "period_type", "currency", "published_at", "accounting_basis"]
    if frame.duplicated(key).any():
        raise ValueError("Duplicate fundamental observation/vintage")
    return frame.sort_values(["published_at", "period_end", "metric"]).reset_index(drop=True)


def add_availability(records: pd.DataFrame, sessions: pd.DatetimeIndex) -> pd.DataFrame:
    """Date-only reports become usable at the first session close strictly after publication."""
    result = records.copy()
    release = result.published_at.fillna(result.get("assumed_published_at", pd.NaT))
    locations = sessions.searchsorted(release, side="right")
    result["available_at"] = [sessions[i] if i < len(sessions) else pd.NaT for i in locations]
    return result


def quality_report(records: pd.DataFrame) -> dict:
    return {"observations": len(records), "periods": sorted(records.period_end.dt.strftime("%Y-%m-%d").unique()),
            "currencies": sorted(records.currency.unique()), "verified_vintage_rows": int(records.vintage_verified.sum()),
            "unverified_vintage_rows": int((~records.vintage_verified).sum()),
            "assumed_release_rows": int(records.published_at.isna().sum()),
            "missing_values": int(records.value.isna().sum()), "metrics": sorted(records.metric.unique())}


def write_template(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(columns=OBSERVATION_COLUMNS).to_csv(path, index=False)
