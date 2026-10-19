#!/usr/bin/env python3
"""Print one part of a conversation-flow export, instead of reading the whole JSON.

An export is about 180 KB, most of it layout and fine-tune examples. Reading it
whole costs tens of thousands of tokens. This prints only what a question needs.
Read-only: never talks to Retell, never writes a file.

What `show` prints satisfies hard rule 8's "read the whole node and every edge":
the full instruction, code, extract variables, global-node condition, and every
outgoing transition of every kind (edges, else_edge, always_edge,
skip_response_edge) with the destination's id, name and type. It also prints the
edges that point INTO the node. Fine-tune examples are counted; pass
--examples to print them.

Nodes are matched by id. A name is accepted only when exactly one node has it,
and the id is always printed: point edges by id, never by name (hard rule 9).

Usage:
    python tools/flowshow.py <export.json> list
    python tools/flowshow.py <export.json> show <node-id> [<node-id> ...] [--examples]
    python tools/flowshow.py <export.json> edges-to <node-id>
    python tools/flowshow.py <export.json> grep "<text>"
    python tools/flowshow.py <export.json> var <name>
    python tools/flowshow.py <export.json> global
    python tools/flowshow.py --client acme --agent intake list
                                                   (newest file in <client>/agents/<agent>/exports/)

`--client/--agent` picks the newest export by modification time and prints which one.
That is a local file, not the server: pull first when the live draft matters.
"""
import argparse
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "kit"))
from retellkit import agent_config  # noqa: E402

EDGE_KINDS = ("edges", "else_edge", "always_edge", "skip_response_edge")
VAR_REF = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")


def load(path):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    return d.get("conversationFlow") or d


def newest_export(client, agent):
    files = sorted(Path(agent_config(client, agent)["exports"]).glob("*.json"),
                   key=lambda p: p.stat().st_mtime)
    if not files:
        sys.exit(f"no exports for {client}/{agent}. Run flowpull.py first.")
    return files[-1]


def outgoing(node):
    out = []
    for k in EDGE_KINDS:
        v = node.get(k)
        for e in (v if isinstance(v, list) else [v] if v else []):
            out.append((k, e))
    return out


def cond_text(e):
    tc = e.get("transition_condition") or {}
    if tc.get("type") == "equation":
        join = " {} ".format(tc.get("operator", "&&"))
        return "[equation] " + join.join(
            "{} {} {}".format(q.get("left"), q.get("operator"), q.get("right", ""))
            for q in tc.get("equations", []))
    return tc.get("prompt", "")


def node_strings(n):
    """Every string the node holds that could read or name a variable."""
    parts = [(n.get("instruction") or {}).get("text", ""), n.get("code", "")]
    parts += [cond_text(e) for _, e in outgoing(n)]
    parts.append((n.get("global_node_setting") or {}).get("condition", ""))
    return "\n".join(p for p in parts if p)


def sets_vars(n):
    names = [v.get("name") for v in n.get("variables") or []]
    names += list((n.get("response_variables") or {}).keys())
    return [x for x in names if x]


class Flow:
    def __init__(self, path):
        self.path = path
        self.cf = load(path)
        self.nodes = {n["id"]: n for n in self.cf["nodes"]}

    def resolve(self, key):
        if key in self.nodes:
            return self.nodes[key]
        hits = [n for n in self.nodes.values() if n.get("name") == key]
        if len(hits) == 1:
            return hits[0]
        if hits:
            sys.exit(f"name {key!r} matches {len(hits)} nodes: "
                     + ", ".join(n["id"] for n in hits) + ". Use an id.")
        sys.exit(f"no node with id or name {key!r}. Try: list")

    def label(self, nid):
        n = self.nodes.get(nid)
        if not n:
            return f"{nid}  (MISSING NODE)"
        return f"{nid}  \"{n.get('name', '')}\" [{n['type']}]"

    def incoming(self, nid):
        return [(src, k, e) for src in self.nodes.values()
                for k, e in outgoing(src) if e.get("destination_node_id") == nid]


def cmd_list(f, _):
    start = f.cf.get("start_node_id")
    print(f"{len(f.nodes)} nodes. start = {start}")
    print(f"{'id':<34} {'type':<12} {'words':>5} {'out':>3} {'in':>3}  name")
    for n in f.cf["nodes"]:
        typ = n["type"].replace("extract_dynamic_variables", "extract")
        if n.get("global_node_setting"):
            typ += "*"
        w = len(node_strings(n).split())
        print(f"{n['id']:<34} {typ:<12} {w:>5} {len(outgoing(n)):>3} "
              f"{len(f.incoming(n['id'])):>3}  {n.get('name', '')}")
    print("* = global node. words = instruction + code + edge conditions.")


def print_block(title, text):
    print(f"--- {title}")
    print(text.rstrip() if text else "(empty)")


