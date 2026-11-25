"""Create a local implementation archive from explicit project deliverable folders."""

import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from bist_analytics.io import sha256, utc_now, write_json

ROOT = Path(__file__).resolve().parents[1]


def main():
    files = [ROOT/name for name in ["README.md","TASKS.md","IMPLEMENTATION_PLAN.md","pyproject.toml",
        "uv.lock",".gitignore",".env.example","CSE481_Term_Project_BIST_Python_Fintables_MCP_Final.pdf"]]
    exclude = {"__pycache__",".ipynb_checkpoints",".ruff_cache",".pytest_cache",
               "harness_codex_archive"}  # legacy cloud-LLM runs; submission is local-only
    # Working-session notes and their generator are not submission material.
    exclude_files = {"outputs/deliverables/session_summary_2026-11-23.pdf",
                     "scripts/_build_session_summary.py"}
    # training/outputs/ holds HF checkpoints (multi-GB) — zip only the exportable artefacts.
    for directory in ["config","data","docs","notebooks","src","tests","scripts","outputs","output/pdf"]:
        base = ROOT/directory
        if not base.exists():
            continue
        files.extend(path for path in base.rglob("*") if path.is_file()
                     and not exclude.intersection(path.parts) and path.suffix != ".pyc"
                     and path.relative_to(ROOT).as_posix() not in exclude_files)
    training_dir = ROOT/"training"
    if training_dir.exists():
        for path in training_dir.rglob("*"):
            if not path.is_file() or exclude.intersection(path.parts) or path.suffix == ".pyc":
                continue
            # Skip HF checkpoints and the 1.8 GB merged GGUF (shared separately; its hash is
            # still recorded in the manifest below); keep code, dataset and Modelfiles.
            if "outputs" in path.parts or path.suffix == ".gguf":
                continue
            files.append(path)
    files = sorted({path for path in files if path.exists()})
    manifest_path = ROOT/"SUBMISSION_MANIFEST.json"
    external = {path.relative_to(ROOT).as_posix():{"bytes":path.stat().st_size,"sha256":sha256(path),
        "note":"not in archive; provided separately"} for path in sorted(training_dir.glob("*.gguf"))}
    write_json(manifest_path,{"created_at":utc_now(),"version":"0.1.0",
        "status":"submission_local_finetuned_llm_presentation_ready",
        "files":{path.relative_to(ROOT).as_posix():{"bytes":path.stat().st_size,"sha256":sha256(path)} for path in files},
        "external_files":external})
    destination = ROOT/"output/THYAO_Implementation_Package.zip"
    with ZipFile(destination,"w",compression=ZIP_DEFLATED,compresslevel=8) as archive:
        for path in [*files,manifest_path]:
            archive.write(path,path.relative_to(ROOT).as_posix())
    with ZipFile(destination) as archive:
        assert archive.testzip() is None
    print(json.dumps({"archive":str(destination),"files":len(files)+1,"bytes":destination.stat().st_size,"sha256":sha256(destination)}))


if __name__ == "__main__":
    main()
