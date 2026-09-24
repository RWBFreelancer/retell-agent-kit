#!/usr/bin/env python3
"""Conversation-flow driver: lint offline, pull, sandbox-chat, push a draft.

WHAT THIS IS

The flow half of the kit. It works on any Retell conversation flow, for any
client, and its `lint` command needs no API key at all.

IF THE CLIENT ALREADY HAS AN AGENT AND A TEST SUITE

Prefer the repo's own `tools/` scripts over this file's built-in commands
where both exist: `tools/flowlint.py`, `tools/flowdiff.py`,
`tools/flowapply.py`, `tools/tracerun.py`, `tools/askcheck.py`,
`tools/simtest.py`. They read a client's own trace and scenario files.
This file is the offline-first fallback for a client with no tooling yet.

THE FOUR EXIT KINDS

A Retell node can leave by FOUR different fields, not one:

    edges                a list of conditional transitions
    else_edge            taken when no edge matched
    always_edge          taken unconditionally
    skip_response_edge   node speaks its line and moves on without waiting

A checker that reads only `edges` reports live nodes as dead ends. That
mistake produced two false findings on a real project before anyone noticed
`skip_response_edge` existed. Every walk in this file uses all four.

THE SANDBOX TRAP

create-chat-agent will not accept a version. Point a chat agent at your real
conversation_flow_id and Retell hands it VERSION 0 of that flow, silently.
So `chat` always POSTs the flow object to /create-conversation-flow first and
drives the throwaway copy. That also means testing can never touch
production.

GUARDS

  * lint is offline and read-only.
  * pull only reads.
  * push is a dry run unless --push, refuses a published version, and never
    publishes.
  * cleanup removes every sandbox object this kit made.

Usage:
    python flowkit.py lint flow.json
    python flowkit.py lint flow.json --line "exact spoken sentence"
    python flowkit.py pull --flow-id conversation_flow_xxx --out flow.json
    python flowkit.py chat --file flow.json -m "hello" -m "my car won't start"
    python flowkit.py push --file flow.json --flow-id conversation_flow_xxx
    python flowkit.py cleanup --yes
"""
import argparse
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from retellkit import RetellClient, RetellError  # noqa: E402
import sp as spkit  # noqa: E402  (reuses the sandbox bookkeeping)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

EDGE_KINDS = ("edges", "else_edge", "always_edge", "skip_response_edge")
SANDBOX_PREFIX = spkit.SANDBOX_PREFIX
VAR_RE = re.compile(r"\{\{\s*([A-Za-z_][\w.]*)\s*\}\}")


# --------------------------------------------------------------------------
# reading a flow
# --------------------------------------------------------------------------
def load(path):
    """Find the ConversationFlow object inside whatever file you were given.

    Three shapes turn up in real projects and they are NOT the same:

      1. the API shape       -- the flow object itself, with "nodes" at top
      2. the DASHBOARD shape -- a whole Agent export that nests the flow
                                under "conversationFlow". Note the camelCase.
                                The API uses snake_case everywhere else, so
                                a loader that only looks for
                                "conversation_flow" silently reports
                                "flow has no nodes" on a perfectly good file.
      3. a fragment          -- a bare list, such as an exported
                                post_call_analysis_data. Not a flow at all.
    """
    obj = json.loads(Path(path).read_text(encoding="utf-8", errors="replace"))
    if isinstance(obj, list):
        raise RetellError(
            f"{path} holds a JSON list, not a conversation flow. "
            f"It is probably a field fragment such as "
            f"post_call_analysis_data. Point at a flow or agent export.")
    if "nodes" in obj:
        return obj
    for key in ("conversationFlow", "conversation_flow", "response_engine"):
        nested = obj.get(key)
        if isinstance(nested, dict) and "nodes" in nested:
            return nested
    raise RetellError(
        f"{path} has no 'nodes'. Checked the top level and the keys "
        f"conversationFlow, conversation_flow, response_engine. "
        f"Top-level keys seen: {', '.join(sorted(obj)[:12])}")


