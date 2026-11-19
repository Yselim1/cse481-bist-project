import json

import numpy as np
import pandas as pd
import pytest

from bist_analytics.analysis.fundamentals import align_fundamentals, get_fundamental_metrics
from bist_analytics.config import ProjectConfig, project_root
from bist_analytics.data.fundamentals import add_availability, load_observations
from bist_analytics.data.originals import ORIGINAL_FILE, pdf_payload, verify_original_hashes


def test_original_release_vintages_scale_and_comparative_boundaries():
    records = load_observations(project_root()/ORIGINAL_FILE)
    assert len(records) == 136 and records.vintage_verified.all()
    available = add_availability(records,pd.bdate_range("2021-01-01","2025-12-31"))
    assert get_fundamental_metrics(available,"2022-03-01","TRY")["financial_status"] == "missing"
    first = get_fundamental_metrics(available,"2022-03-02","TRY")
    assert first["revenue"] == 97_378_000_000
    assert first["shares_outstanding"] == 1_380_000_000
    assert np.isnan(first["net_profit_growth"])  # FY2020 comparative loss, not positive growth.
    before = get_fundamental_metrics(available,"2025-02-28","TRY")
    after = get_fundamental_metrics(available,"2025-03-03","TRY")
    assert before["total_assets"] == 1_050_091_000_000
    assert after["revenue"] == 745_430_000_000
    assert after["roe"] == pytest.approx(113378/((679887+457257)/2))
    assert after["roa"] == pytest.approx(113378/((1399606+1048943)/2))
    assert after["ebitda"] == 136_256_000_000
    # Later comparative asset correction cannot change an earlier snapshot.
    truncated = available[available.published_at < "2025-02-28"]
    pd.testing.assert_series_equal(pd.Series(get_fundamental_metrics(truncated,"2025-02-28","TRY")),pd.Series(before))


def test_try_valuation_does_not_require_or_mix_daily_fx():
    records = load_observations(project_root()/ORIGINAL_FILE)
    dates = pd.bdate_range("2022-01-01","2025-03-05")
    market = pd.DataFrame({"raw_close":100.0},index=dates)
    fx = pd.DataFrame({"close":np.nan},index=dates)
    cfg = ProjectConfig(fundamental_currency="TRY",fundamentals_file=ORIGINAL_FILE)
    frame,_ = align_fundamentals(market,records,fx,cfg)
    assert frame.loc["2025-03-03","pe"] == pytest.approx(138000/113378)
    assert np.isnan(frame.loc["2025-03-03","market_cap_usd"])


def test_original_receipt_hashes_and_statement_reconciliations():
    root = project_root()
    verify_original_hashes(root)
    manifest = json.loads((root/"data/raw/fintables/originals/originals_manifest.json").read_text())
    assert len(manifest["statement_checks"]) == 8
    assert all(v == 0 for item in manifest["statement_checks"] for v in item["residuals_million_try"].values())
    assert len(manifest["comparative_revisions"]) == 4
    for item in manifest["files"].values():
        raw = (root/item["path"]).read_bytes()
        payload,offset = pdf_payload(raw)
        assert offset == 27 and payload.startswith(b"%PDF-")
        with pytest.raises(ValueError,match="length"):
            pdf_payload(raw[:-1])
