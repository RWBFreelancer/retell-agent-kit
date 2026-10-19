#!/usr/bin/env python3
"""n8n: read, lint, diff, and (carefully) write workflows that a Retell agent
feeds. Account-aware: N8N_ACCOUNT picks which instance (kit/accounts.py).

Keys, per account:  N8N_BASE_URL__<ACCT>, N8N_API_KEY__<ACCT>
                    (n8n: Settings > n8n API > Create an API key)

READ (safe, no writes anywhere but a local snapshot)

    python kit/n8nkit.py ping
    python kit/n8nkit.py workflows [--name recap] [--active]
    python kit/n8nkit.py pull <workflow-id> [--client acme]
    python kit/n8nkit.py show <file-or-id> [list | node "<name>" | code "<name>"]
    python kit/n8nkit.py executions <workflow-id> [--errors] [--limit 20]
    python kit/n8nkit.py execution <execution-id> [--node "<name>"] [--save]
    python kit/n8nkit.py lint <file>                 (offline, no key needed)
    python kit/n8nkit.py diff <old.json> <new.json>  (offline)

WRITE (dry run unless --apply)

    python kit/n8nkit.py push <workflow-id> --file new.json [--apply] [--live-ok]

GUARDS ON push

  - Lint must report 0 errors.
  - The file must carry the same `updatedAt` as the live workflow, which
    proves it was pulled from what is live now. Someone else's edit in the
    n8n editor since your pull makes it refuse. `--stale-ok` overrides.
  - An ACTIVE workflow serves real traffic. A PUT can reach the next real
    execution. It refuses unless `--live-ok`, which needs a go-ahead.
  - Snapshots before and after, then a read-back compare of nodes and
    connections. A mismatch is reported as NOT landed.
  - It never activates, deactivates, or deletes a workflow. Do that in
    the n8n editor.

A credential's value is never visible through this API. Prove a credential
works with a throwaway probe workflow, not by reading JSON.
"""
import argparse
import difflib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from integrationkit import (IntegrationError, http_json, load_json, need,  # noqa: E402
                            snapshot)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

# PUT /workflows/{id} rejects any settings key it does not know.
PUT_SETTINGS = {"saveExecutionProgress", "saveManualExecutions",
                "saveDataErrorExecution", "saveDataSuccessExecution",
                "executionTimeout", "errorWorkflow", "timezone",
                "executionOrder", "callerPolicy", "callerIds",
                "timeSavedPerExecution", "availableInMCP"}


# --------------------------------------------------------------------------
# client
# --------------------------------------------------------------------------
class N8nClient:
    def __init__(self, env=None):
        vals, self.env = need("n8n", "N8N_BASE_URL", "N8N_API_KEY", env=env)
        self.base = vals["N8N_BASE_URL"].rstrip("/") + "/api/v1"
        self.host = re.sub(r"^https?://", "", vals["N8N_BASE_URL"]).split("/")[0]
        self._h = {"X-N8N-API-KEY": vals["N8N_API_KEY"]}
        self.account = self.env.get("N8N_ACCOUNT") or "(default)"

    def _q(self, method, path, body=None, query=None):
        url = self.base + path
        if query:
            q = "&".join(f"{k}={v}" for k, v in query.items() if v not in (None, ""))
            url += ("?" + q) if q else ""
        return http_json(method, url, self._h, body)

    def list_workflows(self, active=None):
        rows, cursor = [], None
        while True:
            page = self._q("GET", "/workflows", query={
                "limit": 100, "cursor": cursor,
                "active": None if active is None else str(active).lower()})
            rows += page.get("data") or []
            cursor = page.get("nextCursor")
            if not cursor:
                return rows

    def get_workflow(self, wid):
        return self._q("GET", f"/workflows/{wid}")

    def put_workflow(self, wid, wf):
        body = {"name": wf["name"], "nodes": wf["nodes"],
                "connections": wf.get("connections") or {},
                "settings": {k: v for k, v in (wf.get("settings") or {}).items()
                             if k in PUT_SETTINGS}}
        if wf.get("staticData") is not None:
            body["staticData"] = wf["staticData"]
        return self._q("PUT", f"/workflows/{wid}", body=body)

    def list_executions(self, wid, status=None, limit=20):
        return self._q("GET", "/executions", query={
            "workflowId": wid, "status": status, "limit": limit}).get("data") or []

    def get_execution(self, eid):
        return self._q("GET", f"/executions/{eid}", query={"includeData": "true"})


