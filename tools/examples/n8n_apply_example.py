#!/usr/bin/env python3
"""EXAMPLE PATTERN for a one-off n8n code-node change tool. Copy this file,
rename it for the change, and edit OLD_LINE/NEW_LINE/NODE_NAME. Do not run
this file as-is; it is a template, not a working tool.

WHY A NEW FILE PER CHANGE, NOT A GENERAL-PURPOSE PATCHER

Each change edits one exact, known line inside one named node, and refuses
to run if that line is not there. That is what makes it safe to run
unattended: it can never guess, and it can never half-apply to a workflow
someone already edited by hand. A general "find and replace" tool cannot
give you that guarantee.

GUARDS, ALL REQUIRED

  - Dry run by default. `--apply` is required to PATCH.
  - Refuses to run if the live line is not exactly what it expects, so it
    can never half-apply.
  - Snapshots the live workflow to <client>/integrations/ before and after.
  - Touches one node and one line. Nothing else.

USAGE

    python tools/examples/n8n_apply_example.py --client acme
    python tools/examples/n8n_apply_example.py --client acme --apply

REVERSAL

  The pre-change snapshot in <client>/integrations/, or reverse NEW_LINE
  back to OLD_LINE by hand.
"""
import argparse
import datetime
import difflib
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass


def clients_root():
    here = Path.cwd().resolve()
    for d in [here, *here.parents]:
        if (d / ".kit-path").exists():
            return d
    return Path.cwd()


def load_env(client_dir):
    d = {}
    for p in (client_dir.parent / ".env", client_dir / ".env.local"):
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    d[k.strip()] = v.split("#")[0].strip()
    return d


def api(env, method, path, body=None):
    req = urllib.request.Request(
        env["N8N_BASE_URL"].rstrip("/") + path, method=method,
        headers={"X-N8N-API-KEY": env["N8N_API_KEY"],
                 "Content-Type": "application/json"},
        data=json.dumps(body).encode() if body is not None else None)
    try:
        return json.load(urllib.request.urlopen(req, timeout=120))
    except urllib.error.HTTPError as ex:
        print("HTTP %s: %s" % (ex.code, ex.read().decode()[:900]))
        raise


# ---- edit these three for the real change -------------------------------
NODE_NAME = "Node name exactly as it appears in n8n"
OLD_LINE = "the exact literal line of code being replaced,"
NEW_LINE = "the exact literal line of code it becomes,"
# ---------------------------------------------------------------------------


def change(code):
    if NEW_LINE in code and OLD_LINE not in code:
        raise SystemExit(f"{NODE_NAME}: already applied. Stopping.")
    n = code.count(OLD_LINE)
    if n != 1:
        raise SystemExit(
            f"{NODE_NAME}: expected exactly one match, found {n}. "
            f"The node was edited by hand. Stopping.")
    return code.replace(OLD_LINE, NEW_LINE, 1)


def show(name, old, new):
    print("\n" + "=" * 74)
    print(name)
    print("=" * 74)
    for line in difflib.unified_diff(old.split("\n"), new.split("\n"),
                                     "live", "proposed", lineterm="", n=3):
        print(line)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--client", required=True, help="client folder name")
    ap.add_argument("--apply", action="store_true", help="actually PATCH n8n")
    a = ap.parse_args()

    client_dir = clients_root() / a.client
    env = load_env(client_dir)
    wid = env["N8N_WORKFLOW_ID"]
    wf = api(env, "GET", "/api/v1/workflows/" + wid)
    print("workflow : %s" % wf.get("name"))
    print("active   : %s | nodes: %d | updated: %s"
          % (wf.get("active"), len(wf["nodes"]), wf.get("updatedAt")))

    out_dir = client_dir / "integrations"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y-%m-%d")
    pre = out_dir / f"recap-{stamp}-pre-example.json"
    pre.write_text(json.dumps(wf, indent=2, ensure_ascii=False), encoding="utf-8")
    print("snapshot : %s" % pre)

    by = {n["name"]: n for n in wf["nodes"]}
    node = by[NODE_NAME]
    old_code = node["parameters"]["jsCode"]
    new_code = change(old_code)

    show(NODE_NAME, old_code, new_code)

    if not a.apply:
        print("\nDRY RUN. Nothing was written. Re-run with --apply to PATCH.")
        return 0

    node["parameters"]["jsCode"] = new_code
    body = {"name": wf["name"], "nodes": wf["nodes"],
            "connections": wf["connections"], "settings": wf["settings"]}
    api(env, "PUT", "/api/v1/workflows/" + wid, body)
    print("\nPATCHED.")

    back = api(env, "GET", "/api/v1/workflows/" + wid)
    live = {n["name"]: n for n in back["nodes"]}[NODE_NAME]["parameters"]["jsCode"]
    ok = live == new_code
    print(f"verify {NODE_NAME} :", "MATCHES" if ok else "DOES NOT MATCH")

    post = out_dir / f"recap-{stamp}-live-example.json"
    post.write_text(json.dumps(back, indent=2, ensure_ascii=False), encoding="utf-8")
    print("snapshot:", post)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
