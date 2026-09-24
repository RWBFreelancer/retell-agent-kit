# A decider that can speak will speak

Measured 2026-09-04, `--model gpt-4.1`, 5 reps each, same trace `T-AL`.

| Agent | Result |
|---|---|
| one example agent v53 | **5 of 5 PASS** |
| a second example agent v36 | 3 of 5, and the passes hide paraphrases of the same defect |

`T-AL` is the client's own rule from `prd/plan-confirmation-and-uncertain-fields.md`
Step 5 Test 2: on an ordinary call the agent reads back nothing but the phone
number. a second example agent repeats the caller's vehicle back at them. one example agent does not.

Rey called it before the measurement: "it determines call type better in my
opinion."

## Difference one. one example agent's decider is a branch, so it has no voice

`Call Type Router` (`node-1783002296846`) is a **branch** node. A branch has no
instruction and takes no turn. It reads five prompt conditions and routes:
existing customer, service, sales pitch, vendor, or asking for a person.

A branch cannot leak its reasoning into the caller's ear, because it cannot
speak at all. The decision is structurally silent.

a second example agent's equivalent, `Call Type Check`, is an `extract_dynamic_variables`
node. It computes `call_type` with three allowed values, and then:

    "edges": []
    "else_edge" -> node-text-permission

One destination, whatever the answer. The only place `{{call_type}}` routes
anything is a single equation edge on `Text Permission`, `e-tp-existing`,
testing `== existing_customer`. So `new_service` and `non_service` are both
computed and thrown away, and a `non_service` caller who reaches that point is
sent to `Ask Vehicle` and asked "What kind of vehicle or equipment are you
calling about?"

**The rule.** If a node's job is to DECIDE, give it no voice. A branch decides
and is silent. A conversation node that decides will, on some fraction of
calls, say its decision out loud as a question.

**The second rule.** A value you extract and do not route on is not a decision,
it is a note. a second example agent pays a full LLM round trip for `call_type` and acts on
one of its three values.

## Difference two. one example agent has one intake node, so it is never empty-handed

one example agent's `Service Request Intake` owns all four items: vehicle, issue,
location, urgency. It is entered only when something is missing, and it holds
every question, so it always has something to ask. Its instruction closes the
loop explicitly:

    If there is no question, go transition to the next node.

a second example agent splits the same four items across four nodes, chained directly to each
other. Each node owns ONE item, and each can be entered on a caller who already
gave that item. Then the node has nothing to say, no silent exit, and a caller
waiting. It invents a question, usually the next node's, with the caller's own
words folded in.

**The rule.** A node that owns exactly one question can be entered with nothing
to ask. Either it must be unreachable when its item is already answered, or it
must own enough questions that it is never empty-handed. one example agent took the
second route. a second example agent has the machinery for the first, `Intake Gate Check`, and
one path skips it.

This is the same failure as the Naomi re-ask in
[lessons-open-intake-reask.md](lessons-open-intake-reask.md), found the same
day in a different node: **a node with nothing to say and no matching exit
invents a turn.**

## Where one example agent is NOT better

Do not read this as "copy one example agent".

- one example agent carries the defect behind root `CLAUDE.md` hard rule 7: intake nodes
  were wired to `Roadside Flag -> Incomplete Exit`, whose code sets
  `roadside_gate_visited = "true"`, so ordinary callers were stamped roadside
  and heard the emergency-service line. a second example agent has no equivalent trap.
- One big intake node is charged on every intake turn.
  [lessons-token-cost.md](lessons-token-cost.md): a turn costs always-on plus
  the ONE node you are in. a second example agent's small per-item nodes are cheaper per turn,
  which is the whole reason they were split.

The lesson is not the node count. It is that a decider must be silent, and an
asker must never be entered empty-handed.

## Postscript, same day: fixing the node moved the defect one node upstream

`b_v40_text_permission_via_gate` + `b_v41_call_type_router` were built and
measured, `--model gpt-4.1`, 5 reps, twice.

The routing works exactly as designed. On a caller who opens with "Sprinter van
with a coolant leak", `Ask Vehicle` is now skipped and `Ask Location` runs and
speaks the client's approved sentence word for word, which had never happened on
a second example agent for this caller:

    -> Text Permission -> Intake Gate Check -> Intake Gate Router -> Ask Location
    AGENT: What's the address and ZIP code? If you don't have the exact
           address, the nearest cross streets are fine.

