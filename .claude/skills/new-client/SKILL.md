---
name: new-client
description: Creates a new client or project folder in retell-clients from templates/client, then runs intake to fill CLIENT.md. Use when starting work for a client or project with no folder yet.
---

# New client

## Step 1: name the folder

Lowercase, hyphens, the client's name. Use the project name too when one
client has more than one project, for example `acme-dental-intake`.

## Step 2: copy the template

```bash
K=$(cat .kit-path)
cp -r "$K/templates/client" "retell-clients/<name>"
```

This gives the folder its full shape: `CLIENT.md`, `intake.md`,
`sources/`, `agents/`, `tests/`, `integrations/`, `docs/`, `results/`.

## Step 3: run intake

Run the `intake` skill now. It asks the route and source-type questions
and writes `<client>/intake.md`.

## Step 4: fill CLIENT.md

Fill the header fields from the intake answers: who the client is, what
they do, the agent or agents planned, ids (once they exist), the approval
chain, and current status. Keep it at or under 80 lines. Facts only, no
narrative; narrative belongs in `docs/HANDOFF.md`.

## Step 5: confirm

List what was created and ask the client folder name back to the user,
so a typo is caught now, not later.
