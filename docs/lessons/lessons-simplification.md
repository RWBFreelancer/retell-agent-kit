# Lessons from simplifying an over-grown flow

2026-08-24. a second example agent went from 63 nodes to 27, from 23 code nodes to 1, from 10
branch nodes to 1, from 4 extract nodes to 0, and from 32 dynamic variables
to 1.

Read `docs/lessons-v22-overhaul.md` and `docs/lessons-v23-live-call-defects.md`
first. Every defect they record is real and none of it is withdrawn here. This
file is about what happened when all those fixes were added together.

## The finding

**Nineteen correct fixes can add up to a wrong flow.**

Each v21, v22 and v23 transform fixed a defect a real call had shown. Each was
verified. None was a mistake. But the shape they produced had properties nobody
chose:

| Defect that only exists because of the machinery | Where it is recorded |
|---|---|
| A flag written on the way out of a node is lost when a global node steals the turn | v23 lessons 2 and 7 |
| A three-value enum with edges for two values drops the caller out of the loop | v23 lesson 7, second pass |
| A gate loop closed a call in the middle of the question it had just asked | v23 lesson 7, second pass |
| A shortcut edge that skips the recap builder empties the recap | v23 lesson 8 |

None of these can happen in an 11-node flow with no variables. They are the
cost of the cure, and by v23 the cure cost more than the disease.

**The rule.** Count the defects a mechanism prevents against the defects it
creates. Re-count after every third fix that uses it. A mechanism that has
started producing its own defect class is finished, whatever it was fixing.

## The four structural swaps

Each one gives the same guarantee with no state to lose.

### 1. One line, one node, one door

The emergency-service sentence used to be owned by prompt rules in several
nodes, then by `emergency_line_said` plus four flag code nodes plus two
routers. v24 gives it a node, `Roadside Line`, and routes every roadside path
through it exactly once.

Nothing to flag means nothing to lose. This is PRD principle 2, "a node that
speaks one sentence cannot be outvoted", taken to its end: if there is one door,
you do not need a lock.

**The rule.** Before adding a flag that records "has this line been said",
check whether the paths can be made to funnel through one node instead. A funnel
beats a flag, because a global node cannot steal a node out of a path.

### 2. Two nodes instead of a counter

`Safety Line Counter` (code) plus `Safety Branch` (equation on
`safety_line_count < "3"`) capped the 911 line at two. It was also off by one:
the equation allowed three, and `Safety Cap Reached` said "already been said
twice".

v24 chains `Safety Line 1` to `Safety Line 2`. Two nodes, two says, and the
count cannot disagree with the copy because there is no count.

**The rule.** A counter whose maximum is 2 or 3 is a chain of nodes written the
hard way. Use a counter only when the bound is larger than about four, or when
the loop body genuinely repeats.

### 3. A second exit instead of a guard variable

`incomplete_exit` plus `Sign-off Return Gate` plus a stop edge on
`Closing Router` existed to stop a call closed as incomplete from re-entering
Closing. v24 adds `Sign-off (Incomplete)`, a second goodbye node whose only
exit is End Call.

A call that reaches it physically cannot get back to Closing. There is no
equation to be wrong about.

**The rule.** When a variable exists only to say "you came from over there",
give "over there" its own exit node instead.

### 4. The line gets its own node, reached by an edge from the node that asked

`vehicle_is_passenger` was extracted once, read by `Passenger Vehicle Gate`,
and gated by `cars_line_said`. On two live calls the caller named the vehicle
one question after the extract ran, so the fleet-focus line was never said.

**The first v24 attempt was wrong, and trace T-Q caught it.** It deleted the
gate and the variable and put the line in `Ask Vehicle`'s own instruction:
"if the caller names a passenger car, say this line". T-Q failed 0 of 1, then
0 of 2 after a rewrite. The line was never spoken.

The reason is a property of Retell, not of the wording. **An Ask node speaks
once, on the turn it asks. The caller's answer arrives on the NEXT turn, and
that turn is spent taking an edge.** The node never gets a second turn in which
to react to what it just heard. So no instruction of the form "if the caller
says X, say Y" can ever fire inside the node that asked.

v24 gives the line its own node, `Passenger Car Line`, reached by an edge out
of `Ask Vehicle` whose condition is "the caller has named a passenger car". Its
whole instruction is that one sentence. A `skip_response_edge` chains it into
`Ask Problem`, so the caller hears the line and the next question in one turn
and no turn is wasted.

**The rule.** A spoken line that depends on what the caller just said cannot
live in the node that asked. It needs its own node and an edge. This is the
same shape as the v22 roadside double-say fix, and the same fix: one line, one
node. The v23 architecture had this right; what was wrong with v23 was the
variable feeding the gate, not the gate's existence.

### 5. A punctuation mismatch is a failed assertion, not a cosmetic one

