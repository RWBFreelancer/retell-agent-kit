---
name: test-flow
description: Test and fix a Retell conversation flow agent. Lints structure offline across all four exit kinds, drives a throwaway copy over text with a node-by-node path showing which global node grabbed each turn, reads real call transcripts, and applies fixes as a safe draft push. Works with or without an API key. Use when a conversation flow agent misroutes, repeats a line, skips a question, fires a global node wrongly, dead-ends a caller, or when someone wants to audit, debug, trace, QA, or improve a node graph agent.
---

# Test and fix a conversation flow agent

Run `setup` first if the mode is not set.
`K` below means the retell-agent-kit repo root (found via `.kit-path` in retell-clients).

Use the repo tools: `tools/flowlint.py`, `tools/tracerun.py`,
`tools/askcheck.py`, and `tools/simtest.py`. Test on the cheapest model
in `sandbox/config.json` first.

## The fix ladder. In order.

1. **Read a real transcript.** What the caller heard.
2. **Lint.** Offline, free.
3. **Reproduce it in a sandbox** and read the node path.
4. **Change the routing**, not the prose, wherever you can.

## Step 1: read what the caller actually heard

```bash
python "$K/kit/agentkit.py" calls --agent-id agent_xxx --limit 5 --redact
python "$K/kit/agentkit.py" calls --agent-id agent_xxx --limit 10 --summary
```

**Privacy.** Names, numbers, addresses. Terminal only. Never into a repo.

## Step 2: lint. No API key needed.

```bash
python "$K/kit/flowkit.py" pull --flow-id conversation_flow_xxx --out flow.json
python "$K/kit/flowkit.py" lint flow.json
python "$K/kit/flowkit.py" lint flow.json --line "Is there anything else?"
```

No key? Point it at whatever export the client sent. It reads the API
shape, the dashboard shape (nested under `conversationFlow`), and tells you
plainly when a file is a fragment rather than a flow.

What it checks:

| Check | Catches |
|---|---|
| edges | A transition pointing at a node that does not exist |
| dead-end | A node with no exit of any of the four kinds |
| unreachable | A node nothing routes to, ignoring globals |
| no-fallback | Conditional edges with no `else_edge` or `always_edge` |
| variables | A variable read but never set or defaulted |
| double-say | With `--line`, every node saying one exact sentence |
| global-nodes | How many, and that they are meant to have no inbound edge |

## Step 3: reproduce it, and read the path

```bash
python "$K/kit/flowkit.py" chat --file flow.json \
    -m "hi im stuck on the freeway shoulder cars flying past" \
    -m "yes im safe behind the barrier" \
    -m "Jane Doe"
```

You get the transcript, the node path, and `[global]` on any turn a global
node grabbed. That one tag is the fastest way to see a global node firing
when it should not.

Seed variables with `--seed`. Save with `--out`, outside any repository.

Prompt-based edges are probabilistic. Run a route three times before
believing it.

## Step 4: fix the routing, not the prose

Prefer structure. It is deterministic; prose is not.

1. **Fix the edge condition.** An equation beats a sentence every time.
2. **Add the missing `else_edge`.** A conditional node with no fallback
   strands the caller when nothing matches.
3. **Repoint the edge.** Read the destination node first, in full. Never
   pick a node by its name: a node named for one path may set a variable
   that changes another. That exact mistake stamped ordinary callers as
   roadside on a real project and made them hear an emergency line.
4. **Split the node.** A node doing two jobs will do one of them badly.
5. **Spend a negative example on a global node.** To stop one firing, a
   negative fine-tune example works where more words do not.
6. **Only then** edit the prose.

Two rules that prevent the worst defects:

- **A variable the recap depends on must be set on every exit that can end
  the call.** Setting it on the happy path only means the recap reports
  nothing on exactly the calls that went wrong.
- **A go-back on a global node outranks a matching edge.** If a global
  node returns the caller where they came from, that beats an edge you
  added to send them somewhere else.

## Step 5: push

```bash
python "$K/kit/flowkit.py" push --file flow.json --flow-id conversation_flow_xxx
python "$K/kit/flowkit.py" push --file flow.json --flow-id conversation_flow_xxx --push
```

Dry run first. It lints, refuses on a FAIL, refuses a published version,
reads back the node count to confirm it landed, and never publishes.

Keep the pre-change `flow.json`. That snapshot is your only way back. Say
out loud which reversal route exists before asking for approval.

## Verified commands

Example commands, proven against a real workspace.

```bash
K=$(cat .kit-path)
RETELL_API_KEY= python "$K/kit/flowkit.py" lint agents/agent-a/exports/v51.json
python "$K/kit/flowkit.py" pull --flow-id conversation_flow_xxx --out flow.json
python "$K/kit/flowkit.py" chat --file flow.json -m "hi my truck wont start"
python "$K/kit/agentkit.py" calls --agent-id agent_xxx --limit 5 --redact
python "$K/kit/sp.py" cleanup --yes
```

Real output from a live run against a production 21-node flow, showing a
global node grabbing turn two:

```
CALLER: hi im stuck on the freeway shoulder cars flying past
  -> node Greetings [normal]
 AGENT: Thanks for holding. The technician couldn't answer right now...
CALLER: yes im safe behind the barrier
  -> node Roadside / Safety Gate [global]
 AGENT: I'm glad you're safe. We are not an emergency service...

path: Greetings -> Roadside / Safety Gate[global] -> Roadside Flag -> Service Intake

collected_dynamic_variables:
  emergency_line_said = 'true'
  roadside_gate_visited = 'true'
```

## Gotchas

- **A node has four exit kinds:** `edges`, `else_edge`, `always_edge`,
  `skip_response_edge`. Reading only `edges` reports live nodes as dead
  ends. That produced two false findings on a real project.

- **A node transition is its OWN message.** It arrives with
  `role: "node_transition"` carrying `new_node_name` and
  `transition_type`. Filter the reply list to agent messages and you throw
  the whole path away, silently, and get an empty trace.

- **The path you see is a subsequence, never the whole route.** Only
  conversation nodes report a transition. Branch and code nodes are
  instant and invisible. Never assert an exact node list.

- **A global node has no inbound edge on purpose.**

- **`collected_dynamic_variables` fills in only after the chat ends.**
  Send every turn, end, then read. Read early and it is empty.

- **An exact-sentence count is blind to a paraphrase.**

- **Test evidence expires when the flow is edited by hand.**

- **A green flow is not a delivered lead.** `webhook_url` lives on the
  agent. Run `delivery-check`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `flow has no nodes` on a good file | Dashboard export. The flow is nested under `conversationFlow`, camelCase. |
| `holds a JSON list` | A fragment such as `post_call_analysis_data`, not a flow. |
| Empty node path | Single-prompt agent, or you filtered out the `node_transition` messages. |
| A global node fires when it should not | Add a negative fine-tune example. More prose in the condition will not do it. |
| Caller reaches a node and gets stuck | Missing `else_edge`. The lint's `no-fallback` check lists them. |
| Push rejected with a 400 about `tool_id` | Union-type error. Check `else_edge` says exactly `"Else"`. |
| The sandbox ignores your edit | You used `--flow-id`; the chat agent silently got version 0. Use `--file`. |
