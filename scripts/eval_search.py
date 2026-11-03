"""Evaluate hybrid search quality on labelled questions, through the running server's /api/ops/search.

Includes paraphrases that share no words with the answer (only the meaning leg can find them), typos, exact codes,
and off-topic questions that must return nothing. Prints hit@1 / hit@3, which legs fired, and the cosine
similarities seen, with a suggested SEARCH_MIN_SIM for the embeddings model in use.

Usage:
  SEARCH_URL=http://localhost:8000 DASHBOARD_TOKEN=... python scripts/eval_search.py [--min-hit3 0.8]
  SEARCH_URL=https://teamxyz-mcp.onrender.com DASHBOARD_TOKEN=... python scripts/eval_search.py
Read-only: it does not change any data.
"""

import argparse
import os
import statistics
import sys

import httpx

BASE = os.environ.get("SEARCH_URL", "http://localhost:8000").rstrip("/")
TOKEN = os.environ.get("DASHBOARD_TOKEN") or os.environ.get("MCP_BEARER_TOKEN", "")
SHAN = "9845000001"

# (query, scope, phone, expected: ref prefix, or "text:<substring>", or None = must return nothing, kind)
CASES = [
    # keyword-friendly
    ("can my son stay overnight with me in the ward", "kb", "", "kb:faq:attendant", "keyword"),
    ("ICU visiting hours", "kb", "", "kb:faq:icu", "keyword"),
    ("do you take star health cashless", "kb", "", "kb:ins:STAR", "keyword"),
    ("what should I do before an MRI brain", "kb", "", "kb:proc:MRI-BRAIN", "keyword"),
    ("is there wifi", "kb", "", "kb:faq:wifi", "keyword"),
    # typos (fuzzy leg)
    ("cardiolgy floor", "kb", "", "kb:dept:CARD", "typo"),
    ("parkng for patients", "kb", "", "kb:info:parking", "typo"),
    ("pharmasy open at night", "kb", "", "kb:info:pharmacy", "typo"),
    # paraphrases with little or no word overlap (meaning leg)
    ("can I get online while I wait", "kb", "", "kb:faq:wifi", "meaning"),
    ("where can I grab a bite to eat", "kb", "", "kb:faq:food", "meaning"),
    ("can I pay using PhonePe or Google Pay", "kb", "", "kb:faq:payment", "meaning"),
    ("is there somewhere quiet to pray", "kb", "", "kb:faq:prayer", "meaning"),
    ("I left my umbrella somewhere in your building", "kb", "", "kb:faq:lost_found", "meaning"),
    ("someone can come to my house to take blood?", "kb", "", "kb:faq:home_collection", "meaning"),
    ("how do I get my papers after leaving the hospital", "kb", "", "kb:faq:records", "meaning"),
    ("I can't stop scratching my arms", "dept", "", "kb:dept:DERM", "meaning"),
    ("tummy hurts after every meal", "dept", "", "kb:dept:GAST", "meaning"),
    ("my little one needs her shots", "dept", "", "kb:dept:PAED", "meaning"),
    ("always thirsty and peeing a lot", "dept", "", "kb:dept:ENDO", "meaning"),
    ("words come out slurred and one side of my face drooped", "dept", "", "kb:faq:emergency_signs", "meaning"),
    # patient memory (one patient's own notes and actions)
    ("anything about WN-48213?", "patient", SHAN, "text:WN-48213", "code"),
    ("did I ask about my knee MRI report", "patient", SHAN, "text:MRI Knee report", "keyword"),
    ("help getting around at the entrance for my mum", "patient", SHAN, "text:wheelchair", "meaning"),
    # must find nothing
    ("what is the cricket score today", "kb", "", None, "negative"),
    ("recommend a good movie this weekend", "kb", "", None, "negative"),
    ("did I talk to you about buying a car", "patient", SHAN, None, "negative"),
]


