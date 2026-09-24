#!/usr/bin/env python3
"""Print which .env keys are set, never their values.

Reads the same keys listed in .env.example. Exits 1 if a key named with
--need is missing, so a skill or a CI step can gate on it without ever
seeing a value.

Usage:
    python tools/envcheck.py
    python tools/envcheck.py --need RETELL_API_KEY --need N8N_API_KEY
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def env_example_keys(path):
    keys = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([A-Z0-9_]+)=", line)
        if m:
            keys.append(m.group(1))
    return keys


def parse_env_file(path):
    env = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        env[key.strip()] = val.split("#")[0].strip().strip('"').strip("'")
    return env


def load_all(start):
    """Global env, repo .env, and .env.local, in that order. Later wins."""
    env = {}
    global_env = Path.home() / ".retell.env"
    env.update(parse_env_file(global_env))
    here = Path(start).resolve()
    for d in [here, *here.parents]:
        if (d / ".git").exists() or (d / ".env").exists():
            env.update(parse_env_file(d / ".env"))
            break
    env.update(parse_env_file(here / ".env.local"))
    import os
    for k, v in os.environ.items():
        if v:
            env[k] = v
    return env


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--need", action="append", default=[],
                    help="a key this task needs; repeatable. Exit 1 if any "
                         "named key is missing")
    a = ap.parse_args(argv)

    example = ROOT / ".env.example"
    keys = env_example_keys(example) if example.exists() else []
    env = load_all(Path.cwd())

    print("key                                   status")
    print("-" * 55)
    for k in keys:
        status = "set" if env.get(k, "").strip() else "missing"
        print(f"{k:<38} {status}")

    if a.need:
        missing = [k for k in a.need if not env.get(k, "").strip()]
        if missing:
            print(f"\nmissing required keys: {', '.join(missing)}", file=sys.stderr)
            return 1
        print(f"\nall required keys set: {', '.join(a.need)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