The new node first said "...to review," with a trailing comma, copied from the
reference table in `tests/conductor-test-cases.md`. The trace asserts a full
stop. T-Q failed 0 of 2 with the node plainly on the walked path.

The comma is a leftover from v19, where the line ran on into the next question
inside one big node. Once the sentence stands alone, a full stop is correct,
and it is what the v23 node actually shipped. Both files now say full stop.

**The rule.** When a line moves into its own node, re-read its punctuation. A
reference table can be a record of where the line used to live.

## What did NOT get removed, and why

`Closing Pass Counter` (code) and `Closing Router` (branch), and the one
variable `closing_passes`.

Lesson 2 from v23: the Guardrail global node takes the turn out of the Closing
node, and its go-back returns the caller **to that same node**, which reads its
instruction again and asks the anything-else line a second time.

No structural swap helps here, because the destination is the node itself. You
cannot funnel a node away from itself. Counting arrivals is the only tool left.

**The rule.** Structure beats state everywhere except one place: when a global
node's go-back returns the caller to a node that must not repeat itself. That
is the only case in this flow that earns a counter.

## The router that could not exist

The obvious way to collect four intake items is a router node: it reads what is
missing and sends the caller to the right Ask node, which comes back when done.
That is what the reference agent `agent_xxxxxxxxxxxxxxxxxxxxxxxxxx` looks like,
and it is what Rey asked for.

It cannot be built here without a cost. A Retell `conversation` node that speaks
nothing still holds the caller's turn (v23 lesson 8, measured). A routing-only
node would therefore burn a caller turn on every pass. The zero-turn router is
the `branch` node, and a branch needs equations, and equations need the extract
nodes and variables this rebuild is removing.

v24 spreads the router across the Ask nodes instead. Every Ask node carries an
edge to every other item, worded as "this item has not been given and has not
been asked; go here". The routing decision happens on the edge out of a node
that already spoke, so it costs no turn.

**The rule.** In a Retell flow there are exactly two zero-turn routers: a
`branch` node, which needs variables, and the edges leaving a node that already
spoke. If you will not have variables, the edges are your router.

**The bonus.** This is also the fix for v23 lesson 7. The next question is
chosen fresh on every pass from the conversation itself, so a global node
stealing a turn cannot lose an item. The old gate lost the item because the
marker was written on the way out.

## The cost, stated honestly

`missing_required_fields` goes back to post-call analysis reading the whole
transcript. That is PRD goal G2 given up. The PRD built the runtime builder
because one recap wrongly reported an address as not provided.

Watch the first five live calls after publish. If it is wrong again, the builder
comes back as ONE code node at `Closing Pass Counter`, which every path already
passes through, and not as the fourteen nodes it took in v23.

**The rule.** When you remove a mechanism, write down the single place it would
come back, and how small it would be. A removal with no named return path is a
bet, not a decision.

## What made this safe to do at all

- **The inverse round-trips byte-for-byte.** `b_v24_rebuild_inverse.py` reads
  the whole v23 state from `b_v24_rebuild_original.json` and restores it.
  `json.dumps(..., sort_keys=True)` equality was checked before anything was
  pushed.
- **Every contractual sentence was moved, never retyped.** They were lifted out
  of the v23 export by script.
- **`flowlint.py --line` was run for all nineteen contractual sentences.**
  Every one has exactly one sayer, except the 911 line and its re-ask, which
  have two by design, because trace T-C requires exactly two.

**The rule.** A rebuild is safe in exactly the proportion that its reversal is
proven. Prove the reversal first, before the first push, not after.

---

# What the trace suite found, 2026-08-24

The rebuild linted CLEAN on the first dry run and was still wrong in four
places. All four were found by `tracerun.py`, none by `flowlint.py`.

## Lesson 6 - a give-up edge must name what is NOT a give-up

First run of T-W: the caller answered the vehicle question with "I'd rather not
say" and the call ENDED. Path: `Ask Vehicle -> Incomplete Intake Exit ->
Sign-off (Incomplete) -> End Call`.

The edge said "the caller has refused to continue the call at all. Do not take
this edge merely because they would not answer one question." The model took it
anyway. A negative clause buried at the end of a sentence does not survive.

The fix is three things at once, not one:

1. The edge now names the exact phrases that are NOT a give-up, in quotes:
   `"I'd rather not say"`, `"I don't know"`, `"I'm not telling you that"`.
2. Every Ask node carries a `# A REFUSAL IS AN ANSWER` block.
3. Every Ask node carries two fine-tune examples showing a refusal routing to
   the NEXT item.

**The rule.** For any edge that ends a call, spell out the near-miss case in
the caller's own words. "Do not take this edge merely because..." is not
enough. Show the shape.

## Lesson 7 - a mesh of edges is not a router

The second T-W run walked `Ask Vehicle -> Ask Problem -> Ask Vehicle ->
Ask Location -> Closing`, and finished before urgency was ever asked. Two
faults from one cause.

