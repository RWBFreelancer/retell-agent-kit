#!/usr/bin/env python3
"""Sandbox a conversation flow as a chat agent and drive it over the API.

Retell will not drive a voice agent over the API. It will drive a chat agent.
So to test behaviour we stand up a throwaway copy of the flow, talk to it as
text, read what it did, and tear the copy down.

WHY A THROWAWAY COPY, NOT A CLONE OF THE LIVE FLOW
--------------------------------------------------
Two API rules collide:

  - `create-chat-agent` refuses a version:  "Cannot specify version > 0 for
    new agent".  A new chat agent is always version 0.
  - `update-chat-agent` refuses to repoint it: "Response engine version must
    match agent version".

So a chat agent aimed at our real flow gets **version 0** of it -- the very
first version ever saved, not the draft under test. Silently. That is the
exact trap that makes text testing worthless.

The fix: POST the flow object to `create-conversation-flow`. The new flow is
version 0, the chat agent is version 0, and they line up. The sandbox holds a
copy of whatever object we handed it, so we can test the live draft, an old
export, or a transform result that has not been pushed anywhere.

It also means testing can never touch the production flow.

THE SANDBOX ONLY RUNS APPROVED MODELS
--------------------------------------
Test on the cheapest model first. A copied flow keeps its own
`model_choice`, which for a real agent is usually its production model, so
without a guard every sandbox run would bill at production-model rates.

So `Sandbox` forces EVERY `model_choice` in its in-memory copy to a model in
TEST_MODELS, read from `sandbox/config.json`, and refuses any other model.
No flag turns this off. The flow on disk and on Retell is never changed.
See `cost-gate` before widening that list for a client.

Endpoints used (all confirmed live):

    POST   /create-conversation-flow          -> sandbox flow, version 0
    POST   /create-chat-agent                 -> chat agent, version 0
    POST   /create-chat                       -> chat_id
    POST   /create-chat-completion            -> messages for one turn
    PATCH  /end-chat/{chat_id}
    GET    /get-chat/{chat_id}                -> collected_dynamic_variables
    DELETE /delete-chat-agent/{agent_id}
    DELETE /delete-conversation-flow/{flow_id}
    POST   /v2/list-agents                    -> for cleanup

`collected_dynamic_variables` is only filled in AFTER the chat ends, so the
order is always: send every turn, end, then read the variables.

Sandboxes are named with SANDBOX_PREFIX so cleanup deletes its own and leaves
anything Rey made by hand alone.

Usage:
    python tools/retell_chat.py smoke --agent b
    python tools/retell_chat.py smoke --file acme-dental/agents/intake/exports/v21.json
    python tools/retell_chat.py list
    python tools/retell_chat.py cleanup
    python tools/retell_chat.py --help
"""
import sys
import json
import time
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "kit"))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

from retellkit import RetellClient, RetellError, agent_config, load_env

SANDBOX_PREFIX = "zz-sandbox-"

# Fields the API owns. Sending them back on create is rejected or ignored.
_READ_ONLY = ("conversation_flow_id", "version", "last_modification_timestamp",
              "is_published")

# Rough, per-message estimate used for the cost gate. See sandbox/config.json.
CENTS_PER_MESSAGE = 1.5


def _load_test_models():
    """The only models a sandbox may run, cheapest first, from
    sandbox/config.json. This list is the cost gate: never widen it without
    the client's OK for the added cost."""
    cfg_path = Path(__file__).resolve().parent.parent / "sandbox" / "config.json"
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        models = tuple(data["test_models"])
        if models:
            return models
    except (OSError, ValueError, KeyError):
        pass
    return ("gpt-4.1-mini", "gpt-4.1-nano")


TEST_MODELS = _load_test_models()
DEFAULT_TEST_MODEL = TEST_MODELS[0]


def force_test_model(flow_obj, model=DEFAULT_TEST_MODEL):
    """Return (copy, count): a deep copy with every `model_choice.model` set to
    `model`. Refuses a model outside TEST_MODELS, and refuses a copy that still
    names any other model afterwards."""
    if model not in TEST_MODELS:
        raise RetellError("sandbox model {!r} is not allowed. Use one of: {}. "
                          "Edit sandbox/config.json to add one, with the "
                          "client's OK for the added cost.".format(
                              model, ", ".join(TEST_MODELS)))
    flow = json.loads(json.dumps(flow_obj))
    count = 0
    seen = []

    def walk(o):
        nonlocal count
        if isinstance(o, dict):
            mc = o.get("model_choice")
            if isinstance(mc, dict):
                mc["model"] = model
                count += 1
            for k, v in o.items():
                if k == "model_choice" and isinstance(v, dict):
                    seen.append(v.get("model"))
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(flow)
    bad = [m for m in seen if m not in TEST_MODELS]
    if bad:
        raise RetellError("sandbox copy still names {}; refusing".format(bad))
    return flow, count


