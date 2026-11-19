import json

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from bist_analytics.analysis.fundamentals import get_fundamental_metrics, safe_ratio, trailing_value
from bist_analytics.data.fundamentals import add_availability, parse_number
from bist_analytics.io import clean_json
from bist_analytics.schemas import FinancialObservation


def observations():
    rows = []
    for year, revenue, pub in [(2021,100,"2022-03-01"), (2022,120,"2023-03-01"), (2022,999,"2024-05-01")]:
        rows.append({"metric":"revenue", "value":revenue, "period_end":pd.Timestamp(year,12,31),
            "published_at":pd.Timestamp(pub), "period_type":"annual", "currency":"USD",
            "vintage_verified":True, "accounting_basis":"test", "source_url":"https://fintables.com"})
    return pd.DataFrame(rows)


def test_release_strictly_after_publication_and_later_revision_not_leaked():
    data = observations()
    sessions = pd.bdate_range("2022-01-01","2025-01-01")
    available = add_availability(data, sessions)
    assert available.available_at.iloc[0] == pd.Timestamp("2022-03-02")
    assert np.isnan(get_fundamental_metrics(available,"2022-03-01")["revenue"])
    assert get_fundamental_metrics(available,"2023-03-02")["revenue"] == 120
    assert get_fundamental_metrics(available,"2023-03-02")["revenue_growth"] == pytest.approx(.2)
    assert get_fundamental_metrics(available,"2024-05-02")["revenue"] == 999


def test_unverified_vintages_excluded_unless_explicitly_retrospective():
    data = observations()
    data.vintage_verified = False
    assert np.isnan(get_fundamental_metrics(data,"2023-05-01")["revenue"])
    assert get_fundamental_metrics(data,"2023-05-01",allow_unverified=True)["revenue"] == 120


def test_ytd_not_confused_with_single_quarter():
    data = pd.DataFrame({"metric":"revenue", "value":[40,100,60],
        "period_end":pd.to_datetime(["2021-06-30","2021-12-31","2022-06-30"]),
        "period_type":["ytd","annual","ytd"], "published_at":pd.Timestamp("2023-01-01")})
    assert trailing_value(data,"revenue",pd.Timestamp("2022-06-30")) == 120
    assert np.isnan(trailing_value(data.iloc[1:],"revenue",pd.Timestamp("2022-06-30")))


def test_numbers_ratios_and_source_rejection():
    assert parse_number("1.234.567,89","tr") == 1234567.89
    assert parse_number("(1,234.5)") == -1234.5
    assert parse_number("%15,2","tr") == .152
    assert parse_number("-","tr") is None
    assert np.isnan(safe_ratio(10,0)) and np.isnan(safe_ratio(10,-1))
    with pytest.raises(ValidationError,match="Fintables"):
        FinancialObservation(metric="revenue",period_end="2022-12-31",period_type="annual",value=100,
            currency="USD",published_at="2023-03-01",source_url="https://example.com",source_reference="test",
            retrieved_at="2023-03-02")
    assert json.dumps(clean_json({"a": np.nan, "b":pd.NaT}),allow_nan=False) == '{"a": null, "b": null}'