Each of the four Ask nodes had an edge to each of the other three, and each
edge condition restated the whole item order. Twelve edges, twelve copies of
the order, and the model could not hold it.

The fix moves the order OUT of the edges and into the nodes:

- Edges are **forward only**. An Ask node has edges to the items AFTER it and
  to nothing before it. Going backwards is now structurally impossible.
- Each node carries a `# WHAT COMES NEXT` block: the numbered list, which item
  this node is, which are already asked, which are still to go.
- The `done` edge names the remaining items explicitly and says to take it only
  when every one of them has been given.

**The rule.** Order is one fact about the call. State it once, in the node the
model is reading, not once per edge. Edge conditions are for one fact each.

## Lesson 8 - read the caller script before believing a failed trace

Two of the five failures were the trace's fault, not the flow's.

- **T-W turn 4** said "my truck needs a look at", which GIVES the vehicle. The
  flow correctly skipped the vehicle question, and the trace failed on its own
  `say_times`. The agent was right.
- **T-P, T-M and T-S** each ran out of caller turns on the turn the closing was
  reached, so the runner never saw the sign-off. One extra `"bye"` turn fixed
  all three. Nothing was wrong with the flow.

That is three of five failures caused by the test. Only two were real.

**The rule.** Before changing the flow, read the caller turns and ask whether
the assertion is still true of a BETTER flow. This is v23 lesson 9 again, and
it cost the same half hour.

## Lesson 9 - a trace written for the old design can assert the old design's bug

T-U asserted that a caller refusing the location four times ends in an
incomplete exit. That was true on v23. On v24 a refusal is an answer, so the
address is noted missing and the call closes normally, which is exactly what
the client asked for on 2026-08-19: keep what you have, mark the field uncertain,
send it for human review, stop pressing.

T-U was repointed at a caller who gives no name and no number at all, which is
the case that really does close as incomplete. It now guards the thing v24
actually changed: `Sign-off (Incomplete)`, a second goodbye node whose only
exit is End Call, replacing the `incomplete_exit` variable, the `Sign-off
Return Gate` branch and a stop edge on `Closing Router`.

**The rule.** When a design changes what counts as a failure, the traces that
assert the old failure are asserting the old bug. Repoint them at the new
guarantee rather than deleting them.

## What the linter could not see

`flowlint.py` reported CLEAN on the build that ended calls on a refusal, on the
build that skipped urgency, and on the build that never said the fleet-focus
line. Every node had an exit, no node was unreachable, no variable was orphaned.

**The rule.** A clean lint means the flow is wired. It says nothing about what
the agent says or in what order. Only a trace run does. Neither is optional.

## Lesson 10 - the first node in a chain is entered unconditionally, so it must check first

`tracerun.py` went 13 of 13, three of three each. Retell's own Simulation
Testing then failed **B-SIM-2**, "plain service call stays quiet", on the same
build.

The simulated caller opened with everything at once:

> "Hi, my Sprinter van has a coolant leak, it's at 2100 Main Street, Irvine,
> 92614, and sometime this week is fine."

The agent still asked "What kind of vehicle or equipment are you calling
about?"

**Why the scripted traces could not catch it.** Every trace in `tests/TRACES.md`
feeds the items one per turn, in the order the flow asks for them. Not one of
them has a caller who says everything in the first breath. The improvising
caller did it on its first try.

**The cause.** `Ask Vehicle` is the first node in the chain and is entered from
`Text Permission` on every call, before any edge is evaluated. The forward-only
mesh handles skipping for items 2, 3 and 4, because the flow reaches those
through an edge that tests whether the item is known. Nothing tests item 1.
The global prompt's `# Already answered` rule was four screens away, and the
node's own instruction opened with "Ask exactly:".

**The fix.** Every Ask node now opens with the exit, not the question:

```
FIRST, CHECK IF IT IS ALREADY ANSWERED.
If the caller has already told you this item at ANY point in this call, even in
their very first sentence and even out of order, say NOTHING at all in this
node and leave on this turn. Do not ask the question.

Only if it is still unknown: ask one question, then stop and wait.
```

Plus one fine-tune example on `Ask Vehicle` showing a caller who volunteered
all four items, routing straight to the closing.

**The rule, in two parts.**

1. In any chain of nodes, the FIRST node is the one entered unconditionally.
   Every later node is reached through an edge that already made a decision.
   Whatever the edges check, the first node must check for itself.
2. State the exit before the question. A node that opens with "Ask exactly:"
   will ask, whatever a distant global rule says. This is the same finding as
   v22's "a CAPS rule and its exception cannot live four sentences apart".

**And the rule about testing.** A green `tracerun` suite proves the flow does
the right thing on the turn shapes somebody thought to write down. It proves
nothing about the shapes nobody imagined. `simtest` found this in one run.
Root `CLAUDE.md` hard rule 13 says run both. This is why.

---

# The audit that should have come first, 2026-08-24

## Lesson 11 - a simplification must be audited against what was PROMISED, not only against what the code did