def flow_object(source):
    """Return a bare ConversationFlow dict from a file path or a dict.

    Accepts either an agent export (flow nested under `conversationFlow`) or a
    raw flow as the API returns it.
    """
    if isinstance(source, dict):
        return source.get("conversationFlow") or source
    d = json.loads(Path(source).read_text(encoding="utf-8"))
    return d.get("conversationFlow") or d


class Sandbox:
    """One throwaway flow + chat agent pair. Use as a context manager."""

    def __init__(self, client, flow_obj, label="flow", model=DEFAULT_TEST_MODEL):
        self.client = client
        self.flow_obj, self.model_overrides = force_test_model(flow_obj, model)
        self.model = model
        self.label = label
        self.flow_id = None
        self.agent_id = None
        self.name = None

    def __enter__(self):
        payload = {k: v for k, v in self.flow_obj.items() if k not in _READ_ONLY}
        flow = self.client._request("POST", "/create-conversation-flow", body=payload)
        self.flow_id = flow.get("conversation_flow_id")
        if not self.flow_id:
            raise RetellError("create-conversation-flow returned no id")
        self.name = "{}{}-{}".format(SANDBOX_PREFIX, self.label, int(time.time()))
        agent = self.client._request(
            "POST", "/create-chat-agent",
            body={"response_engine": {"type": "conversation-flow",
                                      "conversation_flow_id": self.flow_id},
                  "agent_name": self.name})
        self.agent_id = agent.get("agent_id")
        if not self.agent_id:
            self.destroy()
            raise RetellError("create-chat-agent returned no agent_id")
        return self

    def __exit__(self, *exc):
        self.destroy()
        return False

    def destroy(self):
        """Always runs, even on failure. A leaked sandbox is a dirty account."""
        for path, ident in (("/delete-chat-agent/", self.agent_id),
                            ("/delete-conversation-flow/", self.flow_id)):
            if not ident:
                continue
            try:
                self.client._request("DELETE", path + ident)
            except RetellError as exc:
                print("WARNING: could not delete {}{}: {}".format(path, ident, exc),
                      file=sys.stderr)
        self.agent_id = self.flow_id = None

    # ---------- one conversation ----------
    def start(self, dynamic_vars=None):
        body = {"agent_id": self.agent_id}
        if dynamic_vars:
            body["retell_llm_dynamic_variables"] = {
                k: str(v) for k, v in dynamic_vars.items()}
        row = self.client._request("POST", "/create-chat", body=body)
        chat_id = row.get("chat_id")
        if not chat_id:
            raise RetellError("create-chat returned no chat_id")
        return chat_id

    def send(self, chat_id, content):
        """One caller turn. Returns the raw messages array for that turn."""
        return self.client._request(
            "POST", "/create-chat-completion",
            body={"chat_id": chat_id, "content": content}).get("messages") or []

    def end(self, chat_id):
        """End the chat. A chat the agent already ended is not an error.

        The agent can hang up on its own, for example after the Sales/Spam
        hard-stop line or the Sign-off node. Retell then answers this call with
        HTTP 400 "Chat already ended". Treating that as a failure killed a whole
        trace run on 2026-08-23, part way through T-P.
        """
        try:
            self.client._request("PATCH", "/end-chat/{}".format(chat_id))
        except RetellError as exc:
            if "already ended" not in str(exc).lower():
                raise

    def record(self, chat_id):
        return self.client._request("GET", "/get-chat/{}".format(chat_id))


# ---------- reading a turn ----------
def agent_lines(messages):
    return [m.get("content") or "" for m in messages if m.get("role") == "agent"]


def node_hops(messages):
    """(node_id, node_name, transition_type) for each hop, in order.

    node_transition rows carry former_node_id / new_node_id / new_node_name /
    transition_type. transition_type is "global" when a global node grabbed the
    turn, "normal" otherwise.
    """
    hops = []
    for m in messages:
        if m.get("role") != "node_transition":
            continue
        hops.append((m.get("new_node_id"), m.get("new_node_name"),
                     m.get("transition_type")))
    return hops


