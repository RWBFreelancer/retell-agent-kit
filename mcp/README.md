# mcp/

How assistants in this kit reach Retell and the connected apps through MCP
(Model Context Protocol) servers, and how to reach more than one account of
the same app.

Checked on 2026-10-19. Account-specific notes (which instance a connector
reaches) go in `mcp/accounts.local.md`, which is git-ignored.

## Two kinds of MCP server

| Kind | Where it is set up | Accounts | Tool names |
|---|---|---|---|
| claude.ai connector | claude.ai > Settings > Connectors. Present in every session on the account | **One** per connector | `mcp__claude_ai_<App>__<tool>` |
| Project server | `.mcp.json` at the kit root, written by `tools/mcpgen.py` from `.env` | One per entry, as many as you like | `mcp__<service>-<account>__<tool>` |

Use the connector for the account it is tied to. Generate a project server
for every other account. Never assume a connector reaches the client you are
working on: read `mcp/accounts.local.md`, or ask the connector who it is
(Make `organizations_list`, n8n `search_projects`).

## Connectors on this claude.ai account

| Connector | Use in this kit | Writes live state? |
|---|---|---|
| n8n | Read workflows and executions, validate, build with the Workflow SDK | Yes: `update_workflow`, `publish_workflow`, `execute_workflow`, `archive_workflow` |
| Make | Scenarios, executions, hooks, data stores, blueprints | Yes: `scenarios_update`, `scenarios_run`, `scenarios_activate`, `hooks_*`, `data-store-records_*` |
| Google Sheets, Drive | Lead sheets, recap archives, call recordings a workflow stores | Yes |
| Gmail | Read the recap or alert email a workflow sent. Proves delivery | `send_message`, `forward`, `reply` send real mail |
| Google Calendar | Booking checks for scheduling agents | Yes |
| Notion | Client docs and specs, when the client keeps them there | Yes |
| Granola | Meeting transcripts as intake sources | No |
| Claude Docs | Shareable docs for a client | Yes |
| Cloudflare, Higgsfield | Not authorized yet. Authorize in claude.ai connector settings | - |

Plugin servers (asana, atlassian, figma, intercom, linear, slack, datadog,
github, pagerduty, Savant) also need authorization before use. None of them
are part of the Retell build path.

There is no claude.ai connector for Retell or Modal. Use the project
servers below, or the kit tools.

## Project servers: `servers.json` and `tools/mcpgen.py`

`servers.json` is the catalog. It holds URL shapes and `{KEY}` placeholders,
never a value.

| Service | Server | Needs in `.env` |
|---|---|---|
| retell | `https://mcp.retellai.com`, HTTP, `Authorization: Bearer <key>` | `RETELL_API_KEY__<ACCT>` |
| n8n | the instance's `/mcp-server/http`, `Authorization: Bearer <token>` | `N8N_MCP_URL__<ACCT>`, `N8N_MCP_TOKEN__<ACCT>` |
| make | `https://<zone>/mcp/u/<token>/stateless` | `MAKE_ZONE__<ACCT>`, `MAKE_MCP_TOKEN__<ACCT>` |

```bash
python tools/mcpgen.py --list
python tools/mcpgen.py retell=acme n8n=acme n8n=other          # dry run: names and hosts only
python tools/mcpgen.py retell=acme n8n=acme n8n=other --write  # writes .mcp.json (git-ignored)
```

Then restart Claude Code in the kit folder, approve the project servers,
and check them with `/mcp`.

## Rules for every MCP write

The kit's rules apply to MCP tools exactly as they apply to the kit's own
scripts. An MCP tool is not a way around a guard.

1. Read and validate tools are fine to use freely.
2. Any tool that changes live state (update, publish, run, activate,
   delete, send) needs the same approval as the matching kit command. Ask
   before calling it.
3. Retell's MCP has one generic tool, `invoke_api_endpoint`, that can reach
   every endpoint the key can, publish and delete included. Never
   always-allow it. Approve each call, and prefer the kit tools, which carry
   the dry-run and read-back guards.
4. Never publish a Retell agent through MCP. Publishing goes through the
   `publish` skill only.
5. After an MCP write, confirm it with a fresh read, as with any write.
6. Tokens in `.mcp.json` are secrets. The file is git-ignored; never copy it
   into a committed file or a chat.
