#!/usr/bin/env python3
"""Re-send stored Retell calls to a downstream webhook, for calls that never
got one.

WHY THIS EXISTS

A version can be published with `webhook_url` unset, so every call answered
on it is analysed normally by Retell and then forwarded nowhere. The client
hears nothing about calls that already happened.

Nothing was lost. Retell keeps the whole call, including `call_analysis`
with every custom field. This tool reads those calls back and POSTs them to
a webhook in the same envelope Retell would have used, so the existing
downstream workflow produces the output it always would have. Use
`delivery-check` first to confirm the gap is closed before replaying the
backlog into it.

WHAT IT SENDS

Retell's documented `call_analyzed` envelope, and nothing else:

    {"event": "call_analyzed", "call": { ...the stored call object... }}

signed the way Retell signs it, so a workflow that verifies will accept it:

    X-Retell-Signature: v={unix_ms},d={hmac_sha256(body + timestamp, api_key)}

See https://docs.retellai.com/features/secure-webhook. The timestamp is fresh,
so the 5-minute replay window is satisfied.

GUARDS

- **Dry run by default.** It prints what it would send and sends nothing.
  `--send` is required to POST, and it will not run without `--yes`.
- Read-only against Retell. It never writes to the flow or the agent.
- It refuses to send to any host other than the webhook URL currently set on
  the agent, so a typo cannot leak caller data somewhere new.
- Caller PII is never printed in full and never written into the repository.
  Use `--out` to write a full report, and put it OUTSIDE the repo.

USAGE

    python tools/webhookreplay.py --client acme --agent intake --versions 24,25,26
    python tools/webhookreplay.py --client acme --agent intake --versions 24,25,26 --all
    python tools/webhookreplay.py --client acme --agent intake --call call_xxx --send --yes
    python tools/webhookreplay.py --client acme --agent intake --versions 24,25,26 --send --yes
"""
import sys
import json
import time
import hmac
import hashlib
import argparse
import datetime
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "kit"))
from retellkit import RetellClient, RetellError, agent_config, load_env

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass


# ---------------------------------------------------------------- classifying

MIN_SECONDS_TO_COUNT = 20


def classify(call, contact_field="preferred_callback_number", name_field="caller_name"):
    """HAS_DATA or EMPTY, by whether the call captured anything useful.

    This is a generic, field-name-agnostic default: a short call, or one with
    neither a contact number nor a name in its analysis data, is EMPTY.
    Everything else is HAS_DATA.

    A real agent's schema usually has richer categories (a lead versus a
    spam call versus a message), because every agent defines its own
    `post_call_analysis_data` field names. Adapt this function per client if
    you need those categories back; do not assume any field name here is
    universal.
    """
    cd = (call.get("call_analysis") or {}).get("custom_analysis_data") or {}
    secs = (call.get("duration_ms") or 0) / 1000
    has_contact = bool(str(cd.get(contact_field) or "").strip())
    has_name = bool(str(cd.get(name_field) or "").strip())

    if secs < MIN_SECONDS_TO_COUNT or not (has_contact or has_name):
        return "EMPTY"
    return "HAS_DATA"


# ---------------------------------------------------------------- fetching
def gap_calls(client, agent_id, versions=None, call_id=None):
    if call_id:
        return [client._request("GET", "/v2/get-call/{}".format(call_id))]

    items, key = [], None
    while True:
        body = {"limit": 1000, "filter_criteria": {"agent_id": [agent_id]}}
        if key:
            body["pagination_key"] = key
        page = client._request("POST", "/v3/list-calls", body)
        items += page["items"]
        if not page.get("has_more"):
            break
        key = page.get("pagination_key")

    if versions:
        items = [i for i in items if i.get("agent_version") in versions]
    items.sort(key=lambda x: x.get("start_timestamp") or 0)
    return [client._request("GET", "/v2/get-call/{}".format(i["call_id"]))
            for i in items]


# ---------------------------------------------------------------- sending
def sign(body_bytes, api_key):
    """Retell's scheme: v={unix_ms},d={hmac_sha256(body + timestamp, key)}."""
    ts = str(int(time.time() * 1000))
    mac = hmac.new(api_key.encode("utf-8"),
                   body_bytes + ts.encode("utf-8"),
                   hashlib.sha256).hexdigest()
    return f"v={ts},d={mac}"


def post(url, call, api_key, timeout=20):
    body = json.dumps({"event": "call_analyzed", "call": call},
                      ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json",
                 "X-Retell-Signature": sign(body, api_key)})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, (r.read()[:200] or b"").decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, (e.read()[:200] or b"").decode("utf-8", "replace")
    except Exception as e:                              # noqa: BLE001
        return 0, f"{type(e).__name__}: {e}"


# ---------------------------------------------------------------- reporting
def when(ms):
    if not ms:
        return "-"
    return datetime.datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%M")


