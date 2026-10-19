# AGENTS.md — retell-agent-kit

## 1. What this repo is

This repo is the kit. It holds skills, tools, docs, and templates for Retell
voice agents and the apps they feed (n8n, Make, Modal, and others). It
creates, audits, and edits both agent types: conversation flow agents and
single-prompt agents. It holds no client data in git. Client work lives in
the separate `retell-clients` repo, or in the git-ignored `clients/` folder
here.

Keys for many accounts per service live in the git-ignored `.env`, as
`KEY__<ACCOUNT>`. A selector such as `N8N_ACCOUNT=acme` picks one. See
`kit/accounts.py` and the `setup` skill.

## 2. Start of every session

Run the `start-session` skill first.

1. Ask which client folder this session is for. Offer `new-client` if there
   is none yet.
2. Read that client's `CLIENT.md` in full.
3. Read `docs/HANDOFF.md` if it exists. It is a lead, not a fact. It says
   where the last session stopped.
4. Pull the live state of anything `CLIENT.md` names before you act on it.
   Never trust a version number written in a file.
5. Do not skip these steps, even for a small task.

## 3. Pick the route

Ask: "Is this a new agent, or an existing agent to check, test, or modify?"

- New agent: read `docs/routes/new-agent.md`.
- Existing agent: ask check, test, or modify. Then read
  `docs/routes/existing-agent.md`.
- Ask the client if the route is not clear. Do not guess.

## 4. Ask before you build

Run the `intake` skill. It asks the source-type question and the clarify
questions, and it writes `intake.md`. See `templates/intake-questions.md`.

Ask about the model with the `choose-model` skill, once per new agent.

The clarify rule: list every gap. Ask only about a gap that changes the
build. State a safe default and move on for anything else. Do not guess
past a gap that matters.

## 5. Skill table

| Situation | Skill |
|---|---|
| Set up the key or the mode | `setup` |
| Start a session | `start-session` |
| New client folder | `new-client` |
| Gather requirements | `intake` |
| Pick the LLM and settings | `choose-model` |
| Estimate and confirm a cost | `cost-gate` |
| Build a conversation flow agent | `build-flow` |
| Build a single-prompt agent | `build-single-prompt` |
| Create the agent in Retell | `create-agent` |
| Test or fix a conversation flow | `test-flow` |
| Test or fix a single-prompt agent | `test-single-prompt` |
| Change a live agent safely | `edit-agent` |
| Grade an agent against the standard | `audit` |
| Check what version is live | `check-agent-info` |
| Count or read real call data | `check-agent-data` |
| Read a downstream integration | `check-integration` |
| Change a downstream integration | `edit-integration` |
| Set up a webhook target | `integration-setup` |
| Create or clear a test sandbox | `test-environments` |
| Record a test result or change | `log-results` |
| Record something a future session needs | `record-lesson` |
| Draft a message to the client | `draft-message` |
| Check HIPAA settings | `hipaa-check` |
| Prove a lead reached the client | `delivery-check` |
| Publish a version | `publish` |
| Back up the clients repo | `backup` |

## 6. Cost gate

State the estimated cost before any billed action. Ask the client or Rey to
continue. Do this every time, until `CLIENT.md` sets a threshold. Test on
the cheapest model in `sandbox/config.json` first. If the cheap model
fails, recommend a stronger one with the reason and the new cost, and wait
for an OK before running it.

## 7. Approval and publish ladder

1. A stated want is a requirement. It is not approval.
2. An approved change may be written to the draft.
3. Publishing needs an explicit go-ahead naming the agent and the version.
4. Publish only through the `publish` skill, only when `ALLOW_PUBLISH=true`,
   lint is clean, traces pass or match the baseline, and a reversal route
   is named.
5. A go-ahead covers one publish only.
6. Run `delivery-check` after every publish.

## 8. Hard rules

