"""Evidence bundle builder.

An evidence bundle snapshots everything the agent observed from tool calls plus the subset
it committed to in its final answer. The quality gate audits it; the fine-tuning dataset
embeds its schema; the harness scorer counts committed-evidence coverage.
"""

from __future__ import annotations

import hashlib
from typing import Any, Iterable

import pandas as pd

from bist_analytics.schemas import EvidenceBundle, EvidenceItem


def _digest(payload: Any) -> str:
    return hashlib.sha256(repr(payload).encode("utf-8")).hexdigest()[:12]


def observation(source_tool: str, value: Any, *, as_of: str | None = None, unit: str | None = None,
                source_document: str | None = None, note: str | None = None,
                evidence_id: str | None = None) -> EvidenceItem:
    return EvidenceItem(evidence_id=evidence_id or f"{source_tool}:{_digest(value)}",
                        source_tool=source_tool, value=value, as_of=as_of, unit=unit,
                        source_document=source_document, note=note)


def build_evidence_bundle(*, ticker: str, as_of: str,
                          observed: Iterable[EvidenceItem], committed: Iterable[EvidenceItem],
                          educational_label: str, gate_status: str, reason: str,
                          warnings: Iterable[str] = ()) -> EvidenceBundle:
    return EvidenceBundle(ticker=ticker, as_of=as_of, observed=list(observed),
                          committed=list(committed), educational_label=educational_label,
                          gate_status=gate_status, reason=reason, warnings=list(warnings))


def summarize_from_features(features: pd.DataFrame, as_of: str) -> list[EvidenceItem]:
    """Convenience: observation items for the last available row at `as_of`."""
    day = pd.Timestamp(as_of)
    window = features.loc[features.index <= day]
    if window.empty:
        return []
    row = window.iloc[-1]
    items: list[EvidenceItem] = []
    for col in ["close", "sma_fast", "sma_slow", "rsi", "macd", "macd_signal",
                "bb_lower", "bb_upper", "atr14", "kama10", "supertrend_direction",
                "technical_score", "fundamental_score", "combined_score"]:
        if col in row.index and pd.notna(row[col]):
            items.append(observation("calculate_indicators" if "score" not in col else "calculate_scores",
                                     float(row[col]) if hasattr(row[col], "__float__") else row[col],
                                     as_of=str(window.index[-1].date()), unit="value", note=col))
    return items
