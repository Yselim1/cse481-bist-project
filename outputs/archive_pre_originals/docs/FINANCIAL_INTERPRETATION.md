# Reading the financial results

This explains the **FY2024 Fintables display values available under the modeled date policy at 31 December 2025**. It is an interpretation of the captured retrospective dataset. Values and formulas are in `outputs/retrospective/financial_analysis.csv`, `ratio_analysis.csv`, `data/raw/fintables/` and DATA_SOURCES.md. Financial amounts below are USD billions; stock returns use nominal TRY.

## Earnings and cash generation

Revenue of 22.74 rose 6.82%, while derived EBITDA of 4.16 fell 14.66% and parent net profit of 3.46 fell 49.73%. In this comparison, higher revenue did not translate into higher earnings. EBITDA margin is 18.28% and net margin 15.21%. The score therefore awards neither growth point. The underlying accounts would be needed to attribute the decline to specific operating, tax or translation causes; the aggregate table alone cannot do that.

Operating cash flow of 4.77 exceeds parent net income of 3.46. This supports a stronger cash-generation picture than looking only at earnings, although working-capital movements and noncash accounting items need detailed reconciliation. Investing cash flow is a **positive 0.31 net inflow**. That does not mean capital spending was absent: disposals and financial-investment movements can offset outflows in this aggregate line. Financing cash flow is a **2.30 net outflow**. Cash-flow signs and balance-sheet cash should not be equated without the opening balance, FX effects and detailed reconciliation.

## Liquidity and leverage

Cash is 2.73, financial debt 13.91, and net debt 6.72 after subtracting cash plus the current and noncurrent financial investments included in the declared Fintables formula. Net debt is therefore not simply debt minus cash. Net debt/EBITDA of 1.62 passes both the baseline 4x rule and the 2x sensitivity condition at this final snapshot. Debt/equity is 0.72.

Current ratio 1.01 places current assets only slightly above current liabilities. Quick ratio 0.94 falls below one after inventory is removed. These measures indicate a limited balance-sheet liquidity cushion under the chosen definitions; they do not establish a payment default or predict insolvency. The simplified quick ratio does not remove all potentially illiquid current items such as prepayments. Airline lease obligations and the timing of cash receipts need context beyond these ratios.

## Profitability and valuation

ROE is 19.85%, just below the declared 20% score threshold; ROA is 9.17%. Both use parent-attributable profit and the stated average denominator, so they may differ from vendor ratios using total consolidated profit or ending balances.

P/E 2.49, P/B 0.45 and EV/EBITDA 3.69 combine the 31 December 2025 raw stock close and same-day FX with the latest modeled annual financial inputs. They are not ratios at the FY2024 reporting date. A low multiple alone does not establish undervaluation: accounting gains, currency translation, revised inputs, risk expectations and limited comparability can matter. The score uses the company's prior valid P/E median, not an unsupported peer or intrinsic-value estimate.

## Why the combined strategy was often inactive

At the final stock date, only leverage earns a fundamental point: F=1/5. Technical points are RSI and support: T=2/5. The combined score is 0.32, and the trend entry filter fails. HOLD while flat means remain in cash. It is not a buy/sell recommendation and it does not describe a live portfolio.

Over 2023-2025, the combined simulation returned 26.24% with -10.81% maximum drawdown, eight closed trades and 20.03% exposure. The technical simulation returned 61.19%; stock buy-and-hold 92.73%; BIST100 102.24%. Lower exposure helps explain both the reduced drawdown and missed appreciation. The experiment changes a group of fundamental entry/exit rules; it does not prove which individual ratio caused the performance difference.

The fixed-execution cost-free combined counterfactual returned 29.31%, compared with 26.24% net. That isolates modeled transaction costs on the same trade dates. The separate zero-cost strategy rerun can change stop timing and should not be used as the fee-only effect.

## What remains unresolved

All captured financial values are current table vintages, and four annual release dates are assumed. Strict mode excludes all observations and remains in cash. Neither profitable retrospective results nor passing causal-code tests prove that these exact accounts were known at the historical decision dates. Follow the original-Fintables evidence steps in ACCEPTANCE.md before asserting a point-in-time result.