# --------------------------------------------------------------------------
# lint: a Python port of n8n-projects/src/lib/lint.js. Offline.
# --------------------------------------------------------------------------
REMOVED = {
    "n8n-nodes-base.start": "Start node was removed in n8n 2.0. Use Manual Trigger or Execute Workflow Trigger.",
    "n8n-nodes-base.spontit": "Spontit node was removed in n8n 2.0.",
    "n8n-nodes-base.crowddev": "crowd.dev node was removed in n8n 2.0.",
    "n8n-nodes-base.kitemaker": "Kitemaker node was removed in n8n 2.0.",
    "n8n-nodes-base.automizy": "Automizy node was removed in n8n 2.0.",
}
WRITE_OPS = {"create", "insert", "append", "send", "post", "upload", "add"}
SECRET_KEY = re.compile(r"(api[_-]?key|access[_-]?token|secret|password|passwd|bearer|"
                        r"authorization|private[_-]?key)", re.I)


def _t(n):
    return str(n.get("type") or "").lower()


def _sticky(n):
    return _t(n).endswith(".stickynote")


def _trigger(n):
    t = _t(n)
    return "trigger" in t or t.endswith(".webhook") or t.endswith(".start")


def _walk(v, path=""):
    if isinstance(v, list):
        for i, x in enumerate(v):
            yield from _walk(x, f"{path}[{i}]")
    elif isinstance(v, dict):
        for k, x in v.items():
            yield from _walk(x, f"{path}.{k}" if path else k)
    else:
        yield path, v


def _cycles(names, edges):
    """Strongly connected components with more than one node, or a self loop."""
    index, low, on, stack, out, i = {}, {}, set(), [], [], [0]

    def visit(v):
        index[v] = low[v] = i[0]
        i[0] += 1
        stack.append(v)
        on.add(v)
        for w in edges.get(v, []):
            if w not in index:
                visit(w)
                low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = []
            while True:
                w = stack.pop()
                on.discard(w)
                comp.append(w)
                if w == v:
                    break
            if len(comp) > 1 or v in edges.get(v, []):
                out.append(comp)

    sys.setrecursionlimit(max(1000, len(names) * 4))
    for n in names:
        if n not in index:
            visit(n)
    return out


