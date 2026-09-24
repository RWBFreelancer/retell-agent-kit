---
name: edit-agent
description: Safely change a live Retell agent of either type. The nine-step loop - snapshot, check for drift, design the smallest change, dry run, lint, test, name the reversal route, get approval, push the draft, then confirm what actually landed with a fresh pull. Never publishes and never touches a published version. Also covers agent-level settings such as voice, interruption sensitivity, boosted keywords, and post_call_analysis_data. Use when changing, editing, updating, patching, or fixing an agent that is already live, or when someone asks whether a push landed.
---

# Change a live Retell agent, safely

Run `setup` first if the mode is not set.
`K` below means the retell-agent-kit repo root (found via `.kit-path` in retell-clients).

This skill exists because of one rule: **never assume a write landed.**

## The three levels of approval. Do not mix them up.

1. The client states a want. That is a requirement. **It is not approval.**
2. The client approves a specific change. You may write it to the
   **draft**.
3. The client gives an explicit go-ahead to publish. **A human publishes.**

Nothing in this kit publishes. `ALLOW_PUBLISH` defaults to false and no
skill flips it.

## The nine steps

### 1. Snapshot

```bash
# flow agent
python "$K/kit/flowkit.py" pull --flow-id conversation_flow_xxx --out before.json
# single prompt agent
python "$K/kit/sp.py" pull --llm-id llm_xxx --out before.json
# always, both types
python "$K/kit/agentkit.py" save --agent-id agent_xxx --out agent-before.json
```

The third one is not optional. Voice, interruption sensitivity, boosted
keywords, `webhook_url`, and `post_call_analysis_data` all live on the
agent, not in the flow or the prompt.

### 2. Check for drift

Diff the snapshot against the last known copy in the repo.

```bash
git diff -- agent-before.json
```

People edit in the dashboard between sessions. Understand the drift
**before** designing anything, or your change will quietly revert theirs.

**Retell omits null fields.** A cleared `webhook_url` shows in a diff as a
**deleted line**, not as `null`. That reads like tidying. It is not.

### 3. Design the smallest change

Confirm the requested behaviour. Identify every path affected. Trace the
current behaviour before changing it. Then design the smallest structural
change that fixes it without touching anything else. Everything you did
not name must end byte-identical.

Touch only the intended node, edge, variable, or setting. Prove nothing
else moved, using the diff in step 9.

- [ ] Read the **whole** node and **every** edge before you touch it:
  `edges`, `else_edge`, `always_edge`, `skip_response_edge`. Never a
  truncated view.
- [ ] Read a destination node before you point an edge at it. Never pick
  a node by its name alone.
- [ ] **Count the defect on real calls first.** See `check-agent-data`.
  If real calls do not show it, stop. A sandbox failure alone is not
  proof of a defect.
- [ ] Prefer structure (edges, branch equations, code nodes, extract
  nodes) over new prompt text.
- [ ] Node instructions: plain text, `# HEADER` lines, dashes for lists.
  **Never start a line with a number or a numbered label** such as
  `Step 2`, `(1)`, or `PRIORITY 1`. Retell can read them as transition
  options.

**Do not reword a spoken caller-facing line** unless the request explicitly
asks for wording. Edge conditions can depend on exact sentences, so a
silent wording change breaks routing.

### 4. Make the change in a local file

Edit `before.json` into `after.json`. Never edit in place. The untouched
`before.json` is your reversal route.

### 5. Lint

```bash
python "$K/kit/flowkit.py" lint after.json
python "$K/kit/promptlint.py" after.json
```

Clean, or every exception explained out loud.

### 6. Test what it SAYS

```bash
python "$K/kit/flowkit.py" chat --file after.json -m "..." -m "..."
python "$K/kit/sp.py" chat --file after.json -m "..." -m "..."
```

Use `--file`, never `--flow-id` or `--llm-id`. A chat agent pointed at a
live id silently gets version 0, so you would be testing the oldest
version instead of your change.

Lint proves the wiring. A chat run proves what it says. **Neither alone is
evidence.** If a path cannot be run over text - anything hinging on silence
- say which one and why, and walk it on paper.

### 7. Name the reversal route, then get approval

Say out loud, before asking:

- what changes, in one sentence
- the lint result
- the test result, with how many runs passed
- **the reversal route**: `before.json` exists, here is its path

A change that cannot be undone from material already on disk must not be
pushed.

### 8. Push the draft

```bash
python "$K/kit/flowkit.py" push --file after.json --flow-id conversation_flow_xxx
python "$K/kit/flowkit.py" push --file after.json --flow-id conversation_flow_xxx --push
```

