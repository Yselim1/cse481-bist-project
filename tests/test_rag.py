from bist_analytics.rag import KnowledgeBase, tokenize

DOCS = [
    {"doc_id": "kap:X:a", "title": "Air Europa talks", "text": "nonbinding investment talks",
     "source_type": "kap_disclosure", "published_at": "2025-06-20T21:57:00+03:00",
     "tickers": ["THYAO.IS"]},
    {"doc_id": "doc:decisions:01", "title": "Decisions", "text": "stop loss 8% max holding 40 sessions",
     "source_type": "methodology", "published_at": None, "tickers": []},
    {"doc_id": "universe:AKBNK.IS", "title": "AKBNK", "text": "banking sector peer GARAN",
     "source_type": "universe_metadata", "published_at": None, "tickers": ["AKBNK.IS"]},
]


def test_tokenize_drops_stopwords():
    assert tokenize("The stop-loss of THYAO") == ["stop", "loss", "thyao"]


def test_search_ranks_relevant_doc_first():
    hits = KnowledgeBase(DOCS).search("stop loss holding sessions")
    assert hits[0].doc_id == "doc:decisions:01"


def test_point_in_time_filter_hides_future_documents():
    kb = KnowledgeBase(DOCS)
    assert [h.doc_id for h in kb.search("Air Europa", as_of="2025-12-31")] == ["kap:X:a"]
    assert kb.search("Air Europa", as_of="2025-06-01") == []


def test_ticker_filter_excludes_other_tickers_docs():
    hits = KnowledgeBase(DOCS).search("banking sector", ticker="THYAO.IS")
    assert all("AKBNK.IS" not in h.tickers for h in hits)


def test_search_is_deterministic():
    kb = KnowledgeBase(DOCS)
    assert [h.as_dict() for h in kb.search("sector")] == [h.as_dict() for h in kb.search("sector")]


def test_committed_kb_loads_and_has_sources():
    kb = KnowledgeBase.load()
    assert kb.documents
    for d in kb.documents:
        assert d["source_path"] or d["source_url"]
        assert len(d["sha256"]) == 64