def lint(wf):
    """[(level, code, node, message)], level in error/warn/info."""
    f = []

    def add(level, code, node, msg):
        f.append((level, code, node, msg))

    if not isinstance(wf, dict) or not isinstance(wf.get("nodes"), list):
        add("error", "no-nodes", None, 'No "nodes" array. Not an n8n workflow export.')
        return f
    conns = wf.get("connections") or {}
    by_name = {}
    for n in wf["nodes"]:
        if n.get("name") in by_name:
            add("error", "duplicate-name", n.get("name"), "Two nodes share a name. Connections will break.")
        by_name[n.get("name")] = n
        if _sticky(n):
            continue
        if _t(n) in REMOVED:
            add("error", "removed-node", n["name"], REMOVED[_t(n)])
        if n.get("typeVersion") is None:
            add("error", "no-type-version", n["name"], "Node has no typeVersion.")
        if n.get("disabled"):
            add("warn", "disabled-node", n["name"], "Node is disabled. Remove it or turn it on before go-live.")
        if _t(n).endswith(".executecommand"):
            add("warn", "execute-command", n["name"], "Execute Command is off by default in n8n 2.x and is a security risk.")

    main, anyedges, touched = {}, [], set()
    for src, by_type in conns.items():
        if src not in by_name:
            add("error", "unknown-source", src, "Connection starts from a node that does not exist.")
        for ctype, outputs in (by_type or {}).items():
            for output in outputs or []:
                for link in output or []:
                    if not link or not link.get("node"):
                        continue
                    if link["node"] not in by_name:
                        add("error", "unknown-target", src, f'Connection goes to "{link["node"]}", which does not exist.')
                        continue
                    touched |= {src, link["node"]}
                    anyedges.append((src, link["node"], ctype))
                    if ctype == "main":
                        main.setdefault(src, []).append(link["node"])

    real = [n for n in wf["nodes"] if not _sticky(n)]
    triggers = [n for n in real if _trigger(n) and not n.get("disabled")]
    if not triggers:
        add("error", "no-trigger", None, "No trigger node, so it can never start.")
    reach = {t["name"] for t in triggers}
    grew = True
    while grew:
        grew = False
        for src, to, ctype in anyedges:
            if ctype == "main" and src in reach and to not in reach:
                reach.add(to)
                grew = True
            if ctype != "main" and to in reach and src not in reach:  # AI sub-nodes
                reach.add(src)
                grew = True
    for n in real:
        if n.get("disabled") or n["name"] in reach:
            continue
        if n["name"] not in touched:
            add("warn", "orphan-node", n["name"], "Node is not connected to anything.")
        elif triggers:
            add("warn", "unreachable-node", n["name"], "No trigger leads to this node, so it never runs.")

    for comp in _cycles(list(by_name), main):
        types = [_t(by_name[c]) for c in comp if c in by_name]
        label = " -> ".join(comp)
        if any(t.endswith("splitinbatches") for t in types):
            add("info", "loop-batches", comp[0], f'Loop Over Items loop: {label}. Check the "done" output leaves it.')
        elif any(t.endswith(b) for t in types for b in (".if", ".switch", ".filter")):
            add("warn", "loop-branch", comp[0], f"Loop exits only through IF/Switch/Filter: {label}. Add a max try count.")
        else:
            add("error", "infinite-loop", comp[0], f"Loop with no exit: {label}.")

    paths, has_write, has_dedupe = {}, False, False
    for n in real:
        t, p = _t(n), n.get("parameters") or {}
        if t.endswith(".webhook"):
            if not p.get("path"):
                add("warn", "webhook-no-path", n["name"], "Webhook has no path.")
            elif p["path"] in paths:
                add("error", "webhook-dup-path", n["name"], f'Webhook path also used by "{paths[p["path"]]}".')
            else:
                paths[p["path"]] = n["name"]
            if p.get("authentication") in (None, "", "none"):
                add("info", "webhook-no-auth", n["name"], "Webhook has no auth. Retell calls it from outside: verify x-retell-signature or add header auth.")
        if t.endswith(".scheduletrigger"):
            for rule in (p.get("rule") or {}).get("interval") or []:
                if rule.get("field") == "seconds":
                    add("warn", "schedule-seconds", n["name"], "Schedule runs every few seconds.")
        if t.endswith(".executeworkflow") and wf.get("id"):
            target = p.get("workflowId")
            target = target.get("value") if isinstance(target, dict) else target
            if target and str(target) == str(wf["id"]):
                add("error", "self-call", n["name"], "Execute Workflow calls its own workflow.")
        if t.endswith(".httprequest") and not n.get("retryOnFail"):
            add("info", "http-no-retry", n["name"], "HTTP Request has no Retry On Fail.")
        if t.endswith((".code", ".function", ".functionitem")):
            code = "\n".join(x for x in (p.get("jsCode"), p.get("pythonCode"), p.get("functionCode")) if x)
            if re.search(r"\$evaluateExpression\s*\(", code):
                add("error", "evaluate-expression", n["name"], "$evaluateExpression() was removed in n8n 2.0.")
            if re.search(r"(\$env\b|process\.env)", code):
                add("warn", "code-env", n["name"], "Code reads environment variables. Blocked by default in n8n 2.x.")
            if t.endswith((".function", ".functionitem")):
                add("warn", "old-function", n["name"], "Old Function node. Use the Code node.")
        op = str(p.get("operation") or "").lower()
        if re.search(r"upsert|appendorupdate", op) or t.endswith(("removeduplicates", "comparedatasets")):
            has_dedupe = True
        elif op in WRITE_OPS:
            has_write = True
        for path, v in _walk(p):
            if not isinstance(v, str) or len(v) < 8 or v.startswith("=") or "{{" in v:
                continue
            last = re.sub(r"\[\d+\]$", "", path.split(".")[-1])
            if SECRET_KEY.search(last) or re.match(r"^Bearer\s+\S{8,}", v, re.I) \
                    or re.match(r"^(sk|pk|xox[abp]|key)[-_][A-Za-z0-9_-]{10,}", v):
                add("error", "hardcoded-secret", n["name"], f'Field "{path}" looks like a typed-in secret. Use a credential.')
    if has_write and not has_dedupe:
        add("warn", "no-dedupe", None, "Creates or sends records with no dedupe or upsert step. Check a re-run makes no copies.")

    s = wf.get("settings") or {}
    if s.get("executionOrder") != "v1":
        add("warn", "execution-order", None, 'settings.executionOrder is not "v1".')
    if not s.get("errorWorkflow"):
        add("warn", "no-error-workflow", None, "No error workflow set. Nobody is told when this fails.")
    if wf.get("pinData"):
        add("warn", "pin-data", None, f"Pin data on {len(wf['pinData'])} node(s). Remove before go-live.")
    return f


