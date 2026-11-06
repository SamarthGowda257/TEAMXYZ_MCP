"""Hybrid search: keyword (Postgres full-text) + fuzzy (pg_trgm) + meaning (pgvector), fused with Reciprocal Rank Fusion.

Why hybrid, not embeddings alone: booking codes (WN-48213), doctor names, drug and test names and exact words must
match exactly, which embeddings do badly; typos ("cardiolgy", "Iyyer") need trigram matching; and paraphrases
("my heart races at night" -> Cardiology) need meaning. Each leg ranks its own top 20; RRF adds 1/(60 + rank) per leg,
so a passage found by several legs rises to the top and no leg's raw score scale has to be calibrated against another.

Every hit must also pass a relevance gate (a keyword hit, a strong fuzzy hit, a code hit, or cosine >= SEARCH_MIN_SIM),
so "nothing relevant" is a real answer instead of the least-bad passage.

Scopes: one patient's own notes and actions (never across patients), or the hospital knowledge base (kb).
Degrades on its own: no vector extension or no API key -> keyword + fuzzy; SQLite -> word overlap in Python.
"""

import logging
import re
import threading
import time
from datetime import datetime

from sqlalchemy import select, text

from . import config, db
from . import embeddings as emb

log = logging.getLogger("wellnest.search")

STOP = set("""a an and are as at be been but by can could did do does doing for from had has have how i i'm im if in into is
it its just me my myself of on or our please so than that the their them then there these they this to too us was we were
what when where which who why will with would you your yours ok okay yes no not any about again also ask asked asking tell
told talk talked said say want wanted need needed know get got last week month day today yesterday before earlier previous
time times hospital wellnest doctor doctors sir madam hello hi thanks thank kindly keep keeps kept having feel feeling
felt since days getting really very much lot little bit sometimes often always mother father mom dad amma appa son daughter
wife husband brother sister friend someone something anything there here like""".split())
CODE_RE = re.compile(r"\b(WN|LR|BL|RX|CB|HO|CI|NT|WL)[\s-]?(\d{3,6})\b", re.I)
RRF_K = 60
WEIGHTS = {"f": 1.0, "t": 1.0, "v": 1.0, "c": 3.0}
TRGM_MIN = 0.45          # strict_word_similarity (whole words) a query word needs: typos ~0.5-0.6, "car" in "cardiology" 0.25
LEG_LIMIT = 20           # meaning leg depth
# Only natural-language text gets a meaning vector. Action logs ("book appointment: ... (WN-48213)") are short,
# machine-written records of codes, names and dates: keyword, fuzzy and code matching are the right tools for them.
# Knowledge passages (~95) are embedded eagerly; a patient's notes only when that patient shows up (verified, session
# warm-up, new note), because the free tier allows roughly 1,000 embeddings a day and most patients never call.
EMBED_KINDS = "('kb', 'note')"
BACKFILL_BATCH = 25
BACKFILL_PAUSE_S = 20
KW_LIMIT = 100           # keyword legs go deeper: common words tie across many passages
_embed_lock = threading.Lock()
_status_cache: tuple[float, dict] | None = None


def words(q: str, ignore: frozenset = frozenset()) -> list[str]:
    out = []
    for w in re.findall(r"[a-z0-9]+", (q or "").lower()):
        if len(w) >= 3 and w not in STOP and w not in ignore and w not in out:
            out.append(w)
    return out[:10]


def codes(q: str) -> list[str]:
    return [f"{a.upper()}-{b}" for a, b in CODE_RE.findall(q or "")]