`Ask Vehicle` stopped inventing. And `T-AL` still failed, on a new line, from a
different node:

    -> Text Permission
    AGENT: Got it, thank you. Can you tell me where the Sprinter van is
           located, including the ZIP code?

`Text Permission` decided the caller had volunteered text permission, which
they had not. Its `# BEFORE ASKING` rule then tells it to say "Got it, thank
you." and move on. That leaves a turn with no question in it. So it bolted the
next question on, with the vehicle in it.

The node names this exact trap, in its own text, and does it anyway:

    Bolting one onto the acknowledgement gives the caller a turn with no
    question in it, which stalls the call.

**Third instance in one day, in three different nodes**: `Open Intake` (the
Naomi re-ask), `Ask Vehicle` (the Sprinter readback), and now `Text
Permission`. One disease:

> A node that can reach a state with nothing to say, and must still take a
> turn, will invent one. No amount of prose in that node prevents it. The node
> usually already forbids it in writing.

The cure is never a rule. It is either not entering the node in that state, or
giving it a silent exit. `b_v40` proved the first works, on the node it
covered. Every node that can run dry needs the same treatment, and the flow has
at least three.

`Text Permission` cannot be fixed the same way yet: `Intake Gate Check` tracks
vehicle, issue, location and urgency, and text permission is not one of its
`gate_next` choices. Adding it is the next piece of work, not a free one.

## The defect does not get fixed. It relocates.

Full measurement, 2026-09-04, a second example agent v36 draft, `--model gpt-4.1`, 5 reps per
cell. `T-AL` asserts the agent never says "Sprinter"; `T-W` asserts all four
intake questions are asked once each and the call reaches the goodbye.

| Candidate | What it changed | T-AL | T-W |
|---|---|---|---|
| baseline v36 | nothing | 3/5 | 3/5 |
| `b_v38` | 12 edge conditions stop reading as commands | 2/5 | 4/5 |
| `b_v39` | drop the fine-tune turn that performs the defect | 3/5 | 2/5 |
| `b_v40`+`b_v41` | Text Permission routes through the gate; silent Call Type Router | 3/5, 3/5 | 2/5, 5/5 |
| `+b_v42` | the gate owns text permission too | 2/5 | 3/5 |
| `+b_v43` | a readback yes is not text consent | 3/5, 1/5 | 5/5 |

`T-W` improved and holds at 5/5 on the full stack. `T-AL` never moved, on any
candidate, in six attempts.

It never moved because **each fix moved the defect to the next node**:

| After | Who invented a question |
|---|---|
| baseline | `Ask Vehicle` said the location question, naming the van |
| `b_v40` | `Text Permission` said the location question, naming the van |
| `b_v43` | `Ask Problem` said the location question; `Ask Location` said the urgency question, naming the van |

The final transcript shows the whole chain running one node behind:

    -> Ask Problem    AGENT: Where is the vehicle located right now?
    -> Ask Location   AGENT: How soon do you need help with the Sprinter van?

Each node was entered with its own item already answered, had nothing to ask,
owed the caller a turn, and reached for the next node's question.

**The rule, and it is the expensive one.** Routing around a node that can run
dry only moves the problem to whichever node the router picks next, because the
router is an LLM judgement too. `Intake Gate Check` skipped `Ask Vehicle`
correctly and then named `ask_problem` on a caller who had said "coolant leak".
A better gate raises the pass rate. It cannot remove the failure, because there
is no gate reading that makes an empty-handed node safe.

**What actually removes it** is the shape one example agent already has: ONE intake node
owning every item, entered only while something is missing, so an empty-handed
entry is impossible. one example agent scores 5 of 5 on `T-AL`. a second example agent has scored 3 of 5
on every one of six candidates.

The four-node split was deliberate and it is cheaper per turn
([lessons-token-cost.md](lessons-token-cost.md)). That saving is what is paying
for this defect.

---

## Deleting a node deletes spoken lines, and nothing in the toolchain notices

Found 2026-09-05 by Rey, on live web call `call_xxxxxxxxxxxxxxxxxxxxxxxxxxx`:
"it did not ask the truck model. why?"

`b_v44_merge_intake_into_one_node.py` replaced four nodes with one and its
docstring claimed "Every spoken line is a second example agent's, word for word, unchanged",
then listed seven. The list was incomplete. Two caller-facing questions lived
inside a `# RULES` prose paragraph on `Ask Vehicle`, not under a `# QUESTION`
header, and neither survived:

    "And what's the year and make?"
    "Is it truck-mounted or a standalone unit?"

