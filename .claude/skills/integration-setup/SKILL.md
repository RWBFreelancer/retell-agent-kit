---
name: integration-setup
description: Wires an agent's post-call webhook to n8n, Make, GoHighLevel, Zapier, or HubSpot, and proves one test payload arrives. Use when connecting a new agent to its downstream system, or when a webhook target changes.
---

# Integration setup

## Step 1: confirm the target

Ask which platform, and get its base URL, workflow or scenario id, and
key from `<client>/.env.local` or the repo `.env`. See `.env.example`
for every key name.

## Step 2: set the webhook on the agent

Webhook URL and events live on the **agent**, not the flow or the
prompt. Use `agentkit.py` to set `webhook_url` and `webhook_events`
(must include `call_analyzed` at minimum).

```bash
K=$(cat .kit-path)
python "$K/kit/agentkit.py" show --client <name> --agent <slug>
```

Confirm the current value before changing it. A cleared `webhook_url`
shows as a deleted line in a diff, not as `null`.

## Step 3: prove one payload arrives

Use `sandbox/mock-webhook/` for a dry run with no real downstream
system, or fire one real test call and read the platform's execution log
for it. See `check-integration`.

## Step 4: field mapping

Write the payload's field mapping into
`<client>/integrations/<platform>-mapping.md`: each Retell field, the
downstream field it feeds, and what happens on missing or `unknown`.

## Step 5: run the delivery check

`delivery-check` proves the whole chain, not just this one hop. Run it
after wiring, and again after every publish.
