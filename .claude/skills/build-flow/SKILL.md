---
name: build-flow
description: Build a Retell conversation flow voice agent from a brief, documents, a call script, or from scratch. Designs nodes and edges, writes traces before prompts, lints the structure offline, drives a throwaway copy over text with a node-by-node path, then writes a draft or hands over a flow JSON to import by hand. Works with or without an API key. Use for creating a new conversation flow agent, a node graph voice agent, an agent-led intake or booking or screening agent, or converting a single prompt agent into a flow.
---

# Build a Retell conversation flow agent

Run `setup` first if the mode is not set.

`K` below means the retell-agent-kit repo root (found via `.kit-path` in retell-clients).

**Start with the intake.** Run the `intake` skill first, then the model
question from `choose-model`, then the cost gate before any sandbox run.

## Step 0: is a flow right?

Read `K/docs/reference/agent-type-choice.md`. A flow is right when any of these
is true, and a single prompt is cheaper when none is:

1. A **required field**. The call is worthless without it.
2. A **line that must be said exactly once**, for legal or safety reasons.
3. A **branch that must be exact**, not a judgement call.
4. More than three or four conditional paths, or five or more tools.

## Step 1: gather, then design in prose

Read every input first: the brief, the documents, the call script, existing
transcripts. Do not start from the JSON.

Then write, in plain prose and before any JSON:

- **The node list.** One line each: what it says, what it collects, when it
  leaves.
- **The edges.** Source, destination, and the exact condition.
- **The variable registry.** Every variable, who writes it, who reads it.
- **The global nodes.** What condition fires each one, and what it defers
  to.

Two rules that prevent the worst defects:

- **Read a destination node before you point an edge at it.** Never pick a
  node by its name. A node named for one path may set a variable that
  changes another. This has caused a real caller-facing defect.
- **A variable the recap depends on must be set on every exit that can end
  the call.** Setting it on the happy path only means the recap reports
  nothing on exactly the calls that went wrong.

Do not fill a missing requirement by inventing one. Name the gap and ask.

## Step 2: write the traces BEFORE the prompts

This is the step that gets skipped and it is the one that pays.

For each path, write:

```
### T-1  short name
Setup:    what the caller does
Path:     Node -> Node -> Node, naming each edge
Expect:   what is said, once, and in what order
Vars:     variable values at the end of the call
Fails if: the specific signature of failure
```

Writing these first forces the design to be testable. Writing them after
makes them describe whatever you happened to build.

## Step 3: build from the skeleton

Start from `K/templates/flow-skeleton.json`. Five nodes, lints 0 fail 0
warn, and proven to run live. It shows the exact shape of every piece:
`edges`, `else_edge`, `skip_response_edge`, an `end` node, node variables,
`global_prompt`, and `default_dynamic_variables`.

**Two magic strings, undocumented, that will reject your flow:**

```json
"else_edge":          { "transition_condition": { "type": "prompt", "prompt": "Else" } }
"skip_response_edge": { "transition_condition": { "type": "prompt", "prompt": "Skip response" } }
```

Exactly `"Else"`. Exactly `"Skip response"`. A sensible sentence gets a
400.

Node instruction style: plain text with `# HEADER` lines. No markdown bold.
No `*` bullets. Number inline as `(1)`, `(2)`, `(3)`.

## Step 4: lint. No API key needed.

```bash
python "$K/kit/flowkit.py" lint my-flow.json
python "$K/kit/flowkit.py" lint my-flow.json --line "Is there anything else?"
```

It checks all **four** exit kinds - `edges`, `else_edge`, `always_edge`,
`skip_response_edge` - so a live node is never called a dead end. It knows
a global node has no inbound edge on purpose. `--line` finds every node
saying one sentence, which is how you catch a double-say before a caller
does.

Fix every FAIL. Read every WARN.

## Step 5: walk the traces against a live throwaway

