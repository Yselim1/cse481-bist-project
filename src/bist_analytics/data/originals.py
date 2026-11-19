"""Import reviewed Fintables-hosted original statements, retaining every vintage."""

import hashlib
import json
from io import BytesIO
from pathlib import Path

import pandas as pd
from pypdf import PdfReader

from bist_analytics.data.fundamentals import load_observations
from bist_analytics.io import sha256, write_json
from bist_analytics.schemas import FLOW_METRICS, FinancialObservation

ORIGINAL_FILE = "data/processed/fintables_original_observations.csv"
DIRECT = ["revenue", "gross_profit", "operating_profit", "net_profit", "cash",
          "total_assets", "equity", "current_assets", "inventories", "current_liabilities",
          "operating_cash_flow", "investing_cash_flow", "financing_cash_flow"]
DEBT_LINES = ["bank_loans_current_related", "bank_loans_current_other",
              "bank_loans_current_portion_related", "bank_loans_current_portion_other",
              "lease_debt_current", "bank_loans_noncurrent_related",
              "bank_loans_noncurrent_other", "lease_debt_noncurrent"]


def pdf_payload(raw: bytes) -> tuple[bytes, int]:
    """Unwrap only the observed Java byte-array envelope; never deserialize Java."""
    if raw.startswith(b"%PDF-"):
        return raw, 0
    prefix = bytes.fromhex("aced0005757200025b42acf317f8060854e00200007870")
    if raw[:23] != prefix or raw[27:32] != b"%PDF-":
        raise ValueError("Unrecognized PDF envelope")
    if int.from_bytes(raw[23:27], "big") != len(raw)-27:
        raise ValueError("PDF envelope length mismatch")
    return raw[27:], 27


