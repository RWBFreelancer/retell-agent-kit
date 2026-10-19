#!/usr/bin/env python3
"""Create a brand-new Retell agent: its response engine (a conversation
flow or a single-prompt LLM) and the agent object that carries voice,
webhook, and post-call settings. Dry run by default.

WHY ONE TOOL FOR BOTH OBJECTS

A flow or an LLM on its own takes no calls. The agent object is the half
that holds `voice_id`, `webhook_url`, `post_call_analysis_data`, and timing.
Creating the two by hand in two steps is how an agent ends up live with no
webhook. This tool creates both, reads both back, and writes the ids into
the client's AGENT.md so every other tool can find them.

GUARDS

  - Dry run by default. `--create` is required to write anything.
  - Refuses if AGENT.md already holds an agent_id: this tool never makes a
    second agent for the same slug. Edit the existing one with edit-agent.
  - Lints first: flowkit lint for a flow, promptlint for an LLM. Any FAIL
    refuses unless `--force`.
  - Refuses a settings file that is missing voice_id or agent_name, holds a
    placeholder (a value starting with "<"), or tries to set response_engine.
  - Warns when webhook_url is empty: the agent would deliver nothing.
  - If the agent create fails after the engine was created, deletes that
    fresh engine so nothing is left orphaned, and says so.
  - Never publishes. Never binds a phone number. Both stay with Rey, through
    the `publish` skill and the Retell dashboard.

COST

Creating objects is free. Every call or sandbox chat on the new agent is
billed. Run `cost-gate` before testing it.

Usage:
    python tools/agentcreate.py --list-voices [--provider elevenlabs]
    python tools/agentcreate.py --client acme --agent intake \\
        --flow clients/acme/agents/intake/build/flow.json \\
        --settings clients/acme/agents/intake/agent-settings.json
    python tools/agentcreate.py --client acme --agent faq \\
        --llm llm.json --settings agent-settings.json --create

The Retell account is the one RETELL_ACCOUNT selects (kit/accounts.py).
Start from templates/agent-settings.example.json.
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT / "kit"))
from retellkit import RetellClient, RetellError, clients_root, load_env  # noqa: E402
import flowkit  # noqa: E402
import promptlint  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

REQUIRED = ("agent_name", "voice_id")


def agent_dir(client, agent):
    croot = clients_root() / client
    if not croot.is_dir():
        raise RetellError(f"no client folder {croot}. Run the new-client skill first.")
    d = croot / "agents" / agent
    if not d.exists():
        shutil.copytree(KIT / "templates" / "client" / "agents" / "example-agent", d)
        md = d / "AGENT.md"
        md.write_text(md.read_text(encoding="utf-8").replace("example-agent", agent),
                      encoding="utf-8")
        print(f"made agent folder from the template: {d}")
    return d


def read_fields(md):
    out = {}
    for line in md.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^([a-z_]+):\s*(.*)$", line.strip())
        if m:
            out[m[1]] = m[2].strip()
    return out


def write_fields(md, fields):
    """Set `key: value` lines in place; add missing keys after the last one."""
    lines = md.read_text(encoding="utf-8").splitlines()
    done = set()
    for i, line in enumerate(lines):
        m = re.match(r"^([a-z_]+):", line.strip())
        if m and m[1] in fields:
            lines[i] = f"{m[1]}: {fields[m[1]]}"
            done.add(m[1])
    last = max([i for i, l in enumerate(lines) if re.match(r"^[a-z_]+:", l.strip())], default=len(lines) - 1)
    for k in [k for k in fields if k not in done]:
        last += 1
        lines.insert(last, f"{k}: {fields[k]}")
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def check_settings(s):
    problems = []
    for k in REQUIRED:
        if not str(s.get(k) or "").strip():
            problems.append(f"{k} is empty")
    for k, v in s.items():
        if isinstance(v, str) and v.startswith("<"):
            problems.append(f"{k} is still a placeholder: {v}")
    for k in ("response_engine", "agent_id", "version", "is_published"):
        if k in s:
            problems.append(f"{k} must not be in the settings file; this tool sets it")
    return problems


def list_voices(a):
    rows = RetellClient().list_voices()
    for v in rows:
        if a.provider and a.provider.lower() not in str(v.get("provider", "")).lower():
            continue
        print(f"{v.get('voice_id'):<34} {str(v.get('provider')):<11} "
              f"{str(v.get('gender')):<7} {str(v.get('accent') or ''):<12} {v.get('voice_name')}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--list-voices", action="store_true")
    ap.add_argument("--provider")
    ap.add_argument("--client")
    ap.add_argument("--agent", help="agent slug under <client>/agents/")
    eng = ap.add_mutually_exclusive_group()
    eng.add_argument("--flow", help="conversation flow JSON (API or dashboard shape)")
    eng.add_argument("--llm", help="single-prompt LLM JSON (from kit/sp.py new)")
    ap.add_argument("--settings", help="agent settings JSON")
    ap.add_argument("--create", action="store_true", help="write to Retell")
    ap.add_argument("--force", action="store_true", help="push past lint FAILs (say why)")
    a = ap.parse_args(argv)

    if a.list_voices:
        return list_voices(a)
    if not (a.client and a.agent and a.settings and (a.flow or a.llm)):
        ap.error("needs --client, --agent, --settings, and one of --flow / --llm")

    env = load_env()
    settings = json.loads(Path(a.settings).read_text(encoding="utf-8"))
    problems = check_settings(settings)
    if problems:
        print("REFUSING: the settings file is not ready:\n  - " + "\n  - ".join(problems),
              file=sys.stderr)
        return 1

    d = agent_dir(a.client, a.agent)
    md = d / "AGENT.md"
    have = read_fields(md)
    if have.get("agent_id"):
        print(f"REFUSING: {md} already names agent_id {have['agent_id']}. "
              f"This tool never makes a second agent for one slug.", file=sys.stderr)
        return 1

    # lint the engine
    if a.flow:
        engine_obj = flowkit.load(a.flow)
        rep = flowkit.lint_flow(engine_obj)
        flowkit.render(rep, a.flow)
        fails = len(rep.fails())
        kind = "conversation-flow"
    else:
        engine_obj = json.loads(Path(a.llm).read_text(encoding="utf-8"))
        rep, meta, tokens = promptlint.lint(a.llm)
        promptlint.render(rep, meta, tokens, a.llm)
        fails = len(rep.fails())
        kind = "single-prompt"
    if fails and not a.force:
        print(f"\nREFUSING: lint reports {fails} FAIL(s). Fix them, or --force with a reason.",
              file=sys.stderr)
        return 1

    print("\nPLAN")
    print(f"  retell account : {env.get('RETELL_ACCOUNT') or '(default key)'}")
    print(f"  client / agent : {a.client} / {a.agent}")
    print(f"  engine         : new {kind} from {a.flow or a.llm}")
    print(f"  agent_name     : {settings['agent_name']}")
    print(f"  voice_id       : {settings['voice_id']}")
    print(f"  webhook_url    : {'set' if settings.get('webhook_url') else 'EMPTY'}")
    print(f"  post-call data : {len(settings.get('post_call_analysis_data') or [])} field(s)")
    print(f"  other settings : {', '.join(sorted(set(settings) - {'agent_name', 'voice_id', 'webhook_url', 'post_call_analysis_data'})) or '-'}")
    if not settings.get("webhook_url"):
        print("  WARN: no webhook_url. Calls will be collected and delivered nowhere.")
    if not a.create:
        print("\nDRY RUN. Re-run with --create to write. Nothing was sent.")
        return 0

    client = RetellClient(env)
    if a.flow:
        made = client.create_flow(engine_obj)
        eid_key, eid = "flow_id", made["conversation_flow_id"]
        response_engine = {"type": "conversation-flow", "conversation_flow_id": eid}
    else:
        body = {k: v for k, v in engine_obj.items()
                if k not in ("llm_id", "version", "is_published", "last_modification_timestamp")}
        made = client.create_llm(body)
        eid_key, eid = "llm_id", made["llm_id"]
        response_engine = {"type": "retell-llm", "llm_id": eid}
    print(f"\ncreated {kind}: {eid}")

    try:
        agent = client.create_agent({**settings, "response_engine": response_engine})
    except RetellError as exc:
        print(f"agent create FAILED: {exc}", file=sys.stderr)
        (client.delete_flow if a.flow else client.delete_llm)(eid)
        print(f"deleted the fresh {kind} {eid} so nothing is orphaned.", file=sys.stderr)
        return 1
    aid = agent["agent_id"]
    print(f"created agent: {aid}")

    # Never trust that a write landed. Read both back.
    fresh = client.get_agent(aid)
    re_got = fresh.get("response_engine") or {}
    ok = re_got.get("conversation_flow_id" if a.flow else "llm_id") == eid
    ok &= (fresh.get("voice_id") == settings["voice_id"])
    ok &= (fresh.get("webhook_url") or "") == (settings.get("webhook_url") or "")
    print(f"read back    : engine {'matches' if ok else 'DOES NOT MATCH'}, "
          f"voice and webhook {'match' if ok else 'check by hand'}")

    write_fields(md, {"agent_id": aid, eid_key: eid, "type": kind,
                      "retell_account": env.get("RETELL_ACCOUNT") or "default"})
    print(f"wrote ids to : {md}")
    if a.flow:
        exp = d / "exports"
        exp.mkdir(exist_ok=True)
        flow = client.get_flow(eid)
        path = exp / f"v{flow.get('version', 0)}.json"
        if not path.exists():
            path.write_text(json.dumps(flow, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"first export : {path}")
    print("\nNOT PUBLISHED. No phone number bound. Next: tracerun or retell_chat "
          "(after cost-gate), then the publish skill, then delivery-check.")
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RetellError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