```bash
python "$K/kit/flowkit.py" chat --file my-flow.json \
    -m "hi my truck won't start" \
    -m "it's Jane Doe" \
    -m "five five five one two three four five six seven"
```

You get the transcript **and** the node path, with `[global]` marking any
turn a global node grabbed.

Walk each trace. Record pass or fail and the exact path taken. Re-run the
ones that depend on a prompt-based edge: those are a weighted coin, not a
switch. Nine of ten is a defect, not a pass.

Anything hinging on the caller going silent cannot be run here. Walk it on
paper and say so.

## Step 6: hand it over

**No API key.** Give them the flow JSON and say to import it in the Retell
dashboard.

**With an API key.** Dry run, then push, then confirm:

```bash
python "$K/kit/flowkit.py" push --file my-flow.json --flow-id conversation_flow_xxx
python "$K/kit/flowkit.py" push --file my-flow.json --flow-id conversation_flow_xxx --push
```

It refuses a published version, reads back the result, and never
publishes. Then run `delivery-check`.

## Step 7: write the changelog

Log the build with `log-results`, even for a first build. Name every
source document used, every open gap and its answer, and the traces run.

## Verified commands

Example commands, proven against a real workspace.

```bash
K=$(cat .kit-path)
RETELL_API_KEY= python "$K/kit/flowkit.py" lint "$K/templates/flow-skeleton.json"
python "$K/kit/flowkit.py" chat --file "$K/templates/flow-skeleton.json" \
    -m "hi my van has a flat" -m "Jane Doe"
python "$K/kit/flowkit.py" pull --flow-id conversation_flow_xxx --out flow.json
python "$K/kit/sp.py" cleanup --yes
```

Real output from the live run of the skeleton:

```
CALLER: hi my van has a flat
  -> node Greeting [normal]
 AGENT: Hi, thanks for calling Example Company, this is Kate. How can I help?
CALLER: Jane Doe
  -> node Intake [normal]
 AGENT: Thanks, Jane, spelled J A N E D O E. Could I get the best number...

path: Greeting -> Intake -> Intake
```

## Gotchas

- **The two magic strings.** `"Else"` and `"Skip response"`, exactly. The
  400 you get instead is a **union-type error** that lists every node type
  your object failed to match, so the real cause is buried in a wall
  mentioning `tool_id`, `code`, and `transfer_destination`. Read the FIRST
  clause of the error, not the list.

- **A node has four exit kinds.** Reading only `edges` reports live nodes
  as dead ends. That mistake produced two false findings on a real project.

- **A global node has no inbound edge on purpose.** It is reached by its
  own condition from anywhere. A mature flow has several.

- **The dashboard export nests the flow under `conversationFlow`.**
  CamelCase, in an API that is snake_case everywhere else. A loader looking
  for `conversation_flow` reports "flow has no nodes" on a good file.

- **The path you see is a subsequence, not the whole route.** Only
  conversation nodes report a transition. Branch and code nodes are
  instant and invisible. Never assert an exact node list.

- **The skeleton stacked two questions on its third turn** in the live run
  above, despite the one-question rule in the global prompt. Prompt-level
  rules are probabilistic. If a rule must hold, make it structural: a
  dedicated node, not a sentence.

- **Nineteen correct fixes can still make things worse.** Every fix adds a
  node, and past roughly forty nodes the machinery starts producing its
  own defect class. Prefer replacing state with shape.

## Troubleshooting

| Symptom | Fix |
|---|---|
| HTTP 400 mentioning `tool_id` and `code` | Union-type error. Check `else_edge` says exactly `"Else"`. |
| `flow has no nodes` | Dashboard export. The flow is under `conversationFlow`. |
| `holds a JSON list` | You pointed at a fragment, not a flow. |
| Lint says a node is unreachable but it is global | Older kit copy. `global_node_setting.condition` is the marker; the current lint skips those. |
| The path is empty in a chat run | Single-prompt agent. Only flows report transitions. |
| The sandbox ignores your edit | You used `--flow-id` on a live flow and got version 0. Use `--file`. |