def render_lint(findings):
    order = {"error": 0, "warn": 1, "info": 2}
    for level, code, node, msg in sorted(findings, key=lambda x: order[x[0]]):
        print(f"{level.upper():<5} [{code}]" + (f' "{node}"' if node else "") + f": {msg}")
    c = {k: sum(1 for x in findings if x[0] == k) for k in order}
    print(f"\n{c['error']} error(s), {c['warn']} warning(s), {c['info']} note(s)")
    return c["error"]


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def node_code(n):
    p = n.get("parameters") or {}
    return p.get("jsCode") or p.get("pythonCode") or p.get("functionCode") or ""


def find_node(wf, name):
    hits = [n for n in wf["nodes"] if n.get("name") == name or n.get("id") == name]
    if len(hits) != 1:
        sys.exit(f"{len(hits)} nodes match {name!r}. Try: show <file> list")
    return hits[0]


def load_wf(arg, client=None):
    p = Path(arg)
    if p.exists():
        return load_json(p), str(p)
    return (client or N8nClient()).get_workflow(arg), f"live {arg}"


def wf_signature(wf):
    return json.dumps({"nodes": sorted((n.get("name"), json.dumps(n.get("parameters"), sort_keys=True))
                                       for n in wf.get("nodes") or []),
                       "connections": wf.get("connections") or {}}, sort_keys=True)


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------
def cmd_ping(a):
    c = N8nClient()
    rows = c.list_workflows()
    print(f"account : {c.account}\nhost    : {c.host}\nauth    : OK, {len(rows)} workflows visible")


def cmd_workflows(a):
    c = N8nClient()
    print(f"(account {c.account}, {c.host})")
    for w in c.list_workflows(active=True if a.active else None):
        if a.name and a.name.lower() not in (w.get("name") or "").lower():
            continue
        print(f"{w['id']:<18} {'ACTIVE' if w.get('active') else 'off   '} "
              f"{str(w.get('updatedAt'))[:19]}  {len(w.get('nodes') or []):>3} nodes  {w.get('name')}")


def cmd_pull(a):
    c = N8nClient()
    wf = c.get_workflow(a.id)
    path = snapshot(wf, "n8n", f"{a.id}-{wf.get('name')}", a.client)
    print(f"pulled  : {wf.get('name')} ({a.id}) from {c.host}")
    print(f"active  : {wf.get('active')}   updatedAt: {wf.get('updatedAt')}   "
          f"nodes: {len(wf.get('nodes') or [])}")
    print(f"saved   : {path}")


