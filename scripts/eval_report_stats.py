"""Agent-side numbers from a Talkdesk Agent Evaluation HTML report (the downloadable "Eval Report").

Usage:  python scripts/eval_report_stats.py eval_report_<id>.html [more reports...]

Per report: turn latency (P50/P95/P99 as Talkdesk measured it), agent steps per patient turn, specialist hops,
our MCP tool calls vs Talkdesk's own date-helper calls, and which agent answered. These are the numbers that show
whether the architecture keeps a request to one specialist and one tool call.
"""

import html
import re
import statistics
import sys
from collections import Counter

OURS_EXCLUDE = {"get_weekday_for_date_internal"}


def text_of(path: str) -> str:
    s = open(path, encoding="utf-8").read()
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", s, flags=re.S)
    t = html.unescape(re.sub(r"<[^>]+>", "\n", t))
    return re.sub(r"\n\s*\n+", "\n", t)


def stats(path: str) -> dict:
    t = text_of(path)
    head = t[:1500]
    lat = dict(re.findall(r"(P95 turn latency|P50|P99|Worst turn)\n([\d.]+s)", head))
    scenarios = re.split(r"\n(?=\d{3} [^\n]*\n[01]/1 passed)", t)[1:]
    steps, hops, ours, helper, agents = [], [], Counter(), 0, Counter()
    one_hop = turns = 0
    for sc in scenarios:
        # each agent reply: "<n> steps" then the trace up to the next user/agent line
        for m in re.finditer(r"\n(\d+) steps\n(.*?)(?=\nuser\n|\n\d+/1 goals achieved|\Z)", sc, flags=re.S):
            n, trace = int(m.group(1)), m.group(2)
            handoffs = re.findall(r"\nReceptionist → ([^\n]+)", trace)
            if n <= 1 and not handoffs:
                continue                                   # the greeting
            turns += 1
            steps.append(n)
            hops.append(len(handoffs))
            if len(handoffs) == 1:
                one_hop += 1
            for a in handoffs:
                agents[a] += 1
            for name in re.findall(r"\n⚙\n[^\n]+\n([a-z_]+)\nInput", trace):
                if name in OURS_EXCLUDE:
                    helper += 1
                else:
                    ours[name] += 1
    goals = len(re.findall(r"\n1/1 goals achieved", t))
    tool_turns = [h for h in hops if h]
    return {"report": path.rsplit("/", 1)[-1], "scenarios": len(scenarios), "goals_achieved": goals,
            "turn_latency": lat, "patient_turns": turns,
            "avg_steps_per_turn": round(statistics.mean(steps), 2) if steps else 0,
            "turns_answered_by_one_specialist_pct": round(100 * one_hop / max(1, len(tool_turns)), 1),
            "avg_specialist_hops_when_routed": round(statistics.mean(tool_turns), 2) if tool_turns else 0,
            "mcp_tool_calls": sum(ours.values()), "talkdesk_date_helper_calls": helper,
            "routed_to": dict(agents.most_common()), "top_tools": dict(ours.most_common(8))}


if __name__ == "__main__":
    for p in sys.argv[1:]:
        s = stats(p)
        print(f"\n## {s['report']}")
        for k, v in s.items():
            if k != "report":
                print(f"- {k}: {v}")
