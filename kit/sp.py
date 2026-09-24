#!/usr/bin/env python3
"""Single-prompt Retell agent driver: build, lint, sandbox-chat, push, clean up.

WHAT THIS IS

The thing that lets an agent actually DRIVE a single-prompt Retell agent
instead of describing one. Retell will not drive a voice agent over the API.
It will drive a CHAT agent. So every test here is a text conversation against
a throwaway copy, and the transcript is the evidence.

THE TRAP THIS AVOIDS

create-chat-agent will not accept a version. Point a chat agent at your real
llm_id and Retell hands it VERSION 0 of that LLM -- the very first version
ever saved, not the draft you are testing. Silently. Every answer looks
plausible and none of it is about your current prompt.

The fix, and the reason `chat` always takes a FILE or makes a copy: POST the
prompt object to /create-retell-llm as a brand new throwaway. The throwaway
is version 0, the chat agent is version 0, and the two line up. It also means
testing can never touch production.

Everything created is named with the SANDBOX_PREFIX below and recorded in
.retell-sandbox.json, so `cleanup` can always find it, even after a crash.

COSTS MONEY

Every chat message is billed. `chat` prints the estimate before sending and
needs --yes above CHEAP_TURNS turns.

GUARDS

  * Dry run is the default. `push` prints and stops; `push --push` writes.
  * Writes the DRAFT only. Nothing here publishes, ever.
  * Refuses to push to an llm_id whose version is published.
  * Never prints the API key.

Usage:
    python sp.py new --from prompt.md --out llm.json
    python sp.py new --from prompt.md --out llm.json --begin "Hi, this is Kate."
    python sp.py pull --llm-id llm_xxx --out llm.json
    python sp.py chat --file llm.json -m "hello" -m "my car won't start"
    python sp.py chat --llm-id llm_xxx -m "hello"          # copies it first
    python sp.py push --file llm.json --new
    python sp.py push --file llm.json --llm-id llm_xxx --push
    python sp.py cleanup
    python sp.py cleanup --yes
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from retellkit import (RetellClient, RetellError, load_env,  # noqa: E402
                       project_root)
import promptlint  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

SANDBOX_PREFIX = "ZZ-SANDBOX-promptkit"
STATE_FILE = ".retell-sandbox.json"
CENTS_PER_MESSAGE = 0.7      # Retell chat pricing, working estimate
CHEAP_TURNS = 5              # above this, --yes is required

# Fields that belong on a Retell LLM object. Anything else is dropped before
# a create or update, because the API rejects unknown keys.
LLM_FIELDS = (
    "general_prompt", "begin_message", "general_tools", "states",
    "starting_state", "default_dynamic_variables", "knowledge_base_ids",
    "model", "model_temperature", "model_high_priority",
    "tool_call_strict_mode", "start_speaker", "kb_config", "mcps",
)


# --------------------------------------------------------------------------
# sandbox bookkeeping
# --------------------------------------------------------------------------
def state_path():
    return project_root() / STATE_FILE


def read_state():
    p = state_path()
    if not p.exists():
        return {"llms": [], "chat_agents": []}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {"llms": [], "chat_agents": []}


def record(kind, obj_id):
    st = read_state()
    if obj_id not in st.setdefault(kind, []):
        st[kind].append(obj_id)
    state_path().write_text(json.dumps(st, indent=2) + "\n", encoding="utf-8")


def forget(kind, obj_id):
    st = read_state()
    st[kind] = [x for x in st.get(kind, []) if x != obj_id]
    state_path().write_text(json.dumps(st, indent=2) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------
# building
# --------------------------------------------------------------------------
def clean_llm(obj):
    """Keep only fields the API accepts on create/update."""
    return {k: v for k, v in dict(obj).items()
            if k in LLM_FIELDS and v not in (None, [], {})}


def load_llm_file(path):
    raw = Path(path).read_text(encoding="utf-8", errors="replace")
    if raw.lstrip().startswith("{"):
        return json.loads(raw)
    return {"general_prompt": raw}


def cmd_new(a):
    """Turn a prompt document into a Retell LLM object, then lint it."""
    text = Path(a.from_file).read_text(encoding="utf-8", errors="replace")
    obj = {
        "general_prompt": text,
        "model": a.model,
        "model_temperature": a.temperature,
        "begin_message": a.begin if a.begin is not None else "",
        "start_speaker": "agent" if a.begin else "user",
    }
    out = Path(a.out)
    out.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(f"wrote {out}")
    print(f"  prompt      : {len(text)} chars, about {len(text)//4} tokens")
    print(f"  model       : {a.model}  temperature {a.temperature}")
    print(f"  begin_message: {obj['begin_message']!r}")
    print(f"  start_speaker: {obj['start_speaker']}")
    print()
    rep, meta, tokens = promptlint.lint(out)
    return promptlint.render(rep, meta, tokens, str(out))


def cmd_pull(a):
    client = RetellClient()
    obj = client.get_llm(a.llm_id, a.version)
    out = Path(a.out)
    out.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(f"llm {obj.get('llm_id')} version {obj.get('version')} "
          f"published={bool(obj.get('is_published'))}")
    print(f"  general_prompt: {len(obj.get('general_prompt') or '')} chars")
    print(f"  states        : {len(obj.get('states') or [])}")
    print(f"wrote {out}")
    return 0


# --------------------------------------------------------------------------
# the sandbox
# --------------------------------------------------------------------------
class Sandbox:
    """A throwaway LLM plus a throwaway chat agent. Always version 0."""

    def __init__(self, client, llm_obj, label="run"):
        self.client = client
        body = clean_llm(llm_obj)
        body.setdefault("general_prompt", "")
        self.llm = client.create_llm(body)
        self.llm_id = self.llm["llm_id"]
        record("llms", self.llm_id)
        self.agent = client.create_chat_agent(
            {"type": "retell-llm", "llm_id": self.llm_id},
            agent_name=f"{SANDBOX_PREFIX} {label} {int(time.time())}")
        self.agent_id = self.agent["agent_id"]
        record("chat_agents", self.agent_id)
        self.chat_id = None

    def start(self, dynamic_variables=None):
        chat = self.client.create_chat(self.agent_id, dynamic_variables)
        self.chat_id = chat["chat_id"]
        return chat

    def say(self, text):
        """Send one caller turn. Returns the agent's reply messages."""
        out = self.client.chat_completion(self.chat_id, text)
        msgs = out.get("messages") or []
        return [m.get("content", "") for m in msgs
                if m.get("role") in ("agent", "assistant")]

    def finish(self):
        """End, then read. collected_dynamic_variables fills in only AFTER
        the chat ends, so this order is not optional."""
        try:
            self.client.end_chat(self.chat_id)
        except RetellError:
            pass
        try:
            return self.client.get_chat(self.chat_id)
        except RetellError:
            return {}

    def destroy(self):
        for fn, kind, obj_id in ((self.client.delete_chat_agent, "chat_agents",
                                  self.agent_id),
                                 (self.client.delete_llm, "llms", self.llm_id)):
            try:
                fn(obj_id)
                forget(kind, obj_id)
            except RetellError as exc:
                print(f"  WARN could not delete {obj_id}: {exc}", file=sys.stderr)


