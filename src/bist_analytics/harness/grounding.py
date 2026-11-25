"""Post-hoc audit: does every figure in the model's final answer appear in a tool output?

This is an *audit*, never a rewrite. The answer is left exactly as the model produced it;
the audit is stored next to it in the execution trace so a reader can see which numbers
are traceable to which evidence and which (if any) are not.

Matching rules (all reported per number):
* a figure written with ``d`` decimals matches a tool value if they agree within half a
  unit in the last displayed place (so ``12.35`` matches ``12.3471``);
* percentages may match a fraction (``-4.2%`` vs ``-0.0421``) and vice versa;
* the sign may be dropped in prose ("fell 4.2%" for ``-0.042``) — flagged ``abs_match``;
* thousands separators are stripped; ISO dates, years and ticker/identifier digits
  (``XU100``, ``Q3``) are not treated as figures;
* integers 0–10 (not percentages) are listed separately as ``small_integers`` (counts like "3 tools", "8
  labels") and are not counted as ungrounded unless ``strict_small_ints=True``.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable
from typing import Any

_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}(?:[T ][\d:.+\-Z]*)?\b|\b\d{1,2}[./]\d{1,2}[./]\d{2,4}\b")
_NUMBER = re.compile(r"(?<![A-Za-z0-9_.])([-+−]?)(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(\s?%)?(?![A-Za-z0-9_])")
_SCALES = (1.0, 100.0, 0.01)


def _numbers_in_text(text: str) -> list[float]:
    values = []
    for m in _NUMBER.finditer(_DATE.sub(" ", text or "")):
        sign = -1.0 if m.group(1) in ("-", "−") else 1.0
        try:
            value = sign * float(m.group(2).replace(",", "") + (m.group(3) or ""))
        except ValueError:
            continue
        values.append(value)
        if m.group(4):  # "8%" in evidence text also stands for the fraction 0.08
            values.append(value / 100)
    return values


def _walk(node: Any) -> Iterable[float]:
    if isinstance(node, bool) or node is None:
        return
    if isinstance(node, (int, float)):
        if math.isfinite(node):
            yield float(node)
    elif isinstance(node, str):
        stripped = node.strip()
        if stripped.startswith(("{", "[")):
            try:
                yield from _walk(json.loads(stripped))
                return
            except ValueError:
                pass
        yield from _numbers_in_text(node)
    elif isinstance(node, dict):
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, (list, tuple)):
        for value in node:
            yield from _walk(value)


def extract_figures(answer: str) -> list[dict]:
    """Return every figure in ``answer`` with its displayed precision."""
    figures = []
    for m in _NUMBER.finditer(_DATE.sub(" ", answer or "")):
        raw = m.group(0).strip()
        digits = m.group(2).replace(",", "")
        decimals = len(m.group(3)) - 1 if m.group(3) else 0
        value = float(digits + (m.group(3) or ""))
        if m.group(1) in ("-", "−"):
            value = -value
        is_year = decimals == 0 and not m.group(4) and 1900 <= abs(value) <= 2100
        figures.append({"text": raw, "value": value, "decimals": decimals,
                        "percent": bool(m.group(4)), "is_year": is_year})
    return figures


def _significant_digits(fig: dict) -> int:
    digits = re.sub(r"\D", "", fig["text"].split("%")[0])
    return len(digits.lstrip("0")) or 1


def _match(fig: dict, pool: list[float]) -> dict | None:
    v = fig["value"]
    coarse = _significant_digits(fig) < 2
    if coarse:
        # One significant digit ("5%", "0.3") is too coarse to attribute by rounding:
        # -4.82% would "round" to -5%, and "5%" would match any count of 5. Such figures
        # must equal a tool value exactly, keep their sign, and a percentage may only
        # match a fraction (5% <-> 0.05).
        tol = 1e-9 * max(1.0, abs(v))
        scales = (100.0,) if fig["percent"] else (1.0,)
    else:
        tol = 0.5 * 10 ** (-fig["decimals"]) + 1e-9
        scales = _SCALES
    best = None
    for t in pool:
        for scale in scales:
            candidate = t * scale
            if abs(candidate - v) <= tol:
                return {"tool_value": t, "scale": scale, "abs_match": False}
            if best is None and not coarse and abs(abs(candidate) - abs(v)) <= tol and v != 0:
                best = {"tool_value": t, "scale": scale, "abs_match": True}
    return best


def audit_answer(answer: str, evidence: Iterable[Any], *, prompt_texts: Iterable[str] = (),
                 strict_small_ints: bool = False) -> dict:
    """Audit ``answer`` against ``evidence`` (tool results, retrieved KB text, ...)."""
    pool = sorted(set(_walk(list(evidence))))
    prompt_values = {v for text in prompt_texts for v in _numbers_in_text(text)}
    grounded, ungrounded, from_prompt, small, years = [], [], [], [], []
    for fig in extract_figures(answer):
        if fig["is_year"]:
            years.append(fig["text"])
            continue
        match = _match(fig, pool)
        if match is not None:
            grounded.append({**fig, **match})
        elif fig["value"] in prompt_values or abs(fig["value"]) in prompt_values:
            from_prompt.append(fig["text"])
        elif (fig["decimals"] == 0 and not fig["percent"] and 0 <= abs(fig["value"]) <= 10
              and not strict_small_ints):
            small.append(fig["text"])
        else:
            ungrounded.append(fig)
    return {"numbers_found": len(grounded) + len(ungrounded) + len(from_prompt) + len(small),
            "grounded_count": len(grounded), "ungrounded_count": len(ungrounded),
            "all_grounded": not ungrounded,
            "grounded": grounded, "ungrounded": ungrounded,
            "echoed_from_prompt": from_prompt, "small_integers": small, "years_ignored": years,
            "evidence_values_indexed": len(pool),
            "method": "src/bist_analytics/harness/grounding.py (audit only; answer never modified)"}