def normalize_originals(root: Path) -> dict:
    folder = root/"data/raw/fintables/originals"
    capture = json.loads((folder/"transcription.json").read_text(encoding="utf-8"))
    evidence = json.loads((folder/"release_evidence.json").read_text(encoding="utf-8"))
    if capture["currency"] != "TRY" or capture["unit"] != "million TRY":
        raise ValueError("Expected original million TRY presentation")
    observations, files, checks = [], {}, []
    for year, pairs in capture["reports"].items():
        path = folder/f"THYAO_{year}_original.pdf"
        payload, offset = pdf_payload(path.read_bytes())
        reader = PdfReader(BytesIO(payload))
        if year not in reader.pages[0].extract_text():
            raise ValueError(f"Report year mismatch: {path}")
        url = "https://storage.fintables.com/media/uploads/kap-attachments/THY%20A.O.%20Aral%C4%B1k%20"+year+".pdf"
        files[year] = {"path":path.relative_to(root).as_posix(), "sha256":sha256(path),
                       "pdf_payload_sha256":hashlib.sha256(payload).hexdigest(),
                       "envelope_bytes":offset, "pages":len(reader.pages), "source_url":url,
                       "published_at":evidence[year]["published_at"],
                       "publication_evidence":evidence[year]["evidence_url"],
                       "visually_reviewed_pdf_pages":[9,10,11,13]}
        if set(pairs) != set(capture["pages"]) or any(len(pair) != 2 for pair in pairs.values()):
            raise ValueError(f"Incomplete transcription: {year}")
        for column in [0,1]:
            v = {name:pair[column] for name,pair in pairs.items()}
            period = int(year)-column
            identities = {
                "balance":v["total_assets"]-v["current_liabilities"]-v["noncurrent_liabilities"]-v["equity"]-v["minority_equity"],
                "asset_subtotals":v["total_assets"]-v["current_assets"]-v["noncurrent_assets"],
                "gross_profit":v["revenue"]+v["cost_of_sales"]-v["gross_profit"],
                "cashflow_sum":v["operating_cash_flow"]+v["investing_cash_flow"]+v["financing_cash_flow"]-v["cashflow_change"],
                "cashflow_rollforward":v["cashflow_opening_cash"]+v["cashflow_change"]-v["cashflow_closing_cash"],
            }
            if any(abs(residual) > 1 for residual in identities.values()):
                raise ValueError(f"Statement identity failed: {year}/{period}: {identities}")
            checks.append({"report_year":year, "period":period, "residuals_million_try":identities})
            values = {metric:v[metric] for metric in DIRECT}
            values["ebitda"] = v["gross_profit"]+v["administrative_expense"]+v["selling_expense"]+v["depreciation"]
            values["financial_debt"] = sum(v[name] for name in DEBT_LINES)
            values["net_debt"] = values["financial_debt"]-v["cash"]-v["investments_current"]-v["investments_noncurrent"]
            values["shares_outstanding"] = v["paid_capital"]
            for metric,value in values.items():
                pages = str(capture["pages"][metric]) if metric in DIRECT else {
                    "ebitda":"11,13", "financial_debt":"10", "net_debt":"9,10", "shares_outstanding":"10"}[metric]
                note = f"{'Current' if column == 0 else 'Comparative'} column of FY{year} report. "
                note += {"ebitda":"Gross profit + signed administrative/selling expenses + cash-flow depreciation; no separate R&D line displayed.",
                         "financial_debt":"Bank loans and lease debt, all maturities; excludes the separate other-financial-liabilities line.",
                         "net_debt":"Bank and lease debt minus balance-sheet cash and current/noncurrent financial investments.",
                         "shares_outstanding":"Nominal paid capital / TRY1; treasury shares not subtracted. Scaled to nominal share units."}.get(metric,"Original TRY presentation; no currency conversion.")
                observations.append(FinancialObservation(metric=metric, period_end=f"{period}-12-31",
                    period_type="annual" if metric in FLOW_METRICS else "instant", value=value, scale=1_000_000,
                    currency="TRY", unit="shares" if metric == "shares_outstanding" else "money",
                    published_at=evidence[year]["published_at"], retrieved_at="2026-09-15", vintage_verified=True,
                    accounting_basis="THY-TFRS-consolidated-original-TRY-presentation",
                    source_url=url, source_reference=f"{files[year]['path']}; PDF page(s) {pages}; transcription.json FY{year} column {column}; release_evidence.json",
                    notes=note).model_dump())
    destination = root/ORIGINAL_FILE
    pd.DataFrame(observations).to_csv(destination,index=False)
    records = load_observations(destination)
    revisions = []
    for (period,metric), rows in records.groupby(["period_end","metric"]):
        rows = rows.sort_values("published_at")
        for previous,current in zip(rows.to_dict("records"),rows.to_dict("records")[1:]):
            if current["value"] != previous["value"]:
                revisions.append({"period":period.date().isoformat(),"metric":metric,
                    "previous_value":previous["value"],"revised_value":current["value"],
                    "revision_published_at":current["published_at"].date().isoformat()})
    manifest = {"source":"Fintables-hosted original annual statements", "financial_currency":"TRY",
        "retrieved_at":"2026-09-15", "observations":len(records), "vintage_verified":True,
        "normalized_file":ORIGINAL_FILE, "normalized_sha256":sha256(destination), "files":files,
        "transcription_sha256":sha256(folder/"transcription.json"),
        "release_evidence_sha256":sha256(folder/"release_evidence.json"),
        "statement_checks":checks,"comparative_revisions":revisions,
        "timing_policy":"All columns become available at the first stock session close strictly after the containing report's verified publication date.",
        "scope_limit":"Verified annual report vintages, not a complete archive of interim announcements. Original TRY presentation is nominal and exchange-rate-sensitive."}
    write_json(folder/"originals_manifest.json",manifest)
    return manifest


def verify_original_hashes(root: Path) -> None:
    folder = root/"data/raw/fintables/originals"
    manifest = json.loads((folder/"originals_manifest.json").read_text(encoding="utf-8"))
    expected = {item["path"]:item["sha256"] for item in manifest["files"].values()}
    expected.update({ORIGINAL_FILE:manifest["normalized_sha256"],
                     "data/raw/fintables/originals/transcription.json":manifest["transcription_sha256"],
                     "data/raw/fintables/originals/release_evidence.json":manifest["release_evidence_sha256"]})
    for path,digest in expected.items():
        if sha256(root/path) != digest:
            raise ValueError(f"Original source hash mismatch: {path}")
