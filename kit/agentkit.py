#!/usr/bin/env python3
"""Agent-level settings, delivery proof, and real call review. Read-only.

WHY THIS EXISTS, AND IT IS THE MOST IMPORTANT FILE HERE

A conversation flow and a prompt are only half of an agent. Voice, latency,
interruption sensitivity, boosted keywords, post_call_analysis_data, and
above all `webhook_url` live on the AGENT object. None of it is in the flow
and none of it is in the prompt.

That means every flow test, every prompt lint, and every sandbox chat can be
green while the client receives nothing at all.

This is not hypothetical. On one real project an agent was published with
`webhook_url` unset and stayed that way for three days. Leads were collected
perfectly and forwarded nowhere. Four separate test tools were green the
whole time, because not one of them could see a setting that lives on the
agent rather than in the flow.

Worse: Retell omits null fields from a response, so a cleared webhook does
not appear as `webhook_url: null`. It appears as a DELETED LINE in a diff,
which reads like tidying.

`deliver` is the answer to one question: if a real caller rang right now,
would the client hear about it?

WHAT IT DOES NOT DO

It never fires the webhook. Sending a test event would deliver a fake lead
to a real client. And a 200 from the receiving end means the workflow
started, not that an email arrived. Only the client's inbox proves that.

PRIVACY

`calls` prints real transcripts. They carry names, phone numbers, and
addresses. Terminal only. Never paste them into a repository, a changelog,
or an agent prompt. `--redact` masks the obvious identifiers.

Usage:
    python agentkit.py show    --agent-id agent_xxx
    python agentkit.py save    --agent-id agent_xxx --out settings.json
    python agentkit.py versions --agent-id agent_xxx
    python agentkit.py deliver --agent-id agent_xxx
    python agentkit.py calls   --agent-id agent_xxx --limit 5 --redact
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from retellkit import RetellClient, RetellError  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

# Settings worth reading before touching anything. Grouped the way you
# actually reason about them, not the way the API returns them.
GROUPS = [
    ("delivery, the part no flow test can see",
     ["webhook_url", "webhook_events", "post_call_analysis_model"]),
    ("voice", ["voice_id", "voice_model", "voice_speed", "voice_temperature",
               "volume", "fallback_voice_ids", "language"]),
    ("turn taking", ["interruption_sensitivity", "responsiveness",
                     "enable_backchannel", "backchannel_frequency",
                     "backchannel_words", "reminder_trigger_ms",
                     "reminder_max_count", "begin_message_delay_ms",
                     "ring_duration_ms"]),
    ("transcription", ["boosted_keywords", "denoising_mode",
                       "stt_mode", "vocab_specialization",
                       "allow_user_dtmf", "user_dtmf_options"]),
    ("limits", ["max_call_duration_ms", "end_call_after_silence_ms",
                "normalize_for_speech", "data_storage_setting",
                "opt_out_sensitive_data_storage"]),
]

PHONE = re.compile(r"\+?\d[\d\-\(\)\s]{8,}\d")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def redact(text):
    text = PHONE.sub("[phone]", text or "")
    return EMAIL.sub("[email]", text)


def engine_of(agent):
    eng = agent.get("response_engine") or {}
    kind = eng.get("type")
    if kind == "conversation-flow":
        return f"conversation-flow {eng.get('conversation_flow_id')} " \
               f"v{eng.get('version')}"
    if kind == "retell-llm":
        return f"retell-llm {eng.get('llm_id')} v{eng.get('version')}"
    return str(kind)


# --------------------------------------------------------------------------
def cmd_show(a):
    client = RetellClient()
    agent = client.get_agent(a.agent_id, a.version)
    print(f"{agent.get('agent_name')}")
    print(f"  agent_id : {agent.get('agent_id')}")
    print(f"  version  : {agent.get('version')}  "
          f"published={bool(agent.get('is_published'))}")
    print(f"  engine   : {engine_of(agent)}")
    for title, keys in GROUPS:
        print(f"\n  -- {title} --")
        for k in keys:
            if k in agent:
                val = agent[k]
                if isinstance(val, (list, dict)):
                    val = json.dumps(val, ensure_ascii=False)
                    if len(val) > 90:
                        val = val[:87] + "..."
                print(f"    {k:<32} {val}")
    pcad = agent.get("post_call_analysis_data") or []
    print(f"\n  -- post_call_analysis_data: {len(pcad)} field(s) --")
    for f in pcad[:40]:
        print(f"    {f.get('name'):<34} {f.get('type')}")
    if len(pcad) > 40:
        print(f"    ... and {len(pcad) - 40} more")
    return 0


def cmd_save(a):
    client = RetellClient()
    agent = client.get_agent(a.agent_id, a.version)
    # last_modification_timestamp changes on every read and makes every diff
    # noisy, which trains people to skip reading diffs. Drop it.
    agent.pop("last_modification_timestamp", None)
    Path(a.out).write_text(json.dumps(agent, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print(f"wrote {a.out}")
    print("Commit this and diff it after any dashboard edit. Any change in "
          "the diff is drift between the repo and the live agent.")
    return 0


def cmd_versions(a):
    client = RetellClient()
    # list_agent_versions rows are summaries (no webhook_url, no
    # response_engine), so each version is read in full.
    rows = [dict(client.get_agent(a.agent_id, r.get("version")),
                 is_published=r.get("is_published"))
            for r in client.list_agent_versions(a.agent_id)]
    print(f"{'ver':>5}  {'state':<10} {'webhook':<8} engine")
    for r in rows:
        eng = r.get("response_engine") or {}
        # Retell OMITS null fields, so a cleared webhook is an ABSENT key,
        # not a null one. "-" below means the lead goes nowhere.
        hook = "set" if r.get("webhook_url") else "NONE"
        state = "PUBLISHED" if r.get("is_published") else "draft"
        print(f"{r.get('version'):>5}  {state:<10} {hook:<8} "
              f"{eng.get('type')} v{eng.get('version')}")
    missing = [r.get("version") for r in rows if not r.get("webhook_url")]
    if missing:
        print(f"\nWARNING: no webhook_url on version(s): "
              f"{', '.join(map(str, missing))}")
        print("Any call served by one of those forwarded nothing.")
    return 0


# --------------------------------------------------------------------------
def cmd_deliver(a):
    """Six checks. Each can break on its own. Exit 1 on any failure."""
    client = RetellClient()
    agent = client.get_agent(a.agent_id, a.version)
    ver = agent.get("version")
    fails = []

    def check(ok, label, detail=""):
        print(f"  {'PASS' if ok else 'FAIL'}  {label}")
        if detail:
            print(f"        {detail}")
        if not ok:
            fails.append(label)

    print(f"delivery check: {agent.get('agent_name')} version {ver}\n")

    hook = agent.get("webhook_url")
    check(bool(hook), "1. webhook_url is set on this version",
          hook or "EMPTY. Every recap for this version goes nowhere. "
                  "Retell omits null fields, so this shows up in a diff as a "
                  "deleted line, not as a fault.")

    events = agent.get("webhook_events") or []
    check("call_analyzed" in events,
          "2. webhook_events includes call_analyzed",
          f"got {events or 'nothing'}. Without call_analyzed the recap "
          f"fields are not in the payload, only the raw call.")

    pcad = agent.get("post_call_analysis_data") or []
    check(bool(pcad), "3. post_call_analysis_data is not empty",
          f"{len(pcad)} field(s)")

    if a.expect:
        want = set(a.expect.split(","))
        have = {f.get("name") for f in pcad}
        gone = sorted(want - have)
        check(not gone, "4. every expected recap field is present",
              f"missing: {', '.join(gone)}" if gone else "all present")
    else:
        print("  skip  4. expected recap fields "
              "(pass --expect name1,name2 to check)")

    published = [r for r in client.list_agent_versions(a.agent_id)
                 if r.get("is_published")]
    live = max(published, key=lambda r: r.get("version", 0)) if published else None
    if live:
        # summary row has no webhook_url; read the full published version
        live = client.get_agent(a.agent_id, live.get("version"))
        live_hook = bool(live.get("webhook_url"))
        check(live_hook,
              f"5. the LIVE published version ({live.get('version')}) has a "
              f"webhook_url",
              "" if live_hook else
              "This is the version real callers reach. A webhook on the "
              "draft does not help them.")
    else:
        check(False, "5. an agent version is published",
              "No published version. No phone number can be serving this "
              "agent yet.")

    try:
        calls = client.list_calls({"agent_id": [a.agent_id]}, limit=a.calls)
        analysed = [c for c in calls if c.get("call_analysis")]
        check(bool(analysed),
              f"6. recent calls came back with call_analysis populated",
              f"{len(analysed)} of {len(calls)} recent call(s). This is the "
              f"end-to-end proof: Retell ran the analysis and had something "
              f"to send.")
    except RetellError as exc:
        check(False, "6. recent calls carry call_analysis", str(exc))

    print(f"\n  {len(fails)} failure(s)")
    if fails:
        print("  A lead would NOT reach the client right now.")
        return 1
    print("  Retell's side is sound. That does NOT prove an email arrived. "
          "Only the client's inbox proves that.")
    return 0


# --------------------------------------------------------------------------
def cmd_calls(a):
    client = RetellClient()
    filt = {"agent_id": [a.agent_id]}
    if a.version is not None:
        filt["version"] = [a.version]
    calls = client.list_calls(filt, limit=a.limit)
    if not calls:
        print("no calls found for that filter")
        return 0
    print(f"{len(calls)} call(s)\n")
    print("PRIVACY: this output carries caller names, numbers and addresses. "
          "Terminal only. Never paste it into a repository.\n")
    for c in calls:
        print("=" * 68)
        print(f"call {c.get('call_id')}  agent v{c.get('agent_version')}  "
              f"{c.get('call_status')}  "
              f"{round((c.get('duration_ms') or 0) / 1000)}s  "
              f"disconnect={c.get('disconnection_reason')}")
        if a.summary:
            an = c.get("call_analysis") or {}
            print(f"  summary : {an.get('call_summary')}")
            print(f"  success : {an.get('call_successful')}")
            custom = an.get("custom_analysis_data") or {}
            for k, v in sorted(custom.items()):
                print(f"  {k:<30} {v!r}")
            continue
        for t in (c.get("transcript_object") or []):
            who = "AGENT" if t.get("role") == "agent" else "CALLER"
            text = t.get("content") or ""
            print(f"  {who:>6}: {redact(text) if a.redact else text}")
    return 0


# --------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Agent-level settings, delivery proof, call review. "
                    "Read-only. Never writes to Retell.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    for name, fn, helptext in (
            ("show", cmd_show, "print the settings that matter, grouped"),
            ("save", cmd_save, "snapshot the whole agent object to a file"),
            ("versions", cmd_versions, "every version, and which have a webhook"),
            ("deliver", cmd_deliver, "prove a lead can reach the client"),
            ("calls", cmd_calls, "print what real callers actually heard")):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("--agent-id", required=True)
        p.add_argument("--version", type=int, default=None)
        if name == "save":
            p.add_argument("--out", required=True)
        if name == "deliver":
            p.add_argument("--calls", type=int, default=10)
            p.add_argument("--expect",
                           help="comma-separated recap field names that must "
                                "exist in post_call_analysis_data")
        if name == "calls":
            p.add_argument("--limit", type=int, default=5)
            p.add_argument("--summary", action="store_true",
                           help="recap fields instead of the transcript")
            p.add_argument("--redact", action="store_true",
                           help="mask phone numbers and emails")
        p.set_defaults(fn=fn)

    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RetellError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
