#!/usr/bin/env python3
"""Publish an agent version. The only tool in this kit that can.

GUARDS, ALL REQUIRED, ALL CHECKED BEFORE ANY WRITE

  1. ALLOW_PUBLISH=true in .env. Refuses otherwise. This is a switch a
     human flips by hand; nothing in this kit flips it.
  2. --version must be given explicitly. There is no "publish latest".
  3. The target version must be a draft (is_published: false) and must
     exist. Publishing an already-published version is refused.

This tool does not check lint or trace results itself; the `publish`
skill's gate does that before this ever runs. This tool is the last,
narrow, mechanical step.

Usage:
    python kit/publishkit.py --client acme --agent intake --version 12 \\
        --title "v12: add urgency field" --description "..."
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from retellkit import RetellClient, RetellError, agent_config, load_env


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--client", required=True, help="client folder name")
    ap.add_argument("--agent", required=True, help="agent slug under <client>/agents/")
    ap.add_argument("--version", type=int, required=True,
                    help="the exact draft version to publish. Required.")
    ap.add_argument("--title", required=True, help="version title, for the changelog")
    ap.add_argument("--description", default="", help="version description")
    a = ap.parse_args(argv)

    env = load_env()
    if env.get("ALLOW_PUBLISH", "false").strip().lower() != "true":
        raise RetellError(
            "ALLOW_PUBLISH is not true. Publishing is refused. This switch "
            "is flipped by hand in .env, never by a skill or an agent.")

    cfg = agent_config(a.client, a.agent)
    client = RetellClient(env)
    agent_id = cfg["agent_id"]

    versions = client.list_agent_versions(agent_id)
    row = next((v for v in versions if v.get("version") == a.version), None)
    if row is None:
        raise RetellError(f"version {a.version} not found for this agent")
    if row.get("is_published"):
        raise RetellError(f"version {a.version} is already published")

    print(f"Publishing {a.client}/{a.agent} version {a.version} ...")
    result = client.publish_agent_version(agent_id, a.version, a.title, a.description)
    print("PUBLISHED.")
    print(f"  version     : {a.version}")
    print(f"  title       : {a.title}")
    print("Run delivery-check now, and pull a fresh copy to confirm what landed.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RetellError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
