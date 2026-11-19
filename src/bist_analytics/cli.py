import argparse
import json

from bist_analytics.config import load_config, project_root
from bist_analytics.data.fintables_import import normalize_fintables
from bist_analytics.data.fundamentals import write_template
from bist_analytics.data.market import get_stock_history
from bist_analytics.io import clean_json


def main():
    parser = argparse.ArgumentParser(description="THYAO academic research pipeline; cached Fintables fundamentals")
    parser.add_argument("--config")
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("fetch",help="Download Yahoo stock/index/FX data")
    fetch.add_argument("--refresh",action="store_true")
    sub.add_parser("import-fintables",help="Normalize captured Fintables tables")
    sub.add_parser("import-originals",help="Validate and normalize reviewed Fintables original reports")
    sub.add_parser("import-tms29",help="Parse and validate reviewed post-TMS 29 Fintables reports")
    sub.add_parser("template",help="Write a blank financial-observation import template")
    run = sub.add_parser("run",help="Reproduce analysis and report offline")
    run.add_argument("--strict",action="store_true",help="Only verified historical financial vintages")
    sub.add_parser("status",help="Show configuration and source readiness")
    args = parser.parse_args()
    root, config = project_root(), load_config(args.config)
    if args.command == "fetch":
        tickers = list(dict.fromkeys([config.ticker, config.benchmark, config.fx_ticker, *config.universe]))
        result = {ticker: len(get_stock_history(ticker, str(config.market_start), str(config.evaluation_end),
                  root/"data/raw/market", args.refresh)) for ticker in tickers}
    elif args.command == "import-fintables":
        result = normalize_fintables(root)
    elif args.command == "import-originals":
        from bist_analytics.data.originals import normalize_originals
        result = normalize_originals(root)
    elif args.command == "import-tms29":
        from bist_analytics.data.tms29 import normalize_tms29
        result = normalize_tms29(root)
    elif args.command == "template":
        path = root/"data/templates/fintables_observations.csv"
        write_template(path)
        result = {"template":str(path)}
    elif args.command == "run":
        from bist_analytics.pipeline import run_pipeline
        if args.strict:
            config = config.model_copy(update={"vintage_policy":"verified_only"})
        result = run_pipeline(root,config)
    else:
        result = {"config":config.model_dump(mode="json"),"fundamentals_present":(root/config.fundamentals_file).exists()}
    print(json.dumps(clean_json(result),indent=2,allow_nan=False))


if __name__ == "__main__":
    main()
