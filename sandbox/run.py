#!/usr/bin/env python3
"""Run a client's traces against a flow in a throwaway sandbox.

Thin wrapper over tools/tracerun.py, kept here so the build order in
AGENTS.md can point at one place for "run a sandbox test". See
sandbox/README.md for what this costs and how cleanup works.

Refuses to start without a cost go-ahead (--yes), and refuses a model not
listed in sandbox/config.json.

Usage:
    python sandbox/run.py --client acme --agent intake --yes
    python sandbox/run.py --client acme --agent intake --file export.json --yes
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import tracerun  # noqa: E402


def main(argv=None):
    argv = list(argv if argv is not None else sys.argv[1:])
    if "--yes" not in argv:
        print("Refusing to start without a cost go-ahead. Run cost-gate, "
              "then re-run with --yes.", file=sys.stderr)
        return 1
    return tracerun.main(argv)


if __name__ == "__main__":
    sys.exit(main())
