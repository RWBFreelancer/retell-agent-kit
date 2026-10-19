#!/usr/bin/env python3
"""Modal (modal.com): run the `modal` CLI against the account you pick, for
the Python apps a Retell agent calls (custom functions, webhook receivers,
post-call processing). Account-aware: MODAL_ACCOUNT (kit/accounts.py).

Keys, per account (modal.com > Settings > API Tokens > New token):
    MODAL_TOKEN_ID__<ACCT>       ak-...
    MODAL_TOKEN_SECRET__<ACCT>   as-...
    MODAL_ENVIRONMENT__<ACCT>    optional, e.g. main or dev

The modal CLI reads MODAL_TOKEN_ID / MODAL_TOKEN_SECRET before
~/.modal.toml, so this tool passes the selected account's pair to the child
process only. It never writes ~/.modal.toml and never prints a token.

Needs `pip install modal`.

READ (free)

    python kit/modalkit.py ping                  proves the token works: lists environments
    python kit/modalkit.py apps                  deployed apps and their state
    python kit/modalkit.py logs <app-name>       stream logs (Ctrl+C to stop)
    python kit/modalkit.py secrets               secret NAMES, never values

WRITE (dry run unless --apply)

    python kit/modalkit.py deploy <app.py> [--apply]   a persistent deployment
    python kit/modalkit.py serve  <app.py> [--apply]   a temporary dev URL

A deploy replaces what a live agent calls if the agent points at that app's
URL. Treat a deploy of a live app like a publish: get a go-ahead first.
Modal bills compute per second while a function runs; `serve` and `deploy`
both start billable containers when called.

Create a secret in the Modal dashboard, or with `modal secret create` typed
by hand in your own shell. Never pass a secret value through this tool.
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from integrationkit import IntegrationError, need  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass


def modal_cmd():
    exe = shutil.which("modal")
    if exe:
        return [exe]
    try:
        import modal  # noqa: F401
        return [sys.executable, "-m", "modal"]
    except ImportError:
        raise IntegrationError("modal is not installed. Run: pip install modal") from None


def child_env():
    vals, env = need("modal", "MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET")
    e = dict(os.environ)
    for k in list(e):
        if k.startswith("MODAL_"):
            del e[k]  # never mix a shell token with the selected account
    e.update(vals)
    if env.get("MODAL_ENVIRONMENT"):
        e["MODAL_ENVIRONMENT"] = env["MODAL_ENVIRONMENT"]
    return e, env.get("MODAL_ACCOUNT") or "(default)"


def run(args, dry=False):
    e, account = child_env()
    cmd = modal_cmd() + args
    print(f"(modal account {account}) $ modal {' '.join(args)}")
    if dry:
        print("DRY RUN. Re-run with --apply to execute. Nothing was sent.")
        return 0
    return subprocess.call(cmd, env=e)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Modal CLI for the selected account.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ping")
    sub.add_parser("apps")
    p = sub.add_parser("logs")
    p.add_argument("app")
    sub.add_parser("secrets")
    for name in ("deploy", "serve"):
        p = sub.add_parser(name)
        p.add_argument("file")
        p.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "ping":
        return run(["environment", "list"])
    if a.cmd == "apps":
        return run(["app", "list"])
    if a.cmd == "logs":
        return run(["app", "logs", a.app])
    if a.cmd == "secrets":
        return run(["secret", "list"])
    if not Path(a.file).exists():
        raise IntegrationError(f"no file {a.file}")
    return run([a.cmd, a.file], dry=not a.apply)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except IntegrationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
