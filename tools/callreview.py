#!/usr/bin/env python3
"""Pull real calls from Retell and print what the caller actually heard.

`docs/lessons-v22-overhaul.md`, finding 3: reading seven real transcripts found
five real defects in about ten minutes, and every one was real. A reading of
the flow JSON tells you what the flow SAYS. A transcript tells you what the
caller HEARD. Do this before believing any test run.

Read-only. Uses POST /v3/list-calls and GET /v2/get-call, and never writes
to Retell.

PRIVACY. Transcripts carry caller names, phone numbers and addresses. This
prints them to your terminal because you need them to judge a call. Do NOT
paste them into repository files: root CLAUDE.md forbids personal detail in
the repo, changelogs and agent prompts included. Quote the agent's own lines
and the call id instead. `--redact` masks the obvious identifiers if you need
to hand the output to someone else.

Usage:
    python tools/callreview.py --agent b --version 24
    python tools/callreview.py --agent b --version 24 --limit 30
    python tools/callreview.py --agent b --version 24 --summary
    python tools/callreview.py --agent b --call call_xxxxxxxxxxxxxxxxxxxxxxxxxxx
    python tools/callreview.py --agent b --version 24 --redact
"""
import re
import sys
import argparse
import datetime as dt
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "kit"))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

from retellkit import RetellClient, RetellError, agent_config, load_env

PHONE = re.compile(r"\+?\d[\d\-\(\)\s]{8,}\d")


def redact(text):
    return PHONE.sub("[number]", text or "")


def when(ms):
    if not ms:
        return "?"
    return dt.datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%M")


def fetch(client, agent_id, version, limit):
    """Newest first. list-calls paginates, so keep asking until we have enough."""
    # /v3/list-calls rows carry no transcript, so each kept row is re-read
    # with /v2/get-call. /v2/list-calls is deprecated (Retell, 2026-06-15).
    out, key = [], None
    while len(out) < limit:
        body = {
            "filter_criteria": {"agent_id": [agent_id]},
            "sort_order": "descending",
            "limit": 100,
        }
        if key:
            body["pagination_key"] = key
        page = client._request("POST", "/v3/list-calls", body)
        for c in page.get("items") or []:
            if version is None or c.get("agent_version") == version:
                out.append(c)
        if not page.get("has_more"):
            break
        key = page.get("pagination_key")
    return [client._request("GET", "/v2/get-call/{}".format(c["call_id"]))
            for c in out[:limit]]


def latency_of(call):
    lat = call.get("latency") or {}
    e2e = lat.get("e2e") or {}
    parts = []
    for name in ("e2e", "llm", "tts", "s2s", "knowledge_base"):
        d = lat.get(name) or {}
        if d.get("p50"):
            parts.append("{} p50 {:.0f}ms".format(name, d["p50"]))
    return ", ".join(parts) or "(none reported)"


def print_call(call, args):
    tr = call.get("transcript") or ""
    if args.redact:
        tr = redact(tr)
    an = call.get("call_analysis") or {}
    dv = call.get("collected_dynamic_variables") or {}

    print("=" * 78)
    print("{}  {}  {}s  {}".format(
        call.get("call_id"), when(call.get("start_timestamp")),
        round((call.get("duration_ms") or 0) / 1000),
        call.get("disconnection_reason")))
    print("  agent v{}   from {}".format(
        call.get("agent_version"),
        "[number]" if args.redact else call.get("from_number")))
    print("  latency  : {}".format(latency_of(call)))
    if dv:
        print("  vars     : {}".format(dv))
    if an.get("call_successful") is not None:
        print("  successful: {}".format(an.get("call_successful")))
    if an.get("user_sentiment"):
        print("  sentiment : {}".format(an.get("user_sentiment")))
    if not args.summary:
        print("-" * 78)
        print(tr.strip() or "(no transcript)")
    print()


def main():
    p = argparse.ArgumentParser(description="Read real Retell calls.")
    p.add_argument("--client", required=True, help="client folder name")
    p.add_argument("--agent", required=True, help="agent slug under <client>/agents/")
    p.add_argument("--version", type=int, default=None,
                   help="only calls handled by this agent version")
    p.add_argument("--limit", type=int, default=15)
    p.add_argument("--call", default=None, help="one call id")
    p.add_argument("--summary", action="store_true",
                   help="headers only, no transcripts")
    p.add_argument("--redact", action="store_true",
                   help="mask phone numbers in the output")
    a = p.parse_args()

    env = load_env()
    client = RetellClient(env)
    cfg = agent_config(a.client, a.agent)
    agent_id = cfg.get("agent_id") or cfg.get("id")

    if a.call:
        calls = [client._request("GET", "/v2/get-call/{}".format(a.call))]
    else:
        if not agent_id:
            raise RetellError(
                "no agent_id for agent {!r}. Pass --call, or add the id to "
                ".env / agent-settings.json".format(a.agent))
        calls = fetch(client, agent_id, a.version, a.limit)

    print("{} call(s){}".format(
        len(calls), " on v{}".format(a.version) if a.version else ""))
    print()
    for c in calls:
        print_call(c, a)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RetellError as e:
        print("ERROR: {}".format(e))
        sys.exit(2)
