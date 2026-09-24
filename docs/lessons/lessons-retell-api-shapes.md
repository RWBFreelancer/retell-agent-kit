# Lessons: five Retell API shapes that reject or mislead

Date: 2026-08-29. Found while building the global `retell-*` skills at
`C:\Users\chats\.claude\skills\`. Every item below was confirmed by a live
call against this workspace, not read in a document.

None of these is in the Retell docs. Each one costs an hour if you meet it
without warning.

---

## 1. `else_edge` and `skip_response_edge` need magic strings

The `prompt` value is not free text. It must be **exactly** these words:

```json
"else_edge":          { "transition_condition": { "type": "prompt", "prompt": "Else" } }
"skip_response_edge": { "transition_condition": { "type": "prompt", "prompt": "Skip response" } }
```

A sensible sentence describing the fallback gets a 400.

**And the error hides the cause.** It is a union-type error, so it lists
every node type the object failed to match:

```
must be equal to one of the allowed values: Else,
must be equal to one of the allowed values: subagent,
must have required property 'tool_id',
must have required property 'code',
must have required property 'transfer_destination', ...
```

Read the **first** clause. The rest is noise.

**Rule:** when `create-conversation-flow` returns a 400 mentioning
`tool_id`, `code`, and `transfer_destination`, check the else edge first.

## 2. A node transition is its own message, not a field

`create-chat-completion` returns a mixed list. A transition arrives as a
message with `role: "node_transition"`, carrying `former_node_id`,
`new_node_id`, `new_node_name`, and `transition_type`.

Filter that list to `role in ("agent", "assistant")` and the entire path
disappears, silently, and you get an empty trace that looks like a flow
with no routing.

`tools/retell_chat.py` already gets this right in `node_hops`. A new tool
written from the docs will not.

`transition_type` is `"global"` when a global node grabbed the turn and
`"normal"` otherwise. That single field is the fastest way to see a global
node firing when it should not, and it is worth printing on every line.

## 3. `create-chat` returns no messages at all

Confirmed response keys, and that is all of them:

```
agent_id, agent_name, agent_version, chat_cost, chat_id,
chat_status, chat_type, data_storage_setting, start_timestamp
```

So `begin_message` never arrives as its own first turn. The agent folds it
into its reply to turn one.

**Consequence, and it belongs in section 22 of the flow standard:** a text
sandbox can show you WHAT the greeting says. It can never show you WHETHER
the agent speaks first. Add that to the list of things text testing cannot
prove, next to silence.

*Folded into the standard 2026-08-29.* It is now listed under "Text testing
cannot prove" in section 22, together with the one-turn-behind artifact.

## 4. `/v2/list-agents` rows are slim

Confirmed keys:

```
agent_id, agent_name, channel, folder_id, is_multi_prompt,
response_engine_type, tags, user_modified_timestamp,
voice_avatar_url, voice_id, voice_name
```

There is no `version`, no `webhook_url`, and **no `response_engine`
object**. Code reading
`row["response_engine"]["conversation_flow_id"]` off this list gets `None`
and carries on. Call `get-agent/{id}` for anything real.

Upside: `response_engine_type` plus `is_multi_prompt` tells single prompt
from multi prompt from conversation flow in one call.

## 5. `begin_message` can be the two-character string `""`

one example agent's single-prompt copy in this workspace,
`llm_6110d271e2d649fba045e240b95f`, has `begin_message` set to the literal
two characters `""`. Quote marks, not an empty string.

A dashboard paste does this. The API then reports the field as **set**, so
no check asking "is begin_message empty" catches it, and the agent speaks
a pair of quote marks or nothing at all.

**Rule:** strip quotes before testing a text field for emptiness.

---

## 6. A hand-built `code` node needs four fields the docstring never mentions

Found 2026-08-31, building the intake gate. A new `code` node written with the
fields that seem obvious - `id`, `name`, `type`, `code`, `else_edge`,
`display_position` - is rejected outright:

```
POST /create-conversation-flow failed: HTTP 400 Bad Request
request/body/nodes/33 must have required property 'instruction',
request/body/nodes/33/type must be equal to one of the allowed values: end,
request/body/nodes/33 must have required property 'tool_id', ...
```

The error is misleading. It does not say "your code node is missing fields"; it
walks every node type in the union and reports why the object failed to be each
one, so it reads as though the `type` is wrong. It is not. Four fields are
missing:

```json
"response_variables": { "gate_passes": "gate_passes" },
"speak_during_execution": false,
"wait_for_result": true,
"timeout_ms": 30000,
"edges": []
```

**`response_variables` is the dangerous one.** The other three are hard
failures, so they announce themselves. `response_variables` maps the key the
code RETURNS onto the dynamic variable it is stored in. Omit it and the node is
still accepted once the other three are present: it runs, it returns a value,
and the variable is never written. Every equation reading that variable then
silently takes the wrong edge, and the lint is clean because the variable is
declared.

The rule that avoids all of this: **never hand-write a node type the flow
already contains.** Dump an existing one and copy its key set field for field.

```python
ref = [n for n in flow["nodes"] if n["id"] == "node-closing-pass-counter"][0]
assert sorted(ref.keys()) == sorted(new_node.keys())
```

That assertion is two lines and would have caught this before the API did. It is
the same principle as the handoff's "a hand-typed inverse is a guess": dump the
constants out of the export instead of reconstructing them.

`extract_dynamic_variables` and `branch` nodes did NOT need this treatment in
the same change - their obvious field set was accepted - so the trap is specific
to `code`.

## 7. Repointing an edge orphans its fine-tune examples, and the PATCH is refused

Found 2026-08-31, pushing the intake gate. Lint CLEAN, traces green, round trip
byte-identical, and the push still failed:

```
PATCH /update-conversation-flow/... failed: HTTP 400 Bad Request
{"status":"error","message":"Please remove or update the finetune examples
 before deleting the associated node or edge."}
```

Nothing was deleted. Sixteen edges were REPOINTED from `Closing Pass Counter` to
a new gate node. A fine-tune example carries its own `destination_node_id`, and
Retell requires that id to match a destination its node can still reach. Move
the edge and the examples that taught it are orphaned, which reads to the API as
a deletion.

Five examples were affected here, on `Ask Vehicle`, `Ask Urgency` and
`Ask RS Issue`. All five teach "this caller turn ends the intake", which is
still true - only the node they name had moved.

**The rule: an example follows its edge.** When a transform repoints an edge,
repoint that node's examples with it, and only when the node has no edge left to
the old destination, so an example belonging to a different untouched edge is
never disturbed.

**A GLOBAL node is reachable from anywhere**, so an example naming one is always
legitimate and must never be counted as orphaned. one example agent has exactly one such
example, `fte-1783235215839` on `Service Request Intake`, pointing at
`Roadside / Safety Gate`. A naive orphan check flags it and would "fix" a
correct example.

Assert it before the API does:

```python
global_ids = {n["id"] for n in nodes if n.get("global_node_setting")}
for n in nodes:
    reachable = destinations(n) | global_ids
    for x in n.get("finetune_transition_examples") or []:
        d = x.get("destination_node_id")
        assert d is None or d in reachable
```

`flowlint.py` does not check this. Neither does `flowdiff.py`. The first signal
is a 400 from a push you had every reason to believe was ready.

## What changed because of these

`C:\Users\chats\.claude\skills\retell-setup\kit\` now encodes all five:

| File | Encodes |
|---|---|
| `flowkit.py` | 1, 2. The `say()` docstring and the skeleton template. |
| `sp.py` | 3. The `cmd_chat` comment and the closing note on every run. |
| `retellkit.py` | 4. The `list_agents` docstring. |
| `promptlint.py` | 5. `check_greeting` FAILs on quote marks specifically. |

Full write-up:
`C:\Users\chats\.claude\skills\retell-setup\reference\retell-api.md`.

## Two false-finding classes, also fixed there

Worth knowing before writing any new checker for this repo.

- **A global node has no inbound edge on purpose.** It is reached by its
  own condition. Reporting it as unreachable is a false finding, and Agent
  A has three. The marker is a non-empty `global_node_setting.condition`.

- **A dashboard export nests the flow under `conversationFlow`.**
  CamelCase, in an API that is snake_case everywhere else.
  `agents/agent-a/exports/v51.json` is this shape. A loader looking only
  for `conversation_flow` reports "flow has no nodes" on a perfect file.