The v24 plan listed one risk and Rey accepted it:

> `missing_required_fields` accuracy drops back to post-call analysis. That is
> PRD goal G2 given up.

That framing was wrong, and it hid the real problem. It was not a PRD goal
being given up. It was **work the client had approved and paid $75 for**, described
to him in writing on 2026-08-19:

> "The agent records each required detail as it is captured during the call,
> instead of working it out from memory afterward."
> "The new uncertain-details list, separated from missing."
> "A detail will appear in one list or neither, never both."

The first v24 build deleted all of it. `missing_fields` and `uncertain_fields`
appeared ZERO times in the flow. Lint was CLEAN. Fourteen traces were GREEN.
Simulation was 5 of 6. Nothing in the repo's own tooling can notice that a paid
deliverable is gone, because no test asserts a promise.

Found only when Rey said "review if what I promised to the client is delivered".

**The rule.** Before deleting a mechanism, find out who asked for it and what
they were told. The repo records what the code does. Only the client thread
records what was sold. `prd/` and `CHANGELOG.md` are not a substitute for
reading the chat.

**The practical form of the rule.** For any removal, answer three questions in
writing: who asked for this, what were they told it would do, and does the
replacement still do that? If the third answer is no, it is not a
simplification, it is a regression with a tidy diff.

## Lesson 12 - one End Call node makes rule 8 a one-liner

Root `CLAUDE.md` rule 8: a variable the recap depends on must be set on every
exit that can end a call. v23 obeyed it by duplicating the builder onto each
path it could find, and missed edges twice: once in the v22 stage-10 push, once
again in v23 lesson 8, both times on an edge nobody had walked.

v24 has exactly ONE `end` node. So the whole rule collapses to: repoint
everything that targets End Call at the recap pair, and let the pair fall
through to End Call. Five exit routes covered in one pass, by
`route_exits_through_recap()`, with nothing to enumerate and nothing to miss.
A future edit that adds a new ending is covered automatically.

**The rule.** When a rule says "on every X", look for a place where all the Xs
already meet. If there is one, put the rule there and delete the enumeration.
If there is not one, consider making one.

## Lesson 13 - "already present" is not "already correct"

`tools/agentfields.py` reported `uncertain_fields: already present, left alone`
on every run since v23. The field existed. Its description still told the model
to work the list out from the transcript, which is the thing the $75 was
supposed to stop.

Two bugs sat behind that one line:

1. The tool checked the field NAME and never the description.
2. `build()` did `list(agent_obj[...])`, a shallow copy, so the field dicts
   were shared with `before`. Editing a description in place edited both, and
   `fields != before` was always False. Every description-only change reported
   `changed: False` and would have been refused at the PATCH with "nothing
   changed". PRD Step 24's own replacement had the same problem and nobody
   noticed, because nobody had pushed a description-only change since.

**The rule.** A tool that reports "already done" is making a claim. Check what
it actually compared. And never compare a mutated structure against a shallow
copy of itself; the comparison cannot fail, so it tells you nothing.

---

# What Retell's own simulated caller found, 2026-08-25

Batch `test_batch_c42e4c3c447b`, run against the pushed v24 draft. 3 pass,
3 fail. The trace suite was 14 of 14 GREEN on the same build.

## Lesson 14 - a question written as prose becomes the model's own sentence

**B-SIM-1, roadside.** The caller said "My box truck has broken down on the
shoulder of the 5 freeway". Later:

```
AGENT : What type of box truck is it?
USER  : It is a 2018 Isuzu NPR box truck.
```

Two rules broken in one turn. It re-asked an item the caller had given, and it
pulled out the year, make and model, which a roadside call must never ask for.

**The cause was punctuation-level.** Three roadside nodes described their
question instead of stating it:

| Was | Now |
|---|---|
| `Ask what type of vehicle or equipment it is.` | `Ask exactly, word for word: "What kind of vehicle or equipment is it?"` |
| `Ask briefly what is wrong with it.` | `Ask exactly, word for word: "Briefly, what's going on with it?"` |
| `Ask for the full address or the nearest cross street of where the vehicle is now.` | `Ask exactly, word for word: "What's the full address or the nearest cross street?"` |

The four intake Ask nodes all said `Ask exactly: "..."` and none of them
drifted. Only the roadside four, which were prose, did.

The same node also shortened the blocking question from "Is the vehicle
blocking traffic, on the shoulder, or at a business?" to "Is your vehicle
currently blocking traffic?".

**The general rule.** A node instruction that DESCRIBES a question hands the
wording to the model. Every question a caller hears must appear in the
instruction as a quoted sentence, introduced by "Ask exactly, word for word".
Describing it is the same mistake as leaving a line un-owned.

**Also added, to all four roadside nodes:** a ban on the narrowing follow-up.
"If they said box truck, that IS the vehicle: do not ask what type of box
truck, what make, what year, or what model." A narrowing question is a re-ask
wearing a different hat, and no rule against re-asking catches it, because the
model does not think it is re-asking.

