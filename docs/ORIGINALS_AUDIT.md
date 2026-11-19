# Original financial statement audit

**Completed 15 September 2026.** The four user-downloaded Fintables attachments supply **136 verified observations**: 17 metrics, two year columns, four report vintages. They cover FY2020-2024. No company financial values were imported from any other provider. KAP supplies publication metadata only where needed.

## Receipt and publication

| Report | PDF pages | Published | Evidence | File |
| --- | --- | --- | --- | --- |
| 2021 | 98 | 2022-03-01 | [release](https://www.kap.org.tr/tr/Bildirim/1005607) | THYAO_2021_original.pdf |
| 2022 | 99 | 2023-03-01 | [release](https://www.kap.org.tr/tr/Bildirim/1118481) | THYAO_2022_original.pdf |
| 2023 | 101 | 2024-04-03 | [release](https://fintables.com/borsa-haber-akisi/ca09fa43-446f-4c7e-8593-43eebea89e1b) | THYAO_2023_original.pdf |
| 2024 | 101 | 2025-02-28 | [release](https://www.kap.org.tr/tr/Bildirim/1396940) | THYAO_2024_original.pdf |

The original bytes remain in `data/raw/fintables/originals/`. `originals_manifest.json` records each Fintables URL, SHA-256, PDF payload hash, page count and publication evidence. The 2023 release is evidenced on Fintables itself; the other three original report notices were checked in KAP's browser interface. Auditor or board approval dates alone were not substituted for publication dates.

The downloaded files contain a 27-byte Java byte-array envelope before `%PDF-`. The importer recognizes only that exact envelope and validates its declared payload length. It never executes Java or deserializes objects. Original receipts are unchanged. Standard PDF copies in `output/pdf/originals/` contain the exact original PDF payload bytes, with only the wrapper removed; they open directly in a PDF reader. `scripts/extract_original_pdfs.py` verifies their hashes against the original manifest. Page counts are 98, 99, 101 and 101.

## Transcription and reconciliation

For each report, **PDF pages 9, 10, 11 and 13** (printed pages 1, 2, 3 and 5) were rendered and visually read in full. They contain assets, liabilities/equity, income and cash flow respectively. `transcription.json` keeps the current and comparative columns, page mapping and all debt/EBITDA components. Monetary inputs are millions of TRY and become full TRY amounts exactly once. Parent-attributable income is used, rather than the nearby consolidated profit line.

Five independent statement identities were checked for all eight columns: assets equal liabilities plus total equity; asset subtotals; revenue less cost of sales equals gross profit; three cash-flow categories equal net cash change; opening cash plus change equals closing cash. **All 40 residuals are zero.** Negative minority equity is preserved where printed. The balance-sheet cash and cash-flow cash definitions can differ; neither is overwritten to force equality.

Derived definitions:

- EBITDA = gross profit + signed administrative expense + signed selling expense + depreciation/amortization adjustment. No separate R&D row is displayed. It is not EBITDAR or an airline-adjusted earnings measure.
- Financial debt = related/unrelated bank borrowing and lease debt, including current portions of long-term liabilities. Other financial liabilities are a separate excluded line, matching the chosen borrowing definition.
- Net debt = financial debt - balance-sheet cash - current financial investments - noncurrent financial investments. This formula does not imply all investments are immediately liquid.
- Nominal shares = paid capital / TRY1: 1.38 billion units. Treasury shares are not subtracted.

## Currency decision

The originals present financial statements in **millions of TRY**, although THY's functional currency is USD. The currency notes state that income is translated using monthly average rates; the balance sheet uses closing rates and historical equity translation. One annual average rate cannot exactly recover functional-USD income. The final study therefore uses the original TRY presentation, without reverse conversion. Valuation combines raw TRY stock price and nominal shares with TRY earnings/equity/debt.

Nominal TRY sales growth is **not** inflation-adjusted growth or functional-USD growth. Currency translation also affects return on average equity/assets. The earlier Fintables-displayed-USD study remains in `outputs/retrospective/`, with its own `config/retrospective.yaml` and original unverified observations. The source/currency correction happened after those earlier results were seen. The strategy thresholds were held fixed; this is not a controlled comparison isolating one data correction, nor a pristine blind 2025 test.

## Dated comparatives

| metric | period | previous_value | revised_value | revision_published_at |
| --- | --- | --- | --- | --- |
| investing_cash_flow | 2022-12-31 | -26494000000.0 | -26760000000.0 | 2024-04-03 |
| current_assets | 2023-12-31 | 253043000000.0 | 251895000000.0 | 2025-02-28 |
| current_liabilities | 2023-12-31 | 267956000000.0 | 266808000000.0 | 2025-02-28 |
| total_assets | 2023-12-31 | 1050091000000.0 | 1048943000000.0 | 2025-02-28 |

All amounts in the revision table are full TRY. FY2020 figures first enter with the containing FY2021 report in March 2022. Later comparative revisions enter only after their containing report's publication. They never overwrite earlier decisions. FY2023's revised asset balance is used in FY2024's ROA average only after the FY2024 release.

The source policy uses the first stock-session **close strictly after the release date**, even for pre-open releases. The close decision then executes at the following open. Annual snapshot availability is 2022-03-02, 2023-03-02, 2024-04-04 and 2025-03-03. This deliberately conservative convention is consistent across reports. FY2025 annual results were released in 2026 and are unnecessary for trading through 2025.

## Scope of verification

The original annual source gate is closed. This is an annual-refresh strategy, not a complete archive of interim disclosures. The unchanged 460-day freshness rule allows all 749 evaluation sessions; 710 of 749 sessions have all five score inputs. Early FY2021 profit-growth comparison is unavailable because FY2020 was a loss. Missing values remain unavailable. Original-source hashes are checked every time the pipeline runs.

Source verification does not establish a profitable future strategy, perfect provider prices, executable whole-lot trading, or an unbiased stock-selection experiment. These remain limitations, not unresolved file downloads.
