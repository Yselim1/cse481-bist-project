# Financial data dictionary

| Field | Meaning |
|---|---|
| ticker / metric | Validated THYAO.IS symbol and metric name |
| period_end | Financial period end, not release date |
| period_type | annual, ytd, quarter, ttm, instant or ratio |
| value / scale | Numeric amount times scale; missing stays missing |
| currency / unit | USD or TRY monetary display; money, shares, ratio or fraction. Share rows carry the snapshot currency tag but are not converted. |
| published_at | Verified publication date; empty when unknown |
| assumed_published_at | Explicit modeling date when publication is unknown |
| retrieved_at | Source acquisition date |
| source_url / source_reference | Fintables domain plus local excerpt/evidence reference |
| vintage_verified | True only with verified original-release values and dates |
| accounting_basis / notes | Comparability and source/calculation qualification |
| available_at | Derived first stock session strictly after publication/modeling date; its close decision executes at the following open |

Included annual flows: revenue, gross profit, EBITDA, operating profit, parent net profit and operating/investing/financing cash flows. Balances: cash, debt, net debt, assets, parent equity, current assets, inventory and current liabilities. Nominal share units derive from TRY paid-in capital.

The primary dataset is `fintables_original_observations.csv`: original million-TRY values with scale=1,000,000, converted once on loading. It retains both columns of each original report as distinct dated vintages. TRY valuation uses raw TRY price * nominal units against annual TRY earnings, parent equity and net debt. The separate `fintables_observations.csv` contains earlier USD display values, already expanded from thousands; its valuation uses exact-date USDTRY. USD display values are not original functional-USD accounts. Calculated ratios are not claimed to be Fintables subscription exports.

Growth = current annual flow / positive prior-year flow - 1. ROE/ROA use two period-end averages. Margins divide by positive revenue. Debt/equity uses financial debt / parent equity. Current ratio = current assets / current liabilities; quick ratio subtracts inventory only. Invalid denominators return unavailable.

TTM construction prefers explicit TTM/annual totals, then four standalone quarters, otherwise current YTD + prior annual - comparable prior YTD within one basis. It never sums four cumulative YTD totals. The included study uses annual data.
