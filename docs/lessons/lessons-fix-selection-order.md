# Lessons: choosing between fixes by test, not by argument

What happened when six candidate fixes were built for three defects and the
winners were picked by measurement instead of by argument, and what three
adversarial reviewers found afterwards.

Read `docs/lessons-v24-simplification.md` first for how v24 got its shape, and
`docs/lessons-v23-live-call-defects.md` for the defects that shape came from.

---

## The method, and why it was worth the money

Two candidate fixes were built for each defect, both linted, both round-tripped
against an inverse, then run against the same traces on the same harness the
same day. The loser was thrown away.

Every single time, the variant that reasoning favoured lost.

| Defect | Variant A | Variant B | Winner |
|---|---|---|---|
| `Text Permission` skipped on a passenger-car call | delete the offending edge | keep the edge, add a precondition, a rule and an example | **A**, T-AC 3/3 and T-X 3/3, against B's T-X **0/3** |
| the greeting replayed after a global node interrupted it | say-once guard in the greeting's own instruction | new edge on the global node, forward to the next real node | **A**, T-AD 3/3, against B's **0/3** |
| urgency language interrupting an unconfirmed safety check | tighten the global trigger, plus two negative examples | say-once guard inside both safety-line nodes | **A**, T-AE 3/3, against B's **0/3** |

The three losers were the three that looked more principled. Deleting an edge
felt cruder than ordering it. An edge felt more structural than a prompt rule.
A guard inside the node that speaks felt closer to the problem than a guard on
the trigger. All three were wrong, and only running them showed it.

**The general rule.** On a flow this size, an argument about which fix is more
structural is not evidence. Build both, run both, keep the receipts. Two
variants cost about ten minutes and a few dollars of sandbox time, which is
less than one wrong push costs to find and undo.

## Lesson 26 — a go-back outranks a matching edge on the same global node

The greeting-replay fix looked obvious: the caller is landing back on
`Greeting` because the global node's go-back sends them there, so give the
global node a real edge that goes FORWARD instead, conditioned on the
interrupted-greeting case. Both `Guardrail Refusals` and `Human Request` got
one, pointing at `Open Intake`.

Trace T-AD: **0 of 3**. The edge never fired once. The go-back won every time.

The fix that worked was the unglamorous one: tell `Greeting` not to say itself
twice. 3 of 3.

**The general rule.** You cannot steer a global node's exit by competing with
its go-back. When a global node hands a caller back into a node that speaks a
fixed line, fix the node that speaks. This is the `static_text` trap from
section 7 of the standard, except it bites ordinary `prompt` nodes too, and it
applies to any should-be-said-once line, not just greetings.

The same shape hit `Safety Line 1`, which replayed the 911 sentence after a
global took a turn mid-check. That broke v24's stated design guarantee that
"the 911 line is said at most twice, because there are exactly two nodes." A
go-back re-enters a node, and a re-entered node re-reads its instruction. Any
"said once because there is one node" guarantee in this flow is only true while
no global node interrupts.

## Lesson 26a — repairing a contradictory section beat deleting it, and deletion made things worse

2026-08-31. Eight Ask nodes on a second example agent ended with a `# WHAT COMES NEXT` section
that listed the other items with numbered line-start labels and closed with
"Go to the first one the caller has not already given." The nodes were asking
each other's questions.

Two candidates, same trace, `T-AH` at 5 reps each:

| Failing assertions, out of 5 reps | baseline | A, repair the section | B, delete the section |
|---|---|---|---|
| texting question | 1 | **0** | 3 |
| vehicle question | 3 | **0** | 0 |
| goodbye | 1 | **0** | 0 |
| problem question | 5 | 5 | 5 |
| TOTAL | 10 | **5** | 8 |

**Deletion was worse than the baseline it replaced** on the texting question,
1 of 5 to 3 of 5.

The case for deleting looked strong on paper and is worth writing down because
it was wrong: the section restated the item ORDER, which the edges already
carry; it restated "already asked, do not re-ask", which each node's own opening
block already says more precisely; and it restated "never ask another item",
which is its own CAPS section. Three restatements and two traps, so cut it.

What the measurement says: the restatement was load-bearing. Removing the list
of what remains took away the model's picture of the call, and it started
mishandling the question it DID own. Redundant text is not free to remove -
`docs/lessons-v22-overhaul.md` finding 1 already said duplicated paragraphs are
nearly free to KEEP, and this is the other half of that: they are not free to
delete.

**The general rule.** When a section contains both useful content and a
contradiction, repair the contradiction rather than removing the section. Reach
for deletion only when the measurement says the content is inert - and measure
before believing it is.

The residual failure in both columns, the problem question at 5 of 5, was traced
to a different node entirely: `Text Permission`, re-entered by a guardrail
go-back with its own question already answered, invents the NEXT node's question
and displaces the whole chain. Fixing eight nodes could not fix a defect that
starts in a ninth.