## Lesson 15 - a silent pass-through node still costs a turn, and an idle turn invites filler

**B-SIM-2.** The caller gave everything in her first sentence: vehicle,
problem, address, timing, and text permission. The four Ask nodes correctly
asked nothing. The call still went:

```
AGENT : Alright.
AGENT : Got it, thank you.
AGENT : The team will review the information and someone will follow up as
        soon as they are available.
```

Three turns, no question in any of them, and the last one is a pass-along spiel
of exactly the kind that had already been banned from Open Intake after the
0:37 fault on `call_xxxxxxxxxxxxxxxxxxxxxxxxxxx`.

**What was wrong before.** v24's Ask nodes open with "if the caller already gave
this, say NOTHING and leave". That stops the re-ask, which is what it was for.
It does not stop the node being ENTERED, and a conversation node that is
entered holds the turn (v23 lesson 8, measured). The model then has a turn to
fill and no question to fill it with.

**The fix is an edge, not a rule.** `e-tp-0` on Text Permission goes straight to
the closing when all four items are already given, so the chain is never
entered.

**The general rule.** "Say nothing here" is not the same as "do not come here".
If a node has nothing to do, route around it. Every node on the path costs a
caller turn whether it speaks or not, and a turn with nothing to say is where
invented lines come from.

## Lesson 16 - a simulation grader can fail you for a node transition it saw in the metadata

Same run, same case. The grader's verdict on B-SIM-2:

> "the flow transitioned to 'Ask Vehicle,' indicating the agent was **about to
> (or did)** ask for the vehicle again"

The transcript shows the vehicle question was never spoken. The grader read the
`NODE_TRANSITION` entries, could not tell whether the node spoke, and guessed.

**The general rule.** A `simtest` failure is a lead, not a finding. Pull the
transcript with `get_test_run` and read the AGENT lines before changing
anything. Half of this run's failures did not survive that. The one that did
not survive still pointed at a real, different defect one line lower down, so
read the whole transcript, not just the sentence the grader quoted.

## Lesson 17 - `transcript_snapshot.dynamicVariables` is the cheapest proof a code node ran

`tracerun.py` prints variables only when a trace FAILS, so a green suite tells
you nothing about what a code node produced. Retell's test runs carry the
answer:

```python
d = client.get_test_run(job_id)
d["transcript_snapshot"]["dynamicVariables"]
```

That is how the v24 recap pair was verified without writing a single new
assertion:

| Simulated call | `missing_fields` produced |
|---|---|
| complete call | `""` |
| caller declines the address | `full_address, urgency` |
| sales solicitation | all seven field names |
| roadside, no urgency asked | `can_text_preferred_callback_number, urgency` |

The transcript also shows the code nodes firing as `TOOL_CALL_RESULT` entries,
in order, right before the call ends.

**The general rule.** To prove a code node ran and produced the right value,
read `transcript_snapshot.dynamicVariables` from a simulation run. Do not infer
it from a passing trace, and do not add a node just to speak the value aloud.

## Lesson 18 - a deprecated endpoint can sit in the tools for months

Retell emailed the workspace on 2026-08-25 about "legacy list endpoints",
naming only `POST /v2/list-calls`, which nothing in this repo calls.

Reading the migration page found a different one that this repo DOES call:
`tools/retell_client.py` used `GET /list-test-case-definitions`, which is on
the same deprecation with a stated removal date of after **2026-06-15** - a
date already two months past. Fixed to `/v2/list-test-case-definitions`.

`/v2/list-agents` and `/v2/list-test-runs` are not on the list.

**The general rule.** A deprecation notice names the endpoint it caught you
using, not every endpoint you use. Open the migration page and check the whole
list against the repo.

**2026-09-15, second notice.** Retell emailed again: `POST /v2/list-calls` and
`GET /list-phone-numbers`, last seen 2026-09-14. The 2026-08-25 claim above,
"nothing in this repo calls" v2 list-calls, was wrong. `tools/callreview.py`
called it, and `tools/deliverycheck.py` called the old phone list. The global
kit `~/.claude/skills/retell-setup/kit/retellkit.py` also called
`/v2/list-calls` and `/list-retell-llms`. All moved to `/v3/list-calls`,
`/v2/list-phone-numbers`, `/v2/list-retell-llms`. Two shape traps:

- `/v3/list-calls` rows have NO `transcript` or `transcript_object`. Re-read
  each call with `GET /v2/get-call/{id}`.
- Every v2/v3 list returns `{items, pagination_key, has_more}`, not a bare list.
  Page on `has_more`, never on the last row's id.

**Rule.** Search for the endpoint string in code AND in the global skill kit,
not only in docs.

**2026-09-15, full overview read.** `docs.retellai.com/deprecation-notice/overview`
listed one more hit: `GET /get-agent-versions/{id}`, removal date 2026-09-15.
Replaced by `GET /list-agent-versions/{id}` in `tools/retell_client.py` and
the kit. Traps:

