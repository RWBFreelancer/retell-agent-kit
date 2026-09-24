---
name: delivery-check
description: Prove a lead can actually reach the client. Six read-only checks on webhook_url, webhook_events, post_call_analysis_data, the live published version, and real calls. The delivery setting lives on the agent, not the flow or the prompt, so no flow test and no prompt lint can see it. Run after every publish, and as the first step of any report that the client is not getting leads or calls or emails. Use when someone says leads stopped arriving, the client got no email, the recap is empty, or asks whether the agent is really working.
---

# Prove the lead reaches the client

Run `setup` first. This skill needs an API key. There is no offline
version, because the fault it looks for is only visible on the live agent.

`K` below means the retell-agent-kit repo root (found via `.kit-path` in retell-clients).

## Why this exists

On a real project an agent was published with `webhook_url` unset and
stayed that way for **three days**. Leads were collected perfectly and
forwarded nowhere. Four separate test tools were green the whole time,
because not one of them can see a setting that lives on the **agent**
rather than in the flow or the prompt.

A flow test cannot find this. A prompt lint cannot find this. Nothing in
the conversation does the sending.

One question: **if a real caller rang right now, would the client hear
about it?**

## Run it

```bash
python "$K/kit/agentkit.py" deliver --agent-id agent_xxx
python "$K/kit/agentkit.py" deliver --agent-id agent_xxx \
    --expect caller_name,callback_number,issue_summary
python "$K/kit/agentkit.py" deliver --agent-id agent_xxx --calls 20
```

Read-only. It **never fires the webhook**: sending a test event would
deliver a fake lead to a real client. Exit code 1 on any failure.

## The six checks. Each breaks on its own.

| # | Check | What a failure means |
|---|---|---|
| 1 | `webhook_url` is set on this version | Every recap goes nowhere. Silent. |
| 2 | `webhook_events` includes `call_analyzed` | The payload carries the raw call but none of the recap fields. |
| 3 | `post_call_analysis_data` is not empty | There is no recap to send. |
| 4 | Every expected recap field is present | A field was renamed or deleted. The receiving workflow reads a blank. |
| 5 | The **live published** version has a webhook | A webhook on the draft does not help real callers. This checks the version they actually reach. |
| 6 | Recent real calls came back with `call_analysis` populated | The end-to-end proof: Retell ran the analysis and had something to send. |

Check 5 is the one that catches the real-world case. A draft can be
perfect while the published version serving the phone number is not.

## When to run it

- **After EVERY publish**, before calling anything live.
- **After any dashboard edit**, by anyone.
- **As the FIRST step** of any "the client is not getting leads" report.
  Before reading the flow. Before reading a transcript. Before anything.
- Before telling a client the agent is working.

## Check every version, not just the current one

```bash
python "$K/kit/agentkit.py" versions --agent-id agent_xxx
```

Prints every version with `set` or `NONE` for the webhook, then warns on
the ones with none. Any call served by a `NONE` version forwarded nothing,
and the calls are still recoverable: Retell keeps the whole call including
`call_analysis`.

## Verified commands

Example commands, proven against a real workspace.

```bash
K=$(cat .kit-path)
python "$K/kit/agentkit.py" deliver --agent-id agent_xxx
python "$K/kit/agentkit.py" versions --agent-id agent_xxx
python "$K/kit/agentkit.py" show --agent-id agent_xxx
python "$K/kit/agentkit.py" calls --agent-id agent_xxx --limit 5 --summary
```

Real passing output:

```
delivery check: acme-dental - Intake Assistant version 29

  PASS  1. webhook_url is set on this version
  PASS  2. webhook_events includes call_analyzed
  PASS  3. post_call_analysis_data is not empty
        34 field(s)
  PASS  4. every expected recap field is present
  PASS  5. the LIVE published version (28) has a webhook_url
  PASS  6. recent calls came back with call_analysis populated
        10 of 10 recent call(s).

  0 failure(s)
  Retell's side is sound. That does NOT prove an email arrived.
```

Real `versions` output that independently found a three-version gap:

```
WARNING: no webhook_url on version(s): 26, 25, 24
Any call served by one of those forwarded nothing.
```

## Gotchas

- **Retell omits null fields.** A cleared `webhook_url` does not come back
  as `null`. The key is simply **absent**. In a diff of a saved settings
  file that reads as a deleted line, which looks like tidying rather than
  a fault. This is exactly how the three-day outage happened.

- **A 200 is not an email.** A 200 from the receiving end means the
  workflow started. Only the client's inbox proves an email arrived. Say
  this every time you report a pass.

- **Green flow tests prove nothing here.** The setting is not in the flow.

- **The draft is not the live version.** Check 5 exists for this reason
  alone.

- **Never fire the webhook to test it.** That sends a fake lead to a real
  client. If you must re-send genuine stored calls that a missing webhook
  never forwarded, that is a separate, deliberate replay job: sign the way
  Retell signs, refuse any host other than the one currently on the agent,
  and dry run first.

- **This check cannot see inside the receiving workflow.** A broken n8n
  node, a wrong email address, or a disabled workflow all look like a pass
  here.

## Troubleshooting

| Symptom | Cause |
|---|---|
| Check 1 passes, check 5 fails | The webhook is on the draft, not on the published version callers reach. Publish, or set it on the right version. |
| Check 6 fails but 1 to 5 pass | No recent calls, or the calls are too new for analysis. Raise `--calls`, or wait. |
| Check 4 fails after a rename | A recap field was renamed. The receiving workflow still reads the old name. Fix one side or the other, not both. |
| Everything passes, client still gets nothing | The fault is past Retell. Check the receiving workflow is enabled, the URL is the production one and not the test one, and the destination address is right. |
| `deliver` cannot find the agent | Wrong `--agent-id`. Run `retellkit.py agents` to list them. |
