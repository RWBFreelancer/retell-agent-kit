# Lesson: what actually makes a Retell call feel slow

Measured 2026-09-03 against every real a second example agent call on version 30 and above
that ran longer than 20 seconds (24 calls, 181 caller-to-agent turns).

Rey's observation was that some calls stall "due to computation or assigning of
variables." The measurement says the second half of that is right and the first
half is wrong, and the difference decides where to spend effort.

## The measurement, and how to repeat it

`transcript_with_tool_calls` on a call object carries a `time_sec` on every
`node_transition`, `tool_call_invocation` and `tool_call_result` entry, and
word-level `start`/`end` on every spoken turn. That is enough to time a flow to
the individual node without any instrumentation:

- dwell in a node = `time_sec` of the transition IN, to `time_sec` of the
  transition OUT
- caller-perceived delay = end of the caller's last word, to the start of the
  agent's next word

Nothing in the Retell dashboard shows this. `latency.e2e` only counts turns the
caller perceived, so a chain of silent nodes is invisible in it.

## What each node type costs

Median dwell, from the 24 calls:

| Node type | n | Median | Max |
|---|---|---|---|
| `code` | 46 | 0.02s | 0.05s |
| `branch` | 32 | 0.01s | 0.05s |
| `extract_dynamic_variables` | 47 | 0.65s | 2.60s |

**A `code` node and a `branch` node are free.** Setting a variable, counting a
pass, evaluating an equation: all of it lands under 50 milliseconds. No amount
of arithmetic in a code node will ever be heard by a caller.

**An `extract_dynamic_variables` node is a full extra LLM round trip.** Confirm
it by counting: `latency.llm.num` tracks `agent turns + extract nodes`, not
agent turns. Calls with zero extract nodes report 4 LLM calls for 3 agent
turns; `call_xxxxxxxxxxxxxxxxxxxxxxxxxxx` reports 19 LLM calls for 15 agent
turns and 3 extract nodes.

So the rule is not "avoid computation." It is: **variables assigned by code are
free, variables assigned by extraction are charged at LLM latency, once each,
every time the node is crossed.**

## The costs stack, and nothing speaks while they do

| Turn shape | n | Median delay |
|---|---|---|
| no transition, agent stays in node | 47 | 1.25s |
| one hop, no extract | 89 | 1.74s |
| one extract node crossed | 41 | 3.33s |
| closing chain, 4 or more hops | 15 | 4.01s |

a second example agent's closing chain is six nodes deep — `Gate Pass Counter` (code),
`Intake Gate Check` (extract), `Intake Gate Router` (branch),
`Closing Pass Counter` (code), `Closing Router` (branch), then the spoken node.
The full goodbye chain reaches nine hops and three extract nodes. Worst turns
measured: 7.24s into `Closing / Anything Else`, 5.51s into `Sign-off & Goodbye`
(`call_xxxxxxxxxxxxxxxxxxxxxxxxxxx`).

Every one of those nodes is silent. `ambient_sound` is `coffee-shop`, so what
the caller gets for four to seven seconds is café noise and no voice. It reads
as a dropped line, not as thinking, and the calls where it happens are the two
moments the agent most needs the caller to stay: confirming the intake and
saying goodbye.

## The larger slice is not the chain at all

Splitting the delay three ways — caller stops speaking, first node transition
is logged, last node transition is logged, agent's first word:

| Slice | Median | p90 | Max |
|---|---|---|---|
| think (before any transition) | 1.64s | 2.69s | 4.13s |
| compute (the whole node chain) | 0.00s | 0.92s | 2.67s |
| speak (last transition to first word) | 0.32s | 0.95s | 3.33s |

The routing LLM deciding which edge to take costs more than the entire node
chain it then walks. Turns with **one hop and no tool call at all** still reach
4.18s (`Ask Urgency`) and 3.86s (`Ask Problem`). Trimming nodes cannot fix
those; only fewer or cheaper edge decisions can.

## What this changes

- Never argue for merging `code` or `branch` nodes on latency grounds. They
  cost nothing. `docs/lessons-v24-simplification.md` gives real reasons to
  merge them; speed is not one.
- Do argue about `extract_dynamic_variables`. Each one on a caller-facing path
  is roughly 0.65s of silence, and two on the same path is roughly 1.3s.
- Before blaming the flow for a slow call, split the delay. If `think` is the
  large slice, the fix is the edge set on the node the caller was in, not the
  chain after it.
- A silent chain longer than about two seconds needs something audible in front
  of it, or it needs to move off the caller-facing path.

## Unrelated fault the same measurement exposed

`call_xxxxxxxxxxxxxxxxxxxxxxxxxxx`, at 73.8s: the agent said "Thanks, the caller."
and then nothing. No transition, no tool call. 16.3 seconds later
`reminder_trigger_ms` (15000) fired with "Are you still there, the caller?" The
agent produced an acknowledgement turn and dropped the question that was
supposed to follow it. That is a dead-end turn, not latency, and no latency
metric would ever surface it.