Dry run first, always. Both drivers refuse a published version, because
published versions are immutable and carry live calls. If the latest is
published, create a fresh draft agent version first:

```bash
python -c "
import sys; sys.path.insert(0, r'$K\kit')
from retellkit import RetellClient
print(RetellClient().create_agent_version('agent_xxx', base_version=51))
"
```

### 9. Confirm what landed. This step is the whole point.

```bash
python "$K/kit/flowkit.py" pull --flow-id conversation_flow_xxx --out after-push.json
diff before.json after-push.json
```

The server diff must match your intent, and nothing else. **A push is not
verified until this diff is read.** Never say an agent changed until a
fresh export proves it.

Then run `delivery-check`.

## Agent-level settings

These are not in the flow or the prompt, and no flow test can see them.

```bash
python "$K/kit/agentkit.py" show --agent-id agent_xxx
python "$K/kit/agentkit.py" versions --agent-id agent_xxx
```

`show` groups them the way you reason about them: delivery, voice, turn
taking, transcription, limits, and `post_call_analysis_data`.

`versions` prints every version with `set` or `NONE` for the webhook. A
`NONE` on a published version means every call it served forwarded nothing.

To change one, `RetellClient.update_agent(agent_id, fields)` takes a
partial dict and refuses read-only or wiring fields. Snapshot with `save`
first, and diff after.

`interruption_sensitivity` is worth knowing: it exists **per node** on a
conversation flow, not only on the agent. It appears in no export until you
set it, so reading the JSON will never find it.

## Testing cheaply

Cheapest first. Stop at the first step that answers the question. See
`sandbox/config.json` for the model order, and run `cost-gate` before any
billed step.

1. **Free.** Lint, `flowkit.py lint --line "<sentence>"` for double-say
   paths, real-call counts.
2. **A few cents.** `tracerun.py`, one rep, on the cheapest model.
3. **More cents.** More reps, only when a result is borderline, and only
   with the client's OK for the added cost.

Run every changed-path trace on the unchanged baseline too. A red only
counts if the baseline is green. A trace that also fails on the unchanged
export proves nothing about your change.

## Example commands

```bash
K=$(cat .kit-path)
python "$K/kit/agentkit.py" save --agent-id agent_xxx --out agent-before.json
python "$K/kit/agentkit.py" show --agent-id agent_xxxxxxxxxxxxxxxxxxxxxxxxxx
python "$K/kit/agentkit.py" versions --agent-id agent_yyyyyyyyyyyyyyyyyyyyyyyyyy
python "$K/kit/flowkit.py" pull --flow-id conversation_flow_xxx --out before.json
python "$K/kit/flowkit.py" push --file after.json --flow-id conversation_flow_xxx
```

Real `versions` output that found a three-version delivery gap:

```
  ver  state      webhook  engine
   29  draft      set      conversation-flow v29
   28  PUBLISHED  set      conversation-flow v28
   26  PUBLISHED  NONE     conversation-flow v26

WARNING: no webhook_url on version(s): 26, 25, 24
Any call served by one of those forwarded nothing.
```

## Gotchas

- **Never PATCH the version serving traffic.** Published versions are
  immutable and carry live calls. Both drivers refuse; do not work around
  the guard.

- **PATCH takes the WHOLE object.** `update-conversation-flow` and
  `update-retell-llm` are not field patches. GET, mutate, PATCH back. Strip
  `version`, `is_published`, the id, and
  `last_modification_timestamp` first, or the API rejects it.

- **`update-agent` is different.** It takes a partial dict, because the
  agent carries voice and telephony settings that must not be rewritten by
  accident. Pass only the keys you are changing.

- **Retell omits null fields.** A cleared setting is an absent key, so it
  reads as a deleted line in a diff.

- **`/v2/list-agents` rows are slim.** No version, no webhook, no
  `response_engine`. Use `get_agent`.

- **Never chain unverified edits.** Keep each change small enough to
  verify between pushes.

- **Test evidence expires the moment someone edits by hand.**

## Troubleshooting

| Symptom | Fix |
|---|---|
| `REFUSING: version N is PUBLISHED` | Create a draft agent version from it, then target that. |
| The diff after a push shows more than you changed | Someone edited in the dashboard between your snapshot and your push. Re-snapshot and redo step 2. |
| The push reports success but the read-back does not match | Do not describe it as landed. The drivers return exit 1 for this. Investigate before touching anything else. |
| A setting is missing from the export entirely | It may be a per-node field such as `interruption_sensitivity`, which appears only once set. Check the API reference, not the export. |