def mask(s):
    """Enough to recognise the call, not enough to be a contact record."""
    s = str(s or "").strip()
    if not s:
        return "-"
    return s[:2] + "*" * max(0, len(s) - 4) + s[-2:] if len(s) > 4 else "****"


def line(n, call, verdict):
    cd = (call.get("call_analysis") or {}).get("custom_analysis_data") or {}
    secs = (call.get("duration_ms") or 0) / 1000
    return ("{:>3} {:<17} v{:<3} {:>5.0f}s  {:<8} {:<14} {}".format(
        n, when(call.get("start_timestamp")), call.get("agent_version"),
        secs, verdict, mask(cd.get("caller_name")),
        str(cd.get("issue_summary") or cd.get("call_type") or "")[:44]))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--client", required=True, help="client folder name")
    ap.add_argument("--agent", required=True, help="agent slug under <client>/agents/")
    ap.add_argument("--versions", help="agent versions to replay, e.g. 24,25,26")
    ap.add_argument("--call", help="one call id instead of a version range")
    ap.add_argument("--all", action="store_true",
                    help="send every call, including ones classified EMPTY")
    ap.add_argument("--skip", default="",
                    help="comma-separated call ids to leave out, so a call "
                         "already delivered is never sent twice")
    ap.add_argument("--send", action="store_true", help="actually POST")
    ap.add_argument("--yes", action="store_true", help="skip the confirmation")
    ap.add_argument("--out", help="write a full report here. Keep it OUT of the repo.")
    ap.add_argument("--url",
                    help="send to this webhook path instead of the agent's own. "
                         "The HOST must still match the agent's webhook_url, so a "
                         "typo cannot leak caller data to a new server. Use it to "
                         "aim a replay at a throwaway test workflow on the same "
                         "n8n instance.")
    a = ap.parse_args()

    env = load_env()
    cfg = agent_config(a.client, a.agent)
    client = RetellClient(env)

    agent = client.get_agent(cfg["agent_id"])
    url = agent.get("webhook_url")
    if not url:
        raise RetellError("the agent has no webhook_url set; nothing to replay to")

    if a.url:
        # Same-host guard. The point of --url is a different PATH on the same n8n
        # instance, for a throwaway test workflow. It is never a different server.
        from urllib.parse import urlparse
        want, have = urlparse(a.url), urlparse(url)
        if (want.scheme, want.netloc) != (have.scheme, have.netloc):
            raise RetellError(
                "--url host %r does not match the agent's webhook host %r; refusing"
                % (want.scheme + "://" + want.netloc, have.scheme + "://" + have.netloc))
        print("NOTE: sending to an override path, not the agent's own webhook.")
        print("      agent webhook : %s" % url)
        print("      override      : %s" % a.url)
        url = a.url

    versions = None
    if a.versions:
        versions = {int(v) for v in a.versions.split(",")}

    calls = gap_calls(client, cfg["agent_id"], versions, a.call)
    verdicts = [(c, classify(c)) for c in calls]
    wanted = ("HAS_DATA", "EMPTY") if a.all else ("HAS_DATA",)
    skip = {s.strip() for s in a.skip.split(",") if s.strip()}
    todo = [(c, v) for c, v in verdicts
            if v in wanted and c["call_id"] not in skip]

    print("=" * 78)
    print("webhookreplay")
    print("  agent   : {}".format(f"{a.client}/{a.agent}"))
    print("  webhook : {}".format(url))
    print("  scope   : {}".format(
        "call " + a.call if a.call else "agent versions " + str(sorted(versions or []))))
    print("  found   : {} calls, sending {}".format(len(calls), len(todo)))
    print("=" * 78)

    counts = {}
    for n, (c, v) in enumerate(verdicts, 1):
        counts[v] = counts.get(v, 0) + 1
        if c["call_id"] in skip:
            mark = "DONE"
        else:
            mark = "SEND" if (c, v) in todo else "skip"
        print("{}  {}".format(mark, line(n, c, v)))
    print("\n  " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))

    if a.out:
        Path(a.out).write_text(
            json.dumps([c for c, _ in todo], indent=1, ensure_ascii=False),
            encoding="utf-8")
        print("\n  full records written to {} (contains caller PII)".format(a.out))

    if not a.send:
        print("\nDRY RUN. Nothing was sent.")
        print("To send, re-run with --send --yes")
        return 0

    if not a.yes:
        print("\nrefusing to send without --yes")
        return 1

    print("\nsending {} calls to {} ...".format(len(todo), url))
    ok = 0
    for c, v in todo:
        status, body = post(url, c, client._key)
        good = 200 <= status < 300
        ok += good
        print("  {}  {}  HTTP {} {}".format(
            "ok  " if good else "FAIL", c["call_id"][:28], status, body[:80]))
    print("\n{} of {} accepted.".format(ok, len(todo)))
    print("Nothing was written to the Retell flow or agent.")
    return 0 if ok == len(todo) else 1


if __name__ == "__main__":
    sys.exit(main())
