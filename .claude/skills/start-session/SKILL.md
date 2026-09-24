---
name: start-session
description: Runs at the start of any Retell agent work session. Asks which client folder to use or offers to create one, loads that client's CLIENT.md and docs/HANDOFF.md, and asks the route question. Use at the start of a session, or when no client folder has been picked yet.
---

# Start a session

Run this before any other retell skill, once per session.

## Step 1: find the kit

Read `.kit-path` at the root of `retell-clients`. If it is missing, ask
where `retell-agent-kit` lives and write the file.

## Step 2: pick the client

Use `AskUserQuestion`. List the folders under `retell-clients/` (skip
`.git`, `tools`, hidden files). Ask which one this session is for, with
an option for "new client".

- Existing folder chosen -> go to Step 3.
- New client -> run the `new-client` skill, then continue at Step 3.

## Step 3: load the client's state

- [ ] Read `<client>/CLIENT.md` in full.
- [ ] Read `<client>/docs/HANDOFF.md` if present. Treat it as a lead, not
  a fact: it says where the last session stopped, not what is true now.
- [ ] Pull the live state of anything `CLIENT.md` names before acting on
  it. Never trust a version number written in a file. See
  `check-agent-info`.

## Step 4: ask the route

"Is this a new agent, or an existing agent to check, test, or modify?"

- New -> `$K/docs/routes/new-agent.md`.
- Existing -> ask: check only, test, or modify? Then
  `$K/docs/routes/existing-agent.md`.

Ask only this. Do not re-ask anything `CLIENT.md` or `HANDOFF.md` already
answered.