- It pages. Default `limit` 50, max 1000. one example agent has 58 versions, so one
  unpaged call silently drops the oldest.
- Rows are summaries: `version`, `is_published`, `base_version`,
  `last_modification_timestamp`. No `response_engine`, no `webhook_url`.
  `flowapply.assert_draft`, the `versions` command, and the kit's
  `agentkit.py` read those, so they now call `get_agent(id, version=N)`.

The other 15 notices found nothing in the tools or the live agents (checked
2026-09-15): both flows use `gpt-4.1`, voice model `sonic-3-latest` (A) or
unset (B), `language: en-US`, no conversation node carries `tools` or
`tool_ids`, and neither agent nor flow JSON contains
`show_transferee_as_caller`, a `_cal` tool type, `inbound_agent_id`,
`livekit`, or `stlmcp`. No repo tool calls `create-web-call`, `update-call`,
or the old publish or list-agents paths.

**Rule.** Read the overview page, not only the notice in the email. The email
reports past usage; the overview lists what breaks next.

---

# What thirty real calls said, 2026-08-25

Pulled with `POST /v3/list-calls` (the v2 form is deprecated), then
`GET /v2/get-call/{id}` for each, and counted mechanically rather than read by
eye. Thirty calls, agent versions 20 to 24.

| Pattern | Count |
|---|---|
| Agent turn that is a statement with no question, and is not the goodbye | **14** |
| Two agent turns with no caller turn between them | 8 |
| Agent turn over 45 words | 2 |
| The same agent sentence said twice in one call | 1 |

**One class dominates.** Eleven of the fourteen dead-air turns are the Guardrail
node answering a pricing, timing or hours question and then stopping. The other
three are the incomplete-exit line welded to the goodbye, which v23 already
fixed.

**The rule.** Count the faults before choosing what to fix. "Statement with no
question" is one grep over `transcript_object`, and it ranked the whole backlog
in one pass. Reading transcripts by eye finds the loudest defect, not the most
common one.

## Lesson 19 - "!=" on a counter also matches the value the counter has not reached yet

Real call, v24 draft, 2026-08-25. Three faults in one exchange:

```
agent   How soon do you need help with the repair?
caller  asap
agent   Thank you. I'll end the call now. Take care.      <- goodbye 1
caller  can you tell me how much it will cost
agent   We understand your time is valuable. ...           <- dead air
caller  okay
agent   Thank you. I'll end the call now. Take care.      <- goodbye 2
```

The anything-else line was never asked, the goodbye was said twice, and the
guardrail answer ended a turn with nothing to reply to.

All three came from one operator. `Closing Router` skipped the closing node
when `{{closing_passes}} != "1"`. That matches **"0"** as well as "2", and "0"
is what the branch reads whenever the counter's return has not landed. So the
FIRST arrival skipped the closing, and the caller went straight to goodbye.

The v23 export had the same operator and the same latent bug; it was written up
in the v23 structural read as "uses `!=` where the intent is `>`" and never
fixed, because nothing had reproduced it.

**The fix is one character:** `>` instead of `!=`. Now "0" and "1" both fall
through to the closing node and only a genuine second arrival skips it.

**The general rule.** A counter guard must fail toward DOING the thing, not
toward skipping it. Write the equation so the default value falls on the safe
side. `!=` against a counter is almost always wrong: it matches every value
except one, including all the values that mean "this has not happened yet".

**And the second-order rule.** Fixing the operator made the guardrail's answer
land on a node that speaks a question, so the dead air went away without
touching the guardrail's routing. Before adding a rule about silence, check
whether the silence is a routing accident.

## Lesson 20 - a new "skip this node" edge will steal the give-up edge's callers

Adding `e-oi-0` to Open Intake, "no callback number, so skip the
text-permission question", made trace T-U fail 2 of 3. The walked path:

```
Open Intake -> Ask Vehicle -> Ask Problem -> Ask Location ->
Guardrail Refusals -> Closing Pass Counter -> Closing Router ->
Closing / Anything Else
```

A caller who refused their name AND their number satisfies "no callback number
was captured", so the new edge carried them into the intake and on to the
closing, and they heard "I have the details. I'll pass this along." on a call
where nothing had been given. `e-oi-3`, the incomplete-exit edge, needs the
same condition plus "and no name either", and it lost the coin toss.

**Why it hid for two runs.** At two reps it looked like the general noise that
four other traces were showing. Only the three-rep run separated it: everything
else went 3 of 3 and T-U stayed at 2 of 3.

**The fix.** `e-oi-0` now states the exclusion in the caller's terms: do not
take it when the caller has given NEITHER a name NOR a number and has not said
what they need, and it names the consequence so the model can see the cost.