## Lesson 26b — "state the exit first" backfires when the exit and the job share a trigger

2026-08-31, the same day as 26a and the counter-example to it.

`Text Permission` was inventing the next node's question when a global node
handed the caller back to it. Diagnosis: anti-pattern 20, a node entered with
nothing to do fills its turn. Fix: a section placed FIRST, in the style the node
already used for its other precondition, saying that when the texting question
is already answered the node says nothing and takes its edge.

Measured at 5 reps: failing assertions went from 5 to 12. The texting question,
previously clean at 0 of 5, was never asked at all in 5 of 5.

**Two lessons, and the second is the useful one.**

Anti-pattern 15 says "state the exit first" because a loud rule beats a distant
exception. That advice assumes the exit is a rare special case. Here the exit
("already answered, say nothing") and the main job ("not answered, ask") are
decided by the SAME fact, so putting the exit first did not clarify an ordering,
it just gave the louder position to one of two competing readings. When two
branches turn on one condition, neither goes first: they belong in one block,
stated as a pair.

**The bigger one: the fix disproved the diagnosis.** The node invented a
question on a turn when it DID still have its own question to ask. So the
invention was never "a turn to fill with nothing to fill it". Anti-pattern 20
did not apply, and a fix built on it could not have worked no matter how it was
worded. A candidate that fails in a way the hypothesis cannot explain has told
you something more valuable than a candidate that passes: go back to the
diagnosis, not to the wording.

## Lesson 27 — a negative example moves a global trigger; more prose does not

Two separate cases, same session, same result.

| Case | The condition already said | With the clause alone | After 2 negative examples |
|---|---|---|---|
| a global node saying a contractual sentence a second time on a call that had already said it upstream | "Do NOT trigger ... on a call that already went through the safety gate" | 0 of 3 | 3 of 3 |
| an urgency trigger firing in the middle of an unconfirmed safety check | "DEFER to the Roadside / Safety Gate whenever ... a safety check is in progress and unconfirmed" | 0 of 3 | 3 of 3 |

In both, a plainly worded prohibition was already in the condition and was
already being ignored.

What made the examples work was **putting the distinguishing context in the
AGENT turns**. The user turn is nearly identical in the fire and no-fire cases
— "I need someone ASAP" either way. What separates them is what the agent said
immediately before, so the example has to carry it:

```json
{"transcript": [
  {"role": "agent", "content": "Are you and the vehicle in a safe location right now?"},
  {"role": "user",  "content": "I need help right now, ASAP, this is urgent"}
]}
```

A negative example whose only turn is the user's cannot teach the difference,
because there is no difference in the user's turn.

## Lesson 28 — a say-once guard phrased against the CALL breaks a per-node design

The containment fix for the 911 replay was to add, to both `Safety Line 1` and
`Safety Line 2`: "if you have already said the 911 sentence, do not say it
again."

Trace T-AE: **0 of 3**. The flow is SUPPOSED to say that sentence twice, once
in each node. `Safety Line 2` read `Safety Line 1`'s line as its own and went
quiet.

**The general rule.** Where two nodes each say the same sentence once by
design, a guard scoped to the call silences the second one. Scope it to the
node — "if YOU have already said this in THIS node" — or do not add it at all
and fix the cause instead.

## Lesson 29 — an exact-sentence count is blind to a paraphrase

Trace T-AC asserted the fleet-focus sentence exactly once and passed 3 of 3.
A hand-read transcript of the same flow, same day:

```
AGENT: We primarily focus on fleet and commercial vehicles, but I'll collect
       your details and pass them to the team for review. Where is your Toyota
       Camry sedan located?           <- improvised, not the approved wording
AGENT: Our primary focus is fleet trucks, trailers, RVs, generators, and
       equipment. I'll send your request to the right person for review.
                                      <- the approved sentence, counted, once
```

The caller heard the message twice. The count was 1 and correct. The node that
improvised had been told, in its own instruction, "Say NOTHING about it
yourself here; the Passenger Car Line node says the one approved sentence, and
only it may say it."

**The general rule.** `say_times` is evidence about a SENTENCE, never about a
topic. For anything contractual, read at least one full transcript by hand, or
grade it with an improvising caller who judges meaning. And add a positive
assertion that the node's own scripted question WAS asked, so a node that
speaks when told to stay silent is visible too.

This is why `tools/askcheck.py` exists.

## Lesson 30 — test evidence expires when someone edits the flow by hand

Rey edited `Guardrail Refusals` in the Retell UI during the session, reformatting
the instruction from 1424 to 1478 words. Content survived intact. It was caught
only because the `flowdiff` after the next push showed a change no transform had
made.

Same trace, same assertion, same harness, either side of that edit:

| Flow | Trace T-Z |
|---|---|
| baseline before the session's work | 4 of 5 |
| candidate, built on the pre-edit snapshot | 3 of 3 |
| the real draft, carrying the hand edit | 2 of 5 |

