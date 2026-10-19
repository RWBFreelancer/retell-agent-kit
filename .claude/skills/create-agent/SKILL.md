---
name: create-agent
description: Creates a brand-new Retell agent in the chosen Retell account - the conversation flow or single-prompt LLM plus the agent object with voice, webhook, and post-call fields - with tools/agentcreate.py, then records the ids in AGENT.md. Use after build-flow or build-single-prompt has a linted engine file, when the agent does not exist in Retell yet.
---

# Create agent

This is step 9 of `docs/routes/new-agent.md` for an agent that does not
exist yet. For an agent that exists, use `edit-agent`.

## Step 1: confirm the account

```bash
python tools/accounts.py list --client <name>
```

The Retell account shown as active is where the agent will be created. If
it is wrong or `NONE`, fix it first:

```bash
python tools/accounts.py use --client <name> retell=<account>
```

Say the account name back to the user before step 4.

## Step 2: the settings file

Copy `templates/agent-settings.example.json` to
`<client>/agents/<slug>/agent-settings.json`. Fill it from `intake.md`:

- `agent_name`: `<Client> - <purpose>`.
- `voice_id`: pick with `python tools/agentcreate.py --list-voices --provider elevenlabs`.
  Ask the user if the intake does not name a voice. Do not guess.
- `webhook_url`: the receiver from `integration-setup` (n8n, Make, Modal).
  If it does not exist yet, leave it `""`, accept the warning, and add it
  with `integration-setup` before any publish.
- `post_call_analysis_data`: every field the downstream system reads, named
  exactly as that system reads it. Each one must be set on every exit that
  can end a call (hard rule 10).

## Step 3: dry run

```bash
python tools/agentcreate.py --client <name> --agent <slug> \
    --flow <client>/agents/<slug>/build/flow.json \
    --settings <client>/agents/<slug>/agent-settings.json
```

Use `--llm llm.json` instead of `--flow` for a single-prompt agent. Read the
lint block and the PLAN. Fix every FAIL.

## Step 4: create

Creating is free. Calls and sandbox chats on the new agent are billed. Get
an OK, then add `--create`. The tool:

- creates the engine, then the agent, then reads both back;
- writes `agent_id`, `flow_id` or `llm_id`, `type`, and `retell_account`
  into `AGENT.md`;
- saves the first flow export to `exports/`;
- deletes the fresh engine if the agent create fails.

## Step 5: after

1. `python tools/agentpull.py --client <name> --agent <slug>` to snapshot the
   agent settings.
2. Add the row to `CLIENT.md` > Agents.
3. Test with `test-flow` or `test-single-prompt`, after `cost-gate`.
4. Wire delivery with `integration-setup` if `webhook_url` is empty.
5. Publishing and binding a phone number stay with Rey: `publish` skill,
   then the Retell dashboard, then `delivery-check`.
6. `log-results`: a changelog entry for the first build.
