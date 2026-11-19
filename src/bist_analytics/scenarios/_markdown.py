"""Tiny Markdown-pipe-table formatter so scenario reports don't require `tabulate`."""

from __future__ import annotations

import math

import pandas as pd


def _fmt(value, floatfmt: str) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    if isinstance(value, float):
        return format(value, floatfmt.lstrip("%"))
    return str(value)


def to_markdown(frame: pd.DataFrame, index: bool = False, floatfmt: str = ".3f") -> str:
    if frame.empty:
        return "_(empty)_"
    if index:
        frame = frame.reset_index()
    columns = list(frame.columns)
    rows = frame.values.tolist()
    header = "| " + " | ".join(str(c) for c in columns) + " |"
    sep = "| " + " | ".join("---" for _ in columns) + " |"
    body = "\n".join("| " + " | ".join(_fmt(v, floatfmt) for v in row) + " |" for row in rows)
    return "\n".join([header, sep, body])