def outgoing(node):
    """Every transition leaving a node, across all four exit kinds."""
    out = []
    for kind in EDGE_KINDS:
        val = node.get(kind)
        if isinstance(val, list):
            out.extend((kind, e) for e in val if isinstance(e, dict))
        elif isinstance(val, dict):
            out.append((kind, val))
    return out


def node_text(node):
    """All prose on a node, whatever shape it takes."""
    bits = []
    inst = node.get("instruction")
    if isinstance(inst, dict):
        bits.append(inst.get("text") or "")
    elif isinstance(inst, str):
        bits.append(inst)
    for key in ("name", "prompt", "text", "static_text"):
        if isinstance(node.get(key), str):
            bits.append(node[key])
    return "\n".join(b for b in bits if b)


def cond_text(edge):
    tc = edge.get("transition_condition") or {}
    if isinstance(tc, str):
        return tc
    return (tc.get("prompt") or tc.get("equation") or tc.get("type") or "")


# --------------------------------------------------------------------------
# lint
# --------------------------------------------------------------------------
class Report:
    def __init__(self):
        self.rows = []

    def add(self, level, check, message, detail=None):
        self.rows.append({"level": level, "check": check,
                          "message": message, "detail": detail})

    def fails(self):
        return [r for r in self.rows if r["level"] == "FAIL"]

    def warns(self):
        return [r for r in self.rows if r["level"] == "WARN"]


