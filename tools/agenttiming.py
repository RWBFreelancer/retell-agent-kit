#!/usr/bin/env python3
"""Set the turn-taking fields on the AGENT. Dry run by default. Never publishes.

WHAT IT SETS

    responsiveness            -> --responsiveness
    interruption_sensitivity  -> --interruption-sensitivity

BOTH FIELDS LIVE ON THE AGENT, NOT ON THE FLOW, so `flowapply.py` and every
flow transform are blind to them, the same way they are blind to
`post_call_analysis_data` and `webhook_url`.

READ THE DIRECTIONS CAREFULLY BEFORE PICKING VALUES. THEY DO NOT BOTH MOVE
THE SAME WAY IN CALLER EXPERIENCE.

    responsiveness           lower = faster replies, but more risk of
                              cutting the caller off before they finish.
    interruption_sensitivity higher = easier for a caller (or noise) to
                              interrupt the agent mid-sentence.

Get a real latency measurement (asr, llm, tts, e2e, p50) on recent calls
before changing `responsiveness`, and know whether the goal is speed or
tolerance for background noise before changing `interruption_sensitivity`.
See `check-agent-data` for how to measure real-call latency.

GUARDS

  - Dry run by default. `--push` is required to PATCH.
  - Refuses unless the latest agent version is a DRAFT. Never PATCHes the
    version carrying live calls.
  - Prints every field it will change, old value to new value.
  - Snapshots the agent to <client>/agents/<agent>/exports/ before writing.
  - Touches only the two fields named above.
  - Never publishes.

USAGE

    python tools/agenttiming.py --client acme --agent intake --responsiveness 0.95
    python tools/agenttiming.py --client acme --agent intake \\
        --responsiveness 0.95 --interruption-sensitivity 0.8 --push

REVERSAL

  Set them back to the values in the pre-change snapshot under
  <client>/agents/<agent>/exports/.

AFTER PUBLISHING

  Run `delivery-check`, then re-measure `e2e` on real calls. A settings
  change that is never measured on a real call is a guess that has been
  written down.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "kit"))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

from retellkit import RetellClient, RetellError, agent_config, load_env


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--client", required=True, help="client folder name")
    ap.add_argument("--agent", required=True, help="agent slug under <client>/agents/")
    ap.add_argument("--responsiveness", type=float, default=None,
                    help="0 to 1. Retell default is 1 (fastest).")
    ap.add_argument("--interruption-sensitivity", type=float, default=None,
                    help="0 to 1. Retell default is 1 (easiest to interrupt).")
    ap.add_argument("--push", action="store_true",
                    help="actually PATCH the draft agent. Never publishes.")
    args = ap.parse_args(argv)
    target = {}
    if args.responsiveness is not None:
        target["responsiveness"] = args.responsiveness
    if args.interruption_sensitivity is not None:
        target["interruption_sensitivity"] = args.interruption_sensitivity
    if not target:
        raise SystemExit("pass --responsiveness and/or --interruption-sensitivity")

    load_env()
    cfg = agent_config(args.client, args.agent)
    client = RetellClient()
    agent_id = cfg["agent_id"]

    print("=" * 74)
    print("agenttiming  |  agent %s  |  %s" % (args.agent.upper(), agent_id))
    print("=" * 74)

    versions = client.list_agent_versions(agent_id)
    if not versions:
        raise RetellError("no agent versions returned")
    latest = versions[0]
    if latest.get("is_published"):
        raise SystemExit(
            "agent v%s is PUBLISHED and may be carrying live calls. Create a "
            "draft first with create_agent_version, then re-run. Never PATCH "
            "the version serving traffic." % latest.get("version"))
    print("  agent v%s is a DRAFT. OK." % latest.get("version"))

    agent = client.get_agent(agent_id)

    print("\n  field                      live      ->  new")
    print("  " + "-" * 52)
    changes = {}
    for k, want in target.items():
        have = agent.get(k)
        mark = "same" if have == want else ""
        print("  %-26s %-9s ->  %-7s %s" % (k, have, want, mark))
        if have != want:
            changes[k] = want

    print("\n  DIRECTION CHECK")
    for k, want in target.items():
        have = agent.get(k)
        if have == want:
            continue
        word = "SLOWER, waits longer" if k == "responsiveness" else \
               "EASIER to interrupt" if want > have else "HARDER to interrupt"
        arrow = "up" if want > have else "down"
        print("    %s goes %s (%s -> %s): %s" % (k, arrow, have, want, word))

    # context that is not being changed, but decides what this feels like
    print("\n  NOT CHANGED, but relevant")
    for k in ("enable_dynamic_responsiveness", "denoising_mode", "stt_mode",
              "reminder_trigger_ms", "reminder_max_count",
              "begin_message_delay_ms"):
        if k in agent:
            print("    %-32s %r" % (k, agent[k]))

    if not changes:
        print("\n  Nothing to change. Both fields already hold the target values.")
        return 0

    snap = Path(cfg["exports"]) / ("v%s-agent-pre-timing.json" % latest.get("version"))
    snap.parent.mkdir(parents=True, exist_ok=True)
    snap.write_text(json.dumps(agent, indent=2, ensure_ascii=False),
                    encoding="utf-8")
    print("\n  snapshot: %s" % snap)

    if not args.push:
        print("\nDRY RUN. Nothing was written to Retell.")
        print("To write the DRAFT, re-run with --push. Publishing stays manual.")
        return 0

    client.update_agent(agent_id, changes)
    print("\n  PATCHed the draft agent.")

    back = client.get_agent(agent_id)
    ok = True
    print("\n  VERIFY, from a fresh GET")
    for k, want in target.items():
        got = back.get(k)
        good = got == want
        ok = ok and good
        print("    %-26s %-8s %s" % (k, got, "MATCHES" if good else "DOES NOT MATCH"))
    print("    agent version now          v%s" % back.get("version"))

    post = Path(cfg["exports"]) / ("v%s-agent-post-timing.json" % back.get("version"))
    post.write_text(json.dumps(back, indent=2, ensure_ascii=False),
                    encoding="utf-8")
    print("    snapshot: %s" % post)
    print("\n  NOT PUBLISHED. Publish by hand, then run delivery-check")
    print("  and re-measure e2e on real calls.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
