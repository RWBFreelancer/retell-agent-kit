# The re-ask loop, and the recap that says nothing is missing

Evidence: a second example agent v34, `call_xxxxxxxxxxxxxxxxxxxxxxxxxxx`, 2026-09-03 21:37 UTC.
the client reported it by email on 2026-09-04.

## What the caller heard

The agent took the name, took the callback number, read it back, and got a
"Yes". It then asked the reason twice. The caller said "No. It's just personal.
Leave a message." The agent answered:

    Understood. Just to confirm, could I get your name and a good callback number?

It asked again for two things it already had. The caller hung up.

## Why it happened

`node-open-intake` carries a scripted second-attempt sentence under
`# IF THE CALLER WILL NOT GIVE A NAME OR NUMBER`, with the exact words above.
Nothing in the node gates that sentence on the name or the number actually being
missing. The node's `NEVER` block does say "Never re-ask anything already
given", but a rule loses to a sentence written out in full. That is the
`docs/lessons-v22-overhaul.md` finding: an example outranks the rule it
contradicts.

The node also had nowhere to go. None of its five edges matches "the caller has
name and number, refuses to state a reason, and wants to leave a personal
message". `e-oi-2` reads as a sales, robocall or business matter. Retell's
transition order ends in **stay** when no edge matches
(`/build/conversation-flow/transition-condition`). Staying means taking another
turn, and the node must end every turn with a question, so the model reached for
the most concrete question in the text.

**The rule.** A scripted sentence written out in full inside a node will fire on
a near-miss. Guard the sentence itself with its precondition, in the same
paragraph. Do not rely on a `NEVER` block further down the node.

**The second rule.** A node whose instruction says "every turn must end with a
question" must have an edge for every way the caller can stop cooperating.
A missing edge does not stall quietly; it makes the node improvise a question.

## The recap said the opposite of the truth

The same call's recap email to the client read:

    Incomplete Intake: false
    Missing Required Fields: None
    Unclear Details (confirm on callback): None

Retell's own post-call analysis on that call said `incomplete_intake` true and
listed seven missing fields. The call ended inside `Open Intake`, so
`Capture Check` and `Recap Lists` never ran and the flow variables were never
set. `collected_dynamic_variables` on the call proves it: `current_node` is
`Open Intake`.

This is root `CLAUDE.md` hard rule 8 with a real casualty. A hang-up inside an
intake node is an exit. On exactly the call that collected the least, the recap
told the client nothing was missing.

**The rule.** Before trusting an empty `missing_fields` or `uncertain_fields`,
read `collected_dynamic_variables.current_node` on the call. If it is not a node
past `Capture Check`, the list is empty because it was never written, not
because the call was clean. An empty list from a node that never ran looks
identical to a clean call.

This also corrects a claim made to the downstream owner on 2026-09-04: Naomi does **not**
show that the v32 `uncertain_fields` boundary fix failed. Her Capture Check
never ran.

## 2026-09-11: never say who ended a call without reading both fields

Diagnosing n8n execution 1323, `call_xxxxxxxxxxxxxxxxxxxxxxxxxxx` on v38, the
transcript ended like this:

    User:  I need a scan on my pickup truck. I think it's a fuse.
    User:  don't I'm not sure, but I'd be interested in talking to him.
    Agent: Got it. The team will call you back as soon as they're next available.
    [call ends]

Read on its own, that looks like the agent wrapping up and closing the call
early, before it had asked where the vehicle was. That is what was reported
first, and it was **wrong**.

Two fields on the call object settle it, and they must be read together:

| Field | Value | What it says |
|---|---|---|
| `disconnection_reason` | `user_hangup` | the CALLER ended it, not the agent |
| `collected_dynamic_variables.current_node` | `Human Request` | the node the call died in |
| `collected_dynamic_variables.previous_node` | `Text Permission` | where it came from |
| `collected_dynamic_variables.gate_next` | `ask_text_permission` | what the flow still wanted to ask |
| `collected_dynamic_variables.closing_line_said` | `no` | the closing was NEVER said |

So the agent never closed anything. The caller asked to speak to a human, the
global `Human Request` node answered with the callback line, and the caller
hung up on the back of it. The flow was still mid-intake with text permission,
location and urgency all unasked.

**The rule.** `disconnection_reason` alone says WHO hung up. It does not say
whether the agent had finished. A call can read `user_hangup` on a caller who
was perfectly happy, and on a caller the agent abandoned. Read
`current_node`, `previous_node` and any say-once marker such as
`closing_line_said` beside it, and only then say what happened.

**The reverse trap.** `agent_hangup` does not prove the agent finished either.
It proves the agent ended the call, which it can do from a guardrail or a
disconnect edge in the middle of an intake.

**Where to read them.** From Retell, `callreview.py --call <id>`. From an n8n
execution, they are inside the webhook body:
`data.resultData.runData['Retell call_analyzed'][0].data.main[0][0].json.body.call`.

**A second thing that call showed.** The callback number readback burned five
turns of a ninety second call, and the intake never recovered the time. That is
the cost of a readback measured on a real call, and it belongs beside
[lessons-readback-is-not-verification.md](lessons-readback-is-not-verification.md).
