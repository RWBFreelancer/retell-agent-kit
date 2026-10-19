#!/usr/bin/env python3
"""Several accounts per service in one .env, and a switch to pick one.

WHY THIS EXISTS

One person works for many clients. Each client can have its own Retell
workspace, its own n8n instance, its own Make organization, its own Modal
workspace. Keeping one key per service and swapping it by hand is how an
edit lands on the wrong client's agent.

THE CONVENTION

Store every account's keys once, with a double-underscore suffix naming the
account:

    RETELL_API_KEY__ACME=key_xxx
    RETELL_API_KEY__NINJA=key_yyy
    N8N_BASE_URL__ACME=https://acme.app.n8n.cloud
    N8N_API_KEY__ACME=xxx

Pick one account per service with a selector, `<SERVICE>_ACCOUNT`:

    RETELL_ACCOUNT=acme
    N8N_ACCOUNT=acme

The selected account's keys are promoted to the plain names
(`RETELL_API_KEY`, `N8N_BASE_URL`, ...), so every tool reads the plain name
and never needs to know accounts exist.

WHERE THE SELECTOR COMES FROM (later wins)

    1. the kit's .env, or the repo .env      (your default accounts)
    2. <client>/.env.local                   (this client's accounts)
    3. the process environment               (a one-off override)

PowerShell one-off:  $env:N8N_ACCOUNT='acme'; python kit/n8nkit.py ping
Bash one-off:        N8N_ACCOUNT=acme python kit/n8nkit.py ping

SAFETY RULES

  - A selector that names an account with no keys is an error, never a
    silent fall-back to another account.
  - With no selector and exactly one account defined, that account is used.
  - With no selector and several accounts, nothing is promoted. A tool that
    needs the key then fails with a message naming the accounts it saw.
  - Values are never printed. `summary()` returns account names only.
"""
import re

# Service name -> key prefix. A key belongs to a service when it starts
# with the prefix. Add a row here to make a new service account-aware.
SERVICES = {
    "retell": "RETELL_",
    "n8n": "N8N_",
    "make": "MAKE_",
    "modal": "MODAL_",
    "ghl": "GHL_",
    "hubspot": "HUBSPOT_",
    "zapier": "ZAPIER_",
    "twilio": "TWILIO_",
    "calcom": "CALCOM_",
    "google": "GOOGLE_",
    "openai": "OPENAI_",
    "anthropic": "ANTHROPIC_",
    "openrouter": "OPENROUTER_",
    "webhook": "WEBHOOK_",
}
SUFFIX = re.compile(r"^(?P<key>[A-Z0-9_]+?)__(?P<account>[A-Z0-9_]+)$")


class AccountError(RuntimeError):
    pass


def selector_key(service):
    return SERVICES[service] + "ACCOUNT"


def accounts_in(env, service):
    """{ACCOUNT: [plain key names]} for one service. Names only."""
    prefix = SERVICES[service]
    out = {}
    for k in env:
        m = SUFFIX.match(k)
        if m and m["key"].startswith(prefix):
            out.setdefault(m["account"], []).append(m["key"])
    return {a: sorted(keys) for a, keys in sorted(out.items())}


def resolve(env):
    """Return (env, picks). `env` is a new dict with each selected account's
    keys promoted to their plain names. `picks` maps service -> (account,
    how) where how is 'selected', 'only one', or None."""
    env = dict(env)
    picks = {}
    for service in SERVICES:
        accts = accounts_in(env, service)
        chosen = str(env.get(selector_key(service), "") or "").strip().upper()
        how = "selected" if chosen else None
        if not chosen and len(accts) == 1:
            chosen, how = next(iter(accts)), "only one"
        if not chosen:
            picks[service] = (None, None)
            continue
        if chosen not in accts:
            raise AccountError(
                f"{selector_key(service)}={chosen.lower()} but no "
                f"{SERVICES[service]}*__{chosen} keys exist. "
                f"Accounts seen for {service}: "
                f"{', '.join(a.lower() for a in accts) or 'none'}.")
        for plain in accts[chosen]:
            env[plain] = env[f"{plain}__{chosen}"]
        env[selector_key(service)] = chosen.lower()  # tools can report which account
        picks[service] = (chosen.lower(), how)
    return env, picks


def summary(env):
    """Lines describing accounts per service, never a value."""
    _, picks = resolve(env)
    lines = []
    for service in SERVICES:
        accts = accounts_in(env, service)
        if not accts:
            continue
        active, how = picks.get(service, (None, None))
        names = ", ".join(a.lower() for a in accts)
        if active:
            state = f"active: {active} ({how})"
        else:
            state = f"active: NONE, set {selector_key(service)}"
        lines.append(f"{service:<10} accounts: {names:<32} {state}")
    return lines


def hint(env, service):
    """One sentence to append to a 'key missing' error."""
    accts = accounts_in(env, service)
    if not accts:
        return ""
    return (f" Accounts defined for {service}: "
            f"{', '.join(a.lower() for a in accts)}. "
            f"Pick one with {selector_key(service)}=<name>.")
