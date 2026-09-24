---
name: setup
description: Start here for any Retell voice agent work. Asks whether you have a Retell API key, sets it up, and picks online or offline mode. Owns the shared kit that every other retell skill uses - the REST client, the prompt linter, the flow linter, the text sandbox drivers, and the agent settings and delivery tools. Use when someone says they want to build, create, test, edit, audit, lint, screenshot, or debug a Retell voice agent, a single prompt agent, a conversation flow agent, or a retell.json, and when they mention an API key, a retell export, or having only documents or a prompt.
---

# Retell setup: ask first, then work

Every other retell skill depends on this one. Run it first.

`K` below means the retell-agent-kit repo root. Find it by reading
`.kit-path` at the root of the retell-clients repo.

## Step 1: ask the two questions. Do not skip this.

Use `AskUserQuestion`. Ask about the key **before** reading any file.

**Question 1 - "Do you have a Retell API key?"**

| Option | What it means |
|---|---|
| Yes, I have a key | Full mode. Build, lint, sandbox-test, push drafts, read real calls. |
| No API key | Offline mode. Build, lint, and audit still work fully. |

**Question 2, only if they said no - "What do you have instead?"**

| Option | What still works |
|---|---|
| A `retell.json` or agent export | Everything except push, live chat, and call review. |
| Documents, a call script, or a written brief | The full build path. Output is a JSON file they import by hand in the Retell dashboard. |
| Nothing yet | Start from `$K/templates/`. Same output. |

Then write what they chose to `<client>/.retell-mode.json` so no later
skill asks again.

## Step 2: if they have a key, set it up

Real keys live only in the **retell-clients** repo, never in the kit.

- **Per client** - `<client>/.env.local` in retell-clients. Best when
  different clients have different keys.
- **Repo-wide** - `.env` at the retell-clients root. Best when most
  clients share one Retell account.
- **Global** - `%USERPROFILE%\.retell.env`. Best for one-off work outside
  any client folder.

Copy `$K/.env.example` for the shape. Fill only the keys this task needs.

```
RETELL_API_KEY=key_xxxxxxxxxxxx
RETELL_BASE_URL=https://api.retellai.com
ALLOW_PUBLISH=false
```

Never print a key. Never write one into a file the user will commit.
Check `.gitignore` covers `.env` and `.env.local` before writing either.

## Step 3: verify

Run this from the **client folder**, not from the kit.
Where you stand matters: the kit looks for `.env` in the current
directory and its parents.

```bash
python $K/kit/retellkit.py env
python $K/kit/retellkit.py ping
```

`env` needs no key and no network. It prints where credentials came
from, with the key masked. `ping` proves the key authenticates.

Then see what is in the workspace:

```bash
python $K/kit/retellkit.py agents
python $K/kit/retellkit.py llms
python $K/kit/retellkit.py flows
```

`agents` labels each one `single-prompt`, `multi-prompt`, or
`conversation-flow`, so you know which skill to use next.

## Step 4: send them to the right skill

| They want to | Skill |
|---|---|
| Start a session | `start-session` |
| Set up a new client folder | `new-client` |
| Build a single-prompt agent | `build-single-prompt` |
| Build a conversation flow agent | `build-flow` |
| Test or fix a single-prompt agent | `test-single-prompt` |
| Test or fix a conversation flow | `test-flow` |
| Change a live agent safely | `edit-agent` |
| Grade an agent against the standard | `audit` |
| Prove leads reach the client | `delivery-check` |

Not sure which agent type they need? Read
`$K/docs/reference/agent-type-choice.md` and decide before writing
anything.

## The kit

Five tools. Read the docstring at the top of each before you use it.

| File | Does | Needs a key? |
|---|---|---|
| `kit/retellkit.py` | REST client, credential finder, mode file | Only for network commands |
| `kit/promptlint.py` | 27 checks on a single-prompt agent | **No** |
| `kit/sp.py` | Single-prompt: new, pull, chat, push, cleanup | Yes, except `new` |
| `kit/flowkit.py` | Flow: lint, pull, chat, push, cleanup | **No** for `lint` |
| `kit/agentkit.py` | Agent settings, delivery proof, real calls | Yes |

Reference material:

| File | Read it when |
|---|---|
| `docs/reference/retell-api.md` | Before any API call. Eleven traps, all confirmed live. |
| `docs/reference/agent-type-choice.md` | Before choosing single prompt or flow. |
| `docs/reference/amplify-voice-prompt-engineer.md` | Before writing or auditing any prompt. |

Templates:

| File | Is |
|---|---|
| `templates/single-prompt.md` | A complete prompt. Lints 0 fail. Proven live. |
| `templates/flow-skeleton.json` | A 5-node flow. Lints 0 fail, 0 warn. Proven live. |
| `.env.example` | The credential file shape, every key. |

## Verified commands

```bash
# offline, key deliberately cleared
RETELL_API_KEY= python $K/kit/retellkit.py env
RETELL_API_KEY= python $K/kit/promptlint.py \
    $K/templates/single-prompt.md
RETELL_API_KEY= python $K/kit/flowkit.py lint \
    $K/templates/flow-skeleton.json

# online
python $K/kit/retellkit.py ping
python $K/kit/retellkit.py agents
python $K/kit/agentkit.py show --agent-id agent_xxx
```

## Gotchas

- **Where you stand matters.** The kit finds `.env` by walking up from
  the current directory to the nearest folder holding `.git` or `.env`.
  Run it from the client folder, or set a global key at
  `%USERPROFILE%\.retell.env`.

- **`/v2/list-agents` rows are slim.** No `version`, no `webhook_url`, no
  `response_engine`. Only `response_engine_type`. Reading
  `row["response_engine"]["conversation_flow_id"]` gets `None` silently.
  The `flows` command calls `get_agent` per row for exactly this reason.

- **A green lint is not a working agent.** `promptlint` and `flowkit lint`
  read structure. Neither can tell you what the agent says. Always follow
  a clean lint with a `chat` run.

- **A green everything is not a delivered lead.** `webhook_url` lives on
  the agent, not the flow or the prompt. Run `delivery-check` after every
  publish.

- **Sandbox runs cost money.** About 0.7 cents a message. `chat` prints
  the estimate and refuses more than five turns without `--yes`.

- **Always clean up.** After any crash run
  `python $K/kit/sp.py cleanup --yes`. Sandbox objects are recorded in
  `.retell-sandbox.json` and are also swept by name, so nothing is lost.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `RETELL_API_KEY is empty` while a `.env` clearly exists | You are not standing in the client folder. `cd` there, or create `%USERPROFILE%\.retell.env`. |
| `flow has no nodes` on a good export | It is a dashboard export. The flow is nested under `conversationFlow`, camelCase. `flowkit.load` handles it; other tools may not. |
| `holds a JSON list, not a conversation flow` | You pointed at a fragment, such as an exported `post_call_analysis_data`. |
| HTTP 400 listing `tool_id`, `code`, `transfer_destination` | A union-type error. Read the FIRST clause. Usually an `else_edge` prompt that is not exactly `"Else"`. |
| The sandbox answers plausibly but ignores your change | You pointed a chat agent at a live id and got version 0. Use `--file`, or let the kit copy it. |
| `chat` shows no node path | You are on a single-prompt agent. Only flows report node transitions. |
