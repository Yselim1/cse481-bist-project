"""Regenerate Scenario 1–4 reports from a configured universe analysis.

Usage (PowerShell):
    .\.venv\Scripts\python.exe scripts/build_scenarios.py --config config/universe10.yaml

Writes Markdown + CSV outputs under `outputs/{output_name}/scenarios/`.
Missing universe tickers produce warnings rather than failures.
"""

from __future__ import annotations

import argparse
import json

from bist_analytics.config import load_config, project_root
from bist_analytics.pipeline import build_analysis
from bist_analytics.scenarios import (
    fundamental_reaction,
    reversal_events,
    sector_laggard,
    weekday_patterns,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Scenario 1–4 reports from the configured universe.")
    parser.add_argument("--config", required=True, help="Path to a ProjectConfig YAML with a populated universe.")
    args = parser.parse_args()

    root = project_root()
    config = load_config(args.config)
    if not config.universe:
        raise SystemExit("Config has no `universe` entries; nothing to analyse.")
    analysis = build_analysis(root=root, config=config)
    out = root / "outputs" / config.output_name / "scenarios"
    out.mkdir(parents=True, exist_ok=True)

    start, end = str(config.evaluation_start), str(config.evaluation_end)

    missing = analysis.quality.get("universe_missing", [])
    summary: dict[str, object] = {"start": start, "end": end,
                                   "universe_tickers": sorted(analysis.universe_prices.keys()),
                                   "universe_missing": missing}

    s1 = sector_laggard.run(analysis.universe_prices, config.sector_map, start, end, output_dir=out)
    summary["s1_anchors"] = s1.get("anchors", 0)

    s2 = weekday_patterns.run(analysis.universe_prices, start, end, output_dir=out)
    summary["s2_weekday_rows"] = int(len(s2["weekday_panel"]))

    s3 = reversal_events.run(analysis.universe_prices, analysis.benchmark, start, end, output_dir=out)
    summary["s3_events"] = int(len(s3["events_panel"]))

    # S4 reuses the primary-ticker fundamental release ledger.
    from bist_analytics.data.fundamentals import load_observations
    observations = load_observations(root / config.fundamentals_file)
    releases = (observations[["period_end", "published_at"]]
                .drop_duplicates()
                .assign(ticker=config.ticker)
                .rename(columns={"period_end": "period"}))
    s4 = fundamental_reaction.run(releases, analysis.universe_prices, analysis.benchmark,
                                  sector_map=config.sector_map, ticker=config.ticker, output_dir=out)
    summary["s4_releases"] = int(len(s4["panel"]))

    (out / "scenarios_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
