# Which agent type? Decide this before you write anything

Retell has three types. Picking wrong costs a rebuild, so decide first.

## The short answer

| What you are building | Type |
|---|---|
| FAQ, simple question answering | Single prompt |
| Quick prototype, first version | Single prompt |
| A linear script with clear stages | Single prompt with states, or a flow |
| Agent-led intake with required fields | **Conversation flow** |
| Booking, payment, verification, screening | **Conversation flow** |
| More than three or four conditional paths | **Conversation flow** |
| Five or more tools | **Conversation flow** |
| Tracking several variables through the call | **Conversation flow** |
| A single prompt that behaves inconsistently | **Conversation flow** |
| Production call centre | **Conversation flow** |

## The three types

### Single prompt

One block of prose controls the whole call. `POST /create-retell-llm` with
`general_prompt`.

Good: fastest to build, easiest to read, easiest to change, cheapest to
iterate on. Best for caller-led conversations where the caller decides what
happens next.

Bad: no guarantees. You cannot prove a question was asked. You cannot force
an order. Behaviour drifts as the prompt grows, and past roughly 2,000
tokens it drifts faster.

### Multi prompt (states)

The same object, but with a `states` array and a `starting_state`. Each
state has its own prompt and its own transition rules.

Good for a linear script with distinct phases: greeting, qualification,
scheduling, confirmation. It keeps each phase's prompt short, which is the
whole point.

The honest guidance, from Retell and from practitioners both: once the
stages start branching, a conversation flow is clearer and easier to
maintain. If you find yourself drawing the states on paper, build a flow.

The kit lints multi-prompt agents (`promptlint.py` reads `states`), but has
no dedicated build skill for them. That is deliberate.

### Conversation flow

A graph of nodes and edges. `POST /create-conversation-flow`.

Good: deterministic routing. Branch equations that are true or false, not
probable. A node can be proven reachable. A sentence can be proven to be
said once. Per-node settings such as `interruption_sensitivity`.

Bad: slower to build, more machinery to get wrong, and the machinery starts
producing its own defect class past roughly forty nodes.

## Three things that force a flow

1. **A required field.** If the call is worthless without a callback
   number, prose cannot guarantee it was asked. A node can.
2. **A legal or safety line that must be said, once.** Prose cannot count.
3. **A branch that must be exact.** "If the caller is a returning
   customer" is a branch equation, not a judgement call.

## Cost, and why the argument is not what people think

A turn costs the always-on prompt plus the ONE node you are in. So a
conversation flow does **not** pay for its whole node set on every turn.
Duplicating a paragraph across several nodes is nearly free.

A single prompt pays for the whole prompt on every turn. That is why the
2,000-token guidance bites harder there.

Two size lines matter, and they are different:

- **2,000 tokens** is a quality and latency line. Past it a real-time agent
  is slower and follows instructions less reliably. No extra charge.
- **4,000 tokens** is Retell's billing line. Past it Retell surcharges and
  scales the whole billed duration. A trim here is worth real money.

Below 2,000, a trim buys nothing. Measure with `llm_token_usage` on a real
call. Word counts read at roughly one to one as tokens.

## Switching later

You can. The agent object's `response_engine` is one field. What you cannot
carry across is the testing evidence: traces written against nodes mean
nothing to a prompt, and prompt examples mean nothing to a node graph.

So the cost of switching is the test suite, not the agent.
