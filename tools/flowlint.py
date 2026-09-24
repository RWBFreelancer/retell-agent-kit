#!/usr/bin/env python3
"""Static analyzer for Retell conversation-flow exports.

Walks every outgoing transition kind (edges, else_edge, always_edge,
skip_response_edge), so a
node is never wrongly reported as a dead end. That mistake produced two false
findings on this project; this tool exists so it cannot happen again.

Usage:
    python3 tools/flowlint.py <agent.json> [--line "exact sentence"] [--json]
"""
import json, re, argparse
from collections import deque

EDGE_KINDS = ("edges", "else_edge", "always_edge", "skip_response_edge")

# Variables written inside the flow but read OUTSIDE it: by a post-call
# analysis field, or by a downstream integration. This linter only ever sees
# the ConversationFlow object, so it cannot see these readers and would
# otherwise report every one as an orphan.
#
# Empty by default. This is a narrow, deliberate allowlist, not a mute
# button: add a name here, per client, only when you can say exactly what
# reads it and where, for example:
#
#   EXTERNAL_READERS = {
#       "missing_fields": "post-call analysis field missing_required_fields",
#   }
#
# Anything not named here is still reported as a possible orphan.
EXTERNAL_READERS = {}

# skip_response_edge is a real Retell transition: the node speaks its line and
# moves on without waiting for the caller. Omitting it reported two live nodes
# as dead ends and hid every path that runs through them.


def load(path):
    d = json.load(open(path))
    return d, (d.get("conversationFlow") or d)


def outgoing(node):
    """Every outgoing transition, regardless of which field holds it."""
    out = []
    for k in EDGE_KINDS:
        v = node.get(k)
        if not v:
            continue
        for e in (v if isinstance(v, list) else [v]):
            out.append((k, e))
    return out


def words(s):
    return len(str(s).split())


def cond_text(e):
    tc = e.get("transition_condition") or {}
    if tc.get("type") == "equation":
        join = " {} ".format(tc.get("operator", "?"))
        return "[equation] " + join.join(
            f"{q['left']} {q['operator']} {q['right']}" for q in tc.get("equations", []))
    return tc.get("prompt", "")


def node_text(n):
    """All prose the model sees for this node, including edge conditions."""
    parts = [n.get("instruction", {}).get("text", "")]
    parts += [cond_text(e) for _, e in outgoing(n)]
    parts.append((n.get("global_node_setting") or {}).get("condition", ""))
    return "\n".join(p for p in parts if p)