Nothing in the transform explained the drop.

**The general rule.** `flowpull` and `flowdiff` immediately before trusting a
test result, not only at the start of the work, and read the diff after every
push even when you are certain what you sent. A push that reports success tells
you the PATCH was accepted, not that the object you tested is the object now on
the server. If someone else has the UI open, assume the flow can move under you.

## Lesson 31 — an adversarial reviewer's "critical" finding may be a harness artifact

Three reviewers ran 21 improvised conversations. One returned two CRITICAL
findings: an endangered caller hung up on before the safety gate fired, and the
roadside branch unreachable when the caller confirms safety promptly.

Both were false, and both had the same cause: the scenario's real content was
in turn 1. **The chat sandbox is one turn behind a real call.** On a real
inbound call the agent plays the greeting unprompted; in the sandbox nothing
happens until you send something, so your first message is what produces the
greeting and its content is discarded.

Sent as turn 1, "I'm on the side of the road, there's traffic right next to me"
produced only the greeting and the safety gate never fired. The identical
sentence sent as turn 2, after a filler "hi", fired the gate, asked the safety
question, and walked the whole roadside chain correctly.

**The general rule.** Adversarial review is worth doing — the same three
reviewers found a real safety regression the whole trace suite missed. But
every finding is a LEAD. Reproduce it by hand before acting, and check the
harness before you check the flow. Had these two been taken at face value, the
next change would have been a "fix" to a safety path that already works.

Every scenario in `tools/askcheck.py` opens with a filler `"hi"` for this
reason.

## The one real thing the reviewers found

A regression introduced by the compliance pass earlier the same day. Making
"ASAP" a global trigger meant `Guardrail Refusals` could fire in the middle of
the SAFETY CHECK, because a caller whose safety is unconfirmed says ASAP a lot.
It answered with a non-safety line and its go-back replayed the 911 sentence.

No trace covered it. The suite was 21 of 21 green at the time. It took an
improvising caller to find it, and it was on the highest-stakes path in the
flow.

That is the argument for running both kinds of test, restated with a sharper
example than the one in `docs/lessons-v22-overhaul.md`: the scripted suite
proves the paths you thought of, and nothing else.

---

## Lesson 32 — instruction-body prose is the lever that keeps losing; triggers and edges are the ones that win

Added 2026-08-26, after two more rejected attempts. By this point the same
experiment has been run eleven times on this flow, so the pattern is worth
stating as a rule rather than as a run of bad luck.

