"""Offline, reproducible analysis and evaluation orchestration."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from bist_analytics.analysis.fundamentals import align_fundamentals
from bist_analytics.analysis.indicators import calculate_indicators
from bist_analytics.analysis.levels import find_support_resistance
from bist_analytics.analysis.scoring import add_scores
from bist_analytics.backtest.engine import BacktestResult, replay_order_equity, run_backtest
from bist_analytics.backtest.metrics import calculate_performance, equity_metrics, index_equity
from bist_analytics.config import ProjectConfig, load_config, project_root
from bist_analytics.data.fundamentals import load_observations, quality_report
from bist_analytics.data.market import adjusted_view, file_key, read_market, validate_market
from bist_analytics.data.originals import ORIGINAL_FILE, verify_original_hashes
from bist_analytics.data.tms29 import TMS29_FILE, verify_tms29_hashes
from bist_analytics.io import sha256, utc_now, write_json


@dataclass
class Analysis:
    config: ProjectConfig
    features: pd.DataFrame
    snapshots: pd.DataFrame
    pivots: pd.DataFrame
    zones: pd.DataFrame
    benchmark: pd.DataFrame
    quality: dict
    universe_prices: dict[str, pd.DataFrame] = None  # type: ignore[assignment]


def _load_price_frame(root: Path, ticker: str) -> pd.DataFrame:
    path = root / "data/raw/market" / f"{file_key(ticker)}.csv"
    meta = json.loads(path.with_suffix(".metadata.json").read_text(encoding="utf-8"))
    if sha256(path) != meta["sha256"]:
        raise ValueError(f"Source hash mismatch for {ticker}")
    return read_market(path, ticker)


def build_analysis(root: Path | None = None, config: ProjectConfig | None = None) -> Analysis:
    root, config = root or project_root(), config or load_config()
    prices, market_quality = {}, {}
    for ticker in [config.ticker, config.benchmark, config.fx_ticker]:
        prices[ticker] = _load_price_frame(root, ticker)
        market_quality[ticker] = validate_market(prices[ticker], ticker)
    universe_prices: dict[str, pd.DataFrame] = {}
    universe_warnings: list[str] = []
    for ticker in config.universe:
        if ticker in prices:
            universe_prices[ticker] = prices[ticker]
            continue
        try:
            universe_prices[ticker] = _load_price_frame(root, ticker)
            market_quality[ticker] = validate_market(universe_prices[ticker], ticker)
        except (FileNotFoundError, ValueError) as exc:
            universe_warnings.append(f"Universe ticker {ticker} skipped: {exc}")
    if config.fundamentals_file == ORIGINAL_FILE:
        verify_original_hashes(root)
    if config.fundamentals_file == TMS29_FILE:
        verify_tms29_hashes(root)
    observations = load_observations(root / config.fundamentals_file)
    market = adjusted_view(prices[config.ticker])
    indicators = calculate_indicators(market, config.strategy)
    levels, pivots, zones = find_support_resistance(market, config.strategy)
    fundamentals, snapshots = align_fundamentals(market, observations, prices[config.fx_ticker], config)
    features = add_scores(indicators.join(levels).join(fundamentals), config.strategy)
    evaluation = features.loc[str(config.evaluation_start):].loc[lambda x: x.index < pd.Timestamp(config.evaluation_end)]
    benchmark = prices[config.benchmark]
    warnings = ["Single user-selected stock; selection/survivorship bias; no market-wide inference.",
                "Nominal TRY returns, zero cash yield and zero-risk-free Sharpe.",
                "Adjusted synthetic units; whole-lot execution and taxes not modeled.",
                "BIST100 price-index basis differs from adjusted stock return basis."]
    if quality_report(observations)["unverified_vintage_rows"]:
        warnings.append("Historical Fintables vintages are unverified: retrospective results can contain revision bias; strict mode excludes these inputs.")
    if observations.published_at.isna().any():
        warnings.append("Some releases use an assumed following-June-30 date, not a verified actual publication date.")
    if config.fundamentals_file == ORIGINAL_FILE:
        warnings.extend(["Original annual statement vintages and comparative revisions are dated; interim reports are outside this annual-refresh strategy.",
                         "Original TRY presentation is nominal: growth and return on average balances are affected by inflation and currency translation.",
                         "Source/currency correction was made after the earlier USD results were inspected; 2025 is a chronological parameter holdout, not a pristine blind test."])
    if config.fundamentals_file == TMS29_FILE:
        warnings.extend(["Primary analysis uses one internally consistent post-TMS 29 basis; pre-2025 trading results are outside its evaluation window.",
                         "2026 is partial through the last cached session before the exclusive evaluation end.",
                         "KAP context is evidence for interpretation and does not alter any strategy score or order."])
    warnings.extend(universe_warnings)
    quality = {"market": market_quality, "fundamentals": quality_report(observations),
        "evaluation_sessions": len(evaluation), "fundamental_complete_sessions": int(evaluation.fundamental_score.notna().sum()),
        "fundamental_fresh_sessions": int(evaluation.financial_fresh.sum()),
        "missing_fx_dates": evaluation.index[evaluation.usdtry.isna()].strftime("%Y-%m-%d").tolist(),
        "stock_only_dates": market.index.difference(benchmark.index).strftime("%Y-%m-%d").tolist(),
        "index_only_dates": benchmark.index.difference(market.index).strftime("%Y-%m-%d").tolist(),
        "warnings": warnings, "vintage_policy": config.vintage_policy,
        "universe_tickers": sorted(universe_prices.keys()),
        "universe_missing": [t for t in config.universe if t not in universe_prices]}
    return Analysis(config, features, snapshots, pivots, zones, benchmark, quality, universe_prices)


def evaluate(analysis: Analysis, start: str | None = None, end: str | None = None) -> tuple[dict, dict[str, BacktestResult], pd.Series]:
    config = analysis.config
    results = {mode: run_backtest(analysis.features, config, mode, start, end) for mode in ["combined","technical","buy_hold"]}
    sessions = results["combined"].daily.index
    matched = sessions.intersection(analysis.benchmark.index)
    if matched.empty or matched[0] != sessions[0] or matched[-1] != sessions[-1]:
        raise ValueError("Benchmark comparison needs matching first and last dates")
    reference = index_equity(analysis.benchmark, matched, config.initial_capital)
    bm = equity_metrics(reference, config.initial_capital, config.annual_sessions)
    performance = {mode: calculate_performance(result, bm["cumulative_return"], config.annual_sessions)
                   for mode,result in results.items()}
    for mode,result in results.items():
        gross = replay_order_equity(analysis.features,result)
        performance[mode]["gross_return_same_executions"] = float(gross.iloc[-1]/config.initial_capital-1)
    performance["bist100"] = {**bm, "basis":"BIST100 price index; no costs", "missing_sessions":len(sessions)-len(matched)}
    return performance, results, reference


def run_pipeline(root: Path | None = None, config: ProjectConfig | None = None) -> dict:
    root = root or project_root()
    analysis = build_analysis(root, config)
    output = root / "outputs" / analysis.config.output_name
    output.mkdir(parents=True, exist_ok=True)
    performance, results, reference = evaluate(analysis)
    analysis.features.to_parquet(output / "features.parquet")
    analysis.features.to_csv(output / "features.csv", float_format="%.12g")
    analysis.snapshots.to_csv(output / "financial_snapshots.csv", index=False)
    analysis.pivots.to_csv(output / "pivots.csv", index=False)
    analysis.zones.to_csv(output / "zones.csv", index=False)
    for mode, result in results.items():
        for name in ["daily", "orders", "trades", "signals"]:
            getattr(result,name).to_csv(output / f"{mode}_{name}.csv", index=name in {"daily","signals"})
        replay_order_equity(analysis.features,result).to_csv(output / f"{mode}_gross_same_executions.csv")
    reference.to_csv(output / "bist100_equity.csv")
    periods = {}
    for year in range(analysis.config.evaluation_start.year, analysis.config.evaluation_end.year + 1):
        start = max(pd.Timestamp(analysis.config.evaluation_start), pd.Timestamp(f"{year}-01-01"))
        end = min(pd.Timestamp(analysis.config.evaluation_end), pd.Timestamp(f"{year+1}-01-01"))
        if start < end:
            periods[str(year)] = evaluate(analysis, str(start.date()), str(end.date()))[0]
    write_json(output / "performance.json",performance)
    write_json(output / "annual_evaluations.json",periods)
    write_json(output / "quality.json",analysis.quality)
    sources = [p for p in (root / "data").rglob("*") if p.is_file() and p.suffix in {".csv",".tsv",".json",".pdf"}]
    source_hashes = {str(p.relative_to(root)).replace("\\","/"):sha256(p) for p in sorted(sources)}
    code_hashes = {str(p.relative_to(root)).replace("\\","/"):sha256(p) for p in sorted((root/"src").rglob("*.py"))}
    manifest = {"created_at":utc_now(),"config":analysis.config.model_dump(mode="json"),
                "source_hashes":source_hashes,"code_hashes":code_hashes,"lock_sha256":sha256(root/"uv.lock"),
                "output_directory":str(output),"warnings":analysis.quality["warnings"]}
    manifest["run_id"] = hashlib.sha256(json.dumps({"config":manifest["config"],"sources":source_hashes,
        "code":code_hashes,"lock":manifest["lock_sha256"]},sort_keys=True).encode()).hexdigest()[:16]
    write_json(output / "run_manifest.json",manifest)
    from bist_analytics.reporting import create_report
    create_report(analysis,performance,results,reference,periods,output)
    return {"output":str(output),"performance":performance,"quality":analysis.quality}
