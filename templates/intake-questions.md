# Intake question bank

The `intake` skill draws from this file. Ask only what the sources do not
already answer. Use `AskUserQuestion`, at most 4 questions per call.

## Always ask first

1. "Is this a new agent, or an existing agent to check, test, or modify?"
2. "Where does the content come from?" (multi-select: PRD, prompt
   instructions, flowchart, docs/call scripts/FAQ, a copy of an existing
   agent, a chat or email thread, nothing written)

## Minimum facts before a new build

Ask only the ones the sources leave open.

- Business name and what it does.
- The agent's one job.
- Phone number setup: new number, port an existing one, or route an
  existing number to Retell.
- Hours and after-hours behavior.
- Required fields to collect on every call.
- Where each call's data goes (webhook target: n8n, Make, GHL, Zapier,
  HubSpot, or none yet).
- Who approves a change, and who publishes.
- Hard "never say" items: price, diagnosis, ETA, medical advice, legal
  advice, anything the client names.
- Transfer target, if any, and when a call should transfer.
- Languages the agent must handle.
- Any compliance need: HIPAA, recording consent law in the client's
  state, industry-specific rules.

## For an existing agent (check, test, or modify)

- What changed, or what is suspected to be wrong.
- Since when, if known.
- Any evidence already in hand: a call id, a transcript, a client
  message.
- Who is asking, and who needs to see the answer.

## Clarify rule

List every gap and conflict found in the sources. Ask about each one that
changes the build. State a safe default and move on for anything that
does not change the build. Stop asking once every build-changing gap is
closed. Record every answer, and every open item, in `<client>/intake.md`.
