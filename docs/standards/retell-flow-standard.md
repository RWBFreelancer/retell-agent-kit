# Retell Conversation Flow — Standard

The rules for building, editing, checking, and QA of a Retell conversation flow.

This document is general. It is not tied to one client. Use it on any Retell
conversation flow.

Two short lists go with it:

- [build-checklist.md](build-checklist.md) — use while you build or edit.
- [qa-checklist.md](qa-checklist.md) — use while you check an existing flow.

---

## 0. Scope, sources, and what wins

### Sources

| Source | What it gave |
|---|---|
| `docs.retellai.com` | The node reference, the API schema, and the documented defaults |
| `community.retellai.com` | Retell staff naming a failure and its cause |
| Retell course transcript, 34 chapters, 2026 | How flows work under the hood, and why |
| 29 Retell official templates | Real JSON shapes, real compliance wording |
| Voice AI starter kit | Prompt style, standard handlers, test method |

The last three live in Google Drive at
`C:\GoogleDrive\Freelance Clients\Assets\Retell Conversational Flow\`.
They are read-only.

### How to read a claim in this document

Three kinds of statement appear here, and they carry different weight. Tell them
apart before you act on one.

| Marker | Means | Trust it |
|---|---|---|
| A `docs.retellai.com` or `community.retellai.com` URL | Retell says so | Yes. Re-check the page if it is load-bearing. |
| "Measured on this project, `<date>`" plus a rep count or a call id | We saw it happen here | Yes, for this flow. It may not generalise. |
| Neither | Inherited from the course transcript or the templates | Treat as a working assumption. Verify before you build on it. |

When you verify an unmarked claim, add the URL. When you disprove one, say so in
place and leave the correction visible. Do not delete a claim silently.

### Warning: the starter kit is written for a different agent type

The starter kit teaches **single-prompt agents**. A single-prompt agent is one
big prompt with no nodes.

This document is about **conversation flows**. A conversation flow is a map of
nodes and edges.

Split the kit in two:

| Part of the kit | Use it? |
|---|---|
| Prompt style, sample calls, standard handlers, meta orienter, test method | Yes. It applies to node text. |
| The API section, the "publish after every change" rule, the LLM caching bug | No. Wrong API. It does not apply to flows. |

A flow is written with `update-conversation-flow`, not `create-retell-llm`.
Never follow the kit's API pages when working on a flow.

### Warning: do not copy the key

The starter kit file `PROMPT-WRITING-RULES.md` holds a plain-text Retell API key.
Never copy it. Never paste it. Never write it into any repository.

### What wins when documents disagree

1. A PRD in `prd/`, for its own scope.
2. The project `CLAUDE.md` and any agent-specific `CLAUDE.md`.
3. This standard.

This standard is general. A client rule always beats a general rule. If this
document and a client rule disagree, say so and ask.

---

## 1. Flow or single prompt?

Pick before you build. The wrong choice cannot be fixed later by prompting.

The test is who leads the call.

| The call is | Example | Build |
|---|---|---|
| Caller-led. The caller asks. You react. | General receptionist, support desk, counseling | Single prompt |
| Agent-led. You ask. The caller answers. | Intake, booking, payment, verification, screening | Conversation flow |

Three more triggers that force a flow:

1. A long list of details must be collected in a fixed order.
2. A line must be said word for word, for compliance.
3. Routing must be certain, not likely.

A single prompt can book an appointment. A flow does it more reliably.

Retell states its own thresholds for reaching past a single prompt: more than
three or four conditional paths, five or more tools, several variables tracked
across the call, or a single prompt already behaving inconsistently. Any one of
them is enough.

Source: `https://docs.retellai.com/build/prompt-engineering-guide`.

If the answer is single prompt, stop reading here and use
[single-prompt-standard.md](single-prompt-standard.md). The rest of this document
is about nodes and edges, and almost none of it transfers.

---

## 2. Rigid mode only

### What the model can see

In **rigid mode**, at any point in the call, the model sees only:

1. The global prompt.
2. The **one** node it is in right now.
3. The conversation history so far.
4. A knowledge base, only if that node has one turned on.
5. A tool, only if that node has one attached.

It cannot see the other nodes. It cannot see the other tools.

That is why a flow can grow past 100 nodes and still follow instructions. A
single prompt cannot, because everything fights for attention in one window.

### What a turn actually costs

This follows directly from the list above, and it is the most commonly
misunderstood part of rigid mode:

```
cost of a turn  =  always-on  +  the ONE node you are in
```

where **always-on** is the global prompt plus, for every global node, its
condition, its fine-tune examples, and its go-back conditions. Global node
conditions are evaluated on every turn, so they are paid on every turn even when
the node never fires.

So the worst case for a flow is **always-on plus its largest node**.

Retell counts six things toward the token total that drives the billing
surcharge. Quoted from the billing page, in its order:

> global prompt, functions (tool descriptions), state / node prompt, transcript
> between agent and user, tool call history and results, retrieved knowledge base
> content

Source: `https://docs.retellai.com/accounts/billing-exceptions`. Two of those six
are outside your control once the call starts: the transcript grows every turn,
and so does tool call history. See
[../lessons-token-cost.md](../lessons-token-cost.md) for the formula and for what
a trim is actually worth.

**The linter under-reports this total.** `flowlint.py` counts
`finetune_transition_examples` toward a node's tokens but not
`finetune_conversation_examples`, which exists on three nodes in a second example agent v29. A
node carrying conversation examples costs more per turn than the report says.

Two consequences people get wrong:

- **The same paragraph in two nodes is almost free.** Only one of them is ever
  loaded. A repository-wide duplicate count is a hygiene measure, not a token
  bill. Deduplicating twenty small nodes can look like a large saving and change
  nothing about any real call.
- **The only levers that move the worst case** are the global prompt, the global
  node settings, and the single largest node. Cut there first, and measure per
  turn, never per repository.

Fine-tune examples on a small node are close to free for the same reason. Spend
them where routing is decided, not where the word count is highest.

### Flex mode: default to off

Flex mode looks like a flow but is a single prompt underneath.

It is a supported, current Retell feature. This standard defaults to rigid mode
because our agents are agent-led intake, where the order of questions matters.
Flex mode is a real option only when a caller genuinely needs to jump between
unrelated tasks mid-call.

What the Retell docs actually say, which is narrower than "it does not work":

- Prefer prompt edges over equation edges. Equation edges are discouraged, not
  broken.
- There is no "Speak After Execution" setting in flex mode. That one field is
  missing, not all static text.
- Past 20 nodes, verbatim: "If you use flex mode for more than 20 nodes,
  performance might degrade and agent might have higher hallucination risk."
- Prompts over 4,000 tokens trigger token-scaling billing, which can multiply
  cost several times over.
- A node-level knowledge base is ignored. Verbatim: "Node-level knowledge base
  will be ignored in Flex Mode. You will need to configure the knowledge base at
  agent level."
- `wait_for_result` is gone. The agent always waits for a tool to finish.

Source: `https://docs.retellai.com/build/conversation-flow/flex-mode`.

The cost difference follows from the mode, not from the prompt. In rigid mode
only the active node's prompt reaches the model; in flex mode every node
instruction, every transition, and every tool description is compiled into one
prompt and sent on every turn. That is what pushes a flex flow through the 4,000
token line that a rigid flow of the same size never approaches.

Community reports also put flex-mode latency far above rigid mode. Treat that
as anecdote, not a number to design against.

If you want flex behaviour, a single-prompt agent is usually the clearer build.

All 29 official templates have flex mode off or absent.

Check: `conversationFlow.flex_mode` must be `false` or missing.

---

## 3. Node catalog

Counts below are from all 424 nodes in the 29 official templates. They show what
Retell itself uses most.

| Node type | Count | What it does | Use it when |
|---|---|---|---|
| `conversation` | 264 | The agent speaks and listens | The normal node. Default choice. |
| `end` | 62 | Ends the call | Every branch must reach one |
| `transfer_call` | 26 | Sends the call to a number | Escalation, human request |
| `component` | 20 | A reusable group of nodes | Reuse, or to tidy a busy canvas |
| `function` | 20 | Calls a tool | The tool must run **every** time |
| `extract_dynamic_variables` | 11 | Pulls named values out of the call | You need a value later |
| `subagent` | 11 | A conversation node with its own tools | The tool runs **sometimes** |
| `branch` | 6 | Silent routing split | Route without speaking |
| `press_digit` | 2 | Presses DTMF keys | Navigating another company's IVR |
| `code` | 1 | Runs JavaScript in the flow | Small logic, like business hours |
| `sms` | 1 | Sends a text mid-call | You need a text sent now |

### The authoritative list is the API reference, not this table

The counts above say what the templates use. They do not say what exists. The
create-conversation-flow request schema is the list that decides whether a node
type is real:

`conversation`, `subagent`, `extract_dynamic_variables`, `function`, `code`,
`sms`, `mcp`, `transfer_call`, `agent_swap`, `press_digit`, `branch`, `end`,
`component`, `bridge_transfer`, `cancel_transfer`.

Source: `https://docs.retellai.com/api-references/create-conversation-flow`.

Retell's own node page groups them as dialogue (`conversation`, `subagent`,
`extract_dynamic_variables`), action (`function`, `code`, `sms`, `mcp`), call
control (`transfer_call`, `agent_swap`, `press_digit`, `end`), and structure
(`branch` — "Logic Split" in the editor — and `component`, the reusable subflow).
Source: `https://docs.retellai.com/build/conversation-flow/node`.

A note is not a node. It lives in the flow's `notes` array and does nothing at
run time.

### This repository uses five of them

Across every export in `agents/`, exactly five node types appear:

| Type | a second example agent v29 | one example agent v51 |
|---|---|---|
| `conversation` | 26 | 14 |
| `code` | 3 | 3 |
| `branch` | 1 | 3 |
| `extract_dynamic_variables` | 2 | 0 |
| `end` | 1 | 1 |

There is no `function`, `subagent`, `transfer_call`, `sms`, `press_digit`, `mcp`,
or `agent_swap` node anywhere in this repository, and no `tool_id` key.

This matters when you are asked to add one. You cannot copy the key set from a
node of that type already in the flow, because there isn't one — and hand-writing
a node object is how the eleven-key code node failure below happened. Copy from a
template in the Drive folder instead, and expect the first PATCH to be the moment
the schema is actually enforced.

### The rule people get wrong: `function` versus `subagent`

- A `function` node fires the tool **100 percent of the time** when the flow
  reaches it. It is part of the route.
- A tool inside a `subagent` node fires **only when the model decides to**.

Pick by need:

- Must always run, such as logging every call → `function` node.
- Should run only if it makes sense, such as checking a slot the caller may not
  have asked for → tool inside a `subagent`.

### The `branch` node

A `branch` node routes silently. The caller hears nothing. Use it to split on a
value you already hold, such as new versus returning customer.

Prefer a `branch` with equation edges over a spoken question. It is silent and
it is certain.

### The `code` node

Runs JavaScript inside Retell. No outside host needed.

Rules seen in the real template:

- No `Intl`. No outside libraries. It is sandboxed.
- Return a plain object. Map it with `response_variables`.
- Set `timeout_ms`. The template uses `30000`.
- Set `wait_for_result: true` when the next edge needs the value.

Move small jobs here. Do not host them elsewhere.

**A hand-built code node needs ELEVEN keys, not four.** Writing one from
scratch with only `id`, `type`, `name`, `code`, `display_position` and
`else_edge` is rejected by the API:

```
HTTP 400  request/body/nodes/21 must have required property 'instruction',
          ... must have required property 'wait_for_result', ...
```