def cmd_show(a):
    wf, src = load_wf(a.src)
    print(f"({src}: {wf.get('name')})")
    if a.what == "list":
        for n in wf["nodes"]:
            flag = " DISABLED" if n.get("disabled") else ""
            code = f"  code {len(node_code(n).splitlines())} lines" if node_code(n) else ""
            print(f"{n.get('type', '').replace('n8n-nodes-base.', ''):<28} {n['name']}{flag}{code}")
        return
    n = find_node(wf, a.name)
    if a.what == "code":
        print(node_code(n) or "(no code)")
        return
    shown = {k: v for k, v in n.items() if k != "position"}
    print(json.dumps(shown, indent=2, ensure_ascii=False))
    outs = (wf.get("connections") or {}).get(n["name"]) or {}
    for ctype, outputs in outs.items():
        for i, output in enumerate(outputs or []):
            for link in output or []:
                print(f"--> [{ctype} {i}] {link.get('node')}")
    for src_name, by_type in (wf.get("connections") or {}).items():
        for ctype, outputs in (by_type or {}).items():
            for output in outputs or []:
                if any(l and l.get("node") == n["name"] for l in output or []):
                    print(f"<-- [{ctype}] {src_name}")


def cmd_lint(a):
    return 1 if render_lint(lint(load_json(a.file))) else 0


def cmd_diff(a):
    old, new = load_json(a.old), load_json(a.new)
    on = {n["name"]: n for n in old.get("nodes") or []}
    nn = {n["name"]: n for n in new.get("nodes") or []}
    for name in sorted(set(on) - set(nn)):
        print(f"- removed node: {name}")
    for name in sorted(set(nn) - set(on)):
        print(f"+ added node  : {name}")
    for name in sorted(set(on) & set(nn)):
        a_, b_ = dict(on[name]), dict(nn[name])
        a_.pop("position", None)
        b_.pop("position", None)
        if a_ == b_:
            continue
        print(f"~ changed     : {name}")
        if node_code(a_) != node_code(b_):
            sys.stdout.writelines(difflib.unified_diff(
                node_code(a_).splitlines(True), node_code(b_).splitlines(True),
                f"{name} (old)", f"{name} (new)"))
            print()
        else:
            sys.stdout.writelines(difflib.unified_diff(
                json.dumps(a_, indent=1, sort_keys=True).splitlines(True),
                json.dumps(b_, indent=1, sort_keys=True).splitlines(True), "old", "new", n=1))
    if (old.get("connections") or {}) != (new.get("connections") or {}):
        print("~ connections changed")
    if (old.get("settings") or {}) != (new.get("settings") or {}):
        print("~ settings changed")


def cmd_executions(a):
    c = N8nClient()
    for e in c.list_executions(a.id, "error" if a.errors else None, a.limit):
        print(f"{e.get('id'):<10} {e.get('status', '?'):<9} {str(e.get('startedAt'))[:19]}  "
              f"{e.get('mode', '')}")


def cmd_execution(a):
    c = N8nClient()
    ex = c.get_execution(a.id)
    rd = ((ex.get("data") or {}).get("resultData") or {})
    run = rd.get("runData") or {}
    print(f"execution {a.id}: status {ex.get('status')}  workflow {ex.get('workflowId')}  "
          f"started {ex.get('startedAt')}")
    if rd.get("error"):
        err = rd["error"]
        print(f"ERROR at {(err.get('node') or {}).get('name') or rd.get('lastNodeExecuted')}: "
              f"{(err.get('message') or '')[:300]}")
    print("nodes that ran, in order:")
    for name, runs in run.items():
        r = runs[-1] if runs else {}
        items = sum(len(o or []) for o in ((r.get("data") or {}).get("main") or []))
        err = f"  ERROR {r['error'].get('message', '')[:120]}" if r.get("error") else ""
        print(f"  {name:<40} {items:>3} item(s)  {r.get('executionTime', '?')} ms{err}")
    if a.node:
        runs = run.get(a.node)
        if not runs:
            sys.exit(f"node {a.node!r} did not run")
        main = (runs[-1].get("data") or {}).get("main") or []
        for i, out in enumerate(main):
            print(f"--- output {i}: {len(out or [])} item(s); first item json:")
            if out:
                print(json.dumps(out[0].get("json"), indent=2, ensure_ascii=False)[:6000])
    if a.save:
        print(f"saved: {snapshot(ex, 'n8n-executions', f'exec-{a.id}', a.client)}")
        print("This holds real call data. Keep it out of any committed file.")


