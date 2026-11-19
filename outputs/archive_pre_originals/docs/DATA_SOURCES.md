# Data sources and provenance

## Financial values: Fintables only

Captured manually through the authorized, signed-in browser on 15 September 2026. Local TSVs preserve selected Turkish row labels and formatted values. Parenthetical section names disambiguate duplicated balance-sheet labels. Monetary table units are **thousands** of the displayed currency; normalize once by multiplying by 1,000.

| File | Source | Coverage |
|---|---|---|
| balance_annual_usd.tsv | [Balance sheet](https://fintables.com/sirketler/THYAO/finansal-tablolar/bilanco?period=12&type=&currency=usd&mode=adjusted) | 2020–2025 year ends |
| income_annual_usd.tsv | [Income statement](https://fintables.com/sirketler/THYAO/finansal-tablolar/gelir-tablosu?period=12&type=&currency=usd&mode=adjusted) | 2020–2025 full years |
| cashflow_annual_usd.tsv | [Cash flow](https://fintables.com/sirketler/THYAO/finansal-tablolar/nakit-akim-tablosu?period=12&type=&currency=usd&mode=adjusted) | 2020–2025 full years |
| capital_annual_try.tsv | [TRY balance sheet](https://fintables.com/sirketler/THYAO/finansal-tablolar/bilanco?period=12&type=&currency=try&mode=adjusted) | 2020–2025 nominal capital |

The files reside in `data/raw/fintables`. The import command records SHA-256 hashes. Values were captured from the displayed value element, excluding the adjacent percentage-change badge. Annual periods were explicitly selected. Monetary flow values are annual totals, not standalone fourth quarters. The 1,380,000 thousand TRY capital was independently read for all six years. Fintables' market-cap formula uses nominal capital times share price; we model 1.38 billion TRY-1 nominal units and disclose that treasury-share adjustments are not made.

EBITDA and net debt are calculated from these inputs using [Fintables' published formulas](https://fintables.com/arastirma/yazilar/degerleme-analizi-101/fdfavok). Calculated growth, ratios and scores are project outputs; no subscription-only ratio values are invented or claimed to have been exported. ROE uses average parent equity and ROA average total assets, with parent-attributable net income. Quick ratio excludes inventory only; it can overstate liquidity where prepayments are material.

### Release and vintage limitations

- [Fintables' 2023 financial-report notice](https://fintables.com/borsa-haber-akisi/ca09fa43-446f-4c7e-8593-43eebea89e1b) is dated **3 April 2024, 19:00**, for the 2023 fourth-quarter/year-end results.
- [Fintables' 2025 financial-report notice](https://fintables.com/borsa-haber-akisi/ac19e15a-2370-4ed9-86c7-0a67b6746841/thyao-finansal-rapor) is dated **4 March 2026, 18:55**. The [results announcement](https://fintables.com/borsa-haber-akisi/76b80e73-c31d-4ac7-96cd-c75d172bae3b/thyao-ozel-durum-aciklamasi-genel) at 19:08 confirms the annual results were disclosed.
- Other annual release dates are unknown in this dataset. `published_at` stays empty; `assumed_published_at` explicitly records 30 June of the following year. This is not an actual publication date.
- All table observations have `vintage_verified=false`. The original release notices do not verify every currently displayed financial value. Strict mode excludes all of them. Retrospective mode permits them with warnings. Results therefore remain exploratory and may contain revision bias despite causal code and delayed use.
- No original THY/KAP financial values from a different service were imported. Paid subscription controls and browser protection were not bypassed; the user completed the robot check and sign-in.

## Market data

Selection-date BIST100 membership was verified in the [Fintables XU100 constituent table](https://fintables.com/endeksler/XU100), which contains THYAO, on 15 September 2026. `data/raw/fintables/membership.json` records this observation; it does not establish membership throughout the historical test window.

Yahoo via `yfinance.download`, daily interval, explicit `auto_adjust=False`, actions enabled and repair disabled. Requests, retrieval timestamps, installed provider version and file hashes are in adjacent `.metadata.json` files under `data/raw/market`.

- `THYAO.IS`: Turkish Airlines equity, TRY prices, volume and actions.
- `XU100.IS`: BIST 100 **price index**, not a total-return index or a tradeable asset.
- `TRY=X`: USD/TRY, TRY per USD. Exact-date positive close only is used for valuation conversion. Inconsistent provider FX OHLC ranges are counted; the unused bars are retained for audit.

Requested market window is 2021-01-01 to exclusive 2026-01-01. Stock-only dates were 2021-04-02 and Christmas Day in 2023, 2024 and 2025. Index-only date was 2024-04-09. The run's quality report preserves calendar differences. No missing market price is fabricated.

Raw files are for the user's academic project. Review provider/instructor redistribution rules before publishing datasets publicly. No public upload is performed by the pipeline.