class Flow:
    def __init__(self, path):
        self.agent, self.cf = load(path)
        self.nodes = {n["id"]: n for n in self.cf["nodes"]}
        self.start = self.cf.get("start_node_id")
        self.dv = self.cf.get("default_dynamic_variables") or {}

    def name(self, nid):
        return self.nodes[nid]["name"] if nid in self.nodes else f"<missing:{nid}>"

    # ---------- structure ----------
    def dangling(self):
        return [(n["name"], k, e["destination_node_id"])
                for n in self.cf["nodes"] for k, e in outgoing(n)
                if e["destination_node_id"] not in self.nodes]

    def dead_ends(self):
        return [n["name"] for n in self.cf["nodes"]
                if n["type"] != "end" and not outgoing(n)]

    def unreachable(self):
        seen, q = set(), deque([self.start] if self.start else [])
        q.extend(n["id"] for n in self.cf["nodes"] if n.get("global_node_setting"))
        while q:
            nid = q.popleft()
            if nid in seen or nid not in self.nodes:
                continue
            seen.add(nid)
            q.extend(e["destination_node_id"] for _, e in outgoing(self.nodes[nid]))
        return [n["name"] for n in self.cf["nodes"] if n["id"] not in seen]

    # ---------- variables ----------
    def var_writes(self):
        w = {}
        for n in self.cf["nodes"]:
            if n["type"] == "code":
                for var in (n.get("response_variables") or {}):
                    w.setdefault(var, []).append(n["name"])
        return w

    def var_reads(self):
        r = {}
        for n in self.cf["nodes"]:
            for v in re.findall(r"\{\{(\w+)\}\}", node_text(n)):
                r.setdefault(v, []).append(n["name"])
            # A code node reads a variable as dv.name or dv["name"], never as
            # {{name}}. Without this the linter calls a counter that only its
            # own code reads "written but never read".
            if n["type"] == "code":
                code = n.get("code") or ""
                for v in re.findall(r"""dv\.(\w+)|dv\[["'](\w+)["']\]""", code):
                    name = v[0] or v[1]
                    r.setdefault(name, []).append(n["name"])
        for v in re.findall(r"\{\{(\w+)\}\}", self.cf.get("global_prompt", "")):
            r.setdefault(v, []).append("<global prompt>")
        return r

    def var_issues(self):
        w, r, declared, issues = self.var_writes(), self.var_reads(), set(self.dv), []
        for v, where in r.items():
            if v.startswith("current_"):
                continue
            if v not in w and v not in declared:
                issues.append(f"read but never written or declared: {v} (in {where[:3]})")
            elif v not in declared:
                issues.append(f"written but not declared in default_dynamic_variables: {v}")
        for v, where in w.items():
            if v not in r:
                if v in EXTERNAL_READERS:
                    continue
                issues.append(f"written but never read: {v} (set by {where})")
        return issues

    def external_reader_notes(self):
        """Variables this linter is structurally blind to. See EXTERNAL_READERS."""
        w = self.var_writes()
        return [f"{v}: read by {EXTERNAL_READERS[v]} (set by {w[v]})"
                for v in sorted(EXTERNAL_READERS) if v in w]

    def branch_joins(self):
        """Multi-equation branch edges joined with || are almost always a bug."""
        out = []
        for n in self.cf["nodes"]:
            for _, e in outgoing(n):
                tc = e.get("transition_condition") or {}
                if tc.get("type") == "equation" and len(tc.get("equations", [])) > 1 \
                        and tc.get("operator") != "&&":
                    out.append(f"{n['name']} -> {self.name(e['destination_node_id'])}: "
                               f"{len(tc['equations'])} equations joined with "
                               f"{tc.get('operator')!r}")
        return out

    # ---------- spoken lines ----------
    def sayers(self, line):
        return [n["id"] for n in self.cf["nodes"]
                if line in n.get("instruction", {}).get("text", "")]

    def paths_between(self, src, dst, limit=6):
        found, stack = [], [(src, [src])]
        while stack:
            nid, path = stack.pop()
            if len(path) > limit:
                continue
            for _, e in outgoing(self.nodes[nid]):
                d = e["destination_node_id"]
                if d == dst:
                    found.append(path + [d])
                elif d not in path and d in self.nodes:
                    stack.append((d, path + [d]))
        return found

    def code_sets(self, nid):
        """{var: value} a code node writes, parsed from its return statement."""
        n = self.nodes[nid]
        if n["type"] != "code":
            return {}
        return dict(re.findall(r'(\w+)\s*:\s*"(\w+)"', n.get("code", "")))

    def counter_vars(self, nid):
        """Variables a code node INCREMENTS, e.g. gate_passes, closing_passes.

        A counter is not a literal, so code_sets() cannot see it. A branch that
        tests a counter still blocks a path in the real flow, so it is reported
        separately as COUNTER rather than silently as GUARDED. A human still has
        to read the equation and agree.
        """
        n = self.nodes[nid]
        if n["type"] != "code":
            return set()
        code = n.get("code", "")
        return set(re.findall(r"parseInt\(\s*dv\.(\w+)", code))

    def counter_guarded(self, path):
        """True if a branch on the path can divert away from dst on a counter
        that a code node earlier on the path increments."""
        if len(path) < 2:
            return False
        dst = path[-1]
        counters = set()
        for nid in path[:-1]:
            counters |= self.counter_vars(nid)
        if not counters:
            return False
        for i, nid in enumerate(path[:-1]):
            if self.nodes[nid]["type"] != "branch":
                continue
            taken = path[i + 1]
            for _, e in outgoing(self.nodes[nid]):
                if e["destination_node_id"] == taken:
                    continue
                tc = e.get("transition_condition") or {}
                for q in tc.get("equations", []):
                    var = re.sub(r"[{}]", "", str(q["left"])).strip()
                    if var in counters:
                        return True
        return False

    def guarded(self, path):
        """True if the last hop is a branch edge that tests a variable the path
        has already set to the value that blocks it. Mirrors the manual trace."""
        if len(path) < 2:
            return False
        src, dst = path[-2], path[-1]
        if self.nodes[src]["type"] != "branch":
            return False
        state = {}
        for nid in path[:-1]:
            state.update(self.code_sets(nid))
        for _, e in outgoing(self.nodes[src]):
            if e["destination_node_id"] != dst:
                continue
            tc = e.get("transition_condition") or {}
            for q in tc.get("equations", []):
                var = re.sub(r"[{}]", "", str(q["left"])).strip()
                want = str(q["right"]).strip().strip("'\"")
                if var in state and q["operator"] == "==" and state[var] != want:
                    return True
        return False

    def double_say(self, line):
        """Two nodes speaking the same line, one reachable from the other."""
        s, out = self.sayers(line), []
        for a in s:
            for b in s:
                if a == b:
                    continue
                for p in self.paths_between(a, b):
                    out.append({
                        "from": self.name(a), "to": self.name(b),
                        "guarded": self.guarded(p),
                        "counter_guarded": self.counter_guarded(p),
                        "path": [self.name(x) for x in p],
                        "code_nodes_on_path": [self.name(x) for x in p
                                               if self.nodes[x]["type"] == "code"]})
        return out

    # ---------- tokens ----------
    def tokens(self):
        gp, always, rows = words(self.cf.get("global_prompt", "")), 0, []
        always = gp
        for n in self.cf["nodes"]:
            g = n.get("global_node_setting")
            if not g:
                continue
            c = words(g.get("condition", ""))
            ft = sum(words(t["content"]) for k in
                     ("positive_finetune_examples", "negative_finetune_examples")
                     for ex in (g.get(k) or []) for t in ex["transcript"])
            gb = sum(words(x["transition_condition"].get("prompt", ""))
                     for x in (g.get("go_back_conditions") or []))
            always += c + ft + gb
            rows.append((n["name"], c, ft, gb))
        pkgs = []
        for n in self.cf["nodes"]:
            i = words(n.get("instruction", {}).get("text", ""))
            e = sum(words(cond_text(x)) for _, x in outgoing(n))
            f = sum(words(t["content"]) for ex in
                    (n.get("finetune_transition_examples") or []) for t in ex["transcript"])
            if i + e + f:
                pkgs.append((i + e + f, n["name"], i, e, f))
        return {"global_prompt": gp, "global_nodes": rows,
                "always_on": always, "packages": sorted(pkgs, reverse=True)}

    def duplicate_paragraphs(self, minwords=12):
        seen, dups = {}, []
        for n in self.cf["nodes"]:
            for p in n.get("instruction", {}).get("text", "").split("\n\n"):
                p = p.strip()
                if words(p) < minwords:
                    continue
                if p in seen and seen[p] != n["name"]:
                    dups.append((seen[p], n["name"], p[:70]))
                else:
                    seen[p] = n["name"]
        return dups


