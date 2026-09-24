# Delivery protocol — proving a lead can actually reach the client

Phase 1 exists to collect caller details and send a recap a human reads. The
flow does the collecting. **Nothing in the flow does the sending.**

On 2026-08-24 a second example agent was published with `webhook_url` unset and stayed that
way until 2026-08-27. Every call was answered correctly, analysed correctly,
and forwarded nowhere. 22 calls, 3 real leads, no recap email. Every test in
this repository was green the whole time.

This protocol is what stops that happening twice.

## The one command

```bash
python tools/deliverycheck.py
```

Read-only. It never fires the webhook. It exits **1** if a recap cannot reach
n8n, so it can gate a publish.

Proven against the real fault: `python tools/deliverycheck.py --agent b
--version 26` reports `FAIL webhook_url on v26` and exits 1.

## When to run it

| When | Why |
|---|---|
| **After every publish, before saying anything is live** | Publishing is where the setting was lost. |
| After ANY edit in the Retell dashboard | The dashboard is outside this repo and outside every guard in it. |
| First step of any "the client is not getting leads" report | It separates "not collected" from "not delivered" in one run. |
| Weekly, while Phase 1 is the only delivery route | The fault is silent; only a scheduled look finds it. |

Add it to the Definition of Done for any change that gets published.

## What it checks, and why each can break on its own

| # | Check | What breaking it does |
|---|---|---|
| 1 | The phone number resolves to an agent version | Tells you which version is really live. The draft is not it. |
| 2 | **That live version has `webhook_url` set** | This is the one that failed. Calls are analysed and forwarded nowhere. |
| 3 | `webhook_events` contains `call_analyzed` | A webhook firing only on `call_started` delivers nothing useful. |
| 4 | `post_call_analysis_data` still holds the recap fields | An empty or thinned list makes every recap arrive with holes. |
| 5 | The flow still sets `missing_fields` and `uncertain_fields` | The recap email reads these from `collected_dynamic_variables`. a second example agent only; one example agent never had them. |
| 6 | Recent real calls carry `call_analysis` | End-to-end proof on live traffic. Checks 2 to 5 are the parts; this is the whole. |

## Check the LIVE version, never the draft

This is the part that is easy to get wrong, and it is why the outage lasted
three days.

- `get_agent(agent_id)` returns the **latest** version, which is usually the
  draft.
- The phone number points at a **specific published version**, and that is the
  only one answering calls.

During the outage `get_agent` returned a version WITH the webhook while the
phone number served v26 WITHOUT it. Anyone spot-checking the agent would have
seen a healthy setting and a broken service.

`deliverycheck.py` resolves the number first, then reads that exact version.
Any manual check must do the same:

```bash
python -c "import sys;sys.path.insert(0,'tools');import retell_client as rc;c=rc.RetellClient();print(c._request('GET','/v2/list-phone-numbers'))"
```

## What this protocol cannot tell you

- **It cannot see inside n8n.** A 200 means the workflow started, not that the
  email was sent or that it was readable. Only the client's inbox proves that.
- **It cannot prove the content is right.** It proves fields exist, not that
  their values are correct. `sales_or_spam` was `unknown` on two clear
  solicitations while every check here passed.
- **It is a snapshot.** It says the chain is intact now. It says nothing about
  five minutes from now, which is why it belongs after every publish.

## If it fails

1. Fix the setting in the Retell dashboard, on the version the phone number
   serves. If that version is published and therefore immutable, publish a new
   version with the setting and repoint the number.
2. Re-run `deliverycheck.py` until it passes.
3. Work out the window: `list_agent_versions` shows which versions lacked the
   setting, and `POST /v3/list-calls` shows which calls ran on them.
4. Backfill with `tools/webhookreplay.py`. Dry run first. Retell keeps every
   call, so a missed webhook is a delivery failure, never a data loss.
5. Run `python tools/agentpull.py --agent b` and read `git diff`, so the repo
   records the corrected state.

## Why `git diff` did not catch it, and what changed

`agentpull.py` mirrors the agent object precisely so `git diff` shows drift. It
built its rows with `if k in agent`, and Retell **omits null fields from the
response**. So a cleared `webhook_url` did not appear as `_not set_`. The row
vanished, and `git diff` showed a deleted line, which reads as tidying.

`agentpull.py` now carries a `REQUIRED` list rendered unconditionally, and
writes an explicit `null` into the JSON. A cleared webhook is now a CHANGED
value, which reads as a fault.

**The general rule.** Any drift mirror must tell "this is off" apart from "this
is not in the response". Only one of them is an outage.

Full history: [lessons-webhook-gap.md](lessons-webhook-gap.md), lessons 41-44.
