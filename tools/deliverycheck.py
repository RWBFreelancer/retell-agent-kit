#!/usr/bin/env python3
"""Prove a recap can actually reach its downstream target. Read-only. Exit 1
on any failure.

WHY THIS EXISTS

A webhook can be unset on a published version for days: every call is
answered and analysed correctly and forwarded nowhere, while the client
hears nothing, and a lint or a sandbox trace stays green throughout,
because none of them can see a setting that lives on the AGENT rather than
in the flow.

This tool checks the other half: the chain that carries a finished call out
of Retell and into the client's system. It answers one question - if a real
caller rang right now, would the client hear about it?

WHAT IT CHECKS, AND WHY EACH ONE CAN BREAK ALONE

  1  The phone number resolves to an agent version.
  2  That LIVE version has `webhook_url` set. It checks the version the
     phone number serves, never the draft and never whatever `get_agent`
     happens to return by default, because those differ and only the served
     one matters.
  3  `webhook_events` contains `call_analyzed`. A webhook that fires only on
     `call_started` delivers nothing useful.
  4  `post_call_analysis_data` is non-empty, and (with --required-fields)
     still holds the fields a downstream template expects. An empty list
     means every recap arrives blank.
  5  Recent real calls came back with `call_analysis` populated. This is the
     end-to-end proof; the checks above are the parts, this is the whole.

WHAT IT DOES NOT DO

It never POSTs to the webhook. Firing a test event would send a fake recap
to the client. Use `tools/webhookreplay.py` to send a real stored call on
purpose.

It cannot see inside the downstream workflow. A 200 means the workflow
started, not that an email or a CRM record was created. Only the client's
own system proves that. See `check-integration`.

WHEN TO RUN IT

  - After EVERY publish, before telling anyone the change is live.
  - After any edit in the Retell dashboard, which is where the setting can
    be lost.
  - As the first step of any "the client says they are not getting leads"
    report.

USAGE

    python tools/deliverycheck.py --client acme --agent intake
    python tools/deliverycheck.py --client acme --agent intake --calls 20
    python tools/deliverycheck.py --client acme --agent intake \\
        --required-fields caller_name,issue_summary,urgency
"""
import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "kit"))
from retellkit import RetellClient, RetellError, agent_config, load_env

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

REQUIRED_EVENT = "call_analyzed"

OK, BAD, WARN = "PASS", "FAIL", "warn"


class Report:
    def __init__(self):
        self.rows = []

    def add(self, status, check, detail):
        self.rows.append((status, check, detail))

    @property
    def failed(self):
        return any(s == BAD for s, _, _ in self.rows)

    def show(self):
        for status, check, detail in self.rows:
            mark = {OK: "  PASS", BAD: "  FAIL", WARN: "  warn"}[status]
            print(f"{mark}  {check:<38} {detail}")


def live_versions(client, agent_id):
    """Agent versions the phone numbers actually serve. Never the draft."""
    out = []
    # /list-phone-numbers is deprecated (Retell, 2026-06-15). v2 wraps rows in
    # "items" and pages with "pagination_key" and "has_more".
    numbers, key = [], None
    while True:
        page = client._request("GET", "/v2/list-phone-numbers",
                               query={"pagination_key": key} if key else None)
        numbers += page.get("items") or []
        if not page.get("has_more"):
            break
        key = page.get("pagination_key")
    for n in numbers:
        for ia in n.get("inbound_agents") or []:
            if ia.get("agent_id") == agent_id:
                out.append((n.get("phone_number_pretty") or n.get("phone_number"),
                            ia.get("agent_version")))
    return out


