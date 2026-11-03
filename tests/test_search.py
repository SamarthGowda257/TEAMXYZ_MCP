"""Hybrid search: helpers, fallback path, patient isolation, and the Gemini client (network mocked).

The Postgres legs (full-text, trigram, pgvector) are exercised end to end in CI by scripts/smoke_mcp.py and
scripts/eval_search.py against a pgvector database.
"""

import os
import tempfile

os.environ.setdefault("MCP_BEARER_TOKEN", "test-token")
os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "test.db"))
os.environ.pop("DATABASE_URL", None)

import pytest  # noqa: E402

from app import config, embeddings, search, seed  # noqa: E402
from app.services import records, ref, support  # noqa: E402

SHAN = ("+919845000001", "1959-03-04")
ARJUN = ("+919845000002", "1992-06-15")


@pytest.fixture(scope="module", autouse=True)
def data():
    seed.reset(verbose=False)
    ref.load()
    search.sync_kb()
    search.sync()


def test_words_drop_filler_and_keep_terms():
    assert search.words("Did I ask you about my knee MRI last week?") == ["knee", "mri"]
    assert search.words("need a cardiolgy check up", frozenset({"check"})) == ["cardiolgy"]
    assert search.codes("anything on wn 48213 or LR-20931?") == ["WN-48213", "LR-20931"]


def test_memory_finds_exact_booking_code():
    r = support.search_interactions(*SHAN, query="anything about WN-48213?")
    assert r.ok and "WN-48213" in r.message


def test_memory_never_crosses_patients():
    r = support.search_interactions(*ARJUN, query="WN-48213")
    assert r.ok and "WN-48213" not in r.message


def test_memory_requires_identity():
    r = support.search_interactions(SHAN[0], "1960-01-01", query="knee")
    assert not r.ok


def test_new_note_is_searchable_immediately():
    support.save_note(SHAN[0], "Asked whether the hospital has a dietitian for diabetic meal plans.", topics="diet")
    r = support.search_interactions(*SHAN, query="dietitian")
    assert r.ok and "dietitian" in r.message


def test_hospital_info_answers_free_text_question():
    r = records.hospital_info("can my son stay overnight with me in the ward")
    assert r.ok and "attendant" in r.message.lower()


def test_hospital_info_keeps_exact_topics():
    r = records.hospital_info("parking")
    assert r.ok and r.data["topic"] == "parking"


def test_department_red_flags_stay_deterministic():
    r = records.suggest_department("sudden chest pain and sweating")
    assert r.ok and r.data["emergency"] is True


def test_kb_has_all_sources():
    refs = {d["ref"].split(":")[1] for d in __import__("app.kb", fromlist=["documents"]).documents()}
    assert {"info", "dept", "proc", "ins", "faq"} <= refs


# ------------------------------------------------------------------ Gemini client (no network)
class FakeResp:
    def __init__(self, status, payload):
        self.status_code, self._p = status, payload
        self.text = str(payload)

    def json(self):
        return self._p


@pytest.fixture
def gemini(monkeypatch):
    monkeypatch.setattr(config, "EMBEDDINGS_PROVIDER", "gemini")
    monkeypatch.setattr(config, "EMBEDDINGS_API_KEY", "k-test")
    monkeypatch.setattr(config, "EMBED_DAILY_BUDGET", 1000)
    monkeypatch.setattr(embeddings, "_breaker_until", 0.0)
    calls = []

    def post(url, json=None, headers=None, timeout=None):
        calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return FakeResp(200, {"embeddings": [{"values": [3.0, 4.0] + [0.0] * (config.EMBEDDINGS_DIM - 2)}
                                             for _ in json["requests"]]})
    import httpx
    monkeypatch.setattr(httpx, "post", post)
    return calls


def test_gemini_request_shape_and_normalisation(gemini):
    out = embeddings.embed_documents(["a", "b"])
    assert len(out) == 2 and abs(out[0][0] - 0.6) < 1e-9 and abs(out[0][1] - 0.8) < 1e-9   # unit length
    req = gemini[0]
    assert req["url"].endswith("/models/gemini-embedding-001:batchEmbedContents")
    assert req["headers"]["x-goog-api-key"] == "k-test"
    r0 = req["json"]["requests"][0]
    assert r0["taskType"] == "RETRIEVAL_DOCUMENT" and r0["outputDimensionality"] == 768


def test_query_embedding_is_cached(gemini):
    q = "unique question for cache test 1234"
    assert embeddings.embed_query(q) is not None
    assert embeddings.embed_query(q) is not None
    assert len(gemini) == 1 and gemini[0]["json"]["requests"][0]["taskType"] == "RETRIEVAL_QUERY"
    assert gemini[0]["timeout"] == config.EMBEDDINGS_TIMEOUT


def test_quota_error_opens_breaker(gemini, monkeypatch):
    import httpx
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResp(429, {"error": {"message": "quota"}}))
    assert embeddings.embed_documents(["x"]) is None
    assert embeddings.status()["breaker_open"] is True
    assert embeddings.embed_query("another question entirely") is None       # fails fast, no network


def test_daily_budget_stops_background_embedding(gemini, monkeypatch):
    monkeypatch.setattr(config, "EMBED_DAILY_BUDGET", 0)
    assert embeddings.embed_documents(["x"]) is None and gemini == []


def test_no_key_means_meaning_leg_off(monkeypatch):
    monkeypatch.setattr(config, "EMBEDDINGS_PROVIDER", "gemini")
    monkeypatch.setattr(config, "EMBEDDINGS_API_KEY", "")
    assert embeddings.provider() == "none" and embeddings.embed_query("hello") is None
