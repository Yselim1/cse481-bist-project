"""Validated project configuration; dates use an exclusive end."""

import re
from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

_TICKER_SHAPE = re.compile(r"^(?:\^?[A-Z0-9]{2,10}\.IS|[A-Z]{2,6}=X)$")


def _check_ticker_shape(value: str, label: str) -> None:
    if not _TICKER_SHAPE.match(value):
        raise ValueError(f"{label} {value!r} must look like 'XXXX.IS' (BIST) or 'XXX=X' (FX)")


class StrategyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sma_fast: int = Field(20, ge=2)
    sma_slow: int = Field(50, ge=3)
    pivot_left: int = Field(5, ge=1)
    pivot_right: int = Field(5, ge=1)
    zone_lookback: int = Field(252, ge=20)
    zone_tolerance: float = Field(0.015, gt=0, lt=0.2)
    zone_min_touches: int = Field(2, ge=2)
    support_distance: float = Field(0.02, gt=0, lt=0.2)
    revenue_growth_threshold: float = 0.15
    profit_growth_threshold: float = 0.15
    roe_threshold: float = 0.20
    debt_ebitda_threshold: float = Field(4, gt=0)
    valuation_min_history: int = Field(63, ge=5)
    valuation_lookback: int = Field(252, ge=5)
    technical_weight: float = Field(0.6, ge=0, le=1)
    fundamental_min_score: int = Field(3, ge=0, le=5)
    entry_score: float = Field(0.7, ge=0, le=1)
    stop_loss: float = Field(0.08, gt=0, lt=1)
    max_holding_sessions: int = Field(40, ge=1)

    @model_validator(mode="after")
    def check_windows(self):
        if self.sma_fast >= self.sma_slow:
            raise ValueError("sma_fast must be smaller than sma_slow")
        if self.valuation_min_history > self.valuation_lookback:
            raise ValueError("valuation_min_history exceeds lookback")
        return self


class ProjectConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticker: str = "THYAO.IS"
    benchmark: str = "XU100.IS"
    fx_ticker: str = "TRY=X"
    market_start: date = date(2021, 1, 1)
    evaluation_start: date = date(2023, 1, 1)
    evaluation_end: date = date(2026, 1, 1)
    currency: str = "TRY"
    fundamental_currency: str = "USD"
    fundamentals_file: str = "data/processed/fintables_observations.csv"
    output_name: str = "verified_only"
    initial_capital: float = Field(100_000, gt=0)
    commission_bps: float = Field(10, ge=0, lt=1000)
    slippage_bps: float = Field(5, ge=0, lt=1000)
    annual_sessions: int = Field(252, ge=1)
    max_fundamental_age_days: int = Field(460, ge=1)
    vintage_policy: Literal["verified_only", "retrospective"] = "verified_only"
    universe: list[str] = Field(default_factory=list)
    sector_map: dict[str, str] = Field(default_factory=dict)
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)

    @model_validator(mode="after")
    def check_scope(self):
        if not self.market_start <= self.evaluation_start < self.evaluation_end:
            raise ValueError("Require market_start <= evaluation_start < evaluation_end")
        _check_ticker_shape(self.ticker, "ticker")
        _check_ticker_shape(self.benchmark, "benchmark")
        _check_ticker_shape(self.fx_ticker, "fx_ticker")
        for extra in self.universe:
            _check_ticker_shape(extra, "universe ticker")
        if len(set(self.universe)) != len(self.universe):
            raise ValueError("universe tickers must be unique")
        unknown_sectors = set(self.sector_map) - set(self.universe) - {self.ticker}
        if unknown_sectors:
            raise ValueError(f"sector_map keys not in universe/primary: {sorted(unknown_sectors)}")
        if self.currency != "TRY" or self.fundamental_currency not in {"USD", "TRY"}:
            raise ValueError("Primary market uses TRY prices and explicitly selected TRY or USD fundamentals")
        path = Path(self.fundamentals_file)
        if path.is_absolute() or ".." in path.parts or path.parent.as_posix() != "data/processed" or path.suffix != ".csv":
            raise ValueError("fundamentals_file must be a CSV directly under data/processed")
        if not path.name.startswith("fintables_"):
            raise ValueError("Historical fundamentals must use a Fintables dataset")
        if not self.output_name.replace("_", "").replace("-", "").isalnum():
            raise ValueError("output_name must contain only letters, numbers, hyphens, or underscores")
        if (self.fundamentals_file.endswith("fintables_original_observations.csv") or
                self.fundamentals_file.endswith("fintables_tms29_observations.csv")) and self.fundamental_currency != "TRY":
            raise ValueError("Original statements use TRY presentation")
        return self


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_config(path: str | Path | None = None) -> ProjectConfig:
    config_path = Path(path) if path else project_root() / "config/project.yaml"
    return ProjectConfig.model_validate(yaml.safe_load(config_path.read_text(encoding="utf-8")))


def load_universe(path: str | Path | None = None) -> dict:
    """Load the multi-ticker universe manifest shared across sector/weekday/reversal analyses."""
    manifest_path = Path(path) if path else project_root() / "config/bist100_universe.yaml"
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    tickers = [row["ticker"] for row in data["tickers"]]
    for ticker in tickers:
        _check_ticker_shape(ticker, "universe ticker")
    if len(set(tickers)) != len(tickers):
        raise ValueError("universe manifest contains duplicate tickers")
    return {"name": data.get("universe_name", "universe"), "tickers": tickers,
            "sector_map": {row["ticker"]: row["sector"] for row in data["tickers"]},
            "primary": data.get("primary"), "benchmark": data.get("benchmark"), "fx": data.get("fx")}
