#!/usr/bin/env python3
"""Print which .env keys are set, never their values.

Reads the key names listed in .env.example (an account suffix such as
__ACME is stripped, so each key is listed once), resolves accounts the same
way every kit tool does (kit/accounts.py), and reports each key as set or
missing for the accounts active here. Then lists the accounts per service.

Exits 1 if a key named with --need is missing, so a skill or a CI step can
gate on it without ever seeing a value.

Usage:
    python tools/envcheck.py
    python tools/envcheck.py --need RETELL_API_KEY --need N8N_API_KEY
    (run from a client folder to see that client's accounts)
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "kit"))
import accounts  # noqa: E402
from retellkit import RetellError, load_env  # noqa: E402


def env_example_keys(path):
    keys = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip().lstrip("#").strip()
        m = re.match(r"^([A-Z0-9_]+?)(__[A-Z0-9_]+)?=", line)
        if m and m.group(1) not in keys and not m.group(1).endswith("_ACCOUNT"):
            keys.append(m.group(1))
    return keys


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--need", action="append", default=[],
                    help="a key this task needs; repeatable. Exit 1 if any "
                         "named key is missing")
    a = ap.parse_args(argv)

    example = ROOT / ".env.example"
    keys = env_example_keys(example) if example.exists() else []
    try:
        env = load_env()
    except RetellError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print("key                                   status")
    print("-" * 55)
    for k in keys:
        status = "set" if str(env.get(k, "")).strip() else "missing"
        print(f"{k:<38} {status}")

    lines = accounts.summary(env)
    if lines:
        print("\naccounts")
        print("-" * 55)
        print("\n".join(lines))

    if a.need:
        missing = [k for k in a.need if not str(env.get(k, "")).strip()]
        if missing:
            print(f"\nmissing required keys: {', '.join(missing)}", file=sys.stderr)
            return 1
        print(f"\nall required keys set: {', '.join(a.need)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
