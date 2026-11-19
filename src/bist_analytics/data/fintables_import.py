"""Reproducibly normalize captured Fintables table excerpts; no network scraping."""

from pathlib import Path

import pandas as pd

from bist_analytics.data.fundamentals import load_observations, parse_number
from bist_analytics.io import sha256, write_json
from bist_analytics.schemas import FLOW_METRICS, FinancialObservation

BASE_URL = "https://fintables.com/sirketler/THYAO/finansal-tablolar/"
SOURCES = {"balance": "bilanco", "income": "gelir-tablosu", "cashflow": "nakit-akim-tablosu",
           "capital": "bilanco"}
MAP = {
    "revenue": ("income", "Satış Gelirleri"), "gross_profit": ("income", "Brüt Kar (Zarar)"),
    "operating_profit": ("income", "Faaliyet Karı (Zararı)"), "net_profit": ("income", "Ana Ortaklık Payları"),
    "cash": ("balance", "Nakit ve Nakit Benzerleri"), "total_assets": ("balance", "Toplam Varlıklar"),
    "equity": ("balance", "Ana Ortaklığa Ait Özkaynaklar"),
    "current_assets": ("balance", "Toplam Dönen Varlıklar"), "inventories": ("balance", "Stoklar"),
    "current_liabilities": ("balance", "Toplam Kısa Vadeli Yükümlülükler"),
    "operating_cash_flow": ("cashflow", "İşletme Faaliyetlerinden Nakit Akışları"),
    "investing_cash_flow": ("cashflow", "Yatırım Faaliyetlerinden Kaynaklanan Nakit Akışları"),
    "financing_cash_flow": ("cashflow", "Finansman Faaliyetlerinden Nakit Akışları"),
}


def normalize_fintables(root: Path) -> dict:
    folder = root / "data/raw/fintables"
    tables, files = {}, {}
    for name in SOURCES:
        path = folder / f"{name}_annual_{'try' if name == 'capital' else 'usd'}.tsv"
        tables[name] = pd.read_csv(path, sep="\t", dtype=str).set_index("label")
        files[name] = {"path": str(path.relative_to(root)), "sha256": sha256(path),
                       "source_url": BASE_URL+SOURCES[name]+"?period=12&type=&currency="
                                     + ("try" if name == "capital" else "usd") + "&mode=adjusted"}
    observations = []
    for period in tables["income"].columns:
        end = pd.Timestamp(int(period[:4]), 12, 31)

        def value(table, label):
            number = parse_number(tables[table].loc[label, period], "tr")
            if number is None:
                raise ValueError(f"Missing source value: {table}/{label}/{period}")
            return number*1000

        values = {metric: value(*mapping) for metric, mapping in MAP.items()}
        values["ebitda"] = sum(value("income", label) for label in ["Brüt Kar (Zarar)",
            "Genel Yönetim Giderleri (-)", "Pazarlama, Satış ve Dağıtım Giderleri (-)", "Amortisman"])
        values["financial_debt"] = value("balance", "Finansal Borçlar (Kısa)")+value("balance", "Finansal Borçlar (Uzun)")
        values["net_debt"] = values["financial_debt"]-values["cash"]-value("balance", "Finansal Yatırımlar (Dönen)")-value("balance", "Finansal Yatırımlar (Duran)")
        # TRY 1 nominal-capital units, as in Fintables' market-cap formula. Treasury shares are not subtracted.
        values["shares_outstanding"] = value("capital", "Ödenmiş Sermaye")
        verified_dates = {2023: "2024-04-03", 2025: "2026-03-04"}
        for metric, number in values.items():
            name = MAP[metric][0] if metric in MAP else {"ebitda": "income", "shares_outstanding": "capital"}.get(metric, "balance")
            observations.append(FinancialObservation(metric=metric, period_end=end.date(),
                period_type="annual" if metric in FLOW_METRICS else "instant", value=number,
                currency="USD", unit="shares" if metric == "shares_outstanding" else "money",
                published_at=verified_dates.get(end.year),
                assumed_published_at=None if end.year in verified_dates else pd.Timestamp(end.year+1, 6, 30).date(),
                source_url=files[name]["source_url"], source_reference=files[name]["path"]+"; docs/DATA_SOURCES.md",
                retrieved_at="2026-09-15", vintage_verified=False,
                accounting_basis="Fintables-displayed-USD-current-vintage",
                notes="Captured table values; not an original-release archive. Unknown release dates use June 30 of the following year. "
                      + ("Derived using Fintables formula; signed expenses; no separate R&D line displayed." if metric == "ebitda" else
                         "Financial debt minus cash and both financial-investment rows." if metric == "net_debt" else
                         "TRY nominal capital / TRY 1; share units have no currency conversion." if metric == "shares_outstanding" else "")
            ).model_dump())
    destination = root / "data/processed/fintables_observations.csv"
    destination.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(observations).to_csv(destination, index=False)
    records = load_observations(destination)
    manifest = {"source": "Fintables", "retrieved_at": "2026-09-15", "files": files,
        "observations": len(records), "normalized_sha256": sha256(destination),
        "vintage_verified": False, "release_policy": "Two verified dates; other dates explicitly assumed at following June 30",
        "formula_source": "https://fintables.com/arastirma/yazilar/degerleme-analizi-101/fdfavok"}
    write_json(folder / "manifest.json", manifest)
    return manifest
