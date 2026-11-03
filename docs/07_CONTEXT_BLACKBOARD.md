# 07 — Context Blackboard, Prefetch, Cache and Memory

## Why this exists
Talkdesk agents run one after another and each sees only its own tool results. Two problems follow:
1. **Facts get lost between agents.** Billing finds "MRI needs pre-authorisation", then Booking books it without mentioning that.
2. **Every tool call re-reads the same data.** The same patient snapshot, doctor list and slot list are fetched again and again inside one conversation.

The **blackboard** is our backend's per-patient working memory for the current conversation. Tools **write** facts to it and **read** from it, and each tool response carries the few most important facts in `related`. The agents don't need any extra tool to use it, so it adds **zero extra agent hops**.

The blackboard is keyed by the patient (normalised phone → patient_ref). A tool call with no phone (e.g. `check_coverage` by insurer name only) neither reads nor writes facts. For that reason, tool descriptions ask agents to pass `phone` whenever it is known.

What it is not: Talkdesk's supervisor cannot read our blackboard directly. It only sees tool results and Talkdesk variables. That's why facts travel inside tool responses.

## Priority levels
| Level | What | Where it lives | TTL | Who writes it |
|---|---|---|---|---|
| **P0** live conversation | current intent, the patient's last messages, variables | **Talkdesk** (variables, conversation) | conversation | Talkdesk |
| **P1** patient snapshot | identity, age/is_senior, upcoming bookings, pending reports, insurer, caregiver, last 3 notes | backend blackboard | 10 min | `verify_patient`, prefetch, invalidated by writes |
| **P2** session facts | slots just offered, chosen slot, coverage result, waitlist offer, handoff, assistance | backend blackboard | 30 min | the tool that produced the fact |
| **Reference** | doctors, departments, procedures, insurers, coverage rules, hospital info | backend cache | 5 min (cleared on edit) | loaded on first use / startup warm |

## Data structures
```python
@dataclass
class Fact:
    kind: str           # "coverage", "preauth", "slot_offered", "waitlist_offer", "handoff", "senior", ...
    text: str           # one speakable sentence
    priority: int       # 0 = critical ... 9 = nice to know
    created_at: float
    expires_at: float
    ref: str | None     # booking/procedure code it relates to

class Blackboard:
    # key: patient_ref (from verified phone) -> SessionContext
    snapshot: PatientSnapshot | None      # P1
    facts: list[Fact]                     # P2, small (<30)
```
**Selecting what goes into `related` (the top-k):** each response includes at most **k = 3** facts, chosen with a small heap (`heapq.nsmallest(3, ...)`) by:
1. `priority` (critical first): emergency/handoff 0, pre-auth required or not covered 1, offer expiring soon 2, senior/caregiver/mobility 3, everything else 5+
2. relevance: same `ref` (booking/procedure) as the current tool call first
3. recency: newer first
Facts the patient already heard in this response are skipped. Expired facts are dropped on read.

Example: `book_appointment(procedure=MRI-KNEE)` after `check_coverage` returns:
```json
"related": [
  {"kind":"preauth","text":"Star Health needs pre-approval for this MRI, usually within 24 hours."},
  {"kind":"senior","text":"Wheelchair help is on file for this patient."}
]
```

## Cache layers
```
tool/service ──► L1 in-process dict (TTL, LRU, ~5k entries)  ~microseconds
                    │ miss
                    ▼
                 L2 Redis (optional, REDIS_URL)                ~1–5 ms
                    │ miss
                    ▼
                 Postgres                                       ~5–20 ms
```
- Implement `Cache` as an interface: `get`, `set(ttl)`, `delete`, `delete_prefix`. `MemoryCache` is the default; `RedisCache` (redis-py asyncio) is enabled only when `REDIS_URL` is set. If Redis errors, log once and fall back to L1 (never fail a tool because of Redis).
- Blackboard storage uses the same interface (key `bb:{patient_ref}`), so it moves to Redis automatically when enabled.
- Run Render with **one worker** so L1 stays coherent.

| Key | TTL | Invalidated by |
|---|---|---|
| `ref:doctors`, `ref:departments`, `ref:procedures`, `ref:insurers`, `ref:coverage`, `ref:hospital_info` | 300 s | startup reload; any admin edit endpoint (none in V2) |
| `slots:{doctor_or_resource}:{date}` | 45 s | book / cancel / reschedule / offer accept touching that date |
| `patient:{ref}:snapshot` | 600 s | any write for that patient |
| `bb:{ref}` (facts) | 1800 s | expiry per fact |
| `auth:{auth_user_id}` → patient id | 600 s | link endpoint |

**Writes never trust the cache.** Booking always checks and updates the slot inside a Postgres transaction.

## Asynchronous prefetch
Prefetch runs in the background after we learn who the patient is, so the **next** tool call is a cache hit. It never delays the current response.

