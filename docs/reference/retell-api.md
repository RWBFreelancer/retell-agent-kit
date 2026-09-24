# Retell API: the shapes, and the traps that cost real time

Every trap below was **confirmed live on 2026-08-29** by running the kit
against a real Retell workspace. None of them is guesswork, and most are not
in the docs.

## Endpoints the kit uses

### Single prompt (a "Retell LLM")

| Method | Path |
|---|---|
| POST | `/create-retell-llm` |
| GET | `/get-retell-llm/{llm_id}[?version=N]` |
| PATCH | `/update-retell-llm/{llm_id}[?version=N]` |
| DELETE | `/delete-retell-llm/{llm_id}` |
| GET | `/v2/list-retell-llms` |

Request fields: `general_prompt`, `begin_message`, `general_tools`,
`states`, `starting_state`, `default_dynamic_variables`,
`knowledge_base_ids`, `model`, `model_temperature`, `model_high_priority`,
`tool_call_strict_mode`, `start_speaker`, `kb_config`, `mcps`,
`is_transfer_llm`.

Response adds: `llm_id`, `version`, `is_published`,
`last_modification_timestamp`. Strip those four before a PATCH.

### Conversation flow

| Method | Path |
|---|---|
| POST | `/create-conversation-flow` |
| GET | `/get-conversation-flow/{id}[?version=N]` |
| PATCH | `/update-conversation-flow/{id}[?version=N]` |
| DELETE | `/delete-conversation-flow/{id}` |

### Agent

| Method | Path |
|---|---|
| POST | `/create-agent` |
| GET | `/get-agent/{agent_id}[?version=N]` |
| PATCH | `/update-agent/{agent_id}[?version=N]` |
| GET | `/list-agent-versions/{agent_id}` (paged; summary rows, no `response_engine` or `webhook_url`) |
| POST | `/create-agent-version/{agent_id}` body `{"base_version": N}` |
| POST | `/publish-agent-version/{agent_id}` |
| POST | `/v2/list-agents` |
| DELETE | `/delete-agent/{agent_id}` |

`response_engine` takes exactly three shapes:

```json
{"type": "retell-llm",        "llm_id": "llm_xxx",               "version": 0}
{"type": "conversation-flow", "conversation_flow_id": "cf_xxx",  "version": 0}
{"type": "custom-llm",        "llm_websocket_url": "wss://..."}
```

### Text sandbox

| Method | Path |
|---|---|
| POST | `/create-chat-agent` |
| POST | `/create-chat` |
| POST | `/create-chat-completion` |
| PATCH | `/end-chat/{chat_id}` |
| GET | `/get-chat/{chat_id}` |
| DELETE | `/delete-chat-agent/{agent_id}` |

### Calls and simulation testing

| Method | Path |
|---|---|
| POST | `/v3/list-calls` |
| GET | `/v2/get-call/{call_id}` |
| POST | `/create-test-case-definition` |
| POST | `/create-batch-test` |
| GET | `/get-batch-test/{batch_id}` |

`create-batch-test` accepts `retell-llm` and `conversation-flow` engines, so
simulation testing works for both agent types.

---

## The three rules that shape every workflow

1. `update-conversation-flow` and `update-retell-llm` take the **whole
   object**, not a field patch. Always GET, mutate, PATCH back.
2. Those PATCH calls write the **latest draft**. They never publish.
3. Published versions are **immutable** and carry live calls. Never target
   one. Create a fresh draft with `create-agent-version` first.

---

## The traps

### 1. `/v2/list-agents` returns a slim row

Confirmed keys, and that is the whole list:

```
agent_id, agent_name, channel, folder_id, is_multi_prompt,
response_engine_type, tags, user_modified_timestamp,
voice_avatar_url, voice_id, voice_name
```

There is **no `version`**, **no `webhook_url`**, and **no
`response_engine`** object. Code that reads
`row["response_engine"]["conversation_flow_id"]` off this list silently
gets `None`. Call `get-agent/{id}` for the real thing.

Upside: `response_engine_type` plus `is_multi_prompt` is how you tell a
single-prompt agent from a multi-prompt one without a second call.

### 2. `create-chat-agent` silently gives you version 0