def _vec_literal(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


def _pg_path(c) -> None:
    c.execute(text(f"SET LOCAL search_path TO {db.SEARCH['path']}"))


# ------------------------------------------------------------------ indexing
_NOTE_SQL = """INSERT INTO search_docs (ref, kind, patient_id, title, body, created_at)
SELECT 'note:' || n.id, 'note', n.patient_id, n.topics, n.summary || CASE WHEN n.outcome IS NULL THEN '' ELSE ' Outcome: ' || n.outcome END, n.created_at
FROM interaction_notes n WHERE n.patient_id IS NOT NULL {pf}
  AND NOT EXISTS (SELECT 1 FROM search_docs d WHERE d.ref = 'note:' || n.id)
ON CONFLICT (ref) DO NOTHING"""
_ACTION_SQL = """INSERT INTO search_docs (ref, kind, patient_id, title, body, created_at)
SELECT 'action:' || r.id, 'action', r.patient_id, r.action,
       replace(r.action, '_', ' ') || ': ' || coalesce(r.summary, '') || CASE WHEN r.ref IS NULL THEN '' ELSE ' (' || r.ref || ')' END
         || CASE WHEN r.ok THEN '' ELSE ' (not completed)' END, r.created_at
FROM resolutions r WHERE r.patient_id IS NOT NULL {pf}
  AND NOT EXISTS (SELECT 1 FROM search_docs d WHERE d.ref = 'action:' || r.id)
ON CONFLICT (ref) DO NOTHING"""


def sync(conn=None, patient_id: int | None = None) -> None:
    """Copy new notes and actions into search_docs (one patient, or everyone). Cheap and idempotent: the search tool
    runs it for the patient before every search, so a note saved seconds ago is already findable by keyword."""
    def run(c):
        pf = "AND {t}.patient_id = :pid" if patient_id else ""
        args = {"pid": patient_id} if patient_id else {}
        c.execute(text(_NOTE_SQL.format(pf=pf.format(t="n"))), args)
        c.execute(text(_ACTION_SQL.format(pf=pf.format(t="r"))), args)
    try:
        if conn is not None and db.IS_POSTGRES:
            with conn.begin_nested():           # never let indexing break the caller's booking or note
                run(conn)
        elif conn is not None:
            run(conn)
        else:
            with db.engine.begin() as c:
                run(c)
    except Exception as e:
        log.warning("search sync failed: %s", str(e).splitlines()[0][:200])


def sync_kb() -> int:
    """Upsert the knowledge passages (from kb.py + reference data). Changed text loses its embedding."""
    from . import kb
    docs = {d["ref"]: d for d in kb.documents()}
    D = db.search_docs
    with db.engine.begin() as c:
        have = {r.ref: (r.title, r.body) for r in c.execute(text("SELECT ref, title, body FROM search_docs WHERE kind = 'kb'"))}
        new = [d for r, d in docs.items() if r not in have]
        changed = [d for r, d in docs.items() if r in have and have[r] != (d["title"], d["body"])]
        gone = [r for r in have if r not in docs]
        if new:
            c.execute(D.insert(), [{"ref": d["ref"], "kind": "kb", "patient_id": None, "title": d["title"], "body": d["body"],
                                    "created_at": config.now()} for d in new])
        reset_vec = ", embedding = NULL" if (db.IS_POSTGRES and db.SEARCH["vector"]) else ""
        for d in changed:
            c.execute(text(f"UPDATE search_docs SET title = :t, body = :b{reset_vec} WHERE ref = :r"),
                      {"t": d["title"], "b": d["body"], "r": d["ref"]})
        for r in gone:
            c.execute(text("DELETE FROM search_docs WHERE ref = :r"), {"r": r})
    return len(new) + len(changed)


def vector_ready() -> bool:
    return db.IS_POSTGRES and db.SEARCH["vector"] and emb.enabled()


def embed_pending(limit: int = 200, patient_id: int | None = None) -> int:
    """Background: give un-embedded rows a vector. Re-uses embedding_cache first (free), then calls the provider for
    the rest. Without patient_id: knowledge passages only. With patient_id: that patient's notes. Never raises."""
    if not vector_ready():
        return 0
    if not _embed_lock.acquire(timeout=0 if patient_id is None else 10):
        return 0
    try:
        model = emb.model_id()
        pf = "AND patient_id = :pid AND kind = 'note'" if patient_id else "AND kind = 'kb'"
        if not patient_id:
            limit = min(limit, emb.budget_left()) if emb.provider() == "gemini" else limit
        args = {"m": model, "pid": patient_id, "n": limit}
        with db.engine.begin() as c:
            _pg_path(c)
            filled = c.execute(text(f"""UPDATE search_docs d SET embedding = e.embedding FROM embedding_cache e
                WHERE d.embedding IS NULL AND d.kind IN {EMBED_KINDS} AND e.model = :m AND e.chash = d.chash
                {pf.replace('patient_id', 'd.patient_id').replace('kind =', 'd.kind =')}"""), args).rowcount or 0
            todo = c.execute(text(f"""SELECT chash, min(title) AS title, min(body) AS body,
                    max(CASE kind WHEN 'kb' THEN 3 WHEN 'note' THEN 2 ELSE 1 END) AS pri, max(created_at) AS at
                FROM search_docs WHERE embedding IS NULL AND kind IN {EMBED_KINDS} {pf}
                GROUP BY chash ORDER BY pri DESC, at DESC LIMIT :n"""), args).all() if limit > 0 else []
        if not todo:
            return filled
        vecs = emb.embed_documents([f"{t.title or ''}\n{t.body}".strip() for t in todo])
        if not vecs:
            return filled
        rows = [{"m": model, "h": t.chash, "v": _vec_literal(v)} for t, v in zip(todo, vecs)]
        with db.engine.begin() as c:
            _pg_path(c)
            c.execute(text("INSERT INTO embedding_cache (model, chash, embedding) VALUES (:m, :h, CAST(:v AS vector)) "
                           "ON CONFLICT DO NOTHING"), rows)
            n = 0
            for r in rows:
                n += c.execute(text(f"UPDATE search_docs SET embedding = CAST(:v AS vector) WHERE chash = :h AND embedding IS NULL "
                                    f"AND kind IN {EMBED_KINDS}"),
                               r).rowcount or 0
        return filled + n
    except Exception as e:
        log.warning("embedding backfill failed: %s", str(e).splitlines()[0][:200])
        return 0
    finally:
        _embed_lock.release()


def rebuild_async() -> None:
    """Startup and after a demo reset: index everything, then embed in the background (cache makes repeats free)."""
    def run():
        try:
            sync_kb()
            from . import kb
            from .services import hospital_ctx
            hospital_ctx.publish(kb.documents())     # hospital profile + knowledge version on the blackboard
            sync()
            if vector_ready():
                # Paced: Gemini's free tier counts each text against ~100 requests per minute, shared with live
                # questions. 25 texts every 20 s (75/min) leaves room for callers; the cache makes restarts free.
                for _ in range(400):
                    if embed_pending(BACKFILL_BATCH) == 0:
                        break
                    if emb.provider() == "gemini":      # pacing is for Google's per-minute limit only
                        time.sleep(BACKFILL_PAUSE_S)
        except Exception as e:
            log.warning("search rebuild failed: %s", e)
    threading.Thread(target=run, name="search-rebuild", daemon=True).start()


# ------------------------------------------------------------------ search
def search(query: str, *, patient_id: int | None = None, ref_prefixes: tuple[str, ...] = ("kb:",), k: int = 3,
           conn=None, ignore: frozenset = frozenset(), gate: bool = True) -> dict:
    """Returns {"hits": [...], "mode": "hybrid" | "keyword+fuzzy" | "keyword"}. Each hit: ref, kind, title, body,
    created_at, score, signals {fts, trgm, vec, code}, confident. Hits are already filtered by the relevance gate."""
    q = " ".join((query or "").split())[:500]
    if db.IS_POSTGRES:
        try:
            return _search_pg(q, patient_id, ref_prefixes, k, conn, ignore, gate)
        except Exception as e:
            log.warning("hybrid search failed, using fallback: %s", str(e).splitlines()[0][:200])
    return _search_py(q, patient_id, ref_prefixes, k, ignore)


def _scope(patient_id, ref_prefixes, args) -> str:
    if patient_id is not None:
        args["pid"] = patient_id
        return "d.patient_id = :pid AND d.kind IN ('note', 'action')"
    parts = []
    for i, p in enumerate(ref_prefixes):
        args[f"p{i}"] = p + "%"
        parts.append(f"d.ref LIKE :p{i}")
    return "d.kind = 'kb' AND (" + " OR ".join(parts) + ")"


def _search_pg(q, patient_id, ref_prefixes, k, conn, ignore=frozenset(), gate=True) -> dict:
    ws, cs = words(q, ignore), codes(q)
    args: dict = {"k": k * 4}
    scope = _scope(patient_id, ref_prefixes, args)
    ctes, legs = [], []
    if ws and db.SEARCH["fts"]:
        args["tsq"] = " | ".join(ws)
        ctes.append(f"""fts AS (SELECT d.id, ts_rank_cd(d.tsv, q) AS s, NULL::int AS n FROM search_docs d, to_tsquery('english', :tsq) q
            WHERE {scope} AND d.tsv @@ q ORDER BY s DESC LIMIT {KW_LIMIT})""")
        legs.append(("f", "fts"))
    tw = [w for w in ws if not w.isdigit()]
    if tw and db.SEARCH["trgm"]:
        args["tw"], args["tmin"] = tw, TRGM_MIN
        # Per query word: a whole-word fuzzy match (typos) or a stemmed full-text match ("visiting" ~ "visits") counts.
        # n = how many query words the passage covers; s = how well.
        stem = "d.tsv @@ plainto_tsquery('english', w)" if db.SEARCH["fts"] else "false"
        ctes.append(f"""tri AS (SELECT d.id, x.s, x.n FROM search_docs d CROSS JOIN LATERAL (
              SELECT sum(greatest(ws, CASE WHEN hit THEN 0.9 ELSE 0 END)) AS s, count(*)::int AS n FROM (
                SELECT strict_word_similarity(w, coalesce(d.title, '') || ' ' || d.body) AS ws, {stem} AS hit
                FROM unnest(CAST(:tw AS text[])) AS w) y WHERE ws >= :tmin OR hit) x
            WHERE {scope} AND x.n > 0 ORDER BY x.s DESC LIMIT {KW_LIMIT})""")
        legs.append(("t", "tri"))
    if cs:
        args["codes"] = [f"%{c}%" for c in cs]
        ctes.append(f"code AS (SELECT d.id, 1.0 AS s, NULL::int AS n FROM search_docs d WHERE {scope} AND d.body ILIKE ANY(CAST(:codes AS text[])) LIMIT {LEG_LIMIT})")
        legs.append(("c", "code"))
    vec = emb.embed_query(q) if (q and vector_ready()) else None
    if vec is not None:
        args["v"] = _vec_literal(vec)
        if patient_id is not None:     # exact scoring over this patient's rows only (an ANN index would post-filter)
            ctes.append(f"cand AS MATERIALIZED (SELECT d.id, d.embedding FROM search_docs d WHERE {scope} AND d.embedding IS NOT NULL)")
            ctes.append(f"vec0 AS (SELECT id, 1 - (embedding <=> CAST(:v AS vector)) AS s, NULL::int AS n FROM cand ORDER BY embedding <=> CAST(:v AS vector) LIMIT {LEG_LIMIT})")
        else:
            ctes.append(f"""vec0 AS (SELECT d.id, 1 - (d.embedding <=> CAST(:v AS vector)) AS s, NULL::int AS n FROM search_docs d
                WHERE {scope} AND d.embedding IS NOT NULL ORDER BY d.embedding <=> CAST(:v AS vector) LIMIT {LEG_LIMIT})""")
        # Only a meaningful similarity earns ranking credit. Without this floor, any passage that merely HAS a vector
        # (e.g. the first batch embedded after a deploy) outranks the right keyword match through a near-zero cosine.
        args["vfloor"] = config.SEARCH_VEC_FLOOR
        ctes.append("vec AS (SELECT id, s, n FROM vec0 WHERE s >= :vfloor)")
        legs.append(("v", "vec"))
    mode = "hybrid" if vec is not None else ("keyword+fuzzy" if db.SEARCH["trgm"] else "keyword")
    if not legs:
        return {"hits": [], "mode": mode}
    union = " UNION ALL ".join(f"SELECT id, '{l}' AS leg, s, n, dense_rank() OVER (ORDER BY s DESC) AS r FROM {name}" for l, name in legs)
    weight = "CASE leg " + " ".join(f"WHEN '{l}' THEN {WEIGHTS[l]}" for l in WEIGHTS) + " END"
    sql = f"""WITH {', '.join(ctes)}, ranked AS ({union})
        SELECT d.ref, d.kind, d.title, d.body, d.created_at, sum({weight} / ({RRF_K}.0 + r)) AS score,
               max(CASE WHEN leg = 'f' THEN s END) AS fts, max(CASE WHEN leg = 't' THEN s END) AS trgm,
               max(CASE WHEN leg = 'v' THEN s END) AS vec, bool_or(leg = 'c') AS code, max(n) AS n
        FROM ranked JOIN search_docs d ON d.id = ranked.id
        GROUP BY d.id, d.ref, d.kind, d.title, d.body, d.created_at
        ORDER BY score DESC, max(n) DESC NULLS LAST, d.created_at DESC LIMIT :k"""

    def run(c):
        _pg_path(c)
        if patient_id is None and vec is not None:
            c.execute(text("SET LOCAL hnsw.ef_search = 200"))   # filtered ANN: look wider so filters keep enough rows
        return c.execute(text(sql), args).mappings().all()
    if conn is not None:
        with conn.begin_nested():               # a failure here must not poison the caller's transaction
            rows = run(conn)
    else:
        with db.engine.begin() as c:
            rows = run(c)
    # Keyword coverage gate: enough of the query's words must appear (exactly or nearly), so one common word
    # ("floor", "night") is not an answer. With no fuzzy leg, any full-text hit counts.
    need = 1 if len(tw) <= 2 else -(-len(tw) // 2)
    hits = []
    for r in rows:
        sig = {"fts": round(float(r["fts"]), 3) if r["fts"] is not None else None,
               "trgm": round(float(r["trgm"]), 3) if r["trgm"] is not None else None,
               "vec": round(float(r["vec"]), 3) if r["vec"] is not None else None, "code": bool(r["code"]),
               "words": f"{r['n'] or 0}/{len(tw)}"}
        # Passages from data/hospital are long prose, so one incidental common word is not an answer:
        # "what is the cricket score today" reduces to two terms, matches "score" in the aftercare
        # passage (which means *pain* score) and would otherwise clear a need of 1. Those passages
        # need two shared words, or the whole query matched, or a real code or meaning hit. The short
        # curated entries in app/kb.py (kb:faq, kb:dept, kb:policy) are tightly scoped and keep need.
        n_words = r["n"] or 0
        long_doc = str(r["ref"]).startswith("kb:doc:")
        want = max(need, 2) if long_doc else need
        kw_ok = (n_words >= want or (n_words and n_words == len(tw))) if "t" in dict(legs) else bool(sig["fts"])
        confident = bool(sig["code"] or kw_ok or (sig["vec"] is not None and sig["vec"] >= config.SEARCH_MIN_SIM))
        if confident or not gate:
            hits.append({"ref": r["ref"], "kind": r["kind"], "title": r["title"], "body": r["body"], "created_at": r["created_at"],
                         "score": round(float(r["score"]), 5), "signals": sig, "confident": confident})
    return {"hits": hits[:k], "mode": mode}


def _search_py(q, patient_id, ref_prefixes, k, ignore=frozenset()) -> dict:
    """SQLite / emergency fallback: word overlap with simple stemming, newest first on ties."""
    ws, cs = words(q, ignore), codes(q)
    D = db.search_docs
    cols = (D.c.ref, D.c.kind, D.c.title, D.c.body, D.c.created_at)        # typed: SQLite returns real datetimes
    with db.engine.connect() as c:
        if patient_id is not None:
            rows = c.execute(select(*cols).where(D.c.patient_id == patient_id, D.c.kind.in_(("note", "action")))
                             .order_by(D.c.created_at.desc()).limit(200)).mappings().all()
        else:
            rows = [r for r in c.execute(select(*cols).where(D.c.kind == "kb")).mappings()
                    if r["ref"].startswith(tuple(ref_prefixes))]
    scored = []
    for r in rows:
        hay = f"{r['title'] or ''} {r['body']}".lower()
        hw = set(re.findall(r"[a-z0-9]+", hay))
        # whole words, or a shared stem for longer words ("visiting" ~ "visits"); never inside a word ("car" in "cardiology")
        s = sum(1 for w in ws if w in hw or (len(w) > 4 and any(h.startswith(w[:-2]) and len(h) > 4 for h in hw))) \
            + sum(3 for c_ in cs if c_.lower() in hay)
        if s:
            ca = r["created_at"]
            ts = ca.timestamp() if isinstance(ca, datetime) else 0
            scored.append((s, ts, r))
    scored.sort(key=lambda x: (-x[0], -x[1]))
    hits = [{**dict(r), "score": s, "signals": {"fts": None, "trgm": None, "vec": None, "code": False, "overlap": s}, "confident": True}
            for s, _, r in scored[:k]]
    return {"hits": hits, "mode": "keyword"}


# ------------------------------------------------------------------ status (for /health and the dashboard)
def status(brief: bool = False):
    if not db.IS_POSTGRES:
        mode = "keyword (sqlite)"
    elif vector_ready():
        mode = "hybrid"
    elif db.SEARCH["trgm"]:
        mode = "keyword+fuzzy"
    else:
        mode = "keyword"
    if brief:
        return mode
    global _status_cache
    if _status_cache and time.monotonic() - _status_cache[0] < 30:
        counts = _status_cache[1]
    else:
        counts = {}
        try:
            with db.engine.connect() as c:
                counts["docs"] = c.execute(text("SELECT count(*) FROM search_docs")).scalar()
                counts["kb_total"] = c.execute(text("SELECT count(*) FROM search_docs WHERE kind = 'kb'")).scalar()
                if db.IS_POSTGRES and db.SEARCH["vector"]:
                    r = c.execute(text("SELECT count(*) FILTER (WHERE kind = 'kb'), count(*) FILTER (WHERE kind = 'note') "
                                       "FROM search_docs WHERE embedding IS NOT NULL")).one()
                    counts["kb_embedded"], counts["notes_embedded"] = r[0], r[1]
        except Exception as e:
            counts["error"] = str(e).splitlines()[0][:120]
        _status_cache = (time.monotonic(), counts)
    legs = {"keyword": bool(db.IS_POSTGRES and db.SEARCH["fts"]), "fuzzy": bool(db.IS_POSTGRES and db.SEARCH["trgm"]),
            "meaning": vector_ready()}
    return {"mode": mode, "legs": legs, "pgvector": bool(db.SEARCH["vector"]), "setup_error": db.SEARCH["error"],
            "embeddings": emb.status(), **counts}