**Platform backing, added 2026-08-29.** Retell's own debug guide reaches the same
conclusion from the other direction. Its first remedy for a node not following
its instruction is not better prose — it is "You can improve consistency by
splitting this into three separate nodes", followed by a stronger model for that
node, then finetune examples, then temperature
(<https://docs.retellai.com/build/conversation-flow/debug-guide>). Rewriting the
instruction body is not on their list at all.

Two of their rungs are levers this project has never pulled: a **per-node model**
and **temperature**. Both are real fields (see flow standard sections 3a and 15),
and neither is set on either agent. If instruction-body prose keeps losing, that
is where to look next rather than at a twelfth rewrite.

Sort every change this work has measured by WHAT it edited, not by what it was
trying to achieve:

| Edited | Change | Result |
|---|---|---|
| an edge, added or deleted | `b_fix1a` delete `e-tp-passenger` | **won**, T-AC 3/3 |
| routing, rewired | `b_fix5` recap before the goodbye | **won**, chain verified |
| a global node's CONDITION plus examples | `b_fix3a` case (e) defers to safety | **won**, 0/3 to 3/3 |
| a global node's CONDITION plus examples | `b_fix6a` solicitation as an intake answer | **won**, 0/3 to 3/3 |
| a global node's condition, negative examples | the T-AB double-say guard | **won**, 0/3 to 3/3 |
| instruction body, small node | `b_fix2a` greeting say-once | trace green, then a live CRITICAL: the model narrated its own silence |
| instruction body, small node | `b_fix4b` greeting re-asks | won, but only after `b_fix4a` lost |
| instruction body, deletion | `b_trim_always_on`, three variants | **lost**, all three |
| instruction body, deletion | `b_fix7a` drop the unused follow-up line | **lost**, 5/8 vs 7/8 |
| instruction body, addition | `b_fix1b` order the passenger edge | **lost**, T-X 0/3 |
| instruction body, addition | `b_fix3b` safety-line say-once guard | **lost**, T-AE 0/3 |
| instruction body, addition | `b_fix8` Guardrails closing-line ownership | **lost**, T-AI 4/8 vs 6/8 |
| instruction body, deletion | `b_fix9` Human Request stops wrapping up | **lost**, T-AI 3/8 vs 6/8 |

**Every structural change won. Every global-condition-plus-examples change won.
Almost every instruction-body edit lost.**

The two instruction-body wins are the exception that shows the shape: both were
on `Greeting`, the smallest node in the flow, and one of them shipped a live
defect anyway.

**The general rule.** On a flow this mature, the instruction body of a node is
near a local optimum. Perturbing it moves behaviour more or less at random, and
because there are far more ways to be worse than better, the expected value of
an instruction-body edit is negative. Reach for an edge, a routing change, or a
trigger condition with fine-tune examples. Treat "let me just add a sentence to
that node telling it not to do that" as the option of last resort, and require
an 8-rep before-and-after to keep it.

**What this does NOT mean.** It does not mean the remaining defects are
unfixable. It means they are not fixable by telling the node harder. The two
that were fixed this week, the recap builder and the sales hard stop, were both
fixed by moving something, not by rewording something.

Both rejected transforms are kept as the record:
`transforms/b_fix8_closing_line_one_owner.py` and
`transforms/b_fix9_human_request_hands_off.py`, each with an inverse. Neither
was pushed, and the draft was verified byte-identical to
`exports/v25-after-stage2.json` afterwards.

---

## Lesson 33 — a misaligned trace manufactures a defect rate that does not exist

The most expensive mistake of 2026-08-26, and the hardest to see.

Trace T-AI was written to reproduce a live defect. Its caller turns did not
answer the questions the agent actually asks. Turn 2 requested a person, which
fires `Human Request`, and that node asks "What do you need help with, so I can
note it for the team?" - to which the script's next line was **"Erica"**, a
name. Every turn after that was one behind, the call derailed differently on
each run, and the trace measured **5 to 6 of 8 with no change to the flow at
all**.

Three candidate fixes were then built and judged against that number. All three
came back at 3 to 4 of 8 and all three were rejected as regressions. They were
not regressions. They were inside the noise of a broken instrument.

**What exposed it.** A noop control. `transforms/noop.py` run through the same
`_combo.py` build path, producing a file verified byte-identical to the
baseline, scored **5 of 8** where the baseline file itself had scored 6 of 8
twice. Identical content, different number. That is the whole proof.

**Two rules.**

1. **Walk any new trace verbose ONCE before trusting a count from it.** One
   run, reading the transcript, would have shown "Erica" answering a question
   about a service need. It costs about twenty seconds and it would have saved
   most of a day.
2. **Run a noop control before any A/B you intend to act on.** Same build path,
   same harness, unchanged content. If the control does not match the baseline,
   the difference you are about to attribute to your fix is not there.

## Lesson 34 — confirm which node SPEAKS the line before fixing anything

Four attempts at one defect went to four different nodes, and the first three
were the wrong one:

| Attempt | Node edited | Result |
|---|---|---|
| `b_fix8` | `Guardrail Refusals` | worse |
| `b_fix9` | `Human Request` | worse |
| `b_fix10` | `Closing / Anything Else` | worse |
| `b_fix11` | `Guardrail Refusals` trigger, correct target found from the transcript | **3/8 to 14/16** |

And again on the next defect: `b_fix15` went to `Ask Location` and `Ask
Urgency`; the node hops showed the lines actually came from `Ask Vehicle` and
`Ask Problem`.

**The tell is always in the transcript, and it takes one verbose run.**
`tracerun --verbose` prints the node hop before every agent line. For item 6
the giveaway was "As mentioned, someone will follow up with you regarding
{issue}" - a template that exists in exactly ONE node's instruction, which
identified the culprit immediately once anyone looked.

**The rule.** Before writing a transform, run the failing trace once with
`--verbose` and read which node emitted the offending line. Grep the exact
sentence across the export to confirm which node owns it. Never infer the node
from the defect description, including one you wrote yourself.

## Lesson 35 — `finetune_conversation_examples` is the lever for what a node SAYS

Unused on both agents until 2026-08-26. It is the only thing that has ever
moved a node's own wording on this flow.

| Use | Trace | Before | After |
|---|---|---|---|
| `Open Intake` stops inventing reassurance lines | T-X canary | 5/8 | **8/8** |
| `Ask Location` and `Ask Urgency` say their scripted questions | T-AL | 0/8 | 3/8 |

Compare the prose attempts at the same class of defect, all of which lost.

**But it cannot teach silence.** `b_fix16` tried the mirror image: transition
examples ending on a USER turn, with no trailing agent line, to teach `Ask
Vehicle` and `Ask Problem` to leave without speaking when their item was
already given. T-AL went from 3/8 to **0/8**. Rejected.

**The rule.** Use conversation examples to fix what a node says wrongly. Do not
use any example to teach a node to say nothing - showing an absence teaches
nothing, and in measurement it actively hurt. A node that must sometimes stay
silent needs the choice moved out of the node, into an edge.

## Lesson 36 — confirmed twice more: a reactive rule cannot live in the node that asked

Structural swap 4 said it and this session measured it twice more.

Item 5, the garbled-location check. `# CITY AND ZIP` is a rule of the form "if
the caller says X, say Y" sitting inside `Ask Location`, the node that asked
the question:

| Fix | T-AK |
|---|---|
| baseline | 0 of 4 |
| four conversation examples on `Ask Location`, including the exact garbled answer and the exact question it should produce | **0 of 4** |
| the same question moved into its own node, reached by an edge | **4 of 4** |

The examples changed nothing, because the node never gets a turn in which to
react: it speaks on the turn it asks, and the caller's answer lands on the turn
it spends taking an edge.

**The rule, now with three independent measurements behind it.** If a spoken
line depends on what the caller just said, it needs its own node and an edge.
No amount of prose, and no number of examples, will make it fire from inside
the node that asked. Recognise the shape early: any instruction containing "if
the caller says", "when they answer", or "compare X and Y once" inside an Ask
node is already broken.


## Lesson 37 — measure the BASELINE before you judge a probabilistic fix

2026-08-27, a second example agent v26, the double "Anything else I should include?".

The fix was built, and the verification run came back RED: trace T-Y passed
only 4 of 5 reps. The obvious reading is "the fix does not work, do not push".

That reading was wrong. Running the SAME trace against the UNCHANGED export
gave the real picture:

| Export | T-Y, closing line said exactly once |
|---|---|
| v26, no fix | **1 of 5** |
| v26 + `b_fix_guardrail_owns_closing_question` | **4 of 5** |

The fix takes the failure rate from 80 percent to about 12 percent. Judged
against 5 of 5 it is a failure. Judged against what it replaced it is a large
win. Only the second judgement is useful.

**The rule.** A prompt-conditioned edge is a weighted coin, never a switch. A
red verdict on a probabilistic trace means nothing until the same trace has
been run at the same rep count against the export you are trying to beat. Run
the baseline BEFORE you decide the fix lost, not after.

The same run also caught two flaps that looked like regressions and were not.
T-P read 2 of 3 with the fix and 3 of 3 without it, which looks like damage;
re-run at 5 reps it was 5 of 5. T-AH read 2 of 3 on BOTH exports, so its
failure belonged to neither.

**Corollary.** Report the pair, never the single number. "T-Y 4 of 5" invites
the wrong decision. "T-Y 1 of 5 before, 4 of 5 after" makes the decision
obvious.

## Lesson 38 — a stale TEMPLATE outranks every prose rule that contradicts it

Same session, and this is the specific thing that moved T-Y from 0 of 2 to
3 of 3.

`Guardrail Refusals` held this near the bottom of its instruction:

    ANSWER FORMAT (FOLLOW FOR CASES a and d
    answer, next_question (or ask: "Anything else I should include?")

Three separate prose blocks higher up the same instruction were rewritten to
say the closing question may be asked at most once per call. The node kept
asking it twice anyway. The template was telling it to append that sentence to
EVERY case-(a) answer, and the template won.

| State | T-Y |
|---|---|
| three prose blocks fixed, template left alone | **0 of 2** |
| the same three blocks, template fixed too | **3 of 3** |

This is `docs/lessons-v22-overhaul.md`'s "an example outranks the rule it
contradicts", with a sharper edge on it: a **template** is an example. So is a
format string, a worked sample, and anything shaped like a fill-in-the-blank.
They are not documentation of the rules above them; they compete with them, and
they win.

**The rule.** When you change a rule in a node instruction, search that whole
instruction for anything shaped like an example, a template, or a format line,
and change it in the same edit. Searching for prose that states the old rule is
not enough. Grep the node for quotes, arrows, and `->` shapes.

## Lesson 39 — a "say it once" guard cannot be made deterministic by prompt

The last 1 in 5 of T-Y is a rep where the guardrail took the general finished
edge instead of the new bypass edge, and the Closing node then asked the
question again.

Three guards sit on that path: the edge condition, the node instruction, and a
guard on the Closing node. All three are prompt-level, because **nothing in
Retell exposes "what the agent has already said" to a branch equation.** A code
node can read dynamic variables; it cannot read the transcript.

So a counter can count ARRIVALS at a node, which is what `closing_passes`
does, and it can never count SAYINGS. A line with two possible sayers, one of
them a global node with no inbound edges, cannot be capped deterministically.

**The rule.** Give a caller-facing sentence exactly ONE sayer wherever you can.
When a second sayer is genuinely wanted, accept that the cap is probabilistic,
measure it, and state the residual rate in the changelog. Do not claim a
prompt-level guard is a guarantee.

`flowlint.py --line` cannot see this either: its double-say check walks EDGES,
and a global node has no inbound edges. It reported 0 unguarded of 8 paths on
the very export whose baseline was 1 of 5.

## Lesson 40 — a global node can PARK a caller, and you cannot rescue it from inside

Found 2026-08-29, the client a second example agent, `call_xxxxxxxxxxxxxxxxxxxxxxxxxxx`.

the client transferred a live the phone forwarding service call to the agent. The agent answered and
then would not hang up. It stayed on the line giving empty answers until he
gave up after 139 seconds. What he heard, from the recap transcript:

    User:  Are you gonna end the call?
    Agent: Nothing else is needed from you.
    User:  Hello?
    Agent: Your message will be passed along.
    User:  Are you gonna stay on the phone as long as I am?

The call record names the cause in two lines:

    current_node : Guardrail Refusals
    previous_node: Human Request

Three node moves in the whole call. The flow never moved again. The call ended
`user_hangup`, not because anything in the flow ended it.

### The shape

`Guardrail Refusals` is a global node with `else_edge: null`. All six of its
edges, and its go-back, presuppose progress the caller had not made:

    e-gr-closed-asked   needs "Anything else I should include?" already spoken
    e-gr-closed-added   the same, plus a new detail
    e-gr-done           needs every intake item captured, refused, or asked
    e-gr-message        needs a TRACK C AMBIGUOUS classification
    e-gr-abuse          needs a threat or extreme abuse
    e-gr-sales-stop     needs the hard-stop line already said

A caller who gives NOTHING satisfies NOTHING. Guardrail, FAQ and objection nodes
drift into this shape naturally, because their exits get written against the
caller who has already given their details.

Retell documents no forced exit. The global-node page covers the trigger, the
go-back and the re-trigger guard, and says nothing about the case where none of
them match. A parked caller is undefined behaviour.

### The fix that failed, and it failed completely

The obvious fix is to give the parked node the door it is missing. It was built
carefully: a seventh edge, ordered FIRST so it is evaluated before every edge
that assumes intake, with two positive transition examples carrying the real
caller's own turns.

| Fix | T-AO, the real call replayed |
|---|---|
| baseline `v29-deadend-baseline` | 0 of 8 |
| A, escape edge on `Guardrail Refusals` itself | **0 of 8** |
| B, route the caller OUT of `Human Request` one hop earlier | **15 of 16** |
| B2, same as B with no transition examples | 3 of 8 |
| B3, same as B with one-user-turn examples | 7 of 8 |

Variant A never fired once in eight runs, and the walked path was byte-identical
to the parked live call every time:

    Greeting -> Human Request -> Guardrail Refusals -> (no further hops)

**The rule. Do not fix a parked global node from inside it. Stop the caller
reaching it.** Find the node that hands them in and give THAT node the exit.
Prefer a node that already owns the right wording and already has working exits
over a new escape hatch: variant B's destination, `Non-Service / Message`,
already held the exact sentence the client approved for this caller on 2026-08-12.

Lesson 26 already said a go-back outranks a matching edge on the same global
node. This is that rule at its worst, and it was written down in this repo
BEFORE variant A was built. Reasoning still picked the loser. Build both,
measure both — lesson 24, confirmed for the twelfth time.

### The examples were worth 12 of 16 reps

B2 is variant B with the two transition examples deleted and nothing else
changed: 3 of 8 against B's 15 of 16. Lesson 27 measured again on a different
node and a different decision. The condition prose was identical in both.

B3 trimmed each example to a single user turn, on the theory that showing the
agent its own line was what cost `T-AI`. It recovered T-AO only to 7 of 8 and
did not recover T-AI, so it bought nothing. Kept as the record.

### Two backstops that will not save you

- `end_call_after_silence_ms` only measures SILENCE. This caller kept talking,
  so it reset on every turn. It was set to 45000 and never fired.
- `max_call_duration_ms` is the real ceiling. It was 362000, so the exposure was
  six minutes of dead air on a live business line.

Never describe either as protection against a stuck caller.

### The part that is not about Retell at all

This was the THIRD report of one defect class. On 2026-08-11 the client reported a
merchant-services call running "almost four minutes". The reply that day named
the general cause correctly — "it can happen on ANY call" — and on 2026-08-12
the client stated the general rule. It was built in `Non-Service / Message`, the
node where the problem had been noticed, and the requirements log marked it
`OK`. It was never built anywhere else, and seventeen days later a caller
arrived through `Human Request` and hit the identical wall.

**A requirement is `OK` only when every path that can meet the caller it
describes is covered.** "Built in the node where I first noticed it" is not
`OK`. Before marking any requirement done, name the nodes a matching caller can
actually be standing in. That correction is now written into
the client's own requirements log for this decision.

### The stale-baseline trap, again

`T-P` measured 4 of 8 on the candidate, against a documented band of "6 to 8 of
8 on every version measured". That reads as a regression. It is not: measured on
the same v29 draft with NO transform applied, `T-P` is 5 of 8. The band was
recorded on an older version and had rotted. Lesson 37 says measure the baseline
before judging a probabilistic fix; this adds that a baseline written down
weeks ago is not a baseline.

## Lesson 41 — a routing edge inherits none of its destination node's guards

2026-08-29. `Text Permission` had ONE forward edge into the intake chain, so a
caller who named the vehicle in their opening sentence still landed on
`Ask Vehicle` with nothing to ask. The remedy from the standard is to route
around the node rather than tell it to be silent, so `Text Permission` was given
a forward fan-out: edges to `Ask Problem`, `Ask Location`, `Ask Urgency` and the
closing, each firing on the first item the caller had not given.

`Ask Vehicle` opens with a hard rule that its own item is not what it looks
like:

> "my Toyota", "the Ford", "a Chevy" all name a MAKE. A make on its own, with
> or without a year, leaves this item UNKNOWN.

**The new edges did not have that rule, and nothing gave it to them.** The
guard was written into `e-tp-1` only, because that is the edge that goes to
`Ask Vehicle`. The other three said merely "the caller has ALREADY said what
kind of vehicle or equipment it is", so "my Toyota" satisfied them, `e-tp-5`
fired, and `Ask Vehicle` was skipped entirely.

That is the exact defect `T-X` was written to catch, from the real call
`call_xxxxxxxxxxxxxxxxxxxxxxxxxxx`, reintroduced by the fix meant to help.

| Variant | T-X | T-AL | Combined |
|---|---|---|---|
| baseline v29, untouched | **8 of 8** | 1 of 8 | **9 of 16** |
| fan-out, guard on `e-tp-1` only | **3 of 8** | 4 of 8 | 7 of 16 |
| fan-out, guard on all four edges | 6 of 8 | 2 of 8 | 8 of 16 |

**The general rule.** An edge condition that decides whether an ITEM was given
is a second, independent judge of that item. It does not inherit the destination
node's definition of it, and it does not inherit the node's negative examples.
Every edge that decides an item must restate the item's definition in full,
including what does NOT count. Otherwise the edge decides the item more loosely
than the node would, and routes around the node that would have caught it.

**The second rule, which is the one that stopped the work.** Tightening the
guard did not recover the loss; it moved it. The strict version bought T-X back
to 6 of 8 and gave T-AL straight back. Neither variant beat leaving the flow
alone. **A fan-out multiplies the number of places a judgement can go wrong,
and on a probabilistic router that cost can exceed the benefit.** Both variants
were kept as the record and neither was pushed.

**What this does NOT overturn.** The underlying finding stands: a node entered
with nothing to ask still gets a turn, fills it, and personalises the next
node's question. "Say nothing here" remains unbuildable. What this measures is
that ROUTING AROUND the node at the chain's entrance is not automatically the
cheaper fix, and must be measured against the traces that guard the node being
skipped — not only against the trace that motivated the change.

## Lesson 42 — inert for the mechanism it names is not the same as useless

2026-08-29. `Sign-off & Goodbye` opened with:

    Say exactly: "OK, thank you. I'll end the call now. Take care." Then end
    the call immediately. No pause, no separate "Goodbye."

"Then end the call immediately" is provably inert as ROUTING. The node has no
`skip_response_edge`; `e-so-1`, `e-so-2` and its else edge are ordinary prompt
edges that need a caller turn. The node cannot end the call, and its own next
paragraph, "IF THE CALLER SPEAKS DURING THIS", concedes that it waits. The audit
listed it as a dead instruction and the transform deleted it.

**Deleting it changed behaviour, in both directions, measured at 8 reps:**

| Trace | Before | After |
|---|---|---|
| T-N, caller adds a detail at the close and must not be cut off | 5 of 8 | **8 of 8** |
| T-Y, closing asked once and goodbye said once | 7 of 8 | 5 of 8 (first pair) |

One sentence caused both. Without it the node is readier to take another turn:
it stops cutting off a caller who volunteers a late detail, and it becomes a
little likelier to say the goodbye twice. On the confirming pair T-Y came back
level at 7 of 8 against 7 of 8, so only the T-N gain survived — but the point
stands regardless of which trace moved.

**The general rule.** An instruction can be inert for the MECHANISM it names
and still be load-bearing for the model's OUTPUT. "End the call immediately"
cannot end a call, but it does suppress a further turn. Before deleting a rule
because the runtime cannot honour it literally, ask the second question:
**is it also functioning as a speech instruction?** A rule that names an
impossible action can still be shaping what the agent says, and the audit that
finds the impossibility is not by itself a licence to delete.

The safe procedure is the one that caught this: delete it, then run the traces
that guard the node's OTHER behaviours, not only the trace that exposed the
inert rule. Here the inert rule was found via `Sign-off & Goodbye` never ending
a silent call, and the movement showed up on a completely different trace about
a caller adding a detail.

**Corollary for the v29 audit.** Its Class B and Class C findings are correct
about what the runtime can and cannot do. They are NOT, on their own, a list of
safe deletions. Each one needs the same treatment.

## Lesson 43 — a global node's go_back is an EDGE, so a global node cannot "answer nothing and slip away"

2026-08-29, from Rey: **"go back conditions are triggered after user responds,
it is also an edge."**

That settles a question this repo had left open twice, and it makes a whole
class of instruction on the global nodes impossible.

The sequence when a global node fires is:

    caller speaks
      -> the global's trigger condition matches
      -> the global node is ENTERED and GENERATES A RESPONSE
      -> the caller responds again
      -> the go_back condition is evaluated, like any other edge
      -> control returns to the node the caller came from

So a `go_back` is not an escape hatch that runs instead of speaking. It runs
**after** the node has spoken and after the caller has answered. A global node
entered by mistake therefore costs a caller turn AND an agent utterance, every
time, and no instruction can prevent it.

**What this invalidates.** `Guardrail Refusals` carries three instructions built
on the opposite assumption:

- case (b), the catch-all: "Anything else, including an intake answer, location,
  detail, confirmation, correction, profanity, venting, or being told to stop ->
  say NOTHING here and return to the node the caller came from."
- "A dated deadline such as 'by Tuesday' or 'tomorrow morning' is NOT case (e);
  say nothing and go back."
- "If the tracked line has been said too, say NOTHING AT ALL here and go back."

None of them can happen. Case (b) is the one that matters, because it is the
catch-all: every spurious trigger of this global lands there, and the trigger is
a probabilistic prompt condition, so spurious triggers are normal. The node is
told to be silent, cannot be, and fills the turn - which is the mechanism behind
the mid-intake interjections this flow keeps producing.

**The general rule.** A global node has exactly the same speech contract as any
other conversation node: entered means spoken. Design its instruction around
what it should SAY when it fires wrongly, not around slipping away unheard. The
cheapest correct answer is usually to re-ask the pending item in the originating
node's exact wording, which Guardrails already does for cases (a) and (e) under
"AFTER THE ANSWER - IF ONE IS LEFT".

**Related.** Lesson 40 already established that a global node can PARK a caller
and cannot be rescued from inside. This is the same shape from the other side:
you cannot steer a global's exit with prose, because the exit is an edge and the
speech has already happened by the time it is evaluated.

---

## When three prompt fixes all land on the baseline, the defect is structural

Measured 2026-09-04, a second example agent v36 draft, `--model gpt-4.1`, 5 reps per cell.

The defect: `Ask Vehicle` is entered on a caller who ALREADY named the vehicle.
It correctly suppresses its own question, then asks `Ask Location`'s question
instead, in its own wording, with the caller's vehicle folded in:

    CALLER: Sprinter van with a coolant leak
    AGENT:  Can you tell me where the Sprinter van is located?

`Ask Location` never appears in the path, so its approved wording is never
spoken. the client has complained about repeated vehicle information twice.

| Candidate | What it changed | T-AL | T-W |
|---|---|---|---|
| baseline | nothing | 3/5 | 3/5 |
| `b_v38_edges_state_condition_not_command` | 12 edge conditions stopped opening with "Go here to ask for X" | 2/5 | 4/5 |
| `b_v39_drop_cross_node_finetune_line` | removed the fine-tune turn that speaks `Ask Problem`'s question inside `Ask Vehicle` | 3/5 | 2/5 |

Every cell is the baseline plus noise. Neither fix moved anything, and both
were well-reasoned: `v38` removed a literal instruction to ask, and `v39`
removed an example that performed the defect. Both were real faults in the
flow. Neither was THE fault.

**The rule.** Two independent prompt-level fixes that both land on the baseline
are not two failures. They are evidence that the cause is not in the prompt.
Stop writing a third. Ask instead what the node is FORCED to do.

Here the answer is plain once asked. `Text Permission -> Ask Vehicle` (`e-tp-1`)
is unconditional: it does not consult whether the vehicle is known. The node is
entered, the caller has just spoken, so the node owes a turn, and its own
question is suppressed. It has nothing to say and no silent exit, so it
improvises. That is the same shape as the Naomi re-ask in
[lessons-open-intake-reask.md](lessons-open-intake-reask.md): **a node with
nothing to say and no matching exit invents a turn.** Twice now, in two
different nodes, on two different days.

The structural answer already exists in the flow and is unused on this path.
`Intake Gate Check` computes `gate_next` and skips every finished item;
`Intake Gate Router` routes to it. Only the ask-chain consults it. Pointing
`e-tp-1` at `Gate Pass Counter` would let the gate choose the first unfinished
item, so `Ask Vehicle` is entered only when the vehicle is genuinely missing.
Not yet built: it burns one `gate_passes`, and `e-gate-bail` closes the call at
`gate_passes > 1`, so the counter has to be reasoned about before it is safe.

**The second rule, and the more expensive one.** `T-AL` asserts
`say_times {"Sprinter": 0}`. On a PASSING rep the agent said "Can you tell me
where the van is located right now?" - the same defect, one word different, and
the trace called it green. The measured 3/5 is not the defect rate. The defect
rate, read from the transcripts, is close to every run where the vehicle
arrives early. An exact-string count sizes the wording, never the behaviour.
Read the transcript before you believe a rate.