def lint_flow(flow, line=None):
    rep = Report()
    nodes = flow.get("nodes") or []
    if not nodes:
        rep.add("FAIL", "input", "flow has no nodes")
        return rep

    by_id = {}
    for n in nodes:
        nid = n.get("id")
        if nid in by_id:
            rep.add("FAIL", "ids", f"duplicate node id {nid!r}")
        by_id[nid] = n

    inbound = defaultdict(list)
    dangling = []
    for n in nodes:
        for kind, e in outgoing(n):
            dest = e.get("destination_node_id")
            if dest is None:
                continue
            if dest not in by_id:
                dangling.append((n.get("id"), kind, dest))
            inbound[dest].append(n.get("id"))

    for src, kind, dest in dangling:
        rep.add("FAIL", "edges",
                f"node {src!r} {kind} points at {dest!r}, which does not exist")
    if not dangling:
        rep.add("OK", "edges", "every transition lands on a real node")

    start = flow.get("start_node_id") or (nodes[0].get("id") if nodes else None)
    ends = {"end", "end_call", "transfer_call", "press_digit"}
    dead = [n.get("id") for n in nodes
            if not outgoing(n) and (n.get("type") or "") not in ends]
    for nid in dead:
        rep.add("FAIL", "dead-end",
                f"node {nid!r} ({by_id[nid].get('type')}) has no exit of any "
                f"kind and is not an end node",
                "Checked across edges, else_edge, always_edge and "
                "skip_response_edge. A caller reaching it is stuck.")
    if not dead:
        rep.add("OK", "dead-end", "no node is stuck")

    # A GLOBAL node is reached by its own condition from anywhere in the
    # call, so it has no inbound edge ON PURPOSE. Reporting it as
    # unreachable is a false finding, and a noisy one: a mature flow has
    # several. The marker is a non-empty global_node_setting.condition.
    globals_ = {n.get("id") for n in nodes
                if (n.get("global_node_setting") or {}).get("condition")}
    if globals_:
        rep.add("OK", "global-nodes",
                f"{len(globals_)} global node(s), reached by condition, "
                f"not by an edge")
    orphans = [n.get("id") for n in nodes
               if n.get("id") != start
               and n.get("id") not in globals_
               and not inbound.get(n.get("id"))]
    for nid in orphans:
        rep.add("WARN", "unreachable",
                f"node {nid!r} ({by_id[nid].get('name') or '?'}) has no "
                f"inbound transition and is not a global node")
    if not orphans:
        rep.add("OK", "unreachable", "every non-global node is reachable")

    # a conditional node with no fallback strands the caller on no match
    for n in nodes:
        conds = [e for k, e in outgoing(n) if k == "edges"]
        fallback = any(k in ("else_edge", "always_edge") for k, _ in outgoing(n))
        if conds and not fallback and (n.get("type") or "") not in ends:
            rep.add("WARN", "no-fallback",
                    f"node {n.get('id')!r} has {len(conds)} conditional "
                    f"edge(s) and no else_edge or always_edge",
                    "If no condition matches, the caller has nowhere to go.")

    # variables written vs read
    written, read = set(), set()
    for n in nodes:
        for key in ("variables", "extraction_variables", "output_variables"):
            for v in (n.get(key) or []):
                if isinstance(v, dict) and v.get("name"):
                    written.add(v["name"])
        text = node_text(n)
        read.update(VAR_RE.findall(text))
        for _, e in outgoing(n):
            read.update(VAR_RE.findall(cond_text(e)))
    # A variable can also be supplied by the flow's own defaults, or by the
    # call that starts the agent. Counting only node-written variables
    # reports every seeded variable as missing, which is noise.
    defaults = set(flow.get("default_dynamic_variables") or {})
    unset = sorted(r for r in read if r not in written and r not in defaults)
    if unset:
        rep.add("WARN", "variables",
                f"read but never set in this flow: {', '.join(unset[:12])}",
                "Each one must arrive as a dynamic variable when the call "
                "starts, or the caller hears the braces. Confirm every "
                "name, or give it a default_dynamic_variables entry.")
    else:
        rep.add("OK", "variables",
                f"{len(read)} read, all set in the flow or in "
                f"default_dynamic_variables")

    # double-say search
    if line:
        hits = [n.get("id") for n in nodes if line in node_text(n)]
        if len(hits) > 1:
            rep.add("WARN", "double-say",
                    f"{len(hits)} nodes contain that sentence: "
                    f"{', '.join(map(str, hits))}",
                    "Any path crossing two of them says it twice. Walk the "
                    "paths, or count it with a scripted chat run.")
        elif hits:
            rep.add("OK", "double-say", f"sentence appears on one node: {hits[0]}")
        else:
            rep.add("WARN", "double-say", "sentence not found on any node",
                    "Check the exact wording, including punctuation.")

    rep.add("OK", "size", f"{len(nodes)} nodes, "
            f"{sum(len(outgoing(n)) for n in nodes)} transitions")
    return rep


def render(rep, path):
    order = {"FAIL": 0, "WARN": 1, "OK": 2}
    glyph = {"FAIL": "FAIL", "WARN": "WARN", "OK": "ok  "}
    print(f"flowkit lint  {path}\n")
    for r in sorted(rep.rows, key=lambda r: (order[r["level"]], r["check"])):
        print(f"  {glyph[r['level']]}  {r['check']:<14} {r['message']}")
        if r.get("detail") and r["level"] != "OK":
            print(f"        {r['detail']}")
    f, w = len(rep.fails()), len(rep.warns())
    print(f"\n  {f} fail, {w} warn, {len(rep.rows) - f - w} ok")
    if f == 0:
        print("  Structure is sound. That is NOT proof of what it SAYS. "
              "Run flowkit.py chat next.")
    return f


def cmd_lint(a):
    return 1 if render(lint_flow(load(a.path), a.line), a.path) else 0


