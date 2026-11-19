"""Parse the reviewed post-TMS 29 THYAO statements hosted by Fintables."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import pandas as pd
from pypdf import PdfReader

from bist_analytics.data.fundamentals import load_observations
from bist_analytics.data.originals import pdf_payload
from bist_analytics.io import sha256, write_json
from bist_analytics.schemas import FLOW_METRICS, FinancialObservation

TMS29_FILE = "data/processed/fintables_tms29_observations.csv"
ACCOUNTING_BASIS = "TMS29-THY-TFRS-consolidated-TRY"
RETRIEVED_AT = "2026-09-27"


@dataclass(frozen=True)
class Report:
    key: str
    period_end: str
    comparative_end: str
    period_type: str
    published_at: str
    pages: tuple[int, int, int, int]
    source_url: str
    evidence_url: str


REPORTS = (
    Report("2024FY", "2024-12-31", "2023-12-31", "annual", "2025-02-28", (9, 10, 11, 13),
           "https://storage.fintables.com/media/uploads/kap-attachments/THY%20A.O.%20Aral%C4%B1k%202024.pdf",
           "https://www.kap.org.tr/tr/Bildirim/1396940"),
    Report("2025Q1", "2025-03-31", "2024-03-31", "ytd", "2025-04-28", (2, 3, 4, 6),
           "https://storage.fintables.com/media/uploads/kap-attachments/THY%20A.O.%20Mart%202025.pdf",
           "https://fintables.com/borsa-haber-akisi/a3432935-b179-4ed1-a5c7-9e21ee900a7a/thyao-finansal-rapor"),
    Report("2025Q2", "2025-06-30", "2024-06-30", "ytd", "2025-08-05", (3, 4, 5, 8),
           "https://storage.fintables.com/media/uploads/kap-attachments/THY%20AO%20Haziran%202025.pdf",
           "https://fintables.com/borsa-haber-akisi/ae1ecf79-500a-4ca7-9153-269b2a6a5a18/thyao-finansal-rapor"),
    Report("2025Q3", "2025-09-30", "2024-09-30", "ytd", "2025-11-07", (2, 3, 4, 7),
           "https://storage.fintables.com/media/uploads/kap-attachments/THY%20AO%20Eyl%C3%BCl%202025.pdf",
           "https://fintables.com/borsa-haber-akisi/231614f1-9ca9-4786-93c5-1cdd96e7d0d1/thyao-finansal-rapor"),
    Report("2025FY", "2025-12-31", "2024-12-31", "annual", "2026-03-04", (9, 10, 11, 13),
           "https://storage.fintables.com/media/uploads/kap-attachments/THY%20A.O.%20Aral%C4%B1k%202025.pdf",
           "https://fintables.com/borsa-haber-akisi/ac19e15a-2370-4ed9-86c7-0a67b6746841/thyao-finansal-rapor"),
    Report("2026Q1", "2026-03-31", "2025-03-31", "ytd", "2026-04-29", (2, 3, 4, 6),
           "https://storage.fintables.com/media/uploads/kap-attachments/THY%20A.O.%20Mart%202026.pdf",
           "https://fintables.com/borsa-haber-akisi/4c4ab8e3-ce67-4f08-b163-c76265f1d391/thyao-finansal-rapor"),
    Report("2026Q2", "2026-06-30", "2025-06-30", "ytd", "2026-08-05", (3, 4, 5, 8),
           "https://storage.fintables.com/media/uploads/kap-attachments/THY%20A.O.%20Haziran%202026.pdf",
           "https://fintables.com/borsa-haber-akisi/bf8af587-78d6-4fe4-82f0-8dbb4bd082a8/thyao-finansal-rapor"),
)

_NUMBER = re.compile(r"\(\s*\d[\d.]*\)|(?<![\w.])-?(?:\d{1,3}(?:\.\d{3})+|\d+)(?![\w.])|(?<!\w)-(?!\w)")


def _number(token: str) -> float:
    token = token.strip()
    if token == "-":
        return 0.0
    negative = token.startswith("(")
    value = float(token.strip("() ").replace(".", ""))
    return -value if negative else value


def _values(line: str, count: int) -> list[float]:
    values = [_number(value) for value in _NUMBER.findall(line)]
    if len(values) < count:
        raise ValueError(f"Expected {count} financial values in: {line!r}")
    return values[-count:]


def _line(text: str, pattern: str, *, occurrence: int = 0) -> str:
    matches = [line for line in text.splitlines() if re.search(pattern, line, re.I)]
    if len(matches) <= occurrence:
        raise ValueError(f"Missing statement line /{pattern}/")
    return matches[occurrence]


def _pair(text: str, pattern: str, count: int = 2, *, occurrence: int = 0) -> list[float]:
    return _values(_line(text, pattern, occurrence=occurrence), count)


def _income_pair(text: str, pattern: str, columns: int) -> list[float]:
    values = _pair(text, pattern, columns)
    return [values[0], values[2]] if columns == 4 else values


def _parse_report(report: Report, root: Path) -> tuple[list[dict], dict, list[dict]]:
    path = (root / "data/raw/fintables/originals/THYAO_2024_original.pdf" if report.key == "2024FY" else
            root / "data/raw/fintables/tms29_originals" / f"THYAO_{report.key}_original.pdf")
    payload, offset = pdf_payload(path.read_bytes())
    reader = PdfReader(BytesIO(payload))
    asset, liability, income, cashflow = [reader.pages[page - 1].extract_text() for page in report.pages]
    income_columns = 4 if "1 Nisan-" in income or "1 Temmuz-" in income else 2

    direct = {
        "cash": _pair(asset, r"^Nakit ve Nakit Benzerleri"),
        "investments_current": _pair(asset, r"^Finansal Yat"),
        "inventories": _pair(asset, r"^Stoklar"),
        "current_assets": _pair(asset, r"^TOPLAM D.*NEN VARLIKLAR"),
        "noncurrent_assets": _pair(asset, r"^TOPLAM DURAN VARLIKLAR"),
        "total_assets": _pair(asset, r"^TOPLAM VARLIKLAR"),
        "current_liabilities": _pair(liability, r"^TOPLAM KISA VADEL"),
        "noncurrent_liabilities": _pair(liability, r"^TOPLAM UZUN VADEL"),
        "equity": _pair(liability, r"^Ana ortakl.*ait.*zkaynaklar", occurrence=-1),
        "total_sources": _pair(liability, r"^TOPLAM KAYNAKLAR"),
        "shares_outstanding": _pair(liability, r"^.?denmi.*Sermaye"),
        "revenue": _income_pair(income, r"^Has.lat", income_columns),
        "cost_of_sales": _income_pair(income, r"^Sat.*lar.*Maliyeti", income_columns),
        "gross_profit": _income_pair(income, r"^BR.T (?:KAR|K.R)", income_columns),
        "administrative_expense": _income_pair(income, r"^Genel Y.netim Giderleri", income_columns),
        "selling_expense": _income_pair(income, r"^Pazarlama Giderleri", income_columns),
        "operating_profit": _income_pair(income, r"^ESAS FAAL.YET (?:KARI|ZARARI|\(ZARARI\)/K.RI|K.RI)", income_columns),
        "net_profit": _income_pair(income, r"Ana Ortakl.*Paylar", income_columns),
        "depreciation": _pair(cashflow, r"^Amortisman ve .tfa Gideri"),
        "operating_cash_flow": _pair(cashflow, r"^.*letme Faaliyetlerinden Kaynaklanan Net Nakit"),
        "investing_cash_flow": _pair(cashflow, r"^Yat.r.m Faaliyetlerinden Kaynaklanan Net Nakit"),
        "financing_cash_flow": _pair(cashflow, r"^Finansman Faaliyetlerinde (?:Kullan.lan|Kaynaklanan) Net Nakit"),
        "cashflow_opening_cash": _pair(cashflow, r"^D.nem Ba.*Nakit ve Nakit Benzerleri"),
        "cashflow_closing_cash": _pair(cashflow, r"^D.nem Sonu Nakit ve Nakit Benzerleri"),
    }
    net_change_lines = [line for line in cashflow.splitlines() if re.search(r"Nakit ve Nakit Benzeri De.erlerdeki Net De.i.im", line, re.I)]
    direct["cashflow_change"] = _values(net_change_lines[-1], 2)
    debt = [0.0, 0.0]
    for line in liability.splitlines():
        if re.search(r"Banka Kredileri|Kiralama .*lemlerinden Bor.lanmalar", line, re.I):
            values = _values(line, 2)
            debt = [a + b for a, b in zip(debt, values)]

    observations, checks = [], []
    balance_ends = [report.period_end, report.period_end[:4] + "-12-31"]
    if report.key.endswith("Q1") or report.key.endswith("Q2") or report.key.endswith("Q3"):
        balance_ends[1] = f"{int(report.period_end[:4])-1}-12-31"
    else:
        balance_ends[1] = report.comparative_end
    pages_by_metric = {
        "cash": report.pages[0], "total_assets": report.pages[0], "current_assets": report.pages[0],
        "inventories": report.pages[0], "financial_debt": report.pages[1], "net_debt": f"{report.pages[0]},{report.pages[1]}",
        "equity": report.pages[1], "current_liabilities": report.pages[1], "shares_outstanding": report.pages[1],
        "revenue": report.pages[2], "gross_profit": report.pages[2], "operating_profit": report.pages[2],
        "net_profit": report.pages[2], "ebitda": f"{report.pages[2]},{report.pages[3]}",
        "operating_cash_flow": report.pages[3], "investing_cash_flow": report.pages[3], "financing_cash_flow": report.pages[3],
    }
    for column in range(2):
        identities = {
            "assets": direct["total_assets"][column] - direct["current_assets"][column] - direct["noncurrent_assets"][column],
            "sources": direct["total_assets"][column] - direct["total_sources"][column],
            "gross_profit": direct["revenue"][column] + direct["cost_of_sales"][column] - direct["gross_profit"][column],
            "cash_rollforward": direct["cashflow_opening_cash"][column] + direct["cashflow_change"][column] - direct["cashflow_closing_cash"][column],
        }
        if any(abs(value) > 1 for value in identities.values()):
            raise ValueError(f"Statement identity failed for {report.key} column {column}: {identities}")
        checks.append({"report": report.key, "column": column, "residuals_million_try": identities})
        computed = {
            "ebitda": direct["gross_profit"][column] + direct["administrative_expense"][column]
                      + direct["selling_expense"][column] + direct["depreciation"][column],
            "financial_debt": debt[column],
            "net_debt": debt[column] - direct["cash"][column] - direct["investments_current"][column],
        }
        for metric in ["cash", "total_assets", "equity", "current_assets", "inventories", "current_liabilities", "shares_outstanding"]:
            computed[metric] = direct[metric][column]
        for metric in FLOW_METRICS - {"ebitda"}:
            computed[metric] = direct[metric][column]
        for metric, value in computed.items():
            period_end = report.period_end if metric in FLOW_METRICS else balance_ends[column]
            if metric in FLOW_METRICS and column == 1:
                period_end = report.comparative_end
            period_type = report.period_type if metric in FLOW_METRICS else "instant"
            note = "Current" if column == 0 else "Comparative"
            if metric == "net_debt":
                note += "; Fintables convention: bank/lease debt minus cash and current financial investments."
            elif metric == "ebitda":
                note += "; gross profit plus signed administrative and selling expenses plus depreciation/amortization."
            elif metric == "shares_outstanding":
                note += "; nominal paid capital divided by TRY1; treasury shares are not subtracted."
            else:
                note += "; original million-TRY presentation, without currency conversion."
            observations.append(FinancialObservation(
                metric=metric, period_end=period_end, period_type=period_type, value=value, scale=1_000_000,
                currency="TRY", unit="shares" if metric == "shares_outstanding" else "money",
                published_at=report.published_at, retrieved_at=RETRIEVED_AT, vintage_verified=True,
                accounting_basis=ACCOUNTING_BASIS, source_url=report.source_url,
                source_reference=f"{path.relative_to(root).as_posix()}; PDF page(s) {pages_by_metric[metric]}; publication evidence {report.evidence_url}",
                notes=note,
            ).model_dump())
    file_record = {
        "path": path.relative_to(root).as_posix(), "sha256": sha256(path),
        "pdf_payload_sha256": hashlib.sha256(payload).hexdigest(), "envelope_bytes": offset,
        "pages": len(reader.pages), "parsed_statement_pages": list(report.pages),
        "source_url": report.source_url, "published_at": report.published_at,
        "publication_evidence": report.evidence_url,
    }
    return observations, file_record, checks


def normalize_tms29(root: Path) -> dict:
    """Parse all reviewed reports, validate identities, and write a hash-addressed dataset."""
    observations, files, checks = [], {}, []
    for report in REPORTS:
        parsed, file_record, report_checks = _parse_report(report, root)
        observations.extend(parsed)
        files[report.key] = file_record
        checks.extend(report_checks)
    destination = root / TMS29_FILE
    destination.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(observations).to_csv(destination, index=False)
    records = load_observations(destination)
    manifest = {
        "source": "Fintables-hosted original post-TMS 29 THYAO statements",
        "accounting_basis": ACCOUNTING_BASIS,
        "financial_currency": "TRY", "unit": "million TRY", "retrieved_at": RETRIEVED_AT,
        "observations": len(records), "verified_vintage_rows": int(records.vintage_verified.sum()),
        "normalized_file": TMS29_FILE, "normalized_sha256": sha256(destination),
        "files": files, "statement_checks": checks,
        "timing_policy": "Every report vintage becomes usable at the first stock-session close strictly after its verified disclosure date.",
        "net_debt_policy": "Financial debt less cash and current financial investments, matching the Fintables company summary.",
        "scope": "Primary internally consistent TMS 29 study: FY2024 annual anchor, 2025, and the latest available 2026 interim report, with report-published comparatives retained as vintages.",
    }
    manifest_path = root / "data/raw/fintables/tms29_originals/tms29_manifest.json"
    write_json(manifest_path, manifest)
    return manifest


def verify_tms29_hashes(root: Path) -> None:
    manifest_path = root / "data/raw/fintables/tms29_originals/tms29_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = {entry["path"]: entry["sha256"] for entry in manifest["files"].values()}
    expected[TMS29_FILE] = manifest["normalized_sha256"]
    for path, digest in expected.items():
        if sha256(root / path) != digest:
            raise ValueError(f"TMS 29 source hash mismatch: {path}")