def cmd_push(a):
    c = N8nClient()
    new = load_json(a.file)
    print(f"account : {c.account} ({c.host})")
    errors = render_lint(lint(new))
    if errors:
        print("\nREFUSING: lint reports errors. Fix them first.", file=sys.stderr)
        return 1
    live = c.get_workflow(a.id)
    print(f"\ntarget  : {live.get('name')} ({a.id})  active={live.get('active')}  "
          f"updatedAt={live.get('updatedAt')}")
    if new.get("updatedAt") != live.get("updatedAt") and not a.stale_ok:
        print(f"REFUSING: the file's updatedAt ({new.get('updatedAt')}) is not the live one. "
              f"Someone changed it since your pull. Pull again and redo the edit, "
              f"or pass --stale-ok.", file=sys.stderr)
        return 1
    if live.get("active") and not a.live_ok:
        print("REFUSING: this workflow is ACTIVE and serves real calls. A PUT can reach the "
              "next real execution. Get a go-ahead, then pass --live-ok.", file=sys.stderr)
        return 1
    on = {n["name"] for n in live.get("nodes") or []}
    nn = {n["name"] for n in new.get("nodes") or []}
    print(f"nodes   : {len(on)} -> {len(nn)}  (+{len(nn - on)} -{len(on - nn)})")
    if not a.apply:
        print("\nDRY RUN. Run `diff` against a fresh pull to read the change. "
              "Re-run with --apply to write. Nothing was sent.")
        return 0
    print(f"before  : {snapshot(live, 'n8n', f'{a.id}-before-push', a.client)}")
    c.put_workflow(a.id, new)
    fresh = c.get_workflow(a.id)
    print(f"after   : {snapshot(fresh, 'n8n', f'{a.id}-after-push', a.client)}")
    if wf_signature(fresh) != wf_signature(new):
        print("WARN: the live workflow does not match the file. Do not call this landed.",
              file=sys.stderr)
        return 1
    print("MATCHES: nodes and connections read back as sent. Watch the next real execution.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="n8n workflows for Retell agents. "
                                             "Writes only with push --apply.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ping")
    p = sub.add_parser("workflows")
    p.add_argument("--name")
    p.add_argument("--active", action="store_true")
    p = sub.add_parser("pull")
    p.add_argument("id")
    p.add_argument("--client")
    p = sub.add_parser("show")
    p.add_argument("src", help="a snapshot file, or a live workflow id")
    p.add_argument("what", nargs="?", default="list", choices=["list", "node", "code"])
    p.add_argument("name", nargs="?")
    p = sub.add_parser("lint")
    p.add_argument("file")
    p = sub.add_parser("diff")
    p.add_argument("old")
    p.add_argument("new")
    p = sub.add_parser("executions")
    p.add_argument("id", help="workflow id")
    p.add_argument("--errors", action="store_true")
    p.add_argument("--limit", type=int, default=20)
    p = sub.add_parser("execution")
    p.add_argument("id", help="execution id")
    p.add_argument("--node")
    p.add_argument("--save", action="store_true")
    p.add_argument("--client")
    p = sub.add_parser("push")
    p.add_argument("id")
    p.add_argument("--file", required=True)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--live-ok", action="store_true")
    p.add_argument("--stale-ok", action="store_true")
    p.add_argument("--client")
    a = ap.parse_args(argv)
    if a.cmd == "show" and a.what != "list" and not a.name:
        ap.error("show node|code needs a node name")
    fn = {"ping": cmd_ping, "workflows": cmd_workflows, "pull": cmd_pull, "show": cmd_show,
          "lint": cmd_lint, "diff": cmd_diff, "executions": cmd_executions,
          "execution": cmd_execution, "push": cmd_push}[a.cmd]
    return fn(a) or 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except IntegrationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
