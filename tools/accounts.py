#!/usr/bin/env python3
"""List the accounts in .env and pick which one a client uses. Never prints
a value.

    python tools/accounts.py list                       every service, every account, which is active
    python tools/accounts.py list --client acme         the same, as seen from that client's folder
    python tools/accounts.py use --client acme retell=acme n8n=acme make=main
    python tools/accounts.py template n8n acme          the key lines to paste into .env for a new account

`use` writes `<SERVICE>_ACCOUNT=<name>` lines into <client>/.env.local
(git-ignored), replacing any earlier choice for that service. Every kit
tool run from that client folder then reaches that account. It refuses an
account name that has no keys in .env.

Conventions: kit/accounts.py.
"""
import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "kit"))
import accounts  # noqa: E402
from retellkit import KIT_ROOT, RetellError, clients_root, load_env, _parse_env_file  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

# Which keys an account of each service needs. Used by `template`.
KEYS = {
    "retell": ["RETELL_API_KEY"],
    "n8n": ["N8N_BASE_URL", "N8N_API_KEY", "N8N_MCP_URL", "N8N_MCP_TOKEN"],
    "make": ["MAKE_API_TOKEN", "MAKE_ZONE", "MAKE_TEAM_ID", "MAKE_MCP_TOKEN"],
    "modal": ["MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET", "MODAL_ENVIRONMENT"],
    "ghl": ["GHL_API_KEY", "GHL_LOCATION_ID"],
    "hubspot": ["HUBSPOT_PRIVATE_APP_TOKEN"],
    "twilio": ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN"],
    "calcom": ["CALCOM_API_KEY"],
    "zapier": ["ZAPIER_WEBHOOK_URL"],
}


def raw_env(start):
    """Every layer merged, before account resolution, so a bad selector is
    reported instead of raised."""
    env = _parse_env_file(Path.home() / ".retell.env")
    env.update(_parse_env_file(KIT_ROOT / ".env"))
    env.update(_parse_env_file(Path(start) / ".env.local"))
    for k, v in os.environ.items():
        if v and k.startswith(tuple(accounts.SERVICES.values())):
            env[k] = v
    return env


def cmd_list(a):
    start = clients_root() / a.client if a.client else Path.cwd()
    env = raw_env(start)
    print(f"(as seen from {start})")
    try:
        lines = accounts.summary(env)
    except accounts.AccountError as exc:
        print(f"ERROR: {exc}")
        return 1
    print("\n".join(lines) or "No KEY__ACCOUNT keys in .env yet. See: accounts.py template")
    plain = [k for k in env if not accounts.SUFFIX.match(k) and env[k]
             and any(k.startswith(p) for p in accounts.SERVICES.values())
             and not k.endswith("_ACCOUNT") and k != "RETELL_BASE_URL"]
    if plain:
        print("\nWARN plain keys also set (used when no account is selected): " + ", ".join(sorted(plain)))
    return 0


def cmd_use(a):
    folder = clients_root() / a.client
    if not folder.is_dir():
        raise RetellError(f"no client folder {folder}")
    env = raw_env(folder)
    picks = {}
    for pair in a.pairs:
        if "=" not in pair:
            raise RetellError(f"expected service=account, got {pair!r}")
        svc, acct = (x.strip().lower() for x in pair.split("=", 1))
        if svc not in accounts.SERVICES:
            raise RetellError(f"unknown service {svc!r}. Known: {', '.join(accounts.SERVICES)}")
        if acct.upper() not in accounts.accounts_in(env, svc):
            raise RetellError(f"no {svc} account {acct!r} in .env."
                              + accounts.hint(env, svc))
        picks[accounts.selector_key(svc)] = acct
    path = folder / ".env.local"
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    lines = [l for l in lines if l.split("=", 1)[0].strip() not in picks]
    lines += [f"{k}={v}" for k, v in picks.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {path}:")
    for k, v in picks.items():
        print(f"  {k}={v}")
    load_env(folder)  # proves the choice resolves
    return 0


def cmd_template(a):
    svc, acct = a.service.lower(), re.sub(r"[^A-Za-z0-9_]", "_", a.account).upper()
    if svc not in KEYS:
        raise RetellError(f"no template for {svc}. Known: {', '.join(KEYS)}")
    print(f"# {svc} account: {acct.lower()}   (paste into {KIT_ROOT / '.env'}, fill the values)")
    for k in KEYS[svc]:
        print(f"{k}__{acct}=")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list")
    p.add_argument("--client")
    p = sub.add_parser("use")
    p.add_argument("--client", required=True)
    p.add_argument("pairs", nargs="+", help="service=account, e.g. retell=acme")
    p = sub.add_parser("template")
    p.add_argument("service")
    p.add_argument("account")
    a = ap.parse_args(argv)
    return {"list": cmd_list, "use": cmd_use, "template": cmd_template}[a.cmd](a)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RetellError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