The error names `instruction` and every other node type's required field,
because the schema tries each node type in turn and reports all of them. It
does not say "you are missing `wait_for_result` on a code node". Read it as
"this node matches no node type", not as "it wants an instruction".

The full key set, copied from a working code node:

| Key | Value |
|---|---|
| `id`, `type`, `name`, `code` | the obvious four |
| `edges` | `[]` — required even when empty |
| `response_variables` | `{"var": "var"}` — see below |
| `timeout_ms` | `30000` |
| `wait_for_result` | `true` |
| `speak_during_execution` | `false` |
| `display_position` | `{"x": ..., "y": ...}` |
| `else_edge` | where it falls through to |

**`response_variables` is the dangerous one.** It is the map from the object
the code RETURNS to the flow variables it WRITES. Omit it and the node runs,
computes the right answer, and throws it away. Nothing errors. The variable
just stays at its default forever, and every node reading it is silently
wrong.

**`flowlint.py` cannot catch any of this.** It reads the object in memory
against its own rules, not against Retell's schema. A hand-built code node
missing every key above still lints CLEAN, including the variable check: the
linter counts the `code` body as the write. The API is the only thing that
knows. So the first `tracerun.py` after adding a node is not optional — it is
the first moment the schema is enforced. Found 2026-08-27 building
`transforms/a_closing_pass_counter.py`.

Never hand-write a node object. Copy the key set from a node of the same type
already in that flow, then change the values.

---

## 3a. GPT-4.1, the model these flows run on

Every flow in this repository sets
`model_choice: {"type": "cascading", "model": "gpt-4.1", "high_priority": false}`,
at flow level and again on every conversation node. All 29 official templates use
`gpt-4.1` too, and Retell's global-settings page recommends it for the balance of
response quality, latency, and cost.

The model is not a detail. Several defects this repository spent days on as
prompt problems are documented GPT-4.1 behaviours. Read this section before
rewriting a node instruction that is not being followed.

Everything below is quoted from OpenAI's GPT-4.1 prompting guide
(`https://developers.openai.com/cookbook/examples/gpt4-1_prompting_guide`) or
from Retell's own pages, and each rule says which.

### It follows instructions literally, and fills in nothing

> "GPT-4.1 is trained to follow instructions more closely and more literally than
> its predecessors, which tended to more liberally infer intent."

This is the root of the largest class of defect in this repository. An
instruction that a human would read as obviously implying something does not
imply it to GPT-4.1. Three shapes that keep failing here, all of them the same
failure:

- A fill-in slot with no empty branch. `"... {always ask next question needed}"`
  is an order to ask on every turn. The model will not infer "unless there is
  nothing left". Give it the empty case in words.
- A rule with an unstated exception. If the exception is not written, it does not
  exist.
- A description of a question instead of the question. "Ask for their vehicle"
  gets you the model's own sentence. `Ask exactly, word for word: "..."` gets you
  yours.

The counterpart is the good news:

> "if model behavior is different from what you expect, a single sentence firmly
> and unequivocally clarifying your desired behavior is almost always sufficient
> to steer the model on course."

One clear sentence. Not a fourth rewrite of the same paragraph. If one clear
sentence does not do it, the problem is structural and prose will not fix it —
go to the fix ladder in section 22.

### A transition is a tool call, which is why the model matters here

Node transitions are executed as tool calls. Retell support, on agents that
transitioned correctly on GPT-4o and stopped on GPT-4.1:

> "tool calling behavior differences between models is a known consideration"

and their recommendation was to enable `tool_call_strict_mode`, which

> "ensures stricter adherence to the tool calling schema"

and could "improve transition reliability".

Source:
`https://community.retellai.com/t/anyone-else-having-node-transitions-not-working-on-gpt-4-1/877`.

Both flows here already set `tool_call_strict_mode: true`. **Do not turn it off.**
It is not a tidy-up field. It is load-bearing for routing on this model.

It also explains why prompt edges are probabilistic in the way section 6
describes. A prompt edge is the model deciding to call a tool. Prompt edge
reliability and tool-calling reliability are the same problem.

### Numbered labels in an instruction can fire a transition

Retell's debug guide, on transitions firing when their condition never matched:

> "Items like 'PRIORITY 1' or 'Step 2' in your global prompt or node instructions
> can be confused with transition options and trigger a transition whose
> condition was never met. Use letters ('PRIORITY A') or descriptive names
> instead."

Source: `https://docs.retellai.com/build/conversation-flow/debug-guide`, repeated
on `https://docs.retellai.com/build/conversation-flow/transition-condition`.

This reverses a rule this repository held for months. See section 4 for the
prompt shape that replaces it, and
an audit of every node carrying the old numbered pattern, done once when the rule below was adopted.

### On conflicting instructions, the later one tends to win

> "if there are conflicting instructions, GPT-4.1 tends to follow the one closer
> to the end of the prompt."

Measured on this project, 2026-08-26, the opposite happened: a CAPS rule beat an
exception written four sentences later, and the exception was never reached (see
section 4, node prompt rule 7).

Both observations are real and they do not resolve into a rule about ordering.
The conclusion is not "put the important thing last" or "put it first". It is:

**Never write a rule and its exception as two separate statements.** Write one
statement with the condition inside it. "If X, do A; otherwise do B" cannot be
half-followed. "ALWAYS do A" followed later by "except when X" can, and which
half wins depends on emphasis, distance, and ordering all at once.

The same applies across the global prompt and the node instruction. The node
instruction arrives after the global prompt, so a node rule that contradicts a
global rule is a coin flip you did not mean to write. Section 5's cleanup rule is
the fix: a rule lives in exactly one place.

### Sample phrases come back verbatim

> "When provided sample phrases, models can use those quotes verbatim and start
> to sound repetitive to users."

Section 4 tells you to end a node prompt with an `Example:` line, and that advice
stands — an example is the strongest lever this platform gives you. But an
example is a template, not a suggestion, and GPT-4.1 will reuse it word for word
across turns.

So: when the exact words matter, that is what you want, and you should be using
`static_text` instead. When the exact words do not matter, say so in the
instruction — "vary the wording" — or the caller hears the same sentence three
times.

This is the mechanism behind some repeated-line defects in section 21. A line
repeating is not always a routing loop. Sometimes the node is being re-entered
and the example is doing exactly what an example does.

### "Always" can backfire

> "Instructing a model to always follow a specific behavior can occasionally
> induce adverse effects"

OpenAI's example is hallucinated tool inputs when a model is told it must always
call a tool. The version seen here is a node told to ALWAYS ASK inventing a
question when nothing was left to ask.

If a behaviour is genuinely unconditional, structure enforces it better than the
word "always": a `skip_response_edge`, an equation edge, a dedicated node. If it
is not unconditional, write the condition.

### It will occasionally speak its own prompt aloud

Reported repeatedly through August 2026 on GPT-4.1 conversation flows: the agent
read its node instruction to the caller instead of acting on it, at short
announcement nodes. Retell's assessment:

> "it looks like a rare model instruction-following slip on gpt-4.1 for this
> specific short-announcement node"

Their mitigation was to switch the node's `instruction` from
`{type: "prompt", ...}` to `{type: "static_text", text: ...}`. Retell submitted a
fix on 2026-08-11 and shipped it gradually; further incidents were reported on
2026-08-17, so treat it as mitigated rather than closed.

Source:
`https://community.retellai.com/t/agent-spoke-its-system-prompt-aloud-to-the-caller-at-a-transfer-call-node-gpt-4-1-conversation-flow/3478`.

This happened on this project too — see
`docs/v24-live-call-review.md` (removed 2026-09-11; read it with `git show da55696:<path>`) defect 1, "the agent
spoke its own stage direction to a caller". It was not a prompt-writing mistake.

**Rule: a node whose whole job is to say one short line uses `static_text`.** Not
because the wording is contractual, but because a prompt instruction at such a
node is the exact shape that leaks.

### Temperature is not set on these flows

`model_temperature` is a flow-level field. It appears in **no export in this
repository**, so both flows run Retell's default.

Retell documents the ranges: "0.0-0.3: Highly consistent, deterministic" for
function calling and data collection, "0.4-0.7" for general service, "0.8-1.0"
for creative. Source: `https://docs.retellai.com/build/llm-options`.

Intake is data collection. If a node is inconsistent and the instruction is
already clear, lowering temperature is on Retell's own fix ladder (section 22).
But setting it is a change to every node at once — measure before and after, and
do not bundle it with anything else.

---

## 4. Instruction format

A node instruction has exactly two types. Nothing else exists.

| Type | Meaning |
|---|---|
| `static_text` | The agent says this, word for word |
| `prompt` | The agent is given a goal and works out the words |

Counts in the templates: `prompt` 258, `static_text` 77.

### When to use `static_text`

Use it whenever the exact words matter:

- The greeting.
- Any legal or compliance line.
- An AI disclosure or recording notice.
- The line said while a tool runs.
- Any line a routing condition depends on.
- Any node whose whole job is to say one short line and move on.

The course is direct about the tool-wait line. A prompt makes the agent
improvise there, and it sounds loose. Hard-code it.

The last bullet is newer and has a different reason. On gpt-4.1, a short
announcement node carrying a `prompt` instruction is the documented shape that
leaks the instruction to the caller, and Retell's own mitigation is to switch it
to `static_text`. See section 3a. Use `static_text` there even when the wording
does not matter.

### When to use `prompt`

Use it when you want a goal, not a script. Collecting details. Answering a
question. Handling an objection.

### Shape of a node prompt

Four parts, in this order:

```
Your job is to <one task>.

- <do this>
- <then this>
- <then this>

RULE: <a rule that matters for this task only>

Example: "<exact words the agent could say>"
```

**Do not number the steps.** This changed on 2026-08-29. Retell's debug guide, on
transitions firing when their condition never matched:

> "Items like 'PRIORITY 1' or 'Step 2' in your global prompt or node instructions
> can be confused with transition options and trigger a transition whose
> condition was never met. Use letters ('PRIORITY A') or descriptive names
> instead."

Source: `https://docs.retellai.com/build/conversation-flow/debug-guide`.

The mechanism is in section 3a: a transition is a tool call, and a numbered list
in the instruction competes with the numbered transition options the model is
choosing between. The failure is silent. The node routes somewhere nobody asked
for, and the instruction that caused it looks perfectly reasonable.

Use, in order of preference:

| Instead of | Write |
|---|---|
| `Step 1:` `Step 2:` | Dashes, or nothing at all |
| `(1)` `(2)` `(3)` inline | Separate sentences |
| `PRIORITY 1` | `PRIORITY A`, or name it: `SAFETY FIRST` |
| `RULE 1` `RULE 2` | One `RULE:` line each, or a descriptive label |

Ordinals in prose are fine — "ask for the vehicle first, then the problem" reads
as instruction, not as a label. What Retell warns about is a **label at the start
of a line**, which is the shape a transition option takes.

If the steps genuinely must be ordered and the order matters enough to label,
that is a signal the node is doing too much. Split it. Retell's own guidance on
the conversation node: "It's recommended to split the node when there's a logic
split, or the instruction gets too long."
(`https://docs.retellai.com/build/conversation-flow/conversation-node`)

You may drop the role line for a small node. A one-line prompt is allowed:

```
Ask the caller what their favorite product is based on what they just said.
```

### Node prompt rules

1. **One node, one job.** Not smaller. Not bigger.
2. **Do not split a node per question.** Four questions in one node is fine. It
   keeps the canvas readable.