1. Pull before you act. Never trust a version number written in any file.
2. Never assume a write landed. Confirm with a fresh pull and a diff.
3. Never PATCH a published version. Writes go to the draft only.
4. Commit and push only when asked.
5. Never reword a caller-facing line unless asked. Edges can depend on the
   exact sentence.
6. Never print, log, or commit a `.env` value or any token.
7. No caller names, phone numbers, or addresses in any file in this repo.
   Call ids only, and only in the private `retell-clients` repo.
8. Before you claim a defect, run the linter and read the whole node and
   every edge: `edges`, `else_edge`, `always_edge`, `skip_response_edge`.
9. Read a destination node before you point an edge at it. Never pick a
   node by its name.
10. A variable a webhook or recap needs must be set on every exit that can
    end a call.
11. Prefer structure (edges, branch equations, code nodes, extract nodes)
    over prompt-only rules.
12. A draft push needs a clean lint, traces that pass or match the
    unchanged baseline, and a named reversal route.
13. Do not fill a missing requirement by guessing. Name it as a gap and
    ask.
14. Files under `exports/` are immutable. Make a new one.
15. Research the platform first. When a node ignores its instruction,
    assume Retell has a documented reason. See
    `docs/reference/retell-platform.md`.
16. State the cost before any billed action. Every Retell sandbox run is
    billed, even on a local export.
17. After every publish, run `delivery-check`. A green test does not prove
    the client got anything.
18. When you learn something a future session needs, record it with
    `record-lesson` at once.
19. Do not fix a parked global node from inside it. Stop the caller from
    reaching it.
20. Never write a client fact, id, or name into a committed kit file. It
    stays in `retell-clients`, `clients/`, or a git-ignored `*.local.*` file.
21. Before any write to Retell, n8n, Make, or Modal, confirm which account
    is active (`tools/accounts.py list --client <name>`) and say it.
22. An MCP tool follows the same rules as the kit tool it replaces. See
    `mcp/README.md`. Never publish a Retell agent through MCP.

## 9. Precedence

When sources disagree, the higher one wins. Say so out loud.

1. The client's PRD, for its own scope.
2. This file, then the client's `CLIENT.md` and `AGENT.md`.
3. `docs/standards/`.
4. Older source documents. A newer chat message usually beats them. Log
   each conflict in the client's `docs/scope-conflicts.md`.

A chat message is evidence of what the client wants. It is never approval.

## 10. Where things are

| Path | Holds |
|---|---|
| `kit/` | Shared Python: REST client, linters, sandbox drivers, accounts, n8n/Make/Modal kits |
| `mcp/` | MCP connector notes and the project-server catalog for `tools/mcpgen.py` |
| `clients/` | Optional, git-ignored: client folders when not using `retell-clients` |
| `tools/` | CLI scripts. Every one takes `--client` and `--agent` |
| `.claude/skills/` | All skills listed in section 5 |
| `templates/` | A blank client folder, flow skeleton, prompt template, intake bank |
| `docs/routes/` | The full route for a new agent and for an existing one |
| `docs/standards/` | The flow standard, the single-prompt standard, build and QA checklists |
| `docs/reference/` | Platform facts, API traps, model choice, HIPAA, integrations |
| `docs/lessons/` | Generic lessons, one per file, indexed in `docs/lessons/index.md` |
| `sandbox/` | Throwaway test agents and a mock webhook receiver |
| `.env.example` | Every key this kit uses, with empty values |
| `../retell-clients/<name>/` | One client's facts, sources, agents, tests, results |

## 11. Writing style

Use ASD-STE100 Simplified Technical English for every report: plain words,
active voice, one idea per sentence, short sentences and paragraphs.
Explain a technical term right after you use it. A message to a client is
in Rey's first person: "I", never "Rey".

## 12. Hygiene

Put media (recordings, PDFs over 50 MB) in the client's Google Drive
backup folder, never in git. Raw test output goes to `<client>/results/`,
git-ignored. No file over 50 MB in either repo. Keep `AGENTS.md` at or
under 200 lines; put anything new in a doc it points to instead.