def cmd_chat(a):
    client = RetellClient()

    if a.file:
        llm_obj = load_llm_file(a.file)
        source = a.file
    else:
        # Copying is deliberate. Pointing a chat agent at a live llm_id
        # silently downgrades it to version 0. See the module docstring.
        llm_obj = client.get_llm(a.llm_id, a.version)
        source = f"{a.llm_id} v{llm_obj.get('version')}"
        print(f"copied {source} into a throwaway so the chat agent cannot "
              f"silently fall back to version 0")

    turns = list(a.message)
    if not turns:
        print("ERROR: give at least one -m/--message", file=sys.stderr)
        return 2
    est = (len(turns) + 1) * CENTS_PER_MESSAGE
    print(f"source : {source}")
    print(f"turns  : {len(turns)}   estimated cost ~{est:.1f} cents")
    if len(turns) > CHEAP_TURNS and not a.yes:
        print(f"ERROR: more than {CHEAP_TURNS} turns needs --yes",
              file=sys.stderr)
        return 2

    box = Sandbox(client, llm_obj, label=a.label)
    print(f"sandbox: llm {box.llm_id}  chat agent {box.agent_id}")
    lines = []
    try:
        box.start(json.loads(a.seed) if a.seed else None)
        # TRAP, confirmed live 2026-08-29: create-chat returns NO messages.
        # Its keys are agent_id, agent_name, agent_version, chat_cost,
        # chat_id, chat_status, chat_type, data_storage_setting,
        # start_timestamp -- and nothing else. So begin_message never
        # arrives as its own first turn here; the agent folds it into its
        # reply to turn one instead.
        # CONSEQUENCE: a text sandbox can show you WHAT the greeting says.
        # It can never show you WHETHER the agent speaks first. Only a real
        # call proves that. Do not read a clean transcript as proof the
        # greeting fires on pickup.
        for turn in turns:
            lines.append(("CALLER", turn))
            for reply in box.say(turn):
                lines.append(("AGENT", reply))
        final = box.finish()
    finally:
        box.destroy()
        print("sandbox destroyed")

    print()
    print("=" * 68)
    for who, text in lines:
        print(f"{who:>6}: {text}")
    print("=" * 68)
    print("NOTE: a text sandbox cannot show whether the agent speaks first, "
          "and cannot express silence. Both need a real call.")
    collected = (final or {}).get("collected_dynamic_variables") or {}
    if collected:
        print("\ncollected_dynamic_variables:")
        for k, v in sorted(collected.items()):
            print(f"  {k} = {v!r}")

    if a.out:
        Path(a.out).write_text(
            json.dumps({"source": source, "turns": turns,
                        "transcript": [{"role": w, "content": t} for w, t in lines],
                        "collected_dynamic_variables": collected},
                       indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\nwrote {a.out}")
        print("NOTE: a real transcript carries caller PII. Keep this file "
              "out of any repository.")
    return 0


# --------------------------------------------------------------------------
# push
# --------------------------------------------------------------------------
def cmd_push(a):
    client = RetellClient()
    obj = load_llm_file(a.file)
    body = clean_llm(obj)

    print(f"source file : {a.file}")
    print(f"prompt      : {len(body.get('general_prompt') or '')} chars, "
          f"about {len(body.get('general_prompt') or '')//4} tokens")
    print(f"fields sent : {', '.join(sorted(body))}")

    rep, meta, tokens = promptlint.lint(a.file)
    fails = len(rep.fails())
    print()
    promptlint.render(rep, meta, tokens, a.file)
    if fails and not a.force:
        print(f"\nREFUSING: promptlint reports {fails} failure(s). "
              f"Fix them, or pass --force with a stated reason.",
              file=sys.stderr)
        return 1

    if a.new:
        target = "a NEW Retell LLM (create-retell-llm)"
    else:
        if not a.llm_id:
            print("ERROR: give --llm-id, or --new to create one",
                  file=sys.stderr)
            return 2
        current = client.get_llm(a.llm_id, a.version)
        if current.get("is_published"):
            print(f"\nREFUSING: llm {a.llm_id} version "
                  f"{current.get('version')} is PUBLISHED. Published versions "
                  f"are immutable and carry live calls. Target a draft.",
                  file=sys.stderr)
            return 1
        target = (f"the DRAFT of {a.llm_id} version {current.get('version')} "
                  f"(update-retell-llm)")

    if not a.push:
        print(f"\nDRY RUN. Would write to {target}.")
        print("Re-run with --push to write. Nothing was sent.")
        return 0

    print(f"\nwriting to {target} ...")
    if a.new:
        out = client.create_llm(body)
        print(f"created llm_id {out.get('llm_id')} version {out.get('version')}")
    else:
        out = client.update_llm(a.llm_id, body, a.version)
        print(f"updated {out.get('llm_id')} version {out.get('version')}")

    # Never trust that a write landed. Read it back.
    fresh = client.get_llm(out["llm_id"], out.get("version"))
    same = (fresh.get("general_prompt") or "") == (body.get("general_prompt") or "")
    print(f"read back   : {len(fresh.get('general_prompt') or '')} chars, "
          f"prompt matches: {same}")
    if not same:
        print("WARN: the server copy does not match what was sent. "
              "Do not describe this change as landed.", file=sys.stderr)
        return 1
    print("NOT PUBLISHED. This wrote a draft only.")
    return 0


# --------------------------------------------------------------------------
# cleanup
# --------------------------------------------------------------------------
def cmd_cleanup(a):
    client = RetellClient()
    st = read_state()
    tracked_agents = list(st.get("chat_agents", []))
    tracked_llms = list(st.get("llms", []))

    # Also sweep by name, in case a crash happened before the state was saved.
    swept = []
    try:
        for row in client.list_agents(limit=200):
            name = row.get("agent_name") or ""
            if name.startswith(SANDBOX_PREFIX) and row["agent_id"] not in tracked_agents:
                swept.append(row["agent_id"])
    except RetellError as exc:
        print(f"  (name sweep skipped: {exc})")

    targets = [("chat agent", i) for i in tracked_agents + swept]
    targets += [("llm", i) for i in tracked_llms]

    if not targets:
        print("clean: no sandbox objects left behind")
        return 0

    for kind, obj_id in targets:
        print(f"  would delete {kind} {obj_id}")
    if not a.yes:
        print(f"\nDRY RUN. {len(targets)} object(s). Re-run with --yes to delete.")
        return 0

    for kind, obj_id in targets:
        try:
            if kind == "chat agent":
                client.delete_chat_agent(obj_id)
                forget("chat_agents", obj_id)
            else:
                client.delete_llm(obj_id)
                forget("llms", obj_id)
            print(f"  deleted {kind} {obj_id}")
        except RetellError as exc:
            print(f"  WARN {obj_id}: {exc}", file=sys.stderr)
    print("cleanup done")
    return 0


# --------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Single-prompt Retell agent driver. Dry run by default. "
                    "Never publishes.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("new", help="build an LLM object from a prompt document")
    p.add_argument("--from", dest="from_file", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--model", default="gpt-4.1")
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--begin", default=None,
                   help="exact opening line. Omit to let the caller speak first.")
    p.set_defaults(fn=cmd_new)

    p = sub.add_parser("pull", help="snapshot a live LLM to a file (read-only)")
    p.add_argument("--llm-id", required=True)
    p.add_argument("--version", type=int, default=None)
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_pull)

    p = sub.add_parser("chat", help="drive a throwaway copy over text")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--file", help="a local LLM json or prompt file")
    g.add_argument("--llm-id", help="a live LLM, copied into a throwaway first")
    p.add_argument("--version", type=int, default=None)
    p.add_argument("-m", "--message", action="append", default=[],
                   help="one caller turn. Repeat for each turn, in order.")
    p.add_argument("--seed", help="JSON dict of dynamic variables")
    p.add_argument("--label", default="run")
    p.add_argument("--out", help="write the transcript to this path (keep it "
                                 "outside any repository)")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(fn=cmd_chat)

    p = sub.add_parser("push", help="write a draft. Dry run unless --push.")
    p.add_argument("--file", required=True)
    p.add_argument("--llm-id")
    p.add_argument("--version", type=int, default=None)
    p.add_argument("--new", action="store_true", help="create instead of update")
    p.add_argument("--push", action="store_true", help="actually write")
    p.add_argument("--force", action="store_true",
                   help="push despite promptlint failures")
    p.set_defaults(fn=cmd_push)

    p = sub.add_parser("cleanup", help="delete every sandbox object")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(fn=cmd_cleanup)

    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RetellError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
