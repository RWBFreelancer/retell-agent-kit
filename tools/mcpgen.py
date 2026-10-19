#!/usr/bin/env python3
"""Write a git-ignored .mcp.json at the kit root with one MCP server per
account you name, so Claude Code can reach a second n8n instance, a client's
Retell workspace, or another Make org beside the claude.ai connectors.

    python tools/mcpgen.py --list                         what the catalog offers
    python tools/mcpgen.py retell=ninja n8n=eiden n8n=ninja        (dry run)
    python tools/mcpgen.py retell=ninja n8n=eiden --write

Server names are <service>-<account>: retell-ninja, n8n-eiden. Tools then
appear as mcp__n8n-eiden__<tool>.

Values come from KEY__ACCOUNT lines in the kit .env (kit/accounts.py). The
catalog is mcp/servers.json, which holds no secrets.

GUARDS

  - Dry run by default: prints server names and URL hosts only, never a
    token. `--write` writes.
  - Refuses to overwrite a .mcp.json it did not generate, or one edited
    by hand since (checked against mcp/.generated), unless `--force`.
  - Refuses unless .gitignore lists .mcp.json and mcp/.generated, because
    both hold tokens.

After writing: restart Claude Code in the kit folder and approve the new
project servers when it asks. `/mcp` shows them.
"""
import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

KIT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT / "kit"))
from retellkit import RetellError, _parse_env_file  # noqa: E402

CATALOG = KIT / "mcp" / "servers.json"
OUT = KIT / ".mcp.json"
# Claude Code may reject unknown keys in .mcp.json, so the "this tool wrote
# it" marker lives beside it: a sidecar holding the file's exact text.
MARKER = KIT / "mcp" / ".generated"


def fill(obj, values):
    if isinstance(obj, dict):
        return {k: fill(v, values) for k, v in obj.items()}
    if isinstance(obj, list):
        return [fill(v, values) for v in obj]
    if isinstance(obj, str):
        return re.sub(r"\{([A-Z0-9_]+)\}", lambda m: values[m[1]], obj)
    return obj


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("pairs", nargs="*", help="service=account")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    catalog = {k: v for k, v in json.loads(CATALOG.read_text(encoding="utf-8")).items()
               if not k.startswith("_")}
    if a.list or not a.pairs:
        for name, entry in catalog.items():
            print(f"{name:<8} needs {', '.join(entry['needs'])}\n         {entry['warning']}")
        return 0

    env = _parse_env_file(KIT / ".env")
    servers = {}
    for pair in a.pairs:
        svc, _, acct = pair.partition("=")
        svc, acct = svc.strip().lower(), acct.strip()
        if svc not in catalog or not acct:
            raise RetellError(f"bad pair {pair!r}. Use service=account; services: {', '.join(catalog)}")
        entry = catalog[svc]
        values, missing = {}, []
        for k in entry["needs"]:
            v = env.get(f"{k}__{acct.upper()}", "").strip()
            (values.__setitem__(k, v) if v else missing.append(f"{k}__{acct.upper()}"))
        if missing:
            raise RetellError(f"{svc}={acct}: missing in .env: {', '.join(missing)}")
        server = fill(entry["server"], values)
        servers[f"{svc}-{acct.lower()}"] = server
        print(f"{svc}-{acct.lower():<16} {server['type']}  host {urlparse(server['url']).hostname}")

    if not a.write:
        print("\nDRY RUN. Re-run with --write to write .mcp.json. Nothing was written.")
        return 0
    gi = (KIT / ".gitignore").read_text(encoding="utf-8").splitlines()
    for need in (".mcp.json", "mcp/.generated"):
        if need not in [l.strip() for l in gi]:
            raise RetellError(f".gitignore does not list {need}. Refusing to write tokens.")
    if OUT.exists() and not a.force:
        mine = MARKER.exists() and MARKER.read_text(encoding="utf-8") == OUT.read_text(encoding="utf-8")
        if not mine:
            raise RetellError(f"{OUT} was not written by this tool, or was edited since. "
                              f"Move it, or pass --force.")
    text = json.dumps({"mcpServers": servers}, indent=2) + "\n"
    OUT.write_text(text, encoding="utf-8")
    MARKER.write_text(text, encoding="utf-8")
    print(f"\nwrote {OUT} with {len(servers)} server(s). Restart Claude Code here, then /mcp.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RetellError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
