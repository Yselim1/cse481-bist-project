"""Lock in Phase A multi-ticker foundation: universe is additive, shape check replaces the whitelist."""

from pathlib import Path

import pytest

from bist_analytics.config import ProjectConfig, load_universe
from bist_analytics.data.context import context_path_for
from bist_analytics.data.market import file_key, is_fx, is_index


def test_ticker_shape_check_accepts_bist_equities_indices_and_fx():
    for ticker in ["THYAO.IS", "AKBNK.IS", "XU100.IS", "XBANK.IS", "TRY=X", "EURTRY=X"]:
        assert file_key(ticker)  # does not raise
    assert is_fx("TRY=X") and not is_fx("THYAO.IS")
    assert is_index("XU100.IS") and not is_index("THYAO.IS")


@pytest.mark.parametrize("bad", ["thyao.is", "THYAO", "THYAO_IS", "THYA_O.IS", "123", ""])
def test_ticker_shape_check_rejects_malformed(bad):
    with pytest.raises(ValueError, match="INVALID_SYMBOL"):
        file_key(bad)


def test_project_config_defaults_stay_single_ticker():
    cfg = ProjectConfig()
    assert cfg.ticker == "THYAO.IS"
    assert cfg.universe == []
    assert cfg.sector_map == {}


def test_project_config_accepts_universe_with_sector_map():
    cfg = ProjectConfig(universe=["AKBNK.IS", "GARAN.IS"],
                        sector_map={"THYAO.IS": "airlines", "AKBNK.IS": "banking", "GARAN.IS": "banking"})
    assert cfg.universe == ["AKBNK.IS", "GARAN.IS"]
    assert cfg.sector_map["AKBNK.IS"] == "banking"


def test_project_config_rejects_duplicate_universe_tickers():
    with pytest.raises(ValueError, match="unique"):
        ProjectConfig(universe=["AKBNK.IS", "AKBNK.IS"])


def test_project_config_rejects_sector_map_entry_outside_universe():
    with pytest.raises(ValueError, match="sector_map keys"):
        ProjectConfig(sector_map={"AKBNK.IS": "banking"})


def test_project_config_rejects_malformed_universe_ticker():
    with pytest.raises(ValueError, match="universe ticker"):
        ProjectConfig(universe=["akbnk"])


def test_context_path_for_derives_slug_from_ticker():
    assert context_path_for("THYAO.IS") == "data/raw/kap/thyao_context_events.csv"
    assert context_path_for("AKBNK.IS") == "data/raw/kap/akbnk_context_events.csv"


def test_bist100_universe_manifest_loads_and_covers_five_sectors():
    manifest = load_universe()
    assert manifest["primary"] == "THYAO.IS"
    assert manifest["benchmark"] == "XU100.IS"
    assert len(manifest["tickers"]) >= 10
    sectors = set(manifest["sector_map"].values())
    assert {"airlines", "banking", "steel", "retail", "telecom"}.issubset(sectors)
    # every ticker has a sector
    assert set(manifest["sector_map"]) == set(manifest["tickers"])


def test_build_analysis_tolerates_missing_universe_cache(monkeypatch, tmp_path):
    """Universe tickers without cached data should log a warning, not break the primary pipeline."""
    from bist_analytics.config import load_config
    from bist_analytics.pipeline import build_analysis

    root = Path(__file__).resolve().parents[1]
    cfg = load_config(root / "config/tms29.yaml").model_copy(update={"universe": ["ZZZZZ.IS"]})
    analysis = build_analysis(root=root, config=cfg)
    assert "ZZZZZ.IS" not in analysis.universe_prices
    assert any("ZZZZZ.IS" in w for w in analysis.quality["warnings"])
    assert analysis.features is not None and len(analysis.features) > 0