3. **Split only when it breaks.** The moment a node stops following its prompt,
   split it. Retell says the same: "It's recommended to split the node when
   there's a logic split, or the instruction gets too long."
   (`https://docs.retellai.com/build/conversation-flow/conversation-node`)
4. **Keep it short.** Long node prompts start to fail. If it runs past a short
   screen, it is too long.
5. **Only local rules.** A rule that applies everywhere belongs in the global
   prompt, not here.
6. **Never reword a `static_text` line** unless you were asked to. Routing may
   depend on the exact sentence.
7. **Write a rule and its exception as one statement, never two.** A block that
   opens with "ALWAYS ASK ... never end your turn on an answer alone" will make
   the model invent a question, even when the same paragraph later says "if
   nothing is left, ask nothing" — measured on this project, 2026-08-26, where
   the loud rule won and the exception four sentences later was never reached.

   OpenAI documents the opposite tendency for this model: "if there are
   conflicting instructions, GPT-4.1 tends to follow the one closer to the end of
   the prompt." Both are true, which is the point. Ordering is not a control you
   can rely on in either direction.

   The fix is not to reorder. It is to stop writing two statements. `If X, ask
   the next question; if nothing is left, say nothing and wait` has no halves to
   choose between. See section 3a.
8. **A fill-in slot with no empty branch is an order.** A line like
   `"... {always ask next question needed}"` commands a question on every turn
   and gives the model no way to express "there is nothing left to ask". Every
   slot needs its "or nothing, and here is what to do instead". This is literal
   instruction-following working as documented, not a model defect.
9. **A rule that names a variable beats a rule that describes a situation.**
   "Read `{{anything_else_asked}}`; if it is true, that line has already been
   asked" held where four rewrites of the same rule in prose did not. If the
   flow already records the fact, point the instruction at the fact.
10. **No numbered labels at the start of a line.** No `Step 2`, no `(1)`, no
    `PRIORITY 1`, no `RULE 3`. They compete with the model's transition options
    and can fire an edge whose condition never matched. See the prompt shape
    above for what to write instead.
11. **An `Example:` line will be reused word for word.** OpenAI: "When provided
    sample phrases, models can use those quotes verbatim and start to sound
    repetitive to users." If the words are contractual, use `static_text` and
    stop pretending it is an example. If they are not, add "vary the wording" —
    otherwise the caller hears your example three times.
12. **A node that only announces one short line uses `static_text`.** A prompt
    instruction at such a node is the documented shape that leaks the prompt to
    the caller on this model. See section 3a.

### The wait marker

Some templates end a node prompt with:

```
<*Wait for customer response*>
```

It marks the point where the agent stops and listens. Use it when a node prompt
could otherwise read as one long speech.

---

## 5. Global prompt versus node prompt

### What belongs in the global prompt

| Put here | Example |
|---|---|
| Role | "You are the AI receptionist for X" |
| Personality | "Warm, direct, never bubbly" |
| Rules that must never break | "NEVER give medical advice" |
| Tone guardrails | "Never sound like a debt collector" |
| Compliance | "Verify identity before sharing account details" |
| Speech formatting | How to say money, dates, phone numbers |
| Time awareness | `Current time is {{current_time_America/los_angeles}}` |
| Business facts | Hours, address, accepted insurance |

### What belongs in a node

Steps. Only steps. Plus rules that apply to that one task.

### The cleanup rule

This is the rule most builders skip, and it costs the most.

**Delete anything from the global prompt that the flow already enforces.**

A rule the routing already guarantees does two bad things. It burns tokens on
every single turn. And it dilutes the rules that still matter.

Real examples from the course:

| Line in the global prompt | Why it was deleted |
|---|---|
| "After 5pm never attempt a live transfer" | A code node already checks the hours and routes |
| "Always open with the recording notice" | A static-text node already says it |
| "Never transfer to an attorney's cell phone" | No transfer in the flow points at one |
| "How to spell out an email" | Every email node already carries that block |
| "If a tool call fails, apologize and take a number" | A failure edge already routes there |

Ask of every global line: *can the caller reach a state where the flow does not
already force this?* If no, delete the line.

---

## 6. Transitions

An edge has a `transition_condition`. There are two types.

### Equation first. Always.

An **equation** edge is a fact check. It fires or it does not.

A **prompt** edge asks the model to judge. That is a probability. It may work 90
percent of the time. Nine out of ten is a defect, not a pass.

**Rule: if an equation can do the job, use an equation.**

The templates use prompt edges 327 times and equation edges 10 times. Do not
copy that ratio. The templates are demos. The course is explicit that equation
edges are the point of conversation flow.

### Edge evaluation order

Retell evaluates the ways out of a node in this order. Know it before you write
an edge, because it decides which one wins.

1. **Always edge.** Fires as soon as the caller replies. Nothing else is read.
2. **Equation edges.** Read top to bottom. First one that is true wins.
3. **Prompt edges.** Only reached if no equation edge matched.
4. **Else edge.** The fallback.
5. Nothing matched: the caller stays in the node.

Source: `https://docs.retellai.com/build/conversation-flow/transition-condition`,
which states the always edge case as: "if the node has one, the agent transitions
through it right after the user responds. Nothing else is checked." For prompt
edges it says the LLM "evaluates all prompt conditions together ... and picks the
single best match — or none." That is one judgement across all of them, not a
scan, which is why two overlapping prompt edges have no tie-break.

Retell also states the rule for writing them: "each condition should stand on its
own — describe what the user said or the state reached, without leaning on the
instruction text." An edge condition that only makes sense if you have read the
node instruction is a defect, because the instruction is not what is being
evaluated.

Two rules follow from this.

**Never put two prompt edges on one node that could both match the same turn.**
Equation edges have a documented tie-break, top to bottom. Prompt edges do not.
Two overlapping prompt edges make the route a coin flip, and the trace results
stop being repeatable. If two conditions could both match, capture the deciding
fact with an `extract_dynamic_variables` node and route on an equation edge.

**Use the else edge for the common case, a prompt edge for the rare one.** A
question node normally has one prompt edge for the exception, such as a hang-up,
and the else edge for "the caller said something". That is deterministic. Two
prompt edges racing each other is not.

### Equation shape

```json
{
  "type": "equation",
  "operator": "&&",
  "equations": [
    { "left": "{{is_business_hours}}", "operator": "==", "right": "true" }
  ]
}
```

Operators available:

| Operator | Meaning |
|---|---|
| `==` | equals |
| `!=` | does not equal |
| `>` `>=` | greater than, or greater than or equal |
| `<` `<=` | less than, or less than or equal |
| `contains` | holds this text |
| `does not contain` | does not hold this text |
| `exists` | the variable has a value |
| `does not exist` | the variable has no value |

`exists` and `does not exist` are the cleanest pair. Use them for "did we
capture this yet?"

### The join trap

`operator` joins the equations in the list.

- `&&` means **all** must be true.
- `||` means **any** may be true.

A common defect: an edge needs two conditions, both are written, but the join is
left as `||`. The edge then fires on either one. This is silent. Nothing errors.

Check every multi-equation edge for the right join.

### Every exit kind

| Field | Fires when |
|---|---|
| `edges` | Its condition is met |
| `else_edge` | No listed edge matched |
| `always_edge` | Always, after the node finishes |
| `skip_response_edge` | The node speaks, then leaves at once, no reply wanted |
| `success_edge` / `failed_edge` | On an `sms` node, sent or not sent |
| `edge` | On a `transfer_call` node, the transfer-failed path |

Rules:

1. A node with `edges` and no `else_edge` can trap the call. Check it.
2. `skip_response_edge` is the right exit for a closing line. The agent says
   goodbye and hangs up. It does not wait.
3. Never leave a `transfer_call` node without a failure path.

### The one question to ask of every node

> **What does the caller need to say here?**

If the answer is "nothing", the node must not wait. It speaks and leaves in the
same turn, which means `skip_response_edge`.

This is not a style preference. **An `always_edge` does not solve it.** An always
edge still needs a caller turn to fire, and a caller who says nothing does not
produce one, so the node re-runs and says its line again. A node that only
announces something and collects nothing will repeat itself on any non-answer
until you give it `skip_response_edge`.

Tested on this project at six repetitions: with an `always_edge` the flow never
left the node and the line was spoken three times; with `skip_response_edge` it
left in the same turn, every time.

Two things that look similar and are not:

| Node | Right exit | Why |
|---|---|---|
| Says a line, asks nothing, collects nothing | `skip_response_edge` | there is no reply to wait for |
| Asks a question | never `skip_response_edge` | it would ask and walk away before the caller answers |

### When an `always_edge` IS correct

The rule above is about a node the caller can be sitting in when they say
nothing. It is not a blanket ban, and this repository contains a correct
`always_edge` that has been mistaken for a bug more than once:
`agents/agent-b/CLAUDE.md` records that Safety Cap Reached uses one deliberately.

The distinction is where the node sits, not what it says:

| The node is | `always_edge` | Why |
|---|---|---|
| Entered directly after a caller turn, on a path that already has the turn | Correct | The turn that carried the caller in is the turn the always edge fires on |
| Entered with no caller turn pending, and it asks for nothing | Wrong | There is no turn to fire on. The node re-runs and repeats its line. Use `skip_response_edge` |

So: an always edge does not *create* a caller turn, but it does not need to if
one has just happened. Before you "fix" one, trace what precedes the node.

Note also that `always_edge` appears in **neither live flow** as of a second example agent v29
and one example agent v51. It survives only in older exports. If you find one in a current
flow, it was added deliberately and recently — read the changelog before touching
it.

### Before you add an `else_edge`, name the normal exit

A node that sometimes stalls looks like it is missing a fallback. Sometimes it
is. But on a **global node**, the ordinary way out is usually the go-back
condition: the caller answered something that belongs to the node they came
from, and they should be returned there.

An `else_edge` on such a node competes with the go-back on every ordinary turn,
and can pull callers out of the middle of an intake. On a global node, widen the
**go-back condition** instead — that is the fallback.

Rule: write down what the node's most common exit is. If an `else_edge` would
also match that case, it is the wrong fix.

---

## 7. Global nodes

A global node can be reached from anywhere in the call, whenever its condition is
met. It is the tool for things a caller can raise at any moment.

### Shape

```json
"global_node_setting": {
  "condition": "<when to jump here>",
  "cool_down": 3,
  "go_back_conditions": [
    { "id": "...", "transition_condition": { "type": "prompt", "prompt": "<when to return>" } }
  ]
}
```

### Good uses

Seen across the templates:

- An FAQ node that answers hours, pricing, service area, and services.
- A safety or emergency node.
- A "caller wants a human" node.
- An "are you a robot / is this spam" node. Needed on outbound.
- An angry-caller node.
- An intent-switch node, for when the caller changes topic mid-call.

### The go-back trap

**A global node with two prompt edges, no `else_edge`, no `always_edge` and no
go-back condition is a trap.** Nothing is guaranteed to match, and a caller who
only says "okay" stays in the node forever while it re-speaks its line every
turn. Seen on a real call: the same sentence four times, and the caller could
not get off the line. Both prompt edges named conditions the caller had no
reason to satisfy.

Check every global node for at least one exit that cannot fail to match. A
go-back condition is usually the right one. Where a node has no go-back at all,
an `else_edge` is correct, and the caution above about competing with the
go-back does not apply, because there is nothing to compete with.

A global node with no `go_back_conditions` has no way home. The call jumps out
mid-flow and cannot return. Everything after that is broken.

Always set a go-back condition unless the global node ends the call.

Give the node a rule so it knows when it is done:

```
After you answer, ask: "Did you have any other questions?"
If no, go back. If yes, keep answering.
```

### A go-back outranks a matching edge on the same global node

**Do not try to steer a global node's exit by adding an edge that competes with
its go-back. The go-back wins.**

Measured on a real conversation-flow agent: The defect: a global node firing while
the caller was still in `Greeting` handed them back to `Greeting`, which
re-read its instruction and replayed the whole greeting. The obvious
structural fix looked like the right one, and lost:

| Fix | What it did | Trace T-AD, 3 reps |
|---|---|---|
| add an edge to the global node, pointing FORWARD to the next real node, with a condition naming the interrupted-greeting case | `Guardrails` and `Human Request` each gained `-> Open Intake` | **0 of 3** |
| put a say-once guard in the interrupted node's own instruction | `Greeting` learns not to say itself twice | 3 of 3 |

The added edge never fired once in three runs. Structure normally beats a
prompt rule in this standard, and here it did not, because the edge never got
the chance to be evaluated.

So when a global node hands a caller back into a node that speaks a fixed
line, fix it in the node that speaks, not in the node that hands back. The
static-text trap below is the same problem in its worst form; this is the
version that bites on ordinary `prompt` nodes too, and it applies to ANY
should-be-said-once line, not just greetings. On the same flow it also hit
`Safety Line 1`, which replayed the 911 sentence after a global took a turn
mid-safety-check, breaking that flow's design guarantee that "the 911 line is
said at most twice, because there are exactly two nodes."

### A global node can PARK a caller, and you cannot rescue it from inside

The rule above says a competing edge loses to the go-back. This is the same
rule at its worst: when the go-back does not fire either, **the caller is stuck
in the global node and the call cannot end.** Retell documents no forced exit.
`docs.retellai.com/build/conversation-flow/global-node` covers the trigger
condition, the go-back, and the re-trigger guard, and says nothing at all about
what happens when none of them match. A parked caller is undefined behaviour.

**The shape to recognise.** A global node whose `else_edge` is `null`, where
every edge condition presupposes progress the caller has not made. Guardrail,
FAQ, and objection nodes drift into this, because their exits get written
against the caller who has already given their details. A caller who gives
NOTHING then satisfies NOTHING.

Measured on a real conversation-flow agent, one real call: The
caller asked for the owner, declined to give a name or a number, and never
described a service need. `collected_dynamic_variables` at hangup:

    current_node : Guardrail Refusals
    previous_node: Human Request

Three node moves in the whole call. The caller then spoke six more times, the
flow never moved again, and the call ended only because the CALLER hung up
after 139 seconds. All six edges on that node needed intake to have happened.

| Fix | Trace T-AO, the real call replayed |
|---|---|
| baseline, no change | 0 of 8 |
| add a seventh edge to the parked global node, for exactly this caller, ordered FIRST, with two transition examples | **0 of 8** |
| route the caller OUT of the previous node, one hop earlier, into a node that already has working exits | **15 of 16** |

The added edge never fired once in eight runs, and the walked path was
identical to the live call every time.

**The rule. Do not fix a parked global node from inside it. Stop the caller
reaching it.** Find the node that hands them in and give THAT node the exit.
Prefer an existing node that already owns the right wording and already has
working exits, over a new escape hatch.

**Two backstops that will not save you, so do not count on them.**

- `end_call_after_silence_ms` only measures silence. A parked caller who keeps
  talking resets it on every turn. It never fired on the call above.
- `max_call_duration_ms` is the real ceiling. On that agent it was 362000, so
  the exposure was six minutes of dead air on a live business line.

**Design rule for every global node.** Ask one question of it: *what does this
node do with a caller who has given me nothing and will give me nothing?*
If no edge answers, the node can park. Either give it an `else_edge`, or make
sure the nodes that hand callers in can route that caller elsewhere first.

Retell's own advice points the same way. Staff on
`community.retellai.com/t/conversation-flow-gets-stuck/833` fixed stuck global
nodes by inserting "an additional conversation node after the global node"
rather than leaning on the go-back. The same thread states the evaluation
order, which is worth knowing when edge order matters: "equation conditions are
evaluated first (top to bottom), then prompt conditions."

### To stop a global node firing, spend a negative example, not more words

Widening the condition's prose does not move the classifier much. A negative
fine-tune example does. Two cases from the same flow, both 0 of 3 before and
3 of 3 after, where the ONLY change was adding two negative examples:

- a second sayer of a contractual sentence firing on a call that had already
  said it upstream
- an urgency trigger firing in the middle of an unconfirmed safety check

In both, a plainly-worded "do NOT trigger when ..." clause was already in the
condition and was already being ignored. See section 8.

### The static-text trap

Never send a go-back edge into a `static_text` node.

The agent will read that fixed line again. A greeting spoken twice destroys the
persona. Point the go-back edge at a `prompt` node instead.

### Cool down

`cool_down` blocks the node from firing again for that many steps. Use it to stop
a global node from grabbing every turn, or to damp a false trigger. Leave it off
when every trigger is genuine.

In the editor this is "Prevent Immediate Re-Trigger", and Retell documents the
default as 3 steps. It exists because a caller whose phrasing keeps matching the
condition will otherwise be pulled back into the node every turn.

Source: `https://docs.retellai.com/build/conversation-flow/global-node`.

a second example agent v29 sets 15, 5, and 10 on its three global nodes; one example agent v51 sets 10 on
Human Request. These are step counts, not seconds.

### A global node only gets a turn after the caller speaks

Retell: "Global nodes are only evaluated after a user turn."

Same source. Two consequences that catch people out:

- A global node cannot rescue a call from silence. Nothing evaluates. Silence is
  handled by the agent settings in section 10, and only by those.
- A global node cannot fire between two nodes the flow walks in one turn. If a
  branch or code node hands straight on, there is no user turn in between and the
  global condition is never checked.

---

## 8. Fine-tune examples

Two node fields:

| Field | Controls |
|---|---|
| `finetune_transition_examples` | Where the agent goes |
| `finetune_conversation_examples` | What the agent says |

This is where routing is made reliable without bloating the prompt. The examples
sit in their own place, so they do not compete with instructions.

### Rules

1. Any node with three or more outgoing edges needs transition examples.
2. Give **four to five minimum** per routing target. More is better.
3. On a global node, give both kinds: when to jump, and when **not** to jump.
4. Spend the examples on the near-misses. Obvious cases route fine on their own.
   The value is in the hair-splitting cases.

Example set for an emergency route:

```
"My house is flooding"           -> Emergency
"There's an active gas smell"    -> Emergency
"Sewage is backing up"           -> Emergency
"My pipes are completely frozen" -> Emergency
"Yeah, I want to book a service" -> do NOT jump
```

### An example outranks the rule it contradicts

If a node instruction says one thing and an example on that node shows another,
the model copies the **example**. Treat every example as an instruction with
more weight than the instruction.

Two consequences, both learned the expensive way:

- **When you change a rule, search for examples that still show the old
  behaviour.** On this project a readback rule was corrected in the global
  prompt and shipped, but two examples still showed the old format. The agent
  kept producing the old format on live calls, and the format flip-flopped
  between calls depending on which text won. Deleting the two stale examples
  fixed it, and removed tokens rather than adding them.
- **Check the `role` on every turn.** An agent line tagged `"role": "user"`
  teaches the model that the caller speaks the agent's lines. Two of these were
  found in one flow.

### A negative example is the strongest tool you have on a global condition

A global node's condition is prose, and prose loses to an example. If a global
node fires when it should not, the fix is a negative example carrying the
context that distinguishes the case, not another sentence in the condition.

Measured 2026-08-25, two independent cases on the same flow, each 3 reps
before and after, with nothing else changed:

| Case | Condition already said | With the clause alone | After 2 negative examples |
|---|---|---|---|
| a global node saying a contractual sentence a second time, on a call where another node had already said it | "Do NOT trigger ... on a call that already went through the safety gate" | 0 of 3 | 3 of 3 |
| an urgency trigger firing mid safety-check | "DEFER to the Roadside / Safety Gate whenever ... a safety check is in progress and unconfirmed" | 0 of 3 | 3 of 3 |

What made the examples work was putting the distinguishing context in the
AGENT turns, not the user turn. The user turn is nearly identical in the fire
and no-fire cases - "I need someone ASAP" either way. What separates them is
what the agent said just before, so the example has to carry it:

```json
{"transcript": [
  {"role": "agent", "content": "Are you and the vehicle in a safe location right now?"},
  {"role": "user",  "content": "I need help right now, ASAP, this is urgent"}
]}
```

### Cover the case the node exists to handle

A global node's positive examples must include its **own headline case**. On
this project the guardrail node owned a whole sales-solicitation track, and its
three positive examples were about arrival times, cars, and whether the agent
was a real person. Not one was a sales pitch. Sales pitches therefore reached an
intake before the refusal fired. Adding three pitch examples fixed it, with no
change to the instruction at all.

When a node has named tracks or cases inside it, give each one at least one
example.

### Cover the shape you do NOT want too

Examples teach a shape, not just a case. If every example on a node shows
"answer, then question", the model will produce a question even on the turn when
the instruction says to ask nothing — because it has never been shown what a
question-free turn looks like.

This happened here. Three examples all showed answer-then-question, and on the
one turn where nothing was left to ask, the agent invented an "anything else"
question that another node had already asked. Rewriting the instruction three
different ways did not stop it.

Whenever a node has a "say nothing / ask nothing / do not add anything" branch,
give that branch its own example.

### Ids must be unique across the WHOLE flow

Retell rejects the entire PATCH with:

```
HTTP 400 {"status":"error","message":"Duplicate example id: fe-cl-finished"}
```

Ids are not scoped per node. Two sibling nodes that make the same decision still
need different ids — suffix them.

A rejected PATCH is **all-or-nothing**: the draft was left completely unchanged,
confirmed by diffing a fresh pull. That is worth knowing before you panic.

Note also that on some flows the **global node** examples
(`positive_finetune_examples`, `negative_finetune_examples`) carry no `id` key at
all, while the per-node ones do. Match the shape already in the file rather than
adding an id.

---

## 9. How a call starts

`conversationFlow.start_speaker` decides the shape. It is the main inbound and
outbound divide.

### Inbound: `start_speaker: "agent"`

19 of 29 templates.

Two nodes, not one:

1. **Greeting node.** `static_text`. Short. One breath. Exits with
   `skip_response_edge` or "after user responds".
2. **Intent router node.** `prompt`. Holds all the routing edges and the
   fine-tune examples.

**Do not merge them.** A node holding a static sentence cannot also hold routing
instructions. There is no room for the routing prompt.

Drop heavy punctuation from a spoken greeting. It sounds more natural in one
breath.

Get intent right at the front. If the flow routes a booking call into the
existing-customer branch, it is very hard to get back. Confirm intent before
branching.

### Outbound: `start_speaker: "user"`

10 of 29 templates. The far side speaks first, because the phone was answered.

The first node is an IVR-navigation or opening component with three exits:

1. A human answered → continue.
2. Voicemail or answering machine → its own path.
3. Could not connect → end.

---

## 10. How a call ends

### Caller silence

Silence is handled on the **agent**, not on the node. There is no node-level
no-input timeout in Retell. Three agent fields do the work:

| Field | What it does | Retell default |
|---|---|---|
| `reminder_trigger_ms` | wait this long after the agent speaks, then prompt again | 10000 |
| `reminder_max_count` | how many reminders before giving up. `0` disables them | 1 |
| `end_call_after_silence_ms` | end the call after this much unbroken silence | 600000 |