# --------------------------------------------------------------------------
# pull
# --------------------------------------------------------------------------
def cmd_pull(a):
    client = RetellClient()
    flow = client.get_flow(a.flow_id, a.version)
    Path(a.out).write_text(json.dumps(flow, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print(f"flow {flow.get('conversation_flow_id')} version "
          f"{flow.get('version')} published={bool(flow.get('is_published'))}")
    print(f"  nodes: {len(flow.get('nodes') or [])}")
    print(f"wrote {a.out}")
    return 0


# --------------------------------------------------------------------------
# sandbox chat
# --------------------------------------------------------------------------
class FlowSandbox:
    """A throwaway flow plus a throwaway chat agent. Both version 0."""

    def __init__(self, client, flow_obj, label="run"):
        self.client = client
        self.flow = client.create_flow(flow_obj)
        self.flow_id = self.flow["conversation_flow_id"]
        spkit.record("flows", self.flow_id)
        self.agent = client.create_chat_agent(
            {"type": "conversation-flow", "conversation_flow_id": self.flow_id},
            agent_name=f"{SANDBOX_PREFIX} flow {label} {int(time.time())}")
        self.agent_id = self.agent["agent_id"]
        spkit.record("chat_agents", self.agent_id)
        self.chat_id = None

    def start(self, dynamic_variables=None):
        self.chat_id = self.client.create_chat(
            self.agent_id, dynamic_variables)["chat_id"]

    def say(self, text):
        """One caller turn. Returns (kind, text, node, transition_type) rows.

        TRAP: a node transition does NOT ride along on the agent message.
        It arrives as its OWN message with role "node_transition", carrying
        former_node_id, new_node_id, new_node_name and transition_type.
        Filter the reply list to role in (agent, assistant) and you throw
        away the entire path, silently, and get an empty trace.

        transition_type is "global" when a GLOBAL node grabbed the turn and
        "normal" otherwise. That single field is the fastest way to see a
        global node firing when it should not.
        """
        out = self.client.chat_completion(self.chat_id, text)
        rows = []
        for m in (out.get("messages") or []):
            role = m.get("role")
            if role == "node_transition":
                rows.append(("NODE", None, m.get("new_node_name")
                             or m.get("new_node_id"),
                             m.get("transition_type")))
            elif role in ("agent", "assistant") and m.get("content"):
                rows.append(("AGENT", m["content"], None, None))
        return rows

    def finish(self):
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
                                 (self.client.delete_flow, "flows", self.flow_id)):
            try:
                fn(obj_id)
                spkit.forget(kind, obj_id)
            except RetellError as exc:
                print(f"  WARN could not delete {obj_id}: {exc}", file=sys.stderr)


def cmd_chat(a):
    client = RetellClient()
    if a.file:
        flow_obj, source = load(a.file), a.file
    else:
        flow_obj = client.get_flow(a.flow_id, a.version)
        source = f"{a.flow_id} v{flow_obj.get('version')}"
        print(f"copied {source} into a throwaway so the chat agent cannot "
              f"silently fall back to version 0")

    turns = list(a.message)
    if not turns:
        print("ERROR: give at least one -m/--message", file=sys.stderr)
        return 2
    print(f"source : {source}")
    print(f"turns  : {len(turns)}   estimated cost "
          f"~{(len(turns) + 1) * spkit.CENTS_PER_MESSAGE:.1f} cents")
    if len(turns) > spkit.CHEAP_TURNS and not a.yes:
        print(f"ERROR: more than {spkit.CHEAP_TURNS} turns needs --yes",
              file=sys.stderr)
        return 2

    box = FlowSandbox(client, flow_obj, a.label)
    print(f"sandbox: flow {box.flow_id}  chat agent {box.agent_id}")
    lines, path = [], []
    try:
        box.start(json.loads(a.seed) if a.seed else None)
        for turn in turns:
            lines.append(("CALLER", turn, None))
            for kind, text, node, ttype in box.say(turn):
                if kind == "NODE":
                    lines.append(("NODE", node, ttype))
                    path.append(f"{node}[global]" if ttype == "global" else node)
                else:
                    lines.append(("AGENT", text, None))
        final = box.finish()
    finally:
        box.destroy()
        print("sandbox destroyed")

    print("\n" + "=" * 68)
    for who, text, extra in lines:
        if who == "NODE":
            print(f"  -> node {text} [{extra}]")
        else:
            print(f"{who:>6}: {text}")
    print("=" * 68)
    if path:
        print(f"\npath: {' -> '.join(path)}")
        print("NOTE: only conversation nodes report a transition. Branch and "
              "code nodes are instant and invisible, so this path is a "
              "subsequence of the real one, never the whole of it.")
    collected = (final or {}).get("collected_dynamic_variables") or {}
    if collected:
        print("\ncollected_dynamic_variables:")
        for k, v in sorted(collected.items()):
            print(f"  {k} = {v!r}")
    if a.out:
        Path(a.out).write_text(json.dumps(
            {"source": source, "path": path,
             "transcript": [{"role": w, "content": t, "extra": n}
                            for w, t, n in lines],
             "collected_dynamic_variables": collected},
            indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\nwrote {a.out}")
        print("NOTE: a real transcript carries caller PII. Keep it out of "
              "any repository.")
    return 0


# --------------------------------------------------------------------------
# push
# --------------------------------------------------------------------------
def cmd_push(a):
    client = RetellClient()
    flow_obj = load(a.file)
    rep = lint_flow(flow_obj)
    render(rep, a.file)
    if rep.fails() and not a.force:
        print(f"\nREFUSING: lint reports {len(rep.fails())} failure(s).",
              file=sys.stderr)
        return 1

    current = client.get_flow(a.flow_id, a.version)
    if current.get("is_published"):
        print(f"\nREFUSING: flow {a.flow_id} version {current.get('version')} "
              f"is PUBLISHED. Published versions are immutable and carry live "
              f"calls. Create a draft agent version first, then target that.",
              file=sys.stderr)
        return 1

    before = len(current.get("nodes") or [])
    after = len(flow_obj.get("nodes") or [])
    print(f"\ntarget : {a.flow_id} version {current.get('version')} (DRAFT)")
    print(f"nodes  : {before} -> {after}")
    if not a.push:
        print("\nDRY RUN. Re-run with --push to write. Nothing was sent.")
        return 0

    out = client.update_flow(a.flow_id, flow_obj, a.version)
    print(f"wrote version {out.get('version')}")
    fresh = client.get_flow(a.flow_id, out.get("version"))
    got = len(fresh.get("nodes") or [])
    print(f"read back: {got} nodes, matches: {got == after}")
    if got != after:
        print("WARN: the server copy does not match. Do not call this landed.",
              file=sys.stderr)
        return 1
    print("NOT PUBLISHED. This wrote a draft only.")
    return 0


def cmd_cleanup(a):
    return spkit.cmd_cleanup(a)


# --------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Conversation-flow driver. lint is offline. "
                    "Dry run by default. Never publishes.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("lint", help="static check. NO API KEY NEEDED.")
    p.add_argument("path")
    p.add_argument("--line", help="find every node saying this exact sentence")
    p.set_defaults(fn=cmd_lint)

    p = sub.add_parser("pull", help="snapshot a live flow (read-only)")
    p.add_argument("--flow-id", required=True)
    p.add_argument("--version", type=int, default=None)
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_pull)

    p = sub.add_parser("chat", help="drive a throwaway copy over text")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--file")
    g.add_argument("--flow-id")
    p.add_argument("--version", type=int, default=None)
    p.add_argument("-m", "--message", action="append", default=[])
    p.add_argument("--seed", help="JSON dict of dynamic variables")
    p.add_argument("--label", default="run")
    p.add_argument("--out")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(fn=cmd_chat)

    p = sub.add_parser("push", help="write a draft. Dry run unless --push.")
    p.add_argument("--file", required=True)
    p.add_argument("--flow-id", required=True)
    p.add_argument("--version", type=int, default=None)
    p.add_argument("--push", action="store_true")
    p.add_argument("--force", action="store_true")
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
