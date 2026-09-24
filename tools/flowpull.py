#!/usr/bin/env python3
"""GET a conversation flow from Retell and snapshot it into exports/.

This is how you take a picture of the flow before and after every change.
It only reads from Retell. It never writes to Retell.

The file is named from the version number the API returns, so a pull of
version 21 lands in <client>/agents/<agent>/exports/v21.json.

Exports are immutable. If the target file already exists with different
content, this refuses to overwrite it. Use --suffix to park the snapshot
beside it, for example --suffix draft -> exports/v21-draft.json.

Usage:
    python tools/flowpull.py --client acme-dental --agent intake
    python tools/flowpull.py --client acme-dental --agent intake --suffix draft
    python tools/flowpull.py --client acme-dental --agent intake --version 50
    python tools/flowpull.py --help
"""
import json
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "kit"))
from retellkit import RetellClient, RetellError, agent_config, load_env


def export_path(exports_dir, version, suffix=None):
    name = f"v{version}" + (f"-{suffix}" if suffix else "") + ".json"
    return Path(exports_dir) / name


def pull(client_name, agent_slug, version=None, suffix=None, force=False, env=None):
    """Fetch the flow and write it to exports/. Returns (path, flow)."""
    env = env if env is not None else load_env()
    cfg = agent_config(client_name, agent_slug)
    client = RetellClient(env)

    flow = client.get_flow(cfg["flow_id"], version)
    got = flow.get("version")
    if got is None:
        raise RetellError("response had no version field; refusing to name a file")

    path = export_path(cfg["exports"], got, suffix)
    text = json.dumps(flow, indent=2, ensure_ascii=False) + "\n"

    if path.exists() and not force:
        if path.read_text(encoding="utf-8") == text:
            print(f"unchanged: {path} already matches the pulled flow")
            return path, flow
        raise RetellError(
            f"{path} already exists with different content.\n"
            f"Exports are immutable. Re-run with --suffix <name> to park this "
            f"snapshot beside it, or --force only if you truly mean to replace it.")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path, flow


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Snapshot a Retell conversation flow into exports/. "
                    "Read-only against Retell.")
    ap.add_argument("--client", required=True, help="client folder name")
    ap.add_argument("--agent", required=True, help="agent slug under <client>/agents/")
    ap.add_argument("--version", type=int, default=None,
                    help="flow version to pull (default: latest)")
    ap.add_argument("--suffix", default=None,
                    help="filename suffix, e.g. draft -> v21-draft.json")
    ap.add_argument("--force", action="store_true",
                    help="overwrite an existing export (avoid; exports are immutable)")
    a = ap.parse_args(argv)

    path, flow = pull(a.client, a.agent, a.version, a.suffix, a.force)
    cfg = agent_config(a.client, a.agent)
    print(f"client       : {a.client}")
    print(f"agent        : {a.agent}")
    print(f"flow_id      : {flow.get('conversation_flow_id')}")
    print(f"version      : {flow.get('version')}")
    print(f"nodes        : {len(flow.get('nodes', []))}")
    print(f"saved        : {path}")
    print("\nNothing was written to Retell.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RetellError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
