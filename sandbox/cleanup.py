#!/usr/bin/env python3
"""Delete any leftover throwaway sandbox agents and flows.

Thin wrapper over tools/retell_chat.py cleanup. Matches only the
`zz-sandbox-` name prefix, so it can never delete anything this kit did
not create itself. Run this at the end of any session that ran a sandbox
test, and always after a crash.

Usage:
    python sandbox/cleanup.py
    python sandbox/cleanup.py --all
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import retell_chat  # noqa: E402


def main(argv=None):
    argv = list(argv if argv is not None else sys.argv[1:])
    return retell_chat.main(["cleanup", *argv])


if __name__ == "__main__":
    sys.exit(main())
