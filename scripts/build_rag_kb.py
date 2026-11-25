"""Build ``rag/knowledge_base.json`` from documents already committed to the repository.

Every document records where it came from (``source_type``, ``source_path`` and/or
``source_url``), when it was published (point-in-time filter key), when it was
collected, and a SHA-256 of its text. Nothing is fetched from the network.

    .\\.venv\\Scripts\\python.exe scripts/build_rag_kb.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "rag" / "knowledge_base.json"
METHOD_DOCS = {
    "docs/DECISIONS.md": "methodology",
    "docs/DATA_DICTIONARY.md": "metric_definition",
    "docs/FINANCIAL_INTERPRETATION.md": "methodology",
    "docs/DATA_SOURCES.md": "data_provenance",
}
CHUNK_WORDS = 220


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _git_date(path: str) -> str | None:
    """Date the file was last committed — used as the methodology doc's publication date."""
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%cs", "--", path], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout.strip()
        return out or None
    except (OSError, subprocess.CalledProcessError):
        return None


def _doc(doc_id: str, title: str, text: str, source_type: str, *, source_path: str | None = None,
         source_url: str | None = None, published_at: str | None = None,
         tickers: list[str] | None = None, sector: str | None = None,
         retrieved_at: str | None = None) -> dict:
    text = re.sub(r"\s+", " ", text).strip()
    return {"doc_id": doc_id, "title": title, "text": text, "source_type": source_type,
            "source_path": source_path, "source_url": source_url, "published_at": published_at,
            "retrieved_at": retrieved_at, "tickers": tickers or [], "sector": sector,
            "sha256": _sha(text)}


def kap_documents(sector_of: dict[str, str]) -> list[dict]:
    docs = []
    for path in sorted((ROOT / "data/raw/kap").glob("*_context_events.csv")):
        ticker = path.name.split("_")[0].upper() + ".IS"
        rel = path.relative_to(ROOT).as_posix()
        with path.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                docs.append(_doc(
                    f"kap:{ticker}:{row['event_id']}", f"{ticker} — {row['title']}",
                    f"{row['title']}. {row['summary']} Category: {row['category']}. "
                    f"Published {row['published_at']}. Evidence status: {row['evidence_status']}.",
                    "kap_disclosure", source_path=rel, source_url=row.get("source_url") or None,
                    published_at=row["published_at"], tickers=[ticker],
                    sector=sector_of.get(ticker)))
    return docs


def _chunks(markdown: str) -> list[tuple[str, str]]:
    """Split on headings, then pack paragraphs into ~CHUNK_WORDS-word chunks."""
    sections: list[tuple[str, list[str]]] = [("", [])]
    for block in re.split(r"\n\s*\n", markdown):
        block = block.strip()
        if not block:
            continue
        heading = re.match(r"^(#{1,4})\s+(.*)$", block.splitlines()[0])
        if heading:
            sections.append((heading.group(2).strip(), []))
            rest = "\n".join(block.splitlines()[1:]).strip()
            if rest:
                sections[-1][1].append(rest)
        else:
            sections[-1][1].append(block)
    out = []
    for heading, paragraphs in sections:
        buf: list[str] = []
        for p in paragraphs:
            buf.append(p)
            if sum(len(x.split()) for x in buf) >= CHUNK_WORDS:
                out.append((heading, "\n\n".join(buf)))
                buf = []
        if buf:
            out.append((heading, "\n\n".join(buf)))
    return out


def method_documents() -> list[dict]:
    docs = []
    for rel, source_type in METHOD_DOCS.items():
        path = ROOT / rel
        if not path.exists():
            continue
        published = _git_date(rel)
        stem = path.stem.lower()
        for i, (heading, text) in enumerate(_chunks(path.read_text(encoding="utf-8")), start=1):
            title = f"{path.stem}: {heading}" if heading else path.stem
            docs.append(_doc(f"doc:{stem}:{i:02d}", title, text, source_type, source_path=rel,
                             published_at=None, retrieved_at=published))
    return docs


def universe_documents() -> tuple[list[dict], dict[str, str]]:
    rel = "config/bist100_universe.yaml"
    meta = yaml.safe_load((ROOT / rel).read_text(encoding="utf-8"))
    sector_of = {t["ticker"]: t["sector"] for t in meta.get("tickers", [])}
    notes = {t["ticker"]: t.get("note", "") for t in meta.get("tickers", [])}
    # The live-question universe extends the 10-ticker sample with more sector pairs.
    live_rel = "config/universe_live.yaml"
    live = yaml.safe_load((ROOT / live_rel).read_text(encoding="utf-8"))
    for ticker, sector in live.get("sector_map", {}).items():
        sector_of.setdefault(ticker, sector)
    docs = []
    for ticker, sector in sector_of.items():
        peers = [p for p, s in sector_of.items() if s == sector and p != ticker]
        in_sample = ticker in notes
        source = rel if in_sample else live_rel
        docs.append(_doc(
            f"universe:{ticker}", f"{ticker} universe membership",
            f"{ticker} belongs to the {sector} sector of the research universe"
            f"{'' if in_sample else ' (live-question extension; prices only, no fundamentals)'}. "
            f"Sector peers: {', '.join(peers) or 'none'}. {notes.get(ticker, '')} "
            f"Benchmark index: {meta.get('benchmark')}.",
            "universe_metadata", source_path=source, tickers=[ticker], sector=sector,
            retrieved_at=str(meta.get("selection_date"))))
    return docs, sector_of


def provenance_documents() -> list[dict]:
    rel = "data/raw/fintables/manifest.json"
    path = ROOT / rel
    if not path.exists():
        return []
    m = json.loads(path.read_text(encoding="utf-8"))
    text = (f"Fundamental statements were imported from {m.get('source')} with release policy "
            f"{m.get('release_policy')}. Formula source: {m.get('formula_source')}. "
            f"Vintage verified: {m.get('vintage_verified')}. Observations: {m.get('observations')}. "
            f"Retrieved at {m.get('retrieved_at')}.")
    return [_doc("provenance:fintables", "Fintables fundamentals provenance", text,
                 "data_provenance", source_path=rel, retrieved_at=str(m.get("retrieved_at")))]


def build() -> dict:
    universe, sector_of = universe_documents()
    documents = kap_documents(sector_of) + method_documents() + universe + provenance_documents()
    ids = [d["doc_id"] for d in documents]
    assert len(ids) == len(set(ids)), "duplicate doc_id"
    return {"version": 1, "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "retrieval": {"method": "BM25 (k1=1.5, b=0.75)", "module": "src/bist_analytics/rag.py",
                          "point_in_time_field": "published_at"},
            "document_count": len(documents),
            "source_counts": {s: sum(d["source_type"] == s for d in documents)
                              for s in sorted({d["source_type"] for d in documents})},
            "documents": documents}


def main() -> None:
    kb = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(kb, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"path": OUT.relative_to(ROOT).as_posix(), "documents": kb["document_count"],
                      "source_counts": kb["source_counts"]}, indent=2))


if __name__ == "__main__":
    main()