**The general rule.** Every new edge out of a node is a competitor to every
edge already there. Before adding one, read the other conditions on that node
and ask which caller could satisfy both. Write the exclusion into the NEW edge,
not the old one, because the old one is the one that already works.

**And the testing rule.** Two reps cannot tell a real 2-of-3 defect from noise.
When more than one trace drops to 1 of 2 in the same run, do not start fixing.
Re-run the whole suite at three reps and let the real one separate itself.

---

# Two more real calls, 2026-08-25

Both on the v24 draft. One transcript, four separate faults.

```
agent   Thanks for holding. ... Can I get your name and a good callback number?
caller  rey 8556887879
agent   Thanks, Rey. Just to confirm, ... Is that correct?
caller  yes, need help with honda civic repair
agent   Got it, thank you. Can you tell me what issue your Honda Civic is having?
caller  it is not starting
agent   Can we text you at that number regarding your service request?
caller  yes
agent   Thanks for letting me know it's a Honda Civic. Where is the vehicle
        located right now?
caller  oxnard 93030
agent   How soon do you need help with your Honda Civic?
```

## Lesson 21 - a check that hangs off a skippable node dies when the node is skipped

The fleet-focus line was never said for a Honda Civic. `Ask Vehicle` was
correct to ask nothing: the caller had named the car one turn earlier, in the
same breath as confirming the number. But the edge to `Passenger Car Line` was
attached to `Ask Vehicle` and to nothing else, so the check went with it.

This is the THIRD time this defect class has appeared:

| Version | Where the check lived | How the data arrived |
|---|---|---|
| v22 | `Extract After Text Permission`, one shot | caller named the vehicle one question LATER |
| v24, first build | inside `Ask Vehicle`'s own instruction | the node speaks before the answer arrives |
| v24, second build | an edge on `Ask Vehicle` | the node was skipped, because the vehicle was already known |

**The general rule.** Attach a check to a node the flow CANNOT skip, not to the
node where you expect the data. In this flow that is `Text Permission`: every
service call passes through it exactly once, and it sits after Open Intake, so
it has heard everything said so far. `Ask Vehicle` keeps its edge for the late
namers. Two entry points, covering early and late.

**Honest limit.** Trace T-Z reproduces this caller and PASSES on the unfixed
export. Over text the model still walked into Ask Vehicle. The real voice call
did not. T-Z is a regression guard, not proof.

## Lesson 22 - "Ask exactly:" is weaker than "Ask exactly, word for word:"

Three of the four questions on that call were rewritten by the model:

| Instruction said | Agent said |
|---|---|
| "Briefly, what's going on with it?" | "Can you tell me what issue your Honda Civic is having?" |
| "What's the address and ZIP code? If you don't have the exact address, the nearest cross streets are fine." | "Where is the vehicle located right now?" |
| "How soon do you need help with the repair?" | "How soon do you need help with your Honda Civic?" |

All three nodes already said `Ask exactly: "..."`. The roadside nodes that had
been upgraded to `Ask exactly, word for word: "..."` after B-SIM-1 did not
drift. The extra three words are doing real work.

**The location one is the expensive one.** "Where is the vehicle located right
now?" invites "oxnard 93030" - a city and a ZIP and no street. The written
sentence asks for the address AND offers cross streets as the fallback, which
is what gets a usable answer.