def from_object(flow_obj):
    """Build a Flow from an in-memory ConversationFlow object instead of a file.

    Same checks, same code paths; only the source of the JSON differs. Used by
    flowapply.py so a mutated flow can be linted before it is written anywhere.
    """
    f = Flow.__new__(Flow)
    f.agent = flow_obj
    f.cf = flow_obj.get("conversationFlow") or flow_obj
    f.nodes = {n["id"]: n for n in f.cf["nodes"]}
    f.start = f.cf.get("start_node_id")
    f.dv = f.cf.get("default_dynamic_variables") or {}
    return f


def build_report(f, lines=()):
    """Run every check and return the report dict."""
    return {"agent": f.agent.get("agent_name"), "version": f.agent.get("version"),
            "nodes": len(f.cf["nodes"]), "dangling": f.dangling(),
            "dead_ends": f.dead_ends(), "unreachable": f.unreachable(),
            "variable_issues": f.var_issues(),
            "external_readers": f.external_reader_notes(),
            "branch_join_warnings": f.branch_joins(),
            "duplicate_paragraphs": f.duplicate_paragraphs(), "tokens": f.tokens(),
            "double_say": {ln: f.double_say(ln) for ln in lines}}


def report_is_clean(rep):
    """True when no structural or variable check produced a finding, and no
    unguarded double-say path was found."""
    for key in ("dangling", "dead_ends", "unreachable", "variable_issues",
                "branch_join_warnings"):
        if rep[key]:
            return False
    for hits in rep["double_say"].values():
        if any(not h["guarded"] and not h.get("counter_guarded") for h in hits):
            return False
    return True


