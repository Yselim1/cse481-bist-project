"""Small offline retrieval layer over ``rag/knowledge_base.json``.

Pure-Python BM25 (Okapi, k1=1.5, b=0.75) — no embeddings, no network, no new
dependencies, and fully deterministic (ties broken by ``doc_id``). Documents carry a
``published_at`` timestamp; queries with ``as_of`` only see documents published on or
before that date, so retrieval obeys the same point-in-time rule as the price and
fundamental tools.

The knowledge base is built by ``scripts/build_rag_kb.py`` from files already in the
repository (KAP disclosures, methodology docs, universe metadata, data provenance).
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from bist_analytics.config import project_root

KB_RELATIVE_PATH = "rag/knowledge_base.json"
_TOKEN = re.compile(r"[a-zçğıöşü0-9]+", re.IGNORECASE)
_STOP = frozenset(
    "a an and are as at be by for from has have in is it its of on or that the this to was "
    "were will with what which who how does do did than then into over under not no".split())


def tokenize(text: str) -> list[str]:
    return [t for t in (m.group(0).lower() for m in _TOKEN.finditer(text or ""))
            if t not in _STOP and len(t) > 1]


@dataclass(frozen=True)
class Hit:
    doc_id: str
    score: float
    title: str
    text: str
    source_type: str
    source: str
    published_at: str | None
    tickers: tuple[str, ...]

    def as_dict(self) -> dict:
        return {"doc_id": self.doc_id, "score": round(self.score, 4), "title": self.title,
                "text": self.text, "source_type": self.source_type, "source": self.source,
                "published_at": self.published_at, "tickers": list(self.tickers)}


class KnowledgeBase:
    def __init__(self, documents: list[dict], k1: float = 1.5, b: float = 0.75) -> None:
        self.documents = documents
        self.k1, self.b = k1, b
        self._tf = [Counter(tokenize(f"{d.get('title', '')} {d.get('text', '')} "
                                     f"{' '.join(d.get('tickers') or [])} {d.get('sector') or ''}"))
                    for d in documents]
        self._len = [sum(tf.values()) for tf in self._tf]
        self._avg = (sum(self._len) / len(self._len)) if self._len else 0.0
        df: Counter = Counter()
        for tf in self._tf:
            df.update(tf.keys())
        n = len(documents)
        self._idf = {term: math.log(1 + (n - f + 0.5) / (f + 0.5)) for term, f in df.items()}

    @classmethod
    def load(cls, path: Path | None = None) -> KnowledgeBase:
        path = path or Path(project_root()) / KB_RELATIVE_PATH
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(payload["documents"])

    def _score(self, index: int, terms: list[str]) -> float:
        tf, length = self._tf[index], self._len[index]
        score = 0.0
        for term in terms:
            f = tf.get(term)
            if not f:
                continue
            denom = f + self.k1 * (1 - self.b + self.b * length / (self._avg or 1.0))
            score += self._idf.get(term, 0.0) * f * (self.k1 + 1) / denom
        return score

    def search(self, query: str, *, top_k: int = 4, as_of: str | None = None,
               ticker: str | None = None) -> list[Hit]:
        terms = tokenize(query)
        if ticker:
            terms += tokenize(ticker.replace(".IS", ""))
        if not terms:
            return []
        results: list[tuple[float, str, int]] = []
        for i, doc in enumerate(self.documents):
            published = doc.get("published_at")
            if as_of and published and published[:10] > as_of[:10]:
                continue  # point-in-time: never surface documents from the future
            tickers = doc.get("tickers") or []
            if ticker and tickers and ticker not in tickers:
                continue  # ticker-scoped docs only match their own ticker
            score = self._score(i, terms)
            if score > 0:
                results.append((score, doc["doc_id"], i))
        results.sort(key=lambda r: (-r[0], r[1]))
        hits = []
        for score, _, i in results[:max(1, top_k)]:
            d = self.documents[i]
            hits.append(Hit(d["doc_id"], score, d.get("title", ""), d.get("text", ""),
                            d.get("source_type", ""), d.get("source_url") or d.get("source_path", ""),
                            d.get("published_at"), tuple(d.get("tickers") or [])))
        return hits


@lru_cache(maxsize=1)
def default_kb() -> KnowledgeBase:
    return KnowledgeBase.load()
