"""Predeclared development/validation variants; never selects a best setting."""

from dataclasses import replace

import pandas as pd

from bist_analytics.analysis.scoring import add_scores
from bist_analytics.config import StrategyConfig, project_root
from bist_analytics.io import write_json
from bist_analytics.pipeline import build_analysis, evaluate


def main():
    analysis = build_analysis()
    variants = {"baseline":{},"zero_costs":{"commission_bps":0,"slippage_bps":0},
                "commission_20bps":{"commission_bps":20},"entry_065":{"entry_score":.65},
                "entry_075":{"entry_score":.75},"debt_limit_2x":{"debt_ebitda_threshold":2}}
    results = []
    for name,changes in variants.items():
        strategy_changes = {k:v for k,v in changes.items() if k in StrategyConfig.model_fields}
        config_changes = {k:v for k,v in changes.items() if k not in strategy_changes}
        config = analysis.config.model_copy(update={**config_changes,"strategy":analysis.config.strategy.model_copy(update=strategy_changes)})
        adjusted = replace(analysis,config=config,features=add_scores(analysis.features,config.strategy))
        performance,_,_ = evaluate(adjusted,"2023-01-01","2025-01-01")
        results.append({"variant":name,"period":"2023–2024 only",**performance["combined"]})
    folder = project_root()/"outputs"/analysis.config.vintage_policy
    pd.DataFrame(results).to_csv(folder/"sensitivity.csv",index=False)
    write_json(folder/"sensitivity.json",{"predeclared_in":"docs/DECISIONS.md","selection":"none; baseline unchanged","results":results})
    print(pd.DataFrame(results)[["variant","cumulative_return","maximum_drawdown","closed_trades"]].to_string(index=False))


if __name__ == "__main__":
    main()
