"""Compare an offline rerun in the calling interpreter with the delivered snapshot."""

import importlib.metadata
import json
import platform
import subprocess
import sys

import pandas as pd

from bist_analytics.config import load_config, project_root
from bist_analytics.io import clean_json, sha256, utc_now, write_json
from bist_analytics.pipeline import build_analysis, evaluate


def main():
    root = project_root()
    records = []
    for args in [["-m","pytest"],["-m","ruff","check","src","tests","scripts"]]:
        result = subprocess.run([sys.executable,*args],cwd=root,capture_output=True,text=True,timeout=120)
        records.append({"command":[sys.executable,*args],"exit_code":result.returncode,
                        "stdout":result.stdout,"stderr":result.stderr})
        if result.returncode:
            raise RuntimeError(result.stdout+result.stderr)
    for policy in ["retrospective","verified_only"]:
        cfg = load_config(root/"config/retrospective.yaml") if policy == "retrospective" else load_config()
        analysis = build_analysis(root,cfg)
        folder = root/"outputs"/policy
        rebuilt, saved_features = analysis.features.copy(), pd.read_parquet(folder/"features.parquet")
        # Parquet can store all-null dates at millisecond rather than second precision.
        # Normalize date precision only; dates, nulls and all financial values must agree.
        for column in rebuilt.select_dtypes(include=["datetime"]).columns:
            rebuilt[column] = rebuilt[column].astype("datetime64[ns]")
            saved_features[column] = saved_features[column].astype("datetime64[ns]")
        pd.testing.assert_frame_equal(rebuilt,saved_features,check_freq=False,check_exact=True)
        metrics,results,_ = evaluate(analysis)
        assert clean_json(metrics) == json.loads((folder/"performance.json").read_text()), policy
        annual = {str(year):clean_json(evaluate(analysis,f"{year}-01-01",f"{year+1}-01-01")[0]) for year in [2023,2024,2025]}
        assert annual == json.loads((folder/"annual_evaluations.json").read_text()), policy
        for mode,result in results.items():
            saved = pd.read_csv(folder/f"{mode}_daily.csv",parse_dates=["date"]).set_index("date")
            pd.testing.assert_frame_equal(result.daily,saved,check_dtype=False,check_freq=False,rtol=1e-11,atol=1e-9)
        records.append({"policy":policy,"features":"all_equal","performance":"exact_json_equal",
            "annual_performance":"exact_json_equal","daily_ledgers":"equal_within_1e-9_TRY",
            "run_id":json.loads((folder/"run_manifest.json").read_text())["run_id"]})
    proof = {"verified_at":utc_now(),"python":sys.version,"interpreter":sys.executable,
        "platform":platform.platform(),"network_used":False,"lock_sha256":sha256(root/"uv.lock"),
        "packages":{name:importlib.metadata.version(name) for name in ["mcp","pandas","numpy","yfinance","pytest","uv"]},
        "checks":records}
    write_json(root/"outputs/verification/reproduction.json",proof)
    print("Offline reproduction passed in",sys.executable)


if __name__ == "__main__":
    main()