def print_report(rep):
    t = rep["tokens"]
    print(f"{rep['agent']}  v{rep['version']}  {rep['nodes']} nodes")
    print(f"always-on: {t['always_on']} words (global prompt {t['global_prompt']})")
    for nm, c, ft, gb in t["global_nodes"]:
        print(f"   global {nm}: cond {c}, finetune {ft}, goback {gb}")
    print("\ntop node packages:")
    for tot, nm, i, e, fn in t["packages"][:6]:
        print(f"   {tot:5d}  {nm}  (inst {i}, edges {e}, finetune {fn})")

    def section(title, items):
        print(f"\n{title}:")
        if not items:
            print("   none")
        for it in items:
            print(f"   - {it}")

    section("DANGLING EDGES", [f"{x} [{k}] -> {d}" for x, k, d in rep["dangling"]])
    section("DEAD ENDS (no outgoing of any kind)", rep["dead_ends"])
    section("UNREACHABLE NODES", rep["unreachable"])
    section("VARIABLE ISSUES", rep["variable_issues"])
    # Not a finding. Printed so an exempted variable is never silent.
    section("READ OUTSIDE THE FLOW (not a finding)", rep["external_readers"])
    section("BRANCH JOIN WARNINGS", rep["branch_join_warnings"])
    section("DUPLICATE PARAGRAPHS",
            [f"{x} == {y}: {p}..." for x, y, p in rep["duplicate_paragraphs"]])
    for ln, hits in rep["double_say"].items():
        print(f"\nDOUBLE-SAY CHECK: {ln[:60]}...")
        if not hits:
            print("   no path between two sayers")
        bad = [h for h in hits
               if not h["guarded"] and not h.get("counter_guarded")]
        for h in hits:
            if h["guarded"]:
                tag = "GUARDED  "
            elif h.get("counter_guarded"):
                tag = "COUNTER  "
            else:
                tag = "UNGUARDED"
            print(f"   [{tag}] {h['from']} -> {h['to']}")
            if tag != "GUARDED  ":
                print(f"      path: {' -> '.join(h['path'])}")
                print(f"      code nodes on path: {h['code_nodes_on_path'] or 'NONE'}")
        print(f"   {len(bad)} unguarded of {len(hits)} paths")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--line", action="append", default=[],
                    help="exact spoken sentence to check for double-say")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    rep = build_report(Flow(a.path), a.line)
    if a.json:
        print(json.dumps(rep, indent=2))
        return
    print_report(rep)


if __name__ == "__main__":
    main()
