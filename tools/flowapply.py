#!/usr/bin/env python3
"""The safe edit loop: GET -> transform -> lint -> save -> (only then) PATCH.

Dry run is the default. Nothing reaches Retell without a second, explicit
--push flag on a second run.

What it does, in order:
  1. Refuse unless the target flow version is a DRAFT. The published version
     serving live traffic is never a target.
  2. GET the current flow from Retell.
  3. Run the named transform on the flow object.
  4. Run tools/flowlint.py on the RESULT, in memory, and print the report.
  5. Save the mutated flow to exports/vNN-<transform>.json. Local only.
  6. Stop. Print exactly what --push would do.
  7. Never publish. Publishing is a separate manual step gated by ALLOW_PUBLISH
     in .env, and nothing in this file calls it.

Transforms live in transforms/ and expose apply(flow) -> flow.

Usage:
    python tools/flowapply.py --agent b --transform noop
    python tools/flowapply.py --agent b --transform noop --line "exact sentence"
    python tools/flowapply.py --agent b --transform noop --push
    python tools/flowapply.py --help
"""
import copy
import json
import sys
import argparse
import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "kit"))

# Node names hold em dashes. Without this the Windows console mangles them.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

import flowlint
from retellkit import RetellClient, RetellError, agent_config, load_env

TRANSFORMS_DIR = REPO / "transforms"


def load_transform(name):
    path = TRANSFORMS_DIR / f"{name}.py"
    if not path.exists():
        have = sorted(p.stem for p in TRANSFORMS_DIR.glob("*.py")
                      if not p.stem.startswith("_"))
        raise RetellError(f"no transform {name!r} in {TRANSFORMS_DIR}. Have: {have}")
    spec = importlib.util.spec_from_file_location(f"transform_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "apply"):
        raise RetellError(f"transform {name!r} has no apply(flow) function")
    return mod


def assert_draft(client, cfg, flow_version):
    """Refuse to target anything but a draft.

    Agent version N carries conversation-flow version N. If the agent version
    matching this flow version is published, that is the immutable version
    serving live traffic, and we stop.
    """
    # list_agent_versions rows are summaries with no response_engine, so read
    # each full agent version, newest first, until one carries this flow.
    rows = client.list_agent_versions(cfg["agent_id"])
    match = None
    for r in rows:
        full = client.get_agent(cfg["agent_id"], version=r.get("version"))
        eng = full.get("response_engine") or {}
        if eng.get("version") == flow_version or r.get("version") == flow_version:
            match = dict(r, response_engine=eng)
            break
    if match is None:
        raise RetellError(
            f"no agent version found carrying flow version {flow_version}. "
            f"Refusing to write blind.")
    if match.get("is_published"):
        raise RetellError(
            f"agent version v{match.get('version')} is PUBLISHED and is serving "
            f"live traffic. Published versions are immutable and are never a "
            f"target.\nMake a fresh draft first:\n"
            f"  create_agent_version({cfg['agent_id']}, base_version="
            f"{match.get('version')})")
    latest = rows[0] if rows else None
    if latest and latest.get("version") != match.get("version"):
        raise RetellError(
            f"flow version {flow_version} is not the latest agent version "
            f"(latest is v{latest.get('version')}). update-conversation-flow "
            f"writes the latest draft, so this would not land where you expect.")
    return match


def run(client_name, agent_slug, transform_name, lines=(), push=False, env=None):
    env = env if env is not None else load_env()
    cfg = agent_config(client_name, agent_slug)
    client = RetellClient(env)
    transform = load_transform(transform_name)

    print("=" * 72)
    print(f"flowapply  {'PUSH' if push else 'DRY RUN'}")
    print(f"  agent      : {client_name}/{agent_slug}  ({cfg['agent_id']})")
    print(f"  flow_id    : {cfg['flow_id']}")
    print(f"  transform  : {getattr(transform, 'NAME', transform_name)} - "
          f"{getattr(transform, 'DESCRIPTION', '')}")
    print("=" * 72)

    # --- 2. GET (before the guard, so we know which version we are aimed at)
    print("\n[1/5] GET current flow from Retell ...")
    before = client.get_flow(cfg["flow_id"])
    version = before.get("version")
    print(f"      got version {version}, {len(before.get('nodes', []))} nodes")

    # --- 1. draft guard
    print("\n[2/5] Draft guard ...")
    row = assert_draft(client, cfg, version)
    print(f"      agent v{row.get('version')} is a DRAFT (base={row.get('base_version')}). OK.")

    # --- 3. transform
    print(f"\n[3/5] Run transform {transform_name!r} ...")
    after = transform.apply(copy.deepcopy(before))
    if not isinstance(after, dict) or "nodes" not in after:
        raise RetellError("transform did not return a ConversationFlow object")
    changed = json.dumps(before, sort_keys=True) != json.dumps(after, sort_keys=True)
    print(f"      flow changed: {changed}")

    # --- 4. lint the RESULT in memory
    print("\n[4/5] flowlint on the transformed flow (in memory) ...\n")
    rep = flowlint.build_report(flowlint.from_object(after), lines)
    flowlint.print_report(rep)
    clean = flowlint.report_is_clean(rep)
    print(f"\n      lint verdict: {'CLEAN' if clean else 'FINDINGS ABOVE'}")

    # --- 5. save locally, do not push
    out = Path(cfg["exports"]) / f"v{version}-{transform_name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(after, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(f"\n[5/5] Saved locally: {out}")

    if not push:
        print("\nDRY RUN. Nothing was written to Retell.")
        print(f"To push, re-run with --push:")
        print(f"  python tools/flowapply.py --client {client_name} --agent {agent_slug} "
              f"--transform {transform_name} --push")
        print("Publishing is NOT part of --push. It stays a separate manual step.")
        return 0

    if not changed:
        print("\nRefusing to push: the transform changed nothing.")
        return 1
    if not clean:
        print("\nRefusing to push: flowlint reported findings. Fix them first.")
        return 1

    print("\nPATCH /update-conversation-flow ...")
    result = client.update_flow(cfg["flow_id"], after)
    print(f"      draft now at version {result.get('version')}, "
          f"{len(result.get('nodes', []))} nodes")
    print("\nPushed to the DRAFT only. Nothing was published.")
    print("Pull a fresh snapshot to verify what landed:")
    print(f"  python tools/flowpull.py --client {client_name} --agent {agent_slug}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Safe Retell edit loop. Dry run by default: GETs, "
                    "transforms, lints, saves locally, and stops. Never publishes.")
    ap.add_argument("--client", required=True, help="client folder name")
    ap.add_argument("--agent", required=True, help="agent slug under <client>/agents/")
    ap.add_argument("--transform", required=True,
                    help="name of a module in transforms/, e.g. noop")
    ap.add_argument("--line", action="append", default=[],
                    help="exact spoken sentence to double-say check (repeatable)")
    ap.add_argument("--push", action="store_true",
                    help="actually PATCH the draft. Requires a clean lint and a "
                         "real change. Still never publishes.")
    a = ap.parse_args(argv)
    return run(a.client, a.agent, a.transform, a.line, a.push)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RetellError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