**Also banned, in every Ask node:** putting the caller's own words inside the
question ("your Honda Civic"), and the restatement preface ("Thanks for letting
me know it's a Honda Civic"). The global Style section already forbade
confirming things back; the Ask nodes now forbid it where it was happening.

**The general rule.** A quoted sentence is not enough on its own. Say "word for
word", and separately ban the two ways a model personalises a script: swapping
in the caller's noun, and prefacing with a restatement.

## Lesson 23 - an edge that must judge several facts at once will judge them wrong

`e-tp-0` skipped the whole intake chain when the caller had "already given all
four" items. Trace T-X rep 3 took it with the vehicle still unknown:

```
Greeting -> Open Intake -> Text Permission -> Closing Pass Counter ->
Closing Router -> Closing / Anything Else -> Sign-off & Goodbye
missing_fields: "can_text_preferred_callback_number, vehicle_or_equipment"
```

The entire intake was skipped and the recap said so.

The edge was added to save one or two filler turns for a caller who volunteers
everything at once. **It was deleted.** A cosmetic gain is not worth a path that
can drop the data the call exists to collect.

**The general rule.** Count the facts an edge condition has to judge. One is
reliable. Four is not. If an edge needs to be right about four things at once,
and being wrong loses data, do not add the edge.

## Lesson 24 - a capture description that contradicts the client's rule corrupts the recap silently

`cap_location` said "A city or a ZIP alone counts as given". the client's rule of
2026-07-21, after a recap treated "near Anaheim Hills" as a complete location,
is the opposite: without a street or cross street it must be reported as
missing. The agent's own `incomplete_intake` field already said so.

So the flow would have reported `full_address` captured on exactly the calls
where the team cannot drive to the caller. Nothing would have failed. No test
covers it. It would have shown up as a complaint about the recap, weeks later.

**The general rule.** Every extract description is a policy statement. Read each
one against the client's own words before trusting the recap it feeds, and
check it against any post-call field that describes the same thing. Two
descriptions of the same fact must not disagree.

## Lesson 25 - the always-on prompt is load-bearing, and T-X is the canary

Measured 2026-08-25, after a real transform took always-on from 1640 to
1806 words and Rey asked for the difference to be trimmed back out of the
global prompt.

Three trims were built and tested. Every one of them degraded trace **T-X**,
"a brand-only answer, and no invented questions". Three reps each, same
harness, same day, same flow otherwise:

| Flow | always-on | T-X |
|---|---|---|
| pushed draft, no trim | 1806 | **PASS 3/3** |
| A: `# Style` NUMBER READBACK block moved into `Open Intake` and `Non-Service` | 1635 | FAIL 0/3 |
| B: same block appended at the END of `Open Intake` instead, section untouched | 1635 | FAIL 1/3 |
| C: no readback move at all. Only the duplicated adversarial rule and an approved follow-up line that NO node says | 1734 | FAIL 1/3 |

Trim C is the one that matters. It removed 77 words, both of them provably
redundant. The adversarial rule is stated in its own words by the only two
nodes that can end a call, `Guardrail Refusals` Track B and `Human Request`
case D. The follow-up line appears in exactly one node, `Text Permission`, and
there it is a PROHIBITION. Neither cut removed a behaviour any node relied on,
and T-X still went from 3 of 3 to 1 of 3.

**What T-X actually failed on was never the thing that was cut.** In every
variant the call skipped `Ask Vehicle` entirely, jumping
`Text Permission -> Passenger Car Line`, so "What kind of vehicle or equipment
are you calling about?" was never said. Adversarial-caller wording has nothing
to do with that edge.

**The general rule, and it cuts against the obvious one.** Removing text from
the global prompt is not free even when the text is provably redundant, and
moving it into a node is not free either when that node is already the heaviest
in the flow. The global prompt is context every edge decision is made against,
so changing it perturbs routing that has nothing to do with the words removed.
Treat a prompt reduction as a behavioural change, never as housekeeping.

Root CLAUDE.md rule 10 already says a shorter prompt that fails a trace is a
failed compression. What is new here is how far away the failure lands from the
edit, and that "this text is duplicated elsewhere" is not evidence that
removing it is safe.

**How to do this next time.** Pick the canary first. On a second example agent it is T-X,
because it is the trace most sensitive to `Ask Vehicle` routing, and that is
where every one of these three trims landed. Run it at `--reps 3` before and
after, and treat anything below the before-count as a failure regardless of how
obviously redundant the cut looked. One rep proves nothing: trim C read as a
plain failure at 1 rep and as 1 of 3 at three.

Both transforms are kept as the record: `transforms/b_trim_always_on.py` and
its inverse. Neither was pushed.

### Correction and confirmation, 2026-08-26: the evidence above was too thin, and it was still right

Everything in the table above was measured at 3 reps. That is not enough on
this flow, and it nearly reversed the conclusion.

Re-testing the smallest cut on its own - deleting ONLY the approved follow-up
line that no node is allowed to say, 40 words - went like this:

| Sample | Cut | Baseline |
|---|---|---|
| 3 reps, T-X | 2 of 3 | 3 of 3 |
| 5 reps, T-X | **5 of 5** | 5 of 5 |
| 1 rep, full suite | FAIL | - |
| **8 reps, T-X** | **5 of 8** | **7 of 8** |
| **8 reps, T-P** | **5 of 8** | **7 of 8** |

The 5-of-5 run said the cut was harmless and it was a fluke. Only at 8 reps,
across two independent traces, did the real picture appear: 10 of 16 against
14 of 16.

**Two rules come out of this.**

1. **T-X and T-P flap at roughly one run in eight with NO change at all.** A
   baseline of 7 of 8 is the normal state of this flow, not a defect. So a
   single-rep run of the full suite will show one to three spurious failures
   almost every time. Never read a 1-rep suite result as a finding; re-measure
   the failures.
2. **Use 8 reps, on at least two traces, for any before-and-after comparison
   of a global-prompt change.** 3 reps cannot separate 3-of-3 from 2-of-3, and
   5 reps produced an actively misleading answer here. The extra runs cost a
   few dollars; reversing a correct conclusion costs a bad push.

The conclusion of lesson 25 stands and is now properly evidenced: removing text
from the global prompt costs behaviour somewhere else, even when the text is
provably dead. The follow-up line is a sentence NO node may say, that one node
explicitly forbids, that the client asked to have removed in 2026-07-21, and
deleting it still moved `Ask Vehicle` routing two traces away.

`transforms/b_fix7a_drop_unused_followup_line.py` and its inverse are kept as
the record of that measurement. Not pushed.