`create-chat-agent` will not accept a version, and `update-chat-agent`
refuses to be repointed ("Response engine version must match agent
version"). So a chat agent aimed at your real flow or LLM gets **version 0**
of it. The very first version ever saved. Not your draft.

It fails silently. Every answer looks plausible and none of it is about the
thing you are testing.

**The fix:** POST the object to `/create-conversation-flow` or
`/create-retell-llm` as a brand new throwaway, then point the chat agent at
that. Both are version 0, so they line up. The kit does this in
`sp.Sandbox` and `flowkit.FlowSandbox`.

### 3. `create-chat` returns no messages at all

Confirmed keys: `agent_id`, `agent_name`, `agent_version`, `chat_cost`,
`chat_id`, `chat_status`, `chat_type`, `data_storage_setting`,
`start_timestamp`.

So `begin_message` never arrives as its own first turn. The agent folds it
into its reply to turn one.

**Consequence:** a text sandbox can show you WHAT the greeting says. It can
never show you WHETHER the agent speaks first. Only a real call proves that.

### 4. A node transition is its own message, not a field

In `create-chat-completion`, the reply list mixes roles. A transition
arrives as a message with `role: "node_transition"`, carrying
`former_node_id`, `new_node_id`, `new_node_name`, and `transition_type`.

Filter the list to `role in ("agent", "assistant")` and you throw the entire
path away, silently, and get an empty trace.

`transition_type` is `"global"` when a global node grabbed the turn and
`"normal"` otherwise. That one field is the fastest way to see a global node
firing when it should not.

### 5. `collected_dynamic_variables` fills in only after the chat ends

Order is not optional: send every turn, **end the chat**, then read it.
Read it early and it is empty.

### 6. Retell omits null fields

A cleared `webhook_url` does not come back as `webhook_url: null`. The key
is simply **absent**. In a `git diff` of a saved settings file that reads as
a deleted line, which looks like tidying rather than a fault.

This is how one real project shipped three published versions that collected
leads perfectly and forwarded none of them.

### 7. The dashboard export nests the flow under camelCase

A flow exported from the Retell dashboard is a whole Agent object with the
flow under **`conversationFlow`**. Note the camelCase, in an API that is
snake_case everywhere else. A loader that only looks for
`conversation_flow` reports "flow has no nodes" on a perfectly good file.

### 8. A node has four exit kinds, not one

```
edges                a list of conditional transitions
else_edge            taken when no edge matched
always_edge          taken unconditionally
skip_response_edge   speaks its line and moves on without waiting
```

A checker that reads only `edges` reports live nodes as dead ends.

### 9. A global node has no inbound edge on purpose

A global node is reached by its own condition from anywhere in the call.
Reporting it as unreachable is a false finding, and a mature flow has
several. The marker is a non-empty `global_node_setting.condition`.

### 10. `else_edge` and `skip_response_edge` need MAGIC STRINGS

This one is not in the docs and it rejects an otherwise perfect flow.

```json
"else_edge":          { "transition_condition": { "type": "prompt", "prompt": "Else" } }
"skip_response_edge": { "transition_condition": { "type": "prompt", "prompt": "Skip response" } }
```

The `prompt` value must be **exactly** `"Else"` and **exactly**
`"Skip response"`. Anything else, including a perfectly sensible sentence
describing the fallback, gets a 400.

Worse, the 400 is a **union-type error**. It lists every node type the
object failed to match, so the real cause is buried in a wall like
"must have required property 'tool_id', must have required property
'code', must have required property 'transfer_destination'...". Read the
FIRST clause, not the list.

### 11. `begin_message` can be the two-character string `""`

A dashboard paste can store quote marks rather than an empty string. The API
reports the field as set, so no check that asks "is it empty" catches it,
and the agent then speaks a pair of quote marks or nothing. Seen live.

---

## Where credentials live

The kit looks in this order, first hit wins:

1. the process environment
2. `.env` in the current directory, or the nearest parent holding `.git`
3. `%USERPROFILE%/.retell.env`

Because of step 2, **the current directory matters**. Running the kit from
the kit folder, rather than from the project, finds no `.env` and reports a
missing key. Either `cd` to the project first, or put a global key in
`%USERPROFILE%/.retell.env`.
