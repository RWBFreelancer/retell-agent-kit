---
name: check-agent-data
description: Checklist for reading and counting real Retell call data correctly - post-call analysis fields, analysis schema changes across agent versions, caller ID versus the number the caller stated, disconnection reason versus node state, whether the caller spoke, and latency. Use before quoting any count, rate, or field value from real calls, and before giving the client a number.
---

# Check agent data

Real calls are the best evidence you have, and the easiest to misread.
Every rule below cost a wrong number once, on a real client.

## Before counting anything

- [ ] **Pin the schema window.** Analysis field descriptions change between versions, and the description is what tells the model how to fill the field. A count across versions mixes different rules. For each field you count, find the version where its description last changed, and count only from that version up.
- [ ] **Pin the agent.** Two agents for the same client are separate populations. Never add them together without saying so.
- [ ] **Give the sample size and window with every number.** "1 of 56 calls, v35 and up", not "1 call".
- [ ] **Say it out loud when a sample is small.** Under about 50 calls, do not build a conclusion on it.

## Fields that look alike and are not

| Field | What it really is |
|---|---|
| `call.from_number` | Caller ID Retell received. Can be missing on some calls |
| `preferred_callback_number` or similar collected field | The number the caller read out. Can exist when caller ID does not |
| `call.to_number` | Always the Retell number. The line the customer actually dialled may live in a SIP diversion header |
| A yes/no collected field, e.g. `service_request` | Often only true or false exist. False can mean "asked, said no" or "never asked". Check a `missing_required_fields`-style field for the field name before reading a false as a no |
| `incomplete_intake` or similar | Usually driven by blocking missing fields, not a silence marker |

When a phone number matters, report both numbers.

## Who ended the call

- [ ] Read `disconnection_reason` together with the collected dynamic variables that show the last node reached, and any say-once marker the flow sets.
- `user_hangup` says who hung up, never whether the agent had finished. `agent_hangup` does not prove the agent finished either.

## Did the caller speak

- [ ] Count a caller as speaking only if `transcript_object` holds a `role: user` turn with non-empty content. A transcript can exist with only the agent in it.

## Tools

| Need | Use |
|---|---|
| Read calls and what the caller heard | `python $K/kit/agentkit.py calls --client <name> --agent <slug> --summary`. Prints PII. Never paste it into a repo file |
| Per question: asked, skipped, or twice | `python $K/tools/askcheck.py --client <name> --agent <slug>` |
| Latency by component | `latency.asr`, `.llm`, `.tts`, `.e2e`, each with `p50` |
| A custom count | A scratch script in the session scratchpad, reading from the same call fetch the tools use. Print call ids and counts only |

## Traps

- Count on real calls before trusting a sandbox trace about routing. It is free, and it has overturned "obviously broken" more than once.
- **Count placeholder words as empty.** An agent told to write `unknown` for a missing name, or `None` for a missing note, is not giving a real answer. A count that treats only a blank value as empty calls those real answers. Bucket every value as blank, a placeholder word, or a real value.
- A number from the client's own team may come from a few alert emails. A number from your pull comes from the whole call list. Say which.
- Log every count you will quote. See `log-results`.