def run(q, scope, phone):
    params = {"q": q, "token": TOKEN, "scope": "dept" if scope == "dept" else "kb", "raw": "true"}
    if scope == "patient":
        params["phone"] = phone
    r = httpx.get(f"{BASE}/api/ops/search", params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def matches(hit, exp):
    if exp.startswith("text:"):
        return exp[5:].lower() in hit["text"].lower()
    return hit["ref"].startswith(exp)


def main(a):
    rows, mode, pos_sims, neg_sims = [], None, [], []
    for q, scope, phone, exp, kind in CASES:
        d = run(q, scope, phone)
        mode = d["mode"]
        raw = d["hits"]                                  # ungated candidates, for calibration
        hits = [h for h in raw if h["confident"]]        # what the tools actually use
        if exp is None:
            ok1 = ok3 = not hits
            neg_sims.append(max([h["signals"].get("vec") or 0 for h in raw] or [0]))
        else:
            rank = next((i + 1 for i, h in enumerate(hits) if matches(h, exp)), None)
            ok1, ok3 = rank == 1, rank is not None and rank <= 3
            right = next((h for h in raw if matches(h, exp)), None)
            if right and right["signals"].get("vec") is not None:
                pos_sims.append(right["signals"]["vec"])
        top = hits[0] if hits else None
        rows.append((kind, ok1, ok3))
        sig = top["signals"] if top else {}
        print(f"{'PASS' if ok3 else 'MISS'} [{kind:8}] {q[:52]:52} -> {(top['ref'] if top else '(nothing)'):28} "
              f"fts={sig.get('fts')} trgm={sig.get('trgm')} vec={sig.get('vec')} words={sig.get('words')} {d['ms']}ms")
        if a.verbose:
            by_vec = sorted([h for h in raw if h["signals"].get("vec") is not None], key=lambda h: -h["signals"]["vec"])
            vr = next((i + 1 for i, h in enumerate(by_vec) if exp and matches(h, exp)), None)
            right_v = by_vec[vr - 1]["signals"]["vec"] if vr else None
            print(f"       meaning leg: " + ", ".join(f"{h['ref'].split(':', 1)[-1]} {h['signals']['vec']:.3f}" for h in by_vec[:3])
                  + (f" | right passage: rank {vr}, cos {right_v:.3f}" if vr else (" | right passage not in top 8" if exp else "")))
    n = len(rows)
    h1 = sum(r[1] for r in rows) / n
    h3 = sum(r[2] for r in rows) / n
    print(f"\nMode: {mode}   hit@1 {h1:.0%}   hit@3 {h3:.0%}   ({n} questions)")
    for kind in ("keyword", "typo", "meaning", "code", "negative"):
        sub = [r for r in rows if r[0] == kind]
        if sub:
            print(f"  {kind:9} hit@3 {sum(r[2] for r in sub)}/{len(sub)}")
    if pos_sims:
        ps = sorted(pos_sims)
        print(f"\nCosine of the correct passage: min {ps[0]:.3f}  25th pct {ps[len(ps) // 4]:.3f}  median {statistics.median(ps):.3f}")
        print(f"Best cosine for off-topic questions: max {max(neg_sims or [0]):.3f}")
        print("SEARCH_MIN_SIM gates meaning-only matches: set it just above the off-topic max and below most correct ones.")
    e = (d.get("status") or {}).get("embeddings", {})
    print(f"\nEmbeddings: provider {e.get('provider')}  queries sent {e.get('query_calls')}  cache hits {e.get('query_cache_hits')}  "
          f"errors {e.get('errors')}  last limit hit: {e.get('last_quota') or 'none'}")
    failed = False
    if a.min_hit3 and h3 < a.min_hit3:
        print(f"FAIL: hit@3 {h3:.0%} < {a.min_hit3:.0%}")
        failed = True
    for kind in filter(None, a.require.split(",")):
        sub = [r for r in rows if r[0] == kind]
        if sub and not all(r[2] for r in sub):
            print(f"FAIL: every '{kind}' question must pass")
            failed = True
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-hit3", type=float, default=0.0)
    ap.add_argument("--verbose", action="store_true", help="print the meaning leg's top candidates per question")
    ap.add_argument("--require", default="", help="comma list of kinds that must all pass, e.g. keyword,typo,code,negative")
    main(ap.parse_args())