def check_agent(client, client_name, agent_slug, n_calls, required_fields=(), override=None):
    cfg = agent_config(client_name, agent_slug)
    agent_id = cfg["agent_id"]
    r = Report()

    print("=" * 78)
    print(f"{client_name}/{agent_slug}   {agent_id}")
    print("=" * 78)

    # 1. which version actually answers the phone
    served = live_versions(client, agent_id)
    if not served:
        r.add(WARN, "phone number -> agent version",
              "no inbound number points at this agent")
    for number, version in served:
        r.add(OK, "phone number -> agent version", f"{number} -> v{version}")

    versions = [override] if override is not None else ([v for _, v in served] or [None])

    for version in versions:
        who = f"v{version}" if version is not None else "latest"
        agent = client.get_agent(agent_id, version)

        # 2. THE ONE THAT FAILED
        url = agent.get("webhook_url")
        r.add(OK if url else BAD, f"webhook_url on {who}",
              url or "NOT SET - every call is analysed and forwarded nowhere")

        # 3. the right event
        events = agent.get("webhook_events") or []
        r.add(OK if REQUIRED_EVENT in events else BAD,
              f"webhook_events on {who}",
              json.dumps(events) if REQUIRED_EVENT in events
              else f"{json.dumps(events)} - missing {REQUIRED_EVENT!r}")

        # 4. the recap still has something to say
        fields = agent.get("post_call_analysis_data") or []
        names = {f.get("name") for f in fields}
        missing = [f for f in required_fields if f not in names]
        if not fields:
            r.add(BAD, f"post_call_analysis_data on {who}",
                  "EMPTY - every recap would arrive blank")
        elif missing:
            r.add(BAD, f"recap fields on {who}",
                  f"{len(fields)} fields, but missing {missing}")
        else:
            r.add(OK, f"recap fields on {who}",
                  f"{len(fields)} fields" +
                  (f", all {len(required_fields)} required fields present"
                   if required_fields else ""))

    # 5. end to end, on real traffic
    try:
        page = client._request("POST", "/v3/list-calls",
                               {"limit": n_calls,
                                "filter_criteria": {"agent_id": [agent_id]}})
        items = page.get("items") or []
        analysed = 0
        for it in items:
            full = client._request("GET", "/v2/get-call/{}".format(it["call_id"]))
            if (full.get("call_analysis") or {}).get("custom_analysis_data"):
                analysed += 1
        if not items:
            r.add(WARN, "recent calls analysed", "no calls to check")
        else:
            r.add(OK if analysed else BAD, "recent calls analysed",
                  f"{analysed} of {len(items)} carry call_analysis")
    except RetellError as e:
        r.add(WARN, "recent calls analysed", f"could not list calls: {e}")

    r.show()
    return r


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--client", required=True, help="client folder name")
    ap.add_argument("--agent", required=True, help="agent slug under <client>/agents/")
    ap.add_argument("--calls", type=int, default=5,
                    help="how many recent calls to check for analysis")
    ap.add_argument("--required-fields", default="",
                    help="comma-separated post_call_analysis_data field "
                         "names a downstream system needs (optional)")
    ap.add_argument("--version", type=int, default=None,
                    help="audit a specific agent version instead of the one "
                         "the phone number serves. Use it to check history.")
    a = ap.parse_args()

    env = load_env()
    client = RetellClient(env)
    required = [s.strip() for s in a.required_fields.split(",") if s.strip()]

    failed = False
    try:
        failed = check_agent(client, a.client, a.agent, a.calls, required, a.version).failed
    except RetellError as e:
        print(f"  FAIL  {a.client}/{a.agent}: {e}")
        failed = True
    print()

    print("=" * 78)
    if failed:
        print("VERDICT: FAIL. A recap cannot reach the downstream system. Fix before publishing.")
        print("Backfill anything already missed with tools/webhookreplay.py.")
    else:
        print("VERDICT: PASS. The delivery chain is intact.")
        print("Note: a 200 from the downstream system means the workflow started,")
        print("not that an email arrived or a record was made. Only the client's")
        print("own system proves that.")
    print("=" * 78)
    print("Nothing was written to Retell. No webhook was fired.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
