# tools/

Every tool opens with a docstring giving its purpose, guards, and usage.
Read it before running the tool.

Every tool that touches a specific agent takes `--client <folder> --agent
<slug>`, and resolves the real Retell ids from
`<clients-repo>/<client>/agents/<slug>/AGENT.md`. Nothing here hard-codes
an id.

## Accounts and setup

| Tool | Use |
|---|---|
| `accounts.py` | `list` accounts per service and which is active, `use --client <name> retell=<acct> ...` to write a client's choice into its `.env.local`, `template <service> <acct>` for the key lines to paste. Never prints a value |
| `envcheck.py` | Which keys are set or missing for the active accounts. `--need KEY` exits 1 when missing |
| `mcpgen.py` | Write a git-ignored `.mcp.json` with one MCP server per named account (`retell=acme n8n=other`). Dry run unless `--write`. Catalog: `mcp/servers.json` |

## Retell: create

| Tool | Use |
|---|---|
| `agentcreate.py` | Create a new agent: the flow or LLM plus the agent object (voice, webhook, post-call fields), read both back, write the ids into `AGENT.md`. Dry run unless `--create`. Refuses a slug that already has an agent. `--list-voices` lists voices. Settings: `templates/agent-settings.example.json` |

## Retell: read

| Tool | Use |
|---|---|
| `flowshow.py` | Read one part of an export instead of the whole JSON: `list`, `show <node-id>` (whole node, every outgoing kind, incoming edges), `edges-to`, `grep`, `var <name>`, `global`. `--client --agent` takes the newest local export |
| `deliverycheck.py` | Live version per phone number, `webhook_url`, `webhook_events`, recap fields, real calls. Read-only, exits 1 on failure. Run first every session and after every publish |
| `flowpull.py` | Snapshot a flow into `exports/`. `--version N` for a specific one, `--suffix` to name it. Read-only |
| `agentpull.py` | Snapshot agent-level settings into `agent-settings.json` and `AGENT-SETTINGS.md`. Read-only |
| `flowdiff.py` | Compare two exports |
| `flowlint.py` | Static check of an export. `--line "<sentence>"` finds double-say paths between two different nodes |
| `flowaudit.py` | Grade a flow against `docs/standards/qa-checklist.md`. Mechanical rows graded, the rest printed as MANUAL |
| `callreview.py` | Real calls and what the caller heard. `--version N`. Prints PII; never paste output into a repo file |
| `askcheck.py` | Per question on a call: asked, skipped, or asked twice. Reads its question list and scenarios from `<client>/tests/ask-questions.json` |
| `flowdiagram.py` | Render a flow export as a PDF diagram for review |

## Retell: write (drafts only, never publish)

| Tool | Use |
|---|---|
| `flowapply.py` | Run one transform from `transforms/`. Dry run by default, `--push` writes the draft. Refuses a published version |
| `agenttiming.py` | Set `responsiveness` and/or `interruption_sensitivity` on the agent draft, from `--responsiveness`/`--interruption-sensitivity`. Prints direction |
| `agentsilence.py` | Set `reminder_max_count` and `end_call_after_silence_ms` on the agent draft, from `--reminder-count`/`--silence-ms`. Prints direction and the quiet time before hang-up |

Nothing in `tools/` edits `post_call_analysis_data`. That field's names and
shape are specific to each client's agent; use `agentkit.py update` (in
`kit/`) with the exact fields for that client, and keep the change
recorded in the client's `CHANGELOG.md`.

## Retell: test

| Tool | Use |
|---|---|
| `tracerun.py` | Run `<client>/tests/TRACES.md` against an export in a throwaway sandbox. Prints path, variables, and billed cost. Model comes from `sandbox/config.json`, cheapest first |
| `retell_chat.py` | Talk to a throwaway copy of a flow. Run `cleanup` after any crash |
| `simtest.py` | Retell Simulation Testing, cases in `<client>/tests/simtests.json`. Runs the flow's own live model; clear the cost with the client before using it |
| `_combo.py` | Apply several transforms in order to a local export, to A/B candidate fixes without touching Retell |

Every sandbox run is billed by Retell, even on a local export. Run
`cost-gate` first.

## Connected apps (in `kit/`)

Each reaches the account its selector picks (`N8N_ACCOUNT`, `MAKE_ACCOUNT`,
`MODAL_ACCOUNT`). Snapshots go to `<client>/integrations/<platform>/` with
`--client`, else to `results/<platform>/`, as new dated, numbered files.

| Tool | Use |
|---|---|
| `kit/n8nkit.py` | `ping`, `workflows`, `pull`, `show <file-or-id> list\|node\|code`, `executions`, `execution <id> --node`, `lint` (offline, a port of the n8n-projects linter), `diff`, `push --file` (dry run unless `--apply`; refuses stale files and active workflows without `--live-ok`) |
| `kit/makekit.py` | `ping`, `scenarios`, `pull`, `show`, `logs`, `hooks`, `diff`, `push --file` (same guards) |
| `kit/modalkit.py` | `ping`, `apps`, `logs`, `secrets` (names only), `deploy`/`serve` (dry run unless `--apply`). Wraps the `modal` CLI with the selected token |

## Integration webhooks

| Tool | Use |
|---|---|
| `webhookreplay.py` | Re-send stored calls to a client's downstream webhook, for calls that never got one. Dry run by default |
| `examples/n8n_apply_example.py` | A scrubbed pattern for a one-off n8n code-node change tool. Copy it per change; do not run it as-is |

## `.env` keys

Never print a value. See `.env.example` at the repo root for the full
list, and `kit/accounts.py` for the `KEY__<ACCOUNT>` convention.

## Transform contract

`transforms/<change>.py`, one file per change, named for the change. It
exposes `NAME`, `DESCRIPTION`, and `apply(flow) -> flow`. It never talks
to Retell and never writes a file; `flowapply.py` owns the GET, lint,
save, and PATCH. It edits structure only unless the client asked for a
wording change. Keep it and its inverse after it lands.