def cmd_show(f, args):
    for key in args.nodes:
        n = f.resolve(key)
        print("=" * 78)
        print(f"{n['id']}  \"{n.get('name', '')}\"  type={n['type']}")
        flags = {k: n[k] for k in ("skippable", "speak_during_execution",
                                   "wait_for_result", "timeout_ms",
                                   "interruption_sensitivity", "responsiveness")
                 if k in n}
        if n.get("model_choice"):
            flags["model_choice"] = n["model_choice"]
        if flags:
            print("flags:", json.dumps(flags))
        g = n.get("global_node_setting")
        if g:
            print_block("global_node_setting: condition", g.get("condition", ""))
            for k, v in g.items():
                if k == "condition":
                    continue
                if isinstance(v, list) and not args.examples:
                    print(f"    {k}: {len(v)} (pass --examples to print)")
                else:
                    print(f"    {k}: {json.dumps(v, ensure_ascii=False)}")
        ins = n.get("instruction")
        if ins:
            print_block(f"instruction ({ins.get('type', '?')})", ins.get("text", ""))
        if n.get("code"):
            print_block("code", n["code"])
        if n.get("response_variables"):
            print_block("response_variables", json.dumps(n["response_variables"], indent=2))
        for v in n.get("variables") or []:
            print_block(f"extract variable {v.get('name')} ({v.get('type')})",
                        v.get("description", "")
                        + ("\nchoices: " + json.dumps(v["choices"]) if v.get("choices") else ""))
        for k in ("finetune_transition_examples", "finetune_conversation_examples"):
            ex = n.get(k)
            if ex:
                if args.examples:
                    print_block(k, json.dumps(ex, indent=2, ensure_ascii=False))
                else:
                    print(f"--- {k}: {len(ex)} (pass --examples to print)")
        other = sorted(set(n) - {"id", "name", "type", "display_position", "instruction",
                                 "code", "response_variables", "variables",
                                 "global_node_setting", "model_choice",
                                 "finetune_transition_examples",
                                 "finetune_conversation_examples", *EDGE_KINDS, *flags})
        for k in other:
            print_block(k, json.dumps(n[k], indent=2, ensure_ascii=False))
        out = outgoing(n)
        print(f"--- outgoing ({len(out)})")
        for k, e in out:
            print(f"[{k}] {e.get('id')} -> {f.label(e.get('destination_node_id'))}")
            print(f"    {cond_text(e)}")
        if not out:
            print("(none: dead end unless this is an end node)")
        inc = f.incoming(n["id"])
        print(f"--- incoming ({len(inc)})")
        for src, k, e in inc:
            print(f"[{k}] {e.get('id')} <- {f.label(src['id'])}")


def cmd_edges_to(f, args):
    n = f.resolve(args.node)
    for src, k, e in f.incoming(n["id"]):
        print(f"[{k}] {e.get('id')} <- {f.label(src['id'])}")
        print(f"    {cond_text(e)}")


def cmd_grep(f, args):
    needle = args.text.lower()
    gp = f.cf.get("global_prompt") or ""
    for i, line in enumerate(gp.splitlines(), 1):
        if needle in line.lower():
            print(f"global_prompt:{i}: {line.strip()}")
    for n in f.cf["nodes"]:
        for line in node_strings(n).splitlines():
            if needle in line.lower():
                print(f"{n['id']} \"{n.get('name', '')}\": {line.strip()}")


def cmd_var(f, args):
    name = args.name
    dv = f.cf.get("default_dynamic_variables") or {}
    print(f"default_dynamic_variables: "
          + (json.dumps(dv[name]) if name in dv else "NOT DECLARED"))
    print("set by:")
    for n in f.cf["nodes"]:
        if name in sets_vars(n):
            print("  " + f.label(n["id"]))
    print("read by ({{" + name + "}}):")
    gp = f.cf.get("global_prompt") or ""
    if name in VAR_REF.findall(gp):
        print("  global_prompt")
    for n in f.cf["nodes"]:
        if name in VAR_REF.findall(node_strings(n)):
            print("  " + f.label(n["id"]))


def cmd_global(f, _):
    print(f.cf.get("global_prompt") or "(no global prompt)")
    dv = f.cf.get("default_dynamic_variables") or {}
    print(f"\n--- default_dynamic_variables ({len(dv)})")
    for k, v in dv.items():
        print(f"{k} = {json.dumps(v)}")
    print(f"\n--- start_node_id = {f.cf.get('start_node_id')}, "
          f"model_choice = {json.dumps(f.cf.get('model_choice'))}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    # With --agent there is no path; a positional here would swallow the subcommand.
    if not any(a == "--agent" or a.startswith("--agent=") for a in sys.argv[1:]):
        ap.add_argument("export", help="path to an export JSON")
    ap.add_argument("--client", help="client folder, with --agent")
    ap.add_argument("--agent", help="use the newest export of this agent slug")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    s = sub.add_parser("show")
    s.add_argument("nodes", nargs="+")
    s.add_argument("--examples", action="store_true")
    s = sub.add_parser("edges-to")
    s.add_argument("node")
    s = sub.add_parser("grep")
    s.add_argument("text")
    s = sub.add_parser("var")
    s.add_argument("name")
    sub.add_parser("global")
    args = ap.parse_args()

    if args.agent:
        if not args.client:
            ap.error("--agent needs --client")
        path = newest_export(args.client, args.agent)
        print(f"(newest local export: {path})")
    else:
        path = Path(args.export)
    f = Flow(path)
    {"list": cmd_list, "show": cmd_show, "edges-to": cmd_edges_to, "grep": cmd_grep,
     "var": cmd_var, "global": cmd_global}[args.cmd](f, args)


if __name__ == "__main__":
    main()