The merge was reviewed by reading the four `# QUESTION` blocks. Both lines sat
outside them. the client's recap then reached him with `year_make_model_unit` blank
on a truck he was expected to send a technician to.

`flowlint` is blind to this. It checks edges, dead ends, unreachable nodes and
variables. **No tool in this repository notices that a spoken sentence stopped
existing.** The lint was CLEAN on every build that had lost them.

**The rule.** When a transform DELETES a node, diff the deleted instruction
text against the replacement SENTENCE BY SENTENCE, before pushing. Not header
by header. This takes seconds:

```python
import json, re
pre  = json.load(open('exports/<before>.json'))
post = json.load(open('exports/<after>.json'))
new  = ' '.join(next(n for n in post['nodes'] if n['id']=='<new>')['instruction']['text'].split())
for nid in ['<deleted>', ...]:
    old = next(n for n in pre['nodes'] if n['id']==nid)['instruction']['text']
    for s in re.split(r'(?<=[.?!]) +', old.replace('\n',' ')):
        if len(s) > 25 and ' '.join(s.split())[:60] not in new:
            print(nid, '|', s[:160])
```

Read every hit. Most will be rewordings you meant. The ones in quotation marks
are spoken lines, and those are hard rule 1 territory.

**The second rule, which cost three attempts.** Restoring the sentence where it
used to live did NOT work, 0 of 5. The merged node's loop is "find the FIRST
item on the list that is not finished, ask that item's question". Year and make
was not ON the list, so that section was never read once "truck" had finished
the vehicle item. Adding it as a listed item made it fire - and fire 4 times a
call, 1 of 5, because the model read "asked once" as satisfied only when the
caller ANSWERS. Only an explicit override in the same paragraph held it:

    ASK IT ONCE ONLY. The moment you have asked it, this item is FINISHED,
    whatever came back ... Asking it a second time is a defect, however little
    the caller gave you.

Identical to the vehicle make rule the day before. **A rule stated once at the
top of a node does not govern a paragraph further down.** Put the override in
the paragraph it guards, every time.

**The third rule, about the trace.** `T-AT` reproduces the real call turn for
turn, and the real call never heard the restored question, so it has no answer
to it. Adding the question shifted every later turn and the transcribed answers
landed on the wrong questions - the trace measured turn alignment, not the
agent. One realistic turn had to be added. **A trace copied from a call that
predates the fix cannot test the fix without one.**

---

## CORRECTION, 2026-09-05. The headline table above is ONE SAMPLE, not a grade.

`T-AL` was re-run the next day, `--model gpt-4.1`, 5 reps, on the live drafts.

| Agent | Flow | 2026-09-04 | 2026-09-05 |
|---|---|---|---|
| one example agent | v53 | 5 of 5 | **3 of 5** |
| a second example agent | v38 | 3 of 5 (on v36) | **5 of 5** |

**one example agent's flow did not change between the two runs.** `flowdiff.py` on
`exports/v53-reviewA.json` against a fresh `exports/v53-drift.json` reports no
change at all: same nodes, same edges, same variables, same version. Same
trace, same model, same rep count. 5 of 5 one day, 3 of 5 the next.

The two failures on 2026-09-05:

    rep 3: said 1x (wanted 0x): 'Sprinter'
    rep 5: said 2x (wanted 1x): 'Can we text you at that number...'

a second example agent's side of the change IS real: `b_v41_call_type_router.py` and
`b_v45_router_owns_existing_customer.py` gave B a real `Call Type Router`
branch, and `b_v44_merge_intake_into_one_node.py` collapsed B's four Ask nodes
into one `Service Intake` node. Both rules below were acted on, and both fixes
landed. What is NOT supported is the number 5 of 5 as a property of one example agent.

**The rule.** A 5-rep run is a sample of a weighted coin, not a grade. Never
quote one 5-rep run as a verdict about an agent, in a changelog, in a lessons
file, or to Rey. `qa-checklist.md` B6f and I12 already said sample before
believing; this is the case that proves the cost of not doing it. Two days of
work were planned around a number that was noise.

**What to do instead.** Run the comparison twice on different days, or at 10
reps, and report the range. If two agents land inside a rep or two of each
other, say they are not separated by this trace.

**The two design rules in this file still stand.** A branch decides silently
and a conversation node that decides will sometimes speak its decision; and a
node owning exactly one question can be entered with nothing to ask. Those were
reasoned from the flow structure and from real transcripts, not from the rep
count. They are why B was changed, and the changes held.