def list_chat_agents(client):
    """Every chat agent on the account.

    The server-side channel filter wants a shape the docs do not pin down, and
    guessing at it is how a cleanup silently matches nothing. Listing all and
    filtering here is small and cannot drift.
    """
    out, key = [], None
    while True:
        body = {"limit": 200}
        if key:
            body["pagination_key"] = key
        page = client._request("POST", "/v2/list-agents", body=body)
        if isinstance(page, list):
            out.extend(page)
            break
        out.extend(page.get("items") or [])
        if not page.get("has_more"):
            break
        key = page.get("pagination_key")
        if not key:
            break
    return [r for r in out if r.get("channel") == "chat"]


# ---------- CLI ----------
def resolve_source(a, env, client):
    """Return (flow_obj, label). --file wins over --agent."""
    if a.file:
        return flow_object(a.file), Path(a.file).stem
    cfg = agent_config(a.client, a.agent)
    flow = client.get_flow(cfg["flow_id"], a.version)
    return flow, "{}-v{}".format(cfg["key"], flow.get("version"))


def cmd_smoke(a, env):
    client = RetellClient(env)
    flow, label = resolve_source(a, env, client)
    print("source      : {}  ({} nodes)".format(label, len(flow.get("nodes", []))))
    with Sandbox(client, flow, label) as sb:
        print("model       : {} ({} overrides, sandbox only)".format(
            sb.model, sb.model_overrides))
        print("sandbox flow: {}".format(sb.flow_id))
        print("chat agent  : {}".format(sb.agent_id))
        chat_id = sb.start()
        for turn in a.message:
            msgs = sb.send(chat_id, turn)
            print("\nCALLER : {}".format(turn))
            for nid, nname, ttype in node_hops(msgs):
                print("  -> node {} [{}]".format(nname, ttype))
            for line in agent_lines(msgs):
                print("  AGENT: {}".format(line))
        sb.end(chat_id)
        rec = sb.record(chat_id)
        print("\ncollected vars: {}".format(rec.get("collected_dynamic_variables")))
        print("chat_cost     : {}".format(rec.get("chat_cost")))
    print("\nsandbox torn down. Production flow untouched.")
    return 0


def cmd_list(a, env):
    rows = list_chat_agents(RetellClient(env))
    if not rows:
        print("no chat agents on the account")
        return 0
    for r in rows:
        mine = "ours" if (r.get("agent_name") or "").startswith(SANDBOX_PREFIX) else "    "
        print("  [{}] {}  {}".format(mine, r.get("agent_id"), r.get("agent_name")))
    print("\n{} chat agents".format(len(rows)))
    return 0


def cmd_cleanup(a, env):
    """Delete leftover sandbox chat agents.

    Sandbox flows are not listed by any endpoint we have, so a chat agent is
    the handle. Normal runs tear themselves down; this is for a crashed run.
    """
    client = RetellClient(env)
    deleted, failed = [], []
    for r in list_chat_agents(client):
        name = r.get("agent_name") or ""
        if not a.all and not name.startswith(SANDBOX_PREFIX):
            continue
        try:
            client._request("DELETE", "/delete-chat-agent/" + r["agent_id"])
            deleted.append(name or r["agent_id"])
        except RetellError as exc:
            failed.append("{}: {}".format(name or r["agent_id"], exc))
    for d in deleted:
        print("deleted: {}".format(d))
    if not deleted:
        print("nothing to delete")
    for f in failed:
        print("FAILED : {}".format(f), file=sys.stderr)
    print("\n{} chat agents remain".format(len(list_chat_agents(client))))
    return 1 if failed else 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Sandbox a conversation flow as a chat agent and talk to "
                    "it. Never touches the production flow or the voice agent.")
    sub = ap.add_subparsers(dest="command", required=True)

    s = sub.add_parser("smoke", help="stand up a sandbox, send turns, tear down")
    s.add_argument("--client", required=True, help="client folder name")
    s.add_argument("--agent", required=True, help="agent slug under <client>/agents/")
    s.add_argument("--version", type=int, default=None,
                   help="flow version to pull (default: latest draft)")
    s.add_argument("--file", default=None,
                   help="test a local export instead of pulling from Retell")
    s.add_argument("--message", action="append", default=None,
                   help="a caller turn (repeatable, in order)")
    s.set_defaults(func=cmd_smoke)

    s = sub.add_parser("list", help="list every chat agent on the account")
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("cleanup", help="delete leftover sandbox chat agents")
    s.add_argument("--all", action="store_true",
                   help="delete EVERY chat agent, not just ours. Use with care.")
    s.set_defaults(func=cmd_cleanup)

    a = ap.parse_args(argv)
    if getattr(a, "message", None) is None and a.command == "smoke":
        a.message = ["hi, my truck broke down"]
    return a.func(a, load_env())


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RetellError as exc:
        print("ERROR: {}".format(exc), file=sys.stderr)
        sys.exit(1)