Those are the **documented defaults**, from
`https://docs.retellai.com/api-references/create-agent`. Neither example agent below runs
them. The live values, from `agents/*/AGENT-SETTINGS.md`:

| Field | Default | one example agent | a second example agent |
|---|---|---|---|
| `reminder_trigger_ms` | 10000 | 15000 | 15000 |
| `reminder_max_count` | 1 | 2 | 1 |
| `end_call_after_silence_ms` | 600000 | 62000 | 45000 |
| `max_call_duration_ms` | 3600000 | 360000 | 362000 |

**Read that table before quoting a number.** Other files in this repository cite
silence values, and they are not all citing the same thing:
different agents' `tests/TRACES.md` files can quote different live values for the same field. Neither is wrong: they are describing different agents, and neither value is the Retell default.

`agents/*/AGENT-SETTINGS.md` is generated by `agentpull.py` from the live agent
and is the ground truth. Prose in any other file is a snapshot.

Set all three on purpose. Do not inherit the defaults by accident — and note that
Retell's own default of ten minutes of silence is far longer than any of these
agents wants.

**The silence kill can beat your own edges.** A reported case has
`end_call_after_silence_ms` ending the call before a node's no-response edge
fires, so a closing line built into the flow never plays. Source:
`https://community.retellai.com/t/custom-closing-message-on-silence-reminder-loop-ends-call-before-transitions-fire/2704`.
Put the wording you need the caller to hear in the last reminder message as a
backstop.

**`skip_response_edge` is not a silence timeout.** It means "leave as soon as
the agent stops speaking, without waiting for a reply at all". It belongs on a
node that makes a statement, never on a node that asks a question. Putting it
on a question node makes the agent ask and walk away.

**Nothing in the flow can see silence.** No edge evaluates, no global node is
checked, no instruction runs. If the desired behaviour on silence is anything
other than these three fields produce, it cannot be built in the flow. This is
also why no text test can prove silence behaviour — see section 22.

### Bounded retries

**Any loop that can route back into the same question node must have a hard
cap.** Retell has no built-in loop bound, confirmed by
`community.retellai.com/t/conversation-flow-gets-stuck/833`. Build the cap the
way the rest of this standard builds anything that must be deterministic: a
code node returns `String(count)`, and an equation edge routes out when the
count is reached. Never leave it to a prompt telling the model not to loop.

Cap any single question at two or three attempts, then move on, hand off, or
log it and continue. The wider voice-agent convention is three no-match or
no-input events before escalating to a human.

### Rules

1. **Every branch reaches an `end` node.** A dead end leaves the call hanging.
2. The closing line lives in a `conversation` node with a
   `skip_response_edge` into `end`. The agent says goodbye and hangs up. It does
   not wait for the caller to say goodbye back.
3. Ask **"Is there anything else I can help you with?"** on service, support,
   and booking calls. It is standard courtesy.
4. **Skip that question** on a payment, collection, or reminder call. The
   templates close directly once the outcome is clear. Asking there reads as
   pressure.

### Paths that must exist

| Path | Needed because |
|---|---|
| Transfer failed | The other end may not pick up |
| Tool or function failed | The webhook may be down |
| After hours | Nobody is there to transfer to |
| Caller goes silent | The call must not hang open |
| Wrong number | It happens on every line |
| Voicemail reached | Outbound only |

An after-hours path should say the office is closed, take the details, log them,
and promise a follow-up time.

---

## 11. Variables

### Defaults

`default_dynamic_variables` holds sample values. They fill the gaps in testing
and give the flow something to render.

```json
"default_dynamic_variables": {
  "clinic_name": "Retell Health Clinic",
  "balance_amount": "$120"
}
```

Never put a real customer name, real number, or real address in there.

### Extracting

An `extract_dynamic_variables` node names what to pull:

```json
"variables": [
  { "name": "patient_name", "type": "string",  "description": "The patient's full name" },
  { "name": "call_type",    "type": "enum",    "description": "Reason for the call", "choices": ["..."] }
]
```

Types: `string`, `boolean`, `number`, `enum` with `choices`.

Write the description for the model, not for you. It is the only clue the model
gets about what to look for.

Use the raw JSON values `string`, `enum`, `boolean`, `number`. The dashboard
shows them as "Text / Enum / Boolean / Number". The key for an enum's values is
`choices`, and it must not be empty.

**Prefer `enum` over `string` for any value a branch equation reads.** A
free-form string lets the model return a value you never planned for, which then
matches no equation and no code test, and the caller silently takes the wrong
edge. `enum` with `choices` closes that off.

**This node cannot ask a question.** It runs silently on entry and reads what
has already been said. Retell states it "is not intended for having a
conversation with the user". If the caller has not said the thing yet, the node
cannot get it. Source:
`docs.retellai.com/build/conversation-flow/extract-dv-node`.

**Re-entry overwrites.** Every time the node runs it writes every variable it
names, so a value set to `true` earlier can be knocked back down on a later
pass. Retell documents no way to stop this. If a value must survive, guard the
way in with an `exists` equation edge rather than asking the model in the
description to be careful. Source:
`docs.retellai.com/build/single-multi-prompt/extract-dv`.

### System variables

Available with no setup:

| Variable | Holds |
|---|---|
| `{{current_time_<timezone>}}` | Time now, for example `America/los_angeles` |
| `{{current_calendar_<timezone>}}` | A 14-day calendar view |
| `{{from_number}}` / `{{user_number}}` | The caller's number, inbound |
| `{{direction}}` | `inbound` or `outbound` |
| `{{call_id}}` | The call's id |
| `{{session_type}}` | `voice` or `chat` |
| `{{session_duration}}` | How long the call has run |

Put the current time in the global prompt on any flow that touches scheduling or
business hours.

### The hard rule

**A variable may record a judgment. It must never make one.**

"Is the caller safe" is a meaning decision. A node decides it. A variable stores
the answer so later nodes can route on it with an equation.

---

## 12. Inbound versus outbound

The same flow rules apply to both, but the risks are opposite.

| | Inbound | Outbound |
|---|---|---|
| `start_speaker` | `agent` | `user` |
| First node | `static_text` greeting | IVR nav or opening component |
| Who leads | Caller states the need | Agent states the reason |
| Identity | Usually not gated | Must confirm the right person answered, first |
| Private detail | Caller already knows their own business | Say nothing private until identity is verified |
| Wrong person | Wrong-number handler | Relay-message handler. Reveal nothing. |
| Voicemail | Not applicable | Needs its own path and its own script |
| "Are you a robot?" | Rare | Common. Needs a global node. |
| Stop calling | Rare | Must be honored at once and recorded |
| Callback request | Rare | Needs a node. Capture a better time. |
| Close | "Anything else?" | Close as soon as the outcome is clear |
| Call length | As long as it takes | Keep it under two minutes |

### Outbound-only rules

1. **Verify before you reveal.** The Payment Reminder template asks for the
   patient by name, then asks for date of birth, and only then states the
   balance. Never reverse that order.
2. **A third party gets nothing.** If a family member answers, leave a
   call-back request only. No amount. No reason. No account detail.
3. **Voicemail gets nothing sensitive.** Name and callback number only.
4. **Never guilt, never threaten, never pressure.** No "final notice." No
   "immediate action required." No "this will affect your credit."
5. **Answer the robot question honestly.** "I'm an automated assistant calling
   from X." Then offer a human.

---

## 13. Niche rules

Each block lists the hard "never" lines that niche needs. Pulled from the
templates that serve it.

### Healthcare

- Never give medical advice. Deflect and transfer.
- Verify full name plus date of birth before any appointment or medical detail.
- Do not repeat sensitive medical detail more than needed.
- Do not invent appointment slots. Collect a preference instead.
- Route anything that sounds life-threatening to 911 advice at once, then a
  human. Do not triage symptoms.
- Say "911" as "nine one one" so the voice engine reads it correctly.
- A caller acting for a patient, such as a parent, is normal. Record who is
  calling for whom.

### Legal

- Never give legal advice.
- Never quote a statute or a deadline.
- If the caller already has a lawyer, exit the intake at once.
- Never promise a case outcome or a fee.
- Collect facts only: when, where, injuries or damages, was a report filed.
- Route jurisdiction questions to the firm, not to the agent's guess.

### Financial, billing, and collections

- Never threaten legal action, wage garnishment, or credit damage.
- Never use urgency or intimidation wording.
- Never guilt the customer about how long a balance has stood.
- Never repeat the balance more than twice in one call.
- Never share account detail with anyone but the verified customer.
- Never mention a debt on voicemail or to a third party.
- Never misrepresent the amount, who you are, or what happens next.
- Allow a dispute without pushback.
- Honor a request to stop calling at once.
- Never read card numbers aloud. Send a link by text instead.

### Home services and trades

- Never quote a price when price depends on the job. Redirect to a visit.
- Never diagnose the fault over the phone.
- Never promise an arrival time you cannot control.
- Screen for the emergency case first: gas, flooding, no heat, live power.
- Capture the service address carefully. It drives dispatch.

### Sales and outbound qualification

- State who you are and why you called in the first breath.
- Never push back on a "no." One graceful sentence, then end.
- Never ask "are you sure?"
- Qualify, then route or exit. Do not pitch.
- Ask the decision-maker question. It decides the route.
- Anchor the call to the real signal, such as "when you visited our pricing
  page."

### IVR and machine-to-machine

- Use a `press_digit` node, not a spoken guess, when the far side is DTMF.
- List the target menu options in priority order.
- Give a fallback for "none of these options exist."
- Expect to be put on hold. Plan for a long wait.

### Multilingual

- Set `language` to a list, not a single value.
- Keep one flow. Do not duplicate the whole tree per language.
- A language the agent cannot handle is a transfer trigger, not an apology loop.

---

## 14. Laws and rules to account for

This section says what the **flow must do**. It is not legal advice. The client's
own counsel decides the final wording.

| Rule | What the flow must do |
|---|---|
| **HIPAA** — health privacy, US | Verify identity before any health or appointment detail. Say nothing health-related to a third party or on voicemail. |
| **FDCPA** — debt collection, US | No threats. No harassment. No false statements. Allow a dispute. Deliver the required disclosure after identity is confirmed. Say nothing about a debt to a third party. |
| **TCPA** — calling rules, US | Honor a stop-calling request at once and record it. Respect calling hours. Keep proof of consent on the dialing side. |
| **PCI DSS** — card data | Never read a card number aloud. Never store one in a variable or a transcript. Send a payment link instead. |
| **AI disclosure** | Say the agent is automated when asked, and up front where the client or the law requires it. Several US states now require it. |
| **Call recording consent** | One-party consent in most US states. Two-party consent in others, including California. Where two-party applies, the notice must be in the greeting, before anything else. |
| **GDPR / privacy, EU and UK** | Say why you are collecting data. Keep only what is needed. Set `pii_config` to redact. |
| **Do-not-call lists** | Screening happens before the dial, not in the flow. The flow must still honor an in-call request. |

### How this shows up in the JSON

| Field | Use |
|---|---|
| `pii_config` | Set `categories` for the data types this flow touches. Templates use `credit_card`, `bank_account`, `address`, `phone_number`, `ssn`, `passport`. |
| `data_storage_setting` | `everything` by default. Use `basic_attributes_only` on a sensitive flow. |
| `guardrail_config` | `input_topics` and `output_topics`. Blocks the model from going somewhere it must not. |

The standard guardrail set used in the templates:

```
input_topics:  platform_integrity_jailbreaking
output_topics: harassment, self_harm, sexual_exploitation, violence,
               defense_and_national_security, illicit_and_harmful_activity,
               gambling, regulated_professional_advice,
               child_safety_and_exploitation
```

`regulated_professional_advice` is the one that matters most for medical, legal,
and financial flows. Turn it on there.

---

## 15. Settings

### Flow level

| Field | Value seen | Note |
|---|---|---|
| `model_choice` | `{"type": "cascading", "model": "gpt-4.1", "high_priority": false}` | All 29 templates, and both flows here |
| `model_temperature` | **absent from every export in this repo** | Both flows run Retell default. See section 3a before setting it |
| `tool_call_strict_mode` | set | Forces tool arguments to match the schema |
| `kb_config` | `{"top_k": 3, "filter_score": 0.6}` | All 29 templates. A good default. |
| `knowledge_base_ids` | list | Empty unless a KB is attached |
| `flex_mode` | `false` or absent | Never turn it on |
| `begin_after_user_silence_ms` | rare | For a flow that waits |

### Voice and speech, agent level

| Field | What it does |
|---|---|
| `interruption_sensitivity` | How easily the caller can cut in |
| `responsiveness` | How fast the agent replies |
| `enable_dynamic_responsiveness` | Reads the flow of speech. Fast when the caller is done, patient when they pause. |
| `enable_backchannel` + `backchannel_frequency` + `backchannel_words` | The "mm-hmm" while listening |
| `denoising_mode` | `noise-and-background-speech-cancellation` removes both |
| `end_call_after_silence_ms` | Hangs up on dead air. 60000 is one minute. |
| `max_call_duration_ms` | Hard stop |
| `reminder_trigger_ms` + `reminder_max_count` | Nudges a silent caller |
| `voice_speed`, `voice_temperature`, `volume` | Voice shaping |
| `normalize_for_speech` | Turns numbers into spoken words |
| `boosted_keywords` | Helps speech-to-text on names and jargon |
| `stt_mode`, `vocab_specialization` | Speech-to-text tuning |
| `ambient_sound`, `ambient_sound_volume` | Background room tone |
| `voicemail_option` | What to do when voicemail answers |
| `ring_duration_ms`, `begin_message_delay_ms` | Timing |
| `allow_user_dtmf`, `user_dtmf_options`, `allow_dtmf_interruption` | Keypad input |

### Node-level overrides

A conversation flow can override settings per node. A single prompt cannot. This
is one of the real advantages.

Two overrides worth using:

1. **Interruption locked off** on a compliance or disclosure node. The caller
   must not be able to talk over a recording notice.
2. **A cheaper, faster model** on simple nodes, such as capturing a name. It cuts
   latency where the work is easy. Keep the strong model on judgment nodes.

The full per-node override list, verbatim from
`https://docs.retellai.com/build/conversation-flow/conversation-node`:

> "interruption sensitivity (0–1), responsiveness (0–1), voice speed (0.5–2), and
> whether keypad presses can interrupt the agent (DTMF interruption)"

plus a per-node `model_choice` — "a cheaper model for simple routing and a
stronger one for complex steps" — and a node-level knowledge base.

Two naming corrections this document previously got wrong. The field is
`responsiveness`, not "response eagerness". And `high_priority` lives inside
`model_choice`; there is no `model_high_priority` key.

**What is actually set here.** one example agent v51 overrides `interruption_sensitivity`
to 0.2 on two nodes and sets `high_priority: true` on its start node. a second example agent v29
sets no per-node override at all — every one of its 26 conversation nodes carries
an identical copy of the flow-level `model_choice` and nothing else. So the
lever described above is, on a second example agent, entirely unused.

### Post-call analysis

`post_call_analysis_data` is a list of fields to pull after the call.

```json
{ "name": "call_disposition", "type": "enum",
  "description": "Final disposition of the intake call.",
  "choices": ["Transferred", "Scheduled", "Outside Jurisdiction", "Declined"] }
```

Types: `string`, `boolean`, `number`, `enum` with `choices`, and
`system-presets` for the built-in summary, success, and sentiment fields. The
editor labels them Text, Boolean, Number, and Selector.

**It reads the transcript.** Retell: post-call extraction "reads the transcript",
and the order is: the call ends, Retell fires `call_ended`, Retell "analyzes the
transcript against your agent's Post Call Extraction configuration", then Retell
fires `call_analyzed`. So `call_ended` never carries `call_analysis`.

Source: `https://docs.retellai.com/features/post-call-analysis-overview`.

Two things follow, and both have bitten this project:

1. **No documented feature copies a dynamic variable into an analysis field.** A
   field description that says "copy `{{missing_fields}}`" is a strong
   instruction to an LLM reading a transcript, not a guarantee. If the value must
   be exact, have the flow speak it, or read it from
   `collected_dynamic_variables` on the call object instead.
2. **A webhook consumer must listen for `call_analyzed`, not `call_ended`.** See
   [../delivery-protocol.md](../delivery-protocol.md).

`post_call_analysis_data` lives on the **agent**, not the flow. No transform and
no flow lint can see it. Use `agentfields.py`.

Rules:

1. Configure it on every agent. It is the only structured record of the call.
2. Extract what the flow was built to collect. Nothing more.
3. Prefer `enum` over `string` for anything with a fixed set of answers.

---

## 16. Handbook config

`handbook_config` is a set of ready-made prompt blocks Retell can inject.

The nine toggles seen in the templates:

| Toggle | Adds |
|---|---|
| `default_personality` | A general professional persona |
| `natural_filler_words` | "um", "uh" |
| `high_empathy` | Softer, warmer replies |
| `speech_normalization` | Numbers and abbreviations spoken naturally |
| `nato_phonetic_alphabet` | Alpha, Bravo, Charlie spell-back |
| `echo_verification` | Repeats names, numbers, emails for a yes/no |
| `smart_matching` | Treats near-variants of a word as the same |
| `scope_boundaries` | Keeps the agent inside the prompt |
| `ai_disclosure` | Says it is an AI when asked |

### The rule

**Turn a toggle off when your prompt already does that job.**

Each toggle injects prompt text, so each one costs tokens on every turn. Having a
toggle on **and** writing the same rules in your prompt costs you twice and helps
you nothing.

An earlier version of this document put `speech_normalization` at about 450
tokens. That number has no source and could not be reproduced, so it is withdrawn.
The rule stands without it; the way to get a real figure is `llm_token_usage` on
a call with the toggle on and one with it off, per
[../lessons-token-cost.md](../lessons-token-cost.md).

The two most often duplicated are `speech_normalization` and `echo_verification`.

Decide once per flow: prompt or toggle. Never both.

---

## 17. Components

A component is a reusable group of nodes shown as one box on the canvas.

| Type | Lives |
|---|---|
| `local` (agent component) | In this agent only |
| `library` | In your library, across all agents |

Use one when:

- The same group of nodes repeats, such as IVR navigation.
- A node has so many branches that the canvas gets hard to read.

A component holds its own `start_node_id`, its own `nodes`, and exit nodes named
like `Exit Component — Success` and `Exit Component — Failure`.

Warning: a component carries its **own** `flex_mode` flag. Several templates ship
components with `flex_mode: true` inside a rigid flow. Check it.

---

## 18. Speech formatting

The agent is one part of a chain: speech-to-text, then the model, then
text-to-speech. Everything the model writes gets spoken. Format it for the ear.

Put this block in the global prompt of any flow that reads back numbers.

```
Format all output for natural speech.
Money: say "two hundred thirty dollars" not "$230".
Phone: say "eight hundred, five five five, twelve thirty-four".
Dates: say "January fifteenth" not "01/15".
Account references: say each character with a pause. Use NATO letters.
Never read a URL or a payment link aloud. Say you will send it by text.
Use -- between chunks of information for a pause.
Never say a punctuation mark.
Street types: Rd is "Road", St is "Street", Ave is "Avenue",
Dr is "Drive", Blvd is "Boulevard", Ln is "Lane".
Square footage: 2100 is "two thousand one hundred square feet".
```

### Email spell-back

```
The format is name@company.com.
Spell it as n-a-m-e-at-c-o-m-p-a-n-y-dot-com.
Say @ as "at".
Do not spell common providers. Say "at gmail dot com", "at yahoo dot com",
"at hotmail dot com".
```

### Phone numbers

- Read a number back in three groups: area code, prefix, last four.
- A very slight pause between digits. A slightly longer pause between groups.
- Do not slow the whole readback down. Only add the small gaps.
- Never ask a caller to slowly recite a number you already have. Confirm the one
  you have instead.

### Addresses

- Ask for it spoken first.
- If it is clear, confirm once and move on.
- Only if it is unclear, offer to text so they can reply with the spelling.
- Never start with texting by default.

### Confirming

- Confirm anything that could be misheard.
- Never confirm the same item twice.
- Do the full summary once, right before the main action.

### A readback is not verification

A readback only catches an error when the caller objects. A caller who says
nothing, or says "yes" to something else, has confirmed nothing. So a readback
lowers the error rate; it does not prove a field.

Measured on a real call. The agent said the name back twice and stored it
wrong both times:

    User:  My name is Tamsin.
    Agent: Thanks, Tim. And a good callback number?
    Agent: Thanks, Tim. Just to confirm, six two six, seven eight six,
           three two two eight. Is that correct?
    User:  Yes.

The caller's name is Tamsin, with no surname. The "Yes" answers the phone
number, which was right. Nothing in the call answers the name. Four separate
speech systems heard four different things off that one fast utterance, and all
four guessed toward a common English name.

Three rules follow:

- Never bundle two facts into one confirmation. A "yes" to a bundle cannot be
  attributed to either field.
- Ask for the spelling of a name given in under about a second, or of a name
  that is not common in the agent's language. Digits already get grouping and
  pauses for this reason; letters are the same tool for a name.
- Do not raise a confidence field because a readback happened. Count
  corrections, not readbacks.

The full case is in
[docs/lessons-readback-is-not-verification.md](../lessons-readback-is-not-verification.md).

---

## 19. Standard handlers

Every flow needs these. Copy them in.

| Case | Handling |
|---|---|
| "Hold on" / "one second" | Reply exactly `NO_RESPONSE_NEEDED`. A hard-coded Retell stop sequence: response generation halts and the agent says nothing. Without it, the agent keeps talking. See `https://docs.retellai.com/build/no-response`. |
| "How are you?" | Ask it back. "I'm doing alright. How are you?" |
| Hostile or abusive caller | One sentence. "I apologize for the interruption. Have a great day." Then end. Do not engage. |
| Wrong number | "I think you may have the wrong number — this is X. No worries." |
| Solicitor or vendor | "We're not taking solicitations at this number. Thanks though." |
| "Are you a robot?" | Answer honestly. Offer a human. |
| Asks for a human | Do not argue. Do not ask why. Transfer. |
| Transfer fails | "Looks like they're on another call. I'll make sure someone calls you back. Is this the best number?" |
| Tool or function fails | Apologize once, take a callback number, log it, move on. |
| Caller goes silent | A reminder nudge, then end after the silence timer. |
| Caller rambles | Acknowledge once, then redirect with the next question. |
| Not interested | Thank them. One sentence. End. Never "are you sure?" |

### Transfer wording

Be assertive. "Let me connect you with X right now."

Do not ask "Would you like me to transfer you?" Just do it.

---

## 20. Edge cases and conflicts

### Two details disagree

The caller gives a city and a ZIP that do not match. Or a name that is not a
name.

Rules:

1. Ask **one** short neutral question. "Which of those is the vehicle at?"
2. **Never say your guess out loud.** The model has a rough memory of ZIP codes
   and it is sometimes wrong. A confident wrong guess puts bad data in the record
   and sounds certain.
3. Cap the re-asks. Two per call is a good cap.
4. Past the cap, stop asking. Keep what you have. Mark the field uncertain. Flag
   for human review.

Three or more garbled details is a bad phone line, not a capture problem. The
right answer is human review, not more questions.

### Missing versus unclear

These are different and must be recorded differently.

| Label | Means |
|---|---|
| Missing | The caller gave nothing |
| Unclear | The caller answered, but it was not understood confidently |

A field appears in one list or neither. Never both.

Getting this wrong sends a false report. "No address given" when the caller did
give one is worse than saying nothing.

### Caller switches intent mid-call

Use a global intent-classifier node. It picks up the new topic from anywhere.
Without one, the flow drags the caller down the old branch.

### Caller refuses to verify

1. Explain why it is needed. Once.
2. If they still refuse, offer a transfer to a human.
3. If they refuse that too, reveal nothing, close politely, and log it.

### Capture state, not memory

Do not ask the agent to work out at the end of the call what it collected. That
is memory, and memory is unreliable.

Record each required detail as a variable **at the moment it is captured**. Build
the missing list from those records.

---

## 21. Anti-patterns

### Conversation anti-patterns

1. Rambling. A paragraph where one line would do.
2. Stacking questions. Name, email, and date of birth in one breath.
3. Quoting a price that was never approved.
4. Over-qualifying before getting to the point.
5. Re-asking something the caller already said.
6. Robotic transitions. "Thank you for that information. Now I would like to..."
7. Inventing availability instead of checking.
8. Giving advice. "That sounds serious."
9. Refusing to help when it easily could.
10. Missing the close. Ending without confirming.
11. Filler overload. "Absolutely! I'd be more than happy to..."
12. Losing control of a rambling caller.

### Flow anti-patterns

13. **Unguarded double-say.** The same line can be spoken twice on one path. Fix
    it with an equation edge or a structure change. Never with a prompt telling
    the model to check its own transcript.

    **A linter cannot see a double-say that involves a global node.** Any
    double-say check works by walking edges between two sayers, and a global
    node is reached by its trigger condition, not by an inbound edge. So it has
    no inbound edges to walk, and the check reports "no path between two
    sayers" and 0 of 0 paths. That reads exactly like a pass and is not one.
    Found on a real flow: `flowlint.py --line "We are not an
    emergency service, and I can't promise availability or a response time."`
    reported 0 unguarded of 0 paths on a flow that had deliberately just been
    given a SECOND sayer, the global `Guardrail Refusals` node. Both sayers
    were present and the tool was right about the edges; there simply are none.
    Whenever a global node is one of the sayers, the only proof is a trace with
    a `say_times` count, run with `--reps 3`.
    **The chat sandbox is one turn behind a real call, and that invalidates
    any scenario whose real content is in turn 1.** On a real inbound call the
    agent plays the greeting unprompted, so the caller's first utterance lands
    while the flow sits in the greeting node and every global node can see it.
    In a chat sandbox nothing happens until you send something, so YOUR first
    message is what produces the greeting, and its content is effectively
    thrown away. Put a filler "hi" first and start the real scenario on turn 2.
    Measured on a real flow: "I'm on the side of the road,
    there's traffic right next to me" sent as turn 1 produced only the
    greeting and the safety gate never fired, which read as a critical safety
    defect. The identical sentence sent as turn 2, after "hi", fired the gate,
    asked the safety question, and walked the whole roadside chain correctly.
    An adversarial reviewer reported two critical findings that were both this
    artifact and nothing else.

14. **A global node with no way back.**
15. **A go-back edge into a `static_text` node.** The fixed line gets re-read.
16. **A prompt edge where an equation would work.**
17. **A dead end.** A node with no reachable exit.
18. **A dangling edge.** It points at a node id that does not exist.
19. **A multi-equation edge joined with `||` when it needed `&&`.**
20. **A greeting node that also tries to route.**
21. **A variable written and never read**, or read and never written.
22. **A rule in the global prompt that the flow already enforces.**
23. **A `transfer_call` node with no failure path.**
24. **Flex mode on.**
25. **A say-once guard phrased against the CALL, in a design that says the line
    once per NODE.** If two nodes are each meant to say the same sentence once,
    telling each of them "if this has already been said on this call, do not say
    it again" silences the second one. Measured 2026-08-25: a flow deliberately
    says its 911 line twice, once in each of two chained safety nodes. A
    say-once guard added to both took the covering trace from 3 of 3 to **0 of
    3**, because the second node read the first node's line as its own. Phrase
    the guard against the NODE - "if YOU have already said this in THIS node" -
    or do not add it. Better still, fix the cause: the guard was only being
    considered because a global node's go-back was re-entering the node. See
    section 7.
26. **An exact-sentence test used as proof that a message was delivered once.**
    See section 22: the count is blind to paraphrase.

---

### Structural anti-patterns

0. **A numbered label at the start of a line in an instruction.** `Step 2`,
   `(3)`, `PRIORITY 1`, `RULE 2`. Retell documents these as competing with the
   node's transition options, so an edge can fire whose condition never matched.
   It is listed first because it is invisible in every other check: the wiring is
   correct, the lint is clean, and the trace failure looks like a bad edge
   condition. See section 3a and section 4.
1. **Two prompt edges on one node that can both match the same turn.** No
   tie-break exists. The route becomes a coin flip and traces stop repeating.
2. **A loop with no counter.** Any path that can return to the same question
   node needs a code-node counter and an equation edge out.
3. **`skip_response_edge` on a question node.** It means "do not wait for a
   reply", so the agent asks and walks away.
4. **`extract_dynamic_variables` used to ask for something.** It cannot speak.
   It only reads what has already been said.
5. **A branch equation reading a free-form `string`.** Use `enum` with
   `choices` so an unplanned value cannot slip past every edge.
6. **Picking a destination node by its name.** Read what the node does first.
   A node named for one path may set variables that change another. This has
   already cost us once: an intake node pointed at a roadside flag node, which
   stamped ordinary callers as roadside and made them hear the emergency-service
   line.
7. **A value computed on one exit path only.** If a variable feeds the recap,
   every exit that can end a call must set it, or the recap reports nothing on
   exactly the calls that went wrong.
8. **A shortcut edge that skips a builder or a marker node.** An edge that jumps
   straight from mid-flow to a sign-off looks harmless and quietly bypasses
   every code node between. Found on this project: a caller who finished from
   inside a global node jumped to Sign-off, skipping both the closing line and
   the node that computed the recap variable. Route through the builder and let
   it decide, rather than around it.
9. **A rule written in terms of "still missing".** A refused item is still
   missing, so any rule phrased that way will ask for it again. Phrase it as
   "not yet asked", and record a refusal as asked.
10. **An "asked" flag set only after the question is spoken.** The flag then
    answers "have I asked this?", which is not the same question as "has the
    caller already said no?". A caller who volunteers a refusal early, before
    the flow reaches the question, is asked anyway. Capture an explicit refusal
    in the extract node that runs before the gate.
11. **An announcement-only node with an `always_edge`.** See section 6. An
    always edge still needs a caller turn. Use `skip_response_edge`.
12. **An `else_edge` added to a global node that HAS a go-back.** It competes
    with the go-back on every ordinary turn. Widen the go-back instead. On a
    global node with NO go-back, an else edge is the right fix.
13. **A node whose only exits are prompt edges naming conditions the caller has
    no reason to satisfy.** It re-speaks its line every turn. Every node needs
    one exit that cannot fail to match.
14. **A fill-in slot with no empty branch**, such as
    `{always ask next question needed}`. It orders the behaviour on every turn.
15. **A CAPS rule whose exception is four sentences below it.** The loud rule
    wins. State the exit first.
16. **A set of examples that all show the same shape**, when the node has a
    branch that needs the opposite shape. The unshown branch will not happen.
17. **A node adding a goodbye it does not own.** "Take care" one turn before the
    sign-off node says it. Name the owner of every closing line, and ban it
    everywhere else by name.
18. **A question the instruction DESCRIBES instead of QUOTING.**
    "Ask what type of vehicle it is" hands the wording to the model, and the
    model narrows it: after a caller said "box truck" it asked "What type of
    box truck is it?", which re-asked the item and pulled out the year and make
    a roadside call must never request. Every caller-facing question belongs in
    the instruction as a quoted sentence: `Ask exactly, word for word: "..."`.
    In the same flow, the four Ask nodes that quoted their question never
    drifted; only the four that described it did.
19. **The narrowing follow-up.** "What kind of X is it?" after the caller has
    already said X. No rule against re-asking catches this, because the model
    does not believe it is re-asking. Ban it by name in every Ask node.
20. **A node that can be entered with nothing to do.** "If it is already
    answered, say nothing here" stops the re-ask but not the visit, and an
    entered conversation node still holds the caller's turn (see 22). The model
    then has a turn to fill and no question to fill it with, and it invents:
    "Alright.", "Got it, thank you.", "The team will review the information and
    someone will follow up as soon as they are available." Route around the
    node instead. "Say nothing here" is not "do not come here".

    Measured on this project, 2026-08-31, because the prose route was tried
    three separate ways on one node and all three failed:

    | Attempt | Result |
    |---|---|
    | the node's own `# NEVER ask anything else` rules | invents anyway |
    | a "say nothing on re-entry" section placed FIRST | suppressed the node's OWN question, 0 of 5, and still invented |
    | naming the other nodes' items and banning each one | invented a question OUTSIDE the banned list, 4 of 5 |

    The second and third are the instructive ones. Banning the specific
    questions does not produce silence; it only moves the invention somewhere
    you did not think to ban. And a "stay quiet" rule strong enough to be
    obeyed is strong enough to suppress the question the node is FOR.

    So treat "route around the node" as the only fix, not the preferred one. If
    a global node's go-back is what lands the caller there, the go-back cannot
    be steered (anti-pattern 12 and lesson 26), so the node itself has to stop
    being a place the caller can be sent back to with nothing to do.
21. **A closing chain gated on repetition but not on completeness.** The
    closing router asks "have I closed before?" and never "did I collect
    anything?". Every unconditional exit upstream then becomes a way to end the
    call with an empty intake. Found on this project: three exits from two
    global nodes led into a closing chain whose only equation was
    `{{closing_passes}} > 1`, and a real caller reached the goodbye with the
    vehicle, the issue, the address and the urgency never asked. The fix is a
    completeness gate on the way IN to the closing, which means the extract node
    that populates the capture variables has to run BEFORE the branch that reads
    them. The usual arrangement, with the extract downstream of the router,
    leaves every variable at its default at the moment the decision is made, so
    an equation written against them fires on every call including the good ones.
22. **An unconditional `else_edge` pointed at a terminal chain.** An else edge
    carries no condition; it is whatever is left over. Pointing one at a closing,
    a sign-off, or a transfer means every turn the prompt edges fail to claim
    ends the call. It is correct only from a node that genuinely sits at the end
    of its chain. From a global node, which any turn can enter, it is an
    unconditional hang-up wearing a catch-all's clothes. Distinguish this from
    anti-pattern 12, which is about an else edge COMPETING with a go-back; this
    one is about where the else edge POINTS.

## 22. What testing can and cannot prove

### Reading a simulation result

A `simtest` failure is a LEAD, not a finding. The grader sees
`NODE_TRANSITION` entries and will infer speech that never happened: on one run
it failed a call because "the flow transitioned to 'Ask Vehicle', indicating
the agent was about to (or did) ask", when the transcript shows the question
was never spoken. Always pull the run and read the AGENT lines:

```python
d = client.get_test_run(job_id)
for m in d["transcript_snapshot"]["transcript"]:
    print(m["role"], m["content"])
```

Read the WHOLE transcript, not the sentence the grader quoted. On that same
call the grader's complaint was wrong and a different, real defect sat three
lines below it.

### Proving a code node ran and produced the right value

`tracerun.py` prints variables only on a FAILING trace, so a green suite says
nothing about what a code node produced. A simulation run carries it:

```python
d["transcript_snapshot"]["dynamicVariables"]
```

Code nodes also appear in the transcript as `TOOL_CALL_RESULT` entries, in
order. This is the cheapest proof that a builder node fired on the path that
actually ends the call. Do not add a node just to speak the value aloud, and do
not infer it from a passing trace.

### A green verdict is only as wide as its assertions

`say_times` counts the sentences the trace author thought to list. Everything
else on the call is unmeasured, and a passing trace says nothing about it.

Measured on this project, 2026-08-31. A trace asserting that the closing
question was said exactly once passed 3 of 3 on a call where the intake
collapsed four questions early and the goodbye — a line the trace did not
mention — was spoken FIVE times. The assertion it carried was true. The call
was a disaster.

So:

- When a trace goes green, read the transcript anyway, at least once per change.
  `--verbose` exists for this. The verdict tells you about the assertions; only
  the transcript tells you about the call.
- Assert the lines a defect would ADD, not only the line you are protecting.
  Every closing and sign-off line deserves a count, in every trace that reaches
  the close, because a repeated goodbye is the visible symptom of a routing loop.
- Assert completeness, not just wording. A trace that walks an intake should
  assert every question was asked. `say_times` on each question sentence does
  this for free and costs nothing extra to run.
- A trace inherited from an earlier defect is scoped to THAT defect. It does not
  become a general regression test just because it passes.

The failure mode this creates is worse than a red trace, because a red trace
gets investigated. A green one closes the ticket.

### Text testing proves

- Prompt behavior and tone.
- Routing decisions.
- Tool-call decisions.
- Edge case handling.
- Rule compliance.
- Hallucination.
- How many times a line is said.

### Text testing cannot prove

- Voice quality.
- Interruption handling.
- Backchannel timing.
- Speech-to-text accuracy on a real accent or a bad line.
- Background noise handling.
- **A caller going silent.** An empty text turn is still a turn. Silence cannot
  be expressed in text.
- **Whether the agent speaks first.** `create-chat` returns no messages, and
  `begin_message` never arrives as its own turn, so the sandbox cannot show you
  the opening. It is also one turn behind a real call: your first message produces
  the greeting and its content is discarded, which is why the convention here is
  to send a throwaway "hi" first. Recorded in
  [../lessons-retell-api-shapes.md](../lessons-retell-api-shapes.md), which asked
  for it to be stated here.

Anything on the second list must be walked on paper and then confirmed on a real
call.

### Repetitions

A prompt edge is probabilistic. Run it more than once.

**Nine out of ten is a defect, not a pass.**

Escalate sensibly. Do not blindly run ten reps on everything:

```
Run it once.
  Passed  -> done.
  Failed  -> run again.
      Failed again  -> confirmed defect.
      Passed        -> run 3 more, 5 total.
            0-1 fails -> intermittent, note it.
            2+ fails  -> confirmed defect.
```

### The fix ladder

When a node will not follow its instruction, escalate in this order. Stop as soon
as it holds.

1. Add or improve a fine-tune example.
2. Add CAPS and stronger wording to the rule.
3. Add an explicit "NEVER do X."
4. Move the rule to the top of the global prompt.
5. **Change the structure.** Add an equation edge, a branch node, or a dedicated
   node.

Step 5 is the real fix. Steps 1 to 4 make a probability better. Step 5 removes
the probability. Prefer a structural fix whenever one exists.

Retell publishes its own ladder, and it agrees on the ends while adding two rungs
this one does not have. For a node not following its instruction:

> "You can improve consistency by splitting this into three separate nodes" ...
> "If the instructions are concise but the agent struggles to follow them, try
> using a more capable LLM model for this node" ... "To achieve a specific
> response style, add conversation finetune examples" ... "If the agent's
> responses are inconsistent, try adjusting the LLM temperature"

and for a transition not firing as expected: review the condition, add finetune
examples, **remove numbered labels**, add a global node for the edge case, and
make the condition more flexible.

Source: `https://docs.retellai.com/build/conversation-flow/debug-guide`.

Two of theirs are worth adding to ours. **Splitting the node is a structural fix**
and belongs at step 5 alongside the others — it is usually the cheapest one.
**A per-node model or temperature change** is a real lever that this project has
never used; see section 3a and section 15. Neither is in this repository today,
so treat the first use as an experiment with a measured before and after.

And their transition rung has no equivalent here because this document used to
recommend the thing it warns against. If a transition fires without its condition
matching, check the instruction for numbered labels **first**. It is a one-minute
check and it was the answer at least nine times in this repository.

### An exact-sentence count is blind to a paraphrase of the same message

A `say_times` assertion counts a string. It does not check that the MESSAGE was
delivered once. An agent that says the approved sentence once and improvises
the same content in different words somewhere else still passes.

Measured on a real conversation-flow agent: A trace asserted the fleet-focus sentence
exactly once and passed 3 of 3. On a hand-read transcript of the same flow, the
caller heard the message twice:

```
AGENT: We primarily focus on fleet and commercial vehicles, but I'll collect
       your details and pass them to the team for review. Where is your Toyota
       Camry sedan located?          <- improvised, not the approved wording
AGENT: Our primary focus is fleet trucks, trailers, RVs, generators, and
       equipment. I'll send your request to the right person for review.
                                     <- the approved sentence, counted, once
```

The count was correct and the call was wrong. Two consequences:

- A green `say_times` run is evidence about a SENTENCE, never about a topic.
  For anything contractual, read at least one full transcript by hand, or grade
  it with an improvising caller who can judge meaning.
- The same blindness hides a node speaking when it was told to stay silent. Add
  a positive assertion that the node's own scripted question WAS asked, so
  silence and improvisation are both visible.

### Test evidence expires when the flow is edited by hand

Anyone with the Retell UI open can edit the draft while you are testing it, and
nothing warns you. Everything you measured before that edit describes a flow
that no longer exists.

Measured 2026-08-25. A hand reformat of one node's instruction, 1424 to 1478
words, arrived between a snapshot and the next push. It was caught only because
the post-push `flowdiff` showed a change no transform had made. On either side
of that edit, the same trace, same assertion, same harness:

| Flow | Trace T-Z, reps |
|---|---|
| baseline before the session's work | 4 of 5 |
| candidate, built on the pre-edit snapshot | 3 of 3 |
| the real draft, carrying the hand edit | 2 of 5 |

Nothing in the transform explained the drop. The hand edit did.

So: `flowpull` and `flowdiff` immediately before you trust a test result, not
only at the start of the work, and read the diff after every push even when you
are certain what you sent. A push that reports success tells you the PATCH was
accepted, not that the object you tested is the object now on the server.

### Scripted turns and an improvising caller are different tests

Two kinds of behaviour test, and neither replaces the other.

| | Scripted turns | Improvising caller |
|---|---|---|
| What it is | you write every caller line | a persona and success criteria; the platform plays the caller |
| Strongest at | counting how many times a line is said, because a repeat is **counted, not judged** | "did this call actually work" |
| Blind to | anything your script does not think to say | exact counts; it judges |

A scripted caller answers one question per turn, politely, in order. A real
caller says four things in one breath and refuses one of them in passing. On
this project a defect survived a fully green scripted suite and was caught on
the first improvising run: the caller refused an item **before** the flow had
asked for it, which no script produced.

Run both before you believe a change.

### An exact-sentence count proves less than it looks

Counting one sentence proves that sentence was said N times. It does **not**
prove which of a node's several lines came out. A node with a case A line, a
case C line and a routing line can satisfy a count of "routing line = 1" by
never entering case A at all, or fail it by correctly choosing a different case.

Assert the sentence the node actually owns for the path you are testing, and say
in the trace's prose which one that is and why. Anything the agent paraphrases —
an invented question, an improvised goodbye — cannot be counted at all. Read
those in the transcript.

### Read the transcript, not just the verdict

A verdict tells you a case failed. The transcript tells you which node did it,
because the agent's exact sentence usually belongs to exactly one node.

A judge's explanation can also be wrong about **why**. Check it against the
transcript before you change the flow.

### A failing test may be a failing test

Before changing an agent to satisfy a criterion, confirm the criterion is right.
Two ways they go bad:

- **Naming a node that no longer exists.** Rename or retire it. A permanently
  red suite stops telling you anything, which is worse than no suite.
- **Banning a concept instead of a sentence.** "No information was asked for
  twice" reads fine and fails a correct agent, because a required readback looks
  like a second ask. Name the case that does not count, in the criterion itself.

If a test asserts something the platform cannot do — a silent caller reaching a
particular node, for instance — rewrite it to assert what text CAN prove, or
retire the runnable part and keep the written contract for a real call.

### After every change

Both of these, or it is not verified:

- A structure check. Dangling edges, dead ends, unreachable nodes, variable use,
  edge joins, double-say paths.
- A behavior check. Run the traces.

One alone is not evidence.

### When a number moves, get more samples

A change that touches no node on a path can still shift that path's numbers,
because these systems are probabilistic. The temptation is to call it noise.

Do not explain it away and do not push on it. Run the same check on both
versions, several times, and turn the hunch into a number. On this project a
count went 3-of-6 to 6-of-6 after a change that touched nothing on that path;
six runs on each version confirmed it was real, and the release was reshaped to
go out net-better instead of net-worse.

### Test before you push, not after

If your tooling can only test a version already on the server, it is forcing you
to publish a judgement before you have made one.

The way around it: stand up a **throwaway copy** of the mutated flow, and point
the test at the copy. The flow object you are about to push is the flow object
you test. Nothing reaches the real draft until it has passed.

Delete the copy afterwards, every time, including after a crash.

---

## Appendix: template index

The 29 official templates, grouped. Use them as worked examples.

| Niche | Templates |
|---|---|
| Healthcare | Medical Receptionist, Healthcare FAQ, IVR Appointment Scheduling, Insurance Verification Caller, Pre Authorization Support, Provider Office Follow-Up, Pharmacy Refill Caller, Reminder & No-Show Reducer |
| Legal | Legal Intake Screener, Multilingual Law Firm Receptionist, Document Request Caller |
| Finance | Payment Collection, Payment Reminder, IVR Navigation Payment Bot, Mortgage Inbound Form Follow-Up |
| Sales | B2B Demo Qualification, Basic Lead Qualification, High-Intent Lead Screener, Outreach Dialer, Lead Reactivation Campaign, Win-Back Campaign |
| Service | Conversation Flow Agent - Plumbing Client, Service Appointment Booking, Rider Appointment Booking, Delivery Status Caller |
| Other | Multi-Department Router, Event / Webinar Reminder, Windows OS IT Support Triage, Live Call Translator |

Best examples to copy from:

| For | Read |
|---|---|
| Inbound shape | Medical Receptionist |
| Outbound shape | Payment Reminder |
| Compliance wording | Payment Collection |
| Code node and business hours | Conversation Flow Agent - Plumbing Client |
| Subagent with tools | Conversation Flow Agent - Plumbing Client |
| Components and IVR | Insurance Verification Caller |
| Intent routing | Multi-Department Router |