**Triggers**
1. `verify_patient` succeeds (chat and voice).
2. Website `POST /api/session/warm` when the logged-in patient opens the chat widget (`onOpenWebchat`). This is the earliest signal we get.
3. `find_available_slots` for a department → prefetch the next 2 working days for the same doctors.

**What gets prefetched (priority order, each a separate task, all with a 2 s timeout)**
1. P1 snapshot (if not already built).
2. Slots for the doctors of the patient's upcoming bookings and last 3 visits, next 7 days.
3. Ready/pending lab reports.
4. Coverage rules for the patient's insurer.
5. Due bills.

```python
async def on_patient_identified(ref):
    tasks = [warm_snapshot(ref), warm_related_slots(ref), warm_reports(ref),
             warm_coverage(ref), warm_bills(ref)]
    for t in tasks:
        asyncio.create_task(with_timeout(t, 2.0))   # fire and forget; errors logged
```
- Dedupe: skip if a warm for the same `ref` ran in the last 60 s.
- Bounded: a semaphore of 4 concurrent DB queries for prefetch so it never starves real tool calls.
- Metric: `prefetch_hits` vs `misses`, shown on the dashboard. This is how we prove prefetch helps.

## Conversation memory (previous chats)
Talkdesk sends no transcript to us, so memory is built from two sources:
1. **`resolutions`**: every action any tool or the website takes (automatic, reliable).
2. **`interaction_notes`**: the agent calls `save_interaction_note(phone, summary, topics, outcome)` at the end of a meaningful conversation (best effort).

**Retrieval**
- `verify_patient` includes the 3 most recent notes in the snapshot. Most "did I ask you…" questions are answered with no extra call.
- `search_past_interactions(phone, dob, query)`: **hybrid search** (built, `app/search.py`), described below.

## Hybrid search (built)
One table, `search_docs`, holds every searchable passage: the patient's notes (`note:`), their actions (`action:`,
from `resolutions`) and the hospital knowledge base (`kb:`: hospital info, departments with lay symptom words,
procedures with preparation, insurers, 28 FAQs in `app/kb.py`). Three legs run in one SQL statement:

| Leg | Postgres feature | Finds | Example |
|---|---|---|---|
| Keyword | generated `tsvector` + GIN, English stemming, OR query | exact words, stems | "visiting" ↔ "visits" |
| Fuzzy | `pg_trgm` `strict_word_similarity` ≥ 0.45 | typos, names | "cardiolgy" → Cardiology, "Iyyer" → Iyer |
| Code | `ILIKE` on normalised codes | booking/report IDs | "wn 48213" → WN-48213 |
| Meaning | `pgvector` `vector(768)`, cosine, Gemini `gemini-embedding-001` | paraphrases | "grab a bite to eat" → cafeteria |

- **Fusion**: Reciprocal Rank Fusion, `score = Σ weight / (60 + rank)` with ties sharing a rank (`dense_rank`), so
  no raw score scales need calibrating against each other and a passage found by several legs rises.
- **Relevance gate**: a hit counts only if it covers enough query words (1 of 1–2, half of 3+, after filler words are
  dropped), has a code match, or has cosine ≥ `SEARCH_MIN_SIM` (0.70). "Nothing relevant" is a real answer.
- **Scope**: patient searches are filtered to one `patient_id` and scored exactly (no ANN post-filtering);
  knowledge passages have an HNSW index (`WHERE kind = 'kb'`).
- **Where it is used**: `search_past_interactions`; `get_hospital_info` (free-text questions); `suggest_department`
  after the deterministic red-flag and keyword rules (a meaning match to the emergency passage only ever escalates).
- **Embeddings**: only natural-language text (knowledge passages and notes, about 900 rows) is embedded, in the
  background (startup, `/jobs/run`, after a note is saved or a patient verified). `embedding_cache` (model + content
  hash) survives demo resets, so re-seeding costs no API calls. Daily budget `EMBED_DAILY_BUDGET` (900) keeps the
  free tier for live queries. The query embedding is the only network call in a live tool call: 1.5 s timeout,
  7-day cache, and a circuit breaker; on any failure the search runs on keyword + fuzzy without the agent noticing.
- **Degrades by itself**: no key → keyword + fuzzy; no `vector`/`pg_trgm` extension → those legs off; SQLite →
  word overlap in Python. `/health` shows `"search": "hybrid" | "keyword+fuzzy" | "keyword"`.
- **Quality**: `scripts/eval_search.py` (26 labelled questions: keyword, typo, code, paraphrase, off-topic) runs in
  CI with keyword, typo, code and off-topic required to pass; `search-live.yml` runs it with the real model.
- **Debug view**: `/api/ops/search?token=<DASHBOARD_TOKEN>&q=...&phone=...&raw=true` shows each hit's legs.
- Patient memory is always scoped to one patient. Never search across patients.

## What to show the judges
- Dashboard tile: cache hit rate, prefetch hit rate, p50/p95 per tool.
- A trace of one multi-agent request where `related` carried the pre-auth fact from Billing into Booking's confirmation.
